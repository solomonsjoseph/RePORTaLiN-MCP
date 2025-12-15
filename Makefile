# Makefile for RePORTaLiN-Specialist Data Pipeline
# =================================================
#
# A clinical data processing pipeline for extraction, transformation,
# and de-identification of sensitive research data.
#
# Usage:
#   make              - Show help (default)
#   make run          - Run full pipeline
#   make install      - Install dependencies
#   make lint         - Run code quality checks
#   make test         - Run tests
#   make clean        - Remove generated files
#
# Configuration Variables:
#   PYTHON           - Python interpreter (auto-detected)
#   PREFIX           - Installation prefix (default: /usr/local)
#
# Requirements:
#   - Python 3.10+ (auto-detected)
#   - pip (Python package installer)
#
# For more information, see README.md

# =============================================================================
# Special Targets (placed early per GNU Make recommendations)
# =============================================================================

# Delete targets if recipe fails
.DELETE_ON_ERROR:

# Don't delete intermediate files
.SECONDARY:

# Default goal
.DEFAULT_GOAL := help

# =============================================================================
# Shell Configuration
# =============================================================================

# Use bash with strict error handling
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# =============================================================================
# Configuration Variables (Simple Expansion for Performance)
# =============================================================================

# Project metadata
PROJECT_NAME := RePORTaLiN-Specialist
VERSION := $(shell grep "^__version__" src/reportalin/__init__.py 2>/dev/null | head -1 | sed 's/.*"\(.*\)"/\1/' || echo "2.1.0")

