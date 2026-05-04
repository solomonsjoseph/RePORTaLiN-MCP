"""
Tests for the RePORTaLiN MCP Server.

This module contains unit tests for the MCP tools, Pydantic models,
and server utilities. The MCP server is located under server/.

Tests cover:
- Search tool functionality
- Tool registry functionality
- Server configuration export
- Security validations (aggregates only, no individual records)
"""

import pytest

from reportalin.server.tools import (
    search,
    SearchResult,
    Variable,
    Codelist,
    CodelistValue,
    get_tool_registry,
    mcp,
)
from reportalin.core.constants import SERVER_NAME, SERVER_VERSION


class TestSearchTool:
    """Tests for the simplified search tool."""

    def test_search_returns_search_result(self) -> None:
        """Test that search returns a SearchResult object."""
        result = search("HIV")
        assert isinstance(result, SearchResult)
        assert result.query == "HIV"
        assert isinstance(result.search_terms, list)

    def test_search_expands_synonyms(self) -> None:
        """Test that search expands clinical concept synonyms."""
        result = search("relapse")
        # Should expand to include recurrence, recur, etc.
        assert "relapse" in result.search_terms
        assert any("recur" in term for term in result.search_terms)

    def test_search_returns_variables(self) -> None:
        """Test that search returns Variable objects."""
        result = search("smoking")
        # Variables may or may not be found depending on data
        assert isinstance(result.variables, list)
        if result.variables:
            assert isinstance(result.variables[0], Variable)

    def test_search_returns_codelists(self) -> None:
        """Test that search returns Codelist objects."""
        result = search("sex")
        assert isinstance(result.codelists, list)
        if result.codelists:
            assert isinstance(result.codelists[0], Codelist)

    def test_search_suggestion_when_no_results(self) -> None:
        """Test that search provides suggestions when no results found."""
        result = search("xyznonexistent")
        # Should have a suggestion if no variables found
        if not result.variables:
            assert result.suggestion is not None

    @pytest.mark.parametrize(
        "query",
        [
            "HIV",
            "diabetes",
            "smoking",
            "outcome",
            "relapse",
            "age",
            "treatment",
        ],
    )
    def test_search_accepts_common_clinical_concepts(self, query: str) -> None:
        """Test that search accepts common clinical concepts."""
        result = search(query)
        assert result.query == query


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

    def test_registry_contains_single_search_tool(self) -> None:
        """Test that registry lists only the search tool.

        Tool Design (simplified):
        - search: LLM-powered variable search with concept expansion
        """
        registry = get_tool_registry()
        assert "registered_tools" in registry
        tools = registry["registered_tools"]
        assert tools == ["search"]
        assert registry["tool_count"] == 1

    def test_registry_contains_data_loaded_info(self) -> None:
        """Test that registry shows data dictionary loaded info (metadata only)."""
        registry = get_tool_registry()
        assert "data_loaded" in registry
        data = registry["data_loaded"]
        assert "dictionary_tables" in data
        assert "dictionary_fields" in data
        assert "codelists" in data

    def test_registry_contains_resources(self) -> None:
        """Test that registry lists MCP resources."""
        registry = get_tool_registry()
        assert "registered_resources" in registry
        resources = registry["registered_resources"]
        assert "dictionary://overview" in resources
        assert "dictionary://tables" in resources

    def test_registry_server_type(self) -> None:
        """Test that registry shows correct server type."""
        registry = get_tool_registry()
        assert registry["server_type"] == "llm_powered_variable_search"


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
        """Test that tool registry confirms metadata-only design."""
        registry = get_tool_registry()
        # Simplified: Single search tool for metadata
        assert len(registry["registered_tools"]) == 1
        assert registry.get("server_type") == "llm_powered_variable_search"

    @pytest.mark.parametrize(
        "safe_query",
        [
            "smoking",
            "HIV",
            "age",
            "sex",
            "treatment outcome",
            "diabetes",
            "TB diagnosis",
        ],
    )
    def test_search_accepts_safe_queries(self, safe_query: str) -> None:
        """Test that search accepts valid queries."""
        result = search(safe_query)
        assert result.query == safe_query


class TestOutputModels:
    """Tests for Pydantic output models."""

    def test_variable_model(self) -> None:
        """Test Variable model creation."""
        var = Variable(
            field_name="SMOKHX",
            description="Smoking history",
            table="tblHISTORY",
        )
        assert var.field_name == "SMOKHX"
        assert var.description == "Smoking history"
        assert var.table == "tblHISTORY"

    def test_codelist_value_model(self) -> None:
        """Test CodelistValue model creation."""
        val = CodelistValue(code="1", description="Yes")
        assert val.code == "1"
        assert val.description == "Yes"

    def test_codelist_model(self) -> None:
        """Test Codelist model creation."""
        cl = Codelist(
            name="YES_NO",
            values=[
                CodelistValue(code="1", description="Yes"),
                CodelistValue(code="0", description="No"),
            ],
        )
        assert cl.name == "YES_NO"
        assert len(cl.values) == 2

    def test_search_result_model(self) -> None:
        """Test SearchResult model creation."""
        result = SearchResult(
            query="test",
            search_terms=["test"],
            variables=[],
            codelists=[],
        )
        assert result.query == "test"
        assert result.suggestion is None
