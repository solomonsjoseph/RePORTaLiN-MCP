# MCP Implementation Plan for RePORT India Clinical Study Data

> **⚠️ ARCHIVE NOTICE**: This document contains historical planning information and may reference deprecated features (e.g., deidentification). For current architecture, see [DATA_PIPELINE.md](DATA_PIPELINE.md) and [MCP_SERVER_SETUP.md](MCP_SERVER_SETUP.md).

<!--
Document Type: Explanation (Diátaxis)
Target Audience: Project managers, architects, and developers
Prerequisites: Understanding of MCP protocol and clinical data requirements
-->

> **Type**: Explanation | **Updated**: 2025-12-08 | **Status**: 📚 Archived  
> **Study**: RePORT India (Regional Prospective Observational Research for Tuberculosis)  
> **Primary Regulation**: DPDPA 2023 (Digital Personal Data Protection Act) + DPDP Rules 2025

**Related Documentation:**
- [MCP Server Setup](MCP_SERVER_SETUP.md) — Server integration guide
- [Data Pipeline](DATA_PIPELINE.md) — Data flow architecture
- [Configuration Reference](CONFIGURATION.md) — Environment variables

---

## Executive Summary

This document outlines the implementation plan for a production-ready MCP (Model Context Protocol) setup for querying **RePORT India** clinical study data. The RePORT India consortium is a multi-site tuberculosis research study conducted across India, generating longitudinal clinical data including TB screening, diagnostics, treatment outcomes, and biomarker data.

The plan aligns with:
- **Indian Regulations**: DPDPA 2023, DPDP Rules 2025, ICMR National Ethical Guidelines 2017
- **International Standards**: CDISC SDTM, ICH-GCP E6(R2)
- **Technical Standards**: MCP Protocol 2025-03-26

### RePORT India Study Overview

| Attribute | Details |
|-----------|---------|
| **Study Name** | Regional Prospective Observational Research for Tuberculosis - India |
| **Acronym** | RePORT India |
| **Study Type** | Multi-site prospective observational cohort |
| **Primary Outcome** | TB disease progression, treatment outcomes |
| **Sites** | Multiple sites across India (NIRT Chennai, BJGMC Pune, etc.) |
| **Data Types** | Demographics, Clinical assessments, Lab results (TST, IGRA, Culture, Smear), Imaging (CXR), Biospecimens |
| **Regulatory Framework** | DPDPA 2023, ICMR Guidelines, CDSCO regulations |

---

## Current State Analysis

### ✅ Already Implemented

Based on workspace analysis, the following components are **already in place**:

| Component | Status | Location |
|-----------|--------|----------|
| MCP Server Core | ✅ Complete | `server/main.py`, `server/tools.py` |
| FastMCP Integration | ✅ Complete | Using `mcp[cli]>=1.0.0` |
| Bearer Token Auth | ✅ Complete | `server/auth.py` |
| AES-256-GCM Encryption | ✅ Complete | `server/security/encryption.py` |
| De-identification Engine | ✅ Complete | `scripts/deidentify.py` |
| Data Extraction | ✅ Complete | `scripts/extract_data.py` |
| Universal Client Adapter | ✅ Complete | `client/universal_client.py` |
| Data Dictionary Loader | ✅ Complete | `scripts/load_dictionary.py` |
| K-Anonymity Enforcement | ✅ Complete | `MIN_K_ANONYMITY = 5` |
| Docker Deployment | ✅ Complete | `Dockerfile`, `docker-compose.yml` |
| **Data Pipeline Connector** | ✅ Complete | `server/data_pipeline.py` |
| **3-Tool MCP Design (v0.3.0)** | ✅ Complete | Data Dictionary Expert - metadata only |
| **Variable Discovery** | ✅ Complete | Via `combined_search` with concept expansion |

### Core Data Pipeline Flow ✅

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CORE PIPELINE (Fully Implemented)                        │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │  EXTRACTION  │ →  │ DE-IDENTIFY  │ →  │   RESULTS    │ →  │MCP ACCESS │ │
│  │              │    │              │    │              │    │           │ │
│  │ Excel→JSONL │    │ PHI Removal  │    │ Clean Data   │    │ Tools API │ │
│  │ extract_    │    │ deidentify.py│    │ results/     │    │ tools.py  │ │
│  │ data.py     │    │              │    │ deidentified/│    │           │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│                                                                             │
│  Run: python main.py --enable-deidentification                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pipeline Components:**

