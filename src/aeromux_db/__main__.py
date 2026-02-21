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
import time

from aeromux_db import __version__
from aeromux_db.builder import build_database
from aeromux_db.cli import parse_args
from aeromux_db.downloader import download, extract_zip, fetch_text
from aeromux_db.sources.adsbexchange import (
    SOURCE_FILENAME as ADSBX_SOURCE_FILENAME,
    SOURCE_URL as ADSBX_SOURCE_URL,
    parse_aircraft as adsbx_parse_aircraft,
    parse_aircraft_details as adsbx_parse_aircraft_details,
    parse_aircraft_fallbackdata as adsbx_parse_aircraft_fallbackdata,
)
from aeromux_db.sources.mictronics import (
    SOURCE_FILENAME,
    SOURCE_URL,
    parse_aircraft,
    parse_operators,
    parse_types,
)
from aeromux_db.sources.opensky import (
    DOWNLOAD_BASE_URL as OPENSKY_DOWNLOAD_BASE_URL,
    S3_LISTING_URL as OPENSKY_S3_LISTING_URL,
    parse_aircraft_enrichment as opensky_parse_aircraft_enrichment,
    parse_manufacturers as opensky_parse_manufacturers,
    parse_operator_iata as opensky_parse_operator_iata,
    resolve_latest_filename as opensky_resolve_latest_filename,
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
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger.debug("Aeromux Database Builder v%s", __version__)
    start_time = time.monotonic()

    try:
        # Step 1: Download Mictronics
        logger.info("Step 1/8: Downloading Mictronics database...")
        result = download(SOURCE_URL, SOURCE_FILENAME)
        file_size_str = _format_file_size(result.size_bytes)
        if result.cached:
            logger.info("  Using cached file (%s)", file_size_str)
        else:
            logger.info("  Downloaded %s", file_size_str)

        # Step 2: Extract Mictronics
        logger.info("Step 2/8: Extracting Mictronics archive...")
        extract = extract_zip(result.path)
        logger.info("  Extracted %d files", extract.file_count)

        # Step 3: Parse Mictronics
        logger.info("Step 3/8: Parsing Mictronics data...")
        logger.info("  Parsing types...")
        types = parse_types(extract.path)
        logger.info("  Parsed %s types", f"{len(types):,}")
        logger.info("  Parsing operators...")
        operators = parse_operators(extract.path)
        logger.info("  Parsed %s operators", f"{len(operators):,}")
        logger.info("  Parsing aircraft...")
        aircraft = parse_aircraft(extract.path)
        logger.info("  Parsed %s aircraft", f"{len(aircraft):,}")

        # Step 4: Download ADS-B Exchange
        logger.info("Step 4/8: Downloading ADS-B Exchange database...")
        adsbx_result = download(ADSBX_SOURCE_URL, ADSBX_SOURCE_FILENAME)
        adsbx_size_str = _format_file_size(adsbx_result.size_bytes)
        if adsbx_result.cached:
            logger.info("  Using cached file (%s)", adsbx_size_str)
        else:
            logger.info("  Downloaded %s", adsbx_size_str)

        # Step 5: Parse ADS-B Exchange
        logger.info("Step 5/8: Parsing ADS-B Exchange data...")
        logger.info("  Parsing aircraft...")
        adsbx_aircraft = adsbx_parse_aircraft(adsbx_result.path)
        logger.info("  Parsed %s aircraft", f"{len(adsbx_aircraft):,}")
        logger.info("  Parsing aircraft details...")
        adsbx_details = adsbx_parse_aircraft_details(adsbx_result.path)
        logger.info("  Parsed %s aircraft details", f"{len(adsbx_details):,}")
        logger.info("  Parsing aircraft fallback data...")
        adsbx_fallback = adsbx_parse_aircraft_fallbackdata(adsbx_result.path)
        logger.info("  Parsed %s aircraft fallback records", f"{len(adsbx_fallback):,}")

        # Step 6: Download OpenSky Network
        logger.info("Step 6/8: Downloading OpenSky Network database...")
        logger.info("  Resolving latest filename...")
        listing_xml = fetch_text(OPENSKY_S3_LISTING_URL)
        opensky_filename = opensky_resolve_latest_filename(listing_xml)
        logger.info("  Latest file: %s", opensky_filename)
        opensky_url = OPENSKY_DOWNLOAD_BASE_URL + opensky_filename
        opensky_result = download(opensky_url, opensky_filename)
        opensky_size_str = _format_file_size(opensky_result.size_bytes)
        if opensky_result.cached:
            logger.info("  Using cached file (%s)", opensky_size_str)
        else:
            logger.info("  Downloaded %s", opensky_size_str)

        # Step 7: Parse OpenSky Network
        logger.info("Step 7/8: Parsing OpenSky Network data...")
        logger.info("  Parsing manufacturers...")
        opensky_manufacturers = opensky_parse_manufacturers(opensky_result.path)
        logger.info("  Parsed %s manufacturers", f"{len(opensky_manufacturers):,}")
        logger.info("  Parsing operator IATA mappings...")
        opensky_op_iata = opensky_parse_operator_iata(opensky_result.path)
        logger.info("  Parsed %s operator IATA mappings", f"{len(opensky_op_iata):,}")
        logger.info("  Parsing aircraft enrichment data...")
        opensky_enrichment = opensky_parse_aircraft_enrichment(opensky_result.path)
        logger.info("  Parsed %s aircraft enrichment records", f"{len(opensky_enrichment):,}")

        # Step 8: Build database
        logger.info("Step 8/8: Building database...")
        result = build_database(
            aircraft,
            types,
            operators,
            adsbx_aircraft,
            adsbx_details,
            adsbx_fallback,
            opensky_manufacturers,
            opensky_op_iata,
            opensky_enrichment,
        )

        # Summary
        elapsed = time.monotonic() - start_time
        logger.info("Build complete! (%.1fs)", elapsed)
        logger.debug(
            "Output: %s | Aircraft: %s | Types: %s | Operators: %s",
            result.path,
            f"{result.total_aircraft:,}",
            f"{len(types):,}",
            f"{len(operators):,}",
        )

        # Print structured summary to stdout for shell integration
        output_file_size = _format_file_size(os.path.getsize(result.path))
        print(f"OUTPUT_FILE={result.path}")
        print(f"AIRCRAFT_COUNT={result.total_aircraft:,}")
        print(f"TYPES_COUNT={len(types):,}")
        print(f"OPERATORS_COUNT={len(operators):,}")
        print(f"ADSBX_AIRCRAFT_COUNT={len(adsbx_aircraft):,}")
        print(f"ADSBX_DETAILS_COUNT={len(adsbx_details):,}")
        print(f"ADSBX_FALLBACK_COUNT={len(adsbx_fallback):,}")
        print(f"OPENSKY_MANUFACTURERS_COUNT={len(opensky_manufacturers):,}")
        print(f"OPENSKY_ENRICHMENT_COUNT={len(opensky_enrichment):,}")
        print(f"FILE_SIZE={output_file_size}")
    except Exception:
        logger.exception("Build failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
