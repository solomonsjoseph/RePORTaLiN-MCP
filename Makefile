# RePORTaLiN MCP Server - Makefile
# ===================================
# Simple build automation for 3-tool MCP server

.PHONY: help install extract serve run nuke test clean config

.DEFAULT_GOAL := help

help:
	@echo "══════════════════════════════════════════════"
	@echo "  RePORTaLiN MCP Server"
	@echo "══════════════════════════════════════════════"
	@echo ""
	@echo "🚀 One-Command Workflows:"
	@echo "  make run         Setup system (install + extract)"
	@echo "  make dev         Full dev cycle (run + serve)"
	@echo "  make nuke        Nuclear clean (wipe everything)"
	@echo ""
	@echo "📦 Individual Commands:"
	@echo "  make install     Install dependencies"
	@echo "  make extract     Extract data dictionary"
	@echo "  make config      Generate Claude Desktop config"
	@echo "  make serve       Start MCP server (stdio - waits for Claude)"
	@echo "  make test        Run tests"
	@echo "  make clean       Remove caches only"
	@echo "══════════════════════════════════════════════"

run: install extract config
	@echo ""
	@echo "✅ System ready!"
	@echo ""
	@echo "Next steps:"
	@echo "  • Run 'make serve' to start stdio server (for Claude Desktop)"
	@echo "  • Run 'make test' to verify functionality"
	@echo "  • Or integrate with Claude Desktop (see README.md)"
	@echo "  • Claude Desktop config generated at: claude_desktop_config.json"
	@echo ""

dev: run serve

install:
	@echo "📦 Installing dependencies..."
	@uv sync --extra data-prep

extract:
	@echo "📚 Extracting data dictionary..."
	@uv run python -m reportalin.data.load_dictionary
	@uv run python -m reportalin.data.load_dataset_headers
	@echo "✅ Data extraction complete"

config:
	@echo "🔧 Generating Claude Desktop config..."
	@uv run python scripts/generate_claude_config.py
	@echo "✅ Claude Desktop config generated at: claude_desktop_config.json"
	@echo "copying to claude desktop config location..."
	@mkdir -p ~/Library/Application\ Support/Claude\ Desktop/configs
	@cp claude_desktop_config.json ~/Library/Application\ Support/Claude\ Desktop/configs/claude_desktop_config.json
	@echo "✅ Config copied to Claude Desktop configs folder."

serve:
	@echo "🚀 Starting MCP server (stdio mode)..."
	@echo ""
	@echo "⚠️  Server will wait for JSON-RPC input from Claude Desktop."
	@echo "    This is NORMAL - the server is not stuck!"
	@echo ""
	@echo "    Press Ctrl+C to stop the server."
	@echo ""
	@trap 'echo ""; echo "🛑 Server stopped."; exit 0' INT TERM; \
	uv run python -m reportalin.server; \
	echo ""; echo "🛑 Server stopped."

test:
	@uv run pytest tests/ -v

clean:
	@echo "🧹 Cleaning caches..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*verify*.py" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true
	@echo "✅ Cache cleanup complete"

nuke:
	@echo "💣 NUCLEAR CLEAN - Wiping everything..."
	@echo "⚠️  This will delete:"
	@echo "   - results/ (all extracted JSONL files)"
	@echo "   - logs/ (all log files)"
	@echo "   - Housekeeping files (*AUDIT*, *STATUS*, *SUMMARY*, *FIX*, etc.)"
	@echo "   - Generated files (_version.py, claude_desktop_config.json, etc.)"
	@echo "   - All Python caches"
	@echo "   - Virtual environment (.venv)"
	@echo ""
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf results/ logs/ .venv; \
		find . -maxdepth 1 -type f \( \
			-name "*AUDIT*.md" -o \
			-name "*STATUS*.md" -o \
			-name "*SUMMARY*.md" -o \
			-name "*REPORT*.md" -o \
			-name "*VERIFICATION*.md" -o \
			-name "*IMPLEMENTATION*.md" -o \
			-name "*ASSESSMENT*.md" -o \
			-name "*FIX*.md" -o \
			-name "CLEANUP_REPORT.md" -o \
			-name "*STDIO*.md" -o \
			-name "FIXES.md" -o \
			-name "NOTES.md" -o \
			-name "CHANGES.md" -o \
			-name "claude_desktop_config.json" -o \
			-name "test_claude_desktop_integration.py" \
		\) -delete 2>/dev/null || true; \
		rm -f src/reportalin/_version.py 2>/dev/null || true; \
		find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true; \
		find . -type f -name "*.pyc" -delete 2>/dev/null || true; \
		find . -type f -name "*.pyo" -delete 2>/dev/null || true; \
		find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true; \
		rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true; \
		echo "💥 Nuclear clean complete! Run 'make run' for fresh start."; \
	else \
		echo "❌ Aborted."; \
	fi
