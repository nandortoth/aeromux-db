# CLAUDE.md

Guidance for AI agents working in this repository. Keep this file short — it is a
**map plus the things that aren't written down elsewhere**, not a re-explanation of
the existing docs.

## What this repo is

A build tool that downloads six external aircraft data sources, merges them, and
emits a single SQLite database (`artifacts/aeromux-db_<version>.sqlite`). The
database is consumed at runtime by [Aeromux](https://github.com/aeromux/aeromux) to
enrich decoded Mode S messages.

**Golden rule:** the database is *generated*. When a field looks wrong, the cause is
almost always a quirk in the upstream source data, not a code bug — so confirm
against the raw source before theorizing (see *Debugging norm* below).

## Commands

```bash
uv sync                          # install deps (runtime: httpx; dev: pytest)
uv run pytest                    # run the test suite
uv run aeromux-db                # full build -> artifacts/*.sqlite
uv run aeromux-db --verbose      # debug logging
uv run aeromux-db --print-version  # print resolved db_version, no build
uv run aeromux-db --release N    # release number within the ISO week
./generate.sh                    # convenience wrapper (clean venv, build, summary)
uv run ruff format               # format   (ruff check --fix to autofix lint)
```

A full build downloads ~120 MB and takes ~70 s. `--print-version` is the cheap way
to exercise the CLI without a build.

## Where things live

| Topic | Source of truth |
|---|---|
| Pipeline, per-source merge logic, registration conflict resolution, manufacturer derivation | [DEVELOPER.md](DEVELOPER.md) |
| Schema, tables, `aircraft_view` | [schema/schema.sql](schema/schema.sql) (authoritative) + [schema/schema.md](schema/schema.md) |
| Dev setup, ruff style, testing, PR process | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Build orchestration (the 16 steps) | `src/aeromux_db/__main__.py` |
| Merge, registration resolution, manufacturer derivation (`build_database`, `_resolve_registration`, `_build_type_manufacturer_map`) | `src/aeromux_db/builder.py` |
| Per-source download/parse | `src/aeromux_db/sources/` |

## Conventions that bite

- **License header:** every source file starts with the GPLv3 header block. Copy it
  into any new file.
- **Tests must never write to `artifacts/`.** `tests/conftest.py` redirects
  `builder.ARTIFACTS_DIR` to a temp dir; rely on it. Use throwaway db_versions like
  `2099.4.w52_rN` so build output never collides with real artifacts.
- **Version:** `pyproject.toml` `version` is the single source of truth for
  `__version__` (read via `importlib.metadata`). Keep it in sync with the top entry
  of [CHANGELOG.md](CHANGELOG.md) — it has drifted before.
- **Never commit or push — ever.** Committing is done exclusively by the maintainer.
  Agents must not run `git commit`/`git push` (or stage with the intent to commit),
  even if it seems implied. Prepare the working-tree changes and, when asked, propose
  a commit message; leave the actual commit to the maintainer.
- **Commit messages:** match the existing history — a single capitalized, imperative
  subject line, no body, combining multiple changes as comma-separated clauses. E.g.
  `Add Plane Alert DB as data source, fix registration conflict resolution and placeholder filtering`.
  The history does not use trailers (no `Co-Authored-By`).
- `artifacts/*.sqlite` and `artifacts/*.csv` are gitignored build output; only
  `artifacts/.gitkeep` is tracked.

## Debugging norm: prove, don't assume

Trace a suspect field back to the raw upstream record before proposing a fix. Each
source is a plain download — fetch the rows for an ICAO hex directly:

```bash
# Mictronics (uppercase hex keys)
curl -sL https://raw.githubusercontent.com/Mictronics/aircraft-database/main/indexedDB.zip -o mic.zip && unzip -p mic.zip aircrafts.json | grep -oiE '"4D2145":\[[^]]*\]'
# ADS-B Exchange (lowercase icao, JSON lines)
curl -sL http://downloads.adsbexchange.com/downloads/basic-ac-db.json.gz | zcat | grep -i '"icao":"4d2145"'
# OpenSky monthly CSV (302 -> S3; quotechar is a single quote)
curl -sL "https://opensky-network.org/datasets/metadata/aircraft-database-complete-YYYY-MM.csv" | awk 'NR==1 || tolower($0) ~ /4d2145/'
# Plane Alert DB
curl -sL https://raw.githubusercontent.com/sdr-enthusiasts/plane-alert-db/main/plane-alert-db.csv | grep -i 4d2145
```

Known data-quality classes (all documented in DEVELOPER.md):

- **Hex reassignment → "Frankenstein" rows.** A hex can move to a new aircraft over
  time; sources disagree. Mictronics tends to hold the *current* aircraft while
  ADS-B/OpenSky can lag. Type stays Mictronics-authoritative (fill-if-null) and the
  manufacturer is derived from it (`_build_type_manufacturer_map`). Registration is
  still majority-resolved (`_resolve_registration`), which can pick a stale value
  when two lagging sources agree — a known open area, so validate reg against ground
  truth (e.g. a flight tracker) before trusting it.
- **OpenSky source-majority errors.** Some OpenSky labels are wrong at the majority
  level (e.g. Lisunov tagged "Douglas"); the deterministic mode-name rule cannot fix
  those — they are upstream, not ours.
- **Dangling references.** Only write `aircraft_operator_icao` when the code exists
  in `operators`; otherwise route the name to `aircraft_fallbackdata`. `aircraft_view`
  falls through join misses rather than keying on the FK being non-null.

When validating a build, spot-check known hexes in `aircraft_view` against an
external flight tracker (ground truth) and confirm `reg_conflicts_resolutions.csv`
looks sane.
