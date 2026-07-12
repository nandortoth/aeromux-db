# Developer Guide

This document is the technical reference for developers working on Aeromux Database Builder. It covers the build pipeline, data source formats, merge logic, and conflict resolution in detail.

For quick start and usage instructions, see [README.md](README.md). For coding standards, testing, and the pull request process, see [CONTRIBUTING.md](CONTRIBUTING.md). For the full database schema reference, see [schema/schema.md](schema/schema.md).

## Pipeline Architecture

The builder follows a sequential pipeline that processes six data sources in a fixed order:

```
Download → Extract → Parse → Merge → Build
```

**Processing order:**

1. **Mictronics** — base aircraft, type, and operator records.
2. **ADS-B Exchange** — extended aircraft details, fill missing registrations.
3. **OpenSky Network** — manufacturer records, operator IATA codes, aircraft enrichment.
4. **Plane Alert DB** — operator/model overwrite, military flag, new aircraft.
5. **Type-longnames** — per-aircraft model descriptions (highest quality).
6. **tar1090-db** — per-type WTC enrichment.

Each source is downloaded, extracted, and parsed into in-memory data structures, then merged into the database. The order matters — later sources enrich and overwrite data from earlier sources according to the merge rules described below.

The technical constraint on tar1090-db is only that it run **after Mictronics (source 1)** — the enrichment merges into the Mictronics-derived `types` list. Sources 2–5 all operate on `aircrafts` / `aircraft_details` / `aircraft_fallbackdata`, not `types`, so they neither depend on nor block the WTC enrichment. Slot 6 (appended at the end) is a presentation choice, not a constraint — it keeps the existing aircrafts-table enrichment chain (sources 1–5) visually contiguous, with the types-table enrichment as a clean tail step.

## Data Sources

### 1. Mictronics Aircraft Database

- **URL:** `https://raw.githubusercontent.com/Mictronics/aircraft-database/main/indexedDB.zip`
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

**Populates:** `manufacturers` (deduplicated, normalized names), `operators` (IATA codes only), `aircrafts` (enrichment of existing records), `aircraft_details` (model, owner), `aircraft_fallbackdata` (manufacturer, operator names).

### 4. Plane Alert DB

- **URL:** `https://raw.githubusercontent.com/sdr-enthusiasts/plane-alert-db/main/plane-alert-db.csv`
- **Format:** CSV file downloaded directly (no archive). Updated frequently.

**Columns used:**

| Column | Description |
|---|---|
| `$ICAO` | ICAO 24-bit address (hex string). |
| `$Registration` | Aircraft registration number. |
| `$Operator` | Operator name. |
| `$Type` | Aircraft model description. |
| `$ICAO Type` | ICAO type designator (e.g. `B77W`). |
| `#CMPG` | Category — when `Mil`, the aircraft is flagged as military. |

**Populates:** `aircrafts` (new records and type code fill), `aircraft_details` (model overwrite, military flag), `aircraft_fallbackdata` (operator overwrite).

### 5. Type-Longnames (wiedehopf/chrisglobe)

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

### 6. tar1090-db (wiedehopf)

- **URL:** `https://github.com/wiedehopf/tar1090-db/archive/refs/heads/master.tar.gz`
- **Format:** Tarball containing a single `icao_aircraft_types.json` file at the repo root. JSON shape is a flat object keyed by ICAO type designator:

  ```json
  {"A388": {"desc": "L4J", "wtc": "J"}, ...}
  ```

  Only the `wtc` field is consumed. The `desc` field overlaps semantically with Mictronics's `type_icao_class` and is intentionally ignored so Mictronics remains the single authority for that column.

**Populates:** `types` (`type_wtc` column only).

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

**Manufacturers:** `manufacturerIcao` keys are case-folded to uppercase so case-variant duplicates (e.g. `BOEING` and `Boeing`) collapse into a single record. For each distinct key, the display `manufacturer_name` is chosen deterministically as the most frequent non-empty `manufacturerName` across all rows (ties broken by longest, then lexicographic), rather than last-write-wins. Note that values which are wrong at the source-majority level (e.g. OpenSky labelling `LISUNOV` as `Douglas`) are not corrected by this rule.

**Operators:** For each row where both `operatorIcao` and `operatorIata` are not null:

- If the operator already exists: set `operator_iata` if it is currently null.

**Aircrafts:** For each row where the ICAO address exists in the `aircrafts` table:

