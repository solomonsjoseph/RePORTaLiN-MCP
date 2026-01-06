"""
RePORTaLiN-Specialist Test Suite.

Tests for the clinical data processing pipeline and MCP server.

Test Organization:
    tests/
    ├── conftest.py          - Shared fixtures (Phase 5: TestClient, auth tokens)
    ├── test_server.py       - Security & integration tests (Phase 5)
    ├── unit/                - Unit tests for individual components
    │   ├── test_auth.py     - Authentication module tests
    │   ├── test_config.py   - Configuration tests
    │   ├── test_logger.py   - Logging tests
    │   ├── test_mcp_server.py - MCP server unit tests
    │   └── test_mcp_client.py - MCP client unit tests
    └── integration/         - Integration tests for MCP server
        ├── test_server_startup.py - Server lifecycle tests
        ├── test_tool_call.py - Tool execution tests
        └── test_mcp_client.py - Live server client tests

Running Tests:
    # All tests
    uv run pytest

    # With coverage
    uv run pytest --cov=server --cov=client --cov-report=html

    # Security tests only
    uv run pytest -m security -v

    # Auth tests only
    uv run pytest -m auth -v

Phase 5 Additions:
    - tests/conftest.py: TestClient fixtures, token management
    - tests/test_server.py: Security hardening tests
    - verify.py: Standalone verification script (in project root)
    - docs/TESTING_GUIDE.md: Complete testing documentation
"""
