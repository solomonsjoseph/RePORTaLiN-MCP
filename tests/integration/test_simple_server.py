"""
Simple test to verify basic FastMCP tool registration.

This is an integration test that verifies FastMCP tool registration.
Run with: pytest tests/integration/ -m integration
"""

from typing import Annotated

import pytest
from mcp.server.fastmcp import FastMCP
from pydantic import Field

pytestmark = [pytest.mark.integration, pytest.mark.mcp]

# Create a simple server
mcp = FastMCP(name="test-server")


@mcp.tool()
def simple_tool(query: str) -> str:
    """A simple test tool."""
    return f"Query: {query}"


@mcp.tool()
def annotated_tool(
    query: Annotated[
        str,
        Field(
            description="A test query",
            min_length=1,
            max_length=100,
        ),
    ],
) -> str:
    """A tool with annotated parameters."""
    return f"Annotated query: {query}"


async def test_tools():
    print("Testing tool registration...")
    print(f"MCP instance: {mcp}")
    print(f"Has list_tools: {hasattr(mcp, 'list_tools')}")

    try:
        tools = await mcp.list_tools()
        print(f"\n✓ Registered {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}")
            print(
                f"    Description: {tool.description[:80] if tool.description else 'None'}"
            )
    except Exception as e:
        print(f"✗ Error listing tools: {e}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_tools())
