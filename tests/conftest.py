"""
Pytest configuration and fixtures for RePORTaLiN-Specialist tests.

This module provides shared fixtures and configuration for all test suites.
Fixtures are organized by scope (session, module, function) for optimal
test execution performance.

Phase 5 Implementation:
    - FastAPI TestClient fixture with async support
    - Token override fixture for controlled auth testing
    - Background server fixture for integration tests
    - MCP client fixture for protocol testing

Usage:
    Fixtures are automatically available to all tests. Import pytest and
    use fixtures as function parameters:

        def test_example(settings):
            assert settings.log_level is not None

        @pytest.mark.asyncio
        async def test_auth(test_client, test_token):
            response = test_client.get("/health")
            assert response.status_code == 200

See Also:
    - tests/unit/ - Unit tests for individual components
    - tests/integration/ - Integration tests for MCP server
    - pytest.ini / pyproject.toml - Pytest configuration
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Test Constants
# =============================================================================

# Known test token for authentication testing
TEST_AUTH_TOKEN = "test-secret-token-12345"

# Invalid tokens for negative testing
INVALID_TOKEN = "invalid-token-wrong"
EMPTY_TOKEN = ""


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "security: marks tests as security-related")
    config.addinivalue_line("markers", "mcp: marks tests as MCP server tests")
    config.addinivalue_line("markers", "auth: marks tests as authentication tests")


@pytest.fixture(autouse=True)
def reset_caches():
    """
    Autouse fixture to reset caches before each test.

    This ensures that:
    1. Settings cache is cleared so env vars can be changed per-test
    2. Rotatable secret cache is cleared so auth state is fresh

    This prevents test pollution where one test's cache affects another.
    """
    # Import and clear caches BEFORE test runs
    try:
        from reportalin.core.config import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass

    try:
        from reportalin.server.auth import get_rotatable_secret

        get_rotatable_secret.cache_clear()
    except ImportError:
        pass

    yield  # Test runs here

    # Clear caches AFTER test as well (cleanup)
    try:
        from reportalin.core.config import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass

    try:
        from reportalin.server.auth import get_rotatable_secret

        get_rotatable_secret.cache_clear()
    except ImportError:
        pass


# =============================================================================
# Session-Scoped Fixtures (created once per test session)
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the test session.

    This fixture provides a shared event loop for all async tests,
    ensuring proper cleanup at session end.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def data_dir(project_root: Path) -> Path:
    """Get the data directory path."""
    return project_root / "data"


@pytest.fixture(scope="session")
def results_dir(project_root: Path) -> Path:
    """Get the results directory path."""
    return project_root / "results"


# =============================================================================
# Module-Scoped Fixtures (created once per test module)
# =============================================================================


@pytest.fixture(scope="module")
def test_token() -> str:
    """
    Get the known test authentication token.

    This token is used for tests that require valid authentication.
    It's set via environment variable override in the app_settings fixture.

    Returns:
        The test authentication token string
    """
    return TEST_AUTH_TOKEN


@pytest.fixture(scope="module")
def app_settings(monkeypatch_module):
    """
    Override application settings for testing.

    Sets MCP_AUTH_TOKEN to a known value for predictable auth testing.
    Also enables auth to ensure security tests work correctly.

    Returns:
        Settings instance with test configuration
    """
    # Override environment variables before importing settings
    monkeypatch_module.setenv("MCP_AUTH_TOKEN", TEST_AUTH_TOKEN)
    monkeypatch_module.setenv("MCP_AUTH_ENABLED", "true")
    monkeypatch_module.setenv("ENVIRONMENT", "local")
    monkeypatch_module.setenv("LOG_LEVEL", "DEBUG")

    # Clear the settings cache to pick up new values
    from reportalin.core.config import get_settings

    get_settings.cache_clear()

    settings = get_settings()
    return settings


@pytest.fixture(scope="module")
def monkeypatch_module():
    """
    Module-scoped monkeypatch fixture.

    Pytest's monkeypatch is function-scoped by default.
    This provides module-scoped environment patching for settings.
    """
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def mcp_instance(app_settings):
    """
    Get the MCP server instance.

    Returns:
        FastMCP instance from reportalin.server.tools
    """
    from reportalin.server.tools import mcp

    return mcp


# =============================================================================
# Function-Scoped Test Client Fixtures
# =============================================================================


@pytest.fixture
def test_app(monkeypatch):
    """
    Get the FastAPI application instance for testing.

    Overrides environment variables to use test token,
    then returns the app instance.

    Note: We use the global app instance rather than create_app()
    because the routes and MCP mount are configured at module load time.
    Environment overrides ensure the auth token is known for testing.

    CRITICAL: Must clear BOTH settings cache AND rotatable_secret cache
    to ensure auth enforcement works correctly in tests.

    Returns:
        FastAPI application configured for testing
    """
    # Set test environment BEFORE importing to ensure settings are picked up
    monkeypatch.setenv("MCP_AUTH_TOKEN", TEST_AUTH_TOKEN)
    monkeypatch.setenv("MCP_AUTH_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "local")

    # Clear settings cache to pick up new env vars
    from reportalin.core.config import get_settings

    get_settings.cache_clear()

    # CRITICAL: Also clear the rotatable secret cache so it picks up the new token
    # Without this, the auth system may use a stale "unconfigured" state
    from reportalin.server.auth import get_rotatable_secret

    get_rotatable_secret.cache_clear()

    # Force settings reload
    _ = get_settings()

    # Use global app (routes are registered at module load time)
    from reportalin.server.main import base_app

    return base_app


@pytest.fixture
def test_client(test_app) -> Generator[TestClient, None, None]:
    """
    Synchronous TestClient for FastAPI endpoint testing.

    This fixture creates a TestClient wrapped around the test app,
    suitable for testing HTTP endpoints without async.

    Usage:
        def test_health(test_client):
            response = test_client.get("/health")
            assert response.status_code == 200

    Yields:
        TestClient instance
    """
    with TestClient(test_app) as client:
        yield client


@pytest.fixture
async def async_test_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing FastAPI endpoints asynchronously.

    This fixture creates an httpx.AsyncClient with ASGI transport,
    allowing async/await style testing of endpoints.

    Usage:
        @pytest.mark.asyncio
        async def test_health(async_test_client):
            response = await async_test_client.get("/health")
            assert response.status_code == 200

    Yields:
        httpx.AsyncClient with ASGI transport
    """
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        yield client


