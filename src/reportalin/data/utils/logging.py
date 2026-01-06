#!/usr/bin/env python3
"""
Centralized Logging Module
===========================

Comprehensive logging system with custom SUCCESS level, dual output (file + console),
and intelligent filtering. Features timestamped files and automatic log directory creation.

New in v0.0.12:
- Enhanced verbose logging with detailed formatter
- VerboseLogger class for tree-view, step-by-step debugging
- Better error context and stack traces
- Timing information for all operations

Key Features
------------
- **Custom SUCCESS Level**: Between INFO and WARNING for successful operations
- **Dual Output**: Console (clean) and file (detailed) with independent filtering
- **Verbose Mode**: Tree-view logging with context managers (DEBUG level)
- **Timestamped Logs**: Automatic log file creation in ``.logs/`` directory
- **UTF-8 Support**: International character encoding
- **Progress Bar Integration**: Works seamlessly with tqdm

Log Levels
----------
- DEBUG (10): Verbose mode only - detailed file processing, timing, metrics
- INFO (20): Default - major steps and summaries
- SUCCESS (25): Custom level - successful completions (console + file)
- WARNING (30): Potential issues
- ERROR (40): Failures
- CRITICAL (50): Fatal errors

Console vs. File Output
-----------------------
- **Console**: Only SUCCESS, ERROR, and CRITICAL (keeps terminal clean)
- **File**: INFO or DEBUG (depending on --verbose flag) and above

Verbose Logging (VerboseLogger)
--------------------------------
The VerboseLogger class provides tree-view formatted output for detailed debugging:

Usage Example:
    >>> from reportalin.data.utils import logging as log
    >>> vlog = log.get_verbose_logger()
    >>>
    >>> with vlog.file_processing("data.xlsx", total_records=100):
    ...     vlog.metric("Total rows", 100)
    ...     with vlog.step("Loading data"):
    ...         vlog.detail("Reading sheet 1...")
    ...         vlog.timing("Load time", 0.45)

Output Format:
    ├─ Processing: data.xlsx (100 records)
    │  ├─ Total rows: 100
    │  ├─ Loading data
    │  │  │  Reading sheet 1...
    │  │  │  ⏱ Load time: 0.45s
    │  └─ ✓ Complete

VerboseLogger Methods:
    - file_processing(filename, total_records): Context manager for file-level operations
    - step(step_name): Context manager for processing steps
    - detail(message): Log detailed information
    - metric(label, value): Log metrics/statistics
    - timing(operation, seconds): Log operation timing
    - items_list(label, items, max_show): Log lists with truncation

Integration
-----------
Used by all pipeline modules:
    - reportalin.data.load_dictionary: Sheet and table processing
    - reportalin.data.extract: File extraction and duplicate column removal

See Also
--------
- User Guide: docs/sphinx/user_guide/usage.rst (Verbose Logging Details section)
- Developer Guide: docs/sphinx/developer_guide/architecture.rst (Logging System section)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    # Constants
    "SUCCESS",
    # Core functions
    "setup_logger",
    "get_logger",
    "get_log_file_path",
    # Convenience logging functions
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "success",
    # Classes
    "CustomFormatter",
    "VerboseLogger",
    # Verbose logging
    "get_verbose_logger",
]

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

_logger: logging.Logger | None = None
_log_file_path: str | None = None


class CustomFormatter(logging.Formatter):
    """Custom log formatter that properly handles the SUCCESS log level.

    Extends the standard Formatter to ensure SUCCESS level records display
    the correct level name in log output.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified log record.

        Args:
            record: The log record to format.

        Returns:
            The formatted log message string.
        """
        if record.levelno == SUCCESS:
            record.levelname = "SUCCESS"
        return super().format(record)


def setup_logger(
    name: str = "reportalin-specialist",
    log_level: int = logging.INFO,
    simple_mode: bool = False,
) -> logging.Logger:
    """Set up central logger with file and console handlers.

    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, etc.)
        simple_mode: If True, minimal console output (success/errors only)

    Note:
        This function is idempotent - if called multiple times, it returns
        the same logger instance. Parameters from subsequent calls are ignored.
        To reconfigure, manually reset the global _logger variable.
    """
    global _logger, _log_file_path

    if _logger is not None:
        # Log a debug message if parameters differ from initial setup
        if _logger.level != log_level:
            _logger.debug(
                f"setup_logger called with different log_level ({log_level}), but logger already initialized with level {_logger.level}"
            )
        return _logger

    _logger = logging.getLogger(name)
    _logger.setLevel(log_level)
    _logger.handlers.clear()

    logs_dir = Path(__file__).parents[4] / ".logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"{name}_{timestamp}.log"
    _log_file_path = str(log_file)

    # Use detailed format for verbose (DEBUG) logging
    if log_level == logging.DEBUG:
        file_formatter = CustomFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
    else:
        file_formatter = CustomFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)

    # Console handler: behavior depends on simple_mode
    # CRITICAL: Use stderr, NOT stdout, for MCP server compatibility.
    # MCP stdio transport requires stdout to be pure JSON-RPC only.
    console_handler = logging.StreamHandler(sys.stderr)

    if simple_mode:
        # Simple mode: only show SUCCESS, WARNING, ERROR, and CRITICAL
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(CustomFormatter("%(levelname)s: %(message)s"))

        class SimpleFilter(logging.Filter):
            """Filter that allows SUCCESS, WARNING, ERROR, and CRITICAL levels.

            This filter passes log records with level SUCCESS (25), WARNING (30),
            ERROR (40), and CRITICAL (50), blocking DEBUG and INFO messages.

            Args:
                record: The log record to evaluate.

            Returns:
                True if the record should be logged, False otherwise.
            """

            def filter(self, record: logging.LogRecord) -> bool:
                return record.levelno == SUCCESS or record.levelno >= logging.WARNING

        console_handler.addFilter(SimpleFilter())
    else:
        # Default mode: Show only SUCCESS, ERROR, and CRITICAL (suppress DEBUG, INFO, WARNING)
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(CustomFormatter("%(levelname)s: %(message)s"))

        class SuccessOrErrorFilter(logging.Filter):
            """Filter that allows SUCCESS, ERROR, and CRITICAL but suppresses WARNING.

            This filter passes log records with level SUCCESS (25), ERROR (40),
            and CRITICAL (50), but blocks WARNING (30) messages along with
            DEBUG and INFO. Used for default console output to keep terminal clean.

            Args:
                record: The log record to evaluate.

            Returns:
                True if the record should be logged, False otherwise.
            """

            def filter(self, record: logging.LogRecord) -> bool:
                return record.levelno == SUCCESS or record.levelno >= logging.ERROR

        console_handler.addFilter(SuccessOrErrorFilter())

    _logger.addHandler(file_handler)
    _logger.addHandler(console_handler)
    _logger.info(f"Logging initialized. Log file: {log_file}")

    return _logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get the configured logger instance or set it up if not already done.

    Args:
        name: Logger name (optional). Accepted for API compatibility with
              standard Python logging patterns (e.g., ``logging.getLogger(__name__)``),
              but currently ignored as this returns a singleton logger instance
              shared by all modules.

    Returns:
        The global 'reportalin-specialist' logger instance

    Note:
        This function implements a singleton pattern - all modules share the same
        logger instance. The name parameter is accepted for compatibility with
        standard Python logging but is currently ignored. A debug message is
        logged if a name is provided and the logger is already initialized.

    Examples:
        Standard usage (singleton pattern)::

            from reportalin.data.utils import logging as log
            logger = log.get_logger()
            logger.info("Processing data...")

        Compatible with Python logging pattern::

            logger = log.get_logger(__name__)  # Works but returns singleton logger
            logger.info("Message logged")

    See Also:
        :func:`setup_logger` - Configure the singleton logger with custom settings
    """
    # Log a debug message if name is provided (helps users understand singleton behavior)
    if name is not None and _logger is not None:
        _logger.debug(
            f"get_logger(name='{name}') called but returning singleton logger instance. "
            f"All modules share the same 'reportalin-specialist' logger."
        )

    return _logger if _logger else setup_logger()