- Set `aircraft_country` from `country`.
- Set `aircraft_serial_number` from `serialNumber`.
- If `model` or `owner` is present, the `aircraft_details` row is created first (`INSERT OR IGNORE`) so the enrichment is not lost for aircraft without an ADS-B Exchange details row.
- If `model` is not empty: set `model` in `aircraft_details` if it is currently empty.
- If `operatorIcao` is not null **and exists in the `operators` table**: set `aircraft_operator_icao` as a foreign key reference. Otherwise, if `operator` is not null, store the plain-text `operator` in `aircraft_fallbackdata`. (An `operatorIcao` absent from `operators` would be a dangling reference that suppresses the fallback name in `aircraft_view`, so it is never written.)
- If `owner` is not null and `owner_operator` in `aircraft_details` is currently null: set `owner_operator`.
- If `registration` is not null and `aircraft_registration` is currently null: set it. If both are non-null and differ: the mismatch is recorded for later conflict resolution.
- If `manufacturerIcao` is not null: set `aircraft_manufacturer_icao` (case-folded to uppercase to match the `manufacturers` table key) as a foreign key reference.
- If `manufacturerIcao` is null and `manufacturerName` is not null: store `manufacturer` in `aircraft_fallbackdata`.

The per-aircraft manufacturer set here is provisional: it is later overridden where the aircraft's type code names a known manufacturer (see [Manufacturer Derivation](#manufacturer-derivation)).

### Plane Alert DB (source 4 — operator/model overwrite)

The CSV is processed row by row. Duplicate ICAO addresses are deduplicated during parsing (last occurrence wins).

**Existing aircraft:** For each row where the ICAO address exists in the `aircrafts` table:

- If `ICAO Type` is not empty: set `aircraft_type_code` if it is currently null.
- If `Type` is not empty: **overwrite** `model` in `aircraft_details` (creates the row if it does not exist).
- If `Operator` is not empty: **overwrite** `operator` in `aircraft_fallbackdata` (creates the row if it does not exist).
- If `CMPG` is `Mil`: set `military = 1` in `aircraft_details` (never unsets; creates the row if it does not exist).
- If `Registration` is not null and `aircraft_registration` is currently null: set it. If both are non-null and differ: the mismatch is recorded for later conflict resolution.

**New aircraft:** If the ICAO address does not exist, a new row is inserted into `aircrafts` (ICAO address, registration, type code). If the record has a model or military flag, `aircraft_details` is created. If the record has an operator, `aircraft_fallbackdata` is created.

### Type-longnames (source 5 — model overwrite)

All CSV files are parsed. For each record:

- **ICAO address already exists:**
  - If `type_code` is not null and `aircraft_type_code` is currently null: set it.
  - If `type_description` is not null: **overwrite** `model` in `aircraft_details` (this source is treated as highest quality). If no `aircraft_details` row exists, one is created.
  - If `registration` is not null and `aircraft_registration` is currently null: set it. If both are non-null and differ: the mismatch is recorded for later conflict resolution.
- **ICAO address does not exist:** A new row is inserted into `aircrafts` (ICAO address, registration, type code) and `aircraft_details` (model).

### tar1090-db (source 6 — type WTC enrichment)

The parsed dict (type code → WTC letter) is merged into the in-memory `types` list before the SQL insert:

```python
for t in types:
    t.type_wtc = wtc_map.get(t.type_code)
```

Mictronics-only type codes (no tar1090-db match) end up with `type_wtc = NULL` — no hard failure, just a coverage gap. tar1090-db-only type codes (no Mictronics row) are ignored — we do not invent a half-populated `types` row from the WTC source alone. Malformed WTC values (anything not in `{L, M, H, J}`) are dropped at parse time; the type row itself is preserved from Mictronics with `type_wtc = NULL`.

**Affects:** `types` (sets `type_wtc`).

## Registration Conflict Resolution

After all sources are processed, registration conflicts are resolved. A conflict exists when two or more sources provide different registration values for the same ICAO address.

**Priority rules (applied in order — first match wins):**

