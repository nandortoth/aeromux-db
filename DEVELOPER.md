# Developer Guide

This document is the technical reference for developers working on Aeromux Database Builder. It covers the build pipeline, data source formats, merge logic, and conflict resolution in detail.

For quick start and usage instructions, see [README.md](README.md). For coding standards, testing, and the pull request process, see [CONTRIBUTING.md](CONTRIBUTING.md). For the full database schema reference, see [schema/schema.md](schema/schema.md).

## Pipeline Architecture

The builder follows a sequential pipeline that processes four data sources in a fixed order:

```
Download → Extract → Parse → Merge → Build
```

**Processing order:**

1. **Mictronics** — base aircraft, type, and operator records.
2. **ADS-B Exchange** — extended aircraft details, fill missing registrations.
3. **OpenSky Network** — manufacturer records, operator IATA codes, aircraft enrichment.
4. **Type-longnames** — per-aircraft model descriptions (highest quality).

Each source is downloaded, extracted, and parsed into in-memory data structures, then merged into the database. The order matters — later sources enrich and overwrite data from earlier sources according to the merge rules described below.

## Data Sources

### 1. Mictronics Aircraft Database

- **URL:** `https://www.mictronics.de/aircraft-database/indexedDB.php`
- **Format:** ZIP archive containing four JSON files.

**`aircrafts.json`** — Aircraft records as a JSON object keyed by ICAO 24-bit address.

Each value is an array: `[registration, type_code, (unused), (unused, optional)]`. Only the first two fields are used.

**`types.json`** — Aircraft type lookup as a JSON object keyed by type code.

Each value is an array: `[type_description, type_icao_class, (unused)]`. Only the first two fields are used.

**`operators.json`** — Operator lookup as a JSON object keyed by operator ICAO code.

Each value is an array: `[operator_name, operator_country, operator_callsign]`.

**`dbversion.json`** — Version metadata for this data source (not used by the builder).

**Populates:** `aircrafts`, `types`, `operators`.

### 2. ADS-B Exchange Aircraft Database

- **URL:** `http://downloads.adsbexchange.com/downloads/basic-ac-db.json.gz`
- **Format:** Gzip-compressed file containing one JSON object per line. Updated daily.

**Fields per record:**

| Field | Description |
|---|---|
| `icao` | ICAO 24-bit address (hex string). |
| `reg` | Aircraft registration number. |
| `icaotype` | ICAO type designator (e.g. `B77W`). |
| `year` | Year of manufacture. |
| `manufacturer` | Aircraft manufacturer name. |
| `model` | Full aircraft model name (e.g. `Boeing 777-36N`). |
| `ownop` | Owner or operator name. |
| `faa_pia` | FAA Privacy ICAO Address flag. |
| `faa_ladd` | FAA Limiting Aircraft Data Displayed flag. |
| `short_type` | ICAO aircraft class (e.g. `L2J`). |
| `mil` | Military aircraft flag. |

**Populates:** `aircrafts` (new records), `aircraft_details` (all records from this source), `aircraft_fallbackdata` (manufacturer field).

### 3. OpenSky Network Aircraft Database

- **S3 listing:** `https://s3.opensky-network.org/data-samples?list-type=2&prefix=metadata/`
- **Download:** `https://opensky-network.org/datasets/metadata/{filename}`
- **File:** The latest `aircraftDatabase-complete-YYYY-MM.csv` is selected automatically from the S3 listing.
- **Format:** CSV file (~108 MB) with the following columns:

