# Aeromux Database Builder

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.md)
[![Python](https://img.shields.io/badge/Python-3.14+-3776ab)](https://www.python.org)

**A database builder for the [Aeromux](https://github.com/nandortoth/aeromux) ADS-B decoder**

Aeromux Database Builder generates a SQLite database from external aircraft data sources. The resulting database is consumed by [Aeromux](https://github.com/nandortoth/aeromux) at runtime to enrich decoded Mode S messages with supplementary aircraft information such as registration numbers, operators, and aircraft types.

## Features

- **Multiple Data Sources** — Aggregates aircraft data from four external sources (Mictronics, ADS-B Exchange, OpenSky Network, type-longnames) into a single, unified SQLite database.

- **Fast Local Lookups** — Provides Aeromux with aircraft metadata keyed by ICAO 24-bit address for instant enrichment of decoded messages.

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
./generate.sh
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

# Specify release number (for multiple builds in the same week)
uv run aeromux-db --release 2
```

### Output

The generated database is written to:

```
artifacts/aeromux-db_YYYY.Q.wWW_rR.sqlite
```

Where `YYYY` is the year, `Q` is the quarter (1–4), `WW` is the ISO 8601 week number (zero-padded), and `R` is the release number within that week (e.g., `aeromux-db_2026.1.w08_r1.sqlite`). The version is computed automatically at build time.

## Database Schema

The database contains the following tables:

| Table | Description |
|---|---|
| `aircrafts` | One row per aircraft, keyed by ICAO 24-bit hex address. References `types` via type code. |
| `types` | Aircraft type lookup — type code, description, and ICAO class (e.g., `L2J` for land-based, two-engine jet). |
| `operators` | Operator lookup — ICAO airline designator, name, country, and callsign. |
| `aircraft_details` | Extended aircraft information — year, manufacturer, model, owner/operator, FAA flags, and military flag. References `aircrafts` via ICAO address. |
| `aircraft_fallbackdata` | Fallback plain-text manufacturer and operator names for aircraft without normalized references. |
| `manufacturers` | Manufacturer lookup — ICAO code and name. |
| `metadata` | Build metadata as key-value pairs. |

### Metadata

| Key | Description |
|---|---|
| `build_timestamp` | ISO 8601 UTC timestamp of when the database was generated. |
| `db_version` | Calendar-based database version (e.g. `2026.1.w08_r1`). |
| `tool_version` | Version of the builder tool that produced the database (from `pyproject.toml`). |
| `schema_version` | Database schema version, so Aeromux can verify compatibility. |
| `record_count` | Total number of aircraft records in the database. |

The full SQL schema is defined in [`schema/schema.sql`](schema/schema.sql) and documented in [`schema/schema.md`](schema/schema.md). For detailed data source formats, merge logic, and conflict resolution rules, see the [Developer Guide](DEVELOPER.md).

## Data Sources

| Source | Description |
|---|---|
| [Mictronics Aircraft Database](https://www.mictronics.de/aircraft-database/) | Aircraft registrations, type designators, and operator information. Distributed as a ZIP archive containing JSON files. |
| [ADS-B Exchange Aircraft Database](https://www.adsbexchange.com/products/historical-data/) | Aircraft registrations with extended details (year, manufacturer, model, owner/operator, FAA flags, military flag). Distributed as a gzip-compressed JSON file, updated daily. |
| [OpenSky Network Aircraft Database](https://opensky-network.org/datasets/metadata/) | Manufacturer records, operator IATA codes, and aircraft enrichment data (country, serial number, owner). Distributed as a monthly CSV file. |
| [Type-Longnames (wiedehopf/chrisglobe)](https://github.com/wiedehopf/type-longnames-chrisglobe) | Per-aircraft type descriptions (e.g. `Boeing C-40A Clipper`). Distributed as a tarball of CSV files, one per type code. |

The tool downloads each data source to `temp/`, extracts and parses the data, and inserts the records into the database.

## Project Structure

```
aeromux-db/
├── generate.sh            # Single entry point for building the database
├── pyproject.toml         # Project metadata and dependencies (PEP 621)
├── uv.lock                # Lockfile for reproducible builds
├── DEVELOPER.md           # Technical reference for developers
├── src/
│   └── aeromux_db/
│       ├── __init__.py    # Package version
│       ├── __main__.py    # Entry point and pipeline orchestration
│       ├── cli.py         # Command-line argument parsing
│       ├── downloader.py  # File download and archive extraction
│       ├── models.py      # Data models (Aircraft, AircraftType, Operator)
│       ├── version.py     # Calendar-based database version computation
│       ├── builder.py     # SQLite database construction
│       └── sources/
│           ├── mictronics.py      # Mictronics data source parser
│           ├── adsbexchange.py    # ADS-B Exchange data source parser
│           ├── opensky.py         # OpenSky Network data source parser
│           └── typelongnames.py   # Type-longnames data source parser
├── schema/
│   ├── schema.sql         # Authoritative SQL schema (single source of truth)
│   └── schema.md          # Human-readable schema documentation
├── artifacts/             # Build output (generated SQLite database)
├── temp/                  # Downloaded and extracted data source files
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
- **[ADS-B Exchange](https://www.adsbexchange.com/)** — Unfiltered flight tracking data and aircraft database, updated daily from government and various sources. Thank you for providing open access to aircraft data.
- **[OpenSky Network](https://opensky-network.org/)** — Community-driven aircraft metadata including manufacturer records, operator IATA codes, and enrichment data. Thank you for maintaining this open dataset.
- **[Type-Longnames (wiedehopf/chrisglobe)](https://github.com/wiedehopf/type-longnames-chrisglobe)** — Per-aircraft type descriptions that provide specific model variants beyond generic type codes. Thank you for curating this detailed dataset.

## Contact

- **Author:** Nandor Toth
- **Email:** dev@nandortoth.com
- **Issues:** [github.com/nandortoth/aeromux-db/issues](https://github.com/nandortoth/aeromux-db/issues)
