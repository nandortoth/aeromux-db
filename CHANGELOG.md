# Changelog

All notable changes to Aeromux Database Builder are documented in this file.

This changelog covers the **builder tool** itself, not the generated database. Each weekly database release has its own record counts and details on the [Releases](https://github.com/aeromux/aeromux-db/releases) page.

## [1.4.1] — 2026-07-07

### Fixed

- Mictronics database download now points at the source's new GitHub location (`raw.githubusercontent.com/Mictronics/aircraft-database/main/indexedDB.zip`). The former `mictronics.de/aircraft-database/indexedDB.php` endpoint was removed and returned `404`, failing every build at step 1. The archive contents are unchanged, so no parsing changes were needed.

## [1.4.0] — 2026-06-27

### Changed

- The aircraft manufacturer is now derived from the (authoritative) aircraft type code instead of being taken from a per-aircraft source. The Mictronics type description names the manufacturer (`AIRBUS A-321`, `BOEING C-17 Globemaster 3`), so `aircraft_manufacturer_icao` is set from the type via a longest-prefix match against the `manufacturers` table. This keeps the manufacturer consistent with the type by construction (an A321 is always Airbus) and corrects stale manufacturers on reassigned ICAO hex addresses — e.g. hex `4D2145` (a Wizz Air A321) previously showed `Dassault` from OpenSky's record for the prior aircraft on that hex, and now shows `Airbus`. Types whose maker is not in the `manufacturers` table keep the per-aircraft value.

### Fixed

- Operator references pointing at an ICAO designator absent from the `operators` table (OpenSky-supplied) are no longer written to `aircrafts.aircraft_operator_icao`; the operator name is routed to `aircraft_fallbackdata.operator` instead. Previously these dangling references forced `aircraft_view.operator_name` to `NULL` and suppressed the available fallback name.
- `aircraft_view.operator_name` now falls through to the fallback/owner tiers when the `operators` join misses, instead of keying off `aircraft_operator_icao IS NOT NULL`.
- Registration conflict resolution: the majority-tiebreak priority map now ranks OpenSky above ADS-B Exchange, matching the documented default priority (`typelongnames > planealertdb > opensky > adsbx > mictronics`). Previously the two rule maps disagreed.
- OpenSky `model` and `owner` enrichment now creates the `aircraft_details` row when absent (via `INSERT OR IGNORE`), matching Plane Alert DB and type-longnames; previously these updates were silently dropped for aircraft without an ADS-B Exchange details row.
- OpenSky manufacturer names are now resolved deterministically (most frequent name per manufacturer key) instead of last-write-wins, and `manufacturer_icao` keys are case-folded to remove duplicate entries (e.g. `BOEING`/`Boeing`). Fixes arbitrary names such as `MCDONNELL DOUGLAS` → `Douglas` (now `Mcdonnell Douglas`). Manufacturer values that are wrong at the OpenSky source-majority level (e.g. Lisunov labelled `Douglas`) are unchanged.

## [1.3.0] — 2026-05-17

### Added

- New data source: [tar1090-db (wiedehopf)](https://github.com/wiedehopf/tar1090-db) — per-type ICAO Wake Turbulence Category (WTC) values derived from DOC 8643.
- New `type_wtc` column on the `types` table: `L` (Light), `M` (Medium), `H` (Heavy), `J` (Super), or `NULL` when unknown. Also surfaced in `aircraft_view`.
- New `TYPES_WTC_COUNT` field in the build summary, showing how many of the imported types received a WTC value.

## [1.2.0] — 2026-04-26

### Added

- `aeromux-db --print-version` flag prints the resolved calendar-based `db_version` to stdout and exits without performing a build.

### Changed

- Scheduled CI build now runs on both Saturday and Sunday at 03:15 UTC. Both runs of a weekend share the same ISO-week-based version; the second run resolves the target version up front and skips the ~15-minute download/build cycle if a release for that version already exists. This mitigates intermittent outbound TCP failures on GitHub-hosted runners ([`actions/runner-images#4700`](https://github.com/actions/runner-images/issues/4700)) by giving each weekend two independent runner draws.

## [1.1.0] — 2026-03-10

### Added

- New data source: [Plane Alert DB](https://github.com/sdr-enthusiasts/plane-alert-db) — community-maintained database of notable aircraft (military, government, VIP). Provides operator names, model descriptions, and military flags.
- Pipeline expanded from 11 to 13 steps to accommodate the new source.
- Registration conflict resolution now covers five sources with updated priority rules.

### Changed

- `operator_name` in `aircraft_view` now resolves through three fallback tiers: `operators` table, `aircraft_fallbackdata`, then `owner_operator` from `aircraft_details`. The `owner_operator` column is no longer exposed as a separate view column.

### Fixed

- Filter out placeholder registrations containing only `?` characters across all five data source parsers.
- Fix majority rule tie-breaking in registration conflict resolution — when multiple values each have 2+ agreeing sources, the group backed by the highest-priority source now wins.

## [1.0.1] — 2026-03-08

### Added

- Retry logic for HTTP downloads with exponential backoff (5 attempts, 1m/2m/4m/8m/16m) and 10s connect timeout to handle transient network failures in CI.
- Unit tests for the download retry mechanism.
- `pytest` as a dev dependency so `uv run pytest` works out of the box.

### Changed

- Scheduled CI build moved from Sunday 06:00 UTC to Sunday 03:15 UTC to reduce network timeout risk during off-peak hours.

## [1.0.0] — 2026-02-22

Initial release of the Aeromux Database Builder.

### Added

- Build a unified SQLite database from four aircraft data sources: Mictronics, ADS-B Exchange, OpenSky Network, and type-longnames.
- Intelligent registration conflict resolution across sources using majority vote, FAA N-number detection, IATA pattern matching, and source priority rules.
- Calendar-based database versioning (`YYYY.Q.wWW_rR`) computed automatically at build time.
- Automated weekly builds via GitHub Actions with database published as a GitHub Release.
- Programmatic access to the latest database version via the GitHub Releases API.

---

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).