| Column | Description |
|---|---|
| `icao24` | ICAO 24-bit address (hex string). |
| `timestamp` | Record timestamp. |
| `acars` | ACARS capability flag. |
| `adsb` | ADS-B capability flag. |
| `built` | Date the aircraft was built. |
| `categoryDescription` | Aircraft category description. |
| `country` | Country of registration. |
| `engines` | Engine configuration. |
| `firstFlightDate` | Date of first flight. |
| `firstSeen` | First seen timestamp. |
| `icaoAircraftClass` | ICAO aircraft class. |
| `lineNumber` | Production line number. |
| `manufacturerIcao` | Manufacturer ICAO code. |
| `manufacturerName` | Manufacturer name. |
| `model` | Aircraft model name. |
| `modes` | Mode-S capability flag. |
| `nextReg` | Next registration number. |
| `notes` | Free-text notes. |
| `operator` | Operator name. |
| `operatorCallsign` | Operator callsign. |
| `operatorIata` | Operator IATA code. |
| `operatorIcao` | Operator ICAO code. |
| `owner` | Aircraft owner name. |
| `prevReg` | Previous registration number. |
| `regUntil` | Registration valid until date. |
| `registered` | Registration date. |
| `registration` | Aircraft registration number. |
| `selCal` | SELCAL code. |
| `serialNumber` | Aircraft serial number. |
| `status` | Aircraft status. |
| `typecode` | ICAO type designator. |
| `vdl` | VDL Mode 2 capability flag. |

**Populates:** `manufacturers`, `operators` (IATA codes only), `aircrafts` (enrichment of existing records), `aircraft_details` (model, owner), `aircraft_fallbackdata` (manufacturer, operator names).

### 4. Type-Longnames (wiedehopf/chrisglobe)

- **URL:** `https://github.com/wiedehopf/type-longnames-chrisglobe/archive/refs/heads/master.tar.gz`
- **Format:** Tarball containing CSV files in `individual-types/`, one file per aircraft type code. Each CSV has no header and five columns:

| Column | Description |
|---|---|
| 1 | ICAO 24-bit address (hex string). |
| 2 | Aircraft registration or serial number. |
| 3 | ICAO type designator (matches the filename). |
| 4 | Unused numeric field. |
| 5 | Per-aircraft type description (e.g. `Boeing C-40A Clipper`). |

The type descriptions are unique per aircraft, not per type code — the same type code may have different descriptions for different aircraft variants. This source is treated as the highest quality for model descriptions and overwrites the `model` field from earlier sources.

**Populates:** `aircrafts` (new records and type code fill), `aircraft_details` (model overwrite).

## Data Merge Logic

### Mictronics (source 1 — base records)

All records are inserted as the initial dataset. This populates the `aircrafts`, `types`, and `operators` tables.

### ADS-B Exchange (source 2 — extended details)

The file is processed line by line. For each aircraft record:

- **ICAO address already exists, registration matches:** No action on the `aircrafts` row.
- **ICAO address already exists, no registration in database:** The ADS-B Exchange registration is used.
- **ICAO address already exists, registration differs:** The mismatch is recorded for later conflict resolution.
- **ICAO address does not exist:** A new row is inserted into `aircrafts` (ICAO address, registration, type code).

Regardless of whether the aircraft is new or existing, `aircraft_details` is populated for every aircraft in this source (year, model, owner/operator, FAA flags, military flag), and `aircraft_fallbackdata` receives the `manufacturer` field.

### OpenSky Network (source 3 — enrichment)

The CSV is processed row by row. OpenSky does not insert new aircraft — it only enriches existing records.

**Manufacturers:** For each row where `manufacturerIcao` is not null:

- If the manufacturer ICAO code does not exist in the `manufacturers` table: insert a new row.
- If it already exists: update `manufacturer_name` if the new value is not null and differs.

**Operators:** For each row where both `operatorIcao` and `operatorIata` are not null:

- If the operator already exists: set `operator_iata` if it is currently null.

**Aircrafts:** For each row where the ICAO address exists in the `aircrafts` table:

- Set `aircraft_country` from `country`.
- Set `aircraft_serial_number` from `serialNumber`.
- If `model` is not empty: set `model` in `aircraft_details` if it is currently empty.
- If `operatorIcao` is not null: set `aircraft_operator_icao` as a foreign key reference.
- If `operatorIcao` is null and `operator` is not null: store `operator` in `aircraft_fallbackdata`.
- If `owner` is not null and `owner_operator` in `aircraft_details` is currently null: set `owner_operator`.
- If `registration` is not null and `aircraft_registration` is currently null: set it. If both are non-null and differ: the mismatch is recorded for later conflict resolution.
- If `manufacturerIcao` is not null: set `aircraft_manufacturer_icao` as a foreign key reference.
- If `manufacturerIcao` is null and `manufacturerName` is not null: store `manufacturer` in `aircraft_fallbackdata`.

