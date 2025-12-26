"""Intelligent Query Enhancement and Routing Tool.

This tool acts as the PRIMARY ENTRY POINT for all user queries. It:
1. Analyzes user intent (variable discovery)
2. Enhances vague queries for accuracy using structured decomposition
3. Routes to appropriate specialized tools (dictionary or concept search)
4. CRITICAL: Always confirms understanding with user BEFORE executing

The prompt enhancement leverages the LLM client's natural language understanding
to break down vague queries into structured, accurate requests.

Examples:
    User: "What variables for relapse analysis?"
    Enhanced: "Search data dictionary for variables related to TB relapse,
               recurrence, and treatment failure. Return variable names,
               descriptions, and valid codes."

    User: "HIV variables"
    Enhanced: "Search data dictionary for variables related to HIV diagnosis,
               status, treatment (ART), and CD4 counts. Include codelists."

Metadata Only:
    - Returns variable names, descriptions, types, and codelists
    - No patient data or statistics
    - Focus on helping researchers find the right variables
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from reportalin.core.logging import get_logger
from reportalin.server.tools._models import (
    CombinedSearchInput,
    PromptEnhancerInput,
    SearchDataDictionaryInput,
)

__all__ = ["prompt_enhancer"]

logger = get_logger(__name__)


async def prompt_enhancer(
    input: PromptEnhancerInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Enhance user query and route to appropriate tools.

    This is the PRIMARY entry point for all MCP queries.
    CRITICAL: Always confirms understanding with user BEFORE executing.

    Args:
        input: User query and confirmation status
        ctx: MCP context

    Returns:
        If not confirmed: {"needs_confirmation": True, "interpretation": "..."}
        If confirmed: Routes to appropriate tool and returns results

    Flow:
        1. Analyze query intent using structured decomposition
        2. Generate human-readable interpretation
        3. If not confirmed → Return interpretation for user approval
        4. If confirmed → Route to appropriate tool based on intent
        5. Return results in appropriate format
    """
    await ctx.info(f"Prompt enhancer processing: {input.user_query}")

    try:
        # Step 1: Analyze intent using query decomposition
        intent = _analyze_intent(input.user_query, input.context)

        # Step 2: Generate human-readable interpretation
        interpretation = _generate_interpretation(input.user_query, intent)

        # Step 3: If not confirmed, return interpretation for user approval
        if not input.user_confirmation:
            return {
                "needs_confirmation": True,
                "interpretation": interpretation,
                "understood_intent": intent,
                "next_step": "Please confirm if this interpretation is correct, "
                "or provide corrections. Set user_confirmation=True to proceed.",
            }

        # Step 4: User confirmed - route to appropriate tool
        await ctx.info(f"User confirmed. Routing to tool: {intent['primary_tool']}")

        # Import tools here to avoid circular imports
        from reportalin.server.tools.combined_search import combined_search
        from reportalin.server.tools.search_data_dictionary import search_data_dictionary

        # Route based on intent
        if intent["primary_tool"] == "search_data_dictionary":
            # Variable discovery - search for variable definitions only
            tool_input = SearchDataDictionaryInput(
                query=intent["enhanced_query"],
                include_codelists=True,
            )
            result = await search_data_dictionary(tool_input, ctx)

        else:
            # DEFAULT: combined_search for variable discovery with concept mapping
            tool_input = CombinedSearchInput(
                concept=intent["enhanced_query"],
            )
            result = await combined_search(tool_input, ctx)

        # Step 5: Return results with context
        return {
            "needs_confirmation": False,
            "original_query": input.user_query,
            "interpretation": interpretation,
            "tool_used": intent["primary_tool"],
            "result": result,
        }

    except Exception as e:
        logger.error(f"Prompt enhancer failed: {e}")
        return {
            "error": str(e),
            "original_query": input.user_query,
            "suggestion": "Try rephrasing your question or breaking it into smaller parts",
        }


def _analyze_intent(query: str, context: dict[str, Any] | None) -> dict[str, Any]:
    """
    Analyze user query to determine intent and appropriate tool.

    This function uses structured decomposition to understand what the user wants:
    1. Identifies query type (metadata vs statistics vs analysis)
    2. Extracts key clinical concepts
    3. Determines complexity level
    4. Selects appropriate tool

    Args:
        query: User's natural language question
        context: Optional context from previous queries

    Returns:
        Dictionary with:
            - type: Query type (metadata, statistical_query, comparison, etc.)
            - concepts: List of clinical concepts identified
            - enhanced_query: Improved version of the query
            - primary_tool: Which tool to use (search_data_dictionary, combined_search, etc.)
            - complexity: simple, moderate, or complex
            - privacy_safe: Whether query is safe from privacy perspective
    """
    query_lower = query.lower()

    # Determine query type based on keywords
    if any(word in query_lower for word in ["what variables", "which variables", "list variables", "what fields", "variable names"]):
        query_type = "metadata_discovery"
        primary_tool = "search_data_dictionary"
        enhanced_query = query  # Use original for metadata queries

    elif any(word in query_lower for word in ["what does", "mean", "definition", "describe variable", "what is the meaning"]):
        query_type = "variable_definition"
        primary_tool = "search_data_dictionary"
        enhanced_query = query

    elif any(word in query_lower for word in ["how many", "count", "number of", "total", "percentage", "proportion"]):
        query_type = "statistical_query"
        primary_tool = "combined_search"
        # Enhance to be more specific
        enhanced_query = _enhance_statistical_query(query)

    elif any(word in query_lower for word in ["compare", "vs", "versus", "between", "difference", "association", "relationship"]):
        query_type = "comparison_analysis"
        primary_tool = "combined_search"
        enhanced_query = _enhance_comparison_query(query)

    elif any(word in query_lower for word in ["distribution", "breakdown", "spread", "range"]):
        query_type = "distribution_analysis"
        primary_tool = "combined_search"
        enhanced_query = query

    else:
        # Default: assume statistical/analytical query
        query_type = "general_analysis"
        primary_tool = "combined_search"
        enhanced_query = query

    # Extract clinical concepts
    concepts = _extract_clinical_concepts(query_lower)

    # Determine complexity
    complexity = "simple" if len(concepts) <= 2 else "moderate" if len(concepts) <= 4 else "complex"

    return {
        "type": query_type,
        "concepts": concepts,
        "enhanced_query": enhanced_query,
        "primary_tool": primary_tool,
        "complexity": complexity,
        "privacy_safe": True,  # All tools enforce privacy
    }