| Stage | Script | Input | Output |
|-------|--------|-------|--------|
| 1. Extraction | `scripts/extract_data.py` | `data/dataset/*.xlsx` | `results/dataset/{name}/` |
| 2. De-identification | `scripts/deidentify.py` | `results/dataset/` | `results/deidentified/{name}/` |
| 3. MCP Access | `server/data_pipeline.py` | `results/deidentified/` | JSON via MCP tools |

### 🔄 Optional Enhancements

| Component | Gap | Priority |
|-----------|-----|----------|
| CDISC/OMOP Standardization | Data validation layer | Medium |
| Audit Log Aggregation | Enhanced compliance logging | Medium |
| FHIR Resource Mapping | Healthcare interoperability | Low |

---

## Implementation Phases

### Phase 1: Data Preparation & Security (Week 1-2)

#### 1.1 Clean and Standardize RePORT India Data

```
Priority: HIGH | Effort: Medium | Dependencies: None
```

**RePORT India Dataset Structure (Indo-VAP Study):**

The Indo-VAP (India Vitamin D and Albumin Profiling) dataset contains 42 Excel files organized by clinical domain:

| Domain | Files | Description |
|--------|-------|-------------|
| **Screening** | `1A_ICScreening`, `1B_HCScreening` | Index Case & Household Contact screening |
| **Demographics** | `2A_ICBaseline`, `2B_HCBaseline` | Baseline demographics for IC/HC |
| **Laboratory** | `4_Smear`, `5_CBC`, `6_HIV`, `7_Culture`, `10_TST`, `11_IGRA` | TB diagnostics, blood work |
| **Imaging** | `8_CXR` | Chest X-Ray findings |
| **Follow-up** | `12A_FUA`, `12B_FUB`, `98A_FOA`, `98B_FOB` | Longitudinal follow-up visits |
| **Treatment** | `13_TxCompliance` | Treatment adherence |
| **Adverse Events** | `95_SAE` | Serious adverse events |
| **Specimens** | `3_Specimen_Collection`, `15_Feces`, `96_Specimen_Tracking` | Biospecimen collection |

**Tasks:**
1. Create data validation schema for RePORT India CRF variables
2. Implement CDISC SDTM validators (TB-specific domains)
3. Map Indian identifiers (Aadhaar, ABHA) for de-identification
4. Add quality checks for TB diagnostic variables (Smear grading, Culture results)

**Files to Create/Modify:**

```
scripts/
├── data_standards/
│   ├── __init__.py
│   ├── report_india_validator.py  # NEW: RePORT India CRF validation
│   ├── cdisc_tb_domains.py        # NEW: TB-specific CDISC domains
│   └── indian_identifiers.py      # NEW: Aadhaar, PAN, ABHA patterns
```

**Implementation:**

```python
# scripts/data_standards/report_india_validator.py
from pydantic import BaseModel, field_validator
from typing import Literal, Optional
from datetime import date

class RePORTIndiaSubject(BaseModel):
    """
    RePORT India subject validation.
    
    Follows ICMR National Ethical Guidelines 2017 requirements
    for clinical research data handling.
    """
    # Subject identifiers (to be pseudonymized)
    subject_id: str           # Study-assigned ID (e.g., "NIRT-2023-001")
    site_code: str            # Site identifier (NIRT, BJGMC, etc.)
    
    # Demographics (age groups for k-anonymity)
    age_years: int
    sex: Literal["M", "F", "O"]
    
    # TB-specific
    tb_status: Literal["IC", "HC", "Control"]  # Index Case, Household Contact
    
    @field_validator('site_code')
    @classmethod
    def validate_indian_site(cls, v):
        """Validate RePORT India consortium sites."""
        valid_sites = [
            'NIRT',    # National Institute for Research in Tuberculosis, Chennai
            'BJGMC',   # B.J. Government Medical College, Pune
            'JHU',     # Johns Hopkins collaboration site
            'BU',      # Boston University collaboration
        ]
        if v.upper() not in valid_sites:
            raise ValueError(f"Unknown RePORT India site: {v}")
        return v.upper()


class TBLabResult(BaseModel):
    """TB laboratory result validation per RNTCP guidelines."""
    
    smear_result: Optional[Literal["Negative", "Scanty", "1+", "2+", "3+"]] = None
    culture_result: Optional[Literal["Negative", "Positive", "Contaminated", "NTM"]] = None
    xpert_result: Optional[Literal["MTB Not Detected", "MTB Detected", "Invalid", "Error"]] = None
    dst_rifampicin: Optional[Literal["Sensitive", "Resistant", "Indeterminate"]] = None
```

