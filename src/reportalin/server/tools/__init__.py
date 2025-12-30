"""MCP Tools package for RePORTaLiN.

This package provides the MCP tools for study design and variable discovery.
The primary tool is `search` - an LLM-powered variable search that's better
than SQL because it understands clinical concepts and synonyms.

Usage:
    from reportalin.server.tools import search
    result = search("relapse")  # Finds all relapse-related variables
"""

from __future__ import annotations

# Primary tool - LLM-powered search
from reportalin.server.tools.search import (
    Codelist,
    CodelistValue,
    SearchResult,
    Variable,
    search,
)

# FastMCP server instance
from reportalin.server.tools.registry import get_tool_registry, mcp

__all__ = [
    # Primary tool (simplified)
    "search",
    "SearchResult",
    "Variable",
    "Codelist",
    "CodelistValue",
    # FastMCP server
    "mcp",
    "get_tool_registry",
]
