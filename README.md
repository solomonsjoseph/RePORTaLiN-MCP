<div align="center">

# RePORTaLiN MCP Server

**Production-ready Model Context Protocol (MCP) server for privacy-preserving clinical data access**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP 1.0+](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/uv-package%20manager-blueviolet.svg)](https://docs.astral.sh/uv/)

[Quick Start](#quick-start) • [Architecture](#architecture) • [Configuration](#configuration) • [Tools](#available-tools) • [Client Integration](#client-integration) • [Docker](#docker-deployment)

</div>

---

## Overview

RePORTaLiN MCP Server is a **Model Context Protocol** implementation that provides a Data Dictionary Expert for the RePORT India TB study. This server focuses exclusively on variable discovery and metadata lookup - NO patient data access.

### Key Features

- 📚 **Metadata Only** — Variable discovery and data dictionary lookup (NO patient data)
- 🔍 **Variable Discovery** — Intelligent concept expansion for clinical research queries
- 🌐 **Universal Transport** — Supports both stdio (Claude Desktop) and HTTP/SSE protocols
- 🔐 **Secure by Default** — Bearer token authentication with constant-time comparison
- 📊 **Schema-Aware Tools** — Pydantic-validated inputs with JSON Schema for LLM reliability
- 🐳 **Production-Ready** — Multi-stage Docker builds with non-root user and health checks

---

## Quick Start

### Prerequisites

- Python 3.10+ (3.11 or 3.13 recommended)
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Local Development (with uv)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/your-org/RePORTaLiN-Agent.git
cd RePORTaLiN-Agent

# Install dependencies (uv creates .venv automatically)
uv sync --all-extras

# Configure environment
cp .env.example .env
# Edit .env with your MCP_AUTH_TOKEN

# Start the MCP server (HTTP/SSE mode)
uv run uvicorn reportalin.server.main:app --host 127.0.0.1 --port 8000 --reload

# Or start in stdio mode (for Claude Desktop)
MCP_TRANSPORT=stdio uv run python -m reportalin.server
```

### Production Deployment (with Docker)

```bash
# Clone and configure
git clone https://github.com/your-org/RePORTaLiN-Agent.git
cd RePORTaLiN-Agent
cp .env.example .env

# Generate a secure auth token
echo "MCP_AUTH_TOKEN=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env

# Build and run with Docker Compose
docker compose up --build mcp-server

# Server is now available at http://localhost:8000
# API docs at http://localhost:8000/docs (local environment only)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LLM Application                                │
│                    (Claude Desktop / Custom Agent)                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   UniversalMCPClient      │
                    │   (client/mcp_client.py)  │
                    │   - Schema Adapters       │
                    │   - OpenAI/Anthropic      │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
    ┌─────────▼─────────┐                 ┌───────────▼───────────┐
    │   stdio Transport │                 │   HTTP/SSE Transport  │
    │   (Claude Desktop)│                 │   (FastAPI + uvicorn) │
    └─────────┬─────────┘                 └───────────┬───────────┘
              │                                       │
              └───────────────────┬───────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     MCPAuthMiddleware     │
                    │   (Bearer Token Auth)     │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      FastMCP Server       │
                    │   (server/tools.py)       │
                    │   - Tool Registration     │
                    │   - Input Validation      │
                    │   - K-Anonymity Checks    │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     Clinical Data Layer   │
                    │   - Data Dictionary       │
                    │   - Aggregate Statistics  │
                    │   - Encrypted Audit Logs  │
                    └───────────────────────────┘
```

### Project Structure

The project follows Python best practices with **src-layout** (PEP 517/518/621):

```
RePORTaLiN-Agent/
├── src/
│   └── reportalin/              # Main package (importable)
│       ├── __init__.py          # Package version and exports
│       ├── __main__.py          # CLI entry point
│       ├── server/              # MCP server implementation
│       │   ├── __main__.py      # Server entry point
│       │   ├── main.py          # FastAPI application
│       │   ├── tools/           # MCP tools package (v0.3.0 - 3 tools)
│       │   │   ├── __init__.py           # Package exports
│       │   │   ├── prompt_enhancer.py    # PRIMARY: Intelligent router
│       │   │   ├── combined_search.py    # DEFAULT: Variable discovery
│       │   │   ├── search_data_dictionary.py  # Direct variable lookup
│       │   │   ├── registry.py           # FastMCP setup
│       │   │   ├── _models.py            # Pydantic models
│       │   │   └── _loaders.py           # Data loading (w/ Excel fallback)
│       │   ├── config.py        # Settings (Pydantic)
│       │   └── auth.py          # Authentication middleware
│       ├── client/              # MCP client library
│       │   ├── mcp_client.py    # Universal client
│       │   └── agent.py         # Agent implementations
│       ├── core/                # Core utilities
│       │   ├── config.py        # Shared configuration
│       │   ├── logging.py       # Structured logging
│       │   └── constants.py     # Shared constants
│       ├── data/                # Data processing
│       │   ├── deidentify.py    # De-identification
│       │   └── extract_data.py  # Data extraction
│       ├── types/               # Type definitions
│       │   └── models.py        # Pydantic models
│       └── cli/                 # CLI commands
│           ├── pipeline.py      # Data pipeline CLI
│           └── verify.py        # Verification CLI
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
├── docker/                      # Docker configurations
│   ├── Dockerfile               # Production image
│   └── Dockerfile.secure        # Hardened image
├── examples/                    # Usage examples
│   ├── client/                  # Client examples
│   └── config/                  # Configuration examples
├── pyproject.toml              # Project metadata (PEP 621)
├── uv.lock                     # Dependency lock file
└── README.md                   # This file
```

**Key Features:**
- **Namespace isolation**: Prevents import conflicts
- **Editable installs**: `uv pip install -e .` for development
- **Type hints**: Fully typed with mypy strict mode
- **Entry points**: CLI commands via `pyproject.toml`

### SSE Handshake Flow

1. **Client** → `GET /mcp/sse` with `Authorization: Bearer <token>`
2. **Server** → Validates token, establishes SSE stream
3. **Server** → Sends `endpoint` event: `/mcp/messages?session_id=<uuid>`
4. **Client** → `POST /mcp/messages` with JSON-RPC 2.0 requests
5. **Server** → Streams responses via SSE `message` events

---

## Configuration

All configuration is managed via environment variables. Create a `.env` file from `.env.example`:

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `local` | Deployment environment: `local`, `development`, `staging`, `production` |
| `MCP_HOST` | No | `127.0.0.1` | Server bind address |
| `MCP_PORT` | No | `8000` | Server port |
| `MCP_AUTH_TOKEN` | **Yes*** | — | Bearer token for API authentication |
| `MCP_AUTH_ENABLED` | No | `true` | Enable/disable authentication |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | No | `auto` | Log format: `auto`, `json`, `pretty` |
| `PRIVACY_MODE` | No | `strict` | Privacy enforcement: `strict`, `standard` |
| `MIN_K_ANONYMITY` | No | `5` | Minimum k-anonymity threshold |
| `OPENAI_API_KEY` | No | — | OpenAI API key (for agent features) |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (for agent features) |
| `LLM_API_KEY` | No | — | Generic LLM API key (agent) |
| `LLM_BASE_URL` | No | — | Custom LLM endpoint (Ollama, vLLM, etc.) |

> **\*** `MCP_AUTH_TOKEN` is required in `staging` and `production` environments. In `local`/`development`, a dev token is auto-generated if not provided.

### Generate a Secure Token

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Available Tools

The MCP server provides **3 specialized tools** for data dictionary exploration. This server is a **Data Dictionary Expert** - it provides metadata only, NO patient data or statistics.

### Tool Selection Guide

| Query Type | Tool to Use |
|------------|-------------|
| **ANY question** (recommended) | `prompt_enhancer` ⭐ |
| Variable discovery for research questions | `combined_search` |
| "What variables should I use for relapse analysis?" | `combined_search` |
| "What variables track TB outcome?" | `combined_search` |
| Direct variable lookup by keyword | `search_data_dictionary` |

### Available Tools (3 Total)

#### `prompt_enhancer` ⭐ **PRIMARY ENTRY POINT**

**Intelligent query router with user confirmation flow.** Analyzes your question, confirms understanding, then automatically routes to the appropriate specialized tool.

**CRITICAL FEATURE:** Always confirms its interpretation with you BEFORE executing queries.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_query` | string | Yes | ANY question about variables/metadata (5-500 chars) |
| `context` | object | No | Optional context from previous queries |
| `user_confirmation` | boolean | No | Set to `true` after confirming interpretation (default: `false`) |

**Example:**
```json
{
  "name": "prompt_enhancer",
  "arguments": {
    "user_query": "What variables should I use for relapse analysis?"
  }
}
// Returns: Variable list with descriptions, tables, and codelists
```

#### `combined_search` (DEFAULT for variable discovery)

**Use this for variable discovery.** Searches through data dictionary with concept expansion (e.g., "relapse" → ["relapse", "recurrence", "recurrent"]).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `concept` | string | Yes | Clinical concept or research question (3-500 chars) |

**Example:**
```json
{
  "name": "combined_search",
  "arguments": {
    "concept": "diabetes variables"
  }
}
// Returns: Relevant variables, descriptions, codelists
```

#### `search_data_dictionary`

Direct variable lookup by keyword - **metadata only, NO statistics**.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Term to search for (1-200 chars) |
| `include_codelists` | boolean | No | Include codelist values (default: `true`) |

### Tool Architecture

```
User Query → prompt_enhancer (confirms) → Routes to appropriate tool
                    ↓
    ┌───────────────┴───────────────┐
    │                               │
combined_search              search_data_dictionary
(variable discovery)         (direct lookup)
```

### What This Server Does

- ✅ Returns **variable names, descriptions, tables, codelists**
- ✅ Concept synonym expansion for variable discovery
- ✅ Data dictionary metadata lookup
- ❌ NO patient data, NO statistics, NO dataset access

---

## Client Integration

### Using UniversalMCPClient

The `UniversalMCPClient` provides a Python interface for connecting to the MCP server with automatic schema adaptation for different LLM providers.

```python
import asyncio
from reportalin.client.mcp_client import UniversalMCPClient

async def main():
    # Connect to MCP server
    async with UniversalMCPClient(
        server_url="http://localhost:8000/mcp/sse",
        auth_token="your-secure-token-here"
    ) as client:
        
        # Get tools formatted for OpenAI
        openai_tools = await client.get_tools_for_openai()
        print(f"Available tools: {[t['function']['name'] for t in openai_tools]}")
        
        # Get tools formatted for Anthropic Claude
        anthropic_tools = await client.get_tools_for_anthropic()
        
        # Execute combined_search (DEFAULT tool for all queries)
        result = await client.execute_tool(
            "combined_search",
            {"concept": "diabetes prevalence"}
        )
        print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Using with OpenAI Function Calling

```python
from openai import OpenAI
from reportalin.client.mcp_client import UniversalMCPClient

async def agent_loop():
    client = OpenAI()
    
    async with UniversalMCPClient(
        "http://localhost:8000/mcp/sse", 
        "your-token"
    ) as mcp:
        # Get tools in OpenAI format
        tools = await mcp.get_tools_for_openai()
        
        messages = [{"role": "user", "content": "What studies are available?"}]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=tools
        )
        
        # Handle tool calls
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                result = await mcp.execute_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments)
                )
                # Process result...