#### 1.2 Security & Compliance Hardening (DPDPA 2023)

```
Priority: HIGH | Effort: Low | Dependencies: 1.1
```

**Current State:** AES-256-GCM encryption, de-identification engine present.

**Indian Regulatory Requirements (DPDPA 2023 + DPDP Rules 2025):**

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Explicit consent before processing | Consent tracking module | 🔄 To Add |
| Pseudonymization for research data | De-identification engine | ✅ Complete |
| Audit logs for 1+ year | Encrypted audit logging | ✅ Complete |
| Breach notification to DPB | Alert system | 🔄 To Add |
| Role-based access controls | Auth middleware | ✅ Complete |
| Encryption (data at rest/transit) | AES-256-GCM + TLS | ✅ Complete |

**India-Specific Identifiers to De-identify:**

| Field | Pattern | Privacy Level |
|-------|---------|---------------|
| Aadhaar Number | `^\d{4}\s?\d{4}\s?\d{4}$` | CRITICAL |
| PAN Number | `^[A-Z]{5}\d{4}[A-Z]$` | HIGH |
| ABHA ID (Health Account) | `^\d{14}$` | CRITICAL |
| UHID (Hospital ID) | Hospital-specific | CRITICAL |
| Voter ID (EPIC) | `^[A-Z]{3}\d{7}$` | HIGH |

**Files to Modify:**

```python
# server/security/compliance.py (NEW)
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ComplianceFramework(str, Enum):
    """Supported compliance frameworks."""
    DPDPA = "dpdpa"      # India - Digital Personal Data Protection Act 2023
    ICMR = "icmr"        # ICMR National Ethical Guidelines 2017
    GXP = "gxp"          # ICH-GCP Good Clinical Practice
    CDSCO = "cdsco"      # Central Drugs Standard Control Organisation

@dataclass
class DataAccessAudit:
    """
    Immutable audit record for DPDPA compliance.
    
    DPDP Rules 2025 require:
    - Audit logs retained for minimum 1 year
    - Track who accessed what data, when, and why
    - Must be provided to Data Protection Board on request
    """
    timestamp: datetime
    user_id: str
    tool_name: str
    query_hash: str  # Hashed query for privacy
    record_count: int
    compliance_frameworks: list[ComplianceFramework]
    k_anonymity_satisfied: bool
    data_principal_consent: bool  # DPDPA requirement
    purpose_of_processing: str    # Must be specified per DPDPA
```

---

### Phase 2: Development Environment Setup (Week 2)

#### 2.1 Prerequisites Verification

```
Priority: HIGH | Effort: Low | Dependencies: None
```

**Current Environment:**
- ✅ Python 3.10+ (pyproject.toml specifies `>=3.10`)
- ✅ uv package manager (recommended in README)
- ✅ Docker support (Dockerfile present)
- ✅ MCP SDK (`mcp[cli]>=1.0.0`)

**Environment Verification:**

```bash
# Verify environment with uv (handles all dependency checks)
uv sync --all-extras

# Verify MCP server is operational
uv run python verify.py --verbose
```

#### 2.2 Database Connection Setup

```
Priority: HIGH | Effort: Medium | Dependencies: 2.1
```

**Recommended Database:** PostgreSQL (HIPAA-capable, audit logging support)

**New Files:**

