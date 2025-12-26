"""
Tests for the Universal MCP Client.

This module tests the client adapter including:
- Client initialization
- Schema adaptation for OpenAI and Anthropic
- Tool execution
- Error handling

Note: These tests use mocks to avoid requiring a running server.
Integration tests with a real server are in tests/integration/.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp import types

from client.mcp_client import (
    MCPAuthenticationError,
    MCPClientError,
    MCPConnectionError,
    MCPToolExecutionError,
    UniversalMCPClient,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_mcp_tools() -> list[types.Tool]:
    """Create sample MCP tools for testing (v0.3.0 - Data Dictionary Expert).

    v0.3.0: 3 tools - metadata only, NO patient data or statistics.
    """
    return [
        types.Tool(
            name="prompt_enhancer",
            description="PRIMARY - Intelligent router with confirmation",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_query": {
                        "type": "string",
                        "description": "ANY question about variables/metadata",
                    },
                    "user_confirmation": {"type": "boolean", "default": False},
                },
                "required": ["user_query"],
            },
        ),
        types.Tool(
            name="combined_search",
            description="DEFAULT - Variable discovery with concept expansion (metadata only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "Clinical concept for variable discovery",
                    },
                },
                "required": ["concept"],
            },
        ),
        types.Tool(
            name="search_data_dictionary",
            description="Direct variable lookup (metadata only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "include_codelists": {"type": "boolean", "default": True},
                },
                "required": ["query"],
            },
        ),
    ]


# =============================================================================
# Client Initialization Tests
# =============================================================================


class TestClientInitialization:
    """Tests for UniversalMCPClient initialization."""

    def test_client_creation(self) -> None:
        """Test client can be created with required arguments."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        assert client.server_url == "http://localhost:8000/mcp/sse"
        assert client.is_connected is False

    def test_client_with_custom_timeouts(self) -> None:
        """Test client creation with custom timeout values."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
            timeout=60.0,
            sse_read_timeout=600.0,
            cache_ttl_seconds=120.0,
        )

        assert client._timeout == 60.0
        assert client._sse_read_timeout == 600.0
        assert client._cache_ttl == 120.0


# =============================================================================
# Schema Adaptation Tests
# =============================================================================


class TestSchemaAdaptation:
    """Tests for tool schema adaptation."""

    def test_tool_to_openai_format(self, sample_mcp_tools: list[types.Tool]) -> None:
        """Test conversion to OpenAI tool format."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        tool = sample_mcp_tools[0]  # combined_search
        result = client._tool_to_openai(tool)

        assert result["type"] == "function"
        assert result["function"]["name"] == "combined_search"
        assert (
            "DEFAULT" in result["function"]["description"]
            or "Search" in result["function"]["description"]
        )
        assert result["function"]["parameters"]["type"] == "object"
        assert "concept" in result["function"]["parameters"]["properties"]
        assert result["function"]["parameters"]["required"] == ["concept"]

    def test_tool_to_anthropic_format(self, sample_mcp_tools: list[types.Tool]) -> None:
        """Test conversion to Anthropic tool format."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        tool = sample_mcp_tools[0]  # combined_search
        result = client._tool_to_anthropic(tool)

        assert result["name"] == "combined_search"
        assert "DEFAULT" in result["description"] or "Search" in result["description"]
        assert result["input_schema"]["type"] == "object"
        assert "concept" in result["input_schema"]["properties"]

    def test_tool_with_empty_schema(self) -> None:
        """Test conversion of tool with empty input schema."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        tool = types.Tool(
            name="simple_tool",
            description="A simple tool",
            inputSchema={"type": "object", "properties": {}},
        )

        openai_result = client._tool_to_openai(tool)
        assert openai_result["function"]["parameters"]["type"] == "object"
        assert openai_result["function"]["parameters"]["properties"] == {}

        anthropic_result = client._tool_to_anthropic(tool)
        assert anthropic_result["input_schema"]["type"] == "object"

    def test_tool_without_description(self) -> None:
        """Test conversion of tool without description."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        tool = types.Tool(
            name="no_desc_tool",
            description=None,
            inputSchema={"type": "object"},
        )

        openai_result = client._tool_to_openai(tool)
        assert "no_desc_tool" in openai_result["function"]["description"]

        anthropic_result = client._tool_to_anthropic(tool)
        assert "no_desc_tool" in anthropic_result["description"]


# =============================================================================
# Content Flattening Tests
# =============================================================================


class TestContentFlattening:
    """Tests for content block flattening."""

    def test_flatten_text_content(self) -> None:
        """Test flattening text content blocks."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        content = [
            types.TextContent(type="text", text="Hello"),
            types.TextContent(type="text", text="World"),
        ]

        result = client._flatten_content(content)
        assert result == "Hello\nWorld"

    def test_flatten_image_content(self) -> None:
        """Test flattening with image content (placeholder)."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        content = [
            types.TextContent(type="text", text="Before image"),
            types.ImageContent(type="image", data="base64data", mimeType="image/png"),
            types.TextContent(type="text", text="After image"),
        ]

        result = client._flatten_content(content)
        assert "[Image Content]" in result
        assert "Before image" in result
        assert "After image" in result

    def test_flatten_empty_content(self) -> None:
        """Test flattening empty content list."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        result = client._flatten_content([])
        assert result == ""


