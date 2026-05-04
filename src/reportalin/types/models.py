"""
Core type definitions for the RePORTaLiN MCP system.

These types are shared between server and client implementations
to ensure consistency in data structures and API contracts.

Aligned with MCP Protocol 2025-03-26 specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias

__all__ = [
    # JSON Types
    "JsonPrimitive",
    "JsonArray",
    "JsonObject",
    "JsonValue",
    # Enums
    "TransportType",
    "LogLevel",
    "PrivacyMode",
    "EnvironmentType",
    # Dataclasses
    "ToolResult",
    "ServerCapabilities",
    "SecurityContext",
    # Type Aliases
    "ToolName",
    "ResourceUri",
    "PromptId",
    "SessionId",
]

# JSON-compatible types (JSON-RPC 2.0 compliant)
JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonArray: TypeAlias = list["JsonValue"]
JsonObject: TypeAlias = dict[str, "JsonValue"]
JsonValue: TypeAlias = JsonPrimitive | JsonArray | JsonObject


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"  # New in 2025 spec


class LogLevel(str, Enum):
    """Log levels for structured logging."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PrivacyMode(str, Enum):
    """Privacy enforcement modes for clinical data."""

    STRICT = "strict"  # Full k-anonymity enforcement, suppress small cells
    STANDARD = "standard"  # Warn on small cells but return data
    PERMISSIVE = "permissive"  # No privacy restrictions (development only)


class EnvironmentType(str, Enum):
    """Deployment environment types."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class ToolResult:
    """
    Standardized result from MCP tool execution.

    Attributes:
        success: Whether the tool executed successfully
        data: The result data (if successful)
        error: Error message (if failed)
        metadata: Additional context about the execution
    """

    success: bool
    data: JsonValue = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        """Convert to JSON-serializable dictionary.

        Returns:
            A dictionary containing success status, data, error, and metadata
            fields. Only non-None/non-empty fields are included.
        """
        result: JsonObject = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass(frozen=True, slots=True)
class ServerCapabilities:
    """
    MCP Server capabilities declaration.

    Used during capability negotiation to inform clients
    what features this server supports.

    Aligned with MCP 2025-03-26 specification.
    """

    tools: bool = True
    resources: bool = True
    prompts: bool = False
    logging: bool = True
    # New capabilities in 2025 spec
    sampling: bool = False  # Server can request LLM completions
    roots: bool = False  # Server can access file system roots
    experimental: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SecurityContext:
    """
    Security context for request processing.

    Contains authentication and authorization information
    for the current request.
    """

    authenticated: bool = False
    auth_method: str | None = None
    client_id: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    rate_limit_remaining: int | None = None

    @property
    def is_authenticated(self) -> bool:
        """Alias for authenticated for API consistency."""
        return self.authenticated


# Type aliases for common patterns
ToolName: TypeAlias = str
ResourceUri: TypeAlias = str
PromptId: TypeAlias = str
SessionId: TypeAlias = str
