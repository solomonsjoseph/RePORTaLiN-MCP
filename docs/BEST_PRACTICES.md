# Best Practices Applied from Awesome Copilot

This document summarizes the best practices applied to the RePORTaLiN-Agent project based on recommendations from the [Awesome Copilot](https://github.com/bsorrentino/awesome-copilot) repository.

## Overview

The RePORTaLiN-Agent project follows industry best practices for:
- Python development (PEP 8, PEP 257)
- Model Context Protocol (MCP) server development
- Security and OWASP guidelines
- Testing and documentation
- Performance optimization

## Python Best Practices

### 1. Code Style (PEP 8)

**Applied**:
- ✅ Black formatter (line length: 88 characters)
- ✅ Ruff linter with comprehensive rule set
- ✅ Proper indentation (4 spaces)
- ✅ Consistent naming conventions

**Configuration** (`pyproject.toml`):
```toml
[tool.black]
line-length = 88
target-version = ['py310', 'py311', 'py312', 'py313']

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM", "TCH", "PTH", "ERA", "RUF"]
```

### 2. Type Hints

**Applied**:
- ✅ Type hints on all function signatures
- ✅ Use of `typing` module for complex types
- ✅ MyPy strict mode enabled

**Example**:
```python
from typing import Any
from pathlib import Path

def load_data(path: Path, limit: int | None = None) -> dict[str, Any]:
    """Load data from path with optional limit."""
    ...
```

### 3. Docstrings (PEP 257)

**Applied**:
- ✅ Comprehensive docstrings on all public functions
- ✅ Args, Returns, Raises sections
- ✅ Examples where helpful

**Template**:
```python
def function_name(arg1: str, arg2: int = 0) -> dict[str, Any]:
    """
    Brief one-line description.
    
    Longer description explaining purpose, behavior, and design decisions.
    
    Args:
        arg1: Description of first argument
        arg2: Description of second argument (default: 0)
        
    Returns:
        Dictionary containing result data with keys:
        - "status": Operation status
        - "data": Result data
        
    Raises:
        ValueError: If arg1 is empty
        FileNotFoundError: If required file not found
        
    Example:
        >>> result = function_name("example", arg2=5)
        >>> assert result["status"] == "success"
        
    Note:
        Additional context or warnings go here.
    """
```

### 4. Edge Case Handling

**Applied**:
- ✅ Explicit edge case documentation
- ✅ Try-except blocks with specific exceptions
- ✅ Validation before processing

**Example**:
```python
def calculate_k_anonymity(records: list[dict]) -> int:
    """
    Calculate k-anonymity threshold.
    
    Edge Cases:
        - Empty list: Returns 0
        - Single record: Returns 1 (not anonymous)
        - All identical: Returns total count
    """
    if not records:  # Edge case: empty
        return 0
    if len(records) == 1:  # Edge case: single record
        return 1
    # ... implementation
```

## MCP Server Best Practices

### 1. FastMCP Patterns

**Applied**:
- ✅ Import from `mcp.server.fastmcp`
- ✅ Use `@mcp.tool()` decorators
- ✅ SSE transport for HTTP servers
- ✅ Structured output with Pydantic models

**Example**:
```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("Data Dictionary Server")

class QueryResult(BaseModel):
    """Structured query result."""
    count: int = Field(description="Number of results")
    variables: list[str] = Field(description="Variable names")

@mcp.tool()
def search_variables(query: str) -> QueryResult:
    """Search for variables in data dictionary."""
    # ... implementation
    return QueryResult(count=10, variables=["age", "gender"])
```

### 2. Context-Aware Logging

**Applied**:
- ✅ Use `Context` parameter for MCP tools
- ✅ Progress reporting with `ctx.report_progress()`
- ✅ Structured logging with `ctx.info()`, `ctx.error()`

**Example**:
```python
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

@mcp.tool()
async def process_data(
    query: str,
    ctx: Context[ServerSession, None]
) -> str:
    """Process data with progress tracking."""
    await ctx.info(f"Starting query: {query}")
    await ctx.report_progress(0.5, 1.0, "Processing...")
    # ... implementation
    await ctx.info("Query completed")
    return result
```

### 3. Error Handling

**Applied**:
- ✅ Consistent error response format
- ✅ Never expose internal stack traces
- ✅ Log errors for debugging

**Pattern**:
```python
@mcp.tool()
async def risky_operation(input: str) -> dict[str, Any]:
    """Operation with comprehensive error handling."""
    try:
        result = await perform_operation(input)
        return {"status": "success", "result": result}
    except ValidationError as e:
        await ctx.error(f"Validation failed: {e}")
        return {"status": "error", "error": f"Invalid input: {e}"}
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}", exc_info=True)
        return {"status": "error", "error": "Internal server error"}
```

### 4. Resource Management

**Applied**:
- ✅ Lifespan context managers for shared resources
- ✅ Proper startup/shutdown handling
- ✅ Connection pooling where applicable

**Example**:
```python
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class AppContext:
    db: Database

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    db = await Database.connect()
    try:
        yield AppContext(db=db)
    finally:
        await db.disconnect()

mcp = FastMCP("My Server", lifespan=app_lifespan)
```

## Security Best Practices (OWASP)

### 1. Authentication & Authorization

**Applied**:
- ✅ Bearer token authentication
- ✅ Constant-time token comparison (timing attack prevention)
- ✅ Authentication middleware at ASGI level
- ✅ Separate public vs. protected endpoints

**Implementation**:
```python
def verify_token(provided: str | None, expected: str | None) -> bool:
    """Constant-time token comparison to prevent timing attacks."""
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided, expected)
```

### 2. Input Validation

**Applied**:
- ✅ ASGI middleware for request validation
- ✅ Max query string/parameter length limits
- ✅ Pydantic models for typed input validation

**Configuration**:
```python
class InputValidationMiddleware:
    """Validate request size limits to prevent DoS."""
    def __init__(
        self,
        app: ASGIApp,
        max_query_param_length: int = 1000,
        max_query_string_length: int = 4096,
    ):
        ...
```

### 3. Rate Limiting

**Applied**:
- ✅ Token bucket algorithm
- ✅ Per-IP rate limiting
- ✅ Configurable limits (requests/minute, burst size)
- ✅ Proper HTTP 429 responses with Retry-After header

**Configuration** (`.env`):
```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_SECOND=10
RATE_LIMIT_BURST_SIZE=20
```

### 4. Security Headers

**Applied**:
- ✅ Content-Security-Policy
- ✅ X-Frame-Options: DENY
- ✅ X-Content-Type-Options: nosniff
- ✅ Strict-Transport-Security (HTTPS)

**Implementation**:
```python
class SecurityHeadersMiddleware:
    """Add security headers to all responses."""
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Content-Security-Policy": "default-src 'self'",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }
```

### 5. CORS Configuration

**Applied**:
- ✅ Environment-specific CORS policies
- ✅ Production: Explicit origin whitelist (deny by default)
- ✅ Development: Permissive for local testing
- ✅ Exposed headers for client tracing

**Configuration**:
```python
# Production: Explicit origins only
cors_origins = settings.cors_allowed_origins  # ["https://example.com"]

# Development: Allow all
cors_origins = ["*"]
```

### 6. Encryption

**Applied**:
- ✅ AES-256-GCM for sensitive data
- ✅ Secure key derivation (PBKDF2)
- ✅ Cryptographically secure random nonces

**See**: `src/reportalin/server/security/encryption.py`

## Testing Best Practices

### 1. Test Structure

**Applied**:
- ✅ Separate unit and integration tests
- ✅ Pytest markers for test categorization
- ✅ Async test support with `pytest-asyncio`
- ✅ Test fixtures for common setup

**Example**:
```python
@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.mcp
async def test_mcp_tool_search():
    """
    Test MCP tool for variable search.
    
    Test Cases:
        1. Valid query returns expected results
        2. Empty query returns all variables
        3. Invalid query returns empty results
        
    Integration Points:
        - MCP server startup
        - Tool registration
        - JSON-RPC message handling
    """
    client = TestMCPClient()
    result = await client.call_tool("search_variables", {"query": "age"})
    assert result["status"] == "success"
```

### 2. Coverage Requirements

**Applied**:
- ✅ Minimum 80% code coverage
- ✅ Branch coverage enabled
- ✅ Coverage reports in CI/CD

**Configuration** (`pyproject.toml`):
```toml
[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 3. Property-Based Testing

**Applied**:
- ✅ Hypothesis for fuzz testing
- ✅ Property-based tests for validation logic

**Example**:
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
def test_variable_name_validation(name: str):
    """Property: All non-empty strings should be valid variable names."""
    result = validate_variable_name(name)
    assert isinstance(result, bool)
```

## Documentation Best Practices

### 1. Project Documentation

**Structure**:
```
docs/
├── CONFIGURATION.md       # Configuration guide
├── DATA_PIPELINE.md       # Data pipeline details
├── IMPLEMENTATION_PLAN.md # Implementation roadmap
├── LOGGING_ARCHITECTURE.md # Logging design
├── MCP_SERVER_SETUP.md    # MCP server setup
├── TESTING_GUIDE.md       # Testing guide
├── BEST_PRACTICES.md      # This document
└── adr/                   # Architecture Decision Records
    ├── 0001-use-fastmcp-for-mcp-server.md
    ├── 0002-aes-256-gcm-over-fernet.md
    └── 0003-structlog-for-logging.md
```

### 2. Architecture Decision Records (ADR)

**Applied**:
- ✅ ADR template for design decisions
- ✅ Numbered ADRs with context, decision, consequences
- ✅ Version control for design evolution

**Example**: `docs/adr/0001-use-fastmcp-for-mcp-server.md`

### 3. Code Comments

**Guidelines**:
- Explain **why**, not **what**
- Document design decisions
- Flag security considerations
- Mark technical debt with `TODO:` or `FIXME:`

**Example**:
```python
# Design Decision: Use constant-time comparison to prevent timing attacks
# that could leak token length information through response time variation
if not secrets.compare_digest(provided_token, expected_token):
    return False
```

## Performance Best Practices

### 1. Async/Await Usage

**Applied**:
- ✅ Async functions for I/O-bound operations
- ✅ Proper await on async calls
- ✅ FastAPI async endpoints

**Example**:
```python
@mcp.tool()
async def fetch_data(url: str) -> dict[str, Any]:
    """Async tool for network I/O."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### 2. Caching

**Applied**:
- ✅ LRU cache for expensive computations
- ✅ File-based caching for static data

**Example**:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(arg: str) -> int:
    """Cached computation to avoid repeated work."""
    # ... expensive operation
    return result
```

### 3. Lazy Loading

**Applied**:
- ✅ Load data on first use, not at import time
- ✅ Generator expressions for large datasets

**Example**:
```python
def load_large_dataset() -> Iterator[dict]:
    """Stream data instead of loading all into memory."""
    with open("data.jsonl") as f:
        for line in f:
            yield json.loads(line)
```

## Continuous Integration Best Practices

### 1. Pre-commit Hooks

**Applied** (`.pre-commit-config.yaml`):
- ✅ Black formatting
- ✅ Ruff linting
- ✅ MyPy type checking
- ✅ Bandit security scanning
- ✅ Commitizen conventional commits

### 2. CI/CD Pipeline

**Applied** (GitHub Actions):
- ✅ Test matrix (Python 3.10, 3.11, 3.12, 3.13)
- ✅ Security scanning (Bandit, pip-audit, safety)
- ✅ Code coverage reporting
- ✅ Automated releases with Commitizen

## Environment-Specific Practices

### 1. Configuration Management

**Applied**:
- ✅ Pydantic Settings for type-safe config
- ✅ `.env` files for local development
- ✅ Environment variables for production
- ✅ Secrets in environment vars (never in code)

**Example**:
```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mcp_auth_token: SecretStr | None = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 2. Logging

**Applied**:
- ✅ Structured logging with `structlog`
- ✅ Environment-specific log levels
- ✅ Request ID propagation
- ✅ No sensitive data in logs (names, DOBs, etc.)

**Configuration**:
```python
def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

## Package Management Best Practices

### 1. UV Package Manager

**Applied**:
- ✅ `uv` for fast dependency management
- ✅ `pyproject.toml` as single source of truth
- ✅ Optional dependency groups (dev, docs, data-prep)
- ✅ Lock file (`uv.lock`) for reproducible builds

**Usage**:
```bash
# Install all dependencies
uv sync --all-extras

# Install only production dependencies
uv sync

# Add new dependency
uv add "package-name>=1.0.0"

# Run scripts
uv run pytest
uv run ruff check .
```

### 2. Dependency Pinning

**Applied**:
- ✅ Upper bounds on major versions
- ✅ Security updates via Dependabot
- ✅ Regular dependency audits

**Example** (`pyproject.toml`):
```toml
dependencies = [
    "fastapi>=0.115.0,<1.0.0",  # Pin major version
    "pydantic>=2.0.0,<3.0.0",   # Pin major version
]
```

## Summary of Key Improvements

### ✅ Completed
1. Removed all deidentification-related code and configuration
2. Applied PEP 8 and PEP 257 standards
3. Implemented OWASP security best practices
4. Set up comprehensive testing framework
5. Created architecture decision records
6. Configured pre-commit hooks and CI/CD
7. Established structured logging

### 📋 Ongoing Best Practices
1. **Code Reviews**: All changes reviewed for:
   - Type hints completeness
   - Docstring quality
   - Security implications
   - Test coverage

2. **Documentation**: Keep docs up-to-date with:
   - API changes
   - Configuration options
   - Security advisories
   - Migration guides

3. **Dependency Management**:
   - Monthly security audit
   - Quarterly dependency updates
   - Document breaking changes

4. **Performance Monitoring**:
   - Track response times
   - Monitor memory usage
   - Profile slow operations

## References

- [Awesome Copilot - Python Instructions](https://github.com/bsorrentino/awesome-copilot/blob/main/instructions/python.instructions.md)
- [Awesome Copilot - Python MCP Server](https://github.com/bsorrentino/awesome-copilot/blob/main/instructions/python-mcp-server.instructions.md)
- [Awesome Copilot - Security & OWASP](https://github.com/bsorrentino/awesome-copilot/blob/main/instructions/security-and-owasp.instructions.md)
- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

## Version History

- **v1.0.0** (2025-01-XX): Initial best practices documentation
  - Based on Awesome Copilot Python and MCP server guidelines
  - Incorporates OWASP security standards
  - Documents current codebase practices
