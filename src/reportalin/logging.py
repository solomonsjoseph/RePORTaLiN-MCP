"""Centralized logging configuration for RePORTaLiN-Agent.

This module provides a unified, hierarchical logging system following Python's
official logging best practices (2024/2025):
- Single centralized configuration point
- Hierarchical logger names
- No custom logging levels in library code
- Lazy logger initialization
- Structured logging via structlog
- Context propagation via contextvars
- Thread-safe and multiprocessing-safe
- Email notifications for ERROR/CRITICAL (optional)

Usage:
    # In application entry points (server, CLI, pipeline):
    from reportalin.logging import configure_logging
    configure_logging(level="INFO", format="json", enable_email=True)

    # In all other modules:
    from reportalin.logging import get_logger
    logger = get_logger(__name__)
    logger.info("message", key="value")
"""

import atexit
import logging
import logging.config
import logging.handlers
import os
import queue
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal

import structlog
from structlog.types import FilteringBoundLogger

__all__ = ["bind_context", "clear_context", "configure_logging", "get_logger", "unbind_context"]

# Context variable for request/operation-scoped logging context
_log_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})

# Configuration state tracking
_configured = False

# Email queue listener for async email notifications
_email_queue_listener: logging.handlers.QueueListener | None = None


def configure_logging(
    *,
    level: str | int = "INFO",
    format: Literal["json", "console"] = "console",
    log_file: str | Path | None = None,
    enable_email: bool = False,
    force: bool = False,
) -> None:
    """Configure the centralized logging system.

    This function should be called ONCE at application startup from entry points
    (server, CLI, pipeline scripts). It configures both stdlib logging and structlog.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) or int
        format: Output format - "json" for production, "console" for development
        log_file: Optional file path for logging output
        enable_email: Enable email notifications for ERROR/CRITICAL logs (default: False, opt-in only)
        force: Force reconfiguration even if already configured

    Environment Variables (for email notifications):
        SMTP_HOST: SMTP server hostname
        SMTP_PORT: SMTP server port (default: 587)
        SMTP_USERNAME: SMTP authentication username
        SMTP_PASSWORD: SMTP authentication password
        SMTP_USE_TLS: Use TLS (default: true)
        ERROR_EMAIL_TO: Recipient email address
        ERROR_EMAIL_FROM: Sender email address
        ERROR_EMAIL_SUBJECT_PREFIX: Email subject prefix (default: [RePORTaLiN Error])
        ERROR_EMAIL_LEVEL: Minimum log level for emails (default: ERROR)

    Raises:
        ValueError: If format is invalid or log_file path is invalid
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
        if not log_path.parent.exists():
            raise ValueError(f"Log file directory does not exist: {log_path.parent}")

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_path),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "default",
        }

    # Add email handler if enabled and configured (async via queue for non-blocking)
    if enable_email:
        if not _can_enable_email():
            raise ValueError(
                "Email logging is enabled but required environment variables are missing. "
                "Required: SMTP_HOST, ERROR_EMAIL_TO, ERROR_EMAIL_FROM. "
                "See .env.email.example for configuration template."
            )
        
        # Create queue for async email processing
        email_queue = queue.Queue(-1)  # Unbounded queue
        
        handlers["email_async"] = {
            "class": "logging.handlers.QueueHandler",
            "queue": email_queue,
        }
        
        # Create actual SMTP handler (runs in background thread)
        smtp_handler = _create_smtp_handler()
        
        # Start queue listener in background thread
        global _email_queue_listener
        _email_queue_listener = logging.handlers.QueueListener(
            email_queue,
            smtp_handler,
            respect_handler_level=True,
        )
        _email_queue_listener.start()
        
        # Ensure cleanup on exit
        atexit.register(_shutdown_email_queue)

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
        # Email DISABLED in lazy config (for tests/library usage)
        configure_logging(level="WARNING", format="console", enable_email=False)

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
    current = _log_context.get().copy()
    current.update(kwargs)
    _log_context.set(current)


def unbind_context(*keys: str) -> None:
    """Remove specific keys from the current context.

    Args:
        *keys: Keys to remove from context

    Examples:
        >>> unbind_context("request_id", "user_id")
    """
    current = _log_context.get().copy()
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
    context = _log_context.get()
    if context:
        event_dict.update(context)
    return event_dict


def _can_enable_email() -> bool:
    """Check if email notifications can be enabled based on environment variables."""
    required_vars = ["SMTP_HOST", "ERROR_EMAIL_TO", "ERROR_EMAIL_FROM"]
    return all(os.getenv(var) for var in required_vars)


def _get_gmail_smtp_config() -> tuple[str, int] | None:
    """Get Gmail SMTP configuration if Gmail is detected.
    
    Returns:
        Tuple of (host, port) for Gmail SMTP, or None if not Gmail.
        
    Note:
        Gmail requires App Passwords (not regular passwords) since May 2022.
        See: https://support.google.com/accounts/answer/185833
        
        To create an App Password:
        1. Enable 2-Step Verification on your Google Account
        2. Visit: https://myaccount.google.com/apppasswords
        3. Generate app-specific password for "Mail"
        4. Use that 16-character password in SMTP_PASSWORD env var
        
        IMPORTANT: For production, use a dedicated email service instead:
        - SendGrid (free tier: 100 emails/day)
        - Mailgun (free tier: 100 emails/day)  
        - AWS SES (pay-as-you-go)
        - Postmark (free tier: 100 emails/month)
        
        These services provide better deliverability, reliability, and features
        compared to Gmail SMTP which is rate-limited (500 emails/day).
    """
    email_from = os.getenv("ERROR_EMAIL_FROM", "").lower()
    
    # Detect Gmail addresses
    if "@gmail.com" in email_from or "@googlemail.com" in email_from:
        # Gmail SMTP with TLS (recommended)
        return ("smtp.gmail.com", 587)
    
    return None


def _create_smtp_handler() -> logging.handlers.SMTPHandler:
    """Create and configure SMTP handler for email notifications.
    
    Returns:
        Configured SMTPHandler instance.
        
    Raises:
        ValueError: If Gmail is detected but no App Password is configured.
    """
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    
    # Gmail-specific configuration
    gmail_config = _get_gmail_smtp_config()
    if gmail_config:
        smtp_host, smtp_port = gmail_config
        if not smtp_password:
            raise ValueError(
                "Gmail SMTP requires an App Password. "
                "Regular Gmail passwords do NOT work (deprecated since May 2022). "
                "\n\nTo create an App Password:"
                "\n1. Enable 2-Step Verification: https://myaccount.google.com/security"
                "\n2. Generate App Password: https://myaccount.google.com/apppasswords"
                "\n3. Set SMTP_PASSWORD env var to the 16-character app password"
                "\n\nIMPORTANT: For production, use a dedicated email service instead:"
                "\n- SendGrid (free tier: 100 emails/day)"
                "\n- Mailgun (free tier: 100 emails/day)"
                "\n- AWS SES (pay-as-you-go)"
            )
    
    # Create SMTP handler
    handler = logging.handlers.SMTPHandler(
        mailhost=(smtp_host, smtp_port),
        fromaddr=os.getenv("ERROR_EMAIL_FROM", "reportalin-mcp@localhost"),
        toaddrs=[os.getenv("ERROR_EMAIL_TO", "admin@localhost")],
        subject=f"{os.getenv('ERROR_EMAIL_SUBJECT_PREFIX', '[RePORTaLiN Error]')} Application Error",
        credentials=(smtp_username, smtp_password) if smtp_username else None,
        secure=() if use_tls else None,
        timeout=30,  # Add explicit timeout for Gmail
    )
    handler.setLevel(os.getenv("ERROR_EMAIL_LEVEL", "ERROR"))
    
    return handler


def _shutdown_email_queue() -> None:
    """Stop email queue listener gracefully on application shutdown.
    
    This ensures all queued email notifications are sent before the process exits.
    Registered via atexit when email logging is enabled.
    """
    global _email_queue_listener
    if _email_queue_listener:
        _email_queue_listener.stop()
        _email_queue_listener = None


# Export type for type hints
Logger = FilteringBoundLogger
