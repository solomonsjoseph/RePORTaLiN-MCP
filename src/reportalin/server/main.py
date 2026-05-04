"""
MCP Server Entry Point and Transport Layer.

This module provides the FastAPI application that exposes the MCP server
via HTTP/SSE transport. It handles authentication, session management,
and routing to the underlying MCP tools.

SSE Handshake Flow (How LLM Clients Connect):
    The MCP protocol uses a request/response pattern over Server-Sent Events:

    1. LLM Client -> GET /mcp/sse (with Authorization: Bearer <token>)
       - Server validates auth token via MCPAuthMiddleware
       - Server establishes SSE stream connection
       - Server sends initial `endpoint` event with message URL

    2. Server -> Client (SSE): event: endpoint
       data: /mcp/messages?session_id=<uuid>
       - Client now knows where to POST JSON-RPC requests

    3. LLM Client -> POST /mcp/messages?session_id=<uuid>
       Content-Type: application/json
       {
         "jsonrpc": "2.0",
         "id": 1,
         "method": "tools/list",
         "params": {}
       }
       - Server processes via FastMCP's internal handler

    4. Server -> Client (SSE): event: message
       data: {"jsonrpc": "2.0", "id": 1, "result": {...}}
       - Client receives the tool list or call result

    This bidirectional pattern allows:
    - tools/list: Discover available tools and their schemas
    - tools/call: Execute tools with typed arguments
    - resources/list, resources/read: Access static resources
    - All while maintaining a single persistent connection

Security Model:
    - MCPAuthMiddleware wraps the FastMCP SSE app
    - Bearer token required for /mcp/* endpoints
    - Health endpoints (/health, /ready) are public for k8s probes
    - Constant-time token comparison prevents timing attacks

Design Decisions:
    - Delegate SSE/session handling to FastMCP (battle-tested, spec-compliant)
    - Wrap with ASGI middleware for auth (can't use FastAPI Depends on mounted app)
    - Keep SessionManager for custom analytics/monitoring only
    - Structured logging with request IDs for tracing

Usage:
    ```bash
    # Run with uvicorn (recommended)
    uv run uvicorn reportalin.server.main:app --host 0.0.0.0 --port 8000

    # Run with reload for development
    uv run uvicorn reportalin.server.main:app --host 0.0.0.0 --port 8000 --reload

    # Or use the Python entry point
    uv run python -m reportalin.server
    ```
"""

from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from reportalin.core.constants import PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION
from reportalin.server.auth import (
    AuthContext,
    optional_auth,
    require_auth,
    verify_token,
)
from reportalin.core.config import get_settings
from reportalin.core.logging import configure_logging, get_logger, set_request_id

