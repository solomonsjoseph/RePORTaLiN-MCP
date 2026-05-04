"""
Tests for config module.

Tests configuration loading, path resolution, and validation.
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


class TestDatasetDetection:
    """Test dataset folder detection."""

    def test_normalize_dataset_name_with_suffix(self) -> None:
        """Should remove common suffixes from dataset names."""
        assert config.normalize_dataset_name("test_csv_files") == "test"
        assert config.normalize_dataset_name("test_files") == "test"

    def test_normalize_dataset_name_without_suffix(self) -> None:
        """Should preserve names without suffixes."""
        assert config.normalize_dataset_name("test_dataset") == "test_dataset"

    def test_normalize_dataset_name_empty(self) -> None:
        """Should return default for empty input."""
        assert config.normalize_dataset_name(None) == config.DEFAULT_DATASET_NAME
        assert config.normalize_dataset_name("") == config.DEFAULT_DATASET_NAME
        assert config.normalize_dataset_name("  ") == config.DEFAULT_DATASET_NAME


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_returns_list(self) -> None:
        """validate_config should return a list."""
        warnings = config.validate_config()
        assert isinstance(warnings, list)

    def test_ensure_directories_creates_dirs(self, tmp_path: Path) -> None:
        """ensure_directories should create necessary directories."""
        # This test just verifies the function runs without error
        # In production, it creates the actual directories
        config.ensure_directories()


class TestExportedAPI:
    """Test that all exported symbols are accessible."""

    def test_all_exports_exist(self) -> None:
        """All items in __all__ should be accessible."""
        for name in config.__all__:
            assert hasattr(config, name), f"Missing export: {name}"
