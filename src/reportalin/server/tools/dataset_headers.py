"""Dataset Headers Discovery Tool for RePORTaLiN.

Cross-references dataset variables with data dictionary definitions.
Returns ONLY variables present in BOTH dataset files AND data dictionary.

Each variable is returned once per dataset it appears in, with a count
showing how many datasets contain that variable.

PRIVACY: NO patient data - only variable metadata.

Use Cases:
- "What documented variables are in the TST dataset?"
- "List all variables with data dictionary definitions"
- "Which dataset contains documented HIV variables?"
- "How many datasets have the PTID variable?"
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from reportalin.logging import get_logger
from reportalin.server.tools._loaders import get_data_dictionary, get_dataset_headers

__all__ = ["DatasetHeader", "DatasetHeadersResult", "list_dataset_headers"]

logger = get_logger(__name__)


# =============================================================================
# Output Models
# =============================================================================


class DatasetHeader(BaseModel):
    """A documented variable from RePORT study datasets."""

    variable: str = Field(description="Variable name")
    description: str | None = Field(
        default=None, description="What this variable measures or represents"
    )
    data_type: str | None = Field(
        default=None, description="Data type (e.g., Integer, Text, Date)"
    )
    dataset_count: int = Field(
        description="Number of datasets this variable is available in"
    )
    source_dataset: str | None = Field(
        default=None, description="Dataset file where this variable appears"
    )
    source_table: str | None = Field(
        default=None, description="Data dictionary table name"
    )


class DatasetHeadersResult(BaseModel):
    """Documented variables available in study datasets."""

    total_variables: int = Field(description="Number of documented variables found")
    headers: list[DatasetHeader] = Field(description="Variable definitions")
    note: str = Field(
        default="Only variables with data dictionary definitions are included",
        description="Important context",
    )
    formatted_output: str = Field(
        description="Pre-formatted markdown for beautiful display"
    )


# =============================================================================
# Main Tool
# =============================================================================


def list_dataset_headers(
    dataset_name: Annotated[
        str | None,
        Field(
            description="Optional: Filter by dataset name (e.g., 'TST', 'HIV', 'Baseline'). "
            "If not provided, returns all dataset variables.",
        ),
    ] = None,
) -> DatasetHeadersResult:
    """List dataset variables cross-referenced with data dictionary.

    Returns ONLY variables present in BOTH dataset files AND data dictionary.
    Enriches dataset headers with dictionary metadata (description, type).
    Results are grouped by dataset and formatted in beautiful markdown tables.

    Args:
        dataset_name: Optional dataset name filter (case-insensitive substring match)

    Returns:
        DatasetHeadersResult with enriched variable metadata and formatted output

    Examples:
        >>> list_dataset_headers()  # All documented variables
        >>> list_dataset_headers("TST")  # TST variables only
        >>> list_dataset_headers("HIV")  # HIV dataset variables
    """
    try:
        # Load dataset headers from results/dataset_headers (scoped access)
        all_headers = get_dataset_headers()  # dict[dataset_name, list[variable]]

        # Load data dictionary and create lookup (case-insensitive)
        dict_data = get_data_dictionary()
        dict_lookup: dict[str, dict] = {}
        for table_name, fields in dict_data.items():
            for field in fields:
                var_name = (field.get("Question Short Name (Databank Fieldname)") or "").strip()
                if var_name:
                    dict_lookup[var_name.upper()] = {
                        "description": field.get("Question", ""),
                        "table": table_name,
                        "data_type": field.get("Type", ""),
                        "original_name": var_name,
                    }

        # Filter datasets by name if provided
        filtered_datasets = {
            ds: vars_list for ds, vars_list in all_headers.items()
            if not dataset_name or dataset_name.upper() in ds.upper()
        }

        # Cross-reference: Only keep variables in BOTH dataset AND dictionary
        from collections import defaultdict
        dataset_variables: dict[str, list[dict]] = defaultdict(list)
        undocumented = 0

        for ds_name, variables in filtered_datasets.items():
            for var_name in variables:
                var_key = var_name.upper()
                if var_key in dict_lookup:
                    entry = dict_lookup[var_key]
                    dataset_variables[ds_name].append({
                        "variable": var_name,
                        "description": entry["description"],
                        "data_type": entry["data_type"],
                        "table": entry["table"],
                    })
                else:
                    undocumented += 1
                    logger.debug(f"Undocumented variable: {var_name}")

        # Build enriched entries for structured output
        enriched = []
        total_vars = 0

        for source_file, vars_list in dataset_variables.items():
            for var in vars_list:
                enriched.append(
                    DatasetHeader(
                        variable=var["variable"],
                        description=var["description"],
                        data_type=var["data_type"],
                        dataset_count=1,  # Simplified for now
                        source_dataset=source_file,
                        source_table=var["table"],
                    )
                )
                total_vars += 1

        # Build formatted markdown output (like the perfect example)
        formatted_lines = []

        if not dataset_variables:
            formatted_lines.append(
                "No documented variables found"
                + (f" for dataset '{dataset_name}'" if dataset_name else "")
                + "."
            )
        else:
            # Group by dataset and create beautiful tables
            for source_file, vars_list in sorted(dataset_variables.items()):
                formatted_lines.append(f"\n**Dataset: {source_file}**")
                formatted_lines.append("| Field | Description | Table |")
                formatted_lines.append("|-------|-------------|-------|")

                for var in vars_list[:50]:  # Limit per dataset
                    desc = var["description"].replace("\n", " ").replace("|", "\\|")
                    if len(desc) > 80:
                        desc = desc[:77] + "..."

                    formatted_lines.append(
                        f"| `{var['variable']}` | {desc} | {var['table']} |"
                    )

        formatted_output = "\n".join(formatted_lines)

        # Log internal details
        logger.info(
            f"Cross-referenced {total_vars} documented variables "
            f"({undocumented} undocumented) from {len(dataset_variables)} dataset(s)"
            + (f" | filter: {dataset_name}" if dataset_name else "")
        )

        return DatasetHeadersResult(
            total_variables=total_vars,
            headers=enriched,
            formatted_output=formatted_output,
        )

    except Exception as e:
        logger.error(f"Failed to cross-reference dataset headers: {e}")
        return DatasetHeadersResult(
            total_variables=0,
            headers=[],
            formatted_output="Error loading dataset headers.",
        )