1. **Majority agreement** — If two or more sources agree on the registration, that value is used. When multiple values each have 2+ agreeing sources (a tie), the group backed by the highest-priority source wins.
2. **US FAA N-number** — If the registration matches the pattern `N` + 1–5 digits + 0–2 letters and only one candidate matches, that value is used.
3. **IATA-style pattern** — If the registration matches `XX-YY` (1–4 alphanumeric characters on each side of a dash) and only one candidate matches, that value is used.
4. **Contains dash** — If only one candidate contains a dash, that value is used.
5. **Source priority** — Type-longnames > Plane Alert DB > OpenSky > ADS-B Exchange > Mictronics. The highest-priority source with a non-null registration wins.

The resolved registration is written back to the `aircrafts` table. All mismatches and their resolutions are written to `artifacts/reg_conflicts_resolutions.csv` with columns: `icao_address`, `mictronics_reg`, `adsbx_reg`, `opensky_reg`, `planealertdb_reg`, `typelongnames_reg`, `selected_source`, `reason`.

## Manufacturer Derivation

The per-aircraft manufacturer is unreliable on its own. An ICAO 24-bit hex address can be reassigned to a different physical aircraft over time, and OpenSky's per-aircraft record can lag that change — for example, hex `4D2145` is currently an Airbus A321 (`9H-WZC`, Wizz Air Malta), but OpenSky still reports its manufacturer as `DASSAULT` from the previous aircraft on that hex. The aircraft **type code**, by contrast, comes from Mictronics and is the authoritative identity of what the aircraft *is*.

Because the Mictronics type description names the manufacturer as its leading token (`AIRBUS A-321`, `DASSAULT Falcon 50`, `BOEING C-17 Globemaster 3`), the manufacturer is derived from the type rather than trusted from the per-aircraft source. After all sources are merged:

1. A `type_code → manufacturer_icao` map is built by matching each type description against the keys of the `manufacturers` table. The **longest** manufacturer key that is a whole-word prefix of the description wins, so `AIRBUS HELICOPTERS` beats `AIRBUS`.
2. For every aircraft whose type code is in that map, `aircraft_manufacturer_icao` is set to the derived manufacturer, overriding whatever a per-aircraft source provided.

This keeps the manufacturer consistent with the type by construction (an A321 is always Airbus) and corrects stale manufacturers on reassigned hexes. Type codes whose description matches no known manufacturer (≈ one third — long-tail makers OpenSky does not list, e.g. `AGUSTA`, `FAIRCHILD`) are left untouched, keeping whatever the per-aircraft sources provided.

> **Note — type/registration on reassigned hexes.** The type code itself is *not* cross-resolved; Mictronics wins via fill-if-null, which (per the example above) is the correct current aircraft. Registration *is* cross-resolved by majority (see [Registration Conflict Resolution](#registration-conflict-resolution)), which for some reassigned hexes can still pick a stale value when two lagging sources agree. Hardening identity resolution against hex reassignment is a known open area.

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
- In-place progress indicators are written to stderr for long-running operations (e.g. large file downloads).
- Verbose/debug output can be enabled with `--verbose`.

## Build & Release

The weekly database build and release runs on a **self-hosted `systemd` timer** (a
home Debian VM), not GitHub Actions. Scheduled builds on GitHub-hosted runners
intermittently failed while downloading source data — outbound connections from the
runner IP ranges timed out for some sources — which a self-hosted host with an ordinary
egress IP avoids. Full install/operate docs live in [`scripts/README.md`](scripts/README.md).

**Schedule:** Monday 03:00 UTC (`Persistent=true`, so a missed run fires on next boot).
A run can also be triggered manually on the host, as root, with
`systemctl start aeromux-db.service`.

**Pipeline** (`scripts/build-and-release.sh`):

1. Updates the checkout to `origin/main`.
2. Resolves the target `db_version` via `uv run aeromux-db --print-version`.
3. Skips if a GitHub Release with that version tag already exists.
4. Runs `uv run aeromux-db` and captures the KEY=VALUE summary output.
5. Creates a GitHub Release (via `gh`) with the `.sqlite` file attached.
6. Deletes old releases, keeping only the 10 most recent.

The KEY=VALUE output from `__main__.py` (written to stdout) is parsed to extract the
database version, output file path, and record counts for the release. The only
credential is a fine-grained GitHub token supplied via a `systemd` `EnvironmentFile`;
all six data sources are public.

## Further Reading

- [README.md](README.md) — Quick start and usage instructions.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Development setup, coding standards, and pull request process.
- [schema/schema.md](schema/schema.md) — Full database schema reference (tables, columns, views, relationships).
- [schema/schema.sql](schema/schema.sql) — Authoritative SQL schema (single source of truth).
