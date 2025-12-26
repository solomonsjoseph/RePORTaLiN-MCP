"""
Unified CLI entry point for RePORTaLiN package.

Usage:
    python -m reportalin --help
"""

import sys


def main() -> int:
    """Main entry point for the reportalin CLI."""
    print("RePORTaLiN v0.3.0")
    print("Available commands:")
    print("  reportalin-mcp     - Start the MCP server")
    print("  reportalin-client  - Start the MCP client")
    print()
    print("Run with --help on each command for more information.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
