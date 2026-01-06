# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-12-26

### 🚨 BREAKING CHANGES

**Complete restructure to Data Dictionary Expert - metadata only, NO patient data**

This release transforms RePORTaLiN from a clinical data analysis server to a specialized data dictionary expert focused exclusively on variable discovery and metadata lookup.

### Removed

- ❌ **`search_cleaned_dataset` tool** - Dataset query functionality removed
- ❌ **Dataset statistics** - All statistical analysis removed from `combined_search`
- ❌ **`_analyzers.py` module** - Statistical functions removed
- ❌ **Dataset loading** - No patient data access whatsoever
- ❌ **Core dependencies**: pandas, numpy, openpyxl, tqdm (→ optional `[data-prep]`)

### Changed

- **Tools: 4 → 3** (removed `search_cleaned_dataset`)
  1. `prompt_enhancer` - PRIMARY entry point (routes queries)
  2. `combined_search` - Variable discovery with concept expansion (NO statistics)
  3. `search_data_dictionary` - Direct variable lookup
- **Server focus**: Clinical data analysis → Data dictionary expert
- **Version**: 2.1.0 → 0.3.0 (pre-1.0 for breaking changes)
- **pandas/openpyxl**: Core dependency → optional `[data-prep]` (for JSONL generation only)

### Added

- ✅ **Excel fallback** in `_loaders.py` - Auto-generates JSONL from Excel if needed
- ✅ **18 JSONL files** committed to repo (1050 variable definitions, 47 codelists)
- ✅ **`load_dictionary.py` restored** - For standalone JSONL generation
- ✅ **Concept synonym mapping preserved** - Critical variable discovery feature intact

### Fixed

- PROJECT_ROOT path calculation (4 levels up from `_loaders.py`)
- All version references updated to 0.3.0
- Removed `include_statistics` parameter from `CombinedSearchInput`

### Migration Guide

**For Runtime Use:**
```bash
# Install without pandas (50MB reduction)
uv pip install reportalin-mcp
```

**For Data Preparation:**
```bash
# Generate JSONL from Excel
uv pip install reportalin-mcp[data-prep]
```

**What This Server Does Now:**
- ✅ Variable discovery: "What variables for relapse analysis?"
- ✅ Returns: Variable names, descriptions, tables, codelists
- ❌ NO patient data, NO statistics, NO dataset access

---

## [Unreleased]

### Added

- **NEW: Intelligent Query Router - `prompt_enhancer` Tool** ⭐
  - PRIMARY entry point for all user queries
  - **CRITICAL FEATURE:** Confirms understanding with user BEFORE executing queries
  - Analyzes intent and automatically routes to appropriate specialized tool
  - Uses LLM's natural prompt enhancement capabilities
  - Two-step workflow: interpretation → confirmation → execution

### Changed

- **BREAKING: MCP Tools Refactored from 10 → 4 Tools**
  - **Reduced tools:** 10 tools consolidated into 4 streamlined tools
  - **New architecture:**
    1. `prompt_enhancer` ⭐ - NEW primary entry point with confirmation flow
    2. `combined_search` - DEFAULT for analytical queries
    3. `search_data_dictionary` - Metadata lookup only
  - **Removed tools:** (functionality merged into `combined_search`)
    - ❌ `natural_language_query` - Replaced by `prompt_enhancer`
    - ❌ `cohort_summary` - Merged into `combined_search`
    - ❌ `cross_tabulation` - Merged into `combined_search`
    - ❌ `variable_details` - Merged into `search_data_dictionary`
    - ❌ `data_quality_report` - Merged into `combined_search`
    - ❌ `multi_variable_comparison` - Merged into `combined_search`

- **Tools Package Refactored to Modular Architecture**
  - **Before:** Single monolithic file (`server/tools.py` - 2,710 lines)
  - **After:** Modular package with 9 files (`server/tools/` - ~150-680 lines each)
  - **New structure:**
    - `tools/__init__.py` - Package exports
    - `tools/prompt_enhancer.py` - NEW intelligent router (~320 lines)
    - `tools/combined_search.py` - DEFAULT analytical tool (~480 lines)
    - `tools/search_data_dictionary.py` - Metadata lookup (~150 lines)
    - `tools/search_cleaned_dataset.py` - Dataset statistics (~110 lines)
    - `tools/registry.py` - FastMCP setup + 6 resources + 4 prompts (~680 lines)
    - `tools/_models.py` - Pydantic input models (~70 lines)
    - `tools/_loaders.py` - Data loading utilities (~200 lines)
    - `tools/_analyzers.py` - Statistical analysis (~150 lines)
  - **Benefits:**
    - Single Responsibility Principle (SRP) - one file per tool
    - Easy to find, test, and modify
    - Improved maintainability (80% reduction in file size)
    - Clear separation of concerns

- **Privacy-First Architecture**
  - All tools enforce aggregate statistics only (no individual records)
  - Data dictionary metadata access only

- **MCP Resources (6 Total) - Maintained**
  - `dictionary://overview` - Updated with new 4-tool architecture
  - `dictionary://tables` - All table listings
  - `dictionary://codelists` - All codelist definitions
  - `dictionary://table/{name}` - Specific table schema
  - `dictionary://codelist/{name}` - Specific codelist values
  - `study://variables/{category}` - Variables by category

