# Contributing to Aeromux Database Builder

Thank you for your interest in contributing to Aeromux Database Builder! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13 or later** - [Download here](https://www.python.org/downloads/)
- **uv** - Fast Python package manager - [Install here](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** - Version control system
- **IDE** (recommended):
  - JetBrains PyCharm
  - Visual Studio Code with the Python extension

### Fork and Clone

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/aeromux-db.git
   cd aeromux-db
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/nandortoth/aeromux-db.git
   ```
4. Keep your fork up to date:
   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

## Development Setup

### Setting Up the Environment

```bash
# Create virtual environment and install dependencies
uv sync

# Or install in development mode with pip
pip install -e .
```

### Running the Builder

```bash
# Run via uv
uv run aeromux-db

# Run with verbose output
uv run aeromux-db --verbose

# Or run directly as a module
python -m aeromux_db
```

### Verify Code Style

```bash
# Format code
uv run ruff format

# Check formatting without making changes
uv run ruff format --check

# Lint code
uv run ruff check

# Lint and auto-fix
uv run ruff check --fix
```

## Architecture Overview

Aeromux Database Builder follows a sequential pipeline architecture:

```
src/aeromux_db/
├── __init__.py           # Package version
├── __main__.py           # Entry point and pipeline orchestration
├── cli.py                # Command-line argument parsing
├── downloader.py         # File download and archive extraction
├── models.py             # Data models (Aircraft, AircraftType, Operator)
├── version.py            # Calendar-based database version computation
├── builder.py            # SQLite database construction
└── sources/
    ├── mictronics.py     # Mictronics data source parser
    ├── adsbexchange.py   # ADS-B Exchange data source parser
    ├── opensky.py        # OpenSky Network data source parser
    └── typelongnames.py  # Type-longnames data source parser
```

**Pipeline flow:** Download → Extract → Parse → Merge → Build

For detailed documentation on data source formats, merge logic, and conflict resolution rules, see the [Developer Guide](DEVELOPER.md).

When contributing, place your code in the appropriate module:

- **New data sources** go in `sources/` as separate modules.
- **New data models** go in `models.py`.
- **Download/extraction logic** goes in `downloader.py`.
- **Database schema and insertion** goes in `builder.py`.
- **CLI arguments** go in `cli.py`.

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes** - Fix issues and improve stability
- **New data sources** - Add parsers for additional aircraft data sources
- **Documentation** - Improve or add documentation
- **Tests** - Add or improve test coverage
- **Code quality** - Refactoring and improvements
- **Tooling** - Improve build scripts, CI/CD, packaging

### Contribution Workflow

1. **Check existing issues** - Look for existing issues or create a new one.
2. **Discuss major changes** - For significant changes, open an issue first to discuss the approach.
3. **Create a branch** - Use a descriptive branch name (see below).
4. **Make your changes** - Follow the coding standards.
5. **Write tests** - Add tests for new functionality.
6. **Run tests** - All tests must pass.
7. **Update documentation** - Update relevant docs and docstrings.
8. **Commit your changes** - Use clear commit messages.
9. **Open a Pull Request** - Submit your PR with a clear description.

### Branch Naming Convention

Use descriptive branch names following this pattern:

```
feature/description       # New features
bugfix/description        # Bug fixes
docs/description          # Documentation updates
refactor/description      # Code refactoring
test/description          # Test additions/improvements
```

Examples:

```bash
git checkout -b feature/add-opensky-source
git checkout -b bugfix/fix-unicode-parsing
git checkout -b docs/add-schema-documentation
```

## Coding Standards

### Code Style

This project uses **Ruff** for formatting and linting. Key rules:

#### Formatting

- **Indentation:** 4 spaces
- **Line length:** 88 characters (Ruff default)
- **Line endings:** LF (Unix-style) for all source files
- **Quotes:** Double quotes for strings

#### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Classes | `PascalCase` | `AircraftType`, `Operator` |
| Functions, Methods | `snake_case` | `parse_types()`, `build_database()` |
| Variables | `snake_case` | `icao_address`, `data_dir` |
| Constants | `UPPER_SNAKE_CASE` | `SOURCE_URL`, `SOURCE_FILENAME` |
| Private functions | `_snake_case` | `_format_file_size()`, `_clear_progress_line()` |

#### Type Annotations

All public functions must have type annotations for parameters and return values:

```python
def parse_types(data_dir: Path) -> list[AircraftType]:
    ...
```

### Docstrings

All public APIs must have Google-style docstrings:

```python
def build_database(
    aircraft: list[Aircraft],
    types: list[AircraftType],
    operators: list[Operator],
) -> Path:
    """Build the SQLite database and return the output path.

    Insert parsed aircraft, type, and operator records into a SQLite
    database with schema versioning and build metadata.

    Args:
        aircraft: Parsed aircraft records with ICAO 24-bit addresses.
        types: Parsed aircraft type records keyed by ICAO type designator.
        operators: Parsed operator records keyed by ICAO airline designator.

    Returns:
        Path to the generated SQLite database file in the artifacts directory.

    Raises:
        sqlite3.OperationalError: When the schema file is missing or invalid.
    """
```

### Comments

- Comments should explain **WHY**, not **WHAT**.
- Use inline comments sparingly and only when logic is non-obvious.
- All source files must include the GPL license header.

## Testing

### Test Framework

The project uses **pytest**:

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_models.py

# Run tests with coverage
uv run pytest --cov=aeromux_db
```

### Test Organization

Tests are located in the `tests/` directory:

```
tests/
├── __init__.py
├── test_models.py
├── test_downloader.py
├── test_builder.py
└── test_sources/
    └── test_mictronics.py
```

### Writing Tests

- Place tests in files that mirror the source module structure.
- Use descriptive test function names that describe the scenario and expected behavior.
- Use pytest fixtures for shared setup.

```python
def test_parse_types_returns_correct_count(tmp_path: Path) -> None:
    """Verify that parse_types returns one record per type code."""
    types_data = {"B738": ["Boeing 737-800", "L2J"]}
    (tmp_path / "types.json").write_text(json.dumps(types_data))

    result = parse_types(tmp_path)

    assert len(result) == 1
    assert result[0].type_code == "B738"
```

## Pull Request Process

### Before Submitting

Ensure your PR meets these requirements:

- [ ] Code follows the project's style guidelines
- [ ] Code passes linting: `uv run ruff check`
- [ ] Code formatting is correct: `uv run ruff format --check`
- [ ] All existing tests pass: `uv run pytest`
- [ ] New code has appropriate test coverage
- [ ] Public APIs have Google-style docstrings
- [ ] CHANGELOG.md is updated with your changes
- [ ] Commit messages are clear and descriptive

### PR Title Format

Use a clear, descriptive title following conventional commits:

```
feat: Add OpenSky Network data source
fix: Correct Unicode handling in operator names
docs: Add schema documentation
refactor: Simplify JSON parsing logic
test: Add unit tests for downloader caching
```

### PR Description

Include in your PR description:

- **What** the PR does and **why**.
- How you **tested** the changes.
- Any **breaking changes** or **migration steps** required.

### Review Process

1. A maintainer will review your PR.
2. Feedback may be provided - please address review comments.
3. Once approved, a maintainer will merge your PR.
4. Your contribution will be included in the next release.

## Reporting Bugs

### Before Reporting

- Check if the bug has already been reported in [Issues](https://github.com/nandortoth/aeromux-db/issues).
- Ensure you are using the latest version.
- Verify the issue is reproducible.

### Bug Report Contents

When reporting bugs, include:

- **Description** - Clear description of the bug.
- **Steps to reproduce** - Minimal steps to trigger the issue.
- **Expected vs. actual behavior** - What you expected and what happened.
- **Environment** - OS, Python version, aeromux-db version.
- **Logs** - Relevant log output (use `--verbose` for debug logs).
- **Data source** - Which data source triggered the issue, if applicable.

## Suggesting Features

When suggesting features:

1. **Check existing issues** - See if it has already been suggested.
2. **Describe the use case** - Why is this feature needed? What problem does it solve?
3. **Provide examples** - How would the CLI usage or API look?
4. **Consider alternatives** - Are there other approaches?

Feature ideas that align well with the project (new data sources, schema improvements, data enrichment) are especially welcome.

## License

By contributing to Aeromux Database Builder, you agree that your contributions will be licensed under the [GNU General Public License v3.0 or later](LICENSE.md).

---

Thank you for contributing to Aeromux Database Builder! Your efforts help make this project better for the aviation tracking community.