# Security middleware imports
from reportalin.server.security.middleware import (
    InputValidationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from reportalin.server.security.rate_limiter import RateLimitConfig
from reportalin.server.tools import get_tool_registry, mcp

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = [
    "app",
    "base_app",
    "create_app",
    "create_secured_app",
    "run_server",
]

# Initialize logging first (must be before any logger calls)
configure_logging()
logger = get_logger(__name__)

# Get settings singleton
settings = get_settings()


# =============================================================================
# ASGI Middleware for MCP Authentication
# =============================================================================


class MCPAuthMiddleware:
    """
    ASGI middleware that enforces Bearer token authentication on MCP routes.

    This wraps the FastMCP SSE app to require valid authentication
    before allowing access to the SSE stream or message endpoints.

    Why ASGI middleware instead of FastAPI Depends?
        - FastMCP.sse_app() returns a Starlette app, not FastAPI routes
        - We cannot inject Depends() into a mounted sub-application
        - ASGI middleware runs before the mounted app processes the request

    Authentication Methods:
        - Authorization: Bearer <token> header (preferred)
        - ?token=<token> query parameter (for SSE clients that can't set headers)

    Attributes:
        app: The wrapped ASGI application (FastMCP's SSE app)
    """

    def __init__(self, app: ASGIApp) -> None:
        """
        Initialize middleware with the app to wrap.

        Args:
            app: The ASGI application to protect (FastMCP's SSE app)
        """
        self.app = app
        self._settings = get_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI interface - validates auth before forwarding to wrapped app.

        Args:
            scope: ASGI scope dict containing request info
            receive: ASGI receive callable for request body
            send: ASGI send callable for response
        """
        # Only intercept HTTP requests (pass through lifespan, websocket, etc.)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip auth if disabled in settings
        if not self._settings.mcp_auth_enabled:
            logger.debug("Auth disabled, passing through")
            await self.app(scope, receive, send)
            return

        # Extract token from Authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # Fallback: check query parameter (for SSE connections)
            query_string = scope.get("query_string", b"").decode()
            for param in query_string.split("&"):
                if param.startswith("token="):
                    token = param.split("=", 1)[1]
                    break

        # Validate token using constant-time comparison
        if not token:
            logger.warning(
                "MCP auth failed - no token",
                path=scope.get("path"),
            )
            await self._send_unauthorized(scope, receive, send)
            return

        # Get expected token from settings
        expected_token = (
            self._settings.mcp_auth_token.get_secret_value()
            if self._settings.mcp_auth_token
            else None
        )

        if not verify_token(token, expected_token):
            logger.warning(
                "MCP auth failed - invalid token",
                path=scope.get("path"),
            )
            # Return 401 Unauthorized
            await self._send_unauthorized(scope, receive, send)
            return

        # Auth passed - forward to MCP app
        logger.debug("MCP auth passed", path=scope.get("path"))
        await self.app(scope, receive, send)

    async def _send_unauthorized(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Send a 401 Unauthorized JSON response."""
        body = b'{"error": "unauthorized", "detail": "Valid Bearer token required"}'

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
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
# Request Tracing Middleware
# =============================================================================


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate and propagate request IDs for distributed tracing.

    Every request gets a unique ID that is:
    - Logged with all log entries during that request
    - Returned in X-Request-ID response header
    - Accepted from X-Request-ID request header if provided
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """Generate/extract request ID and propagate through request lifecycle."""
        # Use provided ID or generate new one
        request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)

        # Set in context for structured logging
        set_request_id(request_id)

        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Clear context after request completes
            set_request_id(None)


# =============================================================================
# Session Analytics (Optional - FastMCP handles actual sessions)
# =============================================================================


class SessionAnalytics:
    """
    Lightweight session tracking for analytics and monitoring.

    Note: FastMCP internally manages SSE sessions. This class provides
    additional metadata tracking for operational monitoring, not for
    protocol-level session management.

    Attributes:
        connections: Counter of total connections
        active_count: Current active connection estimate
    """

    def __init__(self) -> None:
        self._connections_total = 0
        self._active_estimate = 0
        self._lock = asyncio.Lock()

    async def record_connect(self) -> None:
        """Record a new connection."""
        async with self._lock:
            self._connections_total += 1
            self._active_estimate += 1

    async def record_disconnect(self) -> None:
        """Record a disconnection."""
        async with self._lock:
            self._active_estimate = max(0, self._active_estimate - 1)

    async def get_stats(self) -> dict[str, int]:
        """Get connection statistics.

        Returns:
            Dictionary with 'total_connections' and 'active_estimate' counts.
        """
        async with self._lock:
            return {
                "total_connections": self._connections_total,
                "active_estimate": self._active_estimate,
            }


# Global analytics instance (internal use only)
_session_analytics = SessionAnalytics()


