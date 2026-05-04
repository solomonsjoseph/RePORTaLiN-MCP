"""
MCP Agent Driver - ReAct Loop Implementation.

This module implements the agent logic that connects an LLM (Brain) to
the MCP Server (Body/Tools) via the Universal MCP Client Adapter.

The agent follows the ReAct (Reasoning + Action) pattern:
1. Receive user input
2. Send to LLM with available tools
3. If LLM requests tool calls, execute them via MCP
4. Return tool results to LLM for final response
5. Repeat until LLM provides a final answer

Design Decisions:
    - Uses AsyncOpenAI for non-blocking LLM calls
    - Supports both OpenAI API and local LLMs (Ollama) via base_url
    - Manages conversation history for multi-turn interactions
    - Implements proper cleanup with try/finally patterns
    - Configurable via environment variables or dataclass

Architecture:
    ┌─────────────────┐
    │   User Input    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐     tools/list      ┌─────────────────┐
    │    MCPAgent     │◄───────────────────►│   MCP Server    │
    │   (ReAct Loop)  │     tools/call      │   (via SSE)     │
    └────────┬────────┘                     └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │   LLM Provider  │
    │ (OpenAI/Ollama) │
    └─────────────────┘

Usage:
    # Using environment variables
    >>> agent = await MCPAgent.create()
    >>> response = await agent.run("Check the system status")
    >>> await agent.close()

    # Using context manager (recommended)
    >>> async with MCPAgent.create() as agent:
    ...     response = await agent.run("Query the database")
    ...     print(response)

    # Command line
    $ uv run python -m client.agent "Your prompt here"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

from reportalin.client.mcp_client import (
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    UniversalMCPClient,
)

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessage,
        ChatCompletionMessageParam,
        ChatCompletionMessageToolCall,
    )

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "AgentConfig",
    "AgentConfigError",
    "AgentError",
    "AgentExecutionError",
    "MCPAgent",
    "run_agent",
]


# =============================================================================
# Exception Classes
# =============================================================================


class AgentError(Exception):
    """Base exception for agent errors."""


class AgentConfigError(AgentError):
    """Raised when agent configuration is invalid or missing required values."""


class AgentExecutionError(AgentError):
    """Raised when agent execution fails during the ReAct loop."""


# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class AgentConfig:
    """
    Configuration for the MCP Agent.

    Loads settings from environment variables with sensible defaults.
    Supports both OpenAI API and local LLMs via base_url override.

    Attributes:
        llm_api_key: API key for the LLM provider (required for OpenAI)
        llm_base_url: Custom base URL for LLM API (enables Ollama support)
        llm_model: Model identifier to use
        mcp_server_url: MCP server SSE endpoint URL
        mcp_auth_token: Authentication token for MCP server
        max_iterations: Maximum tool call iterations to prevent infinite loops
        temperature: LLM temperature for response generation
        system_prompt: System prompt defining agent behavior

    Environment Variables:
        LLM_API_KEY: API key (defaults to OPENAI_API_KEY if not set)
        LLM_BASE_URL: Optional base URL for local LLMs (e.g., http://localhost:11434/v1)
        LLM_MODEL: Model to use (default: gpt-4o-mini)
        MCP_SERVER_URL: MCP server endpoint (default: http://localhost:8000/mcp/sse)
        MCP_AUTH_TOKEN: Authentication token for MCP server
    """

    llm_api_key: str
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    mcp_server_url: str = "http://localhost:8000/mcp/sse"
    mcp_auth_token: str = ""
    max_iterations: int = 10
    temperature: float = 0.7
    system_prompt: str = field(default_factory=lambda: DEFAULT_SYSTEM_PROMPT)

    @classmethod
    def from_env(cls) -> AgentConfig:
        """
        Create configuration from environment variables.

        Loads .env file if present, then reads configuration from environment.

        Returns:
            AgentConfig instance with loaded settings

        Raises:
            AgentConfigError: If required configuration is missing
        """
        # Load .env file if present
        load_dotenv()

        # Get API key (try LLM_API_KEY first, then OPENAI_API_KEY)
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

        # Get base URL (if set, enables local LLM support)
        base_url = os.getenv("LLM_BASE_URL")

        # For local LLMs, API key might not be required
        if not api_key and not base_url:
            raise AgentConfigError(
                "LLM_API_KEY or OPENAI_API_KEY must be set when not using a local LLM. "
                "Set LLM_BASE_URL for local LLM support (e.g., http://localhost:11434/v1)"
            )

        # Get MCP auth token
        mcp_token = os.getenv("MCP_AUTH_TOKEN") or ""
        if not mcp_token:
            # In development, warn but don't fail
            print("⚠️  Warning: MCP_AUTH_TOKEN not set. Server may reject requests.")

        return cls(
            llm_api_key=api_key,
            llm_base_url=base_url if base_url else None,
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/sse"),
            mcp_auth_token=mcp_token,
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "10")),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
        )

    @property
    def is_local_llm(self) -> bool:
        """Check if using a local LLM (Ollama, etc.)."""
        return self.llm_base_url is not None

    @property
    def provider_name(self) -> str:
        """Get a human-readable provider name."""
        if self.llm_base_url:
            url_lower = self.llm_base_url.lower()
            # Check for Ollama: either by name or by standard port (11434)
            if "ollama" in url_lower or ":11434" in url_lower:
                return "Ollama"
            elif "localhost" in url_lower or "127.0.0.1" in url_lower:
                return "Local LLM"
            return "Custom API"
        return "OpenAI"


# Default system prompt for the agent
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools via the Model Context Protocol (MCP).

Your capabilities include:
- Querying databases for clinical and research data
- Searching data dictionaries for field definitions
- Retrieving aggregate statistics with privacy protection
- Checking system health and status

When responding:
1. Use the available tools to gather information before answering
2. Be precise and cite data from tool responses
3. If a query might return sensitive data, mention privacy protections
4. If you're unsure, ask clarifying questions

Always prioritize accuracy over speed. Use tools to verify information rather than guessing."""


# =============================================================================
# Agent Implementation
# =============================================================================


class MCPAgent:
    """
    MCP Agent implementing the ReAct (Reasoning + Action) pattern.

    This agent connects an LLM to MCP tools, enabling autonomous task
    completion through iterative reasoning and tool execution.

    The ReAct Loop:
        1. User provides a prompt
        2. Agent sends prompt + available tools to LLM
        3. LLM either responds directly or requests tool calls
        4. If tool calls requested:
           a. Execute each tool via MCP
           b. Append results to conversation history
           c. Send updated history back to LLM
        5. Repeat until LLM provides final response (no tool calls)

    Attributes:
        config: Agent configuration
        mcp_client: Universal MCP Client for server communication
        llm_client: AsyncOpenAI client for LLM calls
        messages: Conversation history

    Example:
        >>> config = AgentConfig.from_env()
        >>> async with MCPAgent(config) as agent:
        ...     response = await agent.run("Check the system status")
        ...     print(response)
    """

    def __init__(
        self,
        config: AgentConfig,
        mcp_client: UniversalMCPClient | None = None,
        llm_client: AsyncOpenAI | None = None,
    ) -> None:
        """
        Initialize the MCP Agent.

        Args:
            config: Agent configuration
            mcp_client: Optional pre-configured MCP client
            llm_client: Optional pre-configured LLM client
        """
        self.config = config
        self._mcp_client = mcp_client
        self._llm_client = llm_client
        self._connected = False
        # Using Any for tools since OpenAITool TypedDict is structurally compatible
        # with ChatCompletionToolParam but mypy can't verify this
        self._tools: list[Any] = []
        self._tool_names: list[str] = []

        # Conversation history
        self.messages: list[ChatCompletionMessageParam] = []

    @classmethod
    async def create(
        cls,
        config: AgentConfig | None = None,
    ) -> MCPAgent:
        """
        Factory method to create and initialize an agent.

        This is the recommended way to create an agent as it handles
        async initialization properly.

        Args:
            config: Optional configuration (loads from env if not provided)

        Returns:
            Initialized MCPAgent ready for use

        Example:
            >>> agent = await MCPAgent.create()
            >>> try:
            ...     response = await agent.run("Hello")
            ... finally:
            ...     await agent.close()
        """
        if config is None:
            config = AgentConfig.from_env()

        agent = cls(config)
        await agent.connect()
        return agent

    # =========================================================================
    # Context Manager Protocol
    # =========================================================================

    async def __aenter__(self) -> MCPAgent:
        """Enter async context and connect to services."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context and cleanup resources."""
        await self.close()

    # =========================================================================
    # Connection Lifecycle
    # =========================================================================

    async def connect(self) -> None:
        """
        Connect to MCP server and initialize LLM client.

        This method:
        1. Creates and connects the MCP client
        2. Fetches available tools from the server
        3. Initializes the LLM client
        4. Sets up the system prompt

        Raises:
            MCPConnectionError: If MCP server connection fails
            MCPAuthenticationError: If MCP authentication fails
        """
        if self._connected:
            return

        # Initialize MCP client if not provided
        if self._mcp_client is None:
            self._mcp_client = UniversalMCPClient(
                server_url=self.config.mcp_server_url,
                auth_token=self.config.mcp_auth_token,
            )

        # Connect to MCP server
        try:
            await self._mcp_client.connect()
        except MCPAuthenticationError:
            print("❌ Authentication failed. Check MCP_AUTH_TOKEN.")
            raise
        except MCPConnectionError as e:
            print(f"❌ Failed to connect to MCP server: {e}")
            raise

        # Fetch available tools
        self._tools = await self._mcp_client.get_tools_for_openai()
        self._tool_names = [t["function"]["name"] for t in self._tools]

        # Initialize LLM client if not provided
        if self._llm_client is None:
            client_kwargs: dict[str, Any] = {}

            if self.config.llm_api_key:
                client_kwargs["api_key"] = self.config.llm_api_key

            if self.config.llm_base_url:
                client_kwargs["base_url"] = self.config.llm_base_url
                # For local LLMs, API key might be a placeholder
                if not self.config.llm_api_key:
                    client_kwargs["api_key"] = "ollama"  # Placeholder for local LLMs

            self._llm_client = AsyncOpenAI(**client_kwargs)

        # Initialize conversation with system prompt
        self.messages = [{"role": "system", "content": self.config.system_prompt}]

        self._connected = True

        # Log connection success
        print(f"🔌 Connected to MCP Server ({self.config.mcp_server_url})")
        print(f"🧠 LLM Provider: {self.config.provider_name} ({self.config.llm_model})")
        print(f"🛠️  Tools loaded: {self._tool_names}")

    async def close(self) -> None:
        """
        Close connections and cleanup resources.

        Safe to call multiple times.
        """
        if self._mcp_client is not None:
            await self._mcp_client.close()

        if self._llm_client is not None:
            await self._llm_client.close()

        self._connected = False
        print("👋 Agent disconnected")

    def _ensure_connected(self) -> None:
        """Verify agent is connected.

        Raises:
            AgentError: If agent is not connected.
        """
        if not self._connected:
            raise AgentError("Agent not connected. Call connect() first.")

    # =========================================================================
    # ReAct Loop
    # =========================================================================

    async def run(
        self,
        user_prompt: str,
        *,
        stream: bool = False,
    ) -> str:
        """
        Execute the ReAct loop for a user prompt.

        This is the main entry point for agent interaction. It:
        1. Adds the user prompt to conversation history
        2. Calls the LLM with available tools
        3. Processes any tool calls iteratively
        4. Returns the final response

        Args:
            user_prompt: The user's input/question
            stream: Whether to stream the response (not yet implemented)

        Returns:
            The agent's final response as a string

        Raises:
            AgentError: If not connected
            AgentExecutionError: If execution fails
        """
        self._ensure_connected()

        print(f"\n{'=' * 60}")
        print(f"📝 User: {user_prompt}")
        print(f"{'=' * 60}\n")

        # Add user message to history
        self.messages.append({"role": "user", "content": user_prompt})

        iteration = 0

        while iteration < self.config.max_iterations:
            iteration += 1
            print(f"🔄 Iteration {iteration}/{self.config.max_iterations}")

            # Step A: Call LLM with tools
            response = await self._call_llm()

            # Get the assistant message
            assistant_message = response.choices[0].message

            # Check for tool calls
            if assistant_message.tool_calls:
                # Step B: Handle tool calls
                await self._handle_tool_calls(assistant_message)
            else:
                # No tool calls - we have the final response
                final_response = assistant_message.content or ""

                # Add assistant response to history
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": final_response,
                    }
                )

                print(f"\n{'=' * 60}")
                print(f"🤖 Agent: {final_response}")
                print(f"{'=' * 60}\n")

                return final_response

        # Max iterations reached
        raise AgentExecutionError(
            f"Agent reached maximum iterations ({self.config.max_iterations}) "
            "without completing the task. The task may be too complex or stuck in a loop."
        )

    async def _call_llm(self) -> Any:
        """
        Make a call to the LLM with current conversation history and tools.

        Returns:
            The LLM ChatCompletion response object

        Note:
            Return type is Any due to OpenAI SDK's complex type unions.
            The actual return is always ChatCompletion when stream=False.
        """
        assert self._llm_client is not None

        try:
            response = await self._llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=self.messages,  # type: ignore[arg-type]
                tools=self._tools if self._tools else None,
                tool_choice="auto" if self._tools else None,
                temperature=self.config.temperature,
            )
            return response

        except Exception as e:
            raise AgentExecutionError(f"LLM call failed: {e}") from e

    async def _handle_tool_calls(
        self,
        assistant_message: ChatCompletionMessage,
    ) -> None:
        """
        Process tool calls from the LLM response.

        This method:
        1. Adds the assistant's tool call request to history
        2. Executes each tool via MCP
        3. Adds tool results to history

        Args:
            assistant_message: The assistant message containing tool calls
        """
        assert self._mcp_client is not None
        assert assistant_message.tool_calls is not None

        # Add assistant message with tool calls to history
        # We need to serialize tool_calls for the message history
        # Note: We filter to only function-type tool calls (not custom)
        tool_calls_serialized = []
        for tc in assistant_message.tool_calls:
            # Only process function-type tool calls
            if hasattr(tc, "function") and tc.function is not None:
                tool_calls_serialized.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        self.messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": tool_calls_serialized,
            }
        )

        # Process each tool call
        for tool_call in assistant_message.tool_calls:
            # Only execute function-type tool calls
            if hasattr(tool_call, "function") and tool_call.function is not None:
                await self._execute_tool_call(tool_call)

    async def _execute_tool_call(
        self,
        tool_call: ChatCompletionMessageToolCall,
    ) -> None:
        """
        Execute a single tool call and add result to history.

        Args:
            tool_call: The tool call to execute
        """
        assert self._mcp_client is not None

        tool_name = tool_call.function.name
        tool_call_id = tool_call.id

        # Parse arguments
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            arguments = {}

        print(f"🛠️  Agent invokes tool: {tool_name}")
        print(f"   Args: {json.dumps(arguments, indent=2)}")

        # Execute the tool
        try:
            result = await self._mcp_client.execute_tool(tool_name, arguments)
            print(f"   ✅ Result: {result[:200]}{'...' if len(result) > 200 else ''}")

        except MCPToolExecutionError as e:
            result = f"Tool execution failed: {e}"
            print(f"   ❌ Error: {result}")

        except Exception as e:
            result = f"Unexpected error: {e}"
            print(f"   ❌ Error: {result}")

        # Add tool result to history
        # Critical: Use the correct tool_call_id for proper LLM correlation
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def reset_conversation(self) -> None:
        """
        Reset conversation history, keeping only the system prompt.

        Use this to start a new conversation without reconnecting.
        """
        self.messages = [{"role": "system", "content": self.config.system_prompt}]
        print("🔄 Conversation reset")

    def get_conversation_history(self) -> list[ChatCompletionMessageParam]:
        """
        Get the current conversation history.

        Returns:
            Copy of the messages list for inspection or serialization.
        """
        return list(self.messages)