```

### Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reportalin": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/RePORTaLiN-Agent",
        "python", "-m", "reportalin.server",
        "--transport", "stdio"
      ],
      "env": {
        "MCP_AUTH_TOKEN": "your-secure-token",
        "PRIVACY_MODE": "strict"
      }
    }
  }
}
```

---

## Docker Deployment

### Build Options

```bash
# Production build (recommended)
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile -t reportalin-mcp:latest .

# Secure build with additional hardening
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile.secure -t reportalin-mcp:secure .
```

### Run with Docker Compose

```bash
# Production mode
docker compose up mcp-server

# Development mode (with hot reload)
docker compose up mcp-server-dev

# Rebuild and start
docker compose up --build mcp-server

# Run in background
docker compose up -d mcp-server

# View logs
docker compose logs -f mcp-server

# Stop
docker compose down
```

### Run Standalone

```bash
docker run -d \
  --name reportalin-mcp \
  -p 8000:8000 \
  -e MCP_AUTH_TOKEN=your-secure-token \
  -e ENVIRONMENT=production \
  -v $(pwd)/results:/app/results:ro \
  -v $(pwd)/encrypted_logs:/app/encrypted_logs \
  reportalin-mcp:latest
```

### Health Checks

```bash
# Check container health status
docker inspect --format='{{.State.Health.Status}}' reportalin-mcp

# Manual health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready
```

