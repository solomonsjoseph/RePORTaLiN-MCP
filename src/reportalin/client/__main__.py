"""
RePORTaLiN MCP Client Entry Point.

This module provides the main entry point for the MCP client adapter.
It demonstrates connection to an MCP server and tool execution.

Usage:
    # Set your auth token
    export MCP_AUTH_TOKEN="your-token-here"

    # Run client demo
    uv run python -m client

    # Run with custom server URL
    uv run python -m client --server http://localhost:9000/mcp/sse

    # List tools in OpenAI format
    uv run python -m client --format openai
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from client import (
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    UniversalMCPClient,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="reportalin-client",
        description="RePORTaLiN MCP Client - Connect to MCP servers",
    )

    parser.add_argument(
        "--server",
        type=str,
        default=os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/sse"),
        help="MCP server SSE endpoint URL",
    )

    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("MCP_AUTH_TOKEN", ""),
        help="Authentication token (or use MCP_AUTH_TOKEN env var)",
    )

    parser.add_argument(
        "--format",
        choices=["mcp", "openai", "anthropic"],
        default="mcp",
        help="Output format for tool listing",
    )

    parser.add_argument(
        "--execute",
        type=str,
        default=None,
        help="Tool name to execute (e.g., 'combined_search')",
    )

    parser.add_argument(
        "--args",
        type=str,
        default="{}",
        help="Tool arguments as JSON string",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )

    return parser.parse_args()


async def run_client(args: argparse.Namespace) -> int:
    """Run the MCP client with the given arguments."""
    if not args.token:
        print("Error: No auth token provided.", file=sys.stderr)
        print("Set MCP_AUTH_TOKEN env var or use --token", file=sys.stderr)
        return 1

    print(f"Connecting to {args.server}...", file=sys.stderr)

    try:
        async with UniversalMCPClient(
            server_url=args.server,
            auth_token=args.token,
        ) as client:
            print("Connected!", file=sys.stderr)

            if args.execute:
                # Execute a tool
                tool_args = json.loads(args.args)
                print(f"Executing {args.execute}...", file=sys.stderr)
                result = await client.execute_tool(args.execute, tool_args)
                print(result)
            else:
                # List tools
                if args.format == "openai":
                    tools = await client.get_tools_for_openai()
                elif args.format == "anthropic":
                    tools = await client.get_tools_for_anthropic()
                else:
                    mcp_tools = await client.list_tools()
                    tools = [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.inputSchema,
                        }
                        for t in mcp_tools
                    ]

                print(json.dumps(tools, indent=2))

            return 0

    except MCPAuthenticationError as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1
    except MCPConnectionError as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1
    except MCPToolExecutionError as e:
        print(f"Tool execution failed: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in --args: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """
    Main entry point for the RePORTaLiN MCP client.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    if args.version:
        print("RePORTaLiN MCP Client v2.0.0")
        print("Universal adapter for MCP servers")
        return 0

    return asyncio.run(run_client(args))


if __name__ == "__main__":
    sys.exit(main())