```
server/
├── database/
│   ├── __init__.py
│   ├── connection.py     # Connection pool management
│   ├── models.py         # SQLAlchemy ORM models
│   └── queries.py        # Parameterized query templates
```

**Implementation:**

```python
# server/database/connection.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncpg
from server.config import get_settings

class DatabasePool:
    """PostgreSQL connection pool with audit logging."""
    
    _pool: asyncpg.Pool | None = None
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            settings = get_settings()
            cls._pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password.get_secret_value(),
                min_size=5,
                max_size=20,
                ssl="require",  # Always use TLS
            )
        return cls._pool
    
    @classmethod
    @asynccontextmanager
    async def acquire(cls) -> AsyncGenerator[asyncpg.Connection, None]:
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            yield conn
```

---

### Phase 3: MCP Server Configuration (Week 3)

#### 3.1 Implement Three-Tool Design Pattern

```
Priority: HIGH | Effort: Medium | Dependencies: 2.2
```

The **3-Tool MCP Design (v0.3.0)** is implemented as a Data Dictionary Expert:

**Focus:** Variable discovery and metadata lookup ONLY - NO patient data or statistics.

| Tool | Purpose | Example Query |
|------|---------|---------------|
| `prompt_enhancer` | **PRIMARY** - Intelligent router with confirmation | "What variables for relapse analysis?" |
| `combined_search` | **DEFAULT** - Variable discovery with concept expansion | "Diabetes variables", "TB outcome tracking" |
| `search_data_dictionary` | Direct variable lookup (metadata only) | "Search for smoking", "HIV status variable" |

**What This Server Returns:**
- ✅ Variable names, descriptions, tables, codelists
- ❌ NO patient data, NO statistics, NO dataset access

**Current State:** `server/tools/` package has all 3 tools implemented.

> **Note (v0.3.0):** The enhancements below for dataset access tools (`list_datasets`, `describe_schema`) are NOT applicable to v0.3.0, which is a Data Dictionary Expert focused exclusively on metadata. These enhancements would be relevant for a future version that includes patient data access.

#### 3.2 JSON-RPC Request Handling

```
Priority: MEDIUM | Effort: Low | Dependencies: 3.1
```

**Current State:** FastMCP handles JSON-RPC automatically via `mcp.sse_app()`.

**Verification Checklist:**
- [x] Tools/list endpoint returns all tool schemas
- [x] Tools/call executes tools with validation
- [x] Resources/list returns available resources
- [ ] Add custom error codes for clinical data errors

```python
# server/errors.py (NEW)
from enum import IntEnum

class ClinicalDataErrorCode(IntEnum):
    """Custom JSON-RPC error codes for clinical data operations."""
    
    # -32000 to -32099 are reserved for server errors
    PRIVACY_VIOLATION = -32001  # K-anonymity threshold not met
    UNAUTHORIZED_FIELD = -32002  # Attempted access to restricted field
    DATA_NOT_FOUND = -32003     # Dataset or record not found
    VALIDATION_FAILED = -32004  # Input validation error
    CONSENT_REQUIRED = -32005   # Data access requires consent
```

#### 3.3 Authentication & Authorization

```
Priority: HIGH | Effort: Low | Dependencies: None (already implemented)
```

**Current State:** Bearer token auth implemented in `server/auth.py`.

**Enhancements for Production:**

```python
# server/auth.py - Add role-based access control

from enum import Enum
from typing import set

class DataAccessRole(str, Enum):
    """Role-based access levels for clinical data."""
    
    VIEWER = "viewer"           # Can list and describe only
    ANALYST = "analyst"         # Can query aggregate data
    RESEARCHER = "researcher"   # Full query access (anonymized)
    ADMIN = "admin"             # Full access + audit logs

ROLE_PERMISSIONS: dict[DataAccessRole, set[str]] = {
    DataAccessRole.VIEWER: {"list_datasets", "describe_schema", "health_check"},
    DataAccessRole.ANALYST: {"list_datasets", "describe_schema", "fetch_metrics", "health_check"},
    DataAccessRole.RESEARCHER: {"list_datasets", "describe_schema", "query_database", "search_dictionary", "fetch_metrics", "health_check"},
    DataAccessRole.ADMIN: {"*"},  # All tools
}
```

