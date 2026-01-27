"""Data loading utilities for MCP tools.

Provides cached loaders for:
- Data dictionary (search tool)
- Codelists (search tool)
- Dataset headers (dataset_headers tool)
- Unified results (combined_search tool)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from reportalin.logging import get_logger

__all__ = [
    "get_all_results",
    "get_codelists",
    "get_data_dictionary",
    "get_dataset_headers",
]

logger = get_logger(__name__)

# =============================================================================
# Path Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
DATA_DICTIONARY_PATH = PROJECT_ROOT / "results" / "data_dictionary_mappings"
DATASET_HEADERS_PATH = PROJECT_ROOT / "results" / "dataset_headers"
EXCEL_SOURCE_PATH = (
    PROJECT_ROOT / "data" / "data_dictionary_and_mapping_specifications"
    / "RePORT_DEB_to_Tables_mapping.xlsx"
)


# =============================================================================
# Type Definitions
# =============================================================================


class UnifiedResults(TypedDict):
    """All data from results folder for combined_search."""

    data_dictionary: dict[str, list[dict]]
    codelists: dict[str, list[dict]]
    dataset_headers: dict[str, list[str]]


# =============================================================================
# Internal Loaders
# =============================================================================


def _load_from_excel_fallback() -> dict[str, list[dict]]:
    """Load data dictionary from Excel if JSONL missing. No recursion."""
    if not EXCEL_SOURCE_PATH.exists():
        logger.warning(f"Excel source not found: {EXCEL_SOURCE_PATH}")
        return {}

    try:
        from reportalin.data.load_dictionary import load_study_dictionary

        logger.info(f"Generating JSONL from Excel: {EXCEL_SOURCE_PATH}")
        load_study_dictionary(
            file_path=str(EXCEL_SOURCE_PATH),
            json_output_dir=str(DATA_DICTIONARY_PATH),
        )
        # Load directly with recursive glob (files are in subdirs)
        all_data: dict[str, list[dict]] = {}
        for jsonl_file in DATA_DICTIONARY_PATH.glob("**/*.jsonl"):
            if "Codelists" in str(jsonl_file) or "extraas" in str(jsonl_file):
                continue
            if records := _load_jsonl(jsonl_file):
                all_data[jsonl_file.stem] = records
        return all_data
    except ImportError as e:
        logger.error(f"Excel fallback failed (missing deps): {e}")
        return {}
    except Exception as e:
        logger.error(f"Excel fallback failed: {e}")
        return {}


def _load_jsonl(path: Path) -> list[dict]:
    """Load records from a JSONL file."""
    records = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line := line.strip():
                    records.append(json.loads(line))
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
    return records


def _load_data_dictionary() -> dict[str, list[dict]]:
    """Load all data dictionary JSONL files (recursive search in subdirs)."""
    if not DATA_DICTIONARY_PATH.exists():
        logger.warning(f"Data dictionary path not found: {DATA_DICTIONARY_PATH}")
        return _load_from_excel_fallback()

    all_data: dict[str, list[dict]] = {}
    # JSONL files are in subdirectories like tblMED/tblMED_table.jsonl
    for jsonl_file in DATA_DICTIONARY_PATH.glob("**/*.jsonl"):
        # Skip Codelists (loaded separately) and extraas
        if "Codelists" in str(jsonl_file) or "extraas" in str(jsonl_file):
            continue
        if records := _load_jsonl(jsonl_file):
            all_data[jsonl_file.stem] = records

    return all_data if all_data else _load_from_excel_fallback()


def _load_codelists() -> dict[str, list[dict]]:
    """Load all codelist definitions."""
    codelists: dict[str, list[dict]] = {}
    codelist_path = DATA_DICTIONARY_PATH / "Codelists"

    if not codelist_path.exists():
        return codelists

    for jsonl_file in codelist_path.glob("*.jsonl"):
        for record in _load_jsonl(jsonl_file):
            name = record.get("Codelist") or record.get("New codelists") or "UNKNOWN"
            codelists.setdefault(name, []).append(record)

    return codelists


def _load_dataset_headers() -> dict[str, list[str]]:
    """Load all dataset headers from JSONL files."""
    if not DATASET_HEADERS_PATH.exists():
        logger.warning(f"Dataset headers path not found: {DATASET_HEADERS_PATH}")
        return {}

    all_headers: dict[str, list[str]] = {}
    for jsonl_file in DATASET_HEADERS_PATH.glob("*_headers.jsonl"):
        dataset_name = jsonl_file.stem.replace("_headers", "")
        variables = [r["variable"] for r in _load_jsonl(jsonl_file) if r.get("variable")]
        if variables:
            all_headers[dataset_name] = variables

    return all_headers


# =============================================================================
# Public Cached Getters
# =============================================================================

_dict_cache: dict[str, list[dict]] | None = None
_codelist_cache: dict[str, list[dict]] | None = None
_headers_cache: dict[str, list[str]] | None = None
_unified_cache: UnifiedResults | None = None


def get_data_dictionary() -> dict[str, list[dict]]:
    """Get cached data dictionary (for search tool)."""
    global _dict_cache
    if _dict_cache is None:
        _dict_cache = _load_data_dictionary()
    return _dict_cache


def get_codelists() -> dict[str, list[dict]]:
    """Get cached codelists (for search tool)."""
    global _codelist_cache
    if _codelist_cache is None:
        _codelist_cache = _load_codelists()
    return _codelist_cache


def get_dataset_headers() -> dict[str, list[str]]:
    """Get cached dataset headers (for dataset_headers tool)."""
    global _headers_cache
    if _headers_cache is None:
        _headers_cache = _load_dataset_headers()
    return _headers_cache


def get_all_results() -> UnifiedResults:
    """Get cached unified results (for combined_search tool)."""
    global _unified_cache
    if _unified_cache is None:
        _unified_cache = UnifiedResults(
            data_dictionary=get_data_dictionary(),
            codelists=get_codelists(),
            dataset_headers=get_dataset_headers(),
        )
    return _unified_cache
