# Testing & Verification Guide

<!--
Document Type: How-to Guide (Diátaxis)
Target Audience: Developers and QA Engineers
Prerequisites: Project installed with dev dependencies
-->

> **Type**: How-to Guide | **Updated**: 2025-12-08 | **Status**: ✅ Verified

This guide covers testing the RePORTaLiN MCP system for security, protocol compliance, and functionality.

**Related Documentation:**
- [MCP Server Setup](MCP_SERVER_SETUP.md) — Server installation
- [Configuration Reference](CONFIGURATION.md) — Environment variables
- [Security Policy](../SECURITY.md) — PHI handling guidelines

## Quick Start

```bash
# Install dev dependencies
uv sync --group dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=server --cov=client --cov-report=html
```

---

## Test Categories

### Unit Tests (`tests/unit/`)

Test individual components in isolation:

```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific test file
uv run pytest tests/unit/test_auth.py -v

# Run specific test class
uv run pytest tests/unit/test_mcp_server.py::TestQueryDatabaseInput -v
```

### Security Tests (`tests/test_server.py`)

Test authentication and SQL injection prevention:

```bash
# Run all security tests
uv run pytest tests/test_server.py -m security -v

# Run only authentication tests
uv run pytest tests/test_server.py -m auth -v

# Run query validation tests
uv run pytest tests/test_server.py::TestQueryValidation -v
```

### Integration Tests (`tests/integration/`)

Test server startup and MCP protocol compliance:

```bash
# Run integration tests
uv run pytest tests/integration/ -m integration -v
```

---

## Verification Script (`verify.py`)

A standalone script to verify the MCP server is operational **without requiring an LLM**.

### Prerequisites

1. Start the MCP server:
   ```bash
   uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
   ```

2. Set authentication token:
   ```bash
   export MCP_AUTH_TOKEN="your-secret-token"
   ```

### Usage

```bash
# Basic verification
uv run python verify.py

# Verbose output with tool list
uv run python verify.py --verbose

# JSON output for automation
uv run python verify.py --json

# Custom server URL
uv run python verify.py --url http://localhost:8000/mcp/sse

# Custom token
uv run python verify.py --token your-secret-token
```

### Expected Output

**Success:**
```
🔍 Verifying MCP Server at: http://localhost:8000/mcp/sse

✅ System Online: Found 10 tools

📋 Available Tools:
   • combined_search (DEFAULT - use for all queries)
   • natural_language_query
   • cohort_summary
   • cross_tabulation
   • variable_details
   • data_quality_report
   • multi_variable_comparison
   • search_data_dictionary (variable definitions only)
   • search_cleaned_dataset
   • search_original_dataset
```

**Failure:**
```
🔍 Verifying MCP Server at: http://localhost:8000/mcp/sse

❌ Connection failed
   Error: Server not responding
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - Server online and tools retrieved |
| `1` | Connection failed - Server not reachable |
| `2` | Authentication failed - Invalid token |
| `3` | Configuration error - Missing token |

---

## MCP Inspector (Manual Inspection)

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is the official visual debugger for MCP servers.

### Running the Inspector

```bash
# Start your server first
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000 &

# Run the inspector against your server
npx @modelcontextprotocol/inspector http://localhost:8000/mcp/sse
```

### Authentication with Inspector

The MCP Inspector may not support custom headers out of the box. Options:

#### Option 1: Query Parameter (Recommended)

The server supports token as query parameter:

```bash
npx @modelcontextprotocol/inspector "http://localhost:8000/mcp/sse?token=your-secret-token"
```

#### Option 2: Temporary Auth Disable (Local Dev Only)

For local development inspection, temporarily disable auth:

```bash
# Set environment variable
export MCP_AUTH_ENABLED=false

# Start server
uv run uvicorn server.main:app --host 0.0.0.0 --port 8000

# Run inspector
npx @modelcontextprotocol/inspector http://localhost:8000/mcp/sse
```

> ⚠️ **Security Warning**: Never disable authentication in production or staging environments!

#### Option 3: Use the Inspector with stdio transport

If using Claude Desktop config, you can inspect the stdio server:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/RePORTaLiN-Agent run python -m reportalin.server
```

### Inspector Features

The MCP Inspector allows you to:

- **View Tools**: See all registered tools and their schemas
- **Execute Tools**: Test tool calls with custom parameters
- **View Resources**: Browse available resources
- **Monitor Messages**: See JSON-RPC messages in real-time
- **Validate Schemas**: Check tool input/output schema compliance

---

## Test Fixtures

Common fixtures available in `tests/conftest.py`:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_client` | function | Synchronous FastAPI TestClient |
| `async_test_client` | function | Async httpx client |
| `test_token` | module | Known valid auth token |
| `auth_headers` | function | Valid Authorization header |
| `invalid_auth_headers` | function | Invalid auth header for negative tests |
| `no_auth_headers` | function | Empty headers for missing auth tests |
| `dangerous_queries` | function | List of SQL injection attempts |
| `safe_queries` | function | List of valid SELECT statements |

### Using Fixtures

```python
def test_with_auth(test_client, auth_headers):
    """Test with valid authentication."""
    response = test_client.get("/tools", headers=auth_headers)
    assert response.status_code == 200

def test_without_auth(test_client, no_auth_headers):
    """Test without authentication."""
    response = test_client.get("/tools", headers=no_auth_headers)
    assert response.status_code == 401
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        
      - name: Set up Python
        run: uv python install
        
      - name: Install dependencies
        run: uv sync --group dev
        
      - name: Run tests
        run: uv run pytest --cov=server --cov=client -v
        env:
          MCP_AUTH_TOKEN: test-token-for-ci
          MCP_AUTH_ENABLED: "true"
```

---

## Troubleshooting

### Tests Fail with Import Error

Ensure you're running from the project root:

```bash
cd /path/to/RePORTaLiN-Agent
uv run pytest tests/
```

### Authentication Tests Fail

The test fixtures override `MCP_AUTH_TOKEN`. If tests fail:

1. Clear Python's settings cache (handled by fixtures)
2. Ensure no conflicting `.env` values
3. Check that `MCP_AUTH_ENABLED=true` is set

### Async Tests Timeout

Increase pytest-asyncio timeout:

```bash
uv run pytest --timeout=30 tests/
```

### Server Connection Refused in verify.py

1. Ensure server is running:
   ```bash
   uv run uvicorn server.main:app --port 8000
   ```

2. Check the URL matches server configuration
3. Verify firewall isn't blocking localhost connections

---

## Security Test Coverage

The test suite covers:

| Category | Tests | Status |
|----------|-------|--------|
| Missing Auth | Endpoints return 401 | ✅ |
| Invalid Token | Rejected with 401 | ✅ |
| Valid Token | Access granted | ✅ |
| SQL Injection | DELETE/INSERT/UPDATE blocked | ✅ |
| Comment Injection | `--` and `/*` blocked | ✅ |
| DDL Prevention | DROP/CREATE/ALTER blocked | ✅ |
| Input Sanitization | Special chars removed | ✅ |
| Constant-time Compare | Timing attack prevention | ✅ |
