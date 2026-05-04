"""
Shared constants for the RePORTaLiN MCP system.

Centralizes magic strings, default values, and configuration constants
to ensure consistency and easy modification.

Updated: December 2025 - MCP Protocol 2025-03-26 compliance
"""

from __future__ import annotations

__all__ = [
    # Server identification
    "SERVER_NAME",
    "SERVER_VERSION",
    "PROTOCOL_VERSION",
    # Transport defaults
    "DEFAULT_TRANSPORT",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    # Security constants
    "MIN_K_ANONYMITY",
    "MAX_RESULTS_PER_QUERY",
    "AUDIT_LOG_RETENTION_DAYS",
    # Timeouts
    "REQUEST_TIMEOUT",
    "SHUTDOWN_TIMEOUT",
    "SSE_KEEPALIVE_INTERVAL",
    # Rate limiting
    "DEFAULT_RATE_LIMIT_RPM",
    "DEFAULT_RATE_LIMIT_BURST",
    # File paths
    "DATA_DICTIONARY_PATH",
    "ENCRYPTED_LOGS_PATH",
    # Environment variables
    "ENV_LOG_LEVEL",
    "ENV_TRANSPORT",
    "ENV_HOST",
    "ENV_PORT",
    # Security
    "TOKEN_ROTATION_GRACE_PERIOD_SECONDS",
    "ENCRYPTION_KEY_ROTATION_DAYS",
]

# Server identification
SERVER_NAME = "reportalin-mcp"
SERVER_VERSION = "0.3.0"
# MCP Protocol version - updated to latest stable (March 2025)
# See: https://spec.modelcontextprotocol.io/specification/
PROTOCOL_VERSION = "2025-03-26"

# Transport defaults
DEFAULT_TRANSPORT = "stdio"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# Security constants
MIN_K_ANONYMITY = 5  # Minimum cell size for k-anonymity
MAX_RESULTS_PER_QUERY = 100  # Limit on returned results
AUDIT_LOG_RETENTION_DAYS = 365  # DPDP Rules 2025 compliance

# Timeouts (seconds)
REQUEST_TIMEOUT = 30.0
SHUTDOWN_TIMEOUT = 5.0
SSE_KEEPALIVE_INTERVAL = 15.0  # SSE ping interval for connection health

# Rate limiting defaults (requests per minute)
DEFAULT_RATE_LIMIT_RPM = 60
DEFAULT_RATE_LIMIT_BURST = 20

# File paths (relative to project root)
DATA_DICTIONARY_PATH = "results/data_dictionary_mappings"
ENCRYPTED_LOGS_PATH = "encrypted_logs"

# Environment variable names
ENV_LOG_LEVEL = "REPORTALIN_LOG_LEVEL"
ENV_TRANSPORT = "REPORTALIN_TRANSPORT"
ENV_HOST = "REPORTALIN_HOST"
ENV_PORT = "REPORTALIN_PORT"

# Security-related constants
TOKEN_ROTATION_GRACE_PERIOD_SECONDS = 300  # 5 minutes
ENCRYPTION_KEY_ROTATION_DAYS = 90  # Rotate encryption keys every 90 days