- **MCP Prompts (4 Total) - Updated**
  - `research_question_template` - Updated to recommend `prompt_enhancer`
  - `data_exploration_guide` - Updated workflow with new tools
  - `statistical_analysis_template` - Statistical analysis patterns
  - `tb_outcome_analysis` - TB outcome specific guidance

- **Documentation Updated**
  - README.md - New 4-tool structure with `prompt_enhancer` workflow
  - Project structure diagram updated to show refactored `tools/` package
  - Tool selection guide updated
  - Privacy & security section enhanced

### Fixed

- Eliminated ~1,000 lines of duplicate code (Phase 4A)
- Improved code organization following SRP and DRY principles

## [2.1.0] - 2025-12-07

### Added

- **Security Hardening (Phase 1)**
  - AES-256-GCM encryption module replacing Fernet/AES-128
  - Async rate limiting with token bucket algorithm
  - Security headers middleware (CSP, HSTS, X-Frame-Options, etc.)
  - Input validation middleware for query string/parameter limits
  - Rotatable secrets for Zero Trust token rotation with grace periods
  - CORS hardening with environment-aware configuration
  
- **MCP Protocol Modernization (Phase 2)**
  - Updated to MCP Protocol version `2025-03-26`
  - Enhanced type system with `PrivacyMode`, `EnvironmentType`, `SecurityContext`
  - New `TransportType.STREAMABLE_HTTP` for latest MCP spec
  - Client retry logic with exponential backoff and jitter
  - `MCPRetryConfig` for configurable retry behavior
  - `connect_with_retry()` and `reconnect()` methods for resilience

- **CI/CD Automation (Phase 4)**
  - Comprehensive CI workflow (`.github/workflows/ci.yml`)
    - Multi-Python version testing (3.10-3.13)
    - Linting with Black and Ruff
    - Type checking with MyPy
    - Docker build verification
  - Release workflow (`.github/workflows/release.yml`)
    - Multi-platform Docker builds (amd64/arm64)
    - GitHub Container Registry publishing
    - Automated release notes
  - Security scanning workflow (`.github/workflows/security.yml`)
    - CodeQL analysis
    - Dependency vulnerability scanning
    - Container security with Trivy
    - Secret scanning with TruffleHog
    - SAST with Bandit

- **New Security Module** (`server/security/`)
  - `encryption.py` — AES-256-GCM with key derivation
  - `rate_limiter.py` — Async token bucket rate limiter
  - `middleware.py` — Security headers, input validation, rate limiting
  - `secrets.py` — Rotatable secrets with grace period support
  - Full `py.typed` marker for type checking

### Changed

- Bumped version to 2.1.0
- Updated `shared/constants.py` with 2025 protocol version and security constants
- Enhanced `shared/types.py` with comprehensive type definitions
- Refactored `server/main.py` to properly separate FastAPI routes from ASGI middleware
- Updated `server/auth.py` to use rotatable secrets for token rotation
- Improved `client/mcp_client.py` with retry configuration and connection recovery

### Security

- All encryption now uses AES-256-GCM (NIST approved)
- Rate limiting prevents DoS attacks
- Security headers protect against common web vulnerabilities
- Input validation prevents oversized request attacks
- Token rotation supports Zero Trust architecture

## [2.0.0] - 2025-12-05

### Added

- `CONTRIBUTING.md` with development guidelines and PHI handling rules

### Changed

- Restructured all documentation to follow Diátaxis framework
- Updated `README.md` with GitHub admonitions and navigation anchors
- Enhanced `llms.txt` to match llms.txt specification

## [0.0.2] - 2025-12-04

### Added

- **MCP Server** — Model Context Protocol server for LLM integration
  - `get_study_variables` tool for natural language variable search
  - `generate_federated_code` tool for privacy-safe analysis code
  - `get_data_schema` tool for schema exploration
  - `get_aggregate_statistics` tool with k-anonymity protection
- **Encrypted Logging** — RSA-OAEP + AES-256-CBC hybrid encryption
  - `server/` for secure audit logging (Phase 1)
  - `scripts/core/log_decryptor.py` CLI for authorized decryption
  - Key rotation tracking (90-day NIST guideline)
  - PHI auto-redaction before encryption
- **Structured Logging** — JSON output with context support
  - `scripts/core/structured_logging.py` for log aggregation
  - Request-scoped context via `log_context()` context manager
- **Pydantic Configuration** — Type-safe settings management
  - `scripts/core/settings.py` with environment variable binding
  - Nested configuration groups (logging, encryption, MCP)
- **Privacy Aggregates** — K-anonymity protected data access
  - Minimum cell size of 5 for all aggregates
- **India DPDPA 2023 + DPDP Rules 2025 Compliance**
  - Aadhaar, PAN, ABHA, UHID pattern detection

### Changed

- Updated project structure with `/server/`, `/client/`, `/shared/` (MCP v2.0 architecture)
- Improved type hints throughout codebase

### Fixed

- Timezone-aware datetime handling in crypto_logger.py
- Added `__all__` exports to all public modules

## [0.0.1] - 2024-12-02

### Added

- Initial project setup
- Data extraction pipeline from Excel files
- De-identification engine for PHI/PII
- Country-specific privacy regulations (14 countries)
- Data dictionary loading and processing

[Unreleased]: https://github.com/your-org/RePORTaLiN-Agent/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/your-org/RePORTaLiN-Agent/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/your-org/RePORTaLiN-Agent/releases/tag/v0.0.1
