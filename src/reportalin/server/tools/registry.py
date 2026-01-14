"""FastMCP server setup and tool registry for RePORTaLiN.

This module configures the FastMCP server instance and registers:
- 1 MCP tool: search (LLM-powered variable search)
- 6 MCP resources (study overview, tables, codelists, etc.)
- 4 MCP prompts (research templates and analysis guides)

Simple by design - one powerful tool that understands clinical concepts.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from reportalin.core.constants import SERVER_NAME, SERVER_VERSION
from reportalin.core.config import get_settings
from reportalin.logging import get_logger
from reportalin.server.tools._loaders import (
    get_codelists,
    get_data_dictionary,
)
from reportalin.server.tools.search import search

__all__ = [
    "mcp",
    "get_tool_registry",
]

# Initialize logger
logger = get_logger(__name__)

# =============================================================================
# FastMCP Server Instance
# =============================================================================

settings = get_settings()

SYSTEM_INSTRUCTIONS = """
RePORTaLiN MCP Server - LLM-Powered Variable Search for RePORT India TB Study

This server provides intelligent access to the RePORT India (Indo-VAP) tuberculosis 
cohort study data dictionary. Better than SQL search - understands clinical concepts.

## ONE TOOL - Simple & Powerful

**Use `search` for ALL variable discovery queries.**

Examples:
- search("HIV status") → finds HIV, CD4, ART variables
- search("relapse") → finds relapse, recurrence, recur variables  
- search("diabetes") → finds DM, glucose, HbA1c variables
- search("treatment outcome") → finds cure, failure, death variables

## Why Better Than SQL

1. **Understands Concepts**: "relapse" finds "recurrence", "recur", "recurrent"
2. **Clinical Synonyms**: "diabetes" finds "DM", "glucose", "HbA1c", "OGTT"
3. **Structured Output**: Returns field names, descriptions, codelists ready for analysis
4. **Fast**: No complex SQL joins - instant concept-based search

## Available Resources

- `dictionary://overview` - Study data summary
- `dictionary://tables` - List of all tables  
- `dictionary://codelists` - Categorical value definitions
- `dictionary://table/{name}` - Specific table schema
- `dictionary://codelist/{name}` - Specific codelist values
- `study://variables/{category}` - Variables by category

## Study Context (RePORT India)

Multi-site prospective TB cohort studying:
- Treatment outcomes: cure, failure, death, loss to follow-up
- Comorbidities: HIV, diabetes mellitus, malnutrition
- Risk factors: smoking, alcohol, BMI
- Demographics: age, sex, site (Pune, Chennai, Vellore)

This server provides METADATA only - variable definitions and codelists.
"""

mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SYSTEM_INSTRUCTIONS,
    debug=settings.is_local,
    log_level=settings.log_level.value,
)

# =============================================================================
# Register MCP Tool
# =============================================================================

# Register the single powerful search tool
mcp.tool()(search)


# =============================================================================
# MCP Resources
# =============================================================================


@mcp.resource("dictionary://overview")
def get_study_overview() -> str:
    """Overview of the RePORT India study data dictionary."""
    data_dict = get_data_dictionary()
    codelists = get_codelists()

    dict_fields = sum(len(r) for r in data_dict.values())

    return f"""RePORT India (Indo-VAP) Study Data Dictionary

Data Dictionary:
- Tables defined: {len(data_dict)}
- Total fields: {dict_fields}
- Codelists: {len(codelists)}

## ONE TOOL - Simple & Powerful

Use `search` for ALL variable discovery. Examples:
- search("HIV status") → finds HIV, CD4, ART variables
- search("relapse") → finds relapse, recurrence variables
- search("diabetes") → finds DM, glucose, HbA1c variables

## Available Resources

- dictionary://overview - This overview
- dictionary://tables - List all tables
- dictionary://codelists - All codelist definitions
- dictionary://table/{{name}} - Specific table schema
- dictionary://codelist/{{name}} - Specific codelist values
- study://variables/{{category}} - Variables by category

