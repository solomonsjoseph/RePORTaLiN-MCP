"""Data loading utilities for MCP tools.

This module provides functions to load and cache data from:
- Data dictionary JSONL files (preferred)
- Excel files as fallback (requires optional data-prep dependencies)
- Codelist definitions

Note: Dataset loading removed in v3.0 - focus is data dictionary only.

Excel Fallback:
If JSONL files don't exist, attempts to load from source Excel file.
Requires optional dependencies: uv pip install reportalin-mcp[data-prep]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reportalin.logging import get_logger

__all__ = [
    "DATA_DICTIONARY_PATH",
    "EXCEL_SOURCE_PATH",
    "load_data_dictionary",
    "load_codelists",
    "get_data_dictionary",
    "get_codelists",
]

# Initialize logger
logger = get_logger(__name__)

# =============================================================================
# Path Configuration
# =============================================================================

# __file__ is at: src/reportalin/server/tools/_loaders.py
# Project root is 4 levels up: ../../../../
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
DATA_DICTIONARY_PATH = PROJECT_ROOT / "results" / "data_dictionary_mappings"
EXCEL_SOURCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "data_dictionary_and_mapping_specifications"
    / "RePORT_DEB_to_Tables_mapping.xlsx"
)


# =============================================================================
# Excel Fallback (Optional)
# =============================================================================


def _load_from_excel_fallback() -> dict[str, list[dict]]:
    """Load data dictionary from Excel source file as fallback.

    This function attempts to generate JSONL files from the Excel source
    if they don't already exist. Requires optional data-prep dependencies.

    Returns:
        Dictionary mapping table names to field definitions.
        Empty dict if Excel source doesn't exist or dependencies missing.
    """
    if not EXCEL_SOURCE_PATH.exists():
        logger.warning(
            f"Excel source file not found: {EXCEL_SOURCE_PATH}. "
            "Cannot generate JSONL files."
        )
        return {}

    try:
        # Try importing the load_dictionary module (requires pandas/openpyxl)
        from reportalin.data.load_dictionary import load_study_dictionary

        logger.info(
            "JSONL files not found. Generating from Excel source "
            f"(requires data-prep dependencies): {EXCEL_SOURCE_PATH}"
        )

        # Generate JSONL files from Excel
        load_study_dictionary(
            file_path=str(EXCEL_SOURCE_PATH),
            json_output_dir=str(DATA_DICTIONARY_PATH),
        )

        # Now load the generated JSONL files
        return load_data_dictionary()

    except ImportError as e:
        logger.error(
            "Excel fallback failed: Missing optional dependencies. "
            "Install with: uv pip install reportalin-mcp[data-prep]\n"
            f"Error: {e}"
        )
        return {}
    except Exception as e:
        logger.error(f"Excel fallback failed: {e}")
        return {}


# =============================================================================
# Data Loading Functions
# =============================================================================


def load_data_dictionary() -> dict[str, list[dict]]:
    """Load all data dictionary JSONL files with Excel fallback.

    Tries to load from JSONL files first (fast, no dependencies).
    If JSONL files don't exist, attempts Excel fallback (requires data-prep deps).

    Returns:
        Dictionary mapping table names to lists of field definition records.
        Empty dict if no data sources available.
    """
    all_data: dict[str, list[dict]] = {}

    # Try loading from JSONL files first (preferred)
    if not DATA_DICTIONARY_PATH.exists():
        logger.warning(f"Data dictionary path not found: {DATA_DICTIONARY_PATH}")
        # Try Excel fallback
        return _load_from_excel_fallback()

    for jsonl_file in DATA_DICTIONARY_PATH.rglob("*.jsonl"):
        table_name = jsonl_file.stem
        records = []

        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            all_data[table_name] = records
        except Exception as e:
            logger.error(f"Error loading {jsonl_file}: {e}")

    # If no data was loaded from JSONL, try Excel fallback
    if not all_data:
        logger.info("No JSONL files found. Attempting Excel fallback...")
        return _load_from_excel_fallback()

    return all_data


def load_codelists() -> dict[str, list[dict]]:
    """Load all codelist definitions.

    Returns:
        Dictionary mapping codelist names to lists of code/descriptor records.
        Empty dict if codelist path doesn't exist.
    """
    codelists: dict[str, list[dict]] = {}
    codelist_path = DATA_DICTIONARY_PATH / "Codelists"

    if not codelist_path.exists():
        return codelists

    for jsonl_file in codelist_path.glob("*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        # Handle both field name formats
                        codelist_name = (
                            record.get("Codelist")
                            or record.get("New codelists")
                            or "UNKNOWN"
                        )
                        if codelist_name not in codelists:
                            codelists[codelist_name] = []
                        codelists[codelist_name].append(record)
        except Exception as e:
            logger.error(f"Error loading codelist {jsonl_file}: {e}")

    return codelists


# =============================================================================
# Cache
# =============================================================================

_dict_cache: dict[str, list[dict]] | None = None
_codelist_cache: dict[str, list[dict]] | None = None


def get_data_dictionary() -> dict[str, list[dict]]:
    """Get cached data dictionary.

    Returns:
        Dictionary mapping table names to field definitions.
    """
    global _dict_cache
    if _dict_cache is None:
        _dict_cache = load_data_dictionary()
    return _dict_cache


def get_codelists() -> dict[str, list[dict]]:
    """Get cached codelists.

    Returns:
        Dictionary mapping codelist names to code/descriptor records.
    """
    global _codelist_cache
    if _codelist_cache is None:
        _codelist_cache = load_codelists()
    return _codelist_cache
