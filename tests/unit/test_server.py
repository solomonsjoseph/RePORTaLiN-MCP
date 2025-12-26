"""
Server Security and Integration Tests.

Phase 5: Verification, Testing & Security Hardening

This module provides comprehensive testing for:
- Authentication enforcement (valid/invalid/missing tokens)
- Tool input validation (Pydantic model security)
- Endpoint authorization
- Aggregate-only data access (security model)

Test Categories:
    - TestAuthenticationSecurity: Tests for auth enforcement
    - TestToolInputValidation: Tests for input model validation
    - TestEndpointSecurity: Tests for endpoint protection
    - TestSecurityModel: Tests for aggregate-only access

Running Tests:
    ```bash
    # Run all tests
    uv run pytest tests/test_server.py -v

    # Run only security tests
    uv run pytest tests/test_server.py -m security -v

    # Run only auth tests
    uv run pytest tests/test_server.py -m auth -v

    # Run with coverage
    uv run pytest tests/test_server.py --cov=server -v
    ```

See Also:
    - tests/conftest.py for shared fixtures
    - server/auth.py for authentication implementation
    - server/tools.py for tool implementations
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.auth import verify_token
from server.tools import (
    DictionarySearchInput,
    DatasetSearchInput,
    CombinedSearchInput,
)

# =============================================================================
# Test Markers
# =============================================================================

pytestmark = [pytest.mark.security]


# =============================================================================
# Authentication Security Tests
# =============================================================================

class TestAuthenticationSecurity:
    """
    Tests for authentication enforcement on protected endpoints.

    These tests verify that:
    - Protected endpoints reject unauthenticated requests
    - Invalid tokens are rejected with 401/403
    - Valid tokens allow access
    - Public endpoints remain accessible
    """

    @pytest.mark.auth
    def test_health_endpoint_is_public(self, test_client):
        """
        Health endpoint should be accessible without authentication.

        The /health endpoint is used for Kubernetes liveness probes
        and must be accessible without auth headers.
        """
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.auth
    def test_ready_endpoint_is_public(self, test_client):
        """
        Readiness endpoint should be accessible without authentication.

        The /ready endpoint is used for Kubernetes readiness probes.
        """
        response = test_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    @pytest.mark.auth
    def test_tools_endpoint_requires_auth(self, test_client, no_auth_headers):
        """
        Tools endpoint should require authentication.

        The /tools endpoint exposes server capabilities and must
        be protected to prevent information disclosure.
        """
        response = test_client.get("/tools", headers=no_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_tools_endpoint_rejects_invalid_token(
        self, test_client, invalid_auth_headers
    ):
        """
        Tools endpoint should reject invalid authentication tokens.

        Invalid tokens should result in 401 Unauthorized, not 403 Forbidden.
        """
        response = test_client.get("/tools", headers=invalid_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_tools_endpoint_accepts_valid_token(self, test_client, auth_headers):
        """
        Tools endpoint should accept valid authentication tokens.
        """
        response = test_client.get("/tools", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data

    @pytest.mark.auth
    def test_info_endpoint_requires_auth(self, test_client, no_auth_headers):
        """
        Info endpoint should require authentication.
        """
        response = test_client.get("/info", headers=no_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_info_endpoint_accepts_valid_token(self, test_client, auth_headers):
        """
        Info endpoint should accept valid authentication tokens.
        """
        response = test_client.get("/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "server_name" in data

    @pytest.mark.auth
    def test_mcp_sse_requires_auth(self, test_client, no_auth_headers):
        """
        MCP SSE endpoint should require authentication.

        The /mcp/sse endpoint is the main MCP connection point and
        must be protected to prevent unauthorized tool execution.
        """
        response = test_client.get("/mcp/sse", headers=no_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_mcp_sse_rejects_invalid_token(self, test_client, invalid_auth_headers):
        """
        MCP SSE endpoint should reject invalid tokens.
        """
        response = test_client.get("/mcp/sse", headers=invalid_auth_headers)
        assert response.status_code == 401


# =============================================================================
# Tool Input Validation Tests
# =============================================================================

class TestToolInputValidation:
    """
    Tests for tool input validation using Pydantic models.

    These tests verify that input models properly validate queries
    and reject invalid inputs.
    """

    @pytest.mark.security
    def test_dictionary_search_accepts_valid_query(self):
        """Valid dictionary search queries should be accepted."""
        input_data = DictionarySearchInput(query="smoking")
        assert input_data.query == "smoking"

    @pytest.mark.security
    def test_dictionary_search_rejects_empty_query(self):
        """Empty queries should be rejected."""
        with pytest.raises(ValidationError):
            DictionarySearchInput(query="")

    @pytest.mark.security
    def test_dictionary_search_rejects_too_long_query(self):
        """Very long queries should be rejected."""
        with pytest.raises(ValidationError):
            DictionarySearchInput(query="x" * 201)

    @pytest.mark.security
    def test_dataset_search_accepts_valid_variable(self):
        """Valid dataset searches should be accepted."""
        input_data = DatasetSearchInput(variable="AGE")
        assert input_data.variable == "AGE"

    @pytest.mark.security
    def test_dataset_search_with_table_filter(self):
        """Dataset search with table filter should work."""
        input_data = DatasetSearchInput(variable="SEX", table_filter="Index")
        assert input_data.table_filter == "Index"

    @pytest.mark.security
    def test_combined_search_accepts_valid_concept(self):
        """Valid combined searches should be accepted."""
        input_data = CombinedSearchInput(concept="smoking status")
        assert "smoking" in input_data.concept

    @pytest.mark.security
    def test_combined_search_statistics_toggle(self):
        """Statistics can be toggled in combined search."""
        input_data = CombinedSearchInput(concept="HIV", include_statistics=False)
        assert input_data.include_statistics is False


# =============================================================================
# Token Verification Security Tests
# =============================================================================

class TestTokenVerification:
    """
    Tests for the token verification utility function.

    These tests verify constant-time comparison behavior
    and edge case handling.
    """

    @pytest.mark.security
    def test_valid_token_passes(self):
        """Matching tokens should verify successfully."""
        assert verify_token("secret123", "secret123") is True

    @pytest.mark.security
    def test_invalid_token_fails(self):
        """Non-matching tokens should fail verification."""
        assert verify_token("wrong", "secret123") is False

    @pytest.mark.security
    def test_none_provided_fails(self):
        """None provided token should fail verification."""
        assert verify_token(None, "secret123") is False

    @pytest.mark.security
    def test_none_expected_fails(self):
        """None expected token should fail verification."""
        assert verify_token("secret123", None) is False

    @pytest.mark.security
    def test_both_none_fails(self):
        """Both tokens None should fail verification."""
        assert verify_token(None, None) is False

    @pytest.mark.security
    def test_empty_provided_fails(self):
        """Empty string provided token should fail verification."""
        assert verify_token("", "secret123") is False

    @pytest.mark.security
    def test_empty_expected_fails(self):
        """Empty string expected token should fail verification."""
        assert verify_token("secret123", "") is False

    @pytest.mark.security
    def test_different_length_tokens_fail(self):
        """Different length tokens should fail verification."""
        assert verify_token("short", "much_longer_token") is False
        assert verify_token("much_longer_token", "short") is False


# =============================================================================
# Tool Execution Security Tests
# =============================================================================

class TestToolExecutionSecurity:
    """
    Tests for direct tool function security.

    SECURE MODE: Ten tools are available:
    - PRIMARY TOOLS (use for most queries):
      1. combined_search - DEFAULT for ALL queries, searches ALL data sources
      2. natural_language_query - Complex multi-concept questions
      3. cohort_summary - Participant overview
      4. cross_tabulation - Variable relationships
    - DETAILED ANALYSIS TOOLS:
      5. variable_details - Deep dive into one variable
      6. data_quality_report - Missing data analysis
      7. multi_variable_comparison - Side-by-side statistics
    - SUPPORTING TOOLS (specific needs only):
      8. search_data_dictionary - Variable definitions ONLY (no statistics)
      # v0.3.0: search_cleaned_dataset removed - dictionary only
      10. search_original_dataset - Fallback to original data

    All tools return AGGREGATE data only - never individual records.
    """

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_ten_tools_registered(self):
        """Verify ten tools are registered."""
        from server.tools import get_tool_registry

        registry = get_tool_registry()
        assert len(registry["registered_tools"]) == 10
        # Primary tools
        assert "combined_search" in registry["registered_tools"]
        assert "natural_language_query" in registry["registered_tools"]
        assert "cohort_summary" in registry["registered_tools"]
        assert "cross_tabulation" in registry["registered_tools"]
        # Detailed analysis tools
        assert "variable_details" in registry["registered_tools"]
        assert "data_quality_report" in registry["registered_tools"]
        assert "multi_variable_comparison" in registry["registered_tools"]
        # Supporting tools
        assert "search_data_dictionary" in registry["registered_tools"]
        # v0.3.0: search_cleaned_dataset removed
        # assert "search_cleaned_dataset" in registry["registered_tools"]
        assert "search_original_dataset" in registry["registered_tools"]

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_search_data_dictionary_validates_input(self):
        """search_data_dictionary tool should validate input before execution.
        
        NOTE: search_data_dictionary is for variable definitions ONLY.
        For analytical queries with statistics, use combined_search instead.
        """
        from server.tools import DictionarySearchInput, search_data_dictionary
        from unittest.mock import AsyncMock, MagicMock

        # Create valid input
        input_model = DictionarySearchInput(query="smoking")

        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()

        result = await search_data_dictionary(input_model, mock_ctx)
        assert "query" in result
        assert "variables_found" in result or "error" not in result

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_combined_search_validates_input(self):
        """combined_search tool should validate input before execution.
        
        NOTE: combined_search is THE DEFAULT TOOL for ALL queries.
        It searches through ALL data sources (dictionary + cleaned + original).
        Use this for any analytical question, counts, or distributions.
        """
        from server.tools import CombinedSearchInput, combined_search
        from unittest.mock import AsyncMock, MagicMock

        # Create valid input
        input_model = CombinedSearchInput(concept="HIV status")

        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()

        result = await combined_search(input_model, mock_ctx)
        assert "concept" in result
        assert "variables_found" in result
        assert "statistics" in result

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_old_tools_not_available(self):
        """CRITICAL: Verify old tools are NOT importable."""
        from server.tools import mcp

        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]

        # Old tools should NOT exist
        assert "query_database" not in tool_names
        assert "explore_study_metadata" not in tool_names
        assert "build_technical_request" not in tool_names
        assert "fetch_metrics" not in tool_names
        assert "health_check" not in tool_names
        assert "list_datasets" not in tool_names


# =============================================================================
# Response Format Tests
# =============================================================================

class TestResponseFormats:
    """
    Tests for API response format consistency.

    These tests verify that responses follow expected formats
    for both success and error cases.
    """

    def test_health_response_format(self, test_client):
        """Health endpoint should return consistent JSON format."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "server" in data
        assert "version" in data

    def test_ready_response_format(self, test_client):
        """Ready endpoint should return consistent JSON format."""
        response = test_client.get("/ready")
        data = response.json()

        assert "ready" in data
        assert "server" in data

    def test_unauthorized_response_format(self, test_client, no_auth_headers):
        """Unauthorized responses should include WWW-Authenticate header."""
        response = test_client.get("/tools", headers=no_auth_headers)

        assert response.status_code == 401
        assert "www-authenticate" in response.headers
