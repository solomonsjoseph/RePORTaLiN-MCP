"""Server Configuration - Minimal.

Pydantic Settings for the 3-tool MCP server.
Only settings that are actually used.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from reportalin.core.constants import (
    DATA_DICTIONARY_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TRANSPORT,
)

__all__ = ["Environment", "LogLevel", "Settings", "get_settings", "reload_settings"]

# Path constants for data extraction
ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
DATA_DIR = str(Path(ROOT_DIR) / "data")
RESULTS_DIR = str(Path(ROOT_DIR) / "results")
DICTIONARY_EXCEL_FILE = str(
    Path(DATA_DIR)
    / "data_dictionary_and_mapping_specifications"
    / "RePORT_DEB_to_Tables_mapping.xlsx"
)
DICTIONARY_JSON_OUTPUT_DIR = str(Path(RESULTS_DIR) / "data_dictionary_mappings")


class Environment(str, Enum):
    """Deployment environment."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        return self in (Environment.PRODUCTION, Environment.STAGING)

    @property
    def is_local(self) -> bool:
        return self in (Environment.LOCAL, Environment.DEVELOPMENT)


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Minimal settings for RePORTaLiN MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
        validate_default=True,
    )

    # Environment & Logging
    environment: Environment = Field(default=Environment.LOCAL)
    log_level: LogLevel = Field(default=LogLevel.INFO)

    # Server Configuration
    mcp_host: str = Field(default=DEFAULT_HOST)
    mcp_port: int = Field(default=DEFAULT_PORT, ge=1, le=65535)
    mcp_transport: str = Field(default=DEFAULT_TRANSPORT)

    # Paths
    data_dictionary_path: str = Field(default=DATA_DICTIONARY_PATH)

    @property
    def is_production(self) -> bool:
        return self.environment.is_production

    @property
    def is_local(self) -> bool:
        return self.environment.is_local

    @property
    def project_root(self) -> Path:
        current = Path(__file__).resolve().parent
        for parent in [current, *current.parents]:
            if (parent / "pyproject.toml").exists():
                return parent
        return current.parent.parent


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()


def reload_settings() -> Settings:
    """Reload settings (for testing)."""
    get_settings.cache_clear()
    return get_settings()