---

### Phase 4: Server Deployment (Week 4)

#### 4.1 Launch MCP Server

```
Priority: HIGH | Effort: Low | Dependencies: 3.x
```

**Startup Commands:**

```bash
# Option 1: HTTP/SSE Transport (recommended for remote clients)
uv run uvicorn reportalin.server.main:app --host 0.0.0.0 --port 8000

# Option 2: stdio Transport (for Claude Desktop)
MCP_TRANSPORT=stdio uv run python -m reportalin.server

# Option 3: Docker (production)
docker compose up --build mcp-server
```

**Health Check Verification:**

```bash
# Verify server is running
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "0.3.0", "protocol": "2025-03-26"}
```

#### 4.2 Environment Configuration

```
Priority: HIGH | Effort: Low | Dependencies: None
```

**Production `.env` Template:**

```bash
# .env.production
ENVIRONMENT=production

# Server
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Authentication (REQUIRED in production)
MCP_AUTH_TOKEN=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
MCP_AUTH_ENABLED=true

# Database
DATABASE_URL=postgresql://user:password@db-host:5432/clinical_data?sslmode=require

# Privacy
PRIVACY_MODE=strict
MIN_K_ANONYMITY=5

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Encryption
ENCRYPTION_KEY=<generate with: python -c "from server.security.encryption import AES256GCMCipher; print(AES256GCMCipher.generate().export_key())">
```

---

### Phase 5: Client Configuration (Week 4-5)

#### 5.1 Claude Desktop Configuration

```
Priority: HIGH | Effort: Low | Dependencies: 4.1
```

**Configuration File:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "reportalin-clinical": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/RePORTaLiN-Agent",
        "python", "-m", "server"
      ],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "PRIVACY_MODE": "strict",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

#### 5.2 Programmatic Client Usage

```
Priority: MEDIUM | Effort: Low | Dependencies: 4.1
```

**Example: Querying RePORT India Data**

```python
# examples/query_report_india.py
"""
Example: Query RePORT India TB study data via MCP.

This script demonstrates the three-tool pattern for clinical data:
1. list_datasets - Discover available CRFs
2. describe_schema - Understand data structure  
3. query_database - Execute privacy-safe queries
"""
import asyncio
from client.universal_client import UniversalMCPClient

async def main():
    async with UniversalMCPClient(
        server_url="http://localhost:8000/mcp/sse",
        auth_token="your-secret-token"
    ) as client:
        # Step 1: Discover RePORT India datasets
        datasets = await client.execute_tool("list_datasets", {
            "include_metadata": True
        })
        print("RePORT India Datasets:")
        print(f"  Study: {datasets.get('study_name')}")
        print(f"  Total CRFs: {datasets.get('total_count')}")
        print(f"  Domains: {datasets.get('domains')}")
        
        # Step 2: Get schema for Index Case Baseline (demographics)
        schema = await client.execute_tool("describe_schema", {
            "dataset_name": "2A_ICBaseline",
            "include_statistics": True
        })
        print(f"\nIndex Case Baseline Schema:")
        print(f"  Fields: {schema.get('field_count')}")
        print(f"  Records: {schema.get('row_count')}")
        
        # Step 3: List TB laboratory datasets
        lab_datasets = await client.execute_tool("list_datasets", {
            "domain_filter": "LB"  # Laboratory domain
        })
        print(f"\nLaboratory Datasets: {lab_datasets.get('total_count')}")
        
        # Step 4: Query aggregate TB smear results (k-anonymity protected)
        # NOTE: Individual-level queries are blocked if < k subjects
        result = await client.execute_tool("query_database", {
            "query": """
                SELECT smear_result, COUNT(*) as count 
                FROM 4_Smear 
                GROUP BY smear_result 
                HAVING COUNT(*) >= 5
            """,
            "limit": 100
        })
        print(f"\nSmear Results (k≥5 anonymity):")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Phase 6: Testing & Validation (Week 5-6)

#### 6.1 Connection Testing

```
Priority: HIGH | Effort: Low | Dependencies: 5.x
```

**Test Suite:**

```python
# tests/integration/test_mcp_connection.py
import pytest
from client.universal_client import UniversalMCPClient

