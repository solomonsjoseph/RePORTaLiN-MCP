"""Shared constants for the RePORTaLiN MCP system.

Minimal constants for the 3-tool MCP server.
"""

from __future__ import annotations

__all__ = [
    "DATA_DICTIONARY_PATH",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_TRANSPORT",
    "PROTOCOL_VERSION",
    "SERVER_NAME",
    "SERVER_VERSION",
]

# Server identification
SERVER_NAME = "reportalin-mcp"

# Version from git tags (managed by setuptools-scm)
try:
    from reportalin._version import __version__ as SERVER_VERSION
except ImportError:
    SERVER_VERSION = "0.0.0+unknown"

# MCP Protocol version (March 2025)
PROTOCOL_VERSION = "2025-03-26"

# Transport defaults
DEFAULT_TRANSPORT = "stdio"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# File paths (relative to project root)
DATA_DICTIONARY_PATH = "results/data_dictionary_mappings"