# =============================================================================
# Connection State Tests
# =============================================================================


class TestConnectionState:
    """Tests for connection state management."""

    def test_not_connected_initially(self) -> None:
        """Test that client is not connected after creation."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        assert client.is_connected is False
        assert client.server_info == {}

    def test_ensure_connected_raises_when_not_connected(self) -> None:
        """Test that operations fail when not connected."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        with pytest.raises(MCPConnectionError, match="Not connected"):
            client._ensure_connected()

    @pytest.mark.asyncio
    async def test_double_connect_raises_error(self) -> None:
        """Test that connecting twice raises an error."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        # Manually set connected state
        client._state.connected = True

        with pytest.raises(MCPConnectionError, match="already connected"):
            await client.connect()


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for exception classes."""

    def test_mcp_connection_error(self) -> None:
        """Test MCPConnectionError."""
        error = MCPConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, MCPClientError)

    def test_mcp_authentication_error(self) -> None:
        """Test MCPAuthenticationError."""
        error = MCPAuthenticationError("Invalid token")
        assert str(error) == "Invalid token"
        assert isinstance(error, MCPClientError)

    def test_mcp_tool_execution_error(self) -> None:
        """Test MCPToolExecutionError with tool name."""
        error = MCPToolExecutionError(
            "Tool failed",
            tool_name="combined_search",
            is_error=True,
        )

        assert str(error) == "Tool failed"
        assert error.tool_name == "combined_search"
        assert error.is_error is True


# =============================================================================
# Mock Connection Tests
# =============================================================================


class TestMockConnection:
    """Tests using mocked SSE connection."""

    @pytest.mark.asyncio
    async def test_list_tools_with_mock(
        self, sample_mcp_tools: list[types.Tool]
    ) -> None:
        """Test list_tools with mocked session."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        # Mock the session
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=sample_mcp_tools)

        client._session = mock_session
        client._state.connected = True

        tools = await client.list_tools(use_cache=False)

        assert len(tools) == 2
        assert tools[0].name == "combined_search"
        mock_session.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tools_for_openai_with_mock(
        self, sample_mcp_tools: list[types.Tool]
    ) -> None:
        """Test get_tools_for_openai with mocked session."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=sample_mcp_tools)

        client._session = mock_session
        client._state.connected = True

        tools = await client.get_tools_for_openai()

        assert len(tools) == 2
        assert all(t["type"] == "function" for t in tools)
        assert tools[0]["function"]["name"] == "combined_search"

    @pytest.mark.asyncio
    async def test_get_tools_for_anthropic_with_mock(
        self, sample_mcp_tools: list[types.Tool]
    ) -> None:
        """Test get_tools_for_anthropic with mocked session."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=sample_mcp_tools)

        client._session = mock_session
        client._state.connected = True

        tools = await client.get_tools_for_anthropic()

        assert len(tools) == 2
        assert tools[0]["name"] == "combined_search"
        assert "input_schema" in tools[0]

    @pytest.mark.asyncio
    async def test_execute_tool_with_mock(self) -> None:
        """Test execute_tool with mocked session."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        # Mock tool result
        mock_result = MagicMock()
        mock_result.isError = False
        mock_result.content = [
            types.TextContent(
                type="text", text='{"concept": "diabetes", "variables_found": 5}'
            ),
        ]

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result

        client._session = mock_session
        client._state.connected = True

        result = await client.execute_tool("combined_search", {"concept": "diabetes"})

        assert "diabetes" in result or "variables_found" in result
        mock_session.call_tool.assert_called_once_with(
            "combined_search", {"concept": "diabetes"}
        )

    @pytest.mark.asyncio
    async def test_execute_tool_error_response(self) -> None:
        """Test execute_tool with error response."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        # Mock error result
        mock_result = MagicMock()
        mock_result.isError = True
        mock_result.content = [
            types.TextContent(type="text", text="Search validation failed"),
        ]

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result

        client._session = mock_session
        client._state.connected = True

        with pytest.raises(MCPToolExecutionError) as exc_info:
            await client.execute_tool("combined_search", {"concept": "invalid"})

        assert exc_info.value.tool_name == "combined_search"
        assert "Search validation failed" in str(exc_info.value)


# =============================================================================
# Cache Tests
# =============================================================================


class TestToolsCache:
    """Tests for tools caching."""

    @pytest.mark.asyncio
    async def test_cache_is_used(self, sample_mcp_tools: list[types.Tool]) -> None:
        """Test that cached tools are returned on subsequent calls."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
            cache_ttl_seconds=60.0,
        )

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=sample_mcp_tools)

        client._session = mock_session
        client._state.connected = True

        # First call fetches
        await client.list_tools()
        assert mock_session.list_tools.call_count == 1

        # Second call uses cache
        await client.list_tools()
        assert mock_session.list_tools.call_count == 1  # Still 1

    @pytest.mark.asyncio
    async def test_cache_bypass(self, sample_mcp_tools: list[types.Tool]) -> None:
        """Test that cache can be bypassed."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=sample_mcp_tools)

        client._session = mock_session
        client._state.connected = True

        # First call fetches
        await client.list_tools()

        # Second call with use_cache=False fetches again
        await client.list_tools(use_cache=False)
        assert mock_session.list_tools.call_count == 2