This server provides metadata only - no patient data.
"""


@mcp.resource("dictionary://tables")
def list_tables() -> str:
    """List all available tables in the data dictionary."""
    data_dict = get_data_dictionary()

    output = ["Data Dictionary Tables:"]
    for name, records in sorted(data_dict.items()):
        output.append(f"  - {name}: {len(records)} fields")

    return "\n".join(output)


@mcp.resource("dictionary://codelists")
def list_codelists() -> str:
    """List all available codelists with their values."""
    codelists = get_codelists()

    output = ["Available Codelists:\n"]
    for name, values in sorted(codelists.items()):
        output.append(f"## {name}")
        for v in values[:10]:  # Limit to first 10 values
            code = v.get("Codes", "")
            desc = v.get("Descriptors", "")
            output.append(f"  {code}: {desc}")
        if len(values) > 10:
            output.append(f"  ... and {len(values) - 10} more values")
        output.append("")

    return "\n".join(output)


@mcp.resource("dictionary://table/{table_name}")
def get_table_schema(table_name: str) -> str:
    """Get schema/field definitions for a specific table."""
    data_dict = get_data_dictionary()

    # Find matching table (case-insensitive)
    matched_table = None
    for name in data_dict.keys():
        if table_name.lower() in name.lower():
            matched_table = name
            break

    if not matched_table:
        return f"Table '{table_name}' not found. Use dictionary://tables to see available tables."

    records = data_dict[matched_table]

    output = [f"# Table: {matched_table}\n"]
    output.append(f"Total fields: {len(records)}\n")
    output.append("## Fields:\n")

    for record in records:
        field_name = record.get("Question Short Name (Databank Fieldname)", "Unknown")
        description = record.get("Question", "No description")
        field_type = record.get("Type", "Unknown")
        codelist = record.get("Code List or format", "")

        output.append(f"### {field_name}")
        output.append(f"- Description: {description}")
        output.append(f"- Type: {field_type}")
        if codelist:
            output.append(f"- Codelist/Format: {codelist}")
        output.append("")

    return "\n".join(output)


@mcp.resource("dictionary://codelist/{codelist_name}")
def get_codelist_values(codelist_name: str) -> str:
    """Get values for a specific codelist."""
    codelists = get_codelists()

    # Find matching codelist (case-insensitive)
    matched_codelist = None
    for name in codelists.keys():
        if codelist_name.lower() in name.lower():
            matched_codelist = name
            break

    if not matched_codelist:
        return f"Codelist '{codelist_name}' not found. Use dictionary://codelists to see available codelists."

    values = codelists[matched_codelist]

    output = [f"# Codelist: {matched_codelist}\n"]
    output.append(f"Total values: {len(values)}\n")
    output.append("| Code | Description |")
    output.append("|------|-------------|")

    for v in values:
        code = v.get("Codes", "")
        desc = v.get("Descriptors", "")
        output.append(f"| {code} | {desc} |")

    return "\n".join(output)


@mcp.resource("study://variables/{category}")
def get_variables_by_category(category: str) -> str:
    """Get variables organized by clinical category."""
    data_dict = get_data_dictionary()

    # Category mappings
    category_keywords = {
        "demographics": ["age", "sex", "gender", "site", "birth", "enrol"],
        "comorbidities": ["hiv", "diab", "dm", "glucose", "hba1c"],
        "risk_factors": [
            "smok",
            "tobacco",
            "alcohol",
            "drink",
            "bmi",
            "weight",
            "height",
        ],
        "tb_diagnosis": ["tb", "sputum", "smear", "culture", "xpert", "xray", "cxr"],
        "treatment": ["treat", "regimen", "med", "drug", "dose"],
        "outcomes": ["outcome", "cure", "fail", "death", "ltfu", "off"],
        "laboratory": ["lab", "blood", "test", "cd4", "hemo", "creat"],
        "symptoms": ["symptom", "cough", "fever", "sweat", "weight loss"],
    }

    category_lower = category.lower()
    keywords = category_keywords.get(category_lower, [category_lower])

    output = [f"# Variables related to: {category}\n"]

    found_vars = []
    for table_name, records in data_dict.items():
        for record in records:
            field_name = record.get("Question Short Name (Databank Fieldname)", "")
            description = record.get("Question", "")
            searchable = f"{field_name} {description}".lower()

            if any(kw in searchable for kw in keywords):
                found_vars.append(
                    {
                        "table": table_name,
                        "field": field_name,
                        "description": description,
                        "type": record.get("Type", ""),
                    }
                )

    if not found_vars:
        output.append(f"No variables found for category '{category}'.\n")
        output.append("Available categories: " + ", ".join(category_keywords.keys()))
    else:
        output.append(f"Found {len(found_vars)} variables:\n")
        for var in found_vars[:50]:  # Limit output
            output.append(f"- **{var['field']}** ({var['table']})")
            output.append(f"  {var['description']}")

    return "\n".join(output)


# =============================================================================
# MCP Prompts
# =============================================================================


@mcp.prompt()
def research_question_template() -> str:
    """Template prompt for finding variables for research questions about the TB cohort."""
    return """You are accessing the RePORT India TB cohort study data dictionary through a secure MCP server.

