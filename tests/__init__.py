"""
RePORTaLiN MCP Test Suite.

Minimal tests for the MCP server and search tool.

Test Organization:
    tests/
    ├── conftest.py          - Shared fixtures
    ├── unit/                - Unit tests
    │   ├── test_config.py   - Configuration tests
    │   └── test_mcp_server.py - MCP server unit tests
    └── integration/         - Integration tests
        └── test_simple_server.py - Server lifecycle tests

Running Tests:
    # All tests
    uv run pytest

    # With coverage
    uv run pytest --cov=reportalin --cov-report=html

    # Specific test file
    uv run pytest tests/unit/test_mcp_server.py -v
"""
