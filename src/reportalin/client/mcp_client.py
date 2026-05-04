"""
Universal MCP Client Adapter.

This module provides a universal client for connecting to MCP servers
and translating tool schemas for different LLM providers (OpenAI, Anthropic).

The client manages the SSE connection lifecycle using AsyncExitStack,
ensuring the connection stays open for the duration of the agent's life.

Design Decisions:
    - Uses AsyncExitStack to manually manage context managers (sse_client, ClientSession)
    - Provides schema adapters for OpenAI and Anthropic tool formats
    - Flattens tool results to text for simpler LLM consumption
    - Implements robust error handling with specific exception types

SSE Connection Flow:
    1. Client calls connect() to establish SSE stream
    2. SSE stream receives 'endpoint' event with message URL
    3. Client can now call list_tools(), call_tool(), etc.
    4. Connection persists until close() is called or context exits

Security:
    - Auth token passed via Authorization header (Bearer scheme)
    - Token never logged or exposed in error messages
    - Connection errors include descriptive messages without sensitive data

Usage:
    >>> from reportalin.client.mcp_client import UniversalMCPClient
    >>>
    >>> # Using async context manager (recommended)
    >>> async with UniversalMCPClient(
    ...     server_url="http://localhost:8000/mcp/sse",
    ...     auth_token="your-secret-token"
    ... ) as client:
    ...     # Get tools for OpenAI
    ...     openai_tools = await client.get_tools_for_openai()
    ...
    ...     # Execute combined_search (DEFAULT tool for all queries)
    ...     result = await client.execute_tool("combined_search", {"concept": "diabetes"})
    ...     print(result)
    >>>
    >>> # Or manage lifecycle manually
    >>> client = UniversalMCPClient(server_url, auth_token)
    >>> await client.connect()
    >>> try:
    ...     tools = await client.get_tools_for_anthropic()
    ...     result = await client.execute_tool("combined_search", {"concept": "HIV status"})
    ... finally:
    ...     await client.close()

Updated: December 2025 - MCP Protocol 2025-03-26 compliance with retry logic
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

if TYPE_CHECKING:
    from collections.abc import Callable

# Configure module logger
_logger = logging.getLogger(__name__)

# Type variable for retry decorator
T = TypeVar("T")

__all__ = [
    "AnthropicTool",
    "MCPAuthenticationError",
    "MCPClientError",
    "MCPConnectionError",
    "MCPRetryConfig",
    "MCPToolExecutionError",
    "OpenAIFunction",
    "OpenAIFunctionParameters",
    "OpenAITool",
    "UniversalMCPClient",
    "create_client",
]


# =============================================================================
# Exception Classes
# =============================================================================


class MCPClientError(Exception):
    """Base exception for MCP client errors."""

    pass


class MCPConnectionError(MCPClientError):
    """
    Raised when connection to the MCP server fails.

    This can occur due to:
    - Server not running or unreachable
    - Network timeouts
    - Invalid server URL
    - SSE stream disconnection
    """

    pass


class MCPAuthenticationError(MCPClientError):
    """
    Raised when authentication fails.

    This occurs when:
    - Invalid or expired auth token (HTTP 401/403)
    - Missing Authorization header
    - Token format incorrect
    """

    pass


class MCPToolExecutionError(MCPClientError):
    """
    Raised when tool execution fails.

    This can occur due to:
    - Tool not found
    - Invalid arguments
    - Server-side execution error
    - Timeout during execution
    """

    def __init__(self, message: str, tool_name: str, is_error: bool = True) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.is_error = is_error


# =============================================================================
# Retry Configuration
# =============================================================================


@dataclass
class MCPRetryConfig:
    """
    Configuration for retry behavior on transient failures.

    Uses exponential backoff with jitter for resilient connections.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Multiplier for exponential backoff
        jitter: Random jitter factor (0.0-1.0) to prevent thundering herd
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: float = 0.1

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.

        Args:
            attempt: The current attempt number (0-indexed)

        Returns:
            Delay in seconds with exponential backoff and jitter
        """
        import random

        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)
        # Add jitter
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)
        return max(0, delay)


async def _retry_async(
    func: Callable[..., Any],
    config: MCPRetryConfig,
    retryable_exceptions: tuple[type[Exception], ...] = (MCPConnectionError,),
) -> Any:
    """
    Execute an async function with retry logic.

    Args:
        func: Async callable to execute
        config: Retry configuration
        retryable_exceptions: Tuple of exception types that trigger retry

    Returns:
        Result of the function call

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = config.get_delay(attempt)
                _logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                _logger.error(
                    f"All {config.max_retries + 1} attempts failed. Last error: {e}"
                )

    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error: no exception captured")


