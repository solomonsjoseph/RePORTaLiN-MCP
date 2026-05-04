#!/usr/bin/env python3
"""
Security Middleware for MCP Server.

This module provides ASGI/FastAPI middleware for:
    - Security headers (CSP, X-Content-Type-Options, etc.)
    - Input validation (query param length limits)
    - Rate limiting integration

Why Middleware?
    - Applies uniformly to all requests before routing
    - Cannot be accidentally bypassed by new endpoints
    - Centralizes security logic for easier auditing

Standards Compliance:
    - OWASP Security Headers Checklist 2024
    - CSP Level 3 (Content Security Policy)
    - Referrer-Policy (strict-origin-when-cross-origin)

Usage:
    >>> from fastapi import FastAPI
    >>> from reportalin.server.security.middleware import SecurityHeadersMiddleware
    >>>
    >>> app = FastAPI()
    >>> app.add_middleware(SecurityHeadersMiddleware)

See Also:
    - server/main.py: Middleware registration
    - server/security/rate_limiter.py: Rate limiting backend
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware

from reportalin.server.security.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimiter,
    RateLimitResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = [
    # Middleware classes
    "InputValidationMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    # Constants (for customization)
    "DEFAULT_SECURITY_HEADERS",
    "MAX_HEADER_VALUE_LENGTH",
    "MAX_QUERY_PARAM_LENGTH",
    "MAX_QUERY_STRING_LENGTH",
]


# =============================================================================
# Constants
# =============================================================================

# Maximum allowed length for query parameters (prevent DoS via huge params)
MAX_QUERY_PARAM_LENGTH = 2048

# Maximum total query string length
MAX_QUERY_STRING_LENGTH = 8192

# Maximum header value length
MAX_HEADER_VALUE_LENGTH = 8192

# Security headers to add to all responses
# Based on OWASP Secure Headers Project recommendations
DEFAULT_SECURITY_HEADERS: dict[str, str] = {
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    # Prevent clickjacking
    "X-Frame-Options": "DENY",
    # Enable XSS filter (legacy browsers)
    "X-XSS-Protection": "1; mode=block",
    # Control referrer information
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Prevent caching of sensitive responses
    "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    # Content Security Policy - restrictive default
    # Allows self-origin only, inline styles for docs UI
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    ),
    # Cross-Origin policies
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    # Permissions Policy - disable unnecessary features
    "Permissions-Policy": (
        "accelerometer=(), "
        "camera=(), "
        "geolocation=(), "
        "gyroscope=(), "
        "magnetometer=(), "
        "microphone=(), "
        "payment=(), "
        "usb=()"
    ),
}


# =============================================================================
# Security Headers Middleware
# =============================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.

    This middleware adds headers recommended by OWASP and security best
    practices to protect against common web vulnerabilities:

    Headers Added:
        - X-Content-Type-Options: nosniff (prevent MIME sniffing)
        - X-Frame-Options: DENY (prevent clickjacking)
        - X-XSS-Protection: 1; mode=block (XSS filter)
        - Referrer-Policy: strict-origin-when-cross-origin
        - Content-Security-Policy: restrictive CSP
        - Cache-Control: no-store (prevent caching)
        - Various Cross-Origin policies

    Configuration:
        Pass custom headers dict to override defaults:

        >>> app.add_middleware(
        ...     SecurityHeadersMiddleware,
        ...     custom_headers={"X-Custom": "value"}
        ... )

    Note:
        Some headers may conflict with specific features (e.g., CSP
        may block external resources). Adjust as needed for your app.
    """

    def __init__(
        self,
        app: ASGIApp,
        custom_headers: dict[str, str] | None = None,
        exclude_paths: set[str] | None = None,
    ) -> None:
        """
        Initialize security headers middleware.

        Args:
            app: The ASGI application
            custom_headers: Additional headers to add/override defaults
            exclude_paths: Paths to exclude from header injection
        """
        super().__init__(app)
        self.headers = {**DEFAULT_SECURITY_HEADERS}
        if custom_headers:
            self.headers.update(custom_headers)
        self.exclude_paths = exclude_paths or set()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """Add security headers to response.

        Args:
            request: The incoming HTTP request.
            call_next: Callable to invoke the next middleware/handler.

        Returns:
            Response with security headers added.
        """
        response = await call_next(request)

        # Skip excluded paths (e.g., health checks)
        if request.url.path in self.exclude_paths:
            return response

        # Add security headers
        for name, value in self.headers.items():
            # Don't override if already set
            if name not in response.headers:
                response.headers[name] = value

        return response


