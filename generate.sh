#!/bin/bash

# Aeromux Database Builder — Generate Script
# This script generates the Aeromux SQLite database from external data sources
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

set -e  # Exit on error

# Build step tracking
CURRENT_STEP=""
TERMINAL_WIDTH=$(stty size 2>/dev/null | awk '{print $2}')
: "${TERMINAL_WIDTH:=80}"

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"

# Parse named parameters
SILENT=false
RELEASE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --silent)
            SILENT=true
            shift
            ;;
        --release)
            RELEASE="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo ""
            echo "Usage: ./generate.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --silent       Suppress all output (only errors are shown)"
            echo "  --release N    Release number within the current week (default: 1)"
            echo ""
            echo "Examples:"
            echo "  ./generate.sh                 # Generate database with full output"
            echo "  ./generate.sh --silent        # Generate database silently"
            echo "  ./generate.sh --release 2     # Generate second release of the week"
            exit 1
            ;;
    esac
done

# Logging helper (suppressed in silent mode)
log() { [ "$SILENT" = true ] || echo "$@"; }

# Clear screen (suppressed in silent mode)
[ "$SILENT" = true ] || clear

START_TIME=$SECONDS

log "================================================"
log "Aeromux Database Builder — Generate Script"
log "================================================"
log ""

# Run a command quietly — suppress output on success, show on failure
run_quiet() {
    local output
    output=$("$@" 2>&1) || {
        [ -z "$CURRENT_STEP" ] || [ "$SILENT" = true ] || echo "✗ $CURRENT_STEP failed"
        echo ""
        echo "================================================"
        echo "GENERATE FAILED"
        echo "================================================"
        if [ -n "$output" ]; then
            echo ""
            echo "An error occurred during generation. See the log below for details."
            echo "Paths relative to: $PROJECT_ROOT/"
            echo ""
            echo "$output" | sed "s|$PROJECT_ROOT/|./|g" | sed 's/^[[:space:]]*//' | fold -s -w $((TERMINAL_WIDTH - 3)) | sed 's/^/ | /'
        fi
        echo ""
        exit 1
    }
}

# Step 1: Clean virtual environment
CURRENT_STEP="Clean virtual environment"
log "Cleaning virtual environment..."
rm -rf "$PROJECT_ROOT/.venv"
log "✓ Virtual environment cleaned"
log ""

# Step 2: Install dependencies
CURRENT_STEP="Install dependencies"
log "Installing dependencies..."
run_quiet uv sync --directory "$PROJECT_ROOT"
log "✓ Dependencies installed"
log ""

# Step 3: Generate database
CURRENT_STEP="Generate database"
log "Generating database..."

SUMMARY_FILE=$(mktemp)
STDERR_FILE=$(mktemp)
STDERR_FIFO=$(mktemp -u)
mkfifo "$STDERR_FIFO"
trap "rm -f '$SUMMARY_FILE' '$STDERR_FILE' '$STDERR_FIFO'" EXIT

# Background reader: display stderr log lines as indented progress in real time
(LAST_WAS_PROGRESS=false
while IFS= read -r line; do
    echo "$line" >> "$STDERR_FILE"
    if [ "$SILENT" != true ]; then
        # Strip timestamp and log prefix to show clean progress
        msg=$(echo "$line" | sed 's/^[0-9-]* [0-9:,]*[[:space:]]*\[[A-Z]*\][[:space:]]*[^:]*: //')
        if echo "$msg" | grep -q '^PROGRESS: '; then
            # Download progress — overwrite in place, cursor on next line
            progress_text=$(echo "$msg" | sed 's/^PROGRESS: //')
            if [ "$LAST_WAS_PROGRESS" = true ]; then
                printf "\033[A\r      %-60s\n" "$progress_text"
            else
                printf "\r      %-60s\n" "$progress_text"
            fi
            LAST_WAS_PROGRESS=true
        else
            if [ "$LAST_WAS_PROGRESS" = true ]; then
                # Move up and clear the progress line before printing the next line
                printf "\033[A\r%-66s\r" ""
                LAST_WAS_PROGRESS=false
            fi
            if echo "$msg" | grep -q '^Step [0-9]'; then
                # Step header — display prominently
                echo "  → $msg"
            elif echo "$msg" | grep -q '^Build complete'; then
                # Final summary — display prominently
                echo "  → $msg"
            elif echo "$msg" | grep -q '^Build interrupted'; then
                # Interrupted by user
                echo ""
                echo "✗ $msg"
            else
                # Sub-step detail — indent further
                echo "    $msg"
            fi
        fi
    fi
done < "$STDERR_FIFO") &
READER_PID=$!