@pytest.mark.asyncio
async def test_tool_discovery():
    """Verify server exposes expected tools."""
    async with UniversalMCPClient(
        server_url="http://localhost:8000/mcp/sse",
        auth_token="test-token"
    ) as client:
        tools = await client.list_tools()
        
        # Verify three-tool design
        tool_names = {t.name for t in tools}
        assert "list_datasets" in tool_names
        assert "describe_schema" in tool_names
        assert "query_database" in tool_names

@pytest.mark.asyncio
async def test_k_anonymity_enforcement():
    """Verify k-anonymity threshold is enforced."""
    async with UniversalMCPClient(...) as client:
        # Query that would return < k records should be blocked
        result = await client.execute_tool("query_database", {
            "query": "SELECT * FROM DM WHERE usubjid = 'SINGLE_SUBJECT'"
        })
        
        assert "privacy" in result.lower() or "k-anonymity" in result.lower()
```

#### 6.2 Query Testing

```
Priority: HIGH | Effort: Medium | Dependencies: 6.1
```

**Natural Language Query Examples:**

| User Query | Expected Tool Call |
|------------|-------------------|
| "What datasets are available?" | `list_datasets({})` |
| "Show me the demographics fields" | `describe_schema({"dataset_name": "DM"})` |
| "How many subjects by age group?" | `query_database({"query": "SELECT age_group, COUNT(*) FROM DM GROUP BY age_group"})` |
| "What does the RACE variable mean?" | `search_dictionary({"search_term": "RACE"})` |

#### 6.3 Performance Monitoring

```
Priority: MEDIUM | Effort: Low | Dependencies: 6.1
```

**Metrics to Track:**

```python
# server/metrics.py (NEW)
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
TOOL_REQUESTS = Counter(
    "mcp_tool_requests_total",
    "Total MCP tool requests",
    ["tool_name", "status"]
)

