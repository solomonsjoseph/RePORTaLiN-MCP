"""Minimal pytest configuration for RePORTaLiN MCP tests."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
def reset_logging():
    """Reset logging state between tests."""
    import reportalin.logging as log_module
    from reportalin.logging import clear_context, configure_logging

    # Reset module state
    log_module._configured = False

    # Clear all handlers from root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure logging for tests
    configure_logging(level="WARNING", format="console", force=True)
    clear_context()

    yield

    # Cleanup after test
    clear_context()
    log_module._configured = False
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)


@pytest.fixture(scope="function")
def settings():
    """Get test settings instance."""
    from reportalin.core.config import get_settings

    # Clear cache to get fresh settings
    get_settings.cache_clear()

    yield get_settings()

    # Clear again after test
    get_settings.cache_clear()
