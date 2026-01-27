"""Centralized logging configuration for RePORTaLiN-Agent.

This module provides a unified, hierarchical logging system following Python's
official logging best practices (2024/2025) and 12-Factor App principles:
- Single centralized configuration point
- Hierarchical logger names
- No custom logging levels in library code
- Lazy logger initialization
- Structured logging via structlog
- Context propagation via contextvars
- Thread-safe and multiprocessing-safe
- All logs to stderr (12-Factor App compliant)

Usage:
    # In application entry points (server, CLI, pipeline):
    from reportalin.logging import configure_logging
    configure_logging(level="INFO", format="json")

    # In all other modules:
    from reportalin.logging import get_logger
    logger = get_logger(__name__)
    logger.info("message", key="value")

Note:
    For production error monitoring, use external services:
    - Sentry, Datadog, New Relic (APM/error tracking)
    - ELK, Splunk, Loki (log aggregation)
    - PagerDuty, Opsgenie (alert management)
"""

import logging
import logging.config
import logging.handlers
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal

import structlog
from structlog.types import FilteringBoundLogger

__all__ = [
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_logger",
    "unbind_context",
]

# Context variable for request/operation-scoped logging context
# Note: Using factory to avoid B039 mutable default warning
_log_context: ContextVar[dict[str, Any]] = ContextVar("log_context")

# Configuration state tracking
_configured = False


def configure_logging(
    *,
    level: str | int = "INFO",
    format: Literal["json", "console"] = "console",
    log_file: str | Path | None = None,
    force: bool = False,
) -> None:
    """Configure the centralized logging system.

    This function should be called ONCE at application startup from entry points
    (server, CLI, pipeline scripts). It configures both stdlib logging and structlog.

    All logs are written to stderr following 12-Factor App principles. For production
    error monitoring and alerting, use external services like Sentry, Datadog, or ELK.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) or int
        format: Output format - "json" for production, "console" for development
        log_file: Optional file path for logging output (in addition to stderr).
                  The directory will be auto-created if it doesn't exist.
        force: Force reconfiguration even if already configured (tests only)

    Raises:
        ValueError: If format is invalid
        RuntimeError: If called multiple times without force=True
    """
    global _configured

    if _configured and not force:
        raise RuntimeError(
            "Logging already configured. Use force=True to reconfigure, "
            "but this should only be done in tests.",
        )

    # Validate inputs
    if format not in ("json", "console"):
        raise ValueError(f"Invalid format: {format}. Must be 'json' or 'console'")

    if isinstance(level, str):
        level = level.upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {level}")

    # Build handler configuration
    handlers: dict[str, dict[str, Any]] = {
        "default": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "default",
        },
    }

    if log_file:
        log_path = Path(log_file)
        # Auto-create log directory if it doesn't exist (robust UX)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_path),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "default",
        }

    # Configure stdlib logging using dictConfig (best practice)
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(message)s",
            },
        },
        "handlers": handlers,
        "root": {
            "level": level,
            "handlers": list(handlers.keys()),
        },
        # Configure common third-party loggers
        "loggers": {
            "urllib3": {"level": "WARNING"},
            "requests": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "asyncio": {"level": "WARNING"},
        },
    }

    logging.config.dictConfig(logging_config)

    # Configure structlog processors based on format
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _merge_context_var,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if format == "json":
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:  # console
        processors = [
            *shared_processors,
            structlog.processors.ExceptionRenderer(),
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """Get a hierarchical logger instance.

    This is the ONLY way to obtain a logger in this codebase. Always use
    __name__ for the logger name to create a proper hierarchy.

    Args:
        name: Logger name, typically __name__ from the calling module.
              If None, returns root logger (discouraged except for entry points).

    Returns:
        A structlog BoundLogger instance with context support

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("processing_started", user_id=123)
        >>> logger.error("processing_failed", error=str(exc), user_id=123)
    """
    if not _configured:
        # Lazy configuration with sane defaults for library usage
        configure_logging(level="WARNING", format="console")

    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current context.

    Context is stored in a ContextVar and automatically included in all
    log messages within the current async task or thread. This is perfect
    for request IDs, user IDs, operation IDs, etc.

    Args:
        **kwargs: Key-value pairs to add to context

    Examples:
        >>> bind_context(request_id="abc-123", user_id=456)
        >>> logger.info("processing")  # Will include request_id and user_id
    """
    current = _log_context.get({}).copy()
    current.update(kwargs)
    _log_context.set(current)


def unbind_context(*keys: str) -> None:
    """Remove specific keys from the current context.

    Args:
        *keys: Keys to remove from context

    Examples:
        >>> unbind_context("request_id", "user_id")
    """
    current = _log_context.get({}).copy()
    for key in keys:
        current.pop(key, None)
    _log_context.set(current)


def clear_context() -> None:
    """Clear all context for the current async task or thread.

    Examples:
        >>> clear_context()
    """
    _log_context.set({})


def _merge_context_var(_: Any, __: Any, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Structlog processor to merge ContextVar into event dict.

    This is an internal processor used by structlog to inject our custom
    context into every log event.
    """
    context = _log_context.get({})
    if context:
        event_dict.update(context)
    return event_dict


# Export type for type hints
Logger = FilteringBoundLogger
