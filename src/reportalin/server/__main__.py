"""
RePORTaLiN MCP Server Entry Point.

This module provides the main entry point for the MCP server.
It handles:
  - Command line argument parsing
  - Transport selection (stdio/http/sse)
  - Signal handling for graceful shutdown
  - Server startup with uvicorn (http/sse) or mcp.run() (stdio)

Usage:
    # Run stdio transport (for Claude Desktop)
    uv run python -m reportalin.server --transport stdio

    # Run HTTP/SSE server (default for web clients)
    uv run python -m reportalin.server --transport sse

    # Run with specific options
    uv run python -m reportalin.server --host 0.0.0.0 --port 8000 --reload

    # Or via uvicorn directly
    uv run uvicorn reportalin.server.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import sys

from reportalin.core.config import get_settings
from reportalin.core.logging import configure_logging, get_logger


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="reportalin-mcp",
        description="RePORTaLiN MCP Server - Clinical Data Query System",
    )

    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse", "http"],
        default=None,
        help="Transport protocol: stdio (Claude Desktop), sse/http (web). Default from MCP_TRANSPORT env var.",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Server bind host (default from MCP_HOST env var)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server bind port (default from MCP_PORT env var)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )

    return parser.parse_args()


def run_stdio_server() -> int:
    """
    Run the MCP server in stdio mode for Claude Desktop integration.

    In stdio mode:
    - All JSON-RPC messages are read from stdin
    - All JSON-RPC responses are written to stdout
    - All logs MUST go to stderr to avoid corrupting the protocol

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from reportalin.server.tools import mcp

    # Run the FastMCP server in stdio mode
    # This handles the full MCP protocol including initialize, tools/list, tools/call
    mcp.run(transport="stdio")
    return 0


def main() -> int:
    """
    Main entry point for the RePORTaLiN MCP server.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse command line arguments
    args = parse_args()

    # Handle version flag
    # CRITICAL: Use stderr to avoid corrupting stdio JSON-RPC stream
    if args.version:
        from reportalin.core.constants import (
            PROTOCOL_VERSION,
            SERVER_NAME,
            SERVER_VERSION,
        )

        sys.stderr.write(f"{SERVER_NAME} v{SERVER_VERSION}\n")
        sys.stderr.write(f"MCP Protocol: {PROTOCOL_VERSION}\n")
        return 0

    # Configure logging (structlog already outputs to stderr)
    configure_logging()
    logger = get_logger(__name__)

    # Get settings
    settings = get_settings()

    # Determine transport (CLI arg > env var > default)
    transport = args.transport or settings.mcp_transport

    logger.info(
        "Starting RePORTaLiN MCP Server",
        transport=transport,
        host=args.host or settings.mcp_host,
        port=args.port or settings.mcp_port,
        environment=settings.environment.value,
    )

    try:
        # Route to appropriate transport handler
        if transport == "stdio":
            return run_stdio_server()
        else:
            # HTTP/SSE transport via uvicorn
            from reportalin.server.main import run_server

            run_server(
                host=args.host,
                port=args.port,
                reload=args.reload,
            )
            return 0

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0

    except Exception as e:
        logger.error("Server failed to start", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
