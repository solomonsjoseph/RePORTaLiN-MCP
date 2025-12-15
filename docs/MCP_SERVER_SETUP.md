# MCP Server Setup Guide

<!--
Document Type: How-to Guide (Diátaxis)
Target Audience: Developers integrating with Claude Desktop
Prerequisites: Python 3.10+, basic CLI familiarity
-->

> **Type**: How-to Guide | **Updated**: 2025-12-08 | **Status**: ✅ Verified

This guide walks you through setting up the RePORTaLiN MCP server for Claude Desktop or other MCP-compatible clients.

**Related Documentation:**
- [Configuration Reference](CONFIGURATION.md) — Environment variables and settings
- [Logging Architecture](LOGGING_ARCHITECTURE.md) — Encrypted audit logging
- [Security Policy](../SECURITY.md) — PHI handling guidelines

## Prerequisites

Before starting, ensure you have:

- Python 3.10 or higher installed
- RePORTaLiN-Agent repository cloned
- Basic familiarity with command line

## Step 1: Install Dependencies

Install the required packages:

```bash
cd /path/to/RePORTaLiN-Agent

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (uv creates .venv automatically)
uv sync --all-extras
```

**Required packages (managed via pyproject.toml):**

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp[cli]` | ≥1.0.0 | Model Context Protocol SDK |
| `pydantic` | ≥2.0.0 | Data validation |
| `cryptography` | ≥41.0.0 | Encrypted logging |

## Step 2: Verify Installation

Run the test suite to confirm everything works:

```bash
# Run unit tests
uv run pytest tests/unit/test_mcp_server.py -v