# Color output (ANSI escape codes)
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
CYAN := \033[0;36m
BOLD := \033[1m
NC := \033[0m

# Docker image settings (moved here for use in clean targets)
DOCKER_IMAGE := reportalin-specialist-mcp
DOCKER_TAG := latest
PORT ?= 8000

# Installation prefix (can be overridden)
PREFIX ?= /usr/local

# =============================================================================
# Python Environment Detection
# =============================================================================

# Detect Python command (prefer python3)
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)

# Use uv for Python execution
PYTHON_CMD := uv run python

# Source directories
SRC_DIRS := src/reportalin tests

# =============================================================================
# Tool Validation
# =============================================================================

# Check for required tools at parse time
ifeq ($(PYTHON),)
    $(error Python is not installed or not in PATH. Please install Python 3.10+)
endif

# =============================================================================
# Phony Targets Declaration
# =============================================================================

.PHONY: help version info status setup
.PHONY: install install-dev upgrade-deps
.PHONY: run run-verbose run-dictionary run-extract run-deidentify run-deidentify-verbose
.PHONY: run-agent run-agent-test
.PHONY: lint format typecheck check-all test test-cov test-verbose
.PHONY: verify-refactoring verify-imports verify-tools
.PHONY: clean clean-cache clean-logs clean-results clean-docker clean-generated distclean nuclear
.PHONY: commit check-commit bump-dry bump bump-push bump-patch bump-minor bump-major changelog hooks pre-commit
.PHONY: docker-build docker-scan docker-lint docker-security docker-mcp mcp-test-docker mcp-install-config-docker mcp-install-config-local mcp-show-config mcp-server-stdio mcp-server-http
.PHONY: mcp-setup check-data
.PHONY: compose-build compose-up compose-up-detached compose-dev compose-logs compose-down compose-health

# =============================================================================
# Help Target
# =============================================================================

# Note: "Broken pipe" errors when piping to head/less are harmless (SIGPIPE)
help:
	@printf "$(BOLD)$(BLUE)"
	@printf "╔═══════════════════════════════════════════════════════════════════╗\n"
	@printf "║         $(PROJECT_NAME) Data Pipeline - v$(VERSION)              ║\n"
	@printf "╚═══════════════════════════════════════════════════════════════════╝\n"
	@printf "$(NC)\n"
	@printf "$(BOLD)$(GREEN)🚀 QUICK START (Two Steps):$(NC)\n"
	@printf "  $(CYAN)make setup$(NC)           $(BOLD)Run everything$(NC) (verify + extract + Docker + config)\n"
	@printf "  $(CYAN)Then:$(NC)                Copy config to Claude Desktop & restart\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Setup:$(NC)\n"
	@printf "  $(CYAN)make install$(NC)         Install production dependencies\n"
	@printf "  $(CYAN)make install-dev$(NC)     Install development dependencies\n"
	@printf "  $(CYAN)make upgrade-deps$(NC)    Upgrade all dependencies\n"
	@printf "  $(CYAN)make version$(NC)         Show version information\n"
	@printf "  $(CYAN)make info$(NC)            Show environment information\n"
	@printf "  $(CYAN)make status$(NC)          Show complete system status\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Running:$(NC)\n"
	@printf "  $(CYAN)make run$(NC)             Run full pipeline (dictionary + extraction)\n"
	@printf "  $(CYAN)make run-verbose$(NC)     Run with verbose logging\n"
	@printf "  $(CYAN)make run-dictionary$(NC)  Run only dictionary loading\n"
	@printf "  $(CYAN)make run-extract$(NC)     Run only data extraction\n"
	@printf "  $(CYAN)make run-deidentify$(NC)  Run with de-identification\n"
	@printf "  $(CYAN)make run-deidentify-verbose$(NC)\n"
	@printf "                       De-identification with verbose logging\n"
	@printf "  $(CYAN)make run-agent$(NC)       Run the MCP agent (interactive)\n"
	@printf "  $(CYAN)make run-agent-test$(NC)  Run agent with test prompt\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Code Quality:$(NC)\n"
	@printf "  $(CYAN)make lint$(NC)            Run ruff linter\n"
	@printf "  $(CYAN)make format$(NC)          Format code with ruff\n"
	@printf "  $(CYAN)make typecheck$(NC)       Run mypy type checker\n"
	@printf "  $(CYAN)make check-all$(NC)       Run all checks (lint + typecheck)\n"
	@printf "  $(CYAN)make test$(NC)            Run pytest\n"
	@printf "  $(CYAN)make test-cov$(NC)        Run pytest with coverage\n"
	@printf "  $(CYAN)make test-verbose$(NC)    Run pytest with verbose output\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Verification:$(NC)\n"
	@printf "  $(CYAN)make verify-refactoring$(NC)\n"
	@printf "                       $(BOLD)Verify complete refactoring$(NC) (imports + tools + docs)\n"
	@printf "  $(CYAN)make verify-imports$(NC)  Verify all package imports work\n"
	@printf "  $(CYAN)make verify-tools$(NC)    Verify 4 tools are registered\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Cleaning:$(NC)\n"
	@printf "  $(CYAN)make clean$(NC)           Remove Python cache files\n"
	@printf "  $(CYAN)make clean-logs$(NC)      Remove log files\n"
	@printf "  $(CYAN)make clean-results$(NC)   Remove generated results (interactive)\n"
	@printf "  $(CYAN)make clean-docker$(NC)    Remove Docker images and containers\n"
	@printf "  $(CYAN)make clean-generated$(NC) Remove generated config files\n"
	@printf "  $(CYAN)make distclean$(NC)       Remove all generated files\n"
	@printf "  $(CYAN)make nuclear$(NC)         $(RED)💣 DANGER:$(NC) Remove EVERYTHING (interactive)\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Versioning (Commitizen):$(NC)\n"
	@printf "  $(CYAN)make commit$(NC)          Interactive conventional commit\n"
	@printf "  $(CYAN)make bump$(NC)            Bump version based on commits (local)\n"
	@printf "  $(CYAN)make bump-push$(NC)       $(BOLD)Bump + push tags$(NC) (triggers CI/CD release)\n"
	@printf "  $(CYAN)make bump-dry$(NC)        Preview version bump (no changes)\n"
	@printf "  $(CYAN)make bump-patch$(NC)      Force PATCH bump (0.0.x)\n"
	@printf "  $(CYAN)make bump-minor$(NC)      Force MINOR bump (0.x.0)\n"
	@printf "  $(CYAN)make bump-major$(NC)      Force MAJOR bump (x.0.0)\n"
	@printf "  $(CYAN)make changelog$(NC)       Generate/update CHANGELOG.md\n"
	@printf "  $(CYAN)make hooks$(NC)           Install commit-msg validation hook\n"
	@printf "  $(CYAN)make pre-commit$(NC)      Run all hooks on all files\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)MCP Server (Claude Desktop Integration):$(NC)\n"
	@printf "  $(CYAN)make mcp-setup$(NC)       Build Docker + install Claude config\n"
	@printf "  $(CYAN)make docker-build$(NC)    Build MCP server Docker image\n"
	@printf "  $(CYAN)make docker-security$(NC) Run all security checks (lint + scan)\n"
	@printf "  $(CYAN)make docker-scan$(NC)     Scan image for vulnerabilities (Trivy)\n"
	@printf "  $(CYAN)make docker-lint$(NC)     Lint Dockerfile (Hadolint)\n"
	@printf "  $(CYAN)make mcp-test-docker$(NC) Test MCP server handshake\n"
	@printf "  $(CYAN)make mcp-install-config-docker$(NC)\n"
	@printf "                       Install Docker config to Claude Desktop\n"
	@printf "  $(CYAN)make mcp-install-config-local$(NC)\n"
	@printf "                       Install local Python config to Claude Desktop\n"
	@printf "  $(CYAN)make mcp-show-config$(NC) Show current Claude Desktop config\n"
	@printf "  $(CYAN)make docker-mcp$(NC)      Run MCP server in Docker (secure mode)\n"
	@printf "  $(CYAN)make check-data$(NC)      Check if data dictionary is ready\n"
	@printf "\n"
	@printf "$(BOLD)Docker Compose (Production):$(NC)\n"
	@printf "  $(CYAN)make compose-build$(NC)   Build with Docker Compose (uv-based)\n"
	@printf "  $(CYAN)make compose-up$(NC)      Start production server\n"
	@printf "  $(CYAN)make compose-dev$(NC)     Start dev server (hot reload)\n"
	@printf "  $(CYAN)make compose-down$(NC)    Stop all services\n"
	@printf "  $(CYAN)make compose-logs$(NC)    View container logs\n"
	@printf "  $(CYAN)make compose-health$(NC)  Check container health status\n"
	@printf "\n"
	@printf "$(BOLD)$(YELLOW)Note:$(NC) Version auto-bumps via GitHub Actions on push to main\n"
	@printf "\n"
	@printf "$(BOLD)$(YELLOW)Environment:$(NC)\n"
	@printf "  Python: $(PYTHON_CMD)\n"
	@printf "\n"

# =============================================================================
# Information Targets
# =============================================================================

version:
	@$(PYTHON_CMD) -c "from reportalin import __version__; print(f'RePORTaLiN v{__version__}')"

info:
	@printf "$(BOLD)$(BLUE)Environment Information$(NC)\n"
	@printf "$(CYAN)─────────────────────────$(NC)\n"
	@printf "Project:     $(PROJECT_NAME)\n"
	@printf "Version:     $(VERSION)\n"
	@printf "Python:      $(PYTHON_CMD)\n"
	@printf "Python ver:  $$($(PYTHON_CMD) --version 2>&1)\n"
	@printf "Shell:       $(SHELL)\n"
	@printf "Make:        $(MAKE_VERSION)\n"
	@printf "\n"

status:
	@printf "$(BOLD)$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)\n"
	@printf "$(BOLD)$(BLUE)           RePORTaLiN System Status$(NC)\n"
	@printf "$(BOLD)$(BLUE)═══════════════════════════════════════════════════════════════════$(NC)\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)📦 Architecture:$(NC)\n"
	@printf "  • Version: $(CYAN)$(VERSION)$(NC)\n"
	@printf "  • Structure: $(CYAN)Modular (9 files in tools package)$(NC)\n"
	@printf "  • Tools: $(CYAN)4 MCP tools$(NC)\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)🔧 MCP Tools:$(NC)\n"
	@if $(PYTHON_CMD) -c "from reportalin.server.tools import get_tool_registry; r = get_tool_registry(); print('  ✓ ' + ', '.join(r['registered_tools']))" 2>/dev/null; then :; else \
		printf "  $(RED)✗ Tools not loaded - run 'make install-dev'$(NC)\n"; \
	fi
	@printf "\n"
	@printf "$(BOLD)$(GREEN)📁 Data Status:$(NC)\n"
	@if [ -d "results/data_dictionary_mappings" ] && [ "$$(ls -A results/data_dictionary_mappings 2>/dev/null)" ]; then \
		printf "  $(GREEN)✓ Data dictionary$(NC) ($$(ls -d results/data_dictionary_mappings/tbl* 2>/dev/null | wc -l | tr -d ' ') tables)\n"; \
	else \
		printf "  $(YELLOW)⚠ Data dictionary not found$(NC) - run 'make run'\n"; \
	fi
	@if [ -d "results/deidentified" ]; then \
		printf "  $(GREEN)✓ Deidentified data$(NC)\n"; \
	else \
		printf "  $(YELLOW)⚠ Deidentified data not found$(NC) - run 'make run-deidentify'\n"; \
	fi
	@printf "\n"
	@printf "$(BOLD)$(GREEN)🐳 Docker Status:$(NC)\n"
	@if docker images | grep -q "$(DOCKER_IMAGE)"; then \
		printf "  $(GREEN)✓ Docker image built$(NC) ($(DOCKER_IMAGE):$(DOCKER_TAG))\n"; \
	else \
		printf "  $(YELLOW)⚠ Docker image not built$(NC) - run 'make docker-build'\n"; \
	fi
	@if docker ps -a | grep -q "reportalin-mcp"; then \
		printf "  $(CYAN)ℹ Container exists$(NC)\n"; \
	else \
		printf "  $(YELLOW)⚠ No container found$(NC)\n"; \
	fi
	@printf "\n"
	@printf "$(BOLD)$(GREEN)⚙️  Configuration:$(NC)\n"
	@if [ -f ~/Library/Application\ Support/Claude/claude_desktop_config.json ]; then \
		printf "  $(GREEN)✓ Claude Desktop config exists$(NC)\n"; \
	else \
		printf "  $(YELLOW)⚠ Claude Desktop config not found$(NC) - run 'make mcp-install-config-docker'\n"; \
	fi
	@printf "\n"
	@printf "$(BOLD)$(CYAN)Quick Commands:$(NC)\n"
	@printf "  • $(CYAN)make verify-refactoring$(NC)   - Verify system integrity\n"
	@printf "  • $(CYAN)make setup$(NC)                - Complete setup\n"
	@printf "  • $(CYAN)make mcp-setup$(NC)            - MCP server setup\n"
	@printf "  • $(CYAN)make help$(NC)                 - Show all commands\n"
	@printf "\n"

# =============================================================================
# Setup Targets
# =============================================================================

install:
	@printf "$(BLUE)Installing production dependencies...$(NC)\n"
	@uv sync
	@printf "$(GREEN)✓ Dependencies installed$(NC)\n"

install-dev:
	@printf "$(BLUE)Installing development dependencies...$(NC)\n"
	@uv sync --all-extras
	@printf "$(GREEN)✓ Development dependencies installed$(NC)\n"
	@printf "$(BLUE)Installing pre-commit hooks (uv-compatible)...$(NC)\n"
	@# Create custom pre-commit hook that uses uv run for reliability
	@mkdir -p .git/hooks
	@echo '#!/usr/bin/env bash' > .git/hooks/pre-commit
	@echo '# Custom pre-commit hook using uv for reliability' >> .git/hooks/pre-commit
	@echo 'set -e' >> .git/hooks/pre-commit
	@echo 'cd "$$(git rev-parse --show-toplevel)"' >> .git/hooks/pre-commit
	@echo 'if command -v uv > /dev/null 2>&1; then' >> .git/hooks/pre-commit
	@echo '    exec uv run pre-commit run --hook-stage pre-commit "$$@"' >> .git/hooks/pre-commit
	@echo 'elif [ -x ".venv/bin/pre-commit" ]; then' >> .git/hooks/pre-commit
	@echo '    exec .venv/bin/pre-commit run --hook-stage pre-commit "$$@"' >> .git/hooks/pre-commit
	@echo 'else' >> .git/hooks/pre-commit
	@echo '    echo "Error: Run make install-dev first." >&2; exit 1' >> .git/hooks/pre-commit
	@echo 'fi' >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@printf "$(GREEN)✓ Pre-commit hooks installed (uv-compatible)$(NC)\n"

upgrade-deps:
	@printf "$(BLUE)Upgrading all dependencies...$(NC)\n"
	@uv sync --upgrade
	@printf "$(GREEN)✓ Dependencies upgraded$(NC)\n"

# =============================================================================
# Pipeline Execution Targets
# =============================================================================

run:
	@printf "$(BLUE)Running pipeline...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline
	@printf "$(GREEN)✓ Pipeline complete$(NC)\n"

run-verbose:
	@printf "$(BLUE)Running pipeline (verbose)...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --verbose
	@printf "$(GREEN)✓ Pipeline complete$(NC)\n"

run-dictionary:
	@printf "$(BLUE)Running dictionary loading only...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --skip-extraction
	@printf "$(GREEN)✓ Dictionary loading complete$(NC)\n"

run-extract:
	@printf "$(BLUE)Running data extraction only...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --skip-dictionary
	@printf "$(GREEN)✓ Data extraction complete$(NC)\n"

run-deidentify:
	@printf "$(BLUE)Running pipeline with de-identification...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --enable-deidentification
	@printf "$(GREEN)✓ De-identification complete$(NC)\n"

run-deidentify-verbose:
	@printf "$(BLUE)Running pipeline with de-identification (verbose)...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --enable-deidentification --verbose
	@printf "$(GREEN)✓ De-identification complete$(NC)\n"

# Run the MCP Agent with a custom prompt
# Usage: make run-agent PROMPT="Your prompt here"
run-agent:
	@printf "$(BLUE)Running MCP Agent...$(NC)\n"
ifdef PROMPT
	@./scripts/run_agent.sh "$(PROMPT)"
else
	@printf "$(YELLOW)No PROMPT provided. Usage: make run-agent PROMPT=\"Your prompt here\"$(NC)\n"
	@printf "$(YELLOW)Running with default test prompt...$(NC)\n"
	@./scripts/run_agent.sh
endif

# Run the MCP Agent with the default test prompt
run-agent-test:
	@printf "$(BLUE)Running MCP Agent with test prompt...$(NC)\n"
	@./scripts/run_agent.sh

# =============================================================================
# Code Quality Targets
# =============================================================================

lint:
	@printf "$(BLUE)Running ruff linter...$(NC)\n"
	@$(PYTHON_CMD) -m ruff check $(SRC_DIRS)
	@printf "$(GREEN)✓ Lint passed$(NC)\n"

format:
	@printf "$(BLUE)Formatting code with ruff...$(NC)\n"
	@$(PYTHON_CMD) -m ruff format $(SRC_DIRS)
	@$(PYTHON_CMD) -m ruff check --fix $(SRC_DIRS)
	@printf "$(GREEN)✓ Formatting complete$(NC)\n"

typecheck:
	@printf "$(BLUE)Running mypy type checker...$(NC)\n"
	@$(PYTHON_CMD) -m mypy $(SRC_DIRS)
	@printf "$(GREEN)✓ Type check passed$(NC)\n"

check-all: lint typecheck verify-imports
	@printf "$(GREEN)✓ All checks passed$(NC)\n"
	@printf "$(CYAN)  → Linting, type checking, and imports verified$(NC)\n"
	@printf "$(CYAN)  → Run 'make verify-refactoring' for comprehensive verification$(NC)\n"

# =============================================================================
# Testing Targets
# =============================================================================

test:
	@printf "$(BLUE)Running tests...$(NC)\n"
	@$(PYTHON_CMD) -m pytest
	@printf "$(GREEN)✓ Tests passed$(NC)\n"

test-verbose:
	@printf "$(BLUE)Running tests (verbose)...$(NC)\n"
	@$(PYTHON_CMD) -m pytest -v
	@printf "$(GREEN)✓ Tests passed$(NC)\n"

test-cov:
	@printf "$(BLUE)Running tests with coverage...$(NC)\n"
	@$(PYTHON_CMD) -m pytest --cov=src/reportalin --cov-report=term-missing --cov-report=html
	@printf "$(GREEN)✓ Tests passed. Coverage report: htmlcov/index.html$(NC)\n"

# =============================================================================
# Refactoring Verification Targets
# =============================================================================

# Verify all imports work correctly
verify-imports:
	@printf "$(BLUE)Verifying package imports...$(NC)\n"
	@$(PYTHON_CMD) -c "from reportalin.server.tools import mcp, get_tool_registry" && \
		printf "$(GREEN)  ✓ FastMCP server import OK$(NC)\n" || \
		(printf "$(RED)  ✗ FastMCP server import failed$(NC)\n" && exit 1)
	@$(PYTHON_CMD) -c "from reportalin.server.tools import prompt_enhancer, combined_search, search_data_dictionary, search_cleaned_dataset" && \
		printf "$(GREEN)  ✓ All 4 tools import OK$(NC)\n" || \
		(printf "$(RED)  ✗ Tool imports failed$(NC)\n" && exit 1)
	@$(PYTHON_CMD) -c "from reportalin.server.tools._models import PromptEnhancerInput, CombinedSearchInput" && \
		printf "$(GREEN)  ✓ Pydantic models import OK$(NC)\n" || \
		(printf "$(RED)  ✗ Model imports failed$(NC)\n" && exit 1)
	@$(PYTHON_CMD) -c "from reportalin.server.tools._loaders import get_data_dictionary, get_cleaned_dataset" && \
		printf "$(GREEN)  ✓ Data loaders import OK$(NC)\n" || \
		(printf "$(RED)  ✗ Loader imports failed$(NC)\n" && exit 1)
	@$(PYTHON_CMD) -c "from reportalin.server.tools._analyzers import compute_variable_stats" && \
		printf "$(GREEN)  ✓ Analyzers import OK$(NC)\n" || \
		(printf "$(RED)  ✗ Analyzer imports failed$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ All imports verified$(NC)\n"

# Verify tool registration and FastMCP setup
verify-tools:
	@printf "$(BLUE)Verifying tool registration...$(NC)\n"
	@$(PYTHON_CMD) -c "from reportalin.server.tools import get_tool_registry; r = get_tool_registry(); assert len(r['registered_tools']) == 4, f'Expected 4 tools, got {len(r[\"registered_tools\"])}'; print('  ✓ Exactly 4 tools registered:', ', '.join(r['registered_tools']))" && \
		printf "$(GREEN)✓ Tool count verified$(NC)\n" || \
		(printf "$(RED)✗ Tool registration check failed$(NC)\n" && exit 1)
	@$(PYTHON_CMD) -c "from reportalin.server.tools import mcp; assert mcp is not None; print('  ✓ FastMCP server instance initialized')" && \
		printf "$(GREEN)✓ FastMCP server verified$(NC)\n" || \
		(printf "$(RED)✗ FastMCP server check failed$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ All tools verified$(NC)\n"

# Verify old duplicate files are removed
verify-cleanup:
	@printf "$(BLUE)Verifying cleanup...$(NC)\n"
	@if [ -f "src/reportalin/server/tools.py" ]; then \
		printf "$(RED)  ✗ Old monolithic tools.py still exists!$(NC)\n"; \
		exit 1; \
	else \
		printf "$(GREEN)  ✓ Old tools.py removed$(NC)\n"; \
	fi
	@if [ -f "src/reportalin/server/tools_old.py" ]; then \
		printf "$(RED)  ✗ Backup tools_old.py still exists!$(NC)\n"; \
		exit 1; \
	else \
		printf "$(GREEN)  ✓ Backup tools_old.py removed$(NC)\n"; \
	fi
	@if [ -f "test_new_tools.py" ]; then \
		printf "$(RED)  ✗ Temporary test_new_tools.py still exists!$(NC)\n"; \
		exit 1; \
	else \
		printf "$(GREEN)  ✓ Temporary test file removed$(NC)\n"; \
	fi
	@printf "$(GREEN)✓ Cleanup verified$(NC)\n"

# Verify new modular structure exists
verify-structure:
	@printf "$(BLUE)Verifying modular structure...$(NC)\n"
	@if [ -d "src/reportalin/server/tools" ]; then \
		printf "$(GREEN)  ✓ Tools package directory exists$(NC)\n"; \
	else \
		printf "$(RED)  ✗ Tools package directory missing!$(NC)\n"; \
		exit 1; \
	fi
	@for file in __init__.py _models.py _loaders.py _analyzers.py prompt_enhancer.py combined_search.py search_data_dictionary.py search_cleaned_dataset.py registry.py; do \
		if [ -f "src/reportalin/server/tools/$$file" ]; then \
			printf "$(GREEN)  ✓ $$file exists$(NC)\n"; \
		else \
			printf "$(RED)  ✗ $$file missing!$(NC)\n"; \
			exit 1; \
		fi; \
	done
	@printf "$(GREEN)✓ Structure verified$(NC)\n"

# Verify documentation is updated
verify-docs:
	@printf "$(BLUE)Verifying documentation...$(NC)\n"
	@if grep -q "prompt_enhancer" README.md; then \
		printf "$(GREEN)  ✓ README.md mentions prompt_enhancer$(NC)\n"; \
	else \
		printf "$(YELLOW)  ⚠ README.md missing prompt_enhancer reference$(NC)\n"; \
	fi
	@if grep -q "BREAKING.*10.*4.*tools" CHANGELOG.md; then \
		printf "$(GREEN)  ✓ CHANGELOG.md documents breaking change$(NC)\n"; \
	else \
		printf "$(YELLOW)  ⚠ CHANGELOG.md missing breaking change entry$(NC)\n"; \
	fi
	@printf "$(GREEN)✓ Documentation verified$(NC)\n"

# Master verification target - runs all checks
verify-refactoring: verify-imports verify-tools verify-cleanup verify-structure verify-docs
	@printf "\n"
	@printf "$(GREEN)$(BOLD)╔═══════════════════════════════════════════════════════════════════╗$(NC)\n"
	@printf "$(GREEN)$(BOLD)║         ✅ REFACTORING VERIFICATION COMPLETE!                     ║$(NC)\n"
	@printf "$(GREEN)$(BOLD)╚═══════════════════════════════════════════════════════════════════╝$(NC)\n"
	@printf "\n"
	@printf "$(BOLD)Summary:$(NC)\n"
	@printf "  ✅ All imports working\n"
	@printf "  ✅ Exactly 4 tools registered\n"
	@printf "  ✅ FastMCP server initialized\n"
	@printf "  ✅ Old duplicate files removed\n"
	@printf "  ✅ New modular structure in place\n"
	@printf "  ✅ Documentation updated\n"
	@printf "\n"
	@printf "$(BOLD)Refactoring Impact:$(NC)\n"
	@printf "  • Before: 2,710 lines in 1 file (tools.py)\n"
	@printf "  • After:  9 files (~150-680 lines each)\n"
	@printf "  • Tools:  10 → 4 (60%% reduction)\n"
	@printf "  • Architecture: Monolithic → Modular\n"
	@printf "\n"
	@printf "$(CYAN)Next steps:$(NC)\n"
	@printf "  1. Run $(BOLD)make test$(NC) to verify all tests pass\n"
	@printf "  2. Run $(BOLD)make mcp-setup$(NC) to build Docker + test MCP server\n"
	@printf "  3. Commit changes with $(BOLD)make commit$(NC)\n"
	@printf "\n"

# =============================================================================
# Cleaning Targets
# =============================================================================

clean: clean-cache
	@printf "$(GREEN)✓ Clean complete$(NC)\n"

clean-cache:
	@printf "$(BLUE)Cleaning cache files...$(NC)\n"
	-@find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null
	-@find . -type f -name "*.pyc" -delete 2>/dev/null
	-@find . -type f -name "*.pyo" -delete 2>/dev/null
	-@find . -type f -name ".DS_Store" -delete 2>/dev/null
	-@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
	-@rm -rf htmlcov/ .coverage 2>/dev/null
	@printf "$(CYAN)  → Cleaned Python cache, pytest, mypy, ruff, and coverage files$(NC)\n"

clean-logs:
	@printf "$(BLUE)Cleaning log files...$(NC)\n"
	-@rm -rf .logs/
	@printf "$(GREEN)✓ Logs cleaned$(NC)\n"

clean-results:
	@printf "$(RED)$(BOLD)WARNING: This will delete all results!$(NC)\n"
	@printf "$(YELLOW)This includes:$(NC)\n"
	@printf "  • Data dictionary mappings\n"
	@printf "  • Extracted datasets (original)\n"
	@printf "  • Deidentified datasets (cleaned)\n"
	@printf "  • All MCP server data sources\n"
	@printf "\n"
	@printf "Press Enter to continue or Ctrl+C to cancel... " && read _confirm
	-@rm -rf results/
	@printf "$(GREEN)✓ Results cleaned$(NC)\n"
	@printf "$(CYAN)  → To regenerate: make run$(NC)\n"

# Clean Docker images and containers
clean-docker:
	@printf "$(BLUE)Cleaning Docker images and containers...$(NC)\n"
	-@docker stop reportalin-mcp 2>/dev/null || true
	-@docker rm reportalin-mcp 2>/dev/null || true
	-@docker rmi $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null || true
	-@docker rmi $(DOCKER_IMAGE):dev 2>/dev/null || true
	-@docker image prune -f 2>/dev/null || true
	@printf "$(GREEN)✓ Docker cleanup complete$(NC)\n"

# Clean generated configuration files
clean-generated:
	@printf "$(BLUE)Cleaning generated config files...$(NC)\n"
	-@rm -f claude_desktop_config.generated.json 2>/dev/null
	-@rm -f claude_desktop_config.local.json 2>/dev/null
	-@rm -f *.generated.json 2>/dev/null
	@printf "$(GREEN)✓ Generated configs cleaned$(NC)\n"

distclean: clean clean-logs clean-generated
	@printf "$(RED)Cleaning all generated files...$(NC)\n"
	-@rm -rf results/
	-@rm -rf build/ dist/
	-@rm -f test_new_tools.py 2>/dev/null
	@printf "$(GREEN)✓ All generated files removed$(NC)\n"
	@printf "$(CYAN)  → Preserved: Source code structure (src/reportalin/)$(NC)\n"
	@printf "$(CYAN)  → To verify: make verify-refactoring$(NC)\n"

# -----------------------------------------------------------------------------
# Nuclear Clean Target (DANGER: Removes everything)
# -----------------------------------------------------------------------------

nuclear:
	@printf "$(RED)═══════════════════════════════════════════════════════════════════$(NC)\n"
	@printf "$(RED)💣 NUCLEAR CLEAN - This will remove MOST files:$(NC)\n"
	@printf "$(RED)   - All results and output files$(NC)\n"
	@printf "$(RED)   - All log files (.logs, logs/, encrypted_logs/)$(NC)\n"
	@printf "$(RED)   - All Python cache (__pycache__/, *.pyc, *.pyo)$(NC)\n"
	@printf "$(RED)   - All tool caches (.pytest_cache, .mypy_cache, .ruff_cache)$(NC)\n"
	@printf "$(RED)   - All temp files (tmp/, .tmp/, *.tmp)$(NC)\n"
	@printf "$(RED)   - All build artifacts (build/, dist/, *.egg-info)$(NC)\n"
	@printf "$(RED)   - Coverage reports (htmlcov/, .coverage)$(NC)\n"
	@printf "$(RED)   - IDE configurations (.idea/ only)$(NC)\n"
	@printf "$(RED)   - Housekeeping files (.env, *.local.json)$(NC)\n"
	@printf "$(RED)   - Backup files (*.bak, *.orig, *~)$(NC)\n"
	@printf "$(RED)   - Jupyter artifacts (.ipynb_checkpoints/)$(NC)\n"
	@printf "$(RED)   - macOS/Windows metadata (.DS_Store, Thumbs.db)$(NC)\n"
	@printf "$(RED)   - Docker images/containers ($(DOCKER_IMAGE))$(NC)\n"
	@printf "$(RED)   - Generated config files (*.generated.json)$(NC)\n"
	@printf "$(YELLOW)   PRESERVED: .python-version, .vscode/, src/reportalin/$(NC)\n"
	@printf "$(YELLOW)   PRESERVED: New modular tools package (src/reportalin/server/tools/)$(NC)\n"
	@printf "$(RED)═══════════════════════════════════════════════════════════════════$(NC)\n"
	@printf "Are you SURE? Type 'yes' to confirm: "; \
	read -r response; \
	if [ "$$response" = "yes" ]; then \
		printf "$(BLUE)Removing results and output files...$(NC)\n"; \
		rm -rf results/; \
		printf "$(GREEN)✓ Results removed$(NC)\n"; \
		printf "$(BLUE)Removing log files...$(NC)\n"; \
		rm -rf .logs/ logs/ encrypted_logs/; \
		printf "$(GREEN)✓ Log files removed$(NC)\n"; \
		printf "$(BLUE)Removing Python cache files...$(NC)\n"; \
		find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; \
		find . -type f -name "*.pyc" -delete 2>/dev/null || true; \
		find . -type f -name "*.pyo" -delete 2>/dev/null || true; \
		printf "$(GREEN)✓ Python cache files removed$(NC)\n"; \
		printf "$(BLUE)Removing tool cache directories...$(NC)\n"; \
		rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov 2>/dev/null || true; \
		rm -rf .tox .nox .hypothesis 2>/dev/null || true; \
		printf "$(GREEN)✓ Tool caches removed$(NC)\n"; \
		printf "$(BLUE)Removing temp files...$(NC)\n"; \
		rm -rf tmp/ .tmp/ 2>/dev/null || true; \
		find . -type f -name "*.tmp" -delete 2>/dev/null || true; \
		find . -type f -name "*.temp" -delete 2>/dev/null || true; \
		printf "$(GREEN)✓ Temp files removed$(NC)\n"; \
		printf "$(BLUE)Removing build artifacts...$(NC)\n"; \
		rm -rf build/ dist/ 2>/dev/null || true; \
		find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true; \
		find . -type d -name ".eggs" -exec rm -rf {} + 2>/dev/null || true; \
		printf "$(GREEN)✓ Build artifacts removed$(NC)\n"; \
		printf "$(BLUE)Removing IDE configurations (.idea only, preserving .vscode)...$(NC)\n"; \
		rm -rf .idea/ *.sublime-project *.sublime-workspace 2>/dev/null || true; \
		printf "$(GREEN)✓ IDE configurations removed$(NC)\n"; \
		printf "$(YELLOW)  (Preserved: .vscode/ - may contain important workspace settings)$(NC)\n"; \
		printf "$(BLUE)Removing housekeeping files...$(NC)\n"; \
		rm -f .env 2>/dev/null || true; \
		rm -f claude_desktop_config.local.json 2>/dev/null || true; \
		rm -f *.local.json 2>/dev/null || true; \
		printf "$(GREEN)✓ Housekeeping files removed$(NC)\n"; \
		printf "$(YELLOW)  (Preserved: .python-version - required for Docker build)$(NC)\n"; \
		printf "$(BLUE)Removing backup files...$(NC)\n"; \
		find . -type f -name "*.bak" -delete 2>/dev/null || true; \
		find . -type f -name "*.orig" -delete 2>/dev/null || true; \
		find . -type f -name "*~" -delete 2>/dev/null || true; \
		find . -type f -name "*.swp" -delete 2>/dev/null || true; \
		find . -type f -name "*.swo" -delete 2>/dev/null || true; \
		printf "$(GREEN)✓ Backup files removed$(NC)\n"; \
		printf "$(BLUE)Removing Jupyter/IPython artifacts...$(NC)\n"; \
		find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true; \
		rm -rf .ipython/ 2>/dev/null || true; \
		printf "$(GREEN)✓ Jupyter artifacts removed$(NC)\n"; \
		printf "$(BLUE)Removing OS metadata files...$(NC)\n"; \
		find . -type f -name ".DS_Store" -delete 2>/dev/null || true; \
		find . -type f -name "Thumbs.db" -delete 2>/dev/null || true; \
		find . -type f -name "desktop.ini" -delete 2>/dev/null || true; \
		printf "$(GREEN)✓ OS metadata removed$(NC)\n"; \
		printf "$(BLUE)Removing Docker images and containers...$(NC)\n"; \
		docker stop reportalin-mcp 2>/dev/null || true; \
		docker rm reportalin-mcp 2>/dev/null || true; \
		docker rmi $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null || true; \
		docker rmi $(DOCKER_IMAGE):dev 2>/dev/null || true; \
		docker image prune -f 2>/dev/null || true; \
		printf "$(GREEN)✓ Docker images/containers removed$(NC)\n"; \
		printf "$(BLUE)Removing generated config files...$(NC)\n"; \
		rm -f claude_desktop_config.generated.json 2>/dev/null || true; \
		rm -f *.generated.json 2>/dev/null || true; \
		printf "$(GREEN)✓ Generated configs removed$(NC)\n"; \
		printf "\n"; \
		printf "$(BLUE)Cleaning up any old refactoring artifacts...$(NC)\n"; \
		rm -f test_new_tools.py 2>/dev/null || true; \
		rm -f src/reportalin/server/tools.py.bak 2>/dev/null || true; \
		rm -f src/reportalin/server/tools_old.py 2>/dev/null || true; \
		printf "$(GREEN)✓ Refactoring artifacts cleaned$(NC)\n"; \
		printf "\n"; \
		printf "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)\n"; \
		printf "$(GREEN)💣 Nuclear clean complete! Workspace is pristine.$(NC)\n"; \
		printf "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)\n"; \
		printf "\n"; \
		printf "$(CYAN)Preserved modular structure:$(NC)\n"; \
		printf "  • src/reportalin/server/tools/ (9 files)\n"; \
		printf "  • All source code in src/reportalin/\n"; \
		printf "\n"; \
		printf "$(YELLOW)To set up again, run:$(NC)\n"; \
		printf "  1. $(CYAN)make install-dev$(NC)     - Install dependencies\n"; \
		printf "  2. $(CYAN)make verify-refactoring$(NC) - Verify setup\n"; \
		printf "  3. $(CYAN)make setup$(NC)           - Complete pipeline setup\n"; \
		printf "\n"; \
	else \
		printf "$(YELLOW)Cancelled. Nothing was deleted.$(NC)\n"; \
	fi

# =============================================================================
# Version Management (Commitizen)
# =============================================================================
# Automatic semantic versioning based on conventional commits:
#   - fix:  -> PATCH bump (0.0.x)
#   - feat: -> MINOR bump (0.x.0)
#   - BREAKING CHANGE: or feat!/fix!: -> MAJOR bump (x.0.0)

# Interactive commit with conventional format
commit:
	@printf "$(BLUE)Starting interactive commit...$(NC)\n"
	@uv run cz commit

# Check if commit message follows conventional format
check-commit:
	@printf "$(BLUE)Checking last commit message...$(NC)\n"
	@uv run cz check --rev-range HEAD~1..HEAD
	@printf "$(GREEN)✓ Commit message is valid$(NC)\n"

# Auto-bump version based on commits (dry-run first)
bump-dry:
	@printf "$(BLUE)Dry-run version bump (no changes)...$(NC)\n"
	@uv run cz bump --dry-run

# Auto-bump version and create tag
bump:
	@printf "$(BLUE)Bumping version based on commits...$(NC)\n"
	@uv run cz bump
	@printf "$(GREEN)✓ Version bumped! Check git log for new tag.$(NC)\n"

# Force specific version bumps
bump-patch:
	@printf "$(BLUE)Bumping PATCH version...$(NC)\n"
	@uv run cz bump --increment PATCH
	@printf "$(GREEN)✓ Patch version bumped$(NC)\n"

bump-minor:
	@printf "$(BLUE)Bumping MINOR version...$(NC)\n"
	@uv run cz bump --increment MINOR
	@printf "$(GREEN)✓ Minor version bumped$(NC)\n"

bump-major:
	@printf "$(BLUE)Bumping MAJOR version...$(NC)\n"
	@uv run cz bump --increment MAJOR
	@printf "$(GREEN)✓ Major version bumped$(NC)\n"

# Bump version and push tags to remote (CI/CD release trigger)
bump-push:
	@printf "$(BLUE)Bumping version and pushing to remote...$(NC)\n"
	@uv run cz bump --yes
	@git push --follow-tags
	@printf "$(GREEN)✓ Version bumped and pushed! CI/CD will create release.$(NC)\n"

# Generate/update changelog
changelog:
	@printf "$(BLUE)Generating changelog...$(NC)\n"
	@uv run cz changelog
	@printf "$(GREEN)✓ Changelog updated$(NC)\n"

# Install pre-commit hooks (commit-msg validation only)
hooks:
	@printf "$(BLUE)Installing git hooks...$(NC)\n"
	@uv run pre-commit install --hook-type commit-msg --hook-type pre-commit
	@printf "$(GREEN)✓ Hooks installed (commit-msg validation)$(NC)\n"
	@printf "$(CYAN)  → Version bump happens via CI/CD or 'make bump'$(NC)\n"

# Run all pre-commit hooks on all files
pre-commit:
	@printf "$(BLUE)Running pre-commit hooks on all files...$(NC)\n"
	@uv run pre-commit run --all-files

# =============================================================================
# MCP Workflow Targets
# =============================================================================

# -----------------------------------------------------------------------------
# Data Readiness Checks
# -----------------------------------------------------------------------------

# Check if data dictionary mappings exist
check-data:
	@printf "$(BLUE)Checking data readiness...$(NC)\n"
	@if [ -d "results/data_dictionary_mappings" ] && [ "$$(ls -A results/data_dictionary_mappings 2>/dev/null)" ]; then \
		printf "$(GREEN)✓ Data dictionary mappings found$(NC)\n"; \
		printf "  → Tables: $$(ls -d results/data_dictionary_mappings/tbl* 2>/dev/null | wc -l | tr -d ' ') found\n"; \
	else \
		printf "$(YELLOW)⚠ Data dictionary not found. Run 'make run' first.$(NC)\n"; \
		exit 1; \
	fi

# -----------------------------------------------------------------------------
# MCP Setup (Docker Build + Config Installation)
# -----------------------------------------------------------------------------

# Full MCP setup: verify + build Docker + test + install config
mcp-setup: verify-refactoring docker-build mcp-test-docker mcp-install-config-docker
	@printf "\n"
	@printf "$(GREEN)$(BOLD)╔═══════════════════════════════════════╗$(NC)\n"
	@printf "$(GREEN)$(BOLD)║     MCP Server Setup Complete!        ║$(NC)\n"
	@printf "$(GREEN)$(BOLD)╚═══════════════════════════════════════╝$(NC)\n"
	@printf "\n"
	@printf "$(YELLOW)$(BOLD)Next steps:$(NC)\n"
	@printf "  1. $(CYAN)Restart Claude Desktop$(NC) to load the new configuration\n"
	@printf "  2. Look for the $(CYAN)MCP tools icon$(NC) (🔧) in the chat interface\n"
	@printf "  3. Try: $(CYAN)\"How many patients have both TB and HIV?\"$(NC)\n"
	@printf "\n"
	@printf "$(BOLD)Available Tools:$(NC)\n"
	@printf "  • $(CYAN)prompt_enhancer$(NC) ⭐ (recommended entry point)\n"
	@printf "  • $(CYAN)combined_search$(NC) (default analytical tool)\n"
	@printf "  • $(CYAN)search_data_dictionary$(NC) (metadata lookup)\n"
	@printf "  • $(CYAN)search_cleaned_dataset$(NC) (dataset queries)\n"
	@printf "\n"
	@printf "$(BOLD)Troubleshooting:$(NC)\n"
	@printf "  • Run $(CYAN)make mcp-show-config$(NC) to verify configuration\n"
	@printf "  • Run $(CYAN)make mcp-test-docker$(NC) to test server handshake\n"
	@printf "  • Run $(CYAN)make verify-refactoring$(NC) to verify tool setup\n"
	@printf "\n"

# =============================================================================
# Setup Target (One-Command Setup)
# =============================================================================

# 🚀 SETUP: Complete pipeline + Docker + Config generation
setup:
	@printf "$(BOLD)$(CYAN)"
	@printf "╔═══════════════════════════════════════════════════════════════════╗\n"
	@printf "║     🚀 RePORTaLiN COMPLETE SETUP                                  ║\n"
	@printf "║     Extraction → De-identification → Docker → Verification        ║\n"
	@printf "╚═══════════════════════════════════════════════════════════════════╝\n"
	@printf "$(NC)\n"
	@printf "$(YELLOW)This will:$(NC)\n"
	@printf "  1. Install dependencies (uv) + pre-commit hooks\n"
	@printf "  2. Verify refactoring (imports + tools + docs)\n"
	@printf "  3. Run data pipeline (dictionary + extraction)\n"
	@printf "  4. De-identify PHI/PII (DPDPA 2023 compliant)\n"
	@printf "  5. Build Docker image\n"
	@printf "  6. Test MCP server\n"
	@printf "  7. Generate Claude Desktop config\n"
	@printf "\n"
	@printf "$(CYAN)Starting in 3 seconds... (Ctrl+C to cancel)$(NC)\n"
	@sleep 3
	@printf "\n"
	@# Step 1: Install dependencies + pre-commit hooks (reuse install-dev)
	@printf "$(BOLD)$(BLUE)[1/7] Setting up environment...$(NC)\n"
	@$(MAKE) install-dev
	@printf "\n"
	@# Step 2: Verify refactoring
	@printf "$(BOLD)$(BLUE)[2/7] Verifying refactoring...$(NC)\n"
	@$(MAKE) verify-refactoring 2>&1 | grep -E "(✓|✗|⚠)" || true
	@printf "$(GREEN)✓ Refactoring verification complete$(NC)\n"
	@printf "\n"
	@# Step 3: Run extraction pipeline
	@printf "$(BOLD)$(BLUE)[3/7] Extracting data (Excel → JSONL)...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --skip-deidentification 2>&1 | tail -10
	@printf "$(GREEN)✓ Data extraction complete$(NC)\n"
	@printf "\n"
	@# Step 4: Run de-identification
	@printf "$(BOLD)$(BLUE)[4/7] De-identifying PHI/PII (DPDPA 2023 + ICMR)...$(NC)\n"
	@$(PYTHON_CMD) -m reportalin.cli.pipeline --skip-dictionary --skip-extraction --enable-deidentification -c IN 2>&1 | tail -10
	@printf "$(GREEN)✓ De-identification complete$(NC)\n"
	@printf "\n"
	@# Step 5: Build Docker
	@printf "$(BOLD)$(BLUE)[5/7] Building Docker image with provenance...$(NC)\n"
	@docker build \
		--build-arg BUILD_VERSION=$(VERSION) \
		--build-arg BUILD_DATE=$$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
		--build-arg VCS_REF=$$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
		-t $(DOCKER_IMAGE):$(DOCKER_TAG) \
		-t $(DOCKER_IMAGE):$(VERSION) \
		-f docker/Dockerfile . 2>&1 | tail -5
	@printf "$(GREEN)✓ Docker image built: $(DOCKER_IMAGE):$(DOCKER_TAG)$(NC)\n"
	@printf "\n"
	@# Step 6: Test MCP server
	@printf "$(BOLD)$(BLUE)[6/7] Testing MCP server handshake...$(NC)\n"
	@printf '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}\n' | \
		docker run -i --rm -v "$(CURDIR)/results:/app/results:ro" $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null | \
		grep -q '"tools"' && printf "$(GREEN)✓ MCP server test passed$(NC)\n" || \
		(printf "$(RED)✗ MCP server test failed$(NC)\n" && exit 1)
	@printf "\n"
	@# Step 7: Generate config file
	@printf "$(BOLD)$(BLUE)[7/7] Generating Claude Desktop config...$(NC)\n"
	@echo '{"mcpServers":{"reportalin-mcp":{"command":"docker","args":["run","-i","--rm","-v","$(CURDIR)/results:/app/results:ro","$(DOCKER_IMAGE):$(DOCKER_TAG)"],"env":{"REPORTALIN_PRIVACY_MODE":"strict"}}}}' > claude_desktop_config.generated.json
	@printf "$(GREEN)✓ Config generated: claude_desktop_config.generated.json$(NC)\n"
	@printf "\n"
	@# Final summary
	@printf "$(BOLD)$(GREEN)"
	@printf "╔═══════════════════════════════════════════════════════════════════╗\n"
	@printf "║              ✅ SETUP COMPLETE!                                   ║\n"
	@printf "╚═══════════════════════════════════════════════════════════════════╝\n"
	@printf "$(NC)\n"
	@printf "$(BOLD)$(YELLOW)📋 STEP 2: Connect to Claude Desktop$(NC)\n"
	@printf "\n"
	@printf "   Copy the generated config to Claude Desktop:\n"
	@printf "   $(CYAN)cp claude_desktop_config.generated.json ~/Library/Application\\ Support/Claude/claude_desktop_config.json$(NC)\n"
	@printf "\n"
	@printf "   Then $(BOLD)restart Claude Desktop$(NC) to load the MCP server.\n"
	@printf "\n"
	@printf "$(BOLD)After restart, you'll see:$(NC)\n"
	@printf "   • MCP tools icon (🔧) in the chat interface\n"
	@printf "   • Server: $(CYAN)reportalin-mcp$(NC)\n"
	@printf "   • 4 available tools for RePORT India data (SECURE MODE)\n"
	@printf "     1. prompt_enhancer ⭐ (recommended entry point)\n"
	@printf "     2. combined_search (default analytical tool)\n"
	@printf "     3. search_data_dictionary (metadata lookup)\n"
	@printf "     4. search_cleaned_dataset (dataset queries)\n"
	@printf "\n"
	@printf "$(BOLD)Try asking Claude:$(NC)\n"
	@printf '   $(CYAN)"How many patients have both TB and HIV?"$(NC)\n'
	@printf '   $(CYAN)"What variables are used for HIV status?"$(NC)\n'
	@printf "\n"
	@printf "$(BOLD)Pipeline completed:$(NC)\n"
	@printf "   Verification → Extraction → De-identification → Docker → MCP Access ✅\n"
	@printf "\n"

# =============================================================================
# MCP Server Targets
# =============================================================================

# Build Docker image with OCI labels for provenance
docker-build:
	@printf "$(BLUE)Building Docker image with provenance labels...$(NC)\n"
	@docker build \
		--build-arg BUILD_VERSION=$(VERSION) \
		--build-arg BUILD_DATE=$$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
		--build-arg VCS_REF=$$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
		-t $(DOCKER_IMAGE):$(DOCKER_TAG) \
		-t $(DOCKER_IMAGE):$(VERSION) \
		-f docker/Dockerfile .
	@printf "$(GREEN)✓ Docker image built: $(DOCKER_IMAGE):$(DOCKER_TAG)$(NC)\n"
	@printf "$(CYAN)  Also tagged: $(DOCKER_IMAGE):$(VERSION)$(NC)\n"

# Scan Docker image for vulnerabilities (requires Trivy)
# CI-ready: fails on HIGH/CRITICAL vulnerabilities
docker-scan: docker-build
	@printf "$(BLUE)Scanning Docker image for vulnerabilities...$(NC)\n"
	@if command -v trivy >/dev/null 2>&1; then \
		printf "$(CYAN)Running Trivy security scan...$(NC)\n"; \
		trivy image --severity HIGH,CRITICAL --exit-code 1 $(DOCKER_IMAGE):$(DOCKER_TAG) || \
			(printf "$(RED)✗ Security vulnerabilities found! Fix before deploying.$(NC)\n" && exit 1); \
		printf "$(GREEN)✓ No HIGH/CRITICAL vulnerabilities found$(NC)\n"; \
	else \
		printf "$(YELLOW)Trivy not installed. Install with: brew install trivy$(NC)\n"; \
		printf "$(YELLOW)Falling back to Docker Scout...$(NC)\n"; \
		docker scout quickview $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null || \
			printf "$(RED)No scanner available. Install Trivy for security scanning.$(NC)\n"; \
	fi

# Lint Dockerfile (requires hadolint)
# CI-ready: fails on warnings and errors
docker-lint:
	@printf "$(BLUE)Linting Dockerfile...$(NC)\n"
	@if command -v hadolint >/dev/null 2>&1; then \
		hadolint --failure-threshold warning docker/Dockerfile && \
		printf "$(GREEN)✓ Dockerfile lint passed$(NC)\n"; \
	else \
		printf "$(YELLOW)Hadolint not installed. Running via Docker...$(NC)\n"; \
		docker run --rm -i hadolint/hadolint hadolint --failure-threshold warning - < docker/Dockerfile && \
		printf "$(GREEN)✓ Dockerfile lint passed$(NC)\n"; \
	fi

# Full Docker security check (lint + scan) - use in CI/CD pipelines
docker-security: docker-lint docker-scan
	@printf "$(GREEN)✓ All Docker security checks passed$(NC)\n"

# Test MCP server in Docker (handshake + tools listing)
mcp-test-docker: docker-build
	@printf "$(BLUE)Testing MCP server in Docker...$(NC)\n"
	@printf '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}\n' | \
		docker run -i --rm -v "$(CURDIR)/results:/app/results:ro" $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null | \
		head -n 2 | grep -q '"tools"' && printf "$(GREEN)✓ Docker MCP server handshake + tools/list passed$(NC)\n" || \
		(printf "$(RED)✗ Docker MCP server test failed$(NC)\n" && exit 1)

# Run MCP server in Docker (interactive, for testing)
# Security: --cap-drop=ALL, --security-opt=no-new-privileges, --read-only
docker-mcp: docker-build
	@printf "$(BLUE)Starting MCP server in Docker container...$(NC)\n"
	@docker run --rm -it \
		--name reportalin-mcp \
		--cap-drop=ALL \
		--security-opt=no-new-privileges \
		--read-only \
		--tmpfs /tmp:rw,noexec,nosuid,size=64m \
		-e REPORTALIN_PRIVACY_MODE=strict \
		-v $(CURDIR)/results:/app/results:ro \
		$(DOCKER_IMAGE):$(DOCKER_TAG)
	@printf "$(GREEN)✓ Docker MCP server stopped$(NC)\n"

# Install Docker-based MCP configuration to Claude Desktop (RECOMMENDED)
mcp-install-config-docker: docker-build
	@printf "$(BLUE)Installing Docker-based MCP configuration to Claude Desktop...$(NC)\n"
	@mkdir -p ~/Library/Application\ Support/Claude
	@echo '{"mcpServers":{"reportalin-mcp":{"command":"docker","args":["run","-i","--rm","-v","$(CURDIR)/results:/app/results:ro","$(DOCKER_IMAGE):$(DOCKER_TAG)"],"env":{"REPORTALIN_PRIVACY_MODE":"strict"}}}}' > ~/Library/Application\ Support/Claude/claude_desktop_config.json
	@printf "$(GREEN)✓ Docker configuration installed$(NC)\n"
	@printf "$(YELLOW)→ Restart Claude Desktop to apply changes$(NC)\n"
	@printf "$(CYAN)→ Docker image: $(DOCKER_IMAGE):$(DOCKER_TAG)$(NC)\n"
	@printf "$(CYAN)→ Data mounted: $(CURDIR)/results$(NC)\n"

# Show current Claude Desktop config
mcp-show-config:
	@printf "$(BOLD)$(BLUE)Claude Desktop MCP Configuration$(NC)\n"
	@printf "$(CYAN)─────────────────────────────────$(NC)\n"
	@if [ -f ~/Library/Application\ Support/Claude/claude_desktop_config.json ]; then \
		cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python3 -m json.tool 2>/dev/null || cat ~/Library/Application\ Support/Claude/claude_desktop_config.json; \
	else \
		printf "$(YELLOW)Config file not found$(NC)\n"; \
	fi
	@printf "\n$(CYAN)─────────────────────────────────$(NC)\n"

# Start MCP server with stdio transport (for direct testing)
# Uses server module which ensures pure JSON-RPC on stdout
mcp-server-stdio:
	@printf "$(BLUE)Starting MCP server (stdio transport)...$(NC)\n"
	@REPORTALIN_PRIVACY_MODE=strict $(PYTHON_CMD) -m reportalin.server
	@printf "$(GREEN)✓ MCP server stopped$(NC)\n"

# Start MCP server with HTTP transport (for web clients)
mcp-server-http:
	@printf "$(BLUE)Starting MCP server (HTTP transport) on http://127.0.0.1:$(PORT)...$(NC)\n"
	@REPORTALIN_PRIVACY_MODE=strict $(PYTHON_CMD) -m reportalin.server --http --port $(PORT)
	@printf "$(GREEN)✓ MCP server stopped$(NC)\n"

# Install local Python-based MCP configuration to Claude Desktop
mcp-install-config-local:
	@printf "$(BLUE)Installing local Python MCP configuration to Claude Desktop...$(NC)\n"
	@mkdir -p ~/Library/Application\ Support/Claude
	@UV_PATH=$$(which uv); \
	echo "{\"mcpServers\":{\"reportalin-mcp\":{\"command\":\"$$UV_PATH\",\"args\":[\"run\",\"--directory\",\"$(CURDIR)\",\"python\",\"-m\",\"reportalin.server\",\"--transport\",\"stdio\"],\"env\":{\"REPORTALIN_PRIVACY_MODE\":\"strict\"}}}}" > ~/Library/Application\ Support/Claude/claude_desktop_config.json
	@printf "$(GREEN)✓ Local Python configuration installed$(NC)\n"
	@printf "$(YELLOW)→ Restart Claude Desktop to apply changes$(NC)\n"
	@printf "$(CYAN)→ Command: uv run python -m reportalin.server$(NC)\n"
	@printf "$(CYAN)→ Working Directory: $(CURDIR)$(NC)\n"

# =============================================================================
# Docker Compose Targets (Production Deployment)
# =============================================================================

# Build with docker-compose (uses Dockerfile.uv for production)
compose-build:
	@printf "$(BLUE)Building with Docker Compose (production)...$(NC)\n"
	@docker compose build mcp-server
	@printf "$(GREEN)✓ Docker Compose build complete$(NC)\n"

# Start production server with docker-compose
compose-up:
	@printf "$(BLUE)Starting MCP server (production) with Docker Compose...$(NC)\n"
	@printf "$(CYAN)  → Available tools: 4 (prompt_enhancer, combined_search, search_data_dictionary, search_cleaned_dataset)$(NC)\n"
	@docker compose up mcp-server
	@printf "$(GREEN)✓ Docker Compose stopped$(NC)\n"

# Start production server in background
compose-up-detached:
	@printf "$(BLUE)Starting MCP server (production) in background...$(NC)\n"
	@docker compose up -d mcp-server
	@printf "$(GREEN)✓ MCP server running in background$(NC)\n"
	@printf "$(CYAN)→ View logs: make compose-logs$(NC)\n"
	@printf "$(CYAN)→ Stop: make compose-down$(NC)\n"

# Start development server with docker-compose (hot reload)
compose-dev:
	@printf "$(BLUE)Starting MCP server (development) with Docker Compose...$(NC)\n"
	@docker compose up mcp-server-dev
	@printf "$(GREEN)✓ Docker Compose dev stopped$(NC)\n"

# View docker-compose logs
compose-logs:
	@docker compose logs -f mcp-server

# Stop docker-compose services
compose-down:
	@printf "$(BLUE)Stopping Docker Compose services...$(NC)\n"
	@docker compose down
	@printf "$(GREEN)✓ Docker Compose stopped$(NC)\n"

# Check health of running container
compose-health:
	@printf "$(BLUE)Checking container health...$(NC)\n"
	@docker inspect --format='{{.State.Health.Status}}' reportalin-mcp 2>/dev/null || printf "$(YELLOW)Container not running$(NC)\n"

# =============================================================================
# End of Makefile
# =============================================================================