# =============================================================================
# Type Definitions for LLM Tool Formats
# =============================================================================


class OpenAIFunctionParameters(TypedDict, total=False):
    """OpenAI function parameters schema."""

    type: str
    properties: dict[str, Any]
    required: list[str]


class OpenAIFunction(TypedDict):
    """OpenAI function definition."""

    name: str
    description: str
    parameters: OpenAIFunctionParameters


class OpenAITool(TypedDict):
    """
    OpenAI Chat Completions API tool format.

    Reference: https://platform.openai.com/docs/api-reference/chat/create#chat-create-tools
    """

    type: str  # Always "function"
    function: OpenAIFunction


class AnthropicTool(TypedDict):
    """
    Anthropic Claude API tool format.

    Reference: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
    """

    name: str
    description: str
    input_schema: dict[str, Any]


# =============================================================================
# Client State
# =============================================================================


@dataclass
class ClientState:
    """
    Internal state tracking for the MCP client.

    Attributes:
        connected: Whether the client is currently connected
        server_info: Server metadata from initialization
        tools_cache: Cached tool list to avoid repeated fetches
        cache_timestamp: When the cache was last updated
    """

    connected: bool = False
    server_info: dict[str, Any] = field(default_factory=dict)
    tools_cache: list[types.Tool] | None = None
    cache_timestamp: datetime | None = None


# =============================================================================
# Universal MCP Client
# =============================================================================