# =============================================================================
# CLI Entry Point
# =============================================================================


async def run_agent(
    prompt: str | None = None,
    config: AgentConfig | None = None,
) -> str:
    """
    Run the agent with a given prompt.

    This is a convenience function for running the agent programmatically.

    Args:
        prompt: User prompt (uses default test prompt if not provided)
        config: Optional configuration (loads from env if not provided)

    Returns:
        The agent's response
    """
    # Default test prompt
    if prompt is None:
        prompt = (
            "Check the system status, and if online, "
            "run a select query on the 'users' table."
        )

    # Load config if not provided
    if config is None:
        config = AgentConfig.from_env()

    # Run with proper cleanup
    agent = MCPAgent(config)
    try:
        await agent.connect()
        response = await agent.run(prompt)
        return response
    finally:
        await agent.close()


async def main() -> int:
    """
    CLI entry point for the agent.

    Usage:
        uv run python -m client.agent "Your prompt here"
        uv run python -m client.agent  # Uses default test prompt

    Returns:
        Exit code: 0 for success, 1 for error.
    """
    # Get prompt from command line args or use default
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = None
        print("ℹ️  No prompt provided, using default test prompt")

    try:
        await run_agent(prompt)
        return 0

    except AgentConfigError as e:
        print(f"❌ Configuration error: {e}")
        return 1

    except MCPConnectionError as e:
        print(f"❌ MCP connection error: {e}")
        return 1

    except MCPAuthenticationError as e:
        print(f"❌ MCP authentication error: {e}")
        return 1

    except AgentExecutionError as e:
        print(f"❌ Agent execution error: {e}")
        return 1

    except KeyboardInterrupt:
        print("\n👋 Agent interrupted by user")
        return 0

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
