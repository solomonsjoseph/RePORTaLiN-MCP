"""Pydantic input models for MCP tools.

This module defines the input validation schemas for all 3 MCP tools.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

__all__ = [
    "PromptEnhancerInput",
    "CombinedSearchInput",
    "SearchDataDictionaryInput",
]


class PromptEnhancerInput(BaseModel):
    """Input for the prompt enhancer tool (primary entry point).

    This tool analyzes user queries, enhances them for accuracy, ensures privacy
    compliance, and routes to appropriate specialized tools.
    """

    user_query: Annotated[
        str,
        Field(
            description="Natural language question from the user. Can be vague or imprecise. "
            "Examples: 'How many TB patients?', 'What variables track HIV?', "
            "'Show me diabetes statistics', 'Compare outcomes by site'",
            min_length=5,
            max_length=500,
        ),
    ]

    context: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Optional context from previous queries for multi-turn conversations",
        ),
    ]

    user_confirmation: Annotated[
        bool,
        Field(
            default=False,
            description="Set to True after user confirms the interpretation is correct",
        ),
    ]


class CombinedSearchInput(BaseModel):
    """Input for combined dictionary + codelist search with concept expansion (DEFAULT tool)."""

    concept: Annotated[
        str,
        Field(
            description="Clinical concept for variable discovery. "
            "Examples: 'smoking status', 'HIV variables', 'TB outcome', 'relapse analysis'",
        ),
    ]


class SearchDataDictionaryInput(BaseModel):
    """Input for searching the data dictionary (metadata only)."""

    query: Annotated[
        str,
        Field(
            description="Search term for variable names, descriptions, or codelists. "
            "Examples: 'HIV', 'age', 'smoking', 'SEX codelist', 'outcome'",
            min_length=1,
            max_length=200,
        ),
    ]

    include_codelists: Annotated[
        bool,
        Field(default=True, description="Include codelist searches"),
    ]