## Study Background
RePORT India (Indo-VAP) is a multi-site prospective observational cohort studying:
- TB treatment outcomes (cure, failure, death, loss to follow-up)
- Comorbidities (HIV, diabetes mellitus)
- Risk factors (smoking, alcohol, malnutrition/BMI)
- Demographics across multiple sites in India

## How to Find Variables

Use `search` with your clinical concept:
- search("HIV") → finds HIV status, CD4, ART variables
- search("diabetes") → finds DM, glucose, HbA1c variables
- search("outcome") → finds treatment outcome variables

## Example Workflow
Question: "What variables should I use for HIV analysis?"
1. search("HIV")
2. Review returned variables (HIVSTAT, CD4, etc.)
3. Check codelist values for categorical variables
4. Use variable names in your analysis

## Important
- This server provides METADATA only (variable definitions, not patient data)
- Use returned variable names in your analysis plan
- Review codelists to understand valid values
"""


@mcp.prompt()
def data_exploration_guide() -> str:
    """Guide for exploring the available data dictionary."""
    return """# Data Dictionary Exploration Guide for RePORT India Study

## Step 1: Understand Available Data
- Use resource `dictionary://overview` for summary
- Use resource `dictionary://tables` for available tables
- Use resource `dictionary://codelists` for categorical values

## Step 2: Search for Variables
Use `search` with clinical concepts:
- search("smoking") → finds smoking-related variables
- search("relapse") → finds relapse, recurrence variables
- search("age") → finds age, demographics variables

## Tips
- Variable names are often abbreviated (e.g., "SMOKHX" for smoking history)
- Check codelists to understand valid codes
- This server provides metadata only - use variable names in your analysis
"""


@mcp.prompt()
def statistical_analysis_template() -> str:
    """Template for finding variables for statistical analyses."""
    return """# Variable Discovery Template for Analysis Planning

## Finding Variables for Your Analysis

### Demographics
```
search("demographics")
# Returns age, sex, site, enrollment variables
```

### Clinical Outcomes
```
search("outcome")
# Returns TB outcome variables and codelists
```

### Risk Factors
```
search("diabetes")
# Returns glucose, HbA1c, diagnosis variables
```

### Comorbidities
```
search("HIV")
# Returns HIV status, CD4, ART variables
```

## Next Steps
- Use variable names in your dataset queries
- Review codelists for categorical variable coding
- This server provides metadata only
"""


@mcp.prompt()
def tb_outcome_analysis() -> str:
    """Specific prompt for finding TB treatment outcome variables."""
    return """# TB Treatment Outcome Variable Discovery Guide

## WHO-Defined TB Treatment Outcomes
- **Cured**: Culture/smear negative at treatment completion
- **Treatment Completed**: Completed without bacteriological confirmation
- **Treatment Failure**: Positive culture/smear at month 5+
- **Died**: Death from any cause during treatment
- **Lost to Follow-up (LTFU)**: Interrupted ≥2 months
- **Not Evaluated**: No outcome assigned

## Finding Outcome Variables
```
search("treatment outcome")
# Returns OUTCLIN, OUTOTH, TB_OUTCOME variables
```

## Using Variables
- Use variable names in dataset queries
- Apply codelist codes (e.g., 1=Cured, 2=Completed, 3=Failure)
- Group favorable (cure + completed) vs unfavorable outcomes
"""


# =============================================================================
# Tool Registry
# =============================================================================


def get_tool_registry() -> dict[str, Any]:
    """Get summary of registered tools, resources, and prompts."""
    data_dict = get_data_dictionary()
    codelists = get_codelists()

    return {
        "server_name": SERVER_NAME,
        "version": SERVER_VERSION,
        "registered_tools": ["search"],  # One powerful tool
        "registered_resources": [
            "dictionary://overview",
            "dictionary://tables",
            "dictionary://codelists",
            "dictionary://table/{table_name}",
            "dictionary://codelist/{codelist_name}",
            "study://variables/{category}",
        ],
        "registered_prompts": [
            "research_question_template",
            "data_exploration_guide",
            "statistical_analysis_template",
            "tb_outcome_analysis",
        ],
        "data_loaded": {
            "dictionary_tables": len(data_dict),
            "dictionary_fields": sum(len(r) for r in data_dict.values()),
            "codelists": len(codelists),
        },
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": True,
        },
        "server_type": "llm_powered_variable_search",
        "tool_count": 1,
    }