### Docker Features Summary

| Feature | Implementation |
|---------|----------------|
| Base Image | `python:3.11-slim` |
| Package Manager | `uv` with `pyproject.toml` |
| Init System | `tini` for proper signal handling |
| User | Non-root `app` (UID 1000) |
| Build Strategy | Multi-stage for minimal size |
| Health Check | HTTP `/health` endpoint |
| Logging | JSON format with rotation |

---

## API Endpoints

### Public Endpoints (No Auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/ready` | GET | Readiness probe |

### Protected Endpoints (Bearer Token)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Detailed server status |
| `/tools` | GET | List available tools |
| `/info` | GET | Server info and connection details |
| `/mcp/sse` | GET | SSE stream for MCP protocol |
| `/mcp/messages` | POST | JSON-RPC message handler |

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs (local environment only)
- **ReDoc**: http://localhost:8000/redoc (local environment only)

---

## Security

### Authentication

- All MCP endpoints require Bearer token authentication
- Tokens are validated using constant-time comparison (timing-attack resistant)
- Failed auth attempts are logged with request metadata

### Privacy Protection

- K-anonymity enforcement (configurable threshold, default k=5)
- No raw patient data exposed—only aggregates and schemas
- Encrypted audit logging with RSA/AES hybrid encryption

### Container Security

- Non-root user execution
- Read-only volume mounts for data
- Resource limits via Docker Compose
- No new privileges security option

---

## Troubleshooting

### Connection Refused

```bash
# Check if server is running
curl http://localhost:8000/health

# Check Docker logs
docker compose logs mcp-server
```

### Authentication Failed

```bash
# Verify token is set
echo $MCP_AUTH_TOKEN

# Test with curl
curl -H "Authorization: Bearer $MCP_AUTH_TOKEN" http://localhost:8000/tools
```

### SSE Connection Drops

- Increase `sse_read_timeout` in client configuration
- Check for proxy/load balancer SSE support
- Verify network allows long-lived connections

---

## Development

### Running Tests

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=src/reportalin --cov-report=html
```

### Code Quality

```bash
# Format code
uv run black .

# Lint
uv run ruff check .

# Type check
uv run mypy src/reportalin
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by the RePORTaLiN Team**

[Report Bug](https://github.com/your-org/RePORTaLiN-Agent/issues) • [Request Feature](https://github.com/your-org/RePORTaLiN-Agent/issues)

</div>
