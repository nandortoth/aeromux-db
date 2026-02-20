# Aeromux Database Builder
# Copyright (C) 2025-2026 Nandor Toth <dev@nandortoth.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import logging
import os
import sys

from aeromux_db import __version__
from aeromux_db.builder import build_database
from aeromux_db.cli import parse_args
from aeromux_db.downloader import download, extract_zip
from aeromux_db.sources.mictronics import (
    SOURCE_FILENAME,
    SOURCE_URL,
    parse_aircraft,
    parse_operators,
    parse_types,
)

logger = logging.getLogger("aeromux_db")


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def main() -> None:
    """Run the full database build pipeline: download, extract, parse, and build."""
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info("Aeromux Database Builder v%s", __version__)

    try:
        # Step 1: Download
        logger.info("Downloading Mictronics database...")
        zip_path = download(SOURCE_URL, SOURCE_FILENAME)

        # Step 2: Extract
        logger.info("Extracting archive...")
        data_dir = extract_zip(zip_path)

        # Step 3: Parse
        logger.info("Parsing data sources...")
        types = parse_types(data_dir)
        operators = parse_operators(data_dir)
        aircraft = parse_aircraft(data_dir)

        # Step 4: Build database
        logger.info("Building database...")
        output_path = build_database(aircraft, types, operators)

        # Summary
        logger.info("Build complete!")
        logger.info(
            "Output: %s | Aircraft: %s | Types: %s | Operators: %s",
            output_path,
            f"{len(aircraft):,}",
            f"{len(types):,}",
            f"{len(operators):,}",
        )

        # Print structured summary to stdout for shell integration
        file_size = _format_file_size(os.path.getsize(output_path))
        print(f"OUTPUT_FILE={output_path}")
        print(f"AIRCRAFT_COUNT={len(aircraft):,}")
        print(f"TYPES_COUNT={len(types):,}")
        print(f"OPERATORS_COUNT={len(operators):,}")
        print(f"FILE_SIZE={file_size}")
    except Exception:
        logger.exception("Build failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
