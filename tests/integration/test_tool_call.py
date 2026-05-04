"""
Test actual tool calls to verify the MCP server works end-to-end.

This is an integration test that verifies complete MCP tool functionality.
Run with: pytest tests/integration/ -m integration

Tests cover the 2 implemented MCP tools:
- explore_study_metadata: High-level feasibility queries
- build_technical_request: Data extraction concept sheets

Security constraints are enforced:
- NO access to ./data/dataset/ (raw PHI)
- ALL responses are de-identified
- Zero-Trust output policy
"""

import pytest

from server.tools import (
    BuildTechnicalRequestInput,
    ExploreStudyMetadataInput,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.mcp,
    pytest.mark.asyncio,
]


# =============================================================================
# explore_study_metadata Tool Tests
# =============================================================================


async def test_explore_metadata_variable_check():
    """Test explore_study_metadata for variable availability."""

    from server.tools import explore_study_metadata

    input_data = ExploreStudyMetadataInput(
        query="Do we have CD4 counts available in the study?",
    )

    # Create a mock context
    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await explore_study_metadata(input_data, MockContext())

    assert result["success"] is True
    assert "query_type" in result
    assert "results" in result
    assert result["data_available"] is True


async def test_explore_metadata_site_query():
    """Test explore_study_metadata for site information."""
    from server.tools import explore_study_metadata

    input_data = ExploreStudyMetadataInput(
        query="What study sites are available?",
        site_filter="Pune",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await explore_study_metadata(input_data, MockContext())

    assert result["success"] is True
    assert result["query_type"] == "site_info"
    assert "results" in result


async def test_explore_metadata_enrollment_stats():
    """Test explore_study_metadata for enrollment statistics."""
    from server.tools import explore_study_metadata

    input_data = ExploreStudyMetadataInput(
        query="How many participants are enrolled in the study?",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await explore_study_metadata(input_data, MockContext())

    assert result["success"] is True
    assert result["query_type"] == "enrollment_stats"
    assert "results" in result


async def test_explore_metadata_time_points():
    """Test explore_study_metadata for time point information."""
    from server.tools import explore_study_metadata

    input_data = ExploreStudyMetadataInput(
        query="What follow-up time points are collected?",
        time_point_filter="Month 24",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await explore_study_metadata(input_data, MockContext())

    assert result["success"] is True
    assert result["query_type"] == "time_point_info"


async def test_explore_metadata_rejects_forbidden_access():
    """Test that explore_study_metadata rejects forbidden path access."""
    with pytest.raises(ValueError, match="SECURITY"):
        ExploreStudyMetadataInput(
            query="Read data from data/dataset/Indo-vap_csv_files",
        )


async def test_explore_metadata_rejects_phi_request():
    """Test that explore_study_metadata rejects PHI requests."""
    with pytest.raises(ValueError, match="metadata only"):
        ExploreStudyMetadataInput(
            query="Show me all patient names in the database",
        )


# =============================================================================
# build_technical_request Tool Tests
# =============================================================================


async def test_build_request_concept_sheet():
    """Test build_technical_request for concept sheet generation."""
    from server.tools import build_technical_request

    input_data = BuildTechnicalRequestInput(
        description="Analyze treatment outcomes in TB patients with diabetes",
        inclusion_criteria=["Age 18-65", "Pulmonary TB", "Diabetes"],
        exclusion_criteria=["HIV co-infection", "MDR-TB"],
        variables_of_interest=["Age", "Sex", "Diabetes", "Treatment_Outcome"],
        time_points=["Baseline", "Month 6", "Month 12"],
        output_format="concept_sheet",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await build_technical_request(input_data, MockContext())

    assert result["success"] is True
    assert "request_id" in result
    assert result["request_id"].startswith("REQ-")
    assert "output" in result
    assert result["output_format"] == "concept_sheet"
    assert "variable_mapping" in result
    assert "next_steps" in result


async def test_build_request_query_logic():
    """Test build_technical_request for query logic generation."""
    from server.tools import build_technical_request

    input_data = BuildTechnicalRequestInput(
        description="Generate selection criteria for female participants",
        inclusion_criteria=["Female", "Age 18-45"],
        variables_of_interest=["Age", "Sex", "BMI"],
        output_format="query_logic",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await build_technical_request(input_data, MockContext())

    assert result["success"] is True
    assert result["output_format"] == "query_logic"
    assert "output" in result
    assert "query_logic" in result["output"]
    assert "pseudocode" in result["output"]


async def test_build_request_minimal():
    """Test build_technical_request with minimal input."""
    from server.tools import build_technical_request

    input_data = BuildTechnicalRequestInput(
        description="Compare demographics across study sites",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await build_technical_request(input_data, MockContext())

    assert result["success"] is True
    assert "request_id" in result
    assert "output" in result


async def test_build_request_variable_mapping():
    """Test that build_technical_request maps variables correctly."""
    from server.tools import build_technical_request

    input_data = BuildTechnicalRequestInput(
        description="Extract TB treatment outcome data",
        variables_of_interest=["age", "sex", "hiv", "cd4"],
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await build_technical_request(input_data, MockContext())

    assert result["success"] is True
    assert "variable_mapping" in result
    # Should have mapped at least some variables
    mapping = result["variable_mapping"]
    assert len(mapping) > 0


async def test_build_request_rejects_forbidden_access():
    """Test that build_technical_request rejects forbidden path access."""
    with pytest.raises(ValueError, match="SECURITY"):
        BuildTechnicalRequestInput(
            description="Access the raw dataset in data/dataset folder",
        )


# =============================================================================
# Security Integration Tests
# =============================================================================


async def test_output_sanitization():
    """Test that outputs are properly sanitized."""
    from server.tools import explore_study_metadata

    input_data = ExploreStudyMetadataInput(
        query="What data domains are available in the study?",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await explore_study_metadata(input_data, MockContext())

    assert result["success"] is True

    # Verify no sensitive fields in output
    result_str = str(result).lower()
    sensitive_terms = ["ssn", "aadhaar", "phone", "email", "address"]
    for term in sensitive_terms:
        # If present, should be REDACTED
        if term in result_str:
            assert "redacted" in result_str


async def test_no_raw_phi_in_responses():
    """Test that no raw PHI appears in any response."""
    from server.tools import explore_study_metadata

    input_data = ExploreStudyMetadataInput(
        query="What is the feasibility of studying TB outcomes?",
    )

    class MockContext:
        async def info(self, msg: str) -> None:
            pass

    result = await explore_study_metadata(input_data, MockContext())

    assert result["success"] is True
    assert "note" in result
    # Should mention de-identified or no patient-level data
    assert (
        "patient-level" in result["note"].lower()
        or "de-identified" in result["source"].lower()
    )
