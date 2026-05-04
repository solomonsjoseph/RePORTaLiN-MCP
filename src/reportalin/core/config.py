"""
Server Configuration Management.

This module provides type-safe configuration management using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults
for development, while enforcing strict validation for production deployments.

Design Decisions:
    - Pydantic Settings v2 for automatic .env loading and validation
    - Immutable configuration (frozen=True) to prevent runtime modifications
    - Environment-aware validation (stricter rules in production)
    - Secrets are never logged or serialized to prevent accidental exposure

Usage:
    >>> from reportalin.core.config import get_settings
    >>> settings = get_settings()
    >>> print(settings.mcp_port)
    8000

Environment Variables:
    MCP_PORT         - Server port (default: 8000)
    MCP_HOST         - Server host (default: 127.0.0.1)
    MCP_AUTH_TOKEN   - Authentication token (REQUIRED in production)
    LOG_LEVEL        - Logging level (default: INFO)
    ENVIRONMENT      - Deployment environment (local/staging/production)

See Also:
    - .env.example for all available configuration options
    - server/logger.py for logging configuration
    - server/auth.py for authentication using MCP_AUTH_TOKEN
"""

from __future__ import annotations

import logging
import os
import secrets
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Self

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import shared constants for consistency
from reportalin.core.constants import (
    DATA_DICTIONARY_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TRANSPORT,
    ENCRYPTED_LOGS_PATH,
    MIN_K_ANONYMITY,
)

# =============================================================================
# Data Dictionary Path Constants
# =============================================================================
# Path configuration for the data dictionary pipeline


def _get_project_root_for_paths() -> str:
    """Get project root for path constants during module initialization."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return str(parent)
    return str(current.parent.parent.parent)


# Initialize path constants
ROOT_DIR = _get_project_root_for_paths()
DATA_DIR = os.path.join(ROOT_DIR, "data")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")
DICTIONARY_EXCEL_FILE = os.path.join(
    DATA_DIR,
    "data_dictionary_and_mapping_specifications",
    "RePORT_DEB_to_Tables_mapping.xlsx",
)
DICTIONARY_JSON_OUTPUT_DIR = os.path.join(RESULTS_DIR, "data_dictionary_mappings")

# Logging defaults
LOG_LEVEL = logging.INFO
LOG_NAME = "reportalin-mcp"


def ensure_directories() -> None:
    """Create necessary directories if they don't exist."""
    directories = [RESULTS_DIR, DICTIONARY_JSON_OUTPUT_DIR]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def validate_config() -> list[str]:
    """Validate configuration and return list of warnings."""
    warnings = []
    try:
        if not os.path.exists(DATA_DIR):
            warnings.append(f"Data directory not found: {DATA_DIR}")
        if not os.path.exists(DICTIONARY_EXCEL_FILE):
            warnings.append(f"Data dictionary file not found: {DICTIONARY_EXCEL_FILE}")
    except (OSError, PermissionError) as e:
        warnings.append(f"Error validating configuration: {e}")
    return warnings


# =============================================================================
# Enums
# =============================================================================


class Environment(str, Enum):
    """
    Deployment environment enumeration.

    Affects logging format, validation strictness, and security defaults.
    """

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        """Check if this is a production-like environment."""
        return self in (Environment.PRODUCTION, Environment.STAGING)

    @property
    def is_local(self) -> bool:
        """Check if this is a local development environment."""
        return self in (Environment.LOCAL, Environment.DEVELOPMENT)