def get_log_file_path() -> str | None:
    """Get the path to the current log file.

    Returns:
        The absolute path to the log file, or None if logging is not initialized.
    """
    return _log_file_path


def _append_log_path(msg: str, include_log_path: bool) -> str:
    """Append log file path to error/warning messages.

    Args:
        msg: The original message to potentially modify.
        include_log_path: Whether to append the log file path.

    Returns:
        The message with optional log file path appended.
    """
    if include_log_path and get_log_file_path():
        return f"{msg}\nFor more details, check the log file at: {get_log_file_path()}"
    return msg


def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log a DEBUG level message.

    Args:
        msg: The message to log.
        *args: Additional positional arguments passed to the logger.
        **kwargs: Additional keyword arguments passed to the logger.
    """
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log an INFO level message.

    Args:
        msg: The message to log.
        *args: Additional positional arguments passed to the logger.
        **kwargs: Additional keyword arguments passed to the logger.
    """
    get_logger().info(msg, *args, **kwargs)


def warning(
    msg: str, *args: Any, include_log_path: bool = False, **kwargs: Any
) -> None:
    """Log a WARNING level message.

    Args:
        msg: The message to log.
        *args: Additional positional arguments passed to the logger.
        include_log_path: Whether to append log file path to message.
        **kwargs: Additional keyword arguments passed to the logger.
    """
    get_logger().warning(_append_log_path(msg, include_log_path), *args, **kwargs)


