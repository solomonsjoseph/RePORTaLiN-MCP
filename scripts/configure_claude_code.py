#!/usr/bin/env python3
"""
Configure Claude Code MCP server for the current project.
"""
import json
import sys
from pathlib import Path


def main():
    # Get project path from environment or argument
    project_path = sys.argv[1] if len(sys.argv) > 1 else str(Path.cwd())

    # Config file location
    config_path = Path.home() / ".claude.json"

    # Load existing config or create new
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = {"projectsByPath": {}}

    # Ensure projectsByPath exists
    if "projectsByPath" not in config:
        config["projectsByPath"] = {}

    # Ensure project entry exists
    if project_path not in config["projectsByPath"]:
        config["projectsByPath"][project_path] = {
            "allowedTools": [],
            "mcpContextUris": [],
            "mcpServers": {},
            "enabledMcpjsonServers": [],
            "disabledMcpjsonServers": []
        }

    # Add MCP server configuration
    config["projectsByPath"][project_path]["mcpServers"]["reportalin-mcp"] = {
        "type": "stdio",
        "command": f"{project_path}/.venv/bin/python",
        "args": ["-m", "reportalin.server", "--transport", "stdio"],
        "cwd": project_path,
        "env": {
            "REPORTALIN_PRIVACY_MODE": "strict",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "FORCE_COLOR": "0",
            "PYTHONUNBUFFERED": "1"
        }
    }

    # Write updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"  ✓ Added reportalin-mcp to ~/.claude.json")
    print(f"  ✓ Project: {project_path}")


if __name__ == "__main__":
    main()
