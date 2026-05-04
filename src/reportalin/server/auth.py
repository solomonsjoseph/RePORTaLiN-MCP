"""
Authentication Middleware and Utilities.

This module provides token-based authentication for the MCP server using
FastAPI dependencies. It supports both header-based and query parameter
authentication methods for flexibility in different client scenarios.

Design Decisions:
    - Bearer token authentication via Authorization header (preferred)
    - Optional query parameter fallback for WebSocket/SSE connections
    - Constant-time comparison to prevent timing attacks
    - Environment-aware: can be disabled in local development
    - All auth failures are logged for security auditing

Security Model:
    - Single shared token (MCP_AUTH_TOKEN) for server access
    - Token is never logged or exposed in error messages
    - Rate limiting should be implemented at the proxy/gateway level
    - For multi-user scenarios, consider JWT or OAuth2 in production

Usage:
    >>> from fastapi import FastAPI, Depends
    >>> from reportalin.server.auth import require_auth, AuthContext
    >>>
    >>> app = FastAPI()
    >>>
    >>> @app.get("/api/data")
    >>> async def get_data(auth: AuthContext = Depends(require_auth)):
    >>>     # auth.is_authenticated is True here
    >>>     return {"status": "ok"}

See Also:
    - server/config.py for MCP_AUTH_TOKEN and MCP_AUTH_ENABLED settings
    - server/logger.py for security audit logging
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from reportalin.core.config import get_settings
from reportalin.core.logging import get_logger
from reportalin.server.security.secrets import RotatableSecret

__all__ = [
    "AuthContext",
    "generate_token",
    "get_rotatable_secret",
    "get_token_from_request",
    "optional_auth",
    "require_auth",
    "verify_token",
]

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class AuthContext:
    """
    Authentication context passed to route handlers.

    This immutable dataclass contains authentication state and metadata.
    It is injected into route handlers via FastAPI's dependency system.

    Attributes:
        is_authenticated: Whether the request was successfully authenticated
        auth_method: How authentication was performed ('bearer', 'query', 'none')
        client_info: Optional client identification metadata
        timestamp: Unix timestamp when auth was performed

    Example:
        >>> def handler(auth: AuthContext = Depends(require_auth)):
        >>>     if auth.is_authenticated:
        >>>         logger.info("Authenticated request", method=auth.auth_method)
    """

    is_authenticated: bool
    auth_method: str = "none"
    client_info: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def age_seconds(self) -> float:
        """Get age of this auth context in seconds."""
        return time.time() - self.timestamp


# =============================================================================
# Token Utilities
# =============================================================================


def generate_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Uses secrets.token_hex for URL-safe, high-entropy tokens.

    Args:
        length: Number of bytes (output will be 2x this in hex chars)

    Returns:
        Hex-encoded random token

    Example:
        >>> token = generate_token(32)
        >>> len(token)
        64
    """
    return secrets.token_hex(length)


def verify_token(provided: str | None, expected: str | None) -> bool:
    """
    Verify a token using constant-time comparison.

    This function prevents timing attacks by ensuring the comparison
    takes the same amount of time regardless of where a mismatch occurs.

    Args:
        provided: The token provided by the client
        expected: The expected token from configuration

    Returns:
        True if tokens match, False otherwise

    Note:
        Returns False immediately if either token is None or empty,
        but still performs a dummy comparison to maintain timing.
    """
    if not provided or not expected:
        # Perform dummy comparison to prevent timing leak
        secrets.compare_digest("dummy", "dummy")
        return False

    # Use hmac.compare_digest for constant-time comparison
    # Hash both to normalize length before comparison
    provided_hash = hashlib.sha256(provided.encode()).digest()
    expected_hash = hashlib.sha256(expected.encode()).digest()

    return hmac.compare_digest(provided_hash, expected_hash)


# =============================================================================
# Token Extraction
# =============================================================================

# HTTP Bearer security scheme for OpenAPI documentation
_http_bearer = HTTPBearer(auto_error=False)


# =============================================================================
# Rotatable Secret Management
# =============================================================================


