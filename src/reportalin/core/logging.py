"""
Structured Logging Configuration.

This module configures structlog for the MCP server with environment-aware
output formatting. In development, logs are pretty-printed with colors for
readability. In production, logs are output as compact JSON for machine parsing.

Design Decisions:
    - structlog for structured context and processor chains
    - Automatic format switching based on ENVIRONMENT setting
    - Request ID propagation via context variables
    - Sensitive data filtering in log output
    - Integration with Python's standard logging for library compatibility

Usage:
    >>> from server.logger import get_logger, configure_logging
    >>> configure_logging()  # Call once at startup
    >>> logger = get_logger(__name__)
    >>> logger.info("Server started", port=8000, transport="stdio")

Output Examples:
    Local (pretty):
        2025-12-05 10:30:00 [info     ] Server started    port=8000 transport=stdio

    Production (JSON):
        {"event":"Server started","port":8000,"transport":"stdio","timestamp":"2025-12-05T10:30:00Z","level":"info"}

See Also:
    - server/config.py for LOG_LEVEL and ENVIRONMENT settings
    - https://www.structlog.org/en/stable/ for structlog documentation
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.types import EventDict, Processor, WrappedLogger

__all__ = [
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_logger",
    "get_request_id",
    "set_request_id",
]

# Context variable for request-scoped data (e.g., request_id)
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Module-level flag to prevent duplicate configuration
_logging_configured = False


def get_request_id() -> str | None:
    """
    Get the current request ID from context.

    Returns:
        The request ID if set, None otherwise
    """
    return _request_id_ctx.get()


def set_request_id(request_id: str | None) -> None:
    """
    Set the request ID in context.

    Args:
        request_id: The request ID to set, or None to clear
    """
    _request_id_ctx.set(request_id)


# =============================================================================
# Custom Processors
# =============================================================================


def add_request_id(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Add request_id to log events from context variable.

    This processor automatically includes the current request ID in all
    log events, enabling request tracing across distributed systems.
    """
    request_id = get_request_id()
    if request_id is not None:
        event_dict["request_id"] = request_id
    return event_dict


