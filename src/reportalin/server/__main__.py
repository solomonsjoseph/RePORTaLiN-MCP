"""RePORTaLiN MCP Server Entry Point.

Usage:
    # stdio (Claude Desktop)
    uv run python -m reportalin.server --transport stdio

    # HTTP (Streamable HTTP - production)
    uv run python -m reportalin.server --transport http

    # Or via uvicorn
    uv run uvicorn reportalin.server.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys

from reportalin.core.config import get_settings
from reportalin.logging import configure_logging, get_logger


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
        choices=["stdio", "http"],
        default=None,
        help="Transport: stdio (Claude Desktop) or http (Streamable HTTP). Default from MCP_TRANSPORT env var.",
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
    """Run MCP server in stdio mode (JSON-RPC via stdin/stdout)."""
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

    # Configure centralized logging (stderr + optional file)
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "console")

    # Auto-enable file logging for development debugging
    # Production uses 12-Factor (stderr only, routed by Docker/systemd)
    environment = os.getenv("ENVIRONMENT", "local").lower()
    is_dev = environment in ("local", "development")
    log_file = os.getenv("LOG_FILE") or ("logs/reportalin.log" if is_dev else None)

    # Validate log format
    if log_format not in ("json", "console"):
        log_format = "console"

    # Logging already configured is fine (can happen in dev with make run)
    with contextlib.suppress(RuntimeError):
        configure_logging(
            level=log_level,
            format=log_format,  # type: ignore[arg-type]
            log_file=log_file,
        )

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
            # Streamable HTTP transport via uvicorn
            import uvicorn

            host = args.host or settings.mcp_host
            port = args.port or settings.mcp_port

            uvicorn.run(
                "reportalin.server.main:app",
                host=host,
                port=port,
                reload=args.reload,
                log_level=log_level.lower(),
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
