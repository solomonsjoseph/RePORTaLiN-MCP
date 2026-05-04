"""
ReAct RAG Agent for RePORTaLiN Clinical Data System.

This module implements a **pluggable** ReAct (Reasoning + Acting) agent with RAG
(Retrieval Augmented Generation) capabilities that integrates with MCP servers.

Based on LangChain/LangGraph MCP adapter patterns, this agent:
1. Connects to MCP servers via SSE/HTTP transport
2. Converts MCP tools to LangChain-compatible format
3. Executes ReAct loop: Thought → Action → Observation → Repeat
4. Supports multiple LLM providers (OpenAI, Anthropic, Ollama, etc.)

Key Features:
- **Pluggable MCP Integration**: Connect to any MCP server via SSE
- **Multi-LLM Support**: OpenAI, Anthropic Claude, Ollama, vLLM, LM Studio
- **RAG-based retrieval**: From data dictionary and metadata
- **Adaptive routing**: Decides between retrieval, query, or direct response
- **K-anonymity protection**: All data access is privacy-protected
- **NO raw dataset access**: Only de-identified data

Architecture (LangGraph-style):
    ┌─────────────────────────────────────────────────────────────────┐
    │                         User Query                               │
    └─────────────────────────────────┬───────────────────────────────┘
                                      │
    ┌─────────────────────────────────▼───────────────────────────────┐
    │                     ReAct RAG Agent                              │
    │                                                                  │
    │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
    │  │   LLM Node   │───▶│ Tools Router │───▶│  Tool Node   │       │
    │  │ (call_model) │    │(tools_cond)  │    │ (MCP Tools)  │       │
    │  └──────────────┘    └──────────────┘    └──────────────┘       │
    │         ▲                                       │               │
    │         └───────────────────────────────────────┘               │
    │                      (loop back)                                │
    └─────────────────────────────────────────────────────────────────┘
                                      │
    ┌─────────────────────────────────▼───────────────────────────────┐
    │                      MCP Server (SSE)                           │
    │  - explore_study_metadata                                       │
    │  - build_technical_request                                      │
    │  - (+ custom RAG tools)                                         │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    # Quick start with default MCP server
    >>> from reportalin.client.react_rag_agent import ReActRAGAgent
    >>> agent = await ReActRAGAgent.create()
    >>> response = await agent.run("What TB treatment variables exist?")
    >>> await agent.close()

    # With custom MCP server configuration
    >>> config = ReActConfig.from_env()
    >>> agent = await ReActRAGAgent.create(config)
    >>> async with agent:
    ...     result = await agent.run("List available datasets")

    # CLI usage
    $ uv run python -m client.react_rag_agent "Your query here"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypedDict, runtime_checkable

from dotenv import load_dotenv

__all__ = [
    "AgentState",
    "LLMProvider",
    "MCPToolAdapter",
    "QueryType",
    "ReActConfig",
    "ReActRAGAgent",
    "ToolResult",
    "run_react_agent",
]


# =============================================================================
# Constants
# =============================================================================

# Security: Forbidden paths (raw PHI)
FORBIDDEN_PATHS = ["data/dataset", "data\\dataset"]

# Safe paths for RAG retrieval
SAFE_PATHS = [
    "results/data_dictionary_mappings",
    "results/metadata_summary.json",
    "results/variable_map.json",
]


# =============================================================================
# Enums and Type Definitions
# =============================================================================


class QueryType(str, Enum):
    """Classification of query types for adaptive routing."""

    DICTIONARY_SEARCH = "dictionary_search"
    METADATA_EXPLORE = "metadata_explore"
    AGGREGATE_QUERY = "aggregate_query"
    SCHEMA_DESCRIBE = "schema_describe"
    MCP_TOOL_CALL = "mcp_tool_call"  # Use MCP server tools
    DIRECT_RESPONSE = "direct_response"


class ToolResult(TypedDict):
    """Result from tool execution."""

    success: bool
    tool_name: str
    result: str
    relevance_score: float


class MCPTool(TypedDict):
    """MCP tool definition (OpenAI-compatible format)."""

    type: str
    function: dict[str, Any]


@dataclass
class AgentState:
    """Current state of the ReAct agent (LangGraph MessagesState pattern)."""

    query: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    observations: list[ToolResult] = field(default_factory=list)
    retrieved_context: list[dict[str, Any]] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 5
    should_continue: bool = True
    final_answer: str | None = None

    def add_thought(self, thought: str) -> None:
        self.thoughts.append(f"[Iteration {self.iteration}] {thought}")
        self.messages.append({"role": "assistant", "content": f"Thought: {thought}"})

    def add_action(self, action: str, tool_call: dict | None = None) -> None:
        self.actions.append(f"[Iteration {self.iteration}] {action}")
        if tool_call:
            self.messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                }
            )

    def add_observation(self, result: ToolResult) -> None:
        self.observations.append(result)
        self.messages.append(
            {
                "role": "tool",
                "content": result["result"],
                "tool_call_id": f"call_{len(self.observations)}",
            }
        )
        if result["success"]:
            self.retrieved_context.append(
                {
                    "source": result["tool_name"],
                    "content": result["result"],
                    "relevance": result["relevance_score"],
                }
            )


# =============================================================================
# LLM Provider Protocol (Pluggable Interface)
# =============================================================================


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for pluggable LLM providers."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[MCPTool] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Send chat completion request."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...


class OpenAIProvider:
    """OpenAI-compatible LLM provider (works with OpenAI, Ollama, vLLM, etc.)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ):
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(**kwargs)
        self.model = model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[MCPTool] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        return {
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (msg.tool_calls or [])
            ]
            if msg.tool_calls
            else None,
        }

    async def close(self) -> None:
        await self.client.close()