# =============================================================================
# Input Validation Middleware
# =============================================================================


class InputValidationMiddleware:
    """
    ASGI middleware that validates request input parameters.

    This middleware protects against denial-of-service attacks via
    oversized inputs. It validates:

    - Query parameter individual lengths
    - Total query string length
    - Header value lengths

    Validation Limits:
        - Single query param: 2,048 bytes
        - Total query string: 8,192 bytes
        - Header value: 8,192 bytes

    Security Rationale:
        Large query parameters can:
        - Exhaust memory during parsing
        - Enable ReDoS attacks on regex validators
        - Bypass WAF rules via overflow

    Usage:
        >>> from starlette.applications import Starlette
        >>> app = Starlette()
        >>> app = InputValidationMiddleware(app)
    """

    def __init__(
        self,
        app: ASGIApp,
        max_query_param_length: int = MAX_QUERY_PARAM_LENGTH,
        max_query_string_length: int = MAX_QUERY_STRING_LENGTH,
        max_header_value_length: int = MAX_HEADER_VALUE_LENGTH,
    ) -> None:
        """
        Initialize input validation middleware.

        Args:
            app: The ASGI application to wrap
            max_query_param_length: Max bytes for single query param
            max_query_string_length: Max bytes for entire query string
            max_header_value_length: Max bytes for header values
        """
        self.app = app
        self.max_query_param_length = max_query_param_length
        self.max_query_string_length = max_query_string_length
        self.max_header_value_length = max_header_value_length

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """ASGI interface - validate inputs before forwarding.

        Args:
            scope: ASGI connection scope containing request metadata.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        # Only validate HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Validate query string length
        query_string = scope.get("query_string", b"")
        if len(query_string) > self.max_query_string_length:
            await self._send_error(
                send,
                status=414,
                error="query_string_too_long",
                detail=f"Query string exceeds {self.max_query_string_length} bytes",
            )
            return

        # Validate individual query parameters
        if query_string:
            try:
                query_str = query_string.decode("utf-8", errors="replace")
                for param in query_str.split("&"):
                    if len(param) > self.max_query_param_length:
                        await self._send_error(
                            send,
                            status=414,
                            error="query_param_too_long",
                            detail=f"Query parameter exceeds {self.max_query_param_length} bytes",
                        )
                        return
            except Exception:
                # If we can't parse, let downstream handle it
                pass

        # Validate header lengths
        headers = scope.get("headers", [])
        for name, value in headers:
            if len(value) > self.max_header_value_length:
                header_name = name.decode("utf-8", errors="replace")
                await self._send_error(
                    send,
                    status=431,
                    error="header_too_long",
                    detail=f"Header '{header_name}' exceeds {self.max_header_value_length} bytes",
                )
                return

        # Validation passed - forward to app
        await self.app(scope, receive, send)

    async def _send_error(
        self,
        send: Send,
        status: int,
        error: str,
        detail: str,
    ) -> None:
        """Send an error response.

        Args:
            send: ASGI send callable.
            status: HTTP status code (e.g., 414, 431).
            error: Short error code for machine parsing.
            detail: Human-readable error description.
        """
        import json

        body = json.dumps(
            {
                "error": error,
                "detail": detail,
            }
        ).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )


# =============================================================================
# Rate Limit Middleware
# =============================================================================


class RateLimitMiddleware:
    """
    ASGI middleware that enforces request rate limits.

    This middleware integrates with the RateLimiter backend to enforce
    per-client rate limits. Clients are identified by:

    1. X-Forwarded-For header (if behind proxy)
    2. X-Real-IP header (nginx)
    3. Client IP from connection

    Responses include rate limit headers:
        - X-RateLimit-Limit: Total requests allowed
        - X-RateLimit-Remaining: Requests remaining in window
        - X-RateLimit-Reset: Unix timestamp of window reset
        - Retry-After: Seconds to wait (when blocked)

    Configuration:
        >>> from reportalin.server.security.rate_limiter import RateLimitConfig
        >>> config = RateLimitConfig(requests_per_minute=60)
        >>> app = RateLimitMiddleware(app, config)

    Exclusions:
        Health check endpoints are excluded by default to allow
        monitoring systems unlimited access.
    """

    def __init__(
        self,
        app: ASGIApp,
        config: RateLimitConfig | None = None,
        limiter: RateLimiter | None = None,
        exclude_paths: set[str] | None = None,
        client_id_extractor: Callable[[Scope], str] | None = None,
    ) -> None:
        """
        Initialize rate limit middleware.

        Args:
            app: The ASGI application to wrap
            config: Rate limit configuration (creates InMemoryRateLimiter)
            limiter: Custom rate limiter (overrides config)
            exclude_paths: Paths exempt from rate limiting
            client_id_extractor: Custom function to extract client ID from scope
        """
        self.app = app

        # Use provided limiter or create from config
        if limiter:
            self.limiter = limiter
        else:
            config = config or RateLimitConfig()
            self.limiter = InMemoryRateLimiter(config)

        # Default exclusions: health checks
        self.exclude_paths = exclude_paths or {"/health", "/ready"}

        # Client ID extractor
        self.client_id_extractor = client_id_extractor or self._default_client_id

    def _default_client_id(self, scope: Scope) -> str:
        """Extract client identifier from request scope.

        Determines the client IP address for rate limiting purposes,
        handling various proxy configurations.

        Args:
            scope: ASGI connection scope containing headers and client info.

        Returns:
            Client IP address string, or "unknown" if not determinable.

        Priority:
            1. X-Forwarded-For (first IP, if behind proxy)
            2. X-Real-IP (nginx)
            3. Connection client IP
        """
        headers = dict(scope.get("headers", []))

        # Check X-Forwarded-For (may have multiple IPs)
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded:
            # Take first IP (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = headers.get(b"x-real-ip", b"").decode()
        if real_ip:
            return real_ip

        # Fall back to connection IP
        client = scope.get("client")
        if client:
            return client[0]

        return "unknown"

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """ASGI interface - enforce rate limits.

        Args:
            scope: ASGI connection scope containing request metadata.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        # Only apply to HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check exclusions
        path = scope.get("path", "")
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        # Extract client ID
        client_id = self.client_id_extractor(scope)

        # Check rate limit
        try:
            result = await self.limiter.check(client_id)
        except Exception:
            # On limiter failure, allow request (fail open)
            await self.app(scope, receive, send)
            return

        if not result.allowed:
            await self._send_rate_limit_error(send, result)
            return

        # Wrap send to add rate limit headers to response
        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for name, value in result.to_headers().items():
                    headers.append((name.lower().encode(), value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

    async def _send_rate_limit_error(
        self,
        send: Send,
        result: RateLimitResult,
    ) -> None:
        """Send 429 Too Many Requests response.

        Args:
            send: ASGI send callable.
            result: Rate limit check result with retry information.
        """
        import json

        body = json.dumps(
            {
                "error": "rate_limit_exceeded",
                "detail": "Too many requests. Please retry later.",
                "retry_after": int(result.retry_after) + 1,
            }
        ).encode("utf-8")

        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]

        # Add rate limit headers
        for name, value in result.to_headers().items():
            headers.append((name.lower().encode(), value.encode()))

        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )
