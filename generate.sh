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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --silent)
            SILENT=true
            shift
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo ""
            echo "Usage: ./generate.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --silent  Suppress all output (only errors are shown)"
            echo ""
            echo "Examples:"
            echo "  ./generate.sh           # Generate database with full output"
            echo "  ./generate.sh --silent   # Generate database silently"
            exit 1
            ;;
    esac
done

# Logging helper (suppressed in silent mode)
log() { [ "$SILENT" = true ] || echo "$@"; }

# Clear screen (suppressed in silent mode)
[ "$SILENT" = true ] || clear

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
GENERATE_OUTPUT=$(uv run --directory "$PROJECT_ROOT" aeromux-db 2>&1) || {
    [ "$SILENT" = true ] || echo "✗ $CURRENT_STEP failed"
    echo ""
    echo "================================================"
    echo "GENERATE FAILED"
    echo "================================================"
    if [ -n "$GENERATE_OUTPUT" ]; then
        echo ""
        echo "An error occurred during generation. See the log below for details."
        echo "Paths relative to: $PROJECT_ROOT/"
        echo ""
        echo "$GENERATE_OUTPUT" | sed "s|$PROJECT_ROOT/|./|g" | sed 's/^[[:space:]]*//' | fold -s -w $((TERMINAL_WIDTH - 3)) | sed 's/^/ | /'
    fi
    echo ""
    exit 1
}
log "✓ Database generated"
log ""

# Parse summary values from Python output
OUTPUT_FILE=$(echo "$GENERATE_OUTPUT" | grep "^OUTPUT_FILE=" | cut -d= -f2-)
AIRCRAFT_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^AIRCRAFT_COUNT=" | cut -d= -f2-)
TYPES_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^TYPES_COUNT=" | cut -d= -f2-)
OPERATORS_COUNT=$(echo "$GENERATE_OUTPUT" | grep "^OPERATORS_COUNT=" | cut -d= -f2-)
FILE_SIZE=$(echo "$GENERATE_OUTPUT" | grep "^FILE_SIZE=" | cut -d= -f2-)

# Summary
log "================================================"
log "GENERATE SUMMARY"
log "================================================"
log ""
log "Generation completed successfully!"
log ""
log "Output file: $OUTPUT_FILE"
log "File size: $FILE_SIZE"
log ""
log "Records:"
log "  - Aircraft: $AIRCRAFT_COUNT"
log "  - Types: $TYPES_COUNT"
log "  - Operators: $OPERATORS_COUNT"
log ""

# Step 4: Cleanup
CURRENT_STEP="Cleanup"
log "Cleaning up..."
rm -rf "$PROJECT_ROOT/.venv"
find "$PROJECT_ROOT/temp" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
log "✓ Cleanup complete"
log ""