class UniversalMCPClient:
    """
    Universal client adapter for MCP servers.

    This client connects to an MCP server via SSE transport and provides
    methods to:
    - List available tools with schema adaptation for different LLMs
    - Execute tools and return flattened text results
    - Manage connection lifecycle

    The client uses AsyncExitStack to manage the SSE connection and
    ClientSession context managers, ensuring proper cleanup on exit.

    Attributes:
        server_url: The MCP server SSE endpoint URL
        timeout: Connection timeout in seconds
        sse_read_timeout: SSE read timeout in seconds

    Example:
        >>> async with UniversalMCPClient(
        ...     "http://localhost:8000/mcp/sse",
        ...     "my-auth-token"
        ... ) as client:
        ...     tools = await client.get_tools_for_openai()
        ...     result = await client.execute_tool("combined_search", {"concept": "diabetes"})
    """

    def __init__(
        self,
        server_url: str,
        auth_token: str,
        *,
        timeout: float = 30.0,
        sse_read_timeout: float = 300.0,
        cache_ttl_seconds: float = 60.0,
        retry_config: MCPRetryConfig | None = None,
    ) -> None:
        """
        Initialize the Universal MCP Client.

        Args:
            server_url: The MCP server SSE endpoint URL
                       (e.g., "http://localhost:8000/mcp/sse")
            auth_token: Bearer token for authentication
            timeout: HTTP timeout for regular operations (default: 30s)
            sse_read_timeout: Timeout for SSE read operations (default: 300s)
            cache_ttl_seconds: How long to cache tool list (default: 60s)
            retry_config: Optional retry configuration for transient failures

        Note:
            The connection is not established until connect() is called
            or the client is used as an async context manager.
        """
        self._server_url = server_url
        self._auth_token = auth_token
        self._timeout = timeout
        self._sse_read_timeout = sse_read_timeout
        self._cache_ttl = cache_ttl_seconds
        self._retry_config = retry_config or MCPRetryConfig()

        # Connection management
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._state = ClientState()

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def server_url(self) -> str:
        """The MCP server SSE endpoint URL."""
        return self._server_url

    @property
    def is_connected(self) -> bool:
        """Whether the client is currently connected to the server."""
        return self._state.connected and self._session is not None

    @property
    def server_info(self) -> dict[str, Any]:
        """Server metadata from initialization (empty if not connected)."""
        return self._state.server_info

    # =========================================================================
    # Context Manager Protocol
    # =========================================================================

    async def __aenter__(self) -> UniversalMCPClient:
        """
        Enter async context and establish connection.

        Returns:
            Self for use in async with statement

        Raises:
            MCPConnectionError: If connection fails
            MCPAuthenticationError: If authentication fails
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """
        Exit async context and close connection.

        Ensures proper cleanup even if an exception occurred.
        """
        await self.close()

    # =========================================================================
    # Connection Lifecycle
    # =========================================================================

    async def connect(self) -> None:
        """
        Establish connection to the MCP server.

        This method:
        1. Creates an AsyncExitStack to manage context managers
        2. Establishes SSE connection with auth headers
        3. Creates and initializes ClientSession
        4. Stores server capabilities

        Raises:
            MCPConnectionError: If connection fails (network, server down)
            MCPAuthenticationError: If auth token is invalid (401/403)

        Note:
            This method is idempotent - calling it when already connected
            will raise an error. Use close() first to reconnect.
        """
        if self._state.connected:
            raise MCPConnectionError(
                "Client is already connected. Call close() before reconnecting."
            )

        # Build authorization headers
        headers = {
            "Authorization": f"Bearer {self._auth_token}",
        }

        try:
            # Create exit stack to manage context managers
            self._exit_stack = AsyncExitStack()
            await self._exit_stack.__aenter__()

            # Establish SSE connection
            # sse_client returns (read_stream, write_stream) context manager
            streams = sse_client(
                url=self._server_url,
                headers=headers,
                timeout=self._timeout,
                sse_read_timeout=self._sse_read_timeout,
            )

            read_stream, write_stream = await self._exit_stack.enter_async_context(
                streams
            )

            # Create client session
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # Initialize the session (MCP handshake)
            init_result = await self._session.initialize()

            # Store server info
            self._state.server_info = {
                "protocol_version": init_result.protocolVersion,
                "server_info": {
                    "name": init_result.serverInfo.name
                    if init_result.serverInfo
                    else "unknown",
                    "version": init_result.serverInfo.version
                    if init_result.serverInfo
                    else "unknown",
                },
                "capabilities": {
                    "tools": init_result.capabilities.tools is not None
                    if init_result.capabilities
                    else False,
                    "resources": init_result.capabilities.resources is not None
                    if init_result.capabilities
                    else False,
                    "prompts": init_result.capabilities.prompts is not None
                    if init_result.capabilities
                    else False,
                },
            }

            self._state.connected = True

        except Exception as e:
            # Clean up on failure
            await self._cleanup()

            # Translate exception to appropriate type
            error_msg = str(e).lower()
            if (
                "401" in error_msg
                or "403" in error_msg
                or "unauthorized" in error_msg
                or "forbidden" in error_msg
            ):
                raise MCPAuthenticationError(
                    "Authentication failed: Server rejected the auth token. "
                    "Verify MCP_AUTH_TOKEN is correct."
                ) from e
            else:
                raise MCPConnectionError(
                    f"Failed to connect to MCP server at {self._server_url}: {e}"
                ) from e

    async def connect_with_retry(self) -> None:
        """
        Establish connection with automatic retry on transient failures.

        Uses the configured retry policy to handle temporary network issues.
        Authentication errors are not retried (they're not transient).

        Raises:
            MCPConnectionError: If connection fails after all retries
            MCPAuthenticationError: If authentication fails (not retried)
        """

        async def _do_connect() -> None:
            await self.connect()

        await _retry_async(
            _do_connect,
            self._retry_config,
            retryable_exceptions=(MCPConnectionError,),
        )

    async def close(self) -> None:
        """
        Close the connection to the MCP server.

        This method properly closes all context managers in reverse order
        using the AsyncExitStack. It is safe to call multiple times.
        """
        await self._cleanup()

    async def _cleanup(self) -> None:
        """Internal cleanup method."""
        self._state.connected = False
        self._state.tools_cache = None
        self._state.cache_timestamp = None
        self._session = None

        if self._exit_stack:
            try:
                await self._exit_stack.__aexit__(None, None, None)
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self._exit_stack = None

    async def reconnect(self) -> None:
        """
        Close and reopen the connection.

        Useful for recovering from a broken connection.
        Uses retry logic for the reconnection attempt.
        """
        await self.close()
        await self.connect_with_retry()

    def _ensure_connected(self) -> ClientSession:
        """
        Verify connection and return session.

        Returns:
            The active ClientSession

        Raises:
            MCPConnectionError: If not connected
        """
        if not self._state.connected or self._session is None:
            raise MCPConnectionError(
                "Not connected to MCP server. Call connect() first."
            )
        return self._session

    # =========================================================================
    # Tool Discovery
    # =========================================================================

    async def list_tools(self, *, use_cache: bool = True) -> list[types.Tool]:
        """
        List all available tools from the server.

        Args:
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of MCP Tool objects

        Raises:
            MCPConnectionError: If not connected
        """
        session = self._ensure_connected()

        # Check cache
        if use_cache and self._state.tools_cache is not None:
            cache_age = (
                (
                    datetime.now(timezone.utc) - self._state.cache_timestamp
                ).total_seconds()
                if self._state.cache_timestamp
                else float("inf")
            )

            if cache_age < self._cache_ttl:
                return self._state.tools_cache

        # Fetch from server
        result = await session.list_tools()

        # Update cache
        self._state.tools_cache = list(result.tools)
        self._state.cache_timestamp = datetime.now(timezone.utc)

        return self._state.tools_cache

    async def get_tools_for_openai(self) -> list[OpenAITool]:
        """
        Get tools formatted for OpenAI Chat Completions API.

        Transforms MCP tool schemas to OpenAI's expected format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "Tool description",
                "parameters": { JSON Schema }
            }
        }

        Returns:
            List of tools in OpenAI format

        Raises:
            MCPConnectionError: If not connected
        """
        tools = await self.list_tools()
        return [self._tool_to_openai(tool) for tool in tools]

    async def get_tools_for_anthropic(self) -> list[AnthropicTool]:
        """
        Get tools formatted for Anthropic Claude API.

        Transforms MCP tool schemas to Anthropic's expected format:
        {
            "name": "tool_name",
            "description": "Tool description",
            "input_schema": { JSON Schema }
        }

        Returns:
            List of tools in Anthropic format

        Raises:
            MCPConnectionError: If not connected
        """
        tools = await self.list_tools()
        return [self._tool_to_anthropic(tool) for tool in tools]

    def _tool_to_openai(self, tool: types.Tool) -> OpenAITool:
        """
        Convert MCP Tool to OpenAI function format.

        Args:
            tool: MCP Tool object

        Returns:
            OpenAI-formatted tool dictionary
        """
        # MCP inputSchema is already JSON Schema compatible
        parameters: OpenAIFunctionParameters = {}

        if tool.inputSchema:
            parameters["type"] = tool.inputSchema.get("type", "object")
            if "properties" in tool.inputSchema:
                parameters["properties"] = tool.inputSchema["properties"]
            if "required" in tool.inputSchema:
                parameters["required"] = tool.inputSchema["required"]
        else:
            # Default to empty object schema
            parameters["type"] = "object"
            parameters["properties"] = {}

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or f"Execute the {tool.name} tool",
                "parameters": parameters,
            },
        }

    def _tool_to_anthropic(self, tool: types.Tool) -> AnthropicTool:
        """
        Convert MCP Tool to Anthropic Claude format.

        Args:
            tool: MCP Tool object

        Returns:
            Anthropic-formatted tool dictionary
        """
        # MCP inputSchema is already JSON Schema compatible
        input_schema: dict[str, Any] = tool.inputSchema or {
            "type": "object",
            "properties": {},
        }

        return {
            "name": tool.name,
            "description": tool.description or f"Execute the {tool.name} tool",
            "input_schema": input_schema,
        }

    # =========================================================================
    # Tool Execution
    # =========================================================================

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """
        Execute a tool on the MCP server.

        This method:
        1. Sends the tool call request to the server
        2. Receives the result (list of content blocks)
        3. Flattens the result to a single text string

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments as a dictionary

        Returns:
            Flattened text result from the tool execution.
            Image content is replaced with "[Image Content]" placeholder.

        Raises:
            MCPConnectionError: If not connected
            MCPToolExecutionError: If tool execution fails

        Example:
            >>> # Use combined_search as the DEFAULT tool for all queries
            >>> result = await client.execute_tool(
            ...     "combined_search",
            ...     {"concept": "diabetes prevalence"}
            ... )
            >>> print(result)
        """
        session = self._ensure_connected()

        try:
            # Call the tool
            result = await session.call_tool(tool_name, arguments)

            # Check for error response
            if result.isError:
                error_text = self._flatten_content(result.content)
                raise MCPToolExecutionError(
                    f"Tool '{tool_name}' returned an error: {error_text}",
                    tool_name=tool_name,
                    is_error=True,
                )

            # Flatten content blocks to text
            return self._flatten_content(result.content)

        except MCPToolExecutionError:
            raise  # Re-raise our own exceptions
        except Exception as e:
            raise MCPToolExecutionError(
                f"Failed to execute tool '{tool_name}': {e}",
                tool_name=tool_name,
            ) from e

    def _flatten_content(
        self,
        content: list[types.TextContent | types.ImageContent | types.EmbeddedResource],
    ) -> str:
        """
        Flatten MCP content blocks to a single string.

        Args:
            content: List of MCP content blocks

        Returns:
            Concatenated text content with images replaced by placeholders
        """
        parts: list[str] = []

        for item in content:
            if isinstance(item, types.TextContent):
                parts.append(item.text)
            elif isinstance(item, types.ImageContent):
                # Replace images with placeholder for text-only LLMs
                parts.append("[Image Content]")
            elif isinstance(item, types.EmbeddedResource):
                # Handle embedded resources
                if hasattr(item.resource, "text"):
                    parts.append(item.resource.text)
                else:
                    parts.append(f"[Embedded Resource: {item.resource.uri}]")
            else:
                # Unknown content type
                parts.append(f"[Unknown Content Type: {type(item).__name__}]")

        return "\n".join(parts) if parts else ""

    # =========================================================================
    # Resource Access
    # =========================================================================

    async def list_resources(self) -> list[types.Resource]:
        """
        List all available resources from the server.

        Returns:
            List of MCP Resource objects

        Raises:
            MCPConnectionError: If not connected
        """
        session = self._ensure_connected()
        result = await session.list_resources()
        return list(result.resources)

    async def read_resource(self, uri: str) -> str:
        """
        Read a resource from the server.

        Args:
            uri: Resource URI (e.g., "config://server")

        Returns:
            Resource content as text

        Raises:
            MCPConnectionError: If not connected
        """
        session = self._ensure_connected()
        result = await session.read_resource(uri)

        # Flatten resource contents
        parts: list[str] = []
        for item in result.contents:
            if hasattr(item, "text"):
                parts.append(item.text)
            elif hasattr(item, "blob"):
                parts.append(f"[Binary Content: {len(item.blob)} bytes]")

        return "\n".join(parts)


# =============================================================================
# Convenience Functions
# =============================================================================


async def create_client(
    server_url: str,
    auth_token: str,
    **kwargs: Any,
) -> UniversalMCPClient:
    """
    Create and connect a Universal MCP Client.

    This is a convenience function that creates the client and
    establishes the connection in one step.

    Args:
        server_url: The MCP server SSE endpoint URL
        auth_token: Bearer token for authentication
        **kwargs: Additional arguments passed to UniversalMCPClient

    Returns:
        Connected UniversalMCPClient instance

    Raises:
        MCPConnectionError: If connection fails
        MCPAuthenticationError: If authentication fails

    Important:
        Remember to call close() when done:
        >>> client = await create_client(url, token)
        >>> try:
        ...     result = await client.execute_tool("combined_search", {"concept": "HIV"})
        ... finally:
        ...     await client.close()
    """
    client = UniversalMCPClient(server_url, auth_token, **kwargs)
    await client.connect()
    return client
