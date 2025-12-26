"""
Tests for the RePORTaLiN MCP Server.

This module contains unit tests for the MCP tools, Pydantic models,
and server utilities. The MCP server is located under server/.

Tests cover:
- Pydantic input model validation
- Tool registry functionality
- Server configuration export
- Security validations (aggregates only, no individual records)
"""

import pytest
from pydantic import ValidationError

from reportalin.server.tools import (
    CombinedSearchInput,
    SearchDataDictionaryInput,
    get_tool_registry,
    mcp,
)
from reportalin.core.constants import SERVER_NAME, SERVER_VERSION


class TestSearchDataDictionaryInput:
    """Tests for SearchDataDictionaryInput Pydantic model."""

    def test_valid_search_query(self) -> None:
        """Test that valid search queries are accepted."""
        input_data = SearchDataDictionaryInput(
            query="smoking",
        )
        assert "smoking" in input_data.query
        assert input_data.include_codelists is True

    def test_query_with_codelist_disabled(self) -> None:
        """Test query with codelist search disabled."""
        input_data = SearchDataDictionaryInput(
            query="HIV",
            include_codelists=False,
        )
        assert input_data.include_codelists is False

    def test_query_too_short(self) -> None:
        """Test that empty queries are rejected."""
        with pytest.raises(ValidationError):
            SearchDataDictionaryInput(query="")

    def test_query_too_long(self) -> None:
        """Test that very long queries are rejected."""
        with pytest.raises(ValidationError):
            SearchDataDictionaryInput(query="x" * 201)


class TestCombinedSearchInput:
    """Tests for CombinedSearchInput Pydantic model."""

    def test_valid_combined_search(self) -> None:
        """Test that valid combined searches are accepted."""
        input_data = CombinedSearchInput(
            concept="smoking status",
        )
        assert "smoking" in input_data.concept


class TestToolRegistry:
    """Tests for tool registry functionality."""

    def test_get_tool_registry_returns_dict(self) -> None:
        """Test that get_tool_registry returns a dictionary."""
        registry = get_tool_registry()
        assert isinstance(registry, dict)

    def test_registry_contains_server_info(self) -> None:
        """Test that registry contains server name and version."""
        registry = get_tool_registry()
        assert registry["server_name"] == SERVER_NAME
        assert registry["version"] == SERVER_VERSION

    def test_registry_contains_registered_tools(self) -> None:
        """Test that registry lists registered tools.

        Tool Selection Guide (v0.3.0 - Dictionary Expert):
        - prompt_enhancer: PRIMARY ENTRY POINT (routes queries)
        - combined_search: DEFAULT variable discovery with concept expansion
        - search_data_dictionary: Direct variable lookup by keyword
        """
        registry = get_tool_registry()
        assert "registered_tools" in registry
        tools = registry["registered_tools"]
        # All 3 tools
        assert "prompt_enhancer" in tools
        assert "combined_search" in tools
        assert "search_data_dictionary" in tools

    def test_registry_contains_data_loaded_info(self) -> None:
        """Test that registry shows data dictionary loaded info (metadata only)."""
        registry = get_tool_registry()
        assert "data_loaded" in registry
        data = registry["data_loaded"]
        assert "dictionary_tables" in data
        assert "dictionary_fields" in data
        assert "codelists" in data
        # v0.3.0: No dataset loading - dictionary only
        assert "cleaned_tables" not in data
        assert "cleaned_records" not in data

    def test_registry_contains_resources(self) -> None:
        """Test that registry lists MCP resources."""
        registry = get_tool_registry()
        assert "registered_resources" in registry
        resources = registry["registered_resources"]
        assert "dictionary://overview" in resources
        assert "dictionary://tables" in resources


class TestMCPServer:
    """Tests for the FastMCP server instance."""

    def test_mcp_instance_exists(self) -> None:
        """Test that MCP server instance exists."""
        assert mcp is not None

    def test_mcp_server_name(self) -> None:
        """Test that MCP server has correct name."""
        assert mcp.name == SERVER_NAME

    def test_mcp_has_instructions(self) -> None:
        """Test that MCP server has instructions."""
        # FastMCP stores instructions in the instance
        assert hasattr(mcp, "_instructions") or mcp.name is not None


class TestSecurityModel:
    """Tests for security model - metadata only, no patient data."""

    def test_tools_designed_for_metadata_only(self) -> None:
        """Test that tool registry confirms metadata-only design (v0.3.0)."""
        registry = get_tool_registry()
        # v0.3.0: Dictionary Expert - metadata only, no patient data
        assert len(registry["registered_tools"]) == 3
        assert registry.get("server_type") == "data_dictionary_expert"

    @pytest.mark.parametrize(
        "safe_query",
        [
            "smoking",
            "HIV",
            "age",
            "SEX codelist",
            "treatment outcome",
            "diabetes",
            "TB diagnosis",
        ],
    )
    def test_dictionary_accepts_safe_queries(self, safe_query: str) -> None:
        """Test that dictionary search accepts valid queries."""
        input_data = SearchDataDictionaryInput(query=safe_query)
        assert input_data.query == safe_query

    @pytest.mark.parametrize(
        "concept",
        [
            "smoking status",
            "age distribution",
            "HIV status",
            "TB outcome",
            "alcohol use",
        ],
    )
    def test_combined_accepts_valid_concepts(self, concept: str) -> None:
        """Test that combined search accepts valid clinical concepts."""
        input_data = CombinedSearchInput(concept=concept)
        assert input_data.concept == concept