# =============================================================================
# Application Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan handler for startup and shutdown events.

    Startup:
        - Log server configuration
        - Initialize resources

    Shutdown:
        - Clean up resources
        - Log shutdown event
    """
    # === Startup ===
    logger.info(
        "MCP Server starting",
        server=SERVER_NAME,
        version=SERVER_VERSION,
        protocol=PROTOCOL_VERSION,
        environment=settings.environment.value,
        host=settings.mcp_host,
        port=settings.mcp_port,
        auth_enabled=settings.mcp_auth_enabled,
        transport="sse",
    )

    yield

    # === Shutdown ===
    stats = await _session_analytics.get_stats()
    logger.info(
        "MCP Server stopped",
        total_connections=stats["total_connections"],
    )


# =============================================================================
# FastAPI Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Application Architecture:

        FastAPI (main app at /)
        │
        ├── Health Endpoints (public, no auth)
        │   ├── GET /health      - Liveness probe
        │   ├── GET /ready       - Readiness probe
        │   └── GET /status      - Detailed status (optional auth)
        │
        ├── Discovery Endpoints (auth required)
        │   ├── GET /tools       - Tool listing
        │   └── GET /info        - Server info
        │
        └── MCP Endpoints (mounted at /mcp, auth via middleware)
            ├── GET /mcp/sse     - SSE stream connection
            └── POST /mcp/messages - JSON-RPC message handler

    Returns:
        Configured FastAPI instance ready to serve MCP clients
    """
    fastapi_app = FastAPI(
        title=f"{SERVER_NAME} API",
        description=(
            "RePORTaLiN Model Context Protocol (MCP) Server - SECURE MODE\n\n"
            "This server exposes ONLY TWO authorized tools for secure clinical "
            "data feasibility queries via the MCP protocol over Server-Sent Events (SSE).\n\n"
            "## Security Model\n\n"
            "- **FORBIDDEN:** `./data/dataset/` (raw PHI - access blocked)\n"
            "- **ALLOWED:** `./results/` (de-identified data only)\n"
            "- **Zero-Trust Output:** No names, DOBs, or contact details\n\n"
            "## Quick Start\n\n"
            "1. **Connect** to `/mcp/sse` with `Authorization: Bearer <token>`\n"
            "2. **Wait** for `endpoint` event containing the message URL\n"
            "3. **Send** JSON-RPC 2.0 requests to the message URL\n"
            "4. **Receive** responses via the SSE stream\n\n"
            "## Available Tools (EXCLUSIVE LIST)\n\n"
            "- `explore_study_metadata`: High-level feasibility stats from metadata\n"
            "- `build_technical_request`: Construct data extraction concept sheets"
        ),
        version=SERVER_VERSION,
        lifespan=lifespan,
        # Only expose docs in local environment
        docs_url="/docs" if settings.is_local else None,
        redoc_url="/redoc" if settings.is_local else None,
        openapi_url="/openapi.json" if settings.is_local else None,
    )

    # Add request ID middleware for tracing
    fastapi_app.add_middleware(RequestIDMiddleware)

    # ==========================================================================
    # Security Middleware Stack (order matters - last added runs first)
    # ==========================================================================

    # 1. Security Headers - adds protective headers to all responses
    if settings.security_headers_enabled:
        fastapi_app.add_middleware(
            SecurityHeadersMiddleware,
            exclude_paths={"/health", "/ready"},
        )
        logger.debug("Security headers middleware enabled")

    # Configure CORS based on environment
    # In production, require explicit CORS origins (deny by default)
    if settings.is_production and not settings.cors_allowed_origins:
        cors_origins: list[str] = []  # Deny all cross-origin in production
        logger.warning(
            "CORS disabled in production - no origins configured. "
            "Set CORS_ALLOWED_ORIGINS to enable cross-origin requests."
        )
    else:
        cors_origins = ["*"] if settings.is_local else settings.cors_allowed_origins

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*", "Authorization", "X-Request-ID", "X-Session-ID"],
        expose_headers=[
            "X-Request-ID",
            "X-Session-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
    )

    # Mount the MCP SSE application with authentication middleware
    # FastMCP.sse_app() provides spec-compliant /sse and /messages endpoints
    mcp_sse_app = mcp.sse_app()
    authenticated_mcp_app = MCPAuthMiddleware(mcp_sse_app)
    fastapi_app.mount("/mcp", authenticated_mcp_app)

    logger.info(
        "MCP SSE app mounted",
        path="/mcp",
        endpoints=["/mcp/sse", "/mcp/messages"],
        auth_enabled=settings.mcp_auth_enabled,
    )

    # =========================================================================
    # Register Routes (defined inline to avoid module-level @app decorators)
    # =========================================================================

    # --- Health Endpoints (Public - No Authentication) ---

    @fastapi_app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health_check() -> JSONResponse:
        """
        Liveness probe for load balancers and Kubernetes.

        Returns 200 OK if the server process is running.
        This endpoint has no authentication requirement.

        Returns:
            JSON with status, server name, and version
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        )

    @fastapi_app.get("/ready", tags=["Health"], summary="Readiness probe")
    async def readiness_check() -> JSONResponse:
        """
        Readiness probe indicating server can accept traffic.

        In production, this could additionally check:
        - Database connectivity
        - Required external services
        - Memory/resource thresholds

        Returns:
            JSON with ready status
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ready": True,
                "server": SERVER_NAME,
            },
        )

    @fastapi_app.get("/status", tags=["Health"], summary="Server status")
    async def server_status(
        auth: AuthContext = Depends(optional_auth),
    ) -> JSONResponse:
        """
        Detailed server status with optional authentication.

        - **Public**: Returns basic operational status
        - **Authenticated**: Returns additional metadata and capabilities

        Args:
            auth: Optional authentication context (injected)

        Returns:
            JSON with server status and optional detailed info
        """
        base_status: dict[str, Any] = {
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "status": "operational",
        }

        if auth.is_authenticated:
            stats = await _session_analytics.get_stats()
            base_status.update(
                {
                    "environment": settings.environment.value,
                    "transport": "sse",
                    "mcp_endpoint": "/mcp/sse",
                    "connections": stats,
                    "capabilities": {
                        "tools": True,
                        "resources": True,
                        "prompts": False,
                    },
                    "privacy": {
                        "mode": settings.privacy_mode,
                        "k_anonymity_threshold": settings.min_k_anonymity,
                    },
                }
            )

        return JSONResponse(content=base_status)

    # --- Discovery Endpoints (Authentication Required) ---

    @fastapi_app.get("/tools", tags=["Discovery"], summary="List available tools")
    async def list_tools(
        auth: AuthContext = Depends(require_auth),
    ) -> JSONResponse:
        """
        List available MCP tools with metadata.

        This provides tool discovery outside the SSE stream for documentation
        and client configuration. For full JSON schemas, use the MCP protocol's
        `tools/list` method via the SSE stream.

        Args:
            auth: Required authentication context (injected)

        Returns:
            JSON with tool names and connection info
        """
        logger.info("Tool discovery requested", auth_method=auth.auth_method)

        registry = get_tool_registry()

        return JSONResponse(
            content={
                "server": registry["server_name"],
                "version": registry["version"],
                "tools": registry["registered_tools"],
                "resources": registry["registered_resources"],
                "mcp_endpoint": "/mcp/sse",
                "note": "Use MCP protocol tools/list for full JSON schemas",
            }
        )

    @fastapi_app.get("/info", tags=["Discovery"], summary="Server information")
    async def server_info(
        auth: AuthContext = Depends(require_auth),
    ) -> JSONResponse:
        """
        Get detailed server information and connection instructions.

        Args:
            auth: Required authentication context (injected)

        Returns:
            JSON with server metadata and connection details
        """
        return JSONResponse(
            content={
                "server_name": SERVER_NAME,
                "version": SERVER_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "transport": {
                    "type": "sse",
                    "sse_endpoint": "/mcp/sse",
                    "message_endpoint": "/mcp/messages",
                },
                "authentication": {
                    "type": "bearer",
                    "header": "Authorization",
                    "format": "Bearer <token>",
                    "query_param": "token (fallback for SSE)",
                },
                "documentation": {
                    "openapi": "/docs" if settings.is_local else None,
                    "redoc": "/redoc" if settings.is_local else None,
                },
                "connection_example": {
                    "curl_sse": 'curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/mcp/sse',
                    "note": "See /docs for interactive API documentation",
                },
            }
        )

    # --- Error Handlers ---

    @fastapi_app.exception_handler(status.HTTP_401_UNAUTHORIZED)
    async def unauthorized_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle 401 Unauthorized errors with proper WWW-Authenticate header."""
        logger.warning(
            "Unauthorized request",
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthorized",
                "detail": "Valid Bearer token required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @fastapi_app.exception_handler(status.HTTP_404_NOT_FOUND)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle 404 Not Found errors."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "not_found",
                "detail": f"Path not found: {request.url.path}",
                "hint": "MCP endpoints are at /mcp/sse and /mcp/messages",
            },
        )

    @fastapi_app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Handle unexpected exceptions gracefully.

        - Development: Expose full error details
        - Production: Hide internal error details
        """
        logger.error(
            "Unhandled exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            method=request.method,
        )

        # Don't expose internal errors in production
        detail = str(exc) if settings.is_local else "Internal server error"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "detail": detail,
            },
        )

    return fastapi_app


