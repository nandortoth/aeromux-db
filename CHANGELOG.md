# Changelog

All notable changes to Aeromux Database Builder are documented in this file.

This changelog covers the **builder tool** itself, not the generated database. Each weekly database release has its own record counts and details on the [Releases](https://github.com/nandortoth/aeromux-db/releases) page.

## [1.0.1] — 2026-03-08

### Added

- Retry logic for HTTP downloads with exponential backoff (5 attempts, 5s/10s/20s/40s) to handle transient network failures in CI.
- Unit tests for the download retry mechanism.
- `pytest` as a dev dependency so `uv run pytest` works out of the box.

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
