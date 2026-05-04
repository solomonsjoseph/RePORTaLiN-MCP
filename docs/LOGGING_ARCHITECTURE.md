# Logging Architecture

<!--
Document Type: Explanation (Diátaxis)
Target Audience: Developers and security auditors
Prerequisites: Understanding of encryption basics
-->

> **Type**: Explanation | **Updated**: 2025-12-08 | **Status**: ✅ Verified & Compliant

This document explains the design and implementation of the privacy-compliant logging system for healthcare/PHI data processing.

**Related Documentation:**
- [Configuration Reference](CONFIGURATION.md) — Logging settings
- [MCP Server Setup](MCP_SERVER_SETUP.md) — Server integration
- [Security Policy](../SECURITY.md) — Audit requirements

---

## Overview

The logging system implements four layers:

| Layer | Purpose |
|-------|---------|
| Operational Logging | Standard Python logging with custom SUCCESS level |
| Structured Logging | JSON output with automatic PHI redaction |
| Encrypted Logging | RSA-OAEP + AES-256-CBC hybrid encryption |
| CLI Tools | Secure log decryption and key management |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                 │
│  (main.py, MCP tools, extract_data.py, etc.)                               │
└─────────────┬──────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LOGGING ABSTRACTION LAYER                           │
│ ┌─────────────────────────────┐  ┌─────────────────────────────────────────┐│
│ │  scripts/utils/logging.py  │  │  scripts/core/structured_logging.py    ││
│ │  ─────────────────────────  │  │  ─────────────────────────────────────  ││
│ │  • Standard Python logging  │  │  • JSON-formatted output               ││
│ │  • Custom SUCCESS level     │  │  • Request-scoped context (ContextVar) ││
│ │  • VerboseLogger tree-view  │  │  • Automatic PHI redaction             ││
│ │  • File + Console handlers  │  │  • BoundLogger for context binding     ││
│ └─────────────────────────────┘  └─────────────────────────────────────────┘│
└─────────────┬──────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ENCRYPTION LAYER                                    │
│ ┌─────────────────────────────┐  ┌─────────────────────────────────────────┐│
│ │ server/crypto_logger.py│  │   scripts/core/log_decryptor.py        ││
│ │  ─────────────────────────  │  │   ─────────────────────────────────     ││
│ │  • Hybrid encryption        │  │   • RSA-OAEP + AES-256-CBC decryption  ││
│ │    (RSA-OAEP + AES-256-CBC) │  │   • Key fingerprint authorization      ││
│ │  • PHI auto-redaction       │  │   • Audit trail for decryption ops     ││
│ │  • Key rotation tracking    │  │   • CLI for developer access           ││
│ │  • Audit metadata           │  │   • Keypair generation utility         ││
│ └─────────────────────────────┘  └─────────────────────────────────────────┘│
└─────────────┬──────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                     │
│ ┌──────────────────────────────────┐  ┌───────────────────────────────────┐ │
│ │         .logs/                   │  │     encrypted_logs/               │ │
│ │  • Plain-text operational logs   │  │  • .enc files (JSON-wrapped)      │ │
│ │  • Timestamped filenames         │  │  • AES ciphertext + RSA-enc key   │ │
│ │  • Auto-created directory        │  │  • Content-hash in filename       │ │
│ └──────────────────────────────────┘  └───────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Dependency Graph

```
scripts/core/settings.py
         │
         │ (configuration)
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  server/crypto_logger.py ────► scripts/utils/logging.py      │
│         │                                    ▲                     │
│         │ (decryption/PHI utils)             │                     │
│         ▼                                    │                     │
│  scripts/core/log_decryptor.py               │                     │
│         │                                    │                     │
│         │ (PHI redaction)                    │                     │
│         ▼                                    │                     │
│  scripts/core/structured_logging.py ─────────┘                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Base Logging (`scripts/utils/logging.py`)

**Purpose:** Centralized operational logging with custom levels and verbose debugging.

| Feature | Description |
|---------|-------------|
| **Custom SUCCESS Level** | Level 25 (between INFO:20 and WARNING:30) |
| **Dual Output** | Console (SUCCESS/ERROR/CRITICAL) + File (all levels) |
| **VerboseLogger** | Tree-view formatting for DEBUG mode debugging |
| **Singleton Pattern** | Single logger instance shared across all modules |

**Log Levels:**
```
DEBUG (10)    → Verbose mode only (detailed file processing, timing)
INFO (20)     → Standard operations (file output only)
SUCCESS (25)  → Custom level (console + file)
WARNING (30)  → Potential issues
ERROR (40)    → Failures (console + file)
CRITICAL (50) → Fatal errors (console + file)
```

**Public API:**
```python
from reportalin.data.utils.logging import (
    setup_logger,
    get_logger,
    debug, info, warning, error, critical, success,
)

