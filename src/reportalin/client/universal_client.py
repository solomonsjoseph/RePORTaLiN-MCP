"""
Universal MCP Client Adapter - Public API Module.

Phase 3: Universal Client Adapter

This module re-exports the UniversalMCPClient from mcp_client.py as the
canonical "Universal Adapter" interface. This provides a clear, documented
entry point for integrating with different LLM providers.

The Universal Adapter supports:
    - OpenAI Chat Completions API format
    - Anthropic Claude API format
    - Native MCP Tool format

Architecture:
    ┌────────────────────────────────────────────────────────────────┐
    │                    Universal Client Adapter                     │
    │  (universal_client.py → re-exports from mcp_client.py)         │
    ├────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   get_tools_for_openai()  ──► OpenAI function calling format   │
    │   get_tools_for_anthropic() ► Anthropic tool use format        │
    │   execute_tool()          ──► MCP JSON-RPC tool invocation     │
    │                                                                 │
    └────────────────────────────────────────────────────────────────┘

Usage:
    >>> from reportalin.client.universal_client import UniversalMCPClient
    >>>
    >>> async with UniversalMCPClient(
    ...     server_url="http://localhost:8000/mcp/sse",
    ...     auth_token="your-secret-token"
    ... ) as client:
    ...     # For OpenAI-based agents
    ...     openai_tools = await client.get_tools_for_openai()
    ...
    ...     # For Anthropic-based agents
    ...     anthropic_tools = await client.get_tools_for_anthropic()
    ...
    ...     # Execute combined_search (DEFAULT tool for all queries)
    ...     result = await client.execute_tool("combined_search", {"concept": "diabetes"})
    ...     print(result)

Why This Module Exists:
    - Provides a clear, discoverable entry point for the Universal Adapter
    - Documents the Phase 3 requirement in the 6-Phase MCP Architecture
    - Allows future expansion of the universal adapter without breaking changes

See Also:
    - client/mcp_client.py - Full implementation with schema adapters
    - client/agent.py - ReAct agent loop that uses this adapter
    - server/main.py - MCP server SSE endpoints
"""

from __future__ import annotations

# =============================================================================
# Re-exports from mcp_client.py
# =============================================================================
from reportalin.client.mcp_client import (
    AnthropicTool,
    MCPAuthenticationError,
    # Exception types
    MCPClientError,
    MCPConnectionError,
    MCPToolExecutionError,
    OpenAIFunction,
    OpenAIFunctionParameters,
    # Type definitions for LLM providers
    OpenAITool,
    # Main client class
    UniversalMCPClient,
)

__all__ = [
    "AnthropicTool",
    "MCPAuthenticationError",
    # Exceptions for error handling
    "MCPClientError",
    "MCPConnectionError",
    "MCPToolExecutionError",
    "OpenAIFunction",
    "OpenAIFunctionParameters",
    # Type definitions for static typing
    "OpenAITool",
    # Primary export - the Universal Adapter
    "UniversalMCPClient",
]


# =============================================================================
# Module-level Documentation
# =============================================================================


def get_supported_providers() -> list[str]:
    """
    Get list of supported LLM provider formats.

    Returns:
        List of supported provider names

    Example:
        >>> providers = get_supported_providers()
        >>> print(providers)
        ['openai', 'anthropic', 'mcp']
    """
    return ["openai", "anthropic", "mcp"]


def get_adapter_version() -> str:
    """
    Get the Universal Adapter version.

    Returns:
        Version string matching the project version
    """
    try:
        from reportalin import __version__

        return __version__
    except ImportError:
        return "unknown"
