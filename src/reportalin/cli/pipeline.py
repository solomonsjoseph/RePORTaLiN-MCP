#!/usr/bin/env python3
"""
RePORTaLiN Data Dictionary Pipeline.

Simplified pipeline for loading the data dictionary into JSONL format
for use by the MCP search tool.

Public API:
    - ``main``: Main pipeline entry point
    - ``run_step``: Pipeline step executor with error handling

Pipeline Steps:
    Step 1: Data Dictionary Loading
        - Processes Excel data dictionary file
        - Splits multi-table sheets automatically
        - Outputs JSONL format with metadata to results/data_dictionary_mappings/

See Also:
    - :mod:`reportalin.data.load_dictionary` - Data dictionary processing
    - :mod:`reportalin.server.tools.search` - MCP search tool using the data
"""

import argparse
import logging
import sys
from collections.abc import Callable
from typing import Any

from reportalin import __version__
from reportalin.core import config
from reportalin.data.load_dictionary import load_study_dictionary

try:
    import argcomplete

    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False

__all__ = ["main", "run_step"]


def run_step(step_name: str, func: Callable[[], Any]) -> Any:
    """
    Execute pipeline step with error handling and logging.

    Args:
        step_name: Name of the pipeline step
        func: Callable function to execute

    Returns:
        Result from the function, or exits with code 1 on error
    """
    try:
        logging.info(f"--- {step_name} ---")
        result = func()

        # Check if result indicates failure
        if isinstance(result, bool) and not result:
            logging.error(f"{step_name} failed.")
            sys.exit(1)
        elif isinstance(result, dict) and result.get("errors"):
            logging.error(f"{step_name} completed with {len(result['errors'])} errors.")
            sys.exit(1)

        logging.info(f"{step_name} completed successfully.")
        return result
    except Exception as e:
        logging.error(f"Error in {step_name}: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """
    Main pipeline for loading data dictionary.

    Command-line Arguments:
        -v, --verbose: Enable verbose (DEBUG level) logging
    """
    parser = argparse.ArgumentParser(
        prog="RePORTaLiN-Pipeline",
        description="Load data dictionary for the MCP search tool.",
        epilog="""
Examples:
  %(prog)s                  # Run dictionary loading
  %(prog)s --verbose        # Run with debug logging

For detailed documentation, see the README.md
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging with detailed context",
    )

    # Enable shell completion if available
    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    # Set log level
    log_level = logging.DEBUG if args.verbose else config.LOG_LEVEL

    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("Starting RePORTaLiN data dictionary pipeline...")

    # Validate configuration and warn about missing files
    config_warnings = config.validate_config()
    if config_warnings:
        for warning in config_warnings:
            logging.warning(warning)

    # Ensure required directories exist
    config.ensure_directories()

    # Display startup banner
    print("\n" + "=" * 70)
    print("RePORTaLiN - Data Dictionary Pipeline")
    print("=" * 70 + "\n")

    # Load data dictionary
    run_step(
        "Step 1: Loading Data Dictionary",
        lambda: load_study_dictionary(
            file_path=config.DICTIONARY_EXCEL_FILE,
            json_output_dir=config.DICTIONARY_JSON_OUTPUT_DIR,
        ),
    )

    logging.info("Data dictionary pipeline finished.")
    logging.info(f"Output: {config.DICTIONARY_JSON_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
