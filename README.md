# RePORTaLiN MCP Server

> **Smart clinical variable discovery for RePORT India TB study - 3 intelligent tools**

## What It Does

Provides intelligent variable search for the RePORT India tuberculosis cohort study. Designed for researchers, data scientists, and Claude AI to quickly find relevant clinical variables with privacy-by-default.

### Three Tools (Use combined_search First!)

1. **`combined_search`** 🌟 **USE THIS FIRST** - One-stop smart search across dictionary AND datasets
2. **`search`** - Dictionary-only search when you need definitions without dataset info
3. **`list_dataset_headers`** - Dataset-only listing when you only need available variables

### Example Usage

**PRIMARY TOOL - Combined Search (RECOMMENDED):**
```
User: "What HIV variables do we have?"
Tool: combined_search("HIV")
Returns: HIV variables from dictionary + which are available in datasets + summary
```

**Dictionary-only search (when you don't need dataset info):**
```
User: "What variables track TB relapse?"
Tool: search("relapse")
Returns: Variables for relapse, recurrence, treatment outcomes (definitions only)
```

**Dataset-only listing (when you only need availability):**
```
User: "What TST variables are documented?"
Tool: list_dataset_headers("TST")
Returns: All TST variables with descriptions
```

## Key Features

- **Privacy-First**: No file names or internal details exposed to LLM
- **Concept Understanding**: "relapse" finds "recurrence", "recur" automatically
- **Clinical Synonyms**: "diabetes" expands to DM, glucose, HbA1c, OGTT
- **Structured Output**: Ready for analysis planning
- **Fast**: Instant concept-based retrieval

## Quick Start

```bash
# Setup system (install + extract data)
make run

# Then start server for Claude Desktop
make serve

# Or run full dev cycle
make dev
```

Individual commands:
```bash
make install    # Install dependencies
make extract    # Process data dictionary
make serve      # Start MCP server (stdio - waits for Claude)
make test       # Run tests
```

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reportalin": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/RePORTaLiN-Agent",
        "reportalin-mcp"
      ]
    }
  }
}
```

**Auto-generation (recommended):** Run `make config` to generate `claude_desktop_config.json` with the correct paths automatically. Then copy its contents to your Claude Desktop config.

Replace `/absolute/path/to/RePORTaLiN-Agent` with your actual path if copying manually.

Restart Claude Desktop. All three tools (`combined_search`, `search`, `list_dataset_headers`) will be available.

## Logging Configuration

**Development:** File logging is auto-enabled to `logs/reportalin.log` for easy debugging.

**Production:** Logs to stderr only (12-Factor App compliant). Use Docker/systemd to route logs.

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_FORMAT` | `console` | Output format: `console` (dev) or `json` (production) |
| `LOG_FILE` | `logs/reportalin.log` (dev) | File path for persistent logs. Set to empty to disable. |
| `ENVIRONMENT` | `local` | `local`/`development` enables file logging, `production` disables it |

**Debug with verbose logging:**
```bash
LOG_LEVEL=DEBUG make serve
tail -f logs/reportalin.log  # Watch logs in real-time
```

Logs are rotated automatically (10MB max, 5 backups).

## Requirements

- Python 3.13+
- uv (package manager)

## License

MIT