# =============================================================================
# Authentication Test Fixtures
# =============================================================================


@pytest.fixture
def auth_headers(test_token: str) -> dict[str, str]:
    """
    Valid authentication headers for testing.

    Returns:
        Dictionary with Authorization header set to Bearer token
    """
    return {"Authorization": f"Bearer {test_token}"}


@pytest.fixture
def invalid_auth_headers() -> dict[str, str]:
    """
    Invalid authentication headers for negative testing.

    Returns:
        Dictionary with invalid Bearer token
    """
    return {"Authorization": f"Bearer {INVALID_TOKEN}"}


@pytest.fixture
def no_auth_headers() -> dict[str, str]:
    """
    Empty headers for testing missing authentication.

    Returns:
        Empty dictionary (no auth header)
    """
    return {}


# =============================================================================
# Function-Scoped Fixtures (created fresh for each test)
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for test files.

    Yields:
        Path to temporary directory (cleaned up after test)
    """
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_log_dir(temp_dir: Path) -> Path:
    """
    Create a temporary log directory.

    Returns:
        Path to temporary log directory
    """
    log_dir = temp_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def temp_encrypted_log_dir(temp_dir: Path) -> Path:
    """
    Create a temporary encrypted log directory.

    Returns:
        Path to temporary encrypted log directory
    """
    log_dir = temp_dir / "encrypted_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """
    Set up mock environment variables for testing.

    Returns:
        Dictionary of set environment variables
    """
    env_vars = {
        "REPORTALIN_LOG_LEVEL": "DEBUG",
        "REPORTALIN_LOG_VERBOSE": "true",
        "REPORTALIN_DEBUG_MODE": "false",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


# =============================================================================
# MCP Tool Test Fixtures (SECURE MODE - 2 Tools Only)
# =============================================================================


@pytest.fixture
def explore_study_metadata_input():
    """
    Create a valid ExploreStudyMetadataInput for testing.

    Returns:
        Dictionary with valid metadata query parameters
    """
    return {
        "query": "Do we have any participants from Pune with follow-up data?",
        "site_filter": None,
        "time_point_filter": None,
    }


@pytest.fixture
def build_technical_request_input():
    """
    Create a valid BuildTechnicalRequestInput for testing.

    Returns:
        Dictionary with valid technical request parameters
    """
    return {
        "description": "Analyze treatment outcomes in TB patients",
        "inclusion_criteria": ["Female", "Age 18-45"],
        "exclusion_criteria": ["HIV co-infection"],
        "variables_of_interest": ["Age", "Sex", "TB_Status"],
        "time_points": ["Baseline", "Month 6"],
        "output_format": "concept_sheet",
    }


# =============================================================================
# Security Test Fixtures
# =============================================================================


@pytest.fixture
def dangerous_queries() -> list[str]:
    """
    List of dangerous SQL queries for security testing.

    These queries should all be rejected by the query validator.

    Returns:
        List of SQL strings that should fail validation
    """
    return [
        "DELETE FROM patients WHERE id = 1",
        "INSERT INTO patients VALUES (1, 'test')",
        "UPDATE patients SET name = 'test' WHERE id = 1",
        "DROP TABLE patients",
        "TRUNCATE TABLE patients",
        "SELECT * FROM patients; DROP TABLE patients;--",
        "SELECT * FROM patients /* comment */ DELETE",
        "EXEC sp_executesql @sql",
    ]


@pytest.fixture
def safe_queries() -> list[str]:
    """
    List of safe SQL queries for positive testing.

    These queries should all pass validation.

    Returns:
        List of valid SELECT statements
    """
    return [
        "SELECT * FROM patients",
        "SELECT id, name FROM patients WHERE age > 18",
        "SELECT COUNT(*) FROM patients GROUP BY gender",
        "SELECT p.*, d.diagnosis FROM patients p JOIN diagnoses d ON p.id = d.patient_id",
    ]


# =============================================================================
# Utility Functions
# =============================================================================


def assert_json_error_response(
    response, expected_status: int, error_key: str = "detail"
):
    """
    Assert that a response is a JSON error with expected status.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code
        error_key: Key to check for in JSON response

    Raises:
        AssertionError: If response doesn't match expectations
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}"
    )
    data = response.json()
    assert error_key in data or "error" in data, (
        f"Expected '{error_key}' or 'error' in response: {data}"
    )