def add_service_info(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Add service identification to log events.

    Includes service name and version for log aggregation and filtering.
    Uses constants from core module to ensure consistency.
    """
    from reportalin.core.constants import SERVER_NAME, SERVER_VERSION

    event_dict.setdefault("service", SERVER_NAME)
    event_dict.setdefault("version", SERVER_VERSION)
    return event_dict


def filter_sensitive_data(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Filter sensitive data from log events.

    Redacts or removes sensitive fields to prevent accidental exposure
    of credentials, tokens, or PHI in logs.

    Filtered fields:
        - password, passwd, secret, token, key, auth
        - Any field containing 'credential' or 'authorization'
    """
    sensitive_patterns = {
        "password",
        "passwd",
        "secret",
        "token",
        "key",
        "auth",
        "credential",
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "bearer",
    }

    def is_sensitive(key: str) -> bool:
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)

    filtered = {}
    for key, value in event_dict.items():
        if is_sensitive(key):
            filtered[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # Recursively filter nested dicts
            filtered[key] = {
                k: "[REDACTED]" if is_sensitive(k) else v for k, v in value.items()
            }
        else:
            filtered[key] = value

    return filtered


def add_timestamp(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Add ISO 8601 timestamp to log events.

    Uses UTC timezone for consistency across distributed systems.
    """
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


# =============================================================================
# Logger Configuration
# =============================================================================


def _get_processors(use_json: bool) -> list[Processor]:
    """
    Get the processor chain based on output format.

    Args:
        use_json: If True, output JSON; if False, output pretty console format

    Returns:
        List of structlog processors
    """
    # Common processors for all environments
    common_processors: list[Processor] = [
        # Add context from context variables
        structlog.contextvars.merge_contextvars,
        # Add log level
        structlog.stdlib.add_log_level,
        # Add request ID from context
        add_request_id,
        # Add service identification
        add_service_info,
        # Filter sensitive data
        filter_sensitive_data,
        # Process positional arguments
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add timestamp
        add_timestamp,
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
        # Handle unicode
        structlog.processors.UnicodeDecoder(),
    ]

    if use_json:
        # Production: JSON output
        return [
            *common_processors,
            # Render as JSON
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        return [
            *common_processors,
            # Pretty print with colors
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]


def configure_logging(
    level: str = "INFO",
    use_json: bool | None = None,
    force: bool = False,
) -> None:
    """
    Configure structlog for the application.

    This function should be called once at application startup, before
    any logging is performed. It configures both structlog and the
    standard library logging to work together.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: If True, use JSON output; if False, use pretty output.
                  If None, auto-detect from settings.
        force: If True, reconfigure even if already configured

    Example:
        >>> configure_logging(level="DEBUG", use_json=False)
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    global _logging_configured

    if _logging_configured and not force:
        return

    # Auto-detect format from settings if not specified
    if use_json is None:
        try:
            from server.config import get_settings

            settings = get_settings()
            use_json = settings.effective_log_format == "json"
            level = settings.log_level.value
        except Exception:
            # Fallback to pretty output if settings unavailable
            use_json = False

    # Get appropriate processors
    processors = _get_processors(use_json)

    # Configure structlog
    # CRITICAL: Use stderr for all log output to avoid corrupting stdio JSON-RPC stream
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging for third-party libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    # Reduce noise from verbose libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    _logging_configured = True


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        A bound structlog logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request", user_id=123)
    """
    # Ensure logging is configured
    if not _logging_configured:
        configure_logging()

    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent logs.

    Useful for adding request-scoped context like user_id, session_id, etc.

    Args:
        **kwargs: Key-value pairs to bind to the logging context

    Example:
        >>> bind_context(user_id=123, session_id="abc")
        >>> logger.info("Action performed")  # Includes user_id and session_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Should be called at the end of request handling to prevent
    context leakage between requests.
    """
    structlog.contextvars.clear_contextvars()
    set_request_id(None)


# =============================================================================
# Logging Mode Documentation
# =============================================================================

"""
How the Logger Switches Between Local and Production Modes
==========================================================

The logging format is determined by the `effective_log_format` property
in `server/config.py`, which follows this logic:

1. If `LOG_FORMAT` environment variable is explicitly set to 'json' or 'pretty',
   that format is used regardless of environment.

2. If `LOG_FORMAT` is 'auto' (the default), the format is determined by
   the `ENVIRONMENT` setting:

   - LOCAL or DEVELOPMENT → 'pretty' (colored, human-readable)
   - STAGING or PRODUCTION → 'json' (structured, machine-parseable)

Format Differences:
-------------------

Pretty Format (Local/Development):
    - Colored output for different log levels
    - Human-readable timestamps
    - Exception tracebacks formatted for readability
    - Key-value pairs displayed inline

    Example:
    2025-12-05 10:30:00 [info     ] Server started    port=8000 transport=stdio

JSON Format (Staging/Production):
    - Single-line JSON objects
    - ISO 8601 timestamps in UTC
    - All context fields as JSON properties
    - Easy to parse with log aggregation tools (ELK, Datadog, etc.)

    Example:
    {"event":"Server started","port":8000,"transport":"stdio","timestamp":"2025-12-05T10:30:00+00:00","level":"info","service":"reportalin-mcp"}

Usage in Code:
--------------

The format switching is automatic. Just use the logger normally:

    from server.logger import get_logger, configure_logging

    # Configure once at startup (auto-detects environment)
    configure_logging()

    # Get logger and use it
    logger = get_logger(__name__)
    logger.info("Server started", port=8000)

To force a specific format (useful for testing):

    configure_logging(use_json=True, force=True)   # Force JSON
    configure_logging(use_json=False, force=True)  # Force pretty
"""