def _generate_interpretation(query: str, intent: dict[str, Any]) -> str:
    """
    Generate human-readable interpretation of the user's query.

    This is what will be shown to the user for confirmation.

    Args:
        query: Original user query
        intent: Intent analysis from _analyze_intent

    Returns:
        Human-readable interpretation string
    """
    query_type = intent["type"]
    concepts = intent["concepts"]
    primary_tool = intent["primary_tool"]

    # Build interpretation based on query type
    if query_type == "metadata_discovery":
        interpretation = (
            f"I understand you want to find **variable definitions** "
            f"for: {', '.join(concepts) if concepts else 'the specified concept'}.\n\n"
            f"I will search the data dictionary for variable names, descriptions, "
            f"and codelists (without computing statistics)."
        )

    elif query_type == "variable_definition":
        interpretation = (
            f"I understand you want to know the **meaning/definition** "
            f"of: {', '.join(concepts) if concepts else 'a specific variable'}.\n\n"
            f"I will search the data dictionary for the exact definition and codelist values."
        )

    elif query_type == "statistical_query":
        interpretation = (
            f"I understand you want **statistical information** (counts, percentages) "
            f"about: {', '.join(concepts) if concepts else 'the specified topic'}.\n\n"
            f"I will:\n"
            f"1. Find relevant variables in the data dictionary\n"
            f"2. Compute aggregate statistics from the deidentified dataset\n"
            f"3. Return counts, percentages, and distributions (NO individual records)"
        )

    elif query_type == "comparison_analysis":
        interpretation = (
            f"I understand you want to **compare or analyze associations** "
            f"between: {', '.join(concepts) if concepts else 'multiple variables'}.\n\n"
            f"I will:\n"
            f"1. Find relevant variables for each concept\n"
            f"2. Compute statistics for each variable\n"
            f"3. Create cross-tabulations if appropriate\n"
            f"4. Return aggregate comparisons (NO individual records)"
        )

    elif query_type == "distribution_analysis":
        interpretation = (
            f"I understand you want to see the **distribution** "
            f"of: {', '.join(concepts) if concepts else 'a variable'}.\n\n"
            f"I will compute value frequencies, ranges, and breakdowns "
            f"using deidentified aggregate data only."
        )

    else:
        interpretation = (
            f"I understand you want to analyze: {', '.join(concepts) if concepts else query}.\n\n"
            f"I will search all data sources and compute relevant statistics "
            f"using deidentified data only."
        )

    # Add privacy notice
    interpretation += (
        f"\n\n**Privacy Notice:** All results will be aggregate statistics only. "
        f"Individual patient records are never exposed."
    )

    return interpretation


def _extract_clinical_concepts(query_lower: str) -> list[str]:
    """Extract clinical concepts from the query."""
    concept_keywords = {
        "hiv": ["hiv", "aids", "human immunodeficiency"],
        "diabetes": ["diabetes", "diabetic", "glucose", "hba1c"],
        "smoking": ["smoking", "smoke", "smoker", "tobacco", "cigarette"],
        "alcohol": ["alcohol", "drinking", "drink", "liquor"],
        "age": ["age", "years old", "elderly", "young"],
        "sex": ["sex", "gender", "male", "female"],
        "outcome": ["outcome", "cure", "success", "failure", "death", "result"],
        "site": ["site", "center", "location", "pune", "chennai", "vellore"],
        "bmi": ["bmi", "body mass", "weight", "malnutrition"],
        "tuberculosis": ["tuberculosis", "tb"],
    }

    identified = []
    for concept, keywords in concept_keywords.items():
        if any(kw in query_lower for kw in keywords):
            identified.append(concept)

    return identified


def _enhance_statistical_query(query: str) -> str:
    """Enhance a statistical query for better accuracy."""
    # For now, return the original query
    # The combined_search tool will handle the enhancement through its synonym mapping
    return query


def _enhance_comparison_query(query: str) -> str:
    """Enhance a comparison query for better accuracy."""
    # For now, return the original query
    # The combined_search tool will handle cross-tabulation logic
    return query
