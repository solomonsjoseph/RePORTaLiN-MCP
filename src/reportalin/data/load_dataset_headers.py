"""Dataset Headers Extraction Module.

Extracts ONLY variable names from RePORT study datasets.
Does NOT include dataset values or descriptions - only raw column headers.

Output: JSONL files with {variable, source_file}
Note: Descriptions are added later by cross-referencing with data dictionary.
"""

from __future__ import annotations

__all__ = ["extract_dataset_headers", "load_all_dataset_headers"]

import json
from pathlib import Path

from reportalin.logging import get_logger

logger = get_logger(__name__)


def _get_project_root() -> Path:
    """Get project root by finding pyproject.toml."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent.parent.parent


PROJECT_ROOT = _get_project_root()
DATASET_DIR = PROJECT_ROOT / "data" / "dataset" / "Indo-vap_csv_files"
OUTPUT_DIR = PROJECT_ROOT / "results" / "dataset_headers"


def extract_dataset_headers(
    dataset_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Extract headers from all Excel datasets.

    Args:
        dataset_dir: Path to dataset folder (default: data/dataset/Indo-vap_csv_files)
        output_dir: Path to output folder (default: results/dataset_headers)

    Returns:
        Dictionary mapping source files to header metadata
    """
    dataset_path = Path(dataset_dir) if dataset_dir else DATASET_DIR
    output_path = Path(output_dir) if output_dir else OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    if not dataset_path.exists():
        logger.warning(f"Dataset directory not found: {dataset_path}")
        return {}

    try:
        import pandas as pd
    except ImportError:
        logger.error(
            "pandas required for dataset extraction. "
            "Install: uv pip install reportalin-mcp[data-prep]"
        )
        return {}

    results = {}
    xlsx_files = list(dataset_path.glob("*.xlsx"))

    logger.info(f"Found {len(xlsx_files)} dataset files")

    for file_path in xlsx_files:
        try:
            # Read only first row (headers) - no data
            df = pd.read_excel(file_path, nrows=0)
            headers = df.columns.tolist()

            file_data = [
                {
                    "variable": col,
                    "source_file": file_path.name,
                }
                for col in headers
            ]

            results[file_path.name] = file_data

            # Save to JSONL
            output_file = output_path / f"{file_path.stem}_headers.jsonl"
            with output_file.open("w") as f:
                for item in file_data:
                    f.write(json.dumps(item) + "\n")

            logger.debug(f"Extracted {len(headers)} headers from {file_path.name}")

        except Exception as e:
            logger.error(f"Failed to process {file_path.name}: {e}")
            continue

    logger.info(f"Extracted headers from {len(results)} files → {output_path}")
    return results


def load_all_dataset_headers(
    output_dir: Path | str | None = None,
) -> list[dict[str, str]]:
    """Load all dataset headers from JSONL files.

    Args:
        output_dir: Path to headers folder (default: results/dataset_headers)

    Returns:
        List of all header entries across all datasets
    """
    output_path = Path(output_dir) if output_dir else OUTPUT_DIR

    if not output_path.exists():
        logger.warning(f"Headers directory not found: {output_path}. Extracting now...")
        extract_dataset_headers()

    headers = []
    for jsonl_file in output_path.glob("*_headers.jsonl"):
        try:
            with jsonl_file.open() as f:
                for line in f:
                    headers.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to load {jsonl_file.name}: {e}")

    return headers


if __name__ == "__main__":
    # CLI execution: python -m reportalin.data.load_dataset_headers
    extract_dataset_headers()