# Run Python pipeline:
#   - stdout (KEY=VALUE summary) → captured to file
#   - stderr (log lines) → FIFO for real-time display
EXTRA_ARGS=()
[ -n "$RELEASE" ] && EXTRA_ARGS+=(--release "$RELEASE")
uv run --directory "$PROJECT_ROOT" aeromux-db "${EXTRA_ARGS[@]}" > "$SUMMARY_FILE" 2>"$STDERR_FIFO"
GENERATE_EXIT=$?

wait "$READER_PID"

if [ "$GENERATE_EXIT" -ne 0 ]; then
    if [ "$GENERATE_EXIT" -eq 130 ]; then
        # Interrupted by user — already displayed by FIFO reader
        exit 130
    fi
    [ "$SILENT" = true ] || echo "✗ $CURRENT_STEP failed"
    echo ""
    echo "================================================"
    echo "GENERATE FAILED"
    echo "================================================"
    GENERATE_OUTPUT=$(cat "$STDERR_FILE" 2>/dev/null)
    if [ -n "$GENERATE_OUTPUT" ]; then
        echo ""
        echo "An error occurred during generation. See the log below for details."
        echo "Paths relative to: $PROJECT_ROOT/"
        echo ""
        echo "$GENERATE_OUTPUT" | sed "s|$PROJECT_ROOT/|./|g" | sed 's/^[[:space:]]*//' | fold -s -w $((TERMINAL_WIDTH - 3)) | sed 's/^/ | /'
    fi
    echo ""
    exit 1
fi
log "✓ Database generated"
log ""

# Parse summary values from Python output (stdout)
GENERATE_OUTPUT=$(cat "$SUMMARY_FILE")
DB_VERSION=$(echo "$GENERATE_OUTPUT" | grep "^DB_VERSION=" | cut -d= -f2-)
OUTPUT_FILE=$(echo "$GENERATE_OUTPUT" | grep "^OUTPUT_FILE=" | cut -d= -f2-)
AIRCRAFT_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^AIRCRAFT_COUNT=" | cut -d= -f2-)
TYPES_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^TYPES_COUNT=" | cut -d= -f2-)
OPERATORS_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^OPERATORS_COUNT=" | cut -d= -f2-)
ADSBX_AIRCRAFT_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^ADSBX_AIRCRAFT_COUNT=" | cut -d= -f2-)
ADSBX_DETAILS_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^ADSBX_DETAILS_COUNT=" | cut -d= -f2-)
ADSBX_FALLBACK_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^ADSBX_FALLBACK_COUNT=" | cut -d= -f2-)
OPENSKY_MANUFACTURERS_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^OPENSKY_MANUFACTURERS_COUNT=" | cut -d= -f2-)
OPENSKY_ENRICHMENT_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^OPENSKY_ENRICHMENT_COUNT=" | cut -d= -f2-)
TYPELONGNAMES_AIRCRAFT_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^TYPELONGNAMES_AIRCRAFT_COUNT=" | cut -d= -f2-)
FILE_SIZE=$(echo "$GENERATE_OUTPUT" | grep "^FILE_SIZE=" | cut -d= -f2-)

# Summary
log "================================================"
log "GENERATE SUMMARY"
log "================================================"
log ""
log "Generation completed successfully!"
log ""
log "Database version: $DB_VERSION"
log "Output file: $OUTPUT_FILE"
log "File size: $FILE_SIZE"
log ""
log "Records:"
log "  - Aircraft: $AIRCRAFT_COUNT"
log "  - Types: $TYPES_COUNT"
log "  - Operators: $OPERATORS_COUNT"
log "  - Manufacturers: $OPENSKY_MANUFACTURERS_COUNT"
log "  - Aircraft details: $ADSBX_DETAILS_COUNT"
log "  - Aircraft fallback: $ADSBX_FALLBACK_COUNT"
log "  - OpenSky enriched: $OPENSKY_ENRICHMENT_COUNT"
log "  - Type-longnames: $TYPELONGNAMES_AIRCRAFT_COUNT"
log ""

ELAPSED=$((SECONDS - START_TIME))
log "Elapsed time: ${ELAPSED}s"
log ""

# Step 4: Cleanup
CURRENT_STEP="Cleanup"
log "Cleaning up..."
rm -rf "$PROJECT_ROOT/.venv"
log "✓ Cleanup complete"
log ""
