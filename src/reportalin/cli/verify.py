#!/usr/bin/env python3
"""
RePORTaLiN MCP System Verification Script.

Phase 5: Verification, Testing & Security Hardening

This standalone script verifies that the MCP server is online and operational
WITHOUT requiring an LLM. It connects directly to the server, retrieves the
tool list, and reports the status.

Usage:
    # Basic verification (uses default URL and env token)
    uv run python verify.py

    # Specify server URL
    uv run python verify.py --url http://localhost:8000/mcp/sse

    # Specify auth token
    uv run python verify.py --token your-secret-token

    # Verbose output with tool details
    uv run python verify.py --verbose

    # JSON output for automation
    uv run python verify.py --json

Exit Codes:
    0 - Success: Server is online and tools were retrieved
    1 - Connection failed
    2 - Authentication failed
    3 - Configuration error

See Also:
    - client/mcp_client.py for UniversalMCPClient implementation
    - server/main.py for server endpoints
    - tests/test_server.py for comprehensive tests
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is in path for imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Constants
# =============================================================================

DEFAULT_SERVER_URL = "http://localhost:8000/mcp/sse"
DEFAULT_TIMEOUT = 10.0  # seconds


# =============================================================================
# Result Formatting
# =============================================================================


class VerificationResult:
    """
    Structured result from verification check.

    Attributes:
        success: Whether verification succeeded
        message: Human-readable status message
        tools_count: Number of tools found (if successful)
        tools: List of tool names (if successful)
        server_info: Server metadata (if successful)
        error: Error message (if failed)
        timestamp: When verification was performed
    """

    def __init__(
        self,
        success: bool,
        message: str,
        tools_count: int = 0,
        tools: list[str] | None = None,
        server_info: dict[str, Any] | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.message = message
        self.tools_count = tools_count
        self.tools = tools or []
        self.server_info = server_info or {}
        self.error = error
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for JSON output."""
        return {
            "success": self.success,
            "message": self.message,
            "tools_count": self.tools_count,
            "tools": self.tools,
            "server_info": self.server_info,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Convert result to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


# =============================================================================
# Verification Logic
# =============================================================================


async def verify_server(
    server_url: str,
    auth_token: str,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> VerificationResult:
    """
    Verify the MCP server is operational.

    This function:
    1. Connects to the MCP server via SSE
    2. Retrieves the list of available tools
    3. Returns a structured result

    Args:
        server_url: The MCP server SSE endpoint URL
        auth_token: Bearer token for authentication
        timeout: Connection timeout in seconds
        verbose: Whether to include additional details

    Returns:
        VerificationResult with success/failure status and details
    """
    try:
        # Import client here to avoid import errors if not installed
        from reportalin.client.mcp_client import (
            MCPAuthenticationError,
            MCPConnectionError,
            UniversalMCPClient,
        )
    except ImportError as e:
        return VerificationResult(
            success=False,
            message="Failed to import MCP client",
            error=f"Import error: {e}. Ensure you're running from project root.",
        )

    if verbose:
        print(f"[*] Connecting to: {server_url}")

    try:
        async with UniversalMCPClient(
            server_url=server_url,
            auth_token=auth_token,
            timeout=timeout,
            sse_read_timeout=timeout * 2,
        ) as client:
            if verbose:
                print("[*] Connected successfully")

            # Get tools using OpenAI format (contains all info we need)
            tools = await client.get_tools_for_openai()

            # Extract tool names
            tool_names = [
                tool["function"]["name"]
                for tool in tools
                if "function" in tool and "name" in tool["function"]
            ]

            if verbose:
                print(f"[*] Retrieved {len(tool_names)} tools")

            return VerificationResult(
                success=True,
                message=f"System Online: Found {len(tool_names)} tools",
                tools_count=len(tool_names),
                tools=tool_names,
                server_info=client.server_info,
            )

    except MCPAuthenticationError as e:
        return VerificationResult(
            success=False,
            message="Authentication failed",
            error=str(e),
        )
    except MCPConnectionError as e:
        return VerificationResult(
            success=False,
            message="Connection failed",
            error=str(e),
        )
    except asyncio.TimeoutError:
        return VerificationResult(
            success=False,
            message="Connection timeout",
            error=f"Server did not respond within {timeout} seconds",
        )
    except Exception as e:
        return VerificationResult(
            success=False,
            message="Unexpected error",
            error=f"{type(e).__name__}: {e}",
        )


def get_auth_token_from_env() -> str | None:
    """
    Get authentication token from environment.

    Checks in order:
    1. MCP_AUTH_TOKEN environment variable
    2. .env file in project root

    Returns:
        Token string or None if not found
    """
    # Check environment variable
    token = os.environ.get("MCP_AUTH_TOKEN")
    if token:
        return token

    # Try loading from .env file
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MCP_AUTH_TOKEN="):
                        # Handle quoted values
                        value = line.split("=", 1)[1].strip()
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]
                        return value
        except Exception:
            pass

    return None


# =============================================================================
# CLI
# =============================================================================


def print_result(result: VerificationResult, verbose: bool = False) -> None:
    """
    Print verification result to console with formatting.

    Args:
        result: The verification result to display
        verbose: Whether to show detailed output
    """
    if result.success:
        print(f"\n✅ {result.message}")

        if verbose and result.tools:
            print("\n📋 Available Tools:")
            for tool in sorted(result.tools):
                print(f"   • {tool}")

        if verbose and result.server_info:
            print("\n🖥️  Server Info:")
            for key, value in result.server_info.items():
                print(f"   • {key}: {value}")
    else:
        print(f"\n❌ {result.message}")
        if result.error:
            print(f"   Error: {result.error}")


def main() -> int:
    """
    Main entry point for the verification script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Verify RePORTaLiN MCP server is operational",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python verify.py
  uv run python verify.py --url http://localhost:8000/mcp/sse
  uv run python verify.py --token my-secret-token --verbose
  uv run python verify.py --json
        """,
    )

    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_SERVER_URL,
        help=f"MCP server SSE URL (default: {DEFAULT_SERVER_URL})",
    )

    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Authentication token (default: from MCP_AUTH_TOKEN env var)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Connection timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including tool list",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    # Get auth token
    auth_token = args.token or get_auth_token_from_env()

    if not auth_token:
        if args.json:
            result = VerificationResult(
                success=False,
                message="Configuration error",
                error="No auth token provided. Set MCP_AUTH_TOKEN or use --token",
            )
            print(result.to_json())
        else:
            print("\n❌ Configuration Error")
            print("   No authentication token provided.")
            print("   Set MCP_AUTH_TOKEN environment variable or use --token flag.")
        return 3

    # Run verification
    if not args.json:
        print(f"\n🔍 Verifying MCP Server at: {args.url}")

    result = asyncio.run(
        verify_server(
            server_url=args.url,
            auth_token=auth_token,
            timeout=args.timeout,
            verbose=args.verbose and not args.json,
        )
    )

    # Output result
    if args.json:
        print(result.to_json())
    else:
        print_result(result, verbose=args.verbose)

    # Return appropriate exit code
    if result.success:
        return 0
    elif "Authentication" in result.message:
        return 2
    elif "Connection" in result.message or "timeout" in result.message.lower():
        return 1
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
