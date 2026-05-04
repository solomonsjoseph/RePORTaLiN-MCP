# Contributing to RePORTaLiN-Specialist

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create a branch** for your feature: `git checkout -b feature/your-feature`
4. **Set up** the development environment:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies including dev tools (recommended)
make install-dev

# This automatically:
# - Installs all dependencies via uv sync --all-extras
# - Sets up pre-commit hooks for automatic linting on commit
```

## Development Workflow

### Before Making Changes

1. Pull the latest changes from `main`
2. Create a feature branch with a descriptive name
3. Review existing code patterns in similar files
4. Ensure pre-commit hooks are installed: `uv run pre-commit install`

### Code Standards

Run these before committing:

```bash
make lint      # Check code style (ruff)
make format    # Auto-format code
make typecheck # Type checking (mypy)
make test      # Run test suite
```

### Commit Guidelines

This project uses [Conventional Commits](https://www.conventionalcommits.org/) with [Commitizen](https://commitizen-tools.github.io/commitizen/) for automated versioning.

**Commit Types:**

| Type       | Description                  | Version Bump |
|------------|------------------------------|--------------|
| `feat:`    | New features                 | MINOR        |
| `fix:`     | Bug fixes                    | PATCH        |
| `docs:`    | Documentation changes        | —            |
| `style:`   | Formatting (no code change)  | —            |
| `refactor:`| Code restructuring           | —            |
| `perf:`    | Performance improvements     | PATCH        |
| `test:`    | Test additions/changes       | —            |
| `build:`   | Build system changes         | —            |
| `ci:`      | CI configuration             | —            |
| `chore:`   | Maintenance tasks            | —            |

**Using Commitizen:**

```bash
# Interactive commit (recommended)
cz commit

# Check commit message format
cz check --commit-msg-file .git/COMMIT_EDITMSG

# Bump version based on commits
cz bump

# Generate changelog
cz changelog
```

**Breaking Changes:**

```bash
# Add ! after type for breaking changes
feat!: remove deprecated API endpoint

# Or add BREAKING CHANGE footer
feat: restructure data model

BREAKING CHANGE: field names have changed
```

### Pull Request Process

1. Ensure all checks pass (`make lint test`)
2. Update documentation if needed
3. Add tests for new functionality
4. Update `CHANGELOG.md` under `[Unreleased]`
5. Submit PR with a clear description

## PHI/PII Guidelines

> [!IMPORTANT]
> This project handles Protected Health Information.

**Never commit:**

- Patient data (real or synthetic with identifying info)
- API keys or credentials
- Unencrypted data mappings
- Encryption private keys

**Always:**

- Use aggregate statistics in examples
- Redact PHI in documentation
- Test with synthetic, fully anonymized data
- Follow patterns in `server/` for sensitive operations

See [SECURITY.md](SECURITY.md) for complete security guidelines.

## Adding MCP Tools

When adding new MCP tools:

1. Define Pydantic models in `shared/models.py`
2. Implement tool logic in `server/tools.py`
3. Register with FastMCP in `server/main.py`
4. Add tests in `tests/unit/test_mcp_server.py`
5. Document in `docs/MCP_SERVER_SETUP.md`

**Tool requirements:**

- Clear, descriptive tool descriptions (LLMs rely on these)
- Valid JSON Schema for input parameters
- K-anonymity enforcement for any data access
- Encrypted logging for sensitive operations

## Documentation

Follow [Diátaxis](https://diataxis.fr/) principles:

- **Tutorials** — Learning-oriented guides
- **How-to Guides** — Problem-solving recipes
- **Reference** — Technical specifications
- **Explanation** — Conceptual discussions

Use GitHub Flavored Markdown with:

- Clear headings (`##` for sections)
- Code blocks with language tags
- Tables for structured data
- Admonitions (`> [!NOTE]`, `> [!WARNING]`)

## Questions?

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Tag issues appropriately (`bug`, `enhancement`, `documentation`)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
