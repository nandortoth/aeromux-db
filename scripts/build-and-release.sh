#!/usr/bin/env bash

# Aeromux Database Builder — Build & Release Script
#
# Builds the SQLite database and publishes it as a GitHub Release. Runs unattended
# on a self-hosted server (see scripts/README.md), replacing the former GitHub
# Actions workflow. All six data sources are public; the only credential is a
# GitHub token (GH_TOKEN) with contents:write on this repository, supplied via the
# environment — never committed.
#
# Copyright (C) 2025-2026 Nandor Toth <dev@nandortoth.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

set -euo pipefail

# --- Configuration (env-overridable; CLI flags win) -------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEEP="${KEEP:-10}"          # releases to retain
RELEASE="${RELEASE:-}"      # release number within the ISO week (optional)
PULL=true                   # --no-pull disables the self-update
LOG_FILE="$(mktemp -t aeromux-db-run.XXXXXX.log)"
SUMMARY_FILE=""

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# --- healthchecks.io (optional dead-man's switch) ---------------------------
# HEALTHCHECKS_URL unset -> pings are silent no-ops. On failure, the tail of the
# run log is posted as the ping body. The log must never contain the token, so this
# script never runs `set -x` while GH_TOKEN is exported and never echoes it.
hc_ping() {
    local suffix="${1:-}"
    [ -n "${HEALTHCHECKS_URL:-}" ] || return 0
    local url="${HEALTHCHECKS_URL%/}${suffix}"
    if [ "$suffix" = "/fail" ] && [ -s "$LOG_FILE" ]; then
        tail -c 100000 "$LOG_FILE" \
            | curl -fsS -m 10 --retry 3 --data-binary @- "$url" >/dev/null 2>&1 || true
    else
        curl -fsS -m 10 --retry 3 "$url" >/dev/null 2>&1 || true
    fi
}

# --- Argument parsing -------------------------------------------------------
usage() {
    printf '%s\n' \
        'Usage: build-and-release.sh [--release N] [--keep N] [--no-pull]' \
        '' \
        'Builds the aeromux-db database and publishes it as a GitHub Release.' \
        '' \
        '  --release N   Release number within the current ISO week (default: 1)' \
        '  --keep N      Releases to retain when pruning (default: 10)' \
        '  --no-pull     Skip updating the checkout to origin/main (local testing)' \
        '' \
        'Environment: GH_TOKEN (required), HEALTHCHECKS_URL, KEEP, RELEASE, GH_REPO.'
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --release) RELEASE="$2"; shift 2 ;;
            --keep) KEEP="$2"; shift 2 ;;
            --no-pull) PULL=false; shift ;;
            -h | --help) usage; exit 0 ;;
            *) die "Unknown option: $1 (try --help)" ;;
        esac
    done
}

# --- Helpers ----------------------------------------------------------------
# Emit the --release argument pair (or nothing) as newline-separated tokens.
release_args() { [ -n "$RELEASE" ] && printf -- '--release\n%s\n' "$RELEASE"; }

uvrun() {
    local _r=()
    mapfile -t _r < <(release_args)
    uv run --directory "$PROJECT_ROOT" aeromux-db "$@" "${_r[@]}"
}

summary() { grep "^$1=" "$SUMMARY_FILE" | cut -d= -f2-; }

# --- Pipeline steps ---------------------------------------------------------
update_repo() {
    if [ "$PULL" = true ]; then
        log "Updating checkout to origin/main..."
        git -C "$PROJECT_ROOT" fetch --depth=1 origin main
        git -C "$PROJECT_ROOT" reset --hard origin/main
    else
        log "Skipping repo update (--no-pull)"
    fi
}

resolve_version() { uvrun --print-version; }

create_release() {
    local version="$1" repo output_file filename fsize notes dl api
    repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
    output_file="$(summary OUTPUT_FILE)"          # relative to PROJECT_ROOT
    filename="$(basename "$output_file")"
    fsize="$(summary FILE_SIZE)"
    notes="$(mktemp -t aeromux-db-notes.XXXXXX.md)"
    dl="https://github.com/${repo}/releases/download/${version}/${filename}"
    api="https://api.github.com/repos/${repo}/releases/latest"

    printf '%s\n' \
        '## Download' \
        '' \
        "[\`${filename}\`](${dl}) (${fsize})" \
        '' \
        '## Database Records' \
        '' \
        '| Category | Count |' \
        '|----------|------:|' \
        "| Aircraft | $(summary AIRCRAFT_COUNT) |" \
        "| Types | $(summary TYPES_COUNT) |" \
        "| Operators | $(summary OPERATORS_COUNT) |" \
        "| Manufacturers | $(summary OPENSKY_MANUFACTURERS_COUNT) |" \
        "| Aircraft details | $(summary ADSBX_DETAILS_COUNT) |" \
        "| Aircraft fallback | $(summary ADSBX_FALLBACK_COUNT) |" \
        "| OpenSky enriched | $(summary OPENSKY_ENRICHMENT_COUNT) |" \
        "| Plane Alert DB | $(summary PLANEALERTDB_AIRCRAFT_COUNT) |" \
        "| Type-longnames | $(summary TYPELONGNAMES_AIRCRAFT_COUNT) |" \
        '' \
        '## Programmatic Access' \
        '' \
        '```bash' \
        "curl -s ${api} | jq -r '.tag_name'" \
        "curl -sL ${api} \\" \
        "  | jq -r '.assets[0].browser_download_url' | xargs curl -sLO" \
        '```' \
        > "$notes"

    log "Creating release ${version}..."
    gh release create "$version" "${PROJECT_ROOT}/${output_file}" \
        --title "aeromux-db ${version}" --notes-file "$notes"
    rm -f "$notes"
}

prune_releases() {
    log "Pruning releases (keeping ${KEEP})..."
    gh release list --limit 100 --json tagName -q '.[].tagName' \
        | tail -n "+$((KEEP + 1))" \
        | while read -r tag; do
            log "Deleting old release: $tag"
            gh release delete "$tag" --yes --cleanup-tag
        done
}

# The pipeline. Its combined output is tee'd to $LOG_FILE by main().
run() {
    update_repo

    local version
    version="$(resolve_version)"
    log "Target version: ${version}"

    if gh release view "$version" >/dev/null 2>&1; then
        log "Release ${version} already exists; nothing to do."
        return 0
    fi

    log "Building database..."
    uvrun > "$SUMMARY_FILE"           # stdout = KEY=VALUE summary; stderr -> log

    create_release "$version"
    prune_releases
    log "Done: published ${version}"
}

main() {
    trap 'rm -f "$LOG_FILE" "${SUMMARY_FILE:-}"' EXIT
    parse_args "$@"

    [ -n "${GH_TOKEN:-}" ] || die "GH_TOKEN is not set"
    export GH_TOKEN
    for t in uv gh git curl; do
        command -v "$t" >/dev/null || die "$t not found on PATH"
    done

    SUMMARY_FILE="$(mktemp -t aeromux-db-summary.XXXXXX.txt)"

    hc_ping "/start"

    # Run the pipeline, capturing everything to the log (for the fail ping) and to
    # stdout (journald). errexit is lifted only around the pipeline so the real exit
    # status can be read from PIPESTATUS before deciding which ping to send.
    set +e
    run 2>&1 | tee "$LOG_FILE"
    local rc=${PIPESTATUS[0]}
    set -e

    if [ "$rc" -eq 0 ]; then hc_ping ""; else hc_ping "/fail"; fi
    exit "$rc"
}

main "$@"