class LogLevel(str, Enum):
    """
    Log level enumeration.

    Maps to standard Python logging levels.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# =============================================================================
# Settings Class
# =============================================================================


def get_project_root() -> Path:
    """
    Get the project root directory.

    Traverses up from this file to find the directory containing pyproject.toml.

    Returns:
        Path to project root directory

    Raises:
        RuntimeError: If project root cannot be determined
    """
    current = Path(__file__).resolve().parent

    # Traverse up looking for pyproject.toml
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    # Fallback to parent of server/ directory
    return current.parent


class Settings(BaseSettings):
    """
    Application settings with environment variable binding.

    This class provides type-safe access to all configuration values.
    Values are loaded from environment variables and .env files.

    Attributes:
        environment: Deployment environment (local/staging/production)
        log_level: Logging verbosity level
        mcp_host: Server bind host
        mcp_port: Server bind port
        mcp_auth_token: Authentication token for API access
        mcp_transport: Transport protocol (stdio/http/sse)
        privacy_mode: Privacy enforcement level (strict/standard)

    Example:
        >>> settings = Settings()  # Loads from environment
        >>> settings.mcp_port
        8000
    """

    model_config = SettingsConfigDict(
        # Load from .env file in project root
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow extra fields (forward compatibility)
        extra="ignore",
        # Case-insensitive environment variables
        case_sensitive=False,
        # Freeze after creation (immutable)
        frozen=True,
        # Validate default values
        validate_default=True,
    )

    # ==========================================================================
    # Environment & Logging
    # ==========================================================================

    environment: Environment = Field(
        default=Environment.LOCAL,
        description="Deployment environment (affects logging and validation)",
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging verbosity level",
    )

    log_format: str = Field(
        default="auto",
        description="Log format: 'json', 'pretty', or 'auto' (based on environment)",
    )

    # ==========================================================================
    # Server Configuration
    # ==========================================================================

    mcp_host: str = Field(
        default=DEFAULT_HOST,
        description="Server bind host (use 0.0.0.0 for external access)",
    )

    mcp_port: Annotated[int, Field(ge=1, le=65535)] = Field(
        default=DEFAULT_PORT,
        description="Server bind port",
    )

    mcp_transport: str = Field(
        default=DEFAULT_TRANSPORT,
        description="MCP transport protocol: stdio, http, or sse",
    )

    # ==========================================================================
    # Security Configuration
    # ==========================================================================

    mcp_auth_token: SecretStr | None = Field(
        default=None,
        description="Authentication token for API access (REQUIRED in production)",
    )

    mcp_auth_enabled: bool = Field(
        default=True,
        description="Enable authentication (should always be True in production)",
    )

    cors_allowed_origins: list[str] = Field(
        default_factory=list,
        description="List of allowed CORS origins (empty = none allowed in production)",
    )

    # ==========================================================================
    # Privacy Configuration
    # ==========================================================================

    privacy_mode: str = Field(
        default="strict",
        description="Privacy enforcement: 'strict' or 'standard'",
    )

    min_k_anonymity: Annotated[int, Field(ge=1)] = Field(
        default=MIN_K_ANONYMITY,
        description="Minimum k-anonymity threshold for aggregate statistics",
    )

    # ==========================================================================
    # Paths Configuration
    # ==========================================================================

    data_dictionary_path: str = Field(
        default=DATA_DICTIONARY_PATH,
        description="Path to data dictionary JSONL files (relative to project root)",
    )

    encrypted_logs_path: str = Field(
        default=ENCRYPTED_LOGS_PATH,
        description="Path to encrypted audit logs (relative to project root)",
    )

    # ==========================================================================
    # Rate Limiting Configuration
    # ==========================================================================

    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable request rate limiting",
    )

    rate_limit_requests_per_minute: Annotated[int, Field(ge=1, le=10000)] = Field(
        default=60,
        description="Maximum requests per minute per client",
    )

    rate_limit_requests_per_second: Annotated[int, Field(ge=1, le=1000)] = Field(
        default=10,
        description="Maximum requests per second per client (burst limit)",
    )

    rate_limit_burst_size: Annotated[int, Field(ge=1, le=1000)] = Field(
        default=20,
        description="Maximum burst size for rate limiting",
    )

    # ==========================================================================
    # Security Headers Configuration
    # ==========================================================================

    security_headers_enabled: bool = Field(
        default=True,
        description="Enable security headers middleware",
    )

    input_validation_enabled: bool = Field(
        default=True,
        description="Enable input validation middleware",
    )

    max_query_param_length: Annotated[int, Field(ge=256, le=65536)] = Field(
        default=2048,
        description="Maximum length of a single query parameter in bytes",
    )

    max_query_string_length: Annotated[int, Field(ge=1024, le=131072)] = Field(
        default=8192,
        description="Maximum total query string length in bytes",
    )

    # ==========================================================================
    # Secrets Rotation Configuration
    # ==========================================================================

    mcp_auth_token_previous: SecretStr | None = Field(
        default=None,
        description="Previous auth token during rotation (valid for grace period)",
    )

    secret_rotation_grace_period_hours: Annotated[int, Field(ge=1, le=168)] = Field(
        default=24,
        description="Hours that previous token remains valid after rotation",
    )

    # ==========================================================================
    # Validators
    # ==========================================================================

    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        """Validate transport is one of the supported types.

        Returns:
            Lowercase transport string.

        Raises:
            ValueError: If transport is not stdio, http, or sse.
        """
        allowed = {"stdio", "http", "sse"}
        if v.lower() not in allowed:
            raise ValueError(f"mcp_transport must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("privacy_mode")
    @classmethod
    def validate_privacy_mode(cls, v: str) -> str:
        """Validate privacy mode is one of the supported types.

        Returns:
            Lowercase privacy mode string.

        Raises:
            ValueError: If privacy mode is not strict or standard.
        """
        allowed = {"strict", "standard"}
        if v.lower() not in allowed:
            raise ValueError(f"privacy_mode must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format is one of the supported types.

        Returns:
            Lowercase log format string.

        Raises:
            ValueError: If log format is not json, pretty, or auto.
        """
        allowed = {"json", "pretty", "auto"}
        if v.lower() not in allowed:
            raise ValueError(f"log_format must be one of {allowed}, got '{v}'")
        return v.lower()

    @model_validator(mode="after")
    def validate_production_requirements(self) -> Self:
        """
        Validate that production environments have required security settings.

        In production, we MUST have:
        - An authentication token set
        - Authentication enabled
        - Strict privacy mode

        Raises:
            ValueError: If production requirements are not met
        """
        if self.environment.is_production:
            # Auth token is REQUIRED in production
            if self.mcp_auth_token is None:
                raise ValueError(
                    "MCP_AUTH_TOKEN is REQUIRED in production environments. "
                    "Set the environment variable or add it to your .env file."
                )

            # Warn if auth is disabled (but don't fail - might be behind proxy)
            if not self.mcp_auth_enabled:
                import warnings

                warnings.warn(
                    "Authentication is disabled in a production environment. "
                    "Ensure the server is behind an authenticating proxy.",
                    UserWarning,
                    stacklevel=2,
                )

            # Enforce strict privacy in production
            if self.privacy_mode != "strict":
                raise ValueError(
                    "privacy_mode must be 'strict' in production environments "
                    "to ensure DPDPA/HIPAA compliance."
                )

        return self

    # ==========================================================================
    # Computed Properties
    # ==========================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in a production-like environment."""
        return self.environment.is_production

    @property
    def is_local(self) -> bool:
        """Check if running in a local development environment."""
        return self.environment.is_local

    @property
    def effective_log_format(self) -> str:
        """
        Get the effective log format based on configuration.

        If log_format is 'auto', determines format based on environment:
        - Local/Development: 'pretty' (colored, human-readable)
        - Staging/Production: 'json' (structured, machine-parseable)
        """
        if self.log_format == "auto":
            return "pretty" if self.is_local else "json"
        return self.log_format

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return get_project_root()

    @property
    def data_dictionary_dir(self) -> Path:
        """Get the absolute path to data dictionary directory."""
        return self.project_root / self.data_dictionary_path

    @property
    def encrypted_logs_dir(self) -> Path:
        """Get the absolute path to encrypted logs directory."""
        return self.project_root / self.encrypted_logs_path

    def get_auth_token(self) -> str | None:
        """
        Get the authentication token value.

        Returns:
            The token string, or None if not set

        Note:
            Use this method sparingly. The token should only be accessed
            for comparison in the auth middleware.
        """
        if self.mcp_auth_token is None:
            return None
        return self.mcp_auth_token.get_secret_value()

    def generate_dev_token(self) -> str:
        """
        Generate a secure random token for development.

        Returns:
            A 32-character hex token

        Note:
            Only use this in local/development environments.
            Production should use externally managed secrets.
        """
        if self.is_production:
            raise RuntimeError("Cannot generate tokens in production")
        return secrets.token_hex(16)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings singleton.

    Uses LRU cache to ensure settings are only loaded once per process.
    The cache can be cleared with `get_settings.cache_clear()` if needed
    (useful for testing).

    Returns:
        Validated Settings instance

    Example:
        >>> settings = get_settings()
        >>> settings.mcp_port
        8000
    """
    return Settings()


def reload_settings() -> Settings:
    """
    Reload settings from environment.

    Clears the settings cache and returns fresh settings.
    Primarily useful for testing.

    Returns:
        Fresh Settings instance
    """
    get_settings.cache_clear()
    return get_settings()
