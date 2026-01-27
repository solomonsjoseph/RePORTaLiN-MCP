#!/usr/bin/env python3
"""Generate Claude Desktop configuration for RePORTaLiN MCP server."""

import json
import shutil
from pathlib import Path


def generate_config() -> None:
    """Generate claude_desktop_config.json with correct paths."""
    # Get absolute path to project root
    project_root = Path(__file__).parent.parent.resolve()

    # Find uv executable
    uv_path = shutil.which("uv")
    if not uv_path:
        print("❌ Error: 'uv' not found in PATH")
        print("   Install uv first: https://github.com/astral-sh/uv")
        return

    # Create config
    config = {
        "mcpServers": {
            "reportalin": {
                "command": uv_path,
                "args": [
                    "run",
                    "--directory",
                    str(project_root),
                    "reportalin-mcp",
                ],
            }
        }
    }

    # Write to file
    config_path = project_root / "claude_desktop_config.json"
    with config_path.open("w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Config generated: {config_path}")
    print()
    print("📋 To use with Claude Desktop:")
    print("   1. Open: ~/Library/Application Support/Claude/claude_desktop_config.json")
    print(f"   2. Copy the content from {config_path}")
    print("   3. Restart Claude Desktop")
    print()
    print("Config content:")
    print("-" * 60)
    print(json.dumps(config, indent=2))
    print("-" * 60)


if __name__ == "__main__":
    generate_config()
