"""FastMCP server setup and tool registry for RePORTaLiN.

Registers 3 MCP tools:
- combined_search (primary) - unified search across dictionary AND datasets
- search - data dictionary search only
- list_dataset_headers - dataset variables only
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from reportalin.core.config import get_settings
from reportalin.core.constants import SERVER_NAME
from reportalin.server.tools.combined_search import combined_search
from reportalin.server.tools.dataset_headers import list_dataset_headers
from reportalin.server.tools.search import search

__all__ = ["mcp"]

# =============================================================================
# FastMCP Server Instance
# =============================================================================

settings = get_settings()

SYSTEM_INSTRUCTIONS = """
RePORTaLiN MCP Server - RePORT India TB Study Metadata

## Tools (Use combined_search first)

1. **combined_search** - Smart unified search (dictionary + datasets)
2. **search** - Data dictionary only
3. **list_dataset_headers** - Dataset variables only

Examples:
- combined_search("HIV") → HIV variables + dataset availability
- search("diabetes") → DM variable definitions
- list_dataset_headers("TST") → TST dataset variables

PRIVACY: Metadata only - no patient data.
"""

mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SYSTEM_INSTRUCTIONS,
    debug=settings.is_local,
    log_level=settings.log_level.value,
)

# Register tools
mcp.tool()(combined_search)
mcp.tool()(search)
mcp.tool()(list_dataset_headers)
