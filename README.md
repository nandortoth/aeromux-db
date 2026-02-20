# Aeromux Database Builder

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.md)
[![Python](https://img.shields.io/badge/Python-3.14+-3776ab)](https://www.python.org)

**A database builder for the [Aeromux](https://github.com/nandortoth/aeromux) ADS-B decoder**

Aeromux Database Builder generates a SQLite database from external aircraft data sources. The resulting database is consumed by [Aeromux](https://github.com/nandortoth/aeromux) at runtime to enrich decoded Mode S messages with supplementary aircraft information such as registration numbers, operators, and aircraft types.

## Features

- **Multiple Data Sources** — Aggregates aircraft data from external sources into a single, unified SQLite database. Currently supports the Mictronics aircraft database, with the architecture designed for additional sources.

- **Fast Local Lookups** — Provides Aeromux with aircraft metadata keyed by ICAO 24-bit address for instant enrichment of decoded messages.

- **Download Caching** — Downloaded data sources are cached for 1 hour in the `temp/` directory, so repeated builds during development avoid unnecessary network requests.

- **Reproducible Builds** — Uses `uv` for deterministic dependency resolution with a lockfile, ensuring consistent builds across environments.

- **Normalized Schema** — The database uses separate tables for aircraft, types, and operators, linked by foreign keys, with build metadata for version tracking.

## Quick Start

### Prerequisites

- **Python 3.14 or later** — [Download here](https://www.python.org/downloads/)
- **uv** — Fast Python package manager — [Install here](https://docs.astral.sh/uv/getting-started/installation/)

### Build the Database

```bash
# Clone the repository
git clone https://github.com/nandortoth/aeromux-db.git
cd aeromux-db

# Build the database using the convenience script
./build.sh
```

The build script handles everything: installs dependencies via `uv`, downloads data sources, and produces a fresh SQLite database in the `artifacts/` directory.

Alternatively, run the tool directly:

```bash
# Install dependencies
uv sync

# Run the builder
uv run aeromux-db

# Run with verbose/debug output
uv run aeromux-db --verbose
```

### Output

The generated database is written to:

```
artifacts/aeromux-db_VERSION.sqlite
```

Where `VERSION` is read from `pyproject.toml` (e.g., `aeromux-db_1.0.0.sqlite`).

## Database Schema

The database contains four tables:

| Table | Description |
|---|---|
| `aircraft` | One row per aircraft, keyed by ICAO 24-bit hex address. References `types` via type code. |
| `types` | Aircraft type lookup — type code, description, and ICAO class (e.g., `L2J` for land-based, two-engine jet). |
| `operators` | Operator lookup — ICAO airline designator, name, country, and callsign. |
| `metadata` | Build metadata as key-value pairs. |

### Metadata

| Key | Description |
|---|---|
| `build_timestamp` | ISO 8601 UTC timestamp of when the database was generated. |
| `tool_version` | Version of the builder tool that produced the database. |
| `schema_version` | Database schema version, so Aeromux can verify compatibility. |
| `record_count` | Total number of aircraft records in the database. |

The full SQL schema is defined in [`schema/schema.sql`](schema/schema.sql) and documented in [`schema/schema.md`](schema/schema.md).

## Data Sources

| Source | Description |
|---|---|
| [Mictronics Aircraft Database](https://www.mictronics.de/aircraft-database/) | Aircraft registrations, type designators, and operator information. Distributed as a ZIP archive containing JSON files. |

The tool downloads each data source to `temp/`, extracts and parses the data, and inserts the records into the database. Sources less than 1 hour old are reused from cache.

## Project Structure

```
aeromux-db/
├── build.sh              # Single entry point for building the database
├── pyproject.toml         # Project metadata and dependencies (PEP 621)
├── uv.lock                # Lockfile for reproducible builds
├── src/
│   └── aeromux_db/
│       ├── __init__.py    # Package version
│       ├── __main__.py    # Entry point and pipeline orchestration
│       ├── cli.py         # Command-line argument parsing
│       ├── downloader.py  # File download with caching and ZIP extraction
│       ├── models.py      # Data models (Aircraft, AircraftType, Operator)
│       ├── builder.py     # SQLite database construction
│       └── sources/
│           └── mictronics.py  # Mictronics data source parser
├── schema/
│   ├── schema.sql         # Authoritative SQL schema (single source of truth)
│   └── schema.md          # Human-readable schema documentation
├── artifacts/             # Build output (generated SQLite database)
├── temp/                  # Downloaded and extracted data source files (cached)
└── tests/                 # Test suite
```

## Releases

Each release of this repository represents a new version of the generated database. Releases are published as GitHub Releases with the built SQLite database attached as a release artifact. The generated database is then copied into the Aeromux repository at `artifacts/db/` for runtime use.

## Contributing

Contributions are welcome! Whether it is a bug fix, a new data source, improved documentation, or additional tests, we appreciate your help.

Please read the [Contributing Guide](CONTRIBUTING.md) for development setup, architecture overview, coding standards, and the pull request process. This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## License

Aeromux Database Builder is free software, released under the [GNU General Public License v3.0 or later](LICENSE.md).

## Acknowledgments

This project would not be possible without the following data sources and their maintainers:

- **[Mictronics Aircraft Database](https://www.mictronics.de/aircraft-database/)** — Comprehensive aircraft database providing registration, type, and operator data for hundreds of thousands of aircraft worldwide. Thank you for making this invaluable resource freely available to the aviation community.

## Contact

- **Author:** Nandor Toth
- **Email:** dev@nandortoth.com
- **Issues:** [github.com/nandortoth/aeromux-db/issues](https://github.com/nandortoth/aeromux-db/issues)