# Test server startup
uv run python tests/integration/test_server_startup.py
```

**Expected output:**

```
✓ 30/30 unit tests passing
✓ 10/10 tools properly registered
✓ SERVER IS READY FOR USE
```

## Step 3: Configure Claude Desktop

The server uses **stdio transport** for maximum security. Choose one of these configurations:

### Option 1: Virtual Environment (Recommended)

Use the absolute path to your virtual environment Python:

```json
{
  "mcpServers": {
    "reportalin-mcp": {
      "command": "/absolute/path/to/RePORTaLiN-Agent/.venv/bin/python",
      "args": ["-m", "server"],
      "cwd": "/absolute/path/to/RePORTaLiN-Agent",
      "env": {
        "REPORTALIN_PRIVACY_MODE": "strict",
        "NO_COLOR": "1",
        "TERM": "dumb",
        "FORCE_COLOR": "0",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Option 2: Using `uv` (if installed)

If you have [uv](https://github.com/astral-sh/uv) installed:

```json
{
  "mcpServers": {
    "reportalin-specialist": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/RePORTaLiN-Agent",
        "python", "-m", "server"
      ],
      "env": {
        "REPORTALIN_PRIVACY_MODE": "strict"
      }
    }
  }
}
```

### Option 3: Docker (Maximum Isolation)

For production or maximum security:

```json
{
  "mcpServers": {
    "reportalin-specialist": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/absolute/path/to/RePORTaLiN-Agent/results:/app/results:ro",
        "reportalin-specialist:latest"
      ],
      "env": {
        "REPORTALIN_PRIVACY_MODE": "strict"
      }
    }
  }
}
```

Build the Docker image first:
```bash
docker build -t reportalin-specialist .
```

### Config File Locations

| OS | Location |
|----|----------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

**Important:**

- Use **absolute paths** (not `~/...`)
- The `cwd` must point to your repository root
- Environment variables `NO_COLOR=1`, `TERM=dumb`, `FORCE_COLOR=0` are critical for stdio transport

## Step 4: Restart and Verify

1. **Restart Claude Desktop** completely (quit and reopen)
2. Look for the **MCP server icon** (hammer/tool icon) in Claude Desktop
3. Test with a query: *"What variables are available for HIV status?"*

Claude should automatically use the `get_study_variables` tool.

## Available Tools

### Tool Selection Guide

**DEFAULT BEHAVIOR: Use `combined_search` for ALL queries unless specifically asking about variable definitions.**

| Query Type | Tool to Use |
|------------|-------------|
| Any analytical question | `combined_search` |
| Counts, distributions, statistics | `combined_search` |
| "How many patients have X?" | `combined_search` |
| "What is the distribution of Y?" | `combined_search` |
| "What variables exist for X?" | `search_data_dictionary` |
| "What does variable Y mean?" | `search_data_dictionary` |

### Primary Tools (Use for Most Questions)

| Tool | Description | Example Query |
|------|-------------|---------------|
| `combined_search` | **DEFAULT** - Searches ALL data sources for statistics | "How many have diabetes?", "Age distribution" |
| `natural_language_query` | Complex multi-concept questions | "Compare outcomes between smokers and non-smokers" |
| `cohort_summary` | Comprehensive participant overview | "Give me an overview of the cohort" |
| `cross_tabulation` | Analyze relationships between two variables | "Is HIV associated with outcome?" |

### Detailed Analysis Tools

| Tool | Description | Example Query |
|------|-------------|---------------|
| `variable_details` | Deep dive into ONE specific variable | "Tell me everything about AGE" |
| `data_quality_report` | Missing data and completeness analysis | "What data quality issues exist?" |
| `multi_variable_comparison` | Side-by-side statistics | "Compare AGE, BMI, and CD4 statistics" |

### Supporting Tools (Specific Needs Only)

| Tool | Description | When to Use |
|------|-------------|-------------|
| `search_data_dictionary` | Variable definitions ONLY (no statistics) | Only when asking "what variables exist?" |
| `search_cleaned_dataset` | Direct query to cleaned data | When exact variable name is known |
| `search_original_dataset` | Fallback to original data | When cleaned data is missing something |

## Troubleshooting

### Server Not Appearing

| Symptom | Solution |
|---------|----------|
| No MCP icon | Verify config path; restart Claude Desktop |
| Icon but errors | Check `python3` is in PATH: `which python3` |
| Path errors | Use absolute path; verify directory exists |
| "Server disconnected" | See stdio issues below |

### Server Disconnected (stdio issues)

This error means something is printing to stdout other than JSON-RPC messages.

**Solution:** Ensure these environment variables are set:
```json
"env": {
  "NO_COLOR": "1",
  "TERM": "dumb",
  "FORCE_COLOR": "0",
  "PYTHONUNBUFFERED": "1"
}
```

**Test the server manually:**
```bash
cd /path/to/RePORTaLiN-Agent
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  NO_COLOR=1 TERM=dumb FORCE_COLOR=0 .venv/bin/python -m reportalin.server
```

**Expected:** A single line of JSON starting with `{"jsonrpc":"2.0","id":1,"result":{...}}`

**If you see anything before the JSON**, the server is polluting stdout. Check:
1. No `print()` statements in your code
2. All logging is configured for stderr
3. Environment variables are correct

### Common Errors

**ImportError: No module named 'mcp'**

```bash
uv sync  # Reinstall dependencies
```

**Permission denied**

- On macOS: Grant Claude Desktop full disk access in System Preferences
- Verify the repository directory is readable

**Python version mismatch**

```bash
python3 --version  # Should be 3.10+
```

### Debug Steps

```bash
# 1. Verify server imports correctly
uv run python -c "from reportalin.server import mcp; print('Server OK:', mcp.name)"

# 2. Test the entry point
uv run python -c "from reportalin.server.__main__ import main; print('Entry point OK')"

# 3. Test JSON-RPC response
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  NO_COLOR=1 TERM=dumb uv run python -m reportalin.server

# 4. Verify server is operational
uv run python verify.py --verbose
```

## Security Features

The MCP server enforces privacy protections:

| Feature | Description |
|---------|-------------|
| **PHI Protection** | Only metadata and aggregates exposed |
| **K-Anonymity** | Cell counts < 5 are suppressed |
| **Encrypted Logging** | All operations logged with RSA/AES |
| **Read-Only** | No data modification possible |
| **Network Isolation** | Stdio transport (no network exposure) |
| **DPDPA 2023** | India data protection compliance |

## Architecture

```
server/
├── __init__.py           # Package initialization
├── __main__.py           # Entry point with stdio isolation
├── main.py               # FastMCP server and HTTP endpoints
├── tools.py              # MCP tool definitions and implementation
├── auth.py               # Bearer token authentication
├── config.py             # Server configuration
├── data_pipeline.py      # Data pipeline connector
├── logger.py             # Structured logging
└── security/             # Security modules (encryption, rate limiting)
```

## Next Steps

- See [LOGGING_ARCHITECTURE.md](LOGGING_ARCHITECTURE.md) for encryption details
- See [CONFIGURATION.md](CONFIGURATION.md) for environment variables
- See [../SECURITY.md](../SECURITY.md) for security policy

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Best Practices](https://www.docker.com/blog/mcp-server-best-practices/)
- [India DPDPA 2023](https://www.meity.gov.in/data-protection-framework)
