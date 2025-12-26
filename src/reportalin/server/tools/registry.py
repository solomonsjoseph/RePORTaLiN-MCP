"""FastMCP server setup and tool registry for RePORTaLiN.

This module configures the FastMCP server instance and registers:
- 3 MCP tools (prompt_enhancer, combined_search, search_data_dictionary)
- 6 MCP resources (study overview, tables, codelists, etc.)
- 4 MCP prompts (research templates and analysis guides)
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from reportalin.core.constants import SERVER_NAME, SERVER_VERSION
from reportalin.core.config import get_settings
from reportalin.core.logging import get_logger
from reportalin.server.tools._loaders import (
    get_codelists,
    get_data_dictionary,
)
from reportalin.server.tools.combined_search import combined_search
from reportalin.server.tools.prompt_enhancer import prompt_enhancer
from reportalin.server.tools.search_data_dictionary import search_data_dictionary

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
RePORTaLiN MCP Server - Data Dictionary Expert for RePORT India TB Study

This server provides access to the RePORT India (Indo-VAP) tuberculosis cohort study
data dictionary and variable mappings. Find the right variables for your research questions.

RePORT India is a multi-site prospective observational cohort studying TB treatment outcomes,
comorbidities (HIV, diabetes, malnutrition), and risk factors (smoking, alcohol) in India.

## IMPORTANT: Tool Selection Guide

**PRIMARY ENTRY POINT: Use `prompt_enhancer` for ALL user queries.**

The prompt_enhancer tool will:
1. Analyze your question to understand what you're asking
2. Show you how it interpreted your question
3. Wait for your confirmation before executing
4. Route to the appropriate specialized tool automatically

### Workflow:
```
User Query → prompt_enhancer (interprets + confirms) → Appropriate Tool → Results
```

## Available Tools (3 Total)

### PRIMARY TOOL - Use This First

1. **prompt_enhancer** - INTELLIGENT QUERY ROUTER (USE THIS FIRST)
   - Takes ANY vague or specific question
   - Analyzes intent and enhances query for accuracy
   - CRITICAL: Confirms understanding with you BEFORE executing
   - Automatically routes to the right tool
   - USE FOR: ALL user queries - let it figure out what you need

### Specialized Tools (Auto-selected by prompt_enhancer)

2. **combined_search** - DEFAULT for variable discovery
   - Searches data dictionary and codelists
   - Uses intelligent concept synonym mapping
   - USE FOR: "What variables for relapse analysis?", "Diabetes variables", "TB outcomes"
   - Handles most queries automatically

3. **search_data_dictionary** - Direct variable lookup
   - Returns variable definitions, codelists, field names
   - Precise search by variable name or keyword
   - USE FOR: "What variables exist for X?", "What does variable Y mean?"

## Available Resources (6 Total)

- `dictionary://overview` - Study data summary
- `dictionary://tables` - List of all tables
- `dictionary://codelists` - Categorical value definitions
- `dictionary://table/{name}` - Specific table schema
- `dictionary://codelist/{name}` - Specific codelist values
- `study://variables/{category}` - Variables by category

## Available Prompts (4 Total)

- `research_question_template` - How to answer research questions
- `data_exploration_guide` - Step-by-step data exploration
- `statistical_analysis_template` - Conducting statistical analyses
- `tb_outcome_analysis` - TB treatment outcome specific guidance

## RePORT India Study Context

Common research areas:
- TB treatment outcomes (cure, failure, death, loss to follow-up)
- Comorbidities: HIV, diabetes mellitus, malnutrition/undernutrition
- Risk factors: smoking, alcohol use, BMI
- Demographics: age, sex, site
- Follow-up visits: baseline, month 2, 6, 12, 24

## What This Server Provides

- Variable names and descriptions
- Data dictionary field definitions
- Codelist values (valid codes and their meanings)
- CRF form → Database table mappings
- Clinical concept synonym expansion

This server ONLY provides metadata - no patient data or statistics.
"""

mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SYSTEM_INSTRUCTIONS,
    debug=settings.is_local,
    log_level=settings.log_level.value,
)

# =============================================================================
# Register MCP Tools
# =============================================================================

# Register the 3 tools with FastMCP
mcp.tool()(prompt_enhancer)
mcp.tool()(combined_search)
mcp.tool()(search_data_dictionary)


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

TOOL SELECTION GUIDE:
- For ANY question → Start with `prompt_enhancer` (it will route for you)
- For variable discovery → `combined_search` uses concept synonym mapping
- For direct lookup → `search_data_dictionary`

Available Tools (3):
1. prompt_enhancer - INTELLIGENT ROUTER: Analyzes query, confirms with you, routes automatically
2. combined_search - DEFAULT: Searches dictionary and codelists with concept expansion
3. search_data_dictionary - Variable definitions by keyword

Available Resources (6):
- dictionary://overview - This overview
- dictionary://tables - List all tables
- dictionary://codelists - All codelist definitions
- dictionary://table/{{name}} - Specific table schema
- dictionary://codelist/{{name}} - Specific codelist values
- study://variables/{{category}} - Variables by category

Available Prompts (4):
- research_question_template - Research question guidance
- data_exploration_guide - Data exploration steps
- statistical_analysis_template - Statistical analysis patterns
- tb_outcome_analysis - TB outcome specific guidance

This server provides metadata only - no patient data or statistics.
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

## How to Find Variables for Your Research Question

1. **First**, use `prompt_enhancer` with your question
   - It will analyze your query and confirm understanding
   - It will automatically route to the right tool
   - Example: prompt_enhancer(user_query="What variables for HIV analysis?")