QUERY_LATENCY = Histogram(
    "mcp_query_duration_seconds",
    "Query execution time",
    ["tool_name"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

ACTIVE_SESSIONS = Gauge(
    "mcp_active_sessions",
    "Number of active SSE sessions"
)

# Privacy metrics
PRIVACY_VIOLATIONS = Counter(
    "mcp_privacy_violations_total",
    "Queries blocked due to k-anonymity",
    ["dataset"]
)
```

---

## Implementation Checklist

### Week 1-2: Data Preparation
- [ ] Create CDISC validator module
- [ ] Implement data quality checks
- [ ] Add encryption-at-rest for data files
- [ ] Set up audit log rotation

### Week 2: Environment Setup
- [ ] Run environment verification script
- [ ] Set up PostgreSQL database
- [ ] Configure connection pooling
- [ ] Test database connectivity

### Week 3: Server Configuration
- [ ] Add `list_datasets` tool
- [ ] Add `describe_schema` tool
- [ ] Implement role-based access control
- [ ] Add custom error codes

### Week 4: Deployment
- [ ] Configure production environment variables
- [ ] Deploy with Docker Compose
- [ ] Verify health endpoints
- [ ] Set up monitoring dashboards

### Week 5: Client Integration
- [ ] Configure Claude Desktop
- [ ] Test stdio transport
- [ ] Document API usage examples
- [ ] Create client quickstart guide

### Week 6: Testing & Optimization
- [ ] Run integration test suite
- [ ] Verify k-anonymity enforcement
- [ ] Load test with 100+ concurrent connections
- [ ] Document performance baselines

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLINICAL DATA LAYER                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│  │ Indo-VAP Study │  │ Data Dictionary│  │ Audit Logs     │                │
│  │ (42 Excel/CSV) │  │ (JSONL)        │  │ (Encrypted)    │                │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                │
│          │                   │                   │                          │
│          ▼                   ▼                   ▼                          │
│  ┌───────────────────────────────────────────────────────────┐             │
│  │                    PostgreSQL Database                     │             │
│  │  - TLS encryption in transit                               │             │
│  │  - Row-level security                                      │             │
│  │  - Audit triggers                                          │             │
│  └───────────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP SERVER LAYER                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                        FastMCP Server (tools.py)                       ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  ││
│  │  │list_datasets │  │describe_schema│ │ query_database│  ← Three-Tool   ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘    Design        ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  ││
│  │  │search_dict   │  │fetch_metrics │  │health_check  │                  ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │ Auth Middleware │  │ K-Anonymity     │  │ Input Validator │            │
│  │ (Bearer Token)  │  │ (k≥5)           │  │ (Pydantic)      │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│     stdio Transport         │   │     HTTP/SSE Transport      │
│  (Claude Desktop, Cursor)   │   │  (Custom Agents, APIs)      │
│                             │   │                             │
│  claude_desktop_config.json │   │  http://host:8000/mcp/sse   │
└─────────────────────────────┘   └─────────────────────────────┘
                    │                               │
                    ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                    UniversalMCPClient (mcp_client.py)                  ││
│  │  - get_tools_for_openai()      → OpenAI function calling format        ││
│  │  - get_tools_for_anthropic()   → Anthropic tool use format             ││
│  │  - execute_tool()              → JSON-RPC tool invocation              ││
│  └────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐│
│  │                      ReAct Agent Loop (agent.py)                       ││
│  │  User: "How many subjects in each age group?"                          ││
│  │    └─► list_datasets() → describe_schema("DM") → query_database(...)   ││
│  └────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PHI exposure via query | Medium | Critical | K-anonymity enforcement (k≥5), input validation, audit logging |
| Aadhaar/ABHA number leak | Low | Critical | Pattern-based de-identification, encryption at rest |
| Auth token compromise | Low | High | Token rotation (90 days), TLS-only, rate limiting |
| Database connection leak | Low | Medium | Connection pooling with health checks |
| LLM prompt injection | Medium | Medium | Input sanitization, parameterized queries |
| DPDPA breach notification failure | Low | High | Automated alerting to Data Protection Board |
| Cross-site data mixing | Low | High | Site-level access controls, data segregation |

---

## Success Criteria

1. **Functional**: LLM can successfully list, describe, and query RePORT India datasets
2. **Secure**: All queries pass k-anonymity checks (k≥5) per ICMR guidelines
3. **Compliant**: DPDPA 2023 compliant with full audit trail (1+ year retention)
4. **Performant**: P95 latency < 500ms for standard queries
5. **De-identified**: All Indian identifiers (Aadhaar, PAN, ABHA) properly masked
6. **Documented**: API reference and RePORT India data dictionary complete

---

## References

### Indian Regulations
- [DPDPA 2023 - Digital Personal Data Protection Act](https://www.meity.gov.in/writereaddata/files/Digital%20Personal%20Data%20Protection%20Act%202023.pdf)
- [DPDP Rules 2025](https://www.meity.gov.in/content/digital-personal-data-protection-rules-2025)
- [ICMR National Ethical Guidelines for Biomedical Research 2017](https://main.icmr.nic.in/sites/default/files/guidelines/ICMR_Ethical_Guidelines_2017.pdf)
- [Data Protection Board of India](https://www.dpb.gov.in/)

### RePORT India Study
- [RePORT International Consortium](https://reportinternational.org/)
- [NIRT Chennai - National Institute for Research in Tuberculosis](https://www.nirt.res.in/)
- [RNTCP Technical Guidelines](https://tbcindia.gov.in/index1.php?sublinkid=4573&level=2&lid=3177&lang=1)

### Technical Standards
- [MCP Specification 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26)
- [MCP Best Practices](https://modelcontextprotocol.info/docs/best-practices/)
- [CDISC SDTM Implementation Guide](https://www.cdisc.org/standards/foundational/sdtm)
- [ICH-GCP E6(R2) Guidelines](https://www.ich.org/page/efficacy-guidelines)

### Security
- [CERT-In Guidelines](https://www.cert-in.org.in/)
- [NIST SP 800-38D - GCM Mode Recommendation](https://csrc.nist.gov/publications/detail/sp/800-38d/final)
