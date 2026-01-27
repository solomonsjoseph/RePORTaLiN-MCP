"""Combined Variable Discovery Tool for RePORTaLiN.

Intelligently searches across ALL data in the results folder:
1. Data dictionary mappings (variable definitions, types, tables)
2. Codelists (categorical value definitions)
3. Dataset headers (variables present in study datasets)
4. Notes (additional documentation)

This is the SMART tool for unified search across all metadata.

PRIVACY: Metadata-only. NO patient data. Ever.

Use Cases:
- "Find all HIV variables" → Searches dictionary + shows which are in datasets
- "What diabetes data do we have?" → Dictionary definitions + dataset availability
- "Show me treatment outcome variables" → Full metadata + data availability
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from reportalin.logging import get_logger
from reportalin.server.tools._loaders import get_all_results

__all__ = ["CombinedSearchResult", "UnifiedVariable", "combined_search"]

logger = get_logger(__name__)


# =============================================================================
# Output Model
# =============================================================================


class UnifiedVariable(BaseModel):
    """Variable with source annotations."""

    variable: str = Field(description="Variable name")
    description: str | None = Field(default=None, description="Variable description")
    data_type: str | None = Field(default=None, description="Data type")
    table: str | None = Field(default=None, description="Dictionary table")
    in_dictionary: bool = Field(description="Present in data dictionary")
    in_dataset: bool = Field(description="Present in study datasets")
    dataset_count: int = Field(
        default=0, description="Number of datasets containing this variable"
    )
    datasets: list[str] = Field(
        default_factory=list, description="Dataset names containing this variable"
    )


class CombinedSearchResult(BaseModel):
    """Combined search result across dictionary and datasets."""

    query: str = Field(description="Original search query")
    variables: list[UnifiedVariable] = Field(
        description="Unified list of variables with source annotations"
    )
    codelists_found: int = Field(
        default=0, description="Number of matching codelists"
    )
    summary: str = Field(description="Human-readable summary of findings")
    formatted_output: str = Field(
        description="Pre-formatted markdown for beautiful display"
    )


# =============================================================================
# Search Helpers
# =============================================================================


def _matches_query(text: str | None, query_terms: list[str]) -> bool:
    """Check if any query term matches text (case-insensitive)."""
    if not text:
        return False
    text_lower = text.lower()
    return any(term in text_lower for term in query_terms)


def _expand_query(query: str) -> list[str]:
    """Expand query into search terms (lowercase).

    Handles common clinical synonyms.
    """
    terms = [query.lower()]

    # Add individual words for multi-word queries
    words = query.lower().split()
    if len(words) > 1:
        terms.extend(words)

    # Clinical synonyms expansion
    synonyms = {
        "hiv": ["hiv", "human immunodeficiency", "aids"],
        "tb": ["tb", "tuberculosis", "mycobacterium"],
        "diabetes": ["diabetes", "diabetic", "glucose", "hba1c", "dm"],
        "relapse": ["relapse", "recurrence", "recur", "return"],
        "outcome": ["outcome", "result", "status", "disposition"],
        "death": ["death", "died", "deceased", "mortality"],
        "treatment": ["treatment", "therapy", "medication", "drug", "regimen"],
    }

    for key, syns in synonyms.items():
        if key in query.lower():
            terms.extend(syns)

    return list(set(terms))


# =============================================================================
# Main Tool
# =============================================================================


def combined_search(
    query: Annotated[
        str,
        Field(
            description="Clinical concept or variable to search for. "
            "Examples: 'HIV status', 'diabetes', 'relapse', 'treatment outcome'",
            min_length=2,
            max_length=200,
        ),
    ],
) -> CombinedSearchResult:
    """
    Comprehensive variable discovery across ALL results data.

    Searches:
    1. Data Dictionary: Variables matching your search query with full definitions
    2. Codelists: Categorical value definitions for matching variables
    3. Dataset Headers: Which datasets contain matching variables

    Examples:
        combined_search("HIV") → HIV variables with definitions + dataset availability
        combined_search("diabetes") → Diabetes-related variables across all sources
        combined_search("outcome") → Outcome variables with codelists + datasets

    Args:
        query: Clinical concept to search

    Returns:
        CombinedSearchResult with unified results + formatted markdown
    """
    logger.info(f"Combined search for: {query}")

    # Load ALL results data
    results = get_all_results()
    query_terms = _expand_query(query)

    # Build unified variable map
    unified_map: dict[str, UnifiedVariable] = {}

    # Step 1: Search data dictionary
    for table_name, fields in results["data_dictionary"].items():
        for field in fields:
            var_name = field.get("Question Short Name (Databank Fieldname)", "")
            if not var_name:
                continue

            description = field.get("Question", "")
            data_type = field.get("Type", "")

            # Check if matches query
            if _matches_query(var_name, query_terms) or _matches_query(description, query_terms):
                key = var_name.upper()
                if key not in unified_map:
                    unified_map[key] = UnifiedVariable(
                        variable=var_name,
                        description=description if description else None,
                        data_type=data_type if data_type else None,
                        table=table_name,
                        in_dictionary=True,
                        in_dataset=False,
                        dataset_count=0,
                        datasets=[],
                    )

    # Step 2: Cross-reference with dataset headers
    for dataset_name, variables in results["dataset_headers"].items():
        for var in variables:
            key = var.upper()
            if key in unified_map:
                # Variable in dictionary AND this dataset
                unified_map[key].in_dataset = True
                unified_map[key].dataset_count += 1
                unified_map[key].datasets.append(dataset_name)
            elif _matches_query(var, query_terms):
                # Variable matches query but NOT in dictionary
                if key not in unified_map:
                    unified_map[key] = UnifiedVariable(
                        variable=var,
                        description=None,
                        data_type=None,
                        table=None,
                        in_dictionary=False,
                        in_dataset=True,
                        dataset_count=1,
                        datasets=[dataset_name],
                    )
                else:
                    unified_map[key].dataset_count += 1
                    unified_map[key].datasets.append(dataset_name)

    # Step 3: Count matching codelists
    codelists_found = sum(
        1 for cl_name in results["codelists"]
        if _matches_query(cl_name, query_terms)
    )

    unified_vars = list(unified_map.values())

    # Step 4: Build formatted output
    formatted_lines = [f"# Combined Search: `{query}`\n"]

    # Group by source
    both = [v for v in unified_vars if v.in_dictionary and v.in_dataset]
    dict_only = [v for v in unified_vars if v.in_dictionary and not v.in_dataset]
    dataset_only = [v for v in unified_vars if not v.in_dictionary and v.in_dataset]

    if not unified_vars:
        formatted_lines.append(f"No variables found for **'{query}'**.")
    else:
        # Section 1: Variables in BOTH (most valuable)
        if both:
            formatted_lines.append(
                f"## ✓ In Both Dictionary & Datasets ({len(both)})\n"
            )
            formatted_lines.append("| Variable | Description | Type | Datasets |")
            formatted_lines.append("|----------|-------------|------|----------|")
            for v in sorted(both, key=lambda x: -x.dataset_count)[:50]:
                desc = (v.description or "").replace("\n", " ").replace("|", "\\|")[:80]
                formatted_lines.append(
                    f"| `{v.variable}` | {desc} | {v.data_type or 'N/A'} | {v.dataset_count} |"
                )

        # Section 2: Dictionary only
        if dict_only:
            formatted_lines.append(f"\n## 📚 Dictionary Only ({len(dict_only)})\n")
            formatted_lines.append("*Variables documented but not in datasets*\n")
            formatted_lines.append("| Variable | Description | Type | Table |")
            formatted_lines.append("|----------|-------------|------|-------|")
            for v in dict_only[:30]:
                desc = (v.description or "").replace("\n", " ").replace("|", "\\|")[:80]
                formatted_lines.append(
                    f"| `{v.variable}` | {desc} | {v.data_type or 'N/A'} | {v.table or 'N/A'} |"
                )

        # Section 3: Dataset only
        if dataset_only:
            formatted_lines.append(f"\n## 📊 Dataset Only ({len(dataset_only)})\n")
            formatted_lines.append("*Variables in datasets but not in dictionary*\n")
            formatted_lines.append("| Variable | Datasets |")
            formatted_lines.append("|----------|----------|")
            for v in sorted(dataset_only, key=lambda x: -x.dataset_count)[:20]:
                datasets_str = ", ".join(v.datasets[:3])
                if len(v.datasets) > 3:
                    datasets_str += f" +{len(v.datasets) - 3} more"
                formatted_lines.append(f"| `{v.variable}` | {datasets_str} |")

        # Section 4: Codelists hint
        if codelists_found:
            formatted_lines.append(f"\n---\n📋 **{codelists_found} codelist(s)** match your query.")

    formatted_output = "\n".join(formatted_lines)

    # Step 5: Build summary
    summary_parts = [
        f"Found {len(unified_vars)} variable(s) for '{query}':",
        f"{len(both)} in both dictionary & datasets,",
        f"{len(dict_only)} dictionary-only,",
        f"{len(dataset_only)} dataset-only.",
    ]
    if codelists_found:
        summary_parts.append(f"{codelists_found} codelist(s) also match.")

    summary = " ".join(summary_parts)

    logger.info(
        f"Combined search complete: {len(unified_vars)} vars "
        f"(both={len(both)}, dict={len(dict_only)}, dataset={len(dataset_only)})"
    )

    return CombinedSearchResult(
        query=query,
        variables=unified_vars,
        codelists_found=codelists_found,
        summary=summary,
        formatted_output=formatted_output,
    )
