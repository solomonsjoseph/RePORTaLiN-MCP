# ADR-0003: Structlog for Logging

## Status

Accepted

## Context

The RePORTaLiN MCP server requires a logging solution that:

1. Produces machine-parseable output for log aggregation (ELK, Splunk, etc.)
2. Supports contextual logging (request IDs, user context)
3. Works with async code
4. Provides human-readable output during development
5. Integrates with Python's standard logging ecosystem

## Decision

We will use **structlog** for all application logging.

```python
import structlog

logger = structlog.get_logger(__name__)

# Structured logging with context
logger.info(
    "Query executed",
    query_type="aggregate",
    row_count=150,
    execution_time_ms=23.5,
)
```

Configuration provides environment-aware formatting:
- **Development**: Pretty-printed, colored console output
- **Production**: Compact JSON for log aggregation

## Consequences

### Positive

- **Structured by default**: All log entries are key-value pairs
- **Context propagation**: Easy to add request-scoped context via context variables
- **Flexible processors**: Chain of processors for filtering, enrichment, formatting
- **Environment-aware**: Automatic format switching based on ENVIRONMENT setting
- **Standard library integration**: Works alongside Python's logging module
- **Async-safe**: Context variables work correctly with asyncio
- **PHI redaction**: Custom processors can automatically redact sensitive fields

### Negative

- **Learning curve**: Different paradigm from traditional logging
- **Dependency**: Another library to maintain
- **Performance**: Slightly more overhead than raw print statements

### Neutral

- JSON output requires log aggregator configuration
- Colored output requires terminal support

## Implementation Details

```python
# Context variable for request-scoped data
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Custom processor to add request ID
def add_request_id(logger, method_name, event_dict):
    request_id = _request_id_ctx.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict

# Environment-aware configuration
if settings.environment.is_local:
    # Pretty console output for development
    renderer = structlog.dev.ConsoleRenderer()
else:
    # JSON for production log aggregation
    renderer = structlog.processors.JSONRenderer()
```

## Alternatives Considered

### Python standard logging with JSON formatter

- Well-known API
- No additional dependencies

Not chosen because: Harder to add contextual data, less elegant processor chain.

### Loguru

- Simple API
- Good defaults

Not chosen because: Less flexible processor chain, not as well-suited for structured output.

### Custom logging wrapper

- Full control
- No dependencies

Not chosen because: Reinventing the wheel; structlog is battle-tested.

## References

- [structlog documentation](https://www.structlog.org/en/stable/)
- [12-Factor App: Logs](https://12factor.net/logs)
- [JSON Lines format](https://jsonlines.org/)
