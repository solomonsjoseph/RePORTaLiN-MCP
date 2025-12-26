"""Concept-based search tool for data dictionary and codelists.

This tool searches through:
1. DATA DICTIONARY - Finds relevant variables for your concept
2. CODELISTS - Returns valid values for categorical variables

Uses intelligent concept synonym mapping to expand search queries.
For example, "relapse" also searches for "recurrence", "recurrent", "recur".

Use this tool for questions about what variables are available for a given
clinical concept or research question.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from reportalin.core.logging import get_logger
from reportalin.server.tools._loaders import (
    get_codelists,
    get_data_dictionary,
)
from reportalin.server.tools._models import CombinedSearchInput

__all__ = ["combined_search"]

logger = get_logger(__name__)


async def combined_search(
    input: CombinedSearchInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search for variables related to a clinical concept.

    Uses intelligent concept synonym mapping to find relevant variables.
    For example, searching for "relapse" will also find variables related to
    "recurrence", "recurrent", and "recur".

    Use this for questions like:
    - "What variables are available for relapse analysis?"
    - "Show me diabetes-related variables"
    - "Which variables capture TB treatment outcomes?"
    - "Find HIV status variables"

    Args:
        input: Clinical concept or research question
        ctx: MCP context

    Returns:
        Variables found in dictionary + codelist definitions
    """
    await ctx.info(f"Combined search for: {input.concept}")

    try:
        data_dict = get_data_dictionary()
        codelists = get_codelists()

        concept_lower = input.concept.lower()

        # =================================================================
        # STEP 1: Build comprehensive search terms from the concept
        # =================================================================

        # RePORT India specific synonyms and related terms
        # NOTE: Avoid short terms (2 chars) that match too broadly
        concept_synonyms = {
            # Demographics
            "age": ["age", "birth", "dob", "years old"],
            "sex": ["sex", "gender", "male", "female"],
            "site": ["site", "center", "location", "pune", "chennai", "vellore"],
            # Anthropometrics & Nutrition
            "bmi": ["bmi", "body mass", "weight", "height"],
            "weight": ["weight", "kgs", "mass"],
            "height": ["height", "tall"],
            "malnutrition": [
                "malnutrition",
                "undernutrition",
                "undernourish",
                "bmi",
                "weight",
            ],
            "nutrition": ["nutrition", "bmi", "weight", "diet", "food"],
            # Comorbidities - be specific to avoid false matches
            "diabetes": [
                "diabetes",
                "diabetic",
                "glucose",
                "hba1c",
                "hba1",
                "fbg_",
                "rbg_",
                "ogtt",
                "blood sugar",
            ],
            "hiv": ["hiv", "aids", "hivstat", "retroviral", "antiretroviral"],
            # Risk factors
            "smoking": [
                "smoking",
                "smoke",
                "smoker",
                "tobacco",
                "cigarette",
                "smokhx",
                "bidi",
            ],
            "alcohol": ["alcohol", "drinking", "drink", "liquor", "beer", "alcoh"],
            "drug": ["drug use", "substance", "injection drug", "idu"],
            # TB specific
            "tuberculosis": ["tuberculosis", "tbnew", "tbdx", "pulmonary"],
            "diagnosis": ["diagnosis", "diagnosed", "tbdx", "confirm"],
            "treatment": ["treatment", "therapy", "regimen", "medication", "anti-tb"],
            "outcome": [
                "outcome",
                "outclin",
                "outoth",
                "cure",
                "fail",
                "death",
                "ltfu",
                "treatment result",
            ],
            "cure": ["cure", "cured", "success", "favorable"],
            "failure": ["failure", "fail", "unfavorable", "unsuccessful"],
            "death": ["death", "died", "mortality", "dead"],
            "relapse": ["relapse", "recurrence", "recurrent", "recur"],
            "follow-up": ["follow", "followup", "fua_", "fub_", "visit"],
            # Lab tests
            "sputum": ["sputum", "smear", "afb", "microscopy"],
            "culture": ["culture", "growth"],
            "xpert": ["xpert", "genexpert", "pcr", "molecular"],
            "xray": ["xray", "x-ray", "chest", "radiograph", "cxr"],
            "cd4": ["cd4", "t-cell", "immune"],
            # Clinical
            "symptoms": ["symptom", "cough", "fever", "weight loss", "night sweat"],
            "cough": ["cough", "sputum", "expectoration"],
            "fever": ["fever", "temperature", "febrile"],
            # Time points
            "baseline": ["baseline", "enrollment", "initial", "screening", "index"],
            "month": ["month", "week", "day", "visit", "follow"],
        }

        # Build search terms from the query
        search_terms = set()
        search_terms.add(concept_lower)

        # Add individual words from the query
        for word in concept_lower.split():
            if len(word) > 2:  # Skip very short words
                search_terms.add(word)

        # Add synonyms for matching concepts
        for key, synonyms in concept_synonyms.items():
            if key in concept_lower or any(syn in concept_lower for syn in synonyms):
                search_terms.update(synonyms)

        search_terms = list(search_terms)[:15]  # Limit to avoid too broad search

        # =================================================================
        # STEP 2: Search DATA DICTIONARY (actual search, not guessing)
        # =================================================================

        results = {
            "concept": input.concept,
            "search_terms_used": search_terms,
            "variables_found": [],
            "codelists_found": [],
            "summary": {},
        }

        # Search through all data dictionary tables
        found_vars = {}  # field_name -> info
        for table_name, records in data_dict.items():
            for record in records:
                # Build searchable text from all relevant fields
                field_name = record.get("Question Short Name (Databank Fieldname)", "")
                searchable_parts = [
                    str(field_name),
                    str(record.get("Question", "")),
                    str(record.get("Module", "")),
                    str(record.get("Code List or format", "")),
                    str(record.get("Notes", "")),
                ]
                searchable = " ".join(searchable_parts).lower()

                # Check if any search term matches
                for term in search_terms:
                    if term in searchable:
                        if field_name and field_name not in found_vars:
                            found_vars[field_name] = {
                                "field_name": field_name,
                                "description": record.get("Question"),
                                "type": record.get("Type"),
                                "table": record.get("__table__", table_name),
                                "module": record.get("Module"),
                                "codelist_ref": record.get("Code List or format"),
                                "matched_term": term,
                            }
                        break

        results["variables_found"] = list(found_vars.values())[:30]  # Limit results

        # =================================================================
        # STEP 3: Search CODELISTS for matching values
        # =================================================================

        found_codelists = {}
        for name, values in codelists.items():
            name_lower = name.lower()
            # Check if codelist name matches any search term
            for term in search_terms:
                if term in name_lower:
                    if name not in found_codelists:
                        found_codelists[name] = {
                            "name": name,
                            "values": [
                                {
                                    "code": v.get("Codes"),
                                    "description": v.get("Descriptors"),
                                }
                                for v in values[:15]  # Limit values shown
                            ],
                            "total_values": len(values),
                        }
                    break

            # Also check if any value descriptions match
            if name not in found_codelists:
                for v in values:
                    desc = str(v.get("Descriptors", "")).lower()
                    for term in search_terms:
                        if term in desc:
                            found_codelists[name] = {
                                "name": name,
                                "values": [
                                    {
                                        "code": val.get("Codes"),
                                        "description": val.get("Descriptors"),
                                    }
                                    for val in values[:15]
                                ],
                                "total_values": len(values),
                            }
                            break
                    if name in found_codelists:
                        break

        results["codelists_found"] = list(found_codelists.values())[:10]

        # =================================================================
        # STEP 3: Build summary
        # =================================================================

        results["summary"] = {
            "query": input.concept,
            "variables_found": len(results["variables_found"]),
            "codelists_found": len(results["codelists_found"]),
        }

        # Add guidance if nothing found
        if not results["variables_found"]:
            results["guidance"] = (
                f"No variables found for '{input.concept}'. "
                "Try:\n"
                "- Different keywords (e.g., 'smoking' instead of 'tobacco use')\n"
                "- Medical abbreviations (e.g., 'DM' for diabetes, 'HIV' for human immunodeficiency virus)\n"
                "- Specific variable names if you know them\n"
                "- Use search_data_dictionary to browse all available variables"
            )

        return results

    except Exception as e:
        logger.error(f"Combined search failed: {e}")
        return {"error": str(e), "concept": input.concept}
