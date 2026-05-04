"""
RePORTaLiN MCP Client Adapter Package.

This package provides a universal client adapter for connecting to
MCP servers and translating tool schemas for different LLM providers.

Components:
    - UniversalMCPClient: Main client class for MCP server communication
    - MCPAgent: Agent driver implementing ReAct loop (LLM + Tools)
    - AgentConfig: Configuration dataclass for agent settings
    - Exception classes for error handling
    - create_client: Convenience function for quick client creation

The UniversalMCPClient class (aliased as universal_client) handles:
    - SSE connection lifecycle with AsyncExitStack
    - Bearer token authentication
    - Schema adaptation for OpenAI and Anthropic APIs
    - Tool execution with flattened text output

The MCPAgent class handles:
    - ReAct (Reasoning + Action) loop implementation
    - Multi-turn conversation management
    - Support for OpenAI API and local LLMs (Ollama)
    - Automatic tool execution and result handling

Usage:
    >>> from client import UniversalMCPClient
    >>> # Or use the canonical Phase 3 import:
    >>> from reportalin.client.universal_client import UniversalMCPClient
    >>>
    >>> # Direct MCP client usage (use combined_search as DEFAULT tool)
    >>> async with UniversalMCPClient(
    ...     server_url="http://localhost:8000/mcp/sse",
    ...     auth_token="your-token"
    ... ) as client:
    ...     tools = await client.get_tools_for_openai()
    ...     result = await client.execute_tool("combined_search", {"concept": "diabetes"})
    >>>
    >>> # Agent usage (recommended for LLM integration)
    >>> from client import MCPAgent
    >>> async with await MCPAgent.create() as agent:
    ...     response = await agent.run("What is the diabetes prevalence?")
    ...     print(response)
"""

# Primary imports from mcp_client (implementation)
from reportalin.client.agent import (
    DEFAULT_SYSTEM_PROMPT,
    AgentConfig,
    AgentConfigError,
    AgentError,
    AgentExecutionError,
    MCPAgent,
    run_agent,
)
from reportalin.client.mcp_client import (
    AnthropicTool,
    MCPAuthenticationError,
    MCPClientError,
    MCPConnectionError,
    MCPRetryConfig,
    MCPToolExecutionError,
    OpenAITool,
    UniversalMCPClient,
    create_client,
)
from reportalin.client.react_rag_agent import (
    AgentState,
    LLMProvider,
    MCPToolAdapter,
    QueryType,
    ReActConfig,
    ReActRAGAgent,
    ToolResult,
    run_react_agent,
)

__all__ = [
    # Constants
    "DEFAULT_SYSTEM_PROMPT",
    "AgentConfig",
    "AgentConfigError",
    "AgentError",
    "AgentExecutionError",
    "AgentState",
    "AnthropicTool",
    # Agent classes
    "LLMProvider",
    "MCPAgent",
    "MCPAuthenticationError",
    "MCPToolAdapter",
    # Exception classes
    "MCPClientError",
    "MCPConnectionError",
    # Configuration
    "MCPRetryConfig",
    "MCPToolExecutionError",
    # Type definitions
    "OpenAITool",
    "QueryType",
    "ReActConfig",
    "ReActRAGAgent",
    "ToolResult",
    # Main client class
    "UniversalMCPClient",
    # Convenience functions
    "create_client",
    "run_agent",
    "run_react_agent",
]
