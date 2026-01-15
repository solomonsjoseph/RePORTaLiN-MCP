# RePORTaLiN MCP Server

> **Minimal MCP server with ONE tool: variable search for RePORT India TB study data dictionary**

## What It Does

Exposes a single MCP tool (`search`) that finds variables from the RePORT India data dictionary based on clinical concepts. Better than SQL because it understands synonyms (e.g., "relapse" finds "recurrence", "recur", "recurrent").

**User asks**: "What variables track TB relapse?"  
**Claude calls**: `search("relapse")`  
**Returns**: 10 variables (TBNEW, TBREP, OUTCLIN, etc.) with descriptions and codelists

## Quick Start

```bash
# Development (local testing)
make dev      # Installs deps, extracts data, starts server

# Production (with email alerts)
make prod     # Requires .env.email configured
```

## Email Alerts (REQUIRED for Production)

Email notifications are **ENABLED BY DEFAULT**. All ERROR/CRITICAL logs automatically email the developer.

### Setup (Required)

1. **Copy template**: `cp .env.email.example .env`
2. **Edit `.env`** with your SMTP credentials:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Generate at https://myaccount.google.com/apppasswords
ERROR_EMAIL_TO=developer@example.com
ERROR_EMAIL_FROM=reportalin@example.com
```

Gmail users: Use an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

### Development Mode (Disable Emails)

For local testing without SMTP setup:

```bash
export DISABLE_EMAIL_ALERTS=true
make dev
```

**Production:** Never set `DISABLE_EMAIL_ALERTS`. Email alerts are your error monitoring system.

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reportalin": {
      "command": "/path/to/uv",
      "args": ["run", "--directory", "/path/to/RePORTaLiN-Agent", "reportalin-mcp"]
    }
  }
}
```

Restart Claude Desktop. The `search` tool will be available.

## Project Structure

```
src/reportalin/
├── server/
│   ├── tools/
│   │   ├── search.py        # PRIMARY TOOL: Variable search
│   │   ├── _loaders.py      # Data loaders
│   │   └── registry.py      # FastMCP registry
│   ├── __main__.py          # Entry point
│   └── main.py              # FastAPI app (25 lines)
├── data/
│   └── load_dictionary.py   # Excel → JSONL extractor
├── logging.py               # Centralized logging with email notifications
├── core/
│   ├── config.py            # Settings
│   ├── constants.py         # Constants
│   └── exceptions.py        # Custom exceptions
└── types/
    └── models.py            # Pydantic models

tests/
├── unit/                    # 38 tests
└── integration/             # 1 test

data/
└── data_dictionary_and_mapping_specifications/
    └── RePORT_DEB_to_Tables_mapping.xlsx  # Source data

results/
└── data_dictionary_mappings/  # Generated JSONL files (18 files)
```

## Tool: search

```python
search(query: str) -> SearchResult
```

**What it does**: Searches the data dictionary for variables matching a clinical concept.

**Parameters**:
- `query` (str): Clinical concept or variable name (e.g., "HIV", "relapse", "diabetes")

**Returns**: `SearchResult` with:
- `variables`: List of matching variables (field name, description, table, codelist)
- `codelists`: Related codelists with code/description pairs
- `search_terms`: Terms searched (including synonyms)
- `suggestion`: Helpful message if no results found

**Example**:
```python
result = search("relapse")
# Returns: 10 variables related to TB relapse/recurrence
```

**Synonyms** (built-in clinical concept expansion):
- "relapse" → ["relapse", "recurrence", "recurrent", "recur"]
- "diabetes" → ["diabetes", "diabetic", "glucose", "hba1c", "fbg", "rbg"]
- "HIV" → ["hiv", "aids", "hivstat", "retroviral", "cd4"]
- ... (see `src/reportalin/server/tools/search.py` for full list)

## Logging Architecture

- **Centralized**: All logging via `reportalin.logging.get_logger(__name__)`
- **Structured**: JSON output in production, console colors in dev
- **Hierarchical**: Logger names follow module structure (`reportalin.server.tools.search`)
- **Email Alerts**: ERROR/CRITICAL logs automatically email developer (enabled by default)

## Versioning

Versions are **automatically derived from Git tags** (no manual edits):

```bash
# Create a new version
git tag v0.4.0       # Bump minor version
git push origin v0.4.0

# Check current version
make version
```

Version format: `v{MAJOR}.{MINOR}.{PATCH}` (e.g., v0.3.0, v1.0.0)  
Managed by: `setuptools-scm` (2026 PyPA standard)

## Development

### Running Tests

```bash
make test       # Run all tests (39 tests)
make lint       # Check code quality
make clean      # Remove cache/logs
```

### Architecture

- **Stateless**: No sessions, no auth, no database
- **FastMCP**: MCP protocol via FastAPI + FastMCP library
- **Transport**: SSE (Server-Sent Events)
- **Logging**: Structlog with context propagation
- **Data**: Excel → JSONL (extracted once, served from disk)

## Requirements

- Python 3.13+
- uv (package manager)
- Dependencies: fastapi, fastmcp, structlog, pydantic

## License

[Your License]

## Contributing

See [TOOL_DEVELOPMENT_GUIDE.md](TOOL_DEVELOPMENT_GUIDE.md) for contribution guidelines.