class AnthropicProvider:
    """Anthropic Claude LLM provider."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[MCPTool] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        # Convert OpenAI format to Anthropic format
        system_msg = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": msg["content"],
                            }
                        ],
                    }
                )
            else:
                anthropic_messages.append(msg)

        # Convert tools to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 1024,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self.client.messages.create(**kwargs)

        # Convert response back to OpenAI format
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )

        return {
            "content": content if content else None,
            "tool_calls": tool_calls if tool_calls else None,
        }

    async def close(self) -> None:
        pass  # Anthropic client doesn't need explicit cleanup


# =============================================================================
# MCP Tool Adapter (Pluggable MCP Integration)
# =============================================================================


class MCPToolAdapter:
    """
    Adapter for connecting to MCP servers and using their tools.

    Follows the langchain-mcp-adapters pattern for tool conversion.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8000/mcp/sse",
        auth_token: str = "",
    ):
        self.server_url = server_url
        self.auth_token = auth_token
        self._mcp_client: Any = None
        self._tools: list[MCPTool] = []
        self._connected = False

    async def connect(self) -> None:
        """Connect to MCP server and load tools."""
        if self._connected:
            return

        # Import here to avoid circular deps and allow optional dependency
        try:
            from reportalin.client.mcp_client import UniversalMCPClient
        except ImportError:
            print("⚠️ MCP client not available, using local tools only")
            self._connected = True
            return

        self._mcp_client = UniversalMCPClient(
            server_url=self.server_url,
            auth_token=self.auth_token,
        )

        try:
            await self._mcp_client.connect()
            self._tools = await self._mcp_client.get_tools_for_openai()
            self._connected = True
            print(f"🔌 Connected to MCP server: {self.server_url}")
            print(f"   Tools loaded: {[t['function']['name'] for t in self._tools]}")
        except Exception as e:
            print(f"⚠️ MCP connection failed: {e}")
            self._connected = True  # Continue with local tools

    async def close(self) -> None:
        """Disconnect from MCP server."""
        if self._mcp_client:
            await self._mcp_client.close()
        self._connected = False

    def get_tools(self) -> list[MCPTool]:
        """Get available tools in OpenAI format."""
        return self._tools

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool via MCP server."""
        if not self._mcp_client:
            return json.dumps({"error": "MCP client not connected"})

        try:
            result = await self._mcp_client.execute_tool(name, arguments)
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})


# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class ReActConfig:
    """Configuration for the ReAct RAG Agent."""

    # LLM settings
    llm_provider: str = "openai"  # openai, anthropic, ollama
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"

    # MCP settings
    mcp_server_url: str = "http://localhost:8000/mcp/sse"
    mcp_auth_token: str = ""
    use_mcp_tools: bool = True  # Enable/disable MCP tool integration

    # Agent settings
    max_iterations: int = 5
    temperature: float = 0.3
    relevance_threshold: float = 0.6

    # Paths
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @classmethod
    def from_env(cls) -> ReActConfig:
        """Load configuration from environment variables."""
        load_dotenv()

        # Determine LLM provider
        provider = os.getenv("LLM_PROVIDER", "openai").lower()

        # Get API key based on provider
        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            model = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
        else:
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        base_url = os.getenv("LLM_BASE_URL")

        # Validate
        if not api_key and not base_url:
            raise ValueError(
                "LLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY required. "
                "Set LLM_BASE_URL for local LLM support."
            )

        return cls(
            llm_provider=provider,
            llm_api_key=api_key,
            llm_base_url=base_url if base_url else None,
            llm_model=model,
            mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/sse"),
            mcp_auth_token=os.getenv("MCP_AUTH_TOKEN", ""),
            use_mcp_tools=os.getenv("USE_MCP_TOOLS", "true").lower() == "true",
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "5")),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.3")),
        )


# =============================================================================
# ReAct RAG Agent Prompts
# =============================================================================

REACT_SYSTEM_PROMPT = """You are a clinical research assistant for the RePORT India (Indo-VAP) tuberculosis study.
You help researchers design statistical analyses and plan data requests.

## Your Role
You are a CONSULTANT who helps researchers think through their analysis approach.
- First, understand what they want to analyze
- Provide methodological guidance and analysis plans
- Only provide specific variable names when explicitly requested

## Query Types You Handle

### 1. Statistical Analysis Requests
When a user asks about analyzing relationships (e.g., "Which factors influence TB recurrence?"):
- Discuss the analysis approach (univariate, multivariate, interactions)
- Recommend statistical methods (logistic regression, Cox regression, etc.)
- Suggest visualization strategies
- DO NOT list specific variable names unless asked

### 2. Variable Requests (Only when explicitly asked)
When a user explicitly asks "What variables...", "Show me the fields...", "List the variables...":
- THEN use the variable search tools
- Provide specific variable names with descriptions

