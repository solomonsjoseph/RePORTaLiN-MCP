# RePORTaLiN MCP Server - Quick Reference

## ## � Client Integration (MCP SDK v1.26.0)

### Streamable HTTP (Production)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("combined_search", {"query": "HIV"})
        print(result.structured_content["formatted_output"])
```

---

## 📦 Dependenciesh
uv sync                                          # Install deps
uv run uvicorn reportalin.server.main:app       # Run server
curl http://localhost:8000/health               # Test
```

**Connect**: `http://localhost:8000/mcp`

---

## 🛠️ Three Tools

### 1. `combined_search` ⭐ PRIMARY
Dictionary + Datasets in one query.
```python
combined_search(query="HIV")  # Get everything
```

### 2. `search`
Dictionary only (no dataset info).
```python
search(query="diabetes")
```

### 3. `list_dataset_headers`
Dataset variables only (no patient data).
```python
list_dataset_headers()                      # All documented variables
list_dataset_headers(dataset_name="TST")    # Filtered by dataset
```

---

## 📊 Output

All tools return:
- **Structured data** (Pydantic models)
- **Markdown** (`formatted_output` field)
- **Grouped by source** (table/dataset names always shown)

---

## � Client Integration

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("combined_search", {"query": "HIV"})
        print(result.structured_content["formatted_output"])
```

---

## 📦 Dependencies

```toml
"mcp[cli]>=1.26.0,<2.0.0"  # Latest SDK
```

---

## 🧪 Test

```bash
uv run pytest                                    # All tests
uv run mcp dev src/reportalin/server/__main__.py # MCP Inspector
```

---

**MCP SDK**: v1.26.0  
**Transport**: Streamable HTTP (stateless, JSON responses)  
**Status**: ✅ Production Ready

---

## 🛠️ Three Tools

### 1. `combined_search` ⭐ PRIMARY TOOL

**Use When**: You want BOTH dictionary definitions AND dataset availability

```python
# Example
combined_search(query="HIV status")

# Returns:
# - Dictionary: HIV variables with descriptions + codelists
# - Datasets: Which datasets contain HIV variables
# - Summary: Total variables, codelists, data availability
# - Markdown: Pre-formatted table output
```

**Output**: Dictionary results + Dataset availability + Combined summary

---

### 2. `search` (Dictionary Only)

**Use When**: You only want variable definitions (no dataset info)

```python
# Example
search(query="diabetes")

# Returns:
# - Variables: Matched variables with descriptions
# - Codelists: Referenced categorical values
# - Markdown: Pre-formatted table grouped by clinical category
```

**Output**: Dictionary variables + Codelists + Markdown

---

### 3. `list_dataset_headers` (Datasets Only)

**Use When**: You want to see what's in the actual study datasets

```python
# Example - All datasets
list_dataset_headers()

# Example - Specific dataset
list_dataset_headers(dataset_name="TST")

# Returns:
# - Headers: All dataset variables (NO patient data)
# - Markdown: Pre-formatted table grouped by dataset
```

**Output**: Dataset variables + Markdown

---

## 📊 Output Format (All Tools)

Every tool returns **both**:

1. **Structured Data** (Pydantic models)
   - `variables` (list of Variable objects)
   - `codelists` (list of Codelist objects)
   - `total_variables` (int)
   - `query` (str)

2. **Pre-formatted Markdown** (for LLM display)
   - `formatted_output` (str)
   - Markdown tables grouped by source
   - Summary statistics
   - Codelist values

**Example Result**:

```json
{
  "variables": [...],  // Structured data
  "codelists": [...],  // Structured data
  "total_variables": 5,
  "query": "HIV",
  "formatted_output": "# Variables Found: 5\n\n## HIV Screening...\n| Variable | ... |"
}
```

---

## 🎨 Markdown Output Style

All tools use **consistent markdown formatting**:

```markdown
# Summary Statistics (at top)

## Category Name 1 (grouped by table/dataset)
| Variable | Description | Data Type | ... |
|----------|-------------|-----------|-----|
| var1     | ...         | numeric   | ... |

## Category Name 2
...

## Codelists Referenced (if any)

