#!/usr/bin/env bash
# =============================================================================
# RePORTaLiN MCP Agent Runner
# =============================================================================
# This script starts the MCP server in the background and runs the agent.
#
# Usage:
#   ./scripts/run_agent.sh "Your prompt here"
#   ./scripts/run_agent.sh  # Uses default test prompt
#
# Environment Variables (loaded from .env):
#   MCP_AUTH_TOKEN    - Required: Authentication token for MCP server
#   LLM_API_KEY       - Required: API key for LLM provider (or OPENAI_API_KEY)
#   LLM_BASE_URL      - Optional: Base URL for local LLMs (Ollama)
#   LLM_MODEL         - Optional: Model to use (default: gpt-4o-mini)
#   MCP_SERVER_URL    - Optional: MCP server URL (default: http://localhost:8000/mcp/sse)
#
# Prerequisites:
#   - uv package manager installed
#   - .env file configured with required variables
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory (for relative paths)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  RePORTaLiN MCP Agent Runner${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Load .env file if it exists
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} Loading environment from .env"
    set -a
    source .env
    set +a
else
    echo -e "${YELLOW}⚠${NC} No .env file found. Using environment variables."
fi

# Check required environment variables
if [ -z "$MCP_AUTH_TOKEN" ]; then
    echo -e "${YELLOW}⚠${NC} MCP_AUTH_TOKEN not set. Server may reject requests."
fi

if [ -z "$LLM_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$LLM_BASE_URL" ]; then
    echo -e "${RED}✗${NC} LLM_API_KEY or OPENAI_API_KEY must be set (unless using local LLM with LLM_BASE_URL)"
    exit 1
fi

# Display configuration
echo -e "\n${BLUE}Configuration:${NC}"
echo -e "  MCP Server URL: ${MCP_SERVER_URL:-http://localhost:8000/mcp/sse}"
echo -e "  LLM Model: ${LLM_MODEL:-gpt-4o-mini}"
if [ -n "$LLM_BASE_URL" ]; then
    echo -e "  LLM Base URL: $LLM_BASE_URL (local LLM mode)"
else
    echo -e "  LLM Provider: OpenAI"
fi

# Check if MCP server is running
MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-8000}"
echo -e "\n${BLUE}Checking MCP server...${NC}"

if curl -s "http://${MCP_HOST}:${MCP_PORT}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} MCP server is running at http://${MCP_HOST}:${MCP_PORT}"
else
    echo -e "${YELLOW}⚠${NC} MCP server not detected at http://${MCP_HOST}:${MCP_PORT}"
    echo -e "  Starting MCP server in background..."
    
    # Start the server in background
    uv run python -m reportalin.server &
    SERVER_PID=$!
    
    # Wait for server to be ready
    echo -n "  Waiting for server"
    for i in {1..30}; do
        if curl -s "http://${MCP_HOST}:${MCP_PORT}/health" > /dev/null 2>&1; then
            echo -e "\n${GREEN}✓${NC} Server started (PID: $SERVER_PID)"
            break
        fi
        echo -n "."
        sleep 1
    done
    
    # Check if server started successfully
    if ! curl -s "http://${MCP_HOST}:${MCP_PORT}/health" > /dev/null 2>&1; then
        echo -e "\n${RED}✗${NC} Failed to start MCP server"
        exit 1
    fi
    
    # Trap to kill server on exit
    trap "echo -e '\n${BLUE}Stopping MCP server...${NC}'; kill $SERVER_PID 2>/dev/null" EXIT
fi

# Run the agent
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running Agent${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"

# Pass through any command line arguments as the prompt
if [ $# -gt 0 ]; then
    uv run python -m reportalin.client.agent "$@"
else
    uv run python -m reportalin.client.agent
fi