setup_logger(name, log_level, simple_mode)
get_logger(name)
debug(msg), info(msg), warning(msg)
error(msg), critical(msg), success(msg)
```

---

### 2. Structured Logging (`reportalin.core.logging`)

**Purpose:** JSON-formatted logging with automatic PHI redaction and request-scoped context.

| Feature | Description |
|---------|-------------|
| **JSONFormatter** | Outputs logs as JSON (ELK/Splunk/CloudWatch compatible) |
| **StructuredLogger** | Wrapper with automatic PHI redaction |
| **BoundLogger** | Logger with permanently bound context |
| **log_context()** | Context manager for request-scoped data |
| **PHI_PATTERNS** | Frozenset of PHI-sensitive field patterns |

**PHI Redaction Patterns (21 patterns):**
```python
PHI_PATTERNS = frozenset({
    "name", "ssn", "mrn", "dob", "birth", "address", "phone",
    "email", "patient", "street", "city", "zip", "account",
    "license", "device", "ip_address", "mac_address",
    "biometric", "photo", "fax", "url", "vehicle"
})
```

**Public API:**
```python
from reportalin.core.logging import (
    get_logger,
    bind_context,
    configure_logging,
)

logger = get_logger(__name__)
logger.info("Query executed", query_type="aggregate", row_count=100)

with bind_context(request_id="req-123", user="analyst"):
    logger.info("Processing")  # Includes request_id and user
```

---

### 3. Encrypted Logging (`reportalin.server.security`)

**Purpose:** Secure logging for sensitive MCP operations with hybrid RSA/AES encryption.

| Feature | Description |
|---------|-------------|
| **Hybrid Encryption** | AES-256-GCM for content, RSA-OAEP for key |
| **PHI Auto-Redaction** | Pre-encryption sanitization |
| **Key Rotation** | Tracks key age, warns at 90 days (NIST guideline) |
| **Audit Metadata** | Key fingerprint, timestamp, service name |
| **Graceful Fallback** | Base64 encoding if cryptography unavailable |

**Encryption Scheme:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ENCRYPTION FLOW                                  │
│                                                                         │
│   Log Entry (JSON)                                                      │
│         │                                                               │
│         ▼                                                               │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│   │  AES-256    │    │  RSA-OAEP   │    │  Output     │                │
│   │  CBC Mode   │    │  SHA-256    │    │  .enc file  │                │
│   │  PKCS7 Pad  │    │  2048+ bit  │    │  (JSON)     │                │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                │
│          │                  │                  │                        │
│          ▼                  ▼                  ▼                        │
│   [random 32B key]   [encrypted key]    {                              │
│   [random 16B IV]    ─────────────►       "encrypted": true,           │
│   [ciphertext]                            "encrypted_key": "...",      │
│                                           "iv": "...",                 │
│                                           "ciphertext": "..."          │
│                                         }                              │
└─────────────────────────────────────────────────────────────────────────┘
```

**Public API:**
```python
from server.crypto_logger import (
    SecureLogger,
    get_secure_logger,
    reset_secure_logger,
    CRYPTO_AVAILABLE,
)

logger = get_secure_logger()
logger.log_error("Database failed", {"host": "localhost"}, exception=e)
logger.log_warning("Rate limit approaching", {"current": 95, "max": 100})
logger.log_info("Tool executed", {"tool": "get_study_variables"})
logger.log_crash(exception, {"state": "processing"})
```

---

### 4. Log Decryptor (`scripts/core/log_decryptor.py`)

**Purpose:** CLI tool for authorized developers to decrypt audit logs.

| Feature | Description |
|---------|-------------|
| **Hybrid Decryption** | Matches crypto_logger.py scheme |
| **Authorization** | Key fingerprint verification |
| **Filtering** | By date range, log level |
| **PHI Protection** | Requires `--show-phi` flag for raw data |
| **Key Generation** | Creates RSA keypairs with secure permissions |