@lru_cache(maxsize=1)
def get_rotatable_secret() -> RotatableSecret:
    """
    Get the application's rotatable secret singleton.

    This function initializes a RotatableSecret that supports both
    the primary auth token and the previous token (for rotation).

    The grace period for rotated tokens is configured via:
    SECRET_ROTATION_GRACE_PERIOD_HOURS (default: 24 hours)

    Returns:
        RotatableSecret configured from environment variables

    Usage:
        >>> secret = get_rotatable_secret()
        >>> result = secret.validate(incoming_token)
        >>> if result.is_valid:
        ...     # Allow access
    """
    settings = get_settings()

    grace_period_seconds = settings.secret_rotation_grace_period_hours * 3600

    # Initialize with primary token
    primary_token = settings.get_auth_token()
    secret = RotatableSecret(
        initial_secret=primary_token,
        grace_period_seconds=grace_period_seconds,
    )

    # Add previous token if configured (for rotation)
    if settings.mcp_auth_token_previous:
        previous_token = settings.mcp_auth_token_previous.get_secret_value()
        if previous_token:
            # Manually add previous secret (already in rotation)
            import time as _time

            from reportalin.server.security.secrets import _SecretEntry

            expires_at = _time.time() + grace_period_seconds
            secret._previous = _SecretEntry.from_value(previous_token, expires_at)
            logger.info(
                "Previous auth token configured for rotation",
                grace_period_hours=settings.secret_rotation_grace_period_hours,
            )

    return secret


def reset_rotatable_secret() -> RotatableSecret:
    """
    Reset the rotatable secret cache and return a fresh instance.

    Useful for testing or after configuration changes.
    """
    get_rotatable_secret.cache_clear()
    return get_rotatable_secret()


