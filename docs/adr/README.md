# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the RePORTaLiN-Agent project.

## What is an ADR?

An Architecture Decision Record captures an important architectural decision made along with its context and consequences.

## ADR Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [0001](0001-use-fastmcp-for-mcp-server.md) | Use FastMCP for MCP Server | Accepted | 2025-12-01 |
| [0002](0002-aes-256-gcm-over-fernet.md) | AES-256-GCM Over Fernet | Accepted | 2025-12-05 |
| [0003](0003-structlog-for-logging.md) | Structlog for Logging | Accepted | 2025-12-01 |

## Creating New ADRs

Use the template in `template.md` to create new ADRs:

```bash
cp docs/adr/template.md docs/adr/NNNN-title-with-dashes.md
```

## Status Definitions

- **Proposed**: Under discussion
- **Accepted**: Decision has been made
- **Deprecated**: No longer valid
- **Superseded**: Replaced by another ADR