### 3. Visualization Planning
- Recommend plot types based on variable types
- Violin/box plots for categorical predictors
- Scatter plots for continuous predictors
- Stratification approaches

### 4. Cohort Definition
- Cohort A: TB patients (index cases)
- Cohort B: Household contacts (HHC)

## IMPORTANT BEHAVIOR RULES

1. **DO NOT immediately search for variables** when user asks an analysis question
2. **First provide the analysis plan** in plain language
3. **Ask if they want specific variable names** before revealing them
4. **Only use variable search tools** when user explicitly requests variable details

## Response Format for Analysis Requests

When responding to analysis questions like "Which factors influence X?":

```
## Analysis Approach

### Outcome
[Describe what will be measured - don't list variable names yet]

### Predictors to Consider
[List conceptual categories - NOT specific variable names]
- Comorbidities (diabetes, malnutrition status)
- Lifestyle factors (smoking, alcohol use)
- Demographics (age, sex)

### Recommended Statistical Approach
1. [Step-by-step methodology]

### Visualization Strategy
- [Plot types for each relationship]

Would you like me to provide the specific variable names from the data dictionary?
```

## Cohort Definitions
- **Cohort A**: TB index cases (patients diagnosed with TB)
- **Cohort B**: Household contacts (HHC) - people living with TB patients"""


QUERY_CLASSIFIER_PROMPT = """Classify this query into one of these categories:

- DICTIONARY_SEARCH: Questions about variables, fields, what data exists
- METADATA_EXPLORE: Questions about study overview, participant counts, sites  
- AGGREGATE_QUERY: Questions needing statistical summaries or counts
- SCHEMA_DESCRIBE: Questions about specific dataset structure
- MCP_TOOL_CALL: Complex queries requiring MCP server tools
- DIRECT_RESPONSE: Simple questions answerable without data access

Query: {query}

Respond with ONLY the category name."""


ANSWER_GENERATOR_PROMPT = """Generate a comprehensive answer based on the retrieved context.

User Question: {question}

Retrieved Context:
{context}

Reasoning Chain:
{reasoning}

Instructions:
1. Synthesize information from all relevant sources
2. Be specific and cite data sources
3. Note any limitations (suppressed results, missing data)
4. If context is insufficient, say so honestly