async def get_token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> tuple[str | None, str]:
    """
    Extract authentication token from request.

    Checks the following locations in order:
    1. Authorization header (Bearer token) - preferred
    2. X-API-Key header - alternative header-based auth
    3. Query parameter 'token' - fallback for WebSocket/SSE

    Args:
        request: The incoming FastAPI request
        credentials: Bearer credentials if present

    Returns:
        Tuple of (token, method) where method describes extraction source
    """
    # 1. Check Bearer token in Authorization header
    if credentials and credentials.credentials:
        return credentials.credentials, "bearer"

    # 2. Check X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key, "api_key"

    # 3. Check query parameter (fallback for WebSocket/SSE)
    token_param = request.query_params.get("token")
    if token_param:
        return token_param, "query"

    return None, "none"


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def require_auth(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_http_bearer),
    ] = None,
) -> AuthContext:
    """
    FastAPI dependency that requires authentication.

    This dependency supports token rotation via RotatableSecret:
    - Primary token: Current active token
    - Previous token: Old token valid during grace period

    When a previous token is used, the response includes a header
    indicating the client should update their token.

    If authentication is disabled (MCP_AUTH_ENABLED=false), this will
    allow all requests but log a warning in production.

    Args:
        request: The incoming FastAPI request
        credentials: Bearer credentials extracted by FastAPI

    Returns:
        AuthContext with authentication details

    Raises:
        HTTPException: 401 Unauthorized if authentication fails

    Example:
        >>> @app.get("/api/protected")
        >>> async def protected_route(auth: AuthContext = Depends(require_auth)):
        >>>     return {"authenticated": auth.is_authenticated}
    """
    settings = get_settings()

    # Check if auth is disabled
    if not settings.mcp_auth_enabled:
        if settings.is_production:
            logger.warning(
                "Authentication disabled in production environment",
                remote_ip=request.client.host if request.client else "unknown",
            )
        return AuthContext(
            is_authenticated=True,
            auth_method="disabled",
            client_info={"remote_ip": request.client.host if request.client else None},
        )

    # Extract token from request
    token, method = await get_token_from_request(request, credentials)

    # Get the rotatable secret
    rotatable_secret = get_rotatable_secret()

    # Handle missing token configuration
    if not rotatable_secret.is_configured:
        if settings.is_local:
            # In local dev, generate a warning but allow access
            logger.warning(
                "No MCP_AUTH_TOKEN configured - allowing unauthenticated access in local mode"
            )
            return AuthContext(
                is_authenticated=True,
                auth_method="local_bypass",
                client_info={
                    "remote_ip": request.client.host if request.client else None
                },
            )
        else:
            # In non-local environments, this is a configuration error
            logger.error("MCP_AUTH_TOKEN not configured in non-local environment")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server authentication not configured",
            )

    # Validate the provided token using rotatable secret
    validation_result = rotatable_secret.validate(token)

    if not validation_result.is_valid:
        # Log the failed attempt (but never log the token!)
        logger.warning(
            "Authentication failed",
            method=method,
            remote_ip=request.client.host if request.client else "unknown",
            path=request.url.path,
            reason=validation_result.status.value,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if using previous token (rotation in progress)
    if validation_result.should_notify:
        logger.info(
            "Client using previous token during rotation",
            method=method,
            remote_ip=request.client.host if request.client else "unknown",
        )

    # Success!
    logger.debug(
        "Authentication successful",
        method=method,
        remote_ip=request.client.host if request.client else "unknown",
        using_primary=validation_result.is_primary,
    )

    return AuthContext(
        is_authenticated=True,
        auth_method=method,
        client_info={
            "remote_ip": request.client.host if request.client else None,
            "using_rotated_token": not validation_result.is_primary,
            "should_update_token": validation_result.should_notify,
        },
    )


async def optional_auth(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_http_bearer),
    ] = None,
) -> AuthContext:
    """
    FastAPI dependency for optional authentication.

    Unlike require_auth, this will not raise an exception if authentication
    fails. Instead, it returns an AuthContext with is_authenticated=False.

    Use this for routes that have different behavior for authenticated
    vs unauthenticated users.

    Args:
        request: The incoming FastAPI request
        credentials: Bearer credentials extracted by FastAPI

    Returns:
        AuthContext (check is_authenticated to determine auth status)

    Example:
        >>> @app.get("/api/data")
        >>> async def get_data(auth: AuthContext = Depends(optional_auth)):
        >>>     if auth.is_authenticated:
        >>>         return {"data": "full_data"}
        >>>     return {"data": "limited_data"}
    """
    settings = get_settings()

    # If auth is disabled, treat as authenticated
    if not settings.mcp_auth_enabled:
        return AuthContext(
            is_authenticated=True,
            auth_method="disabled",
            client_info={"remote_ip": request.client.host if request.client else None},
        )

    # Extract token from request
    token, method = await get_token_from_request(request, credentials)

    # No token provided
    if token is None:
        return AuthContext(
            is_authenticated=False,
            auth_method="none",
            client_info={"remote_ip": request.client.host if request.client else None},
        )

    # Get expected token
    expected_token = settings.get_auth_token()

    # No expected token configured
    if expected_token is None:
        if settings.is_local:
            return AuthContext(
                is_authenticated=True,
                auth_method="local_bypass",
                client_info={
                    "remote_ip": request.client.host if request.client else None
                },
            )
        return AuthContext(
            is_authenticated=False,
            auth_method="error",
            client_info={"error": "token not configured"},
        )

    # Verify token
    if verify_token(token, expected_token):
        return AuthContext(
            is_authenticated=True,
            auth_method=method,
            client_info={"remote_ip": request.client.host if request.client else None},
        )

    # Token provided but invalid
    logger.debug(
        "Invalid token provided (optional auth)",
        method=method,
        remote_ip=request.client.host if request.client else "unknown",
    )

    return AuthContext(
        is_authenticated=False,
        auth_method=method,
        client_info={"remote_ip": request.client.host if request.client else None},
    )


# =============================================================================
# Middleware (for use outside of dependency injection)
# =============================================================================

from collections.abc import Awaitable, Callable

from starlette.responses import Response

# Type alias for Starlette middleware
MiddlewareCallable = Callable[
    [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
]


def create_auth_middleware() -> MiddlewareCallable:
    """
    Create a middleware for authentication outside of route dependencies.

    This is useful for:
    - Starlette applications without FastAPI
    - Custom ASGI middleware chains
    - Non-HTTP transports (WebSocket, stdio)

    Returns:
        An async middleware function compatible with Starlette

    Example:
        >>> middleware = create_auth_middleware()
        >>> app.add_middleware(middleware)
    """

    async def auth_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()

        # Skip auth for health checks
        if request.url.path in ("/health", "/ready", "/metrics"):
            return await call_next(request)

        # Skip if auth disabled
        if not settings.mcp_auth_enabled:
            return await call_next(request)

        # Extract and verify token
        token, _method = await get_token_from_request(request, None)
        expected_token = settings.get_auth_token()

        if not verify_token(token, expected_token):
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing authentication token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)

    return auth_middleware