2. **Or**, use `combined_search` directly with the relevant clinical concept
   - Example: combined_search(concept="HIV status")

3. **Review** the variable definitions and codelists returned
   - Note variable names, descriptions, and valid codes
   - Check which database tables contain the variables
   - Review codelist values for categorical variables

## Important Guidelines
- This server provides METADATA only (variable definitions, not patient data)
- Use the returned variable names in your analysis plan
- Review codelists to understand valid values for categorical variables
- Note which CRF forms and database tables contain each variable

## Example Workflow
Question: "What variables should I use for HIV analysis?"
1. Use prompt_enhancer(user_query="What variables for HIV analysis?") OR combined_search(concept="HIV")
2. Find HIV-related variables (e.g., HIVSTAT, CD4 counts, ART variables)
3. Review the variable descriptions and codelists
4. Use these variable names in your data analysis
"""


@mcp.prompt()
def data_exploration_guide() -> str:
    """Guide for exploring the available data dictionary."""
    return """# Data Dictionary Exploration Guide for RePORT India Study

## Step 1: Understand Available Variables
- Use resource `dictionary://overview` for data dictionary summary
- Use resource `dictionary://tables` for available tables
- Use resource `dictionary://codelists` for categorical value definitions

## Step 2: Ask Questions About Variables
- Use `prompt_enhancer` for ANY question (it will guide you)
- Example: prompt_enhancer(user_query="What variables are available for smoking?")

## Step 3: Find Specific Variables
- Use `search_data_dictionary(query="your term")` to find fields
- Common searches: "HIV", "diabetes", "smoking", "outcome", "age", "BMI"

## Step 4: Discover Variables by Clinical Concept
- Use `combined_search(concept="topic")` for intelligent concept-based search
- Example: combined_search(concept="relapse") finds variables for relapse analysis

## Tips
- Start with prompt_enhancer - it will interpret and route for you
- Variable names are often abbreviated (e.g., "SMOKHX" for smoking history)
- Check codelists to understand valid codes for categorical variables
- This server provides metadata only - use variable names in your own analysis
"""


@mcp.prompt()
def statistical_analysis_template() -> str:
    """Template for finding variables for statistical analyses."""
    return """# Variable Discovery Template for Analysis Planning

## Finding Variables for Your Analysis

### 1. Demographics
```
prompt_enhancer(user_query="What demographic variables are available?")
# OR
combined_search(concept="demographics")
# Find age, sex, site, enrollment date variables
```

### 2. Clinical Outcomes
```
search_data_dictionary(query="outcome")
# Returns TB outcome variables and their definitions
```

### 3. Risk Factors
```
combined_search(concept="diabetes")
# Find all diabetes-related variables (glucose, HbA1c, diagnosis, etc.)
```

## Common Variable Discovery Patterns

### For Prevalence Studies
```
# Find HIV status variable
combined_search(concept="HIV")
# Review variable names and codelist values
# Use variable names in your analysis code
```

### For Longitudinal Analysis
```
# Find follow-up visit variables
combined_search(concept="follow-up")
# Identify baseline, month 2, 6, 12, 24 variables
```

### For Comorbidity Analysis
```
# Find comorbidity variables
search_data_dictionary(query="comorbid")
# Review all comorbidity fields
```

## Next Steps
- Use the variable names returned to build your analysis dataset
- Review codelists to understand categorical variable coding
- This server provides metadata - conduct actual analysis in your environment
"""


@mcp.prompt()
def tb_outcome_analysis() -> str:
    """Specific prompt for finding TB treatment outcome variables."""
    return """# TB Treatment Outcome Variable Discovery Guide

## Understanding TB Outcomes
The WHO-defined TB treatment outcomes include:
- **Cured**: Culture/smear negative at treatment completion
- **Treatment Completed**: Completed treatment without bacteriological confirmation
- **Treatment Failure**: Positive culture/smear at month 5 or later
- **Died**: Death from any cause during treatment
- **Lost to Follow-up (LTFU)**: Treatment interrupted for ≥2 months
- **Not Evaluated**: No outcome assigned

## Finding Outcome Variables

### 1. Discover outcome variables
```
prompt_enhancer(user_query="What variables capture TB treatment outcomes?")
# OR
combined_search(concept="treatment outcome")
```

### 2. Key outcome variables to look for:
- OUTCLIN: Clinical outcome
- OUTOTH: Other outcome classification
- TB_OUTCOME: Combined outcome
- Look in 'outcome' or 'offstudy' tables

### 3. Review codelist values
```
# Check the codelist for outcome variables
# Review valid codes and their meanings
# Example: 1=Cured, 2=Completed, 3=Failure, 4=Died, 5=LTFU
```

## Using Variables in Your Analysis
- Use the variable names in your dataset queries
- Apply the codelist codes to categorize outcomes
- Group favorable (cure + completed) vs unfavorable outcomes
- This server provides metadata - conduct analysis in your environment
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
        "registered_tools": [
            "prompt_enhancer",  # Primary entry point
            "combined_search",  # DEFAULT for variable discovery
            "search_data_dictionary",  # Direct lookup
        ],
        "registered_resources": [
            # Overview resources
            "dictionary://overview",
            "dictionary://tables",
            "dictionary://codelists",
            # Dynamic resources
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
            "subscriptions": False,
        },
        "server_type": "data_dictionary_expert",
        "tool_count": 3,
        "primary_entry_point": "prompt_enhancer",
    }
