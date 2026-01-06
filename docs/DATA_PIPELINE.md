# Data Pipeline Architecture

<!--
Document Type: Explanation (Diátaxis)
Target Audience: Developers understanding the data flow
Prerequisites: Basic understanding of data processing pipelines
-->

> **Type**: Explanation | **Updated**: 2026-01-06 | **Status**: ✅ Production Ready

**Related Documentation:**
- [MCP Server Setup](MCP_SERVER_SETUP.md) — Server integration guide
- [Configuration Reference](CONFIGURATION.md) — Environment variables
- [Testing Guide](TESTING_GUIDE.md) — Verification and testing

---

## Overview

The RePORTaLiN-Agent implements a data dictionary service for querying RePORT India clinical study metadata via MCP (Model Context Protocol):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE FLOW                                  │
│                                                                             │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                 │
│    │   EXTRACT   │ ──► │  DICTIONARY │ ──► │     MCP     │                 │
│    │             │     │   MAPPING   │     │   ACCESS    │                 │
│    │ Excel→JSONL │     │   Results   │     │    Tools    │                 │
│    └─────────────┘     └─────────────┘     └─────────────┘                 │
│                                                                             │
│    data/dataset/       results/             server/                        │
│    *.xlsx              data_dictionary_     tools.py                        │
│                        mappings/                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Pipeline Stages

### Stage 1: Data Extraction

Converts raw Excel files to JSONL format:

- **Input**: `data/dataset/Indo-vap_csv_files/*.xlsx`
- **Output**: `results/dataset/{name}/original/` and `results/dataset/{name}/cleaned/`
- **Features**:
  - Type conversion (dates, numbers, NaN handling)
  - Duplicate column removal
  - Progress tracking with integrity checks

### Stage 2: Dictionary Mapping

Creates data dictionary from annotations and mappings:

- **Input**: `data/Annotated_PDFs/` and mapping specifications
- **Output**: `results/data_dictionary_mappings/`
- **Features**:
  - Variable name extraction
  - Codelist mapping
  - Table relationship mapping
  - Metadata generation

### Stage 3: MCP Access

Provides query interface via MCP tools:

- **Input**: `results/data_dictionary_mappings/`
- **Output**: JSON responses via MCP tools
- **Features**:
  - Variable discovery
  - Codelist lookup
  - Table schema queries
  - Audit logging for compliance

## MCP Tools (v0.3.0 - Data Dictionary Expert)

This server provides **3 tools** for metadata lookup ONLY. NO patient data or statistics.

### All Tools (3 Total)

| Tool | Purpose | Returns |
|------|---------|---------|
| `prompt_enhancer` | **PRIMARY** - Intelligent router with confirmation | Routed to appropriate tool |
| `combined_search` | **DEFAULT** - Variable discovery with concept expansion | Variable names, descriptions, tables, codelists |
| `search_data_dictionary` | Direct variable lookup by keyword | Variable definitions, codelists |

**What This Server Does:**
- ✅ Variable discovery for research questions
- ✅ Returns: Variable names, descriptions, tables, codelists
- ❌ NO patient data, NO statistics, NO dataset access

## Quick Start

```bash
# 1. Extract data and build dictionary
uv run python -m reportalin.cli.main

# 2. Start the MCP server
uv run python -m reportalin.server.main

# 3. Run the example client
uv run python examples/client/query_clinical_data.py
```

## Directory Structure

```
RePORTaLiN-Agent/
├── data/
│   ├── Annotated_PDFs/             # Annotated CRFs (INPUT)
│   │   └── Annotated CRFs - Indo-VAP/
│   ├── dataset/
│   │   └── Indo-vap_csv_files/     # Raw Excel files (INPUT)
│   │       ├── 1A_ICScreening.xlsx
│   │       ├── 2A_ICBaseline.xlsx
│   │       └── ...
│   └── data_dictionary_and_mapping_specifications/
│       └── RePORT_DEB_to_Tables_mapping.xlsx
├── results/
│   ├── dataset/
│   │   └── Indo-vap/               # Extracted JSONL
│   │       ├── original/
│   │       └── cleaned/
│   ├── data_dictionary_mappings/   # Data dictionary JSONL (MCP reads from here)
│   │   ├── tblDEMOG/
│   │   ├── tblHISTORY/
│   │   └── ...
│   └── metadata_summary.json       # Generated metadata
├── src/reportalin/
│   ├── data/                       # Data processing modules
│   ├── server/                     # MCP server
│   │   └── tools/                  # MCP tools (v0.3.0 - 3 tools)
│   │       ├── combined_search.py  # Variable discovery
│   │       ├── prompt_enhancer.py  # Intelligent router
│   │       └── search_data_dictionary.py
│   └── cli/                        # Command-line interface
└── docker/                         # Docker deployment
```

## Compliance

- **ICMR Guidelines 2017**: National Ethical Guidelines for Biomedical Research
- **Audit Logging**: All MCP tool access is logged
- **Data Dictionary Only**: No patient-level data is exposed via MCP tools

## Development Workflow

1. **Data Preparation**: Place Excel files in `data/dataset/`
2. **Extract & Map**: Run CLI to generate dictionaries
3. **Verify**: Check `results/data_dictionary_mappings/`
4. **Test Server**: Start MCP server and test with example client
5. **Deploy**: Use Docker for production deployment