Provide your final answer:"""


# =============================================================================
# ReAct RAG Agent Implementation (LangGraph-style)
# =============================================================================


class ReActRAGAgent:
    """
    Pluggable ReAct RAG Agent for clinical data queries.

    Implements LangGraph-style ReAct pattern with MCP tool integration:
    - call_model: LLM reasoning node
    - tools_condition: Route based on tool calls
    - tool_node: Execute MCP or local tools
    """

    def __init__(self, config: ReActConfig) -> None:
        self.config = config
        self._llm: LLMProvider | None = None
        self._mcp_adapter: MCPToolAdapter | None = None
        self._connected = False

        # Data paths for local RAG tools
        self.project_root = config.project_root
        self.dictionary_dir = self.project_root / "results" / "data_dictionary_mappings"
        self.metadata_file = self.project_root / "results" / "metadata_summary.json"

    @classmethod
    async def create(cls, config: ReActConfig | None = None) -> ReActRAGAgent:
        """Factory method to create and initialize the agent."""
        if config is None:
            config = ReActConfig.from_env()

        agent = cls(config)
        await agent.connect()
        return agent

    async def connect(self) -> None:
        """Initialize LLM provider and MCP adapter."""
        if self._connected:
            return

        # Initialize LLM provider based on config
        if self.config.llm_provider == "anthropic":
            self._llm = AnthropicProvider(
                api_key=self.config.llm_api_key,
                model=self.config.llm_model,
            )
            print(f"🧠 LLM: Anthropic ({self.config.llm_model})")
        else:
            self._llm = OpenAIProvider(
                api_key=self.config.llm_api_key or "ollama",
                model=self.config.llm_model,
                base_url=self.config.llm_base_url,
            )
            provider_name = "Ollama" if self.config.llm_base_url else "OpenAI"
            print(f"🧠 LLM: {provider_name} ({self.config.llm_model})")

        # Initialize MCP adapter if enabled
        if self.config.use_mcp_tools:
            self._mcp_adapter = MCPToolAdapter(
                server_url=self.config.mcp_server_url,
                auth_token=self.config.mcp_auth_token,
            )
            await self._mcp_adapter.connect()

        self._connected = True
        print(
            f"✅ ReAct RAG Agent ready (max iterations: {self.config.max_iterations})"
        )

    async def close(self) -> None:
        """Clean up resources."""
        if self._llm:
            await self._llm.close()
        if self._mcp_adapter:
            await self._mcp_adapter.close()
        self._connected = False
        print("👋 Agent closed")

    async def __aenter__(self) -> ReActRAGAgent:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _get_all_tools(self) -> list[MCPTool]:
        """Get all available tools (MCP + local RAG tools)."""
        tools: list[MCPTool] = []

        # Add MCP server tools
        if self._mcp_adapter:
            tools.extend(self._mcp_adapter.get_tools())

        # Add local RAG tools - ONLY use when user explicitly requests variable details
        local_tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_variables",
                    "description": "Search for specific variable names in the data dictionary. ONLY use when user explicitly asks for variable names, field names, or says 'show me the variables'. Do NOT use for general analysis questions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Variable name or keyword to search",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_outcome_variables",
                    "description": "List specific outcome variable names. ONLY use when user explicitly asks 'what variables', 'show me the fields', or 'list the outcome variables'. Do NOT use for general analysis planning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "outcome_type": {
                                "type": "string",
                                "description": "Type of outcome: 'recurrence', 'incident_tb', 'treatment_outcome', 'mortality'",
                            },
                            "cohort": {
                                "type": "string",
                                "description": "Cohort: 'A' (TB patients) or 'B' (household contacts)",
                            },
                        },
                        "required": ["outcome_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_predictor_variables",
                    "description": "List specific predictor variable names by category. ONLY use when user explicitly asks for variable names or field lists. Do NOT use for general analysis planning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Category: 'comorbidities', 'nutrition', 'lifestyle', 'demographics'",
                            },
                            "concept": {
                                "type": "string",
                                "description": "Specific concept to search",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "recommend_visualization",
                    "description": "Get visualization recommendations for analysis. Can be used during analysis planning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "outcome": {
                                "type": "string",
                                "description": "Outcome concept (e.g., 'recurrence', 'incident TB')",
                            },
                            "predictors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of predictor concepts (e.g., ['diabetes', 'smoking'])",
                            },
                            "stratify_by": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Variables to stratify by (e.g., ['age', 'sex'])",
                            },
                        },
                        "required": ["outcome", "predictors"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_datasets",
                    "description": "List available study datasets and forms. Use when user asks about available data or datasets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Optional filter by category",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "describe_dataset",
                    "description": "Get detailed schema for a specific dataset. ONLY use when user explicitly asks about a specific dataset's structure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dataset_name": {
                                "type": "string",
                                "description": "Name of the dataset to describe",
                            },
                        },
                        "required": ["dataset_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_study_overview",
                    "description": "Get high-level study information: cohorts, design, visit schedule. Use for general study structure questions.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
        ]

        tools.extend(local_tools)
        return tools

    # =========================================================================
    # Core ReAct Loop (LangGraph-style)
    # =========================================================================

    async def run(self, query: str) -> str:
        """
        Execute the ReAct loop for a user query.

        LangGraph pattern:
        START → call_model → tools_condition → [tools | END]
                    ▲                              │
                    └──────────────────────────────┘
        """
        if not self._connected:
            raise RuntimeError("Agent not connected. Call connect() first.")

        print(f"\n{'=' * 60}")
        print(f"📝 Query: {query}")
        print(f"{'=' * 60}\n")

        # Initialize state (MessagesState pattern)
        state = AgentState(
            query=query,
            max_iterations=self.config.max_iterations,
            messages=[
                {"role": "system", "content": REACT_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        )

        tools = self._get_all_tools()

        # ReAct Loop
        while state.should_continue and state.iteration < state.max_iterations:
            state.iteration += 1
            print(f"\n🔄 Iteration {state.iteration}/{state.max_iterations}")

            # Step 1: call_model node
            response = await self._call_model(state, tools)

            # Step 2: tools_condition (check for tool calls)
            if response.get("tool_calls"):
                # Execute tools
                for tool_call in response["tool_calls"]:
                    result = await self._execute_tool(tool_call)
                    state.add_action(
                        f"Called {tool_call['function']['name']}", tool_call
                    )
                    state.add_observation(result)
                    print(f"   🛠️  Tool: {result['tool_name']}")
                    print(f"   📊 Result: {result['result'][:200]}...")
            else:
                # No tool calls - we have the final response
                state.should_continue = False
                if response.get("content"):
                    state.final_answer = response["content"]

        # Generate final answer if not already set
        if not state.final_answer:
            state.final_answer = await self._generate_answer(state)

        print(f"\n{'=' * 60}")
        print(f"🤖 Answer: {state.final_answer}")
        print(f"{'=' * 60}\n")

        return state.final_answer

    async def _call_model(
        self,
        state: AgentState,
        tools: list[MCPTool],
    ) -> dict[str, Any]:
        """LLM reasoning node - decide what to do next."""
        assert self._llm is not None

        return await self._llm.chat(
            messages=state.messages,
            tools=tools,
            temperature=self.config.temperature,
        )

    async def _execute_tool(self, tool_call: dict[str, Any]) -> ToolResult:
        """Execute a tool (MCP or local)."""
        name = tool_call["function"]["name"]

        try:
            args = json.loads(tool_call["function"]["arguments"])
        except json.JSONDecodeError:
            args = {"query": tool_call["function"]["arguments"]}

        # Check if it's an MCP tool
        if self._mcp_adapter:
            mcp_tool_names = [
                t["function"]["name"] for t in self._mcp_adapter.get_tools()
            ]
            if name in mcp_tool_names:
                result = await self._mcp_adapter.execute_tool(name, args)
                return ToolResult(
                    success=True,
                    tool_name=name,
                    result=result,
                    relevance_score=0.8,
                )

        # Execute local RAG tool
        local_tools = {
            "search_variables": self._search_variables,
            "find_outcome_variables": self._find_outcome_variables,
            "find_predictor_variables": self._find_predictor_variables,
            "recommend_visualization": self._recommend_visualization,
            "list_datasets": self._list_datasets,
            "describe_dataset": self._describe_dataset,
            "get_study_overview": self._get_study_overview,
        }

        if name in local_tools:
            # Handle different argument patterns
            if name == "describe_dataset":
                return await local_tools[name](args.get("dataset_name", ""))
            elif name == "list_datasets":
                return await local_tools[name](args.get("category", ""))
            elif name == "get_study_overview":
                return await local_tools[name]()
            elif name == "find_outcome_variables":
                return await local_tools[name](
                    args.get("outcome_type", ""), args.get("cohort", "A")
                )
            elif name == "find_predictor_variables":
                return await local_tools[name](
                    args.get("category", ""), args.get("concept", "")
                )
            elif name == "recommend_visualization":
                return await local_tools[name](
                    args.get("outcome", ""),
                    args.get("predictors", []),
                    args.get("stratify_by", []),
                )
            else:
                return await local_tools[name](args.get("query", ""))

        return ToolResult(
            success=False,
            tool_name=name,
            result=f"Unknown tool: {name}",
            relevance_score=0.0,
        )

    async def _generate_answer(self, state: AgentState) -> str:
        """Generate final answer from accumulated context."""
        assert self._llm is not None

        context_parts = []
        for ctx in state.retrieved_context:
            context_parts.append(f"[Source: {ctx['source']}]\n{ctx['content']}")

        context_str = (
            "\n\n---\n\n".join(context_parts) if context_parts else "No data retrieved."
        )

        reasoning_parts = []
        for thought, action in zip(state.thoughts, state.actions):
            reasoning_parts.append(f"Thought: {thought}\nAction: {action}")
        reasoning_str = (
            "\n".join(reasoning_parts) if reasoning_parts else "Direct query."
        )

        prompt = ANSWER_GENERATOR_PROMPT.format(
            question=state.query,
            context=context_str,
            reasoning=reasoning_str,
        )

        response = await self._llm.chat(
            messages=[
                {"role": "system", "content": REACT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature,
        )

        return response.get("content") or "Unable to generate answer."

    # =========================================================================
    # Local RAG Tool Implementations (Study & Variable Queries)
    # =========================================================================

    async def _search_variables(self, query: str) -> ToolResult:
        """Search data dictionary for variable definitions and field metadata."""
        results = []

        if not self.dictionary_dir.exists():
            return ToolResult(
                success=False,
                tool_name="search_variables",
                result="Data dictionary not found. Please run the data extraction pipeline first.",
                relevance_score=0.0,
            )

        # Tokenize search query
        search_terms = [term.lower() for term in query.split() if len(term) > 2]

        # Search all JSONL dictionary files
        for jsonl_file in self.dictionary_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            # Search in variable name, description, and label
                            searchable = json.dumps(record).lower()
                            if any(term in searchable for term in search_terms):
                                # Add source info
                                record["_source_file"] = jsonl_file.stem
                                record["_domain"] = self._infer_domain(jsonl_file.stem)
                                results.append(record)
                                if len(results) >= 25:
                                    break
            except Exception:
                pass

        if results:
            # Format results for readability
            formatted = []
            for r in results[:15]:
                var_info = {
                    "variable": r.get("variable_name")
                    or r.get("name")
                    or r.get("field"),
                    "label": r.get("label") or r.get("description", ""),
                    "type": r.get("data_type") or r.get("type", ""),
                    "source": r.get("_source_file", ""),
                    "domain": r.get("_domain", ""),
                }
                formatted.append(var_info)

            return ToolResult(
                success=True,
                tool_name="search_variables",
                result=json.dumps(
                    {
                        "found": len(results),
                        "showing": len(formatted),
                        "variables": formatted,
                    },
                    indent=2,
                    default=str,
                ),
                relevance_score=0.85,
            )

        return ToolResult(
            success=True,
            tool_name="search_variables",
            result=f"No variables found matching '{query}'. Try broader terms or check spelling.",
            relevance_score=0.2,
        )

    def _infer_domain(self, filename: str) -> str:
        """Infer CDISC domain from filename."""
        name_lower = filename.lower()
        domain_map = {
            "demograph": "DM (Demographics)",
            "lab": "LB (Laboratory)",
            "vital": "VS (Vital Signs)",
            "adverse": "AE (Adverse Events)",
            "medication": "CM (Medications)",
            "medical_history": "MH (Medical History)",
            "baseline": "Baseline",
            "follow": "Follow-up",
            "screening": "Screening",
            "enrollment": "Enrollment",
        }
        for key, domain in domain_map.items():
            if key in name_lower:
                return domain
        return "Study Data"

    async def _list_datasets(self, category: str = "") -> ToolResult:
        """List available study datasets and forms."""
        datasets = []

        # Check dictionary directory for form metadata
        if self.dictionary_dir.exists():
            for jsonl_file in sorted(self.dictionary_dir.glob("*.jsonl")):
                try:
                    # Count variables in each file
                    var_count = sum(1 for line in open(jsonl_file) if line.strip())
                    dataset_info = {
                        "name": jsonl_file.stem,
                        "domain": self._infer_domain(jsonl_file.stem),
                        "variable_count": var_count,
                        "type": "data_dictionary",
                    }

                    # Apply category filter
                    if category:
                        if category.lower() not in jsonl_file.stem.lower():
                            continue

                    datasets.append(dataset_info)
                except Exception:
                    pass

        result = {
            "study": "RePORT India (Indo-VAP)",
            "description": "Tuberculosis clinical study with longitudinal follow-up",
            "total_datasets": len(datasets),
            "filter_applied": category if category else None,
            "datasets": datasets,
        }

        return ToolResult(
            success=True,
            tool_name="list_datasets",
            result=json.dumps(result, indent=2, default=str),
            relevance_score=0.8,
        )

    async def _describe_dataset(self, dataset_name: str) -> ToolResult:
        """Get detailed schema for a specific dataset or form."""
        if not dataset_name:
            return ToolResult(
                success=False,
                tool_name="describe_dataset",
                result="Please specify a dataset name. Use list_datasets to see available options.",
                relevance_score=0.0,
            )

        # Search for matching dictionary file
        matching_files = []
        if self.dictionary_dir.exists():
            for jsonl_file in self.dictionary_dir.glob("*.jsonl"):
                if dataset_name.lower() in jsonl_file.stem.lower():
                    matching_files.append(jsonl_file)

        if not matching_files:
            return ToolResult(
                success=False,
                tool_name="describe_dataset",
                result=f"No dataset found matching '{dataset_name}'. Use list_datasets to see available options.",
                relevance_score=0.1,
            )

        # Read schema from first matching file
        target_file = matching_files[0]
        variables = []

        try:
            with open(target_file, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if line.strip():
                        record = json.loads(line)
                        var_info = {
                            "name": record.get("variable_name")
                            or record.get("name")
                            or record.get("field", f"field_{i}"),
                            "label": record.get("label")
                            or record.get("description", ""),
                            "type": record.get("data_type") or record.get("type", ""),
                            "values": record.get("allowed_values")
                            or record.get("codelist", ""),
                        }
                        variables.append(var_info)
                    if len(variables) >= 50:
                        break
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name="describe_dataset",
                result=f"Error reading dataset: {e}",
                relevance_score=0.0,
            )

        result = {
            "dataset": target_file.stem,
            "domain": self._infer_domain(target_file.stem),
            "source_file": str(target_file.name),
            "variable_count": len(variables),
            "variables": variables,
        }

        return ToolResult(
            success=True,
            tool_name="describe_dataset",
            result=json.dumps(result, indent=2, default=str),
            relevance_score=0.9,
        )

    async def _get_study_overview(self) -> ToolResult:
        """Get high-level study information."""
        # Load metadata if available
        metadata = {}
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file) as f:
                    metadata = json.load(f)
            except Exception:
                pass

        # Count available resources
        dict_files = (
            list(self.dictionary_dir.glob("*.jsonl"))
            if self.dictionary_dir.exists()
            else []
        )

        overview = {
            "study_name": "RePORT India (Indo-VAP)",
            "full_name": "Regional Prospective Observational Research on Tuberculosis - India",
            "study_type": "Observational cohort study",
            "disease_focus": "Tuberculosis (TB)",
            "data_domains": [
                {
                    "code": "DM",
                    "name": "Demographics",
                    "description": "Patient demographics and enrollment",
                },
                {
                    "code": "LB",
                    "name": "Laboratory",
                    "description": "Lab tests including TB diagnostics",
                },
                {
                    "code": "VS",
                    "name": "Vital Signs",
                    "description": "Physical measurements",
                },
                {
                    "code": "MH",
                    "name": "Medical History",
                    "description": "Prior conditions and TB history",
                },
                {
                    "code": "AE",
                    "name": "Adverse Events",
                    "description": "Treatment-related events",
                },
            ],
            "visit_schedule": [
                "Screening",
                "Baseline/Enrollment",
                "Month 2",
                "Month 6",
                "Month 12",
                "Month 18",
                "Month 24",
                "End of Study",
            ],
            "available_resources": {
                "data_dictionary_files": len(dict_files),
            },
            "metadata": metadata,
        }

        return ToolResult(
            success=True,
            tool_name="get_study_overview",
            result=json.dumps(overview, indent=2, default=str),
            relevance_score=0.9,
        )

    async def _find_outcome_variables(
        self, outcome_type: str, cohort: str = "A"
    ) -> ToolResult:
        """Find outcome variables for regression analysis based on cohort and outcome type."""
        # Define outcome variable mappings
        outcome_mappings = {
            "recurrence": {
                "A": {
                    "variables": ["TBRELAPSE", "TBRECUR", "TBOUTCOME", "RETREATMENT"],
                    "description": "TB recurrence/relapse in index cases",
                    "type": "binary",
                    "timeframe": "Post-treatment follow-up",
                },
                "B": {
                    "variables": ["TBINCIDENT", "TBDIAG_NEW", "ACTIVETB"],
                    "description": "Not typically applicable - use incident_tb for contacts",
                    "type": "binary",
                },
            },
            "incident_tb": {
                "A": {
                    "variables": ["TBRELAPSE", "RETREATMENT"],
                    "description": "For index cases, this is TB recurrence",
                    "type": "binary",
                },
                "B": {
                    "variables": [
                        "TBINCIDENT",
                        "TBDIAG",
                        "TST_CONVERT",
                        "IGRA_CONVERT",
                        "ACTIVETB",
                    ],
                    "description": "Incident TB or TB infection in household contacts",
                    "type": "binary/time-to-event",
                    "timeframe": "During follow-up period",
                },
            },
            "treatment_outcome": {
                "A": {
                    "variables": [
                        "TXOUTCOME",
                        "TXSTATUS",
                        "CURED",
                        "COMPLETED",
                        "FAILED",
                        "DEFAULTED",
                    ],
                    "description": "End-of-treatment outcomes for TB patients",
                    "type": "categorical",
                    "categories": ["Cured", "Completed", "Failed", "Defaulted", "Died"],
                },
                "B": {
                    "variables": [],
                    "description": "Not applicable - contacts don't receive TB treatment unless diagnosed",
                    "type": "N/A",
                },
            },
            "mortality": {
                "A": {
                    "variables": ["DEATH", "DTHDAT", "DTHCAUSE", "VITAL_STATUS"],
                    "description": "All-cause or TB-related mortality",
                    "type": "binary/time-to-event",
                },
                "B": {
                    "variables": ["DEATH", "VITAL_STATUS"],
                    "description": "Mortality in household contacts",
                    "type": "binary/time-to-event",
                },
            },
        }

        outcome_key = outcome_type.lower().replace(" ", "_").replace("-", "_")
        cohort_key = cohort.upper() if cohort else "A"

        if outcome_key not in outcome_mappings:
            return ToolResult(
                success=True,
                tool_name="find_outcome_variables",
                result=json.dumps(
                    {
                        "error": f"Unknown outcome type: {outcome_type}",
                        "available_types": list(outcome_mappings.keys()),
                    },
                    indent=2,
                ),
                relevance_score=0.3,
            )

        outcome_info = outcome_mappings[outcome_key].get(
            cohort_key, outcome_mappings[outcome_key]["A"]
        )

        # Search dictionary for these variables
        found_vars = []
        if self.dictionary_dir.exists():
            for var_name in outcome_info["variables"]:
                result = await self._search_variables(var_name)
                if result["success"] and "No variables found" not in result["result"]:
                    found_vars.append(var_name)

        result = {
            "cohort": f"Cohort {cohort_key}"
            + (" (TB index cases)" if cohort_key == "A" else " (Household contacts)"),
            "outcome_type": outcome_type,
            "recommended_variables": outcome_info["variables"],
            "found_in_dictionary": found_vars,
            "variable_type": outcome_info["type"],
            "description": outcome_info["description"],
            "timeframe": outcome_info.get("timeframe", ""),
            "analysis_notes": self._get_outcome_analysis_notes(outcome_key, cohort_key),
        }

        return ToolResult(
            success=True,
            tool_name="find_outcome_variables",
            result=json.dumps(result, indent=2),
            relevance_score=0.9,
        )

    def _get_outcome_analysis_notes(self, outcome_type: str, cohort: str) -> list[str]:
        """Get analysis notes for specific outcome/cohort combinations."""
        notes = []
        if outcome_type == "recurrence" and cohort == "A":
            notes = [
                "Binary outcome: use logistic regression",
                "Consider time-to-recurrence with Cox regression",
                "Define recurrence window (e.g., within 2 years post-treatment)",
            ]
        elif outcome_type == "incident_tb" and cohort == "B":
            notes = [
                "Binary or time-to-event outcome",
                "Consider competing risks (death, loss to follow-up)",
                "TST/IGRA conversion can be intermediate outcome",
            ]
        elif outcome_type == "treatment_outcome":
            notes = [
                "Multinomial outcome or collapse to binary (favorable/unfavorable)",
                "Consider ordinal regression if categories are ordered",
            ]
        return notes

    async def _find_predictor_variables(
        self, category: str = "", concept: str = ""
    ) -> ToolResult:
        """Find predictor/exposure variables for regression models."""
        # Define predictor categories
        predictor_categories = {
            "comorbidities": {
                "variables": [
                    "DIABETES",
                    "DM",
                    "HIV",
                    "HIVSTAT",
                    "MALNUTRITION",
                    "ANEMIA",
                ],
                "search_terms": ["diabetes", "HIV", "comorbid", "chronic"],
                "description": "Chronic conditions and comorbidities",
                "type": "categorical/binary",
            },
            "nutrition": {
                "variables": [
                    "BMI",
                    "WEIGHT",
                    "HEIGHT",
                    "MUAC",
                    "NUTSTAT",
                    "MALNUTRITION",
                ],
                "search_terms": ["BMI", "weight", "nutrition", "malnutrition", "MUAC"],
                "description": "Nutritional status indicators",
                "type": "continuous (BMI) / categorical (malnutrition status)",
            },
            "lifestyle": {
                "variables": ["SMOKING", "SMOKESTAT", "ALCOHOL", "ALCFREQ", "ALCQTY"],
                "search_terms": ["smoking", "alcohol", "tobacco", "drink"],
                "description": "Behavioral and lifestyle factors",
                "type": "categorical (status) / continuous (quantity)",
            },
            "demographics": {
                "variables": ["AGE", "SEX", "GENDER", "SITEID", "COUNTRY", "EDUCATION"],
                "search_terms": ["age", "sex", "gender", "site", "education"],
                "description": "Demographic characteristics",
                "type": "continuous (age) / categorical (sex, site)",
            },
            "socioeconomic": {
                "variables": ["INCOME", "OCCUPATION", "EDUCATION", "HOUSING"],
                "search_terms": ["income", "education", "socioeconomic", "poverty"],
                "description": "Socioeconomic factors",
                "type": "categorical/ordinal",
            },
            "clinical": {
                "variables": [
                    "TBTYPE",
                    "CAVITARY",
                    "SMEAR",
                    "CULTURE",
                    "XRAY",
                    "SEVERITY",
                ],
                "search_terms": ["smear", "culture", "cavity", "severity", "extent"],
                "description": "Clinical TB characteristics",
                "type": "categorical/binary",
            },
        }

        results = {}

        if category:
            cat_key = category.lower()
            if cat_key in predictor_categories:
                cat_info = predictor_categories[cat_key]
                # Search for variables
                found = []
                for term in cat_info["search_terms"][:3]:
                    search_result = await self._search_variables(term)
                    if (
                        search_result["success"]
                        and "No variables found" not in search_result["result"]
                    ):
                        found.append(term)

                results[category] = {
                    "recommended_variables": cat_info["variables"],
                    "search_terms_found": found,
                    "description": cat_info["description"],
                    "variable_type": cat_info["type"],
                }
            else:
                return ToolResult(
                    success=True,
                    tool_name="find_predictor_variables",
                    result=json.dumps(
                        {
                            "error": f"Unknown category: {category}",
                            "available_categories": list(predictor_categories.keys()),
                        },
                        indent=2,
                    ),
                    relevance_score=0.3,
                )
        elif concept:
            # Search by specific concept
            search_result = await self._search_variables(concept)
            results["search_results"] = (
                json.loads(search_result["result"]) if search_result["success"] else {}
            )
            results["concept"] = concept
        else:
            # Return all categories
            for cat_name, cat_info in predictor_categories.items():
                results[cat_name] = {
                    "variables": cat_info["variables"],
                    "description": cat_info["description"],
                    "type": cat_info["type"],
                }

        return ToolResult(
            success=True,
            tool_name="find_predictor_variables",
            result=json.dumps(results, indent=2),
            relevance_score=0.85,
        )

    async def _recommend_visualization(
        self, outcome: str, predictors: list[str], stratify_by: list[str] | None = None
    ) -> ToolResult:
        """Recommend visualizations based on variable types."""
        # Variable type classifications
        continuous_vars = {"age", "bmi", "weight", "height", "muac", "hba1c", "glucose"}
        categorical_vars = {
            "sex",
            "gender",
            "diabetes",
            "dm",
            "smoking",
            "alcohol",
            "hiv",
            "site",
        }
        binary_outcome_keywords = {
            "recurrence",
            "incident",
            "death",
            "relapse",
            "outcome",
        }

        recommendations = []

        for predictor in predictors:
            pred_lower = predictor.lower()

            # Determine predictor type
            is_continuous = any(cv in pred_lower for cv in continuous_vars)
            is_categorical = any(cv in pred_lower for cv in categorical_vars)

            # Determine outcome type
            outcome_lower = outcome.lower()
            is_binary_outcome = any(
                bo in outcome_lower for bo in binary_outcome_keywords
            )

            viz = {
                "predictor": predictor,
                "predictor_type": "continuous" if is_continuous else "categorical",
                "outcome": outcome,
            }

            if is_continuous:
                if is_binary_outcome:
                    viz["recommended_plot"] = "scatter plot with logistic curve"
                    viz["alternatives"] = ["box plot by outcome groups", "ROC curve"]
                else:
                    viz["recommended_plot"] = "scatter plot"
                    viz["alternatives"] = ["density plot by groups"]
            else:
                if is_binary_outcome:
                    viz["recommended_plot"] = "violin plot or box plot"
                    viz["alternatives"] = ["grouped bar chart", "forest plot (for ORs)"]
                else:
                    viz["recommended_plot"] = "grouped bar chart or mosaic plot"

            # Add stratification recommendations
            if stratify_by:
                viz["stratification"] = {
                    "variables": stratify_by,
                    "method": "color/facet by " + ", ".join(stratify_by),
                }
                if is_continuous:
                    viz["stratified_plot"] = (
                        f"scatter plot colored by {'/'.join(stratify_by)}"
                    )
                else:
                    viz["stratified_plot"] = (
                        f"faceted violin plots by {'/'.join(stratify_by)}"
                    )

            recommendations.append(viz)

        result = {
            "outcome_variable": outcome,
            "predictors_analyzed": len(predictors),
            "stratification_variables": stratify_by or [],
            "recommendations": recommendations,
            "general_notes": [
                "Use violin plots for categorical predictors with binary outcomes",
                "Use scatter plots for continuous predictors",
                "Add color/facets for age and sex stratification",
                "Consider interaction plots for effect modification analysis",
            ],
        }

        return ToolResult(
            success=True,
            tool_name="recommend_visualization",
            result=json.dumps(result, indent=2),
            relevance_score=0.9,
        )


# =============================================================================
# CLI Entry Point
# =============================================================================


async def run_react_agent(query: str | None = None) -> str:
    """Run the ReAct RAG agent."""
    if query is None:
        query = "What variables are available for measuring TB treatment outcomes?"

    config = ReActConfig.from_env()

    async with ReActRAGAgent(config) as agent:
        return await agent.run(query)


async def main() -> int:
    """CLI entry point."""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = None
        print("ℹ️  No query provided, using default test query")

    try:
        await run_react_agent(query)
        return 0
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
