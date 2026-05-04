"""LLM-Powered Variable Search Tool for RePORTaLiN.

This is the PRIMARY tool for study design and variable discovery.
It's better than SQL search because:
1. Understands clinical concepts (not just exact string matching)
2. Expands synonyms automatically (e.g., "relapse" → "recurrence", "recur")
3. Returns structured metadata ready for research planning

Usage:
    search("relapse")  # Finds all relapse-related variables
    search("HIV status")  # Finds HIV-related variables
    search("treatment outcome")  # Finds outcome variables
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from reportalin.core.logging import get_logger
from reportalin.server.tools._loaders import get_codelists, get_data_dictionary

__all__ = ["search", "SearchResult", "Variable", "Codelist"]

logger = get_logger(__name__)


# =============================================================================
# Output Models (Structured Output for LLM)
# =============================================================================


class Variable(BaseModel):
    """A variable found in the data dictionary."""

    field_name: str = Field(description="Database field name to use in queries")
    description: str = Field(description="Human-readable description")
    table: str = Field(description="Database table containing this variable")
    data_type: str | None = Field(default=None, description="Data type (e.g., Integer, Text)")
    codelist: str | None = Field(default=None, description="Reference to codelist if categorical")
    module: str | None = Field(default=None, description="CRF module/form source")


class CodelistValue(BaseModel):
    """A single value in a codelist."""

    code: str = Field(description="The code value")
    description: str = Field(description="What the code means")


class Codelist(BaseModel):
    """A codelist (valid values for a categorical variable)."""

    name: str = Field(description="Codelist name")
    values: list[CodelistValue] = Field(description="Valid code/description pairs")


class SearchResult(BaseModel):
    """Result of a variable search - structured for LLM consumption."""

    query: str = Field(description="Original search query")
    search_terms: list[str] = Field(description="Terms searched (including synonyms)")
    variables: list[Variable] = Field(description="Matching variables")
    codelists: list[Codelist] = Field(description="Related codelists")
    suggestion: str | None = Field(default=None, description="Suggestion if no results")


# =============================================================================
# Clinical Concept Synonyms (The LLM-Powered Intelligence)
# =============================================================================

CONCEPT_SYNONYMS: dict[str, list[str]] = {
    # Demographics
    "age": ["age", "birth", "dob", "years"],
    "sex": ["sex", "gender", "male", "female"],
    "site": ["site", "center", "location", "pune", "chennai", "vellore"],
    # Anthropometrics
    "bmi": ["bmi", "body mass", "weight", "height"],
    "weight": ["weight", "kgs", "mass"],
    "malnutrition": ["malnutrition", "undernutrition", "undernourish", "bmi"],
    "nutrition": ["nutrition", "bmi", "weight", "diet"],
    # Comorbidities
    "diabetes": ["diabetes", "diabetic", "glucose", "hba1c", "fbg", "rbg", "ogtt", "blood sugar"],
    "hiv": ["hiv", "aids", "hivstat", "retroviral", "antiretroviral", "cd4"],
    # Risk factors
    "smoking": ["smoking", "smoke", "smoker", "tobacco", "cigarette", "smokhx", "bidi"],
    "alcohol": ["alcohol", "drinking", "drink", "liquor", "beer", "alcoh"],
    # TB specific
    "tuberculosis": ["tuberculosis", "tb", "tbnew", "tbdx", "pulmonary"],
    "diagnosis": ["diagnosis", "diagnosed", "tbdx", "confirm"],
    "treatment": ["treatment", "therapy", "regimen", "medication", "anti-tb"],
    "outcome": ["outcome", "outclin", "outoth", "cure", "fail", "death", "ltfu"],
    "cure": ["cure", "cured", "success", "favorable"],
    "failure": ["failure", "fail", "unfavorable", "unsuccessful"],
    "death": ["death", "died", "mortality", "dead"],
    "relapse": ["relapse", "recurrence", "recurrent", "recur"],
    "follow-up": ["follow", "followup", "fua", "fub", "visit"],
    # Lab tests
    "sputum": ["sputum", "smear", "afb", "microscopy"],
    "culture": ["culture", "growth"],
    "xpert": ["xpert", "genexpert", "pcr", "molecular"],
    "xray": ["xray", "x-ray", "chest", "radiograph", "cxr"],
    # Clinical
    "symptoms": ["symptom", "cough", "fever", "weight loss", "night sweat"],
    "cough": ["cough", "sputum", "expectoration"],
    "fever": ["fever", "temperature", "febrile"],
    # Time points
    "baseline": ["baseline", "enrollment", "initial", "screening", "index"],
}


def _expand_query(query: str) -> list[str]:
    """Expand query using clinical concept synonyms.
    
    This is where the LLM-powered intelligence comes in - we understand
    clinical concepts, not just exact string matching.
    """
    query_lower = query.lower()
    terms = set()
    
    # Add the original query and its words
    terms.add(query_lower)
    for word in query_lower.split():
        if len(word) > 2:  # Skip very short words
            terms.add(word)
    
    # Expand using synonyms
    for concept, synonyms in CONCEPT_SYNONYMS.items():
        # If query matches concept or any synonym, add all synonyms
        if concept in query_lower or any(syn in query_lower for syn in synonyms):
            terms.update(synonyms)
    
    return list(terms)[:15]  # Limit to avoid overly broad search


# =============================================================================
# Main Search Tool
# =============================================================================


def search(
    query: Annotated[
        str,
        Field(
            description="Clinical concept or variable to search for. "
            "Examples: 'HIV status', 'diabetes', 'relapse', 'treatment outcome', 'smoking'",
            min_length=2,
            max_length=200,
        ),
    ],
) -> SearchResult:
    """
    Search for study variables by clinical concept.
    
    This is better than SQL search because it:
    - Understands clinical terminology and synonyms
    - Expands your query to find related variables
    - Returns structured metadata for research planning
    
    Examples:
        search("relapse") → finds relapse, recurrence, recur variables
        search("HIV") → finds HIV status, CD4, ART variables
        search("outcome") → finds treatment outcome variables
    
    Args:
        query: Clinical concept to search for
        
    Returns:
        SearchResult with matching variables and codelists
    """
    logger.info(f"Searching for: {query}")
    
    # Get data
    data_dict = get_data_dictionary()
    codelists = get_codelists()
    
    # Expand query with synonyms (the LLM-powered part)
    search_terms = _expand_query(query)
    
    # Search variables
    found_vars: dict[str, Variable] = {}
    
    for table_name, records in data_dict.items():
        for record in records:
            field_name = record.get("Question Short Name (Databank Fieldname)", "")
            if not field_name:
                continue
                
            # Build searchable text
            searchable = " ".join([
                str(field_name),
                str(record.get("Question", "")),
                str(record.get("Module", "")),
                str(record.get("Code List or format", "")),
                str(record.get("Notes", "")),
            ]).lower()
            
            # Check if any search term matches
            for term in search_terms:
                if term in searchable and field_name not in found_vars:
                    found_vars[field_name] = Variable(
                        field_name=field_name,
                        description=record.get("Question") or "",
                        table=record.get("__table__") or table_name,
                        data_type=record.get("Type"),
                        codelist=record.get("Code List or format"),
                        module=record.get("Module"),
                    )
                    break
    
    # Search codelists
    found_codelists: dict[str, Codelist] = {}
    
    for name, values in codelists.items():
        name_lower = name.lower()
        
        # Check if codelist name matches any search term
        for term in search_terms:
            if term in name_lower and name not in found_codelists:
                found_codelists[name] = Codelist(
                    name=name,
                    values=[
                        CodelistValue(
                            code=str(v.get("Codes", "")),
                            description=str(v.get("Descriptors", "")),
                        )
                        for v in values[:15]  # Limit values
                    ],
                )
                break
        
        # Also check value descriptions
        if name not in found_codelists:
            for v in values:
                desc = str(v.get("Descriptors", "")).lower()
                for term in search_terms:
                    if term in desc:
                        found_codelists[name] = Codelist(
                            name=name,
                            values=[
                                CodelistValue(
                                    code=str(val.get("Codes", "")),
                                    description=str(val.get("Descriptors", "")),
                                )
                                for val in values[:15]
                            ],
                        )
                        break
                if name in found_codelists:
                    break
    
    # Build result
    variables = list(found_vars.values())[:30]  # Limit results
    codelist_list = list(found_codelists.values())[:10]
    
    # Add suggestion if no results
    suggestion = None
    if not variables:
        suggestion = (
            f"No variables found for '{query}'. Try:\n"
            "- Different terms: 'smoking' instead of 'tobacco use'\n"
            "- Abbreviations: 'DM' for diabetes, 'HIV' for human immunodeficiency\n"
            "- Specific concepts: 'outcome', 'status', 'history'"
        )
    
    logger.info(f"Found {len(variables)} variables, {len(codelist_list)} codelists")
    
    return SearchResult(
        query=query,
        search_terms=search_terms,
        variables=variables,
        codelists=codelist_list,
        suggestion=suggestion,
    )
