"""Tests for config module - minimal."""

from pathlib import Path

from reportalin.core import config


class TestConfigPaths:
    """Test configuration path constants."""

    def test_root_dir_exists(self) -> None:
        """ROOT_DIR should be a valid directory."""
        assert Path(config.ROOT_DIR).is_dir()

    def test_data_dir_path(self) -> None:
        """DATA_DIR should be under ROOT_DIR."""
        assert config.DATA_DIR.startswith(config.ROOT_DIR)
        assert config.DATA_DIR.endswith("data")

    def test_results_dir_path(self) -> None:
        """RESULTS_DIR should be under ROOT_DIR."""
        assert config.RESULTS_DIR.startswith(config.ROOT_DIR)
        assert config.RESULTS_DIR.endswith("results")


class TestSettings:
    """Test Settings class."""

    def test_get_settings(self) -> None:
        """Test settings singleton."""
        from reportalin.core.config import get_settings

        settings = get_settings()
        assert settings.mcp_host == "127.0.0.1"
        assert settings.mcp_port == 8000
        assert settings.mcp_transport == "stdio"
