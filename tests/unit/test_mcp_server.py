"""
Tests for the RePORTaLiN MCP Server.

Tests cover:
- Search tool functionality
- Dataset headers tool functionality
- Combined search tool functionality
- MCP server instance
"""

import pytest

from reportalin.core.constants import SERVER_NAME
from reportalin.server.tools import (
    combined_search,
    list_dataset_headers,
    mcp,
    search,
)
from reportalin.server.tools.search import (
    Codelist,
    CodelistValue,
    SearchResult,
    Variable,
)


class TestSearchTool:
    """Tests for the search tool."""

    def test_search_returns_search_result(self) -> None:
        """Test that search returns a SearchResult object."""
        result = search("HIV")
        assert isinstance(result, SearchResult)
        assert result.query == "HIV"
        assert isinstance(result.search_terms, list)

    def test_search_expands_synonyms(self) -> None:
        """Test that search expands clinical concept synonyms."""
        result = search("relapse")
        assert "relapse" in result.search_terms
        assert any("recur" in term for term in result.search_terms)

    def test_search_returns_variables(self) -> None:
        """Test that search returns Variable objects."""
        result = search("smoking")
        assert isinstance(result.variables, list)
        if result.variables:
            assert isinstance(result.variables[0], Variable)

    def test_search_returns_codelists(self) -> None:
        """Test that search returns Codelist objects."""
        result = search("sex")
        assert isinstance(result.codelists, list)
        if result.codelists:
            assert isinstance(result.codelists[0], Codelist)

    @pytest.mark.parametrize(
        "query",
        ["HIV", "diabetes", "smoking", "outcome", "relapse", "age", "treatment"],
    )
    def test_search_accepts_common_clinical_concepts(self, query: str) -> None:
        """Test that search accepts common clinical concepts."""
        result = search(query)
        assert result.query == query


class TestDatasetHeadersTool:
    """Tests for list_dataset_headers tool."""

    def test_list_dataset_headers_returns_result(self) -> None:
        """Test that list_dataset_headers returns DatasetHeadersResult."""
        from reportalin.server.tools.dataset_headers import DatasetHeadersResult

        result = list_dataset_headers()
        assert isinstance(result, DatasetHeadersResult)
        assert isinstance(result.headers, list)
        assert isinstance(result.total_variables, int)

    def test_list_dataset_headers_with_filter(self) -> None:
        """Test that dataset_name filter works."""
        from reportalin.server.tools.dataset_headers import DatasetHeadersResult

        result = list_dataset_headers(dataset_name="TST")
        assert isinstance(result, DatasetHeadersResult)


class TestCombinedSearchTool:
    """Tests for combined_search tool."""

    def test_combined_search_returns_result(self) -> None:
        """Test that combined_search returns CombinedSearchResult."""
        from reportalin.server.tools.combined_search import CombinedSearchResult

        result = combined_search("HIV")
        assert isinstance(result, CombinedSearchResult)
        assert result.query == "HIV"

    def test_combined_search_has_summary(self) -> None:
        """Test that combined_search includes summary."""
        result = combined_search("diabetes")
        assert result.summary is not None
        assert isinstance(result.formatted_output, str)


class TestMCPServer:
    """Tests for the FastMCP server instance."""

    def test_mcp_instance_exists(self) -> None:
        """Test that MCP server instance exists."""
        assert mcp is not None

    def test_mcp_server_name(self) -> None:
        """Test that MCP server has correct name."""
        assert mcp.name == SERVER_NAME


class TestOutputModels:
    """Tests for Pydantic output models."""

    def test_variable_model(self) -> None:
        """Test Variable model creation."""
        var = Variable(
            field_name="SMOKHX",
            description="Smoking history",
            source_table="tblHISTORY",
        )
        assert var.field_name == "SMOKHX"

    def test_codelist_value_model(self) -> None:
        """Test CodelistValue model creation."""
        val = CodelistValue(code="1", description="Yes")
        assert val.code == "1"

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