# Create the global application instances
# base_app is the FastAPI instance (for testing and direct access)
# app is the secured ASGI app (for production deployment)
base_app = create_app()


def create_secured_app(fastapi_app: FastAPI | None = None) -> ASGIApp:
    """
    Create the application wrapped with security middleware.

    This function wraps the FastAPI app with ASGI-level security
    middleware that must run before any request processing:

    1. Input Validation: Blocks oversized query params/headers
    2. Rate Limiting: Prevents DoS attacks

    Args:
        fastapi_app: Optional FastAPI app to wrap. If None, uses base_app.

    Returns:
        ASGI application with security middleware applied
    """
    app_to_wrap = fastapi_app or base_app
    settings = get_settings()

    # Start with the base FastAPI app
    secured: ASGIApp = app_to_wrap

    # Wrap with input validation middleware (innermost)
    if settings.input_validation_enabled:
        secured = InputValidationMiddleware(
            secured,
            max_query_param_length=settings.max_query_param_length,
            max_query_string_length=settings.max_query_string_length,
        )
        logger.info(
            "Input validation middleware enabled",
            max_query_param=settings.max_query_param_length,
            max_query_string=settings.max_query_string_length,
        )

    # Wrap with rate limiting middleware (outermost)
    if settings.rate_limit_enabled:
        rate_config = RateLimitConfig(
            requests_per_minute=settings.rate_limit_requests_per_minute,
            requests_per_second=settings.rate_limit_requests_per_second,
            burst_size=settings.rate_limit_burst_size,
            enabled=True,
        )
        secured = RateLimitMiddleware(
            secured,
            config=rate_config,
            exclude_paths={"/health", "/ready"},
        )
        logger.info(
            "Rate limiting middleware enabled",
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst_size=settings.rate_limit_burst_size,
        )

    return secured


# Create the secured app for production use
app = create_secured_app(base_app)


# =============================================================================
# CLI Entry Point
# =============================================================================


def run_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
) -> None:
    """
    Run the server using uvicorn.

    Args:
        host: Bind host (defaults to settings.mcp_host)
        port: Bind port (defaults to settings.mcp_port)
        reload: Enable auto-reload (only works in local environment)

    Raises:
        SystemExit: If uvicorn fails to start or encounters a fatal error.

    Example:
        >>> from reportalin.server.main import run_server
        >>> run_server(host="0.0.0.0", port=8000, reload=True)
    """
    import uvicorn

    final_host = host or settings.mcp_host
    final_port = port or settings.mcp_port

    logger.info(
        "Starting uvicorn",
        host=final_host,
        port=final_port,
        reload=reload and settings.is_local,
    )

    uvicorn.run(
        "server.main:app",
        host=final_host,
        port=final_port,
        reload=reload and settings.is_local,
        log_level=settings.log_level.value.lower(),
    )


if __name__ == "__main__":
    run_server()
