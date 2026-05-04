# Configuration Reference

<!--
Document Type: Reference (Diátaxis)
Target Audience: Developers configuring the application
Prerequisites: Basic understanding of environment variables
-->

> **Type**: Reference | **Updated**: 2025-12-12 | **Status**: ✅ Production Ready

**Related Documentation:**
- [MCP Server Setup](MCP_SERVER_SETUP.md) — Server integration guide
- [Logging Architecture](LOGGING_ARCHITECTURE.md) — Encrypted logging configuration
- [Security Policy](../SECURITY.md) — Security-related settings

---

## Overview

RePORTaLiN-Agent uses Pydantic-based type-safe configuration with `reportalin.core.config`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ENVIRONMENT LAYER                                  │
│  .env file, OS environment variables, shell exports                         │
└─────────────────┬───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION LAYER                                   │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │                  reportalin.core.config (Settings)                       │ │
│ │  ─────────────────────────────────────────────────────────────────────  │ │
│ │  • Pydantic BaseSettings                                                 │ │
│ │  • Environment variable binding                                          │ │
│ │  • Type validation & coercion                                            │ │
│ │  • Nested settings groups                                                │ │
│ │  • Path constants for data pipeline                                      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                                    │
│  server/main.py, client/agent.py, data processing modules                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Module

### `reportalin.core.config`

**Purpose:** Type-safe, environment-aware configuration using Pydantic.

#### Settings Hierarchy

```python
Settings
├── debug: bool
├── log_level: str
├── privacy_mode: str
├── logging: LoggingSettings
│   ├── json_format: bool
│   ├── redact_phi: bool
│   ├── encrypted_log_dir: Path
│   └── encrypt_sensitive: bool
├── encryption: EncryptionSettings
│   ├── public_key_path: Optional[Path]
│   ├── private_key_path: Optional[Path]
│   ├── key_rotation_days: int
│   └── authorized_key_fingerprints: list[str]
└── mcp: MCPSettings
    ├── transport: TransportMode (stdio | sse)
    ├── host: str
    ├── port: int
    ├── k_anonymity_threshold: int
    └── allow_raw_data: bool
```

#### Environment Variable Mapping

| Setting | Environment Variable | Default |
|---------|---------------------|---------|
| `debug` | `REPORTALIN_DEBUG_MODE` | `false` |
| `log_level` | `REPORTALIN_LOG_LEVEL` | `INFO` |
| `privacy_mode` | `REPORTALIN_PRIVACY_MODE` | `strict` |
| `logging.json_format` | `REPORTALIN_LOG_JSON_FORMAT` | `false` |
| `logging.redact_phi` | `REPORTALIN_LOG_REDACT_PHI` | `true` |
| `logging.encrypt_sensitive` | `REPORTALIN_LOG_ENCRYPT_SENSITIVE` | `true` |
| `encryption.key_rotation_days` | `REPORTALIN_CRYPTO_KEY_ROTATION_DAYS` | `90` |
| `mcp.transport` | `REPORTALIN_MCP_TRANSPORT` | `stdio` |
| `mcp.host` | `REPORTALIN_MCP_HOST` | `127.0.0.1` |
| `mcp.port` | `REPORTALIN_MCP_PORT` | `8765` |
| `mcp.k_anonymity_threshold` | `REPORTALIN_MCP_K_ANONYMITY_THRESHOLD` | `5` |

#### Usage

```python
from reportalin.core.config import get_settings

settings = get_settings()  # Singleton instance

# Access nested settings
if settings.logging.redact_phi:
    redact_sensitive_fields(data)

# Check transport mode
if settings.mcp.transport == TransportMode.STDIO:
    run_stdio_server()

# Type-safe access
port: int = settings.mcp.port  # Guaranteed to be int
```

---

## Configuration Priority

Settings are loaded with the following priority (highest to lowest):

1. **Environment Variables** - Override everything
2. **`.env` File** - Project-specific defaults
3. **Default Values** - Hardcoded in settings classes

```
Environment Variable  >  .env File  >  Code Default
```

---

## Security Considerations

### Secure Defaults

All security-sensitive settings default to the **most restrictive** option:

| Setting | Default | Why |
|---------|---------|-----|
| `privacy_mode` | `strict` | Maximum PHI protection |
| `logging.redact_phi` | `true` | Prevent accidental PHI logging |
| `mcp.allow_raw_data` | `false` | Block raw PHI access |
| `mcp.k_anonymity_threshold` | `5` | HIPAA-compliant minimum |
| `mcp.host` | `127.0.0.1` | No network exposure |

### Warnings

The settings system emits warnings for potentially insecure configurations:

```python
if settings.mcp.allow_raw_data:
    warnings.warn("SECURITY: Raw data access enabled - PHI may be exposed!")

if settings.debug:
    warnings.warn("DEBUG mode enabled - not for production use!")
```

---

## Validation

### Pydantic Validation

All settings are validated at load time:

```python
class MCPSettings(BaseModel):
    port: int = Field(ge=1, le=65535)  # Valid port range
    k_anonymity_threshold: int = Field(ge=1)  # Must be positive
    transport: TransportMode  # Enum validation
```

### Custom Validators

```python
@field_validator("log_level")
def validate_log_level(cls, v: str) -> str:
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if v.upper() not in valid:
        raise ValueError(f"Invalid log level: {v}")
    return v.upper()
```

---

## Integration Points

### MCP Server

```python
# reportalin/server/main.py
from reportalin.core.config import get_settings

settings = get_settings()

if settings.mcp.transport == TransportMode.SSE:
    mcp.run(transport="sse", port=settings.mcp.port)
else:
    mcp.run()  # Default stdio
```

### Encrypted Logging

```python
# reportalin/core/logging.py
from reportalin.core.config import get_settings

class SecureLogger:
    def __init__(self):
        settings = get_settings()
        self.log_dir = settings.logging.encrypted_log_dir
        self.key_rotation_days = settings.encryption.key_rotation_days
```

### Structured Logging

```python
# reportalin/core/logging.py
from reportalin.core.config import get_settings

def configure_logging():
    settings = get_settings()
    if settings.logging.json_format:
        add_json_handler()
```

---

## Testing Configuration

### Unit Test Setup

```python
# tests/conftest.py
import pytest
from reportalin.core.config import get_settings

@pytest.fixture(autouse=True)
def reset_config():
    """Reset settings singleton between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

### Environment Override in Tests

```python
def test_strict_mode(monkeypatch):
    monkeypatch.setenv("REPORTALIN_PRIVACY_MODE", "strict")
    settings = get_settings()
    assert settings.privacy_mode == "strict"
```

---

## Reference

### Complete `.env.example`

See [.env.example](../.env.example) for all available environment variables with documentation.

### Related Modules

- `reportalin.core.config` - Configuration settings
- `reportalin.core.logging` - Structured logging
- `reportalin.types.models` - Data models including `TransportMode`

---

**Last Updated**: 2025-12-12  
**Document Version**: 2.0
