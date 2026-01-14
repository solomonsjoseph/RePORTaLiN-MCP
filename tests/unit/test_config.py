"""
Tests for config module.

Minimal tests for configuration loading and validation.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reportalin.core import config


class TestConfigPaths:
    """Test configuration path constants."""

    def test_root_dir_exists(self) -> None:
        """ROOT_DIR should be a valid directory."""
        assert os.path.isdir(config.ROOT_DIR)

    def test_data_dir_path(self) -> None:
        """DATA_DIR should be under ROOT_DIR."""
        assert config.DATA_DIR.startswith(config.ROOT_DIR)
        assert config.DATA_DIR.endswith("data")

    def test_results_dir_path(self) -> None:
        """RESULTS_DIR should be under ROOT_DIR."""
        assert config.RESULTS_DIR.startswith(config.ROOT_DIR)
        assert config.RESULTS_DIR.endswith("results")


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_returns_list(self) -> None:
        """validate_config should return a list."""
        warnings = config.validate_config()
        assert isinstance(warnings, list)

    def test_ensure_directories_creates_dirs(self, tmp_path: Path) -> None:
        """ensure_directories should create necessary directories."""
        # This test just verifies the function runs without error
        config.ensure_directories()
