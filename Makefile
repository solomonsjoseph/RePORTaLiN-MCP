# RePORTaLiN MCP Server - Minimal Makefile
# =========================================
# A single-tool MCP server for variable search via Claude Desktop
#
# Quick Start (Choose Your Environment):
#   make dev      - 🧑‍💻 Development: install + extract + serve (no email alerts)
#   make prod     - 🚀 Production: install + extract + serve (WITH email alerts)
#
# Other Commands:
#   make test     - Run tests
#   make clean    - Remove cache
#   make nuclear  - 🚨 Fresh start (removes venv + results + cache)

.PHONY: all help dev prod install extract serve serve-prod test lint clean nuclear

.DEFAULT_GOAL := help

all: install extract
	@echo "✓ Build complete - ready to run 'make serve'"

help:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "  RePORTaLiN MCP Server - Variable Search Tool"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "🚀 Quick Start (Choose Your Environment):"
	@echo "  make dev        🧑‍💻 Development mode (no email alerts)"
	@echo "                  → install + extract + serve"
	@echo ""
	@echo "  make prod       🚀 Production mode (with email alerts)"
	@echo "                  → install + extract + serve with monitoring"
	@echo "                  ⚠️  Requires: .env.email configured"
	@echo ""
	@echo "───────────────────────────────────────────────────────────────"
	@echo "📦 Build Commands:"
	@echo "  make all        Build everything (install + extract)"
	@echo "  make install    Install dependencies (uv sync)"
	@echo "  make extract    Extract Excel → JSONL"
	@echo ""
	@echo "🔧 Server Commands:"
	@echo "  make serve      Start server (dev mode, no email)"
	@echo "  make serve-prod Start server (prod mode, with email)"
	@echo ""
	@echo "🧪 Quality Commands:"
	@echo "  make test       Run tests"
	@echo "  make lint       Check code quality"
	@echo ""
	@echo "🧹 Cleanup Commands:"
	@echo "  make clean      Remove cache/logs"
	@echo "  make nuclear    🚨 REMOVE EVERYTHING (venv + results + cache)"
	@echo ""
	@echo "───────────────────────────────────────────────────────────────"
	@echo "💡 Performance Tips:"
	@echo "  make -j4 test   Run tests with 4 parallel jobs"
	@echo "  make -j\$$(nproc) test  Use all CPU cores"
	@echo "═══════════════════════════════════════════════════════════════"

dev: install extract serve
	@echo "✓ Development server complete"

prod: install extract serve-prod
	@echo "✓ Production server complete"

install:
	uv sync --extra data-prep

extract:
	uv run python -m reportalin.data.load_dictionary

serve:
	@echo "🧑‍💻 Starting development server (email alerts: disabled)..."
	uv run python -m reportalin.server.__main__

serve-prod:
	@echo "🚀 Starting production server (email alerts: enabled)..."
	@if [ ! -f .env.email ]; then \
		echo "⚠️  WARNING: .env.email not found!"; \
		echo "   Email alerts will be disabled unless SMTP_* env vars are set."; \
		echo "   Copy .env.email.example to .env.email and configure it."; \
		echo ""; \
	fi
	@echo "Loading production environment..."
	@if [ -f .env.email ]; then \
		set -a; source .env.email; set +a; \
	fi; \
	ENABLE_EMAIL_ALERTS=true uv run python -m reportalin.server.__main__

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

clean:
	@echo "Cleaning cache files and directories..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true
	@rm -rf htmlcov .coverage .coverage.* 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info 2>/dev/null || true
	@rm -rf logs/*.log 2>/dev/null || true
	@rm -rf .tox/ .nox/ 2>/dev/null || true
	@find . -type f \( -name "*.tmp" -o -name "*.swp" -o -name "*~" \) -delete 2>/dev/null || true
	@echo "✓ Clean complete - removed all cache, build, and temporary files"

nuclear: clean
	@echo "🚨 NUCLEAR CLEAN - This will PERMANENTLY DELETE:"
	@echo "   • .venv/ (virtual environment)"
	@echo "   • results/ (extracted JSONL files)"
	@echo "   • All cache files"
	@echo ""
	@echo "You will need to run 'make dev' or 'make prod' to rebuild everything."
	@echo ""
	@read -p "Are you sure you want to continue? (y/N): " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🗑️  Removing .venv/..."; \
		rm -rf .venv/ 2>/dev/null || true; \
		echo "🗑️  Removing results/..."; \
		rm -rf results/ 2>/dev/null || true; \
		echo "✓ Nuclear clean complete - workspace reset to fresh state"; \
		echo "   Next step: Run 'make run' to rebuild everything"; \
	else \
		echo "❌ Aborted - nothing was deleted"; \
		exit 1; \
	fi
