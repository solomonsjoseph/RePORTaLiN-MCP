# ADR-0001: Use FastMCP for MCP Server

## Status

Accepted

## Context

We needed to implement a Model Context Protocol (MCP) server for the RePORTaLiN clinical data system. The MCP protocol enables LLMs to interact with external tools and data sources in a standardized way.

Options considered:
1. **FastMCP** (official Python SDK with high-level API)
2. **Low-level MCP SDK** (raw Server class)
3. **Custom implementation** (build from scratch)

## Decision

We will use **FastMCP** from the official `mcp` Python SDK for implementing the MCP server.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="RePORTaLiN",
    instructions="Clinical data query system...",
)

@mcp.tool()
def query_database(input: QueryDatabaseInput) -> dict:
    ...
```

## Consequences

### Positive

- **Automatic schema generation**: Type hints on tool functions automatically generate JSON schemas for LLMs
- **Decorator-based registration**: Clean `@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()` syntax
- **Built-in transports**: stdio and HTTP/SSE transports work out of the box
- **Spec compliance**: Maintained by Anthropic, guaranteed protocol compatibility
- **Reduced boilerplate**: ~70% less code compared to low-level implementation
- **Context parameter**: Easy access to logging and progress reporting via `Context`

### Negative

- **Less control**: Some protocol details are abstracted away
- **Dependency on external library**: Must track SDK updates
- **Learning curve**: Team needs to understand FastMCP patterns

### Neutral

- We can drop down to low-level `Server` class if FastMCP becomes limiting
- FastMCP is the recommended approach in official MCP documentation

## Alternatives Considered

### Low-level MCP Server class

More control but significantly more boilerplate:
- Manual handler registration
- Manual schema definition
- Manual transport setup

Not chosen because: FastMCP provides all features we need with much less code.

### Custom implementation

Full control but:
- Protocol compliance risk
- Maintenance burden
- No community support

Not chosen because: MCP protocol is complex and evolving; better to use official SDK.

## References

- [MCP Python SDK Documentation](https://modelcontextprotocol.io/docs/tools/python)
- [FastMCP API Reference](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
