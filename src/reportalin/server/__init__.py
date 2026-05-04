"""
RePORTaLiN MCP Server Package.

This package contains the production-ready Model Context Protocol (MCP)
server implementation for the RePORTaLiN clinical data system.

Modules:
    config: Configuration management with Pydantic Settings
    logger: Structured logging with structlog
    auth: Token-based authentication for FastAPI
    tools: MCP tool definitions with Pydantic models
    main: FastAPI application with SSE transport

Public API:
    - get_settings(): Get the application settings singleton
    - get_logger(): Get a structured logger instance
    - configure_logging(): Configure logging (call once at startup)
    - require_auth: FastAPI dependency for required authentication
    - optional_auth: FastAPI dependency for optional authentication
    - AuthContext: Authentication context dataclass
    - mcp: FastMCP server instance with registered tools
    - app: FastAPI application instance
    - run_server(): Start the server with uvicorn

Example:
    >>> from server import get_settings, get_logger, configure_logging
    >>> configure_logging()
    >>> settings = get_settings()
    >>> logger = get_logger(__name__)
    >>> logger.info("Server initialized", port=settings.mcp_port)

    # Or run the server directly:
    >>> from reportalin.server import run_server
    >>> run_server(host="0.0.0.0", port=8000)
"""

from reportalin.server.auth import (
    AuthContext,
    generate_token,
    optional_auth,
    require_auth,
    verify_token,
)
from reportalin.core.config import (
    Environment,
    LogLevel,
    Settings,
    get_project_root,
    get_settings,
)
from reportalin.core.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    get_request_id,
    set_request_id,
)
from reportalin.server.main import (
    app,
    base_app,
    create_app,
    create_secured_app,
    run_server,
)

# Security module exports (lazy import to avoid circular dependencies)
from reportalin.server.security import (
    AES256GCMCipher,
    InputValidationMiddleware,
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
    RotatableSecret,
    SecurityHeadersMiddleware,
)
from reportalin.server.tools import get_tool_registry, mcp

__all__ = [
    # Security
    "AES256GCMCipher",
    # Authentication
    "AuthContext",
    "Environment",
    "InputValidationMiddleware",
    "LogLevel",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "RateLimiter",
    "RotatableSecret",
    "SecurityHeadersMiddleware",
    # Configuration
    "Settings",
    # FastAPI Application
    "app",
    "base_app",
    "bind_context",
    "clear_context",
    # Logging
    "configure_logging",
    "create_app",
    "create_secured_app",
    "generate_token",
    "get_logger",
    "get_project_root",
    "get_request_id",
    "get_settings",
    "get_tool_registry",
    # MCP Server
    "mcp",
    "optional_auth",
    "require_auth",
    "run_server",
    "set_request_id",
    "verify_token",
]