### Type-longnames (source 4 — model overwrite)

All CSV files are parsed. For each record:

- **ICAO address already exists:**
  - If `type_code` is not null and `aircraft_type_code` is currently null: set it.
  - If `type_description` is not null: **overwrite** `model` in `aircraft_details` (this source is treated as highest quality). If no `aircraft_details` row exists, one is created.
  - If `registration` is not null and `aircraft_registration` is currently null: set it. If both are non-null and differ: the mismatch is recorded for later conflict resolution.
- **ICAO address does not exist:** A new row is inserted into `aircrafts` (ICAO address, registration, type code) and `aircraft_details` (model).

## Registration Conflict Resolution

After all four sources are processed, registration conflicts are resolved. A conflict exists when two or more sources provide different registration values for the same ICAO address.

**Priority rules (applied in order — first match wins):**

1. **Majority agreement** — If two or more sources agree on the registration, that value is used.
2. **US FAA N-number** — If the registration matches the pattern `N` + 1–5 digits + 0–2 letters and only one candidate matches, that value is used.
3. **IATA-style pattern** — If the registration matches `XX-YY` (1–4 alphanumeric characters on each side of a dash) and only one candidate matches, that value is used.
4. **Contains dash** — If only one candidate contains a dash, that value is used.
5. **Source priority** — Type-longnames > OpenSky > ADS-B Exchange > Mictronics. The highest-priority source with a non-null registration wins.

The resolved registration is written back to the `aircrafts` table. All mismatches and their resolutions are written to `artifacts/reg_conflicts_resolutions.csv` with columns: `icao_address`, `mictronics_reg`, `adsbx_reg`, `opensky_reg`, `typelongnames_reg`, `selected_source`, `reason`.

## Database Properties

- **Unencrypted** with no password — the database is an open SQLite file.
- **UTF-8** text encoding.
- **Read-only at runtime** — Aeromux only reads from the database. The builder recreates the entire database from scratch on each run.
- **Default journal mode** — no WAL needed since the database is not modified at runtime.
- Missing or unavailable fields are stored as `NULL`.

## Versioning

The database version follows a calendar-based scheme:

```
YYYY.Q.wWW_rR
```

| Component | Description |
|---|---|
| `YYYY` | Year (e.g. `2026`). |
| `Q` | Quarter (1–4). |
| `WW` | ISO 8601 week number, zero-padded, Monday-start (e.g. `08`). |
| `R` | Release number within that week (default `1`). |

Example: `2026.1.w08_r1` — first release of week 8 in Q1 2026.

The version is computed automatically at build time from the current UTC date. Use `--release N` to specify the release number when building multiple times in the same week.

## Download Caching

Downloaded data sources are cached in the `temp/` directory:

- If a previously downloaded file exists and is **less than 1 hour old**, it is reused.
- Otherwise, the latest version is downloaded, replacing the cached file.
- The `temp/` directory contains a `.gitkeep` so the directory is tracked, but cached files are not committed.

## Error Handling

The builder follows an **abort-on-failure** strategy — partial databases are never produced:

- If a data source download fails (network error, HTTP error), the build aborts.
- If a data source returns data that cannot be parsed, the build aborts with a clear error message identifying the problematic source.
- All errors are logged with sufficient detail (source URL, HTTP status, exception message) to allow diagnosis.
- On any failure, `generate.sh` exits with a non-zero exit code.

## Logging and Progress

- Uses Python's built-in `logging` module. All output goes to stdout/stderr (no log files).
- Log messages include a timestamp, log level, and a descriptive message.
- Key milestones are logged during a normal build: start, each data source download, record counts, database write, and completion.
- **Textual** is used for terminal UI progress bars and status messages during long-running operations.
- Verbose/debug output can be enabled with `--verbose`.

## Further Reading

- [README.md](README.md) — Quick start and usage instructions.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Development setup, coding standards, and pull request process.
- [schema/schema.md](schema/schema.md) — Full database schema reference (tables, columns, views, relationships).
- [schema/schema.sql](schema/schema.sql) — Authoritative SQL schema (single source of truth).