def error(msg: str, *args: Any, include_log_path: bool = True, **kwargs: Any) -> None:
    """Log an ERROR level message with optional log file path.

    Args:
        msg: The message to log.
        *args: Additional positional arguments passed to the logger.
        include_log_path: Whether to append log file path to message.
        **kwargs: Additional keyword arguments passed to the logger.
    """
    get_logger().error(_append_log_path(msg, include_log_path), *args, **kwargs)


def critical(
    msg: str, *args: Any, include_log_path: bool = True, **kwargs: Any
) -> None:
    """Log a CRITICAL level message with optional log file path.

    Args:
        msg: The message to log.
        *args: Additional positional arguments passed to the logger.
        include_log_path: Whether to append log file path to message.
        **kwargs: Additional keyword arguments passed to the logger.
    """
    get_logger().critical(_append_log_path(msg, include_log_path), *args, **kwargs)


def success(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log a SUCCESS level message (custom level 25).

    Args:
        msg: The message to log.
        *args: Additional positional arguments passed to the logger.
        **kwargs: Additional keyword arguments passed to the logger.
    """
    get_logger().log(SUCCESS, msg, *args, **kwargs)


# Add success method to Logger class properly
def _success_method(self: logging.Logger, msg: str, *args: Any, **kwargs: Any) -> None:
    """Custom success logging method for Logger instances.

    This method is dynamically added to the Logger class to support
    the custom SUCCESS level (25) via ``logger.success()`` calls.

    Args:
        self: The logger instance.
        msg: The message to log.
        *args: Additional positional arguments passed to log().
        **kwargs: Additional keyword arguments passed to log().
    """
    if self.isEnabledFor(SUCCESS):
        self.log(SUCCESS, msg, *args, **kwargs)


logging.Logger.success = _success_method  # type: ignore[attr-defined]

# Verbose Logging Utilities (for detailed debugging across all steps)
# ====================================================================


class VerboseLogger:
    """Centralized verbose logging for detailed output in DEBUG mode.

    Provides formatted tree-view output for file processing, step execution,
    and operation timing. Only logs when logger is in DEBUG mode.

    Usage:
        vlog = VerboseLogger(log)
        with vlog.file_processing("file.xlsx", total_records=412):
            with vlog.step("Processing step"):
                vlog.detail("Details here")
    """

    def __init__(self, logger_module) -> None:
        """Initialize with logger module.

        Args:
            logger_module: The logging module to use for output (typically
                ``reportalin.data.utils.logging`` or ``sys.modules[__name__]``).
        """
        self.log = logger_module
        self._indent = 0

    def _is_verbose(self) -> bool:
        """Check if verbose (DEBUG) logging is enabled.

        Returns:
            True if the logger level is DEBUG, False otherwise.
        """
        return get_logger().level == logging.DEBUG

    def _log_tree(self, prefix: str, message: str) -> None:
        """Log with tree-view formatting.

        Args:
            prefix: Tree-view prefix character(s) (e.g., "├─ ", "│  ", "└─ ").
            message: The message to log.
        """
        if self._is_verbose():
            indent = "  " * self._indent
            self.log.debug(f"{indent}{prefix}{message}")

    class _ContextManager:
        """Context manager for tree-view logging blocks.

        Manages indentation and provides header/footer output for structured
        tree-view logging of processing steps.

        Args:
            vlog: The parent VerboseLogger instance.
            prefix: Tree-view prefix character(s) for the header.
            header: Message to display on context entry.
            footer: Optional message to display on context exit.
        """

        def __init__(
            self,
            vlog: VerboseLogger,
            prefix: str,
            header: str,
            footer: str | None = None,
        ) -> None:
            self.vlog = vlog
            self.prefix = prefix
            self.header = header
            self.footer = footer

        def __enter__(self) -> VerboseLogger._ContextManager:
            self.vlog._log_tree(self.prefix, self.header)
            self.vlog._indent += 1
            return self

        def __exit__(self, *args: object) -> None:
            self.vlog._indent -= 1
            if self.footer:
                # Use └─ for footer instead of ├─ to show the final item
                self.vlog._log_tree("└─ ", self.footer)

    def file_processing(
        self, filename: str, total_records: int | None = None
    ) -> _ContextManager:
        """Context manager for processing a file.

        Args:
            filename: Name of the file being processed.
            total_records: Optional total number of records in the file.

        Returns:
            A context manager that logs file processing start/end.
        """
        header = f"Processing: {filename}"
        if total_records is not None:
            header += f" ({total_records} records)"
        return self._ContextManager(self, "├─ ", header, "✓ Complete")

    def step(self, step_name: str) -> _ContextManager:
        """Context manager for a processing step.

        Args:
            step_name: Name of the processing step.

        Returns:
            A context manager that logs step start.
        """
        return self._ContextManager(self, "├─ ", step_name)

    def detail(self, message: str) -> None:
        """Log a detail message within a step.

        Args:
            message: The detail message to log.
        """
        self._log_tree("│  ", message)

    def metric(self, label: str, value: Any) -> None:
        """Log a metric/statistic.

        Args:
            label: The metric label.
            value: The metric value.
        """
        self._log_tree("├─ ", f"{label}: {value}")

    def timing(self, operation: str, seconds: float) -> None:
        """Log operation timing.

        Args:
            operation: Name of the timed operation.
            seconds: Duration in seconds.
        """
        self._log_tree("├─ ", f"⏱ {operation}: {seconds:.2f}s")

    def items_list(self, label: str, items: list, max_show: int = 5) -> None:
        """Log a list of items with truncation if too long.

        Args:
            label: Label for the list.
            items: List of items to display.
            max_show: Maximum number of items to show before truncating.
        """
        if not self._is_verbose():
            return

        if len(items) <= max_show:
            self.detail(f"{label}: {', '.join(str(i) for i in items)}")
        else:
            self.detail(
                f"{label}: {', '.join(str(i) for i in items[:max_show])} ... (+{len(items) - max_show} more)"
            )


# Create a global VerboseLogger instance for use across modules
_verbose_logger: VerboseLogger | None = None


def get_verbose_logger() -> VerboseLogger:
    """Get or create the global VerboseLogger instance.

    Returns:
        The singleton VerboseLogger instance for tree-view logging.
    """
    global _verbose_logger
    if _verbose_logger is None:
        _verbose_logger = VerboseLogger(sys.modules[__name__])
    return _verbose_logger