**CLI Usage:**
```bash
# Decrypt a single file
python -m scripts.core.log_decryptor encrypted_logs/log_xxx.enc

# Decrypt all ERROR logs from last 24 hours
python -m scripts.core.log_decryptor encrypted_logs/ --level ERROR --since "1 day ago"

# Export to JSON (PHI redacted)
python -m reportalin.core.log_decryptor encrypted_logs/ --output decrypted.json

# Show PHI (requires explicit flag)
python -m reportalin.core.log_decryptor encrypted_logs/ --show-phi

# Generate new keypair
python -m reportalin.core.log_decryptor --generate-keys
```

**Public API:**
```python
from reportalin.core.log_decryptor import (
    LogDecryptor,
    generate_keypair,
    DecryptionError,
    AuthorizationError,
)

decryptor = LogDecryptor(private_key_path="~/.ssh/reportalin_key")
entries = decryptor.decrypt_directory("encrypted_logs/", level="ERROR")
```

---

## Security Analysis

### ✅ Strengths

| Area | Implementation |
|------|----------------|
| **Encryption** | RSA-OAEP (2048+ bit) + AES-256-GCM hybrid |
| **Key Management** | 90-day rotation warnings, fingerprint-based auth |
| **PHI Protection** | Multi-layer redaction (pre-encrypt + post-decrypt) |
| **Audit Trail** | Key fingerprint, timestamps in encrypted logs |
| **Secure Storage** | `.enc` files with content hashes, restricted permissions |
| **Fallback** | Graceful degradation to base64 if crypto unavailable |

### ⚠️ Recommendations

| Area | Current State | Recommendation |
|------|--------------|----------------|
| **Key Storage** | Placeholder key in code | Replace with production key via settings |
| **Private Key** | Env var or file | Consider HSM for production |
| **Log Rotation** | Manual cleanup | Add automatic log rotation policy |
| **Monitoring** | Warnings to console | Integrate with alerting system |

---

## Integration Points

### MCP Server (`reportalin/server/main.py`)

```python
from reportalin.core.logging import get_logger

logger = get_logger(__name__)

async def handle_tool_call(name: str, arguments: dict):
    try:
        result = await execute_tool(name, arguments)
        logger.info(f"Tool executed: {name}", extra={"args": arguments})
        return result
    except Exception as e:
        logger.error(f"Tool failed: {name}", extra={"args": arguments}, exc_info=e)
        raise
```

### Pipeline Modules

```python
from reportalin.data.utils.logging import info, success
from reportalin.core.logging import get_logger, bind_context

# Standard logging
info("Processing started")
success("Processing complete")

# Structured logging with context
logger = get_logger(__name__)
with log_context(batch_id="batch-001", user="analyst"):
    logger.info("Processing batch", record_count=1000)
```

---

## Testing Recommendations

### Unit Tests

```python
# tests/unit/test_crypto_logger.py
def test_phi_redaction():
    """Verify PHI patterns are redacted before encryption."""
    
def test_encryption_roundtrip():
    """Verify encrypt → decrypt produces original content."""
    
def test_key_rotation_warning():
    """Verify warning when key age exceeds threshold."""
```

### Integration Tests

```python
# tests/integration/test_logging_integration.py
def test_encrypted_log_file_created():
    """Verify .enc files are created in encrypted_logs/."""
    
def test_decryption_with_authorized_key():
    """Verify authorized keys can decrypt logs."""
    
def test_decryption_denied_unauthorized_key():
    """Verify unauthorized keys are rejected."""
```

---

## Configuration Reference

### Settings (`scripts/core/settings.py`)

```python
class EncryptionSettings:
    public_key_path: Optional[Path]  # RSA public key for encryption
    
class LoggingSettings:
    encrypted_log_dir: Path  # Default: project_root/encrypted_logs
    
class Settings:
    encryption: EncryptionSettings
    logging: LoggingSettings
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `REPORTALIN_CRYPTO_PRIVATE_KEY` | RSA private key PEM for decryption |

---

## Compliance Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| PHI/PII Redaction | ✅ | Multi-layer (21 patterns) |
| Encryption at Rest | ✅ | AES-256-CBC for content |
| Key Protection | ✅ | RSA-OAEP for AES key |
| Audit Trail | ✅ | Timestamps, fingerprints |
| Access Control | ✅ | Key fingerprint authorization |
| Key Rotation | ✅ | 90-day warnings |
| Secure Defaults | ✅ | Encryption on, redaction on |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-04 | Initial architecture documentation |
| 1.0 | 2025-12-04 | Fixed datetime to timezone-aware UTC |
| 1.0 | 2025-12-04 | Added `__all__` exports to crypto_logger.py |
| 1.0 | 2025-12-04 | Added `__all__` exports to structured_logging.py |