### Codelist Name
- code: description
- code: description
```

**Key Features**:
- ✅ Always shows table/dataset names
- ✅ Grouped by clinical category
- ✅ Markdown tables for structured display
- ✅ Summary statistics at top
- ✅ Codelist values included

---

## 🔧 Client Integration (MCP SDK v1.26.0)

### Streamable HTTP (Production)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # Call tool
        result = await session.call_tool("combined_search", {"query": "HIV"})
        
        # Access structured data
        variables = result.structured_content["variables"]
        
        # Access markdown
        markdown = result.structured_content["formatted_output"]
        print(markdown)
```

---

## 📦 Dependencies (Updated to v1.26.0)

```toml
# pyproject.toml
dependencies = [
    "mcp[cli]>=1.26.0,<2.0.0",  # ⬅️ Latest SDK
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.0.0",
    # ...
]
```

**Install/Update**:
```bash
uv sync
```

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/reportalin --cov-report=html

# Test specific tool
uv run pytest tests/integration/test_search.py -v

# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

---

## 🚦 Server Status Check

```bash
# Check if server is running
curl http://localhost:8000/health

# Expected output
{"status": "healthy"}

# Check MCP endpoint
curl http://localhost:8000/mcp

# Should return MCP protocol info
```

---

## 🔍 MCP Inspector (Testing Tool)

The MCP Inspector is the **official testing tool** for MCP servers:

```bash
# Start server
uv run mcp dev src/reportalin/server/__main__.py

# In another terminal, start inspector
npx -y @modelcontextprotocol/inspector

# Connect to: http://localhost:8000/mcp
```

**Inspector Features**:
- List available tools, resources, prompts
- Call tools with arguments
- View structured and markdown output
- Test error handling

---

## 📝 Best Practices (2026 Edition)

✅ **Always use `combined_search` first** - It's the smart default  
✅ **Use markdown output for display** - Pre-formatted for LLMs  
✅ **Use structured output for logic** - Pydantic models for code  
✅ **Connect via Streamable HTTP** - Recommended transport  
✅ **Group results by source** - Shows table/dataset names  
✅ **Include codelists** - Categorical variable values  
✅ **Provide summaries** - Stats at top of markdown  

---

## 🆘 Common Issues

### Server won't start
```bash
# Check if port is in use
lsof -i :8000

# Use different port
uv run uvicorn reportalin.server.main:app --port 8001
```

### Dependencies out of date
```bash
# Update all dependencies
uv sync --upgrade

# Check installed version
uv pip list | grep mcp
```

### MCP client connection fails
```bash
# Verify server is running
curl http://localhost:8000/health

# Check endpoint
curl http://localhost:8000/mcp

# Check logs
# (logs go to stderr, check terminal output)
```

---

## 📚 Documentation

- **Full Upgrade Guide**: `docs/MCP_SDK_v1.26.0_UPGRADE_SUMMARY.md`
- **MCP SDK Docs**: https://modelcontextprotocol.github.io/python-sdk/
- **MCP Specification**: https://modelcontextprotocol.io/specification/latest
- **FastAPI Docs**: https://fastapi.tiangolo.com/

---

## 🎯 Key Improvements in v1.26.0 Upgrade

1. ✅ **Updated to MCP SDK v1.26.0** (latest as of Jan 2026)
2. ✅ **Added Streamable HTTP transport** (production-ready)
3. ✅ **Markdown output in all tools** (`formatted_output` field)
4. ✅ **Grouped by table/dataset** (always show source names)
5. ✅ **Structured output** (Pydantic V2 models)
6. ✅ **Server metadata** (website_url for documentation)

---

## 💡 Pro Tips

- **Use combined_search by default** - It's the most comprehensive tool
- **Display markdown to users** - It's pre-formatted and looks great
- **Use structured data in code** - Type-safe Pydantic models
- **Group results by source** - Tables/datasets always visible
- **Check codelists** - Categorical values help with analysis planning
- **Use Streamable HTTP** - Production standard

---

**Last Updated**: January 2026  
**MCP SDK Version**: v1.26.0  
**Server Status**: ✅ Production Ready
