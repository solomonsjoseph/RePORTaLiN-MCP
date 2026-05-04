"""
Integration tests for the Universal MCP Client.

These tests verify the client can connect to and communicate with
a real MCP server. They require the server to be running.

Run with: pytest tests/integration/test_mcp_client.py -v

Note: Most tests are skipped by default unless a server is running.
Set MCP_INTEGRATION_TEST=1 to enable live server tests.
"""

import os

import pytest

from reportalin.client import (
    MCPAuthenticationError,
    MCPConnectionError,
    UniversalMCPClient,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.mcp,
    pytest.mark.asyncio,
]

# Skip live server tests unless explicitly enabled
LIVE_TESTS_ENABLED = os.getenv("MCP_INTEGRATION_TEST", "0") == "1"
SKIP_REASON = "Set MCP_INTEGRATION_TEST=1 to run live server tests"


# =============================================================================
# Connection Tests (Mocked)
# =============================================================================


class TestClientConnection:
    """Tests for client connection handling."""

    async def test_client_not_connected_initially(self) -> None:
        """Test that client is not connected after creation."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        assert client.is_connected is False
        assert client.server_info == {}

    async def test_operations_fail_when_not_connected(self) -> None:
        """Test that operations fail when not connected."""
        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        with pytest.raises(MCPConnectionError, match="Not connected"):
            await client.list_tools()

    async def test_connection_to_invalid_url_fails(self) -> None:
        """Test that connecting to invalid URL raises error."""
        client = UniversalMCPClient(
            server_url="http://localhost:99999/invalid",
            auth_token="test-token",
            timeout=2.0,  # Short timeout for test
        )

        with pytest.raises(MCPConnectionError):
            await client.connect()


# =============================================================================
# Live Server Tests (Require Running Server)
# =============================================================================


@pytest.mark.skipif(not LIVE_TESTS_ENABLED, reason=SKIP_REASON)
class TestLiveServerConnection:
    """Tests that require a running MCP server."""

    @pytest.fixture
    def server_url(self) -> str:
        """Get server URL from environment."""
        return os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/sse")

    @pytest.fixture
    def auth_token(self) -> str:
        """Get auth token from environment."""
        token = os.getenv("MCP_AUTH_TOKEN", "")
        if not token:
            pytest.skip("MCP_AUTH_TOKEN not set")
        return token

    async def test_connect_to_live_server(
        self, server_url: str, auth_token: str
    ) -> None:
        """Test connecting to a live MCP server."""
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:
            assert client.is_connected is True
            assert "server_info" in client.server_info

    async def test_list_tools_from_live_server(
        self, server_url: str, auth_token: str
    ) -> None:
        """Test listing tools from a live server."""
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:
            tools = await client.list_tools()

            assert len(tools) >= 10
            tool_names = [t.name for t in tools]
            # Primary tool (DEFAULT for all queries)
            assert "combined_search" in tool_names

    async def test_get_openai_tools_from_live_server(
        self, server_url: str, auth_token: str
    ) -> None:
        """Test getting tools in OpenAI format from live server."""
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:
            tools = await client.get_tools_for_openai()

            assert len(tools) >= 10
            assert all(t["type"] == "function" for t in tools)
            assert all("function" in t for t in tools)

    async def test_get_anthropic_tools_from_live_server(
        self, server_url: str, auth_token: str
    ) -> None:
        """Test getting tools in Anthropic format from live server."""
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:
            tools = await client.get_tools_for_anthropic()

            assert len(tools) >= 10
            assert all("name" in t for t in tools)
            assert all("input_schema" in t for t in tools)

    async def test_execute_combined_search_on_live_server(
        self, server_url: str, auth_token: str
    ) -> None:
        """Test executing combined_search tool (DEFAULT) on live server."""
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:
            result = await client.execute_tool(
                "combined_search", {"concept": "diabetes"}
            )

            assert (
                "concept" in result.lower()
                or "variables" in result.lower()
                or "diabetes" in result.lower()
            )

    async def test_list_resources_from_live_server(
        self, server_url: str, auth_token: str
    ) -> None:
        """Test listing resources from live server."""
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
        ) as client:
            resources = await client.list_resources()

            assert len(resources) >= 1
            uris = [str(r.uri) for r in resources]
            assert "config://server" in uris

    async def test_invalid_token_fails(self, server_url: str) -> None:
        """Test that invalid token raises authentication error."""
        client = UniversalMCPClient(
            server_url=server_url,
            auth_token="invalid-token-12345",
        )

        with pytest.raises((MCPAuthenticationError, MCPConnectionError)):
            await client.connect()


# =============================================================================
# Schema Format Tests
# =============================================================================


class TestSchemaFormats:
    """Tests for schema format conversions."""

    async def test_openai_format_structure(self) -> None:
        """Test OpenAI format has correct structure."""
        from mcp import types

        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        tool = types.Tool(
            name="test_tool",
            description="A test tool for unit testing",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        )

        result = client._tool_to_openai(tool)

        # Verify OpenAI structure
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool for unit testing"
        assert result["function"]["parameters"]["type"] == "object"
        assert "query" in result["function"]["parameters"]["properties"]
        assert result["function"]["parameters"]["required"] == ["query"]

    async def test_anthropic_format_structure(self) -> None:
        """Test Anthropic format has correct structure."""
        from mcp import types

        client = UniversalMCPClient(
            server_url="http://localhost:8000/mcp/sse",
            auth_token="test-token",
        )

        tool = types.Tool(
            name="test_tool",
            description="A test tool for unit testing",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        )

        result = client._tool_to_anthropic(tool)

        # Verify Anthropic structure
        assert result["name"] == "test_tool"
        assert result["description"] == "A test tool for unit testing"
        assert result["input_schema"]["type"] == "object"
        assert "query" in result["input_schema"]["properties"]
