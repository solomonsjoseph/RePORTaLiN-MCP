#!/usr/bin/env python3
"""
Example: Using the Universal MCP Client.

This script demonstrates how to use the UniversalMCPClient to:
1. Connect to an MCP server
2. List available tools in different LLM formats
3. Execute tools and handle results

Prerequisites:
    - MCP server running at http://localhost:8000/mcp/sse
    - Valid auth token (set MCP_AUTH_TOKEN env var or use the token below)

Usage:
    # Set your auth token
    export MCP_AUTH_TOKEN="your-token-here"

    # Run the example
    python -m client.examples.basic_usage

    # Or with uv
    uv run python -m client.examples.basic_usage
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from reportalin.client import (
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    UniversalMCPClient,
)


async def main() -> int:
    """Main example function."""

    # Configuration
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/sse")
    auth_token = os.getenv("MCP_AUTH_TOKEN", "dev-token-change-in-production")

    print("=" * 60)
    print("Universal MCP Client Example")
    print("=" * 60)
    print(f"\nServer URL: {server_url}")
    print(f"Auth Token: {'*' * 10}...{auth_token[-4:] if len(auth_token) > 4 else '****'}")

    # Method 1: Using async context manager (recommended)
    print("\n" + "-" * 60)
    print("Method 1: Using async context manager")
    print("-" * 60)

    try:
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
            timeout=30.0,
        ) as client:
            print("\n✅ Connected to server!")
            print(f"   Server info: {json.dumps(client.server_info, indent=2)}")

            # List tools in OpenAI format
            print("\n📋 Tools (OpenAI format):")
            openai_tools = await client.get_tools_for_openai()
            for tool in openai_tools:
                print(f"   - {tool['function']['name']}: {tool['function']['description'][:50]}...")

            # List tools in Anthropic format
            print("\n📋 Tools (Anthropic format):")
            anthropic_tools = await client.get_tools_for_anthropic()
            for tool in anthropic_tools:
                print(f"   - {tool['name']}: {tool['description'][:50]}...")

            # Execute combined_search tool (DEFAULT for all queries)
            print("\n🔧 Executing 'combined_search' tool (DEFAULT for all analytical queries):")
            result = await client.execute_tool("combined_search", {"concept": "diabetes"})
            print(f"   Result: {result[:200]}...")
            
            # Execute search_data_dictionary tool (ONLY for variable definitions)
            print("\n🔧 Executing 'search_data_dictionary' tool (ONLY for variable definitions):")
            result = await client.execute_tool(
                "search_data_dictionary",
                {"query": "diabetes"}
            )
            print(f"   Result: {result[:200]}...")

            # List resources
            print("\n📦 Available resources:")
            resources = await client.list_resources()
            for resource in resources:
                print(f"   - {resource.uri}")

            # Read a resource
            if resources:
                print(f"\n📖 Reading resource '{resources[0].uri}':")
                content = await client.read_resource(str(resources[0].uri))
                print(f"   Content: {content[:200]}...")

    except MCPAuthenticationError as e:
        print(f"\n❌ Authentication failed: {e}")
        print("   Check your MCP_AUTH_TOKEN environment variable")
        return 1
    except MCPConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        print("   Make sure the MCP server is running at the specified URL")
        return 1
    except MCPToolExecutionError as e:
        print(f"\n❌ Tool execution failed: {e}")
        print(f"   Tool: {e.tool_name}")
        return 1

    # Method 2: Manual lifecycle management
    print("\n" + "-" * 60)
    print("Method 2: Manual lifecycle management")
    print("-" * 60)

    client = UniversalMCPClient(
        server_url=server_url,
        auth_token=auth_token,
    )

    try:
        await client.connect()
        print("\n✅ Connected manually!")

        tools = await client.list_tools()
        print(f"   Found {len(tools)} tools")

    except MCPConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        return 1
    finally:
        await client.close()
        print("   Connection closed")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)

    return 0


# Example: Integration with OpenAI
async def openai_example() -> None:
    """
    Example showing how to use the client with OpenAI.

    Note: Requires openai package installed.
    """
    # This is pseudocode - requires actual OpenAI setup
    """
    from openai import OpenAI

    openai_client = OpenAI()

    async with UniversalMCPClient(server_url, auth_token) as mcp_client:
        # Get tools in OpenAI format
        tools = await mcp_client.get_tools_for_openai()

        # Make a chat completion with tools
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Check the server health"}],
            tools=tools,
        )

        # Handle tool calls
        for tool_call in response.choices[0].message.tool_calls or []:
            result = await mcp_client.execute_tool(
                tool_call.function.name,
                json.loads(tool_call.function.arguments),
            )
            print(f"Tool result: {result}")
    """
    pass


# Example: Integration with Anthropic
async def anthropic_example() -> None:
    """
    Example showing how to use the client with Anthropic.

    Note: Requires anthropic package installed.
    """
    # This is pseudocode - requires actual Anthropic setup
    """
    import anthropic

    claude_client = anthropic.Anthropic()

    async with UniversalMCPClient(server_url, auth_token) as mcp_client:
        # Get tools in Anthropic format
        tools = await mcp_client.get_tools_for_anthropic()

        # Make a message with tools
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Check the server health"}],
            tools=tools,
        )

        # Handle tool use blocks
        for block in response.content:
            if block.type == "tool_use":
                result = await mcp_client.execute_tool(
                    block.name,
                    block.input,
                )
                print(f"Tool result: {result}")
    """
    pass


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
