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
import tempfile
import time
from pathlib import Path

from aeromux_db import __version__
from aeromux_db.builder import PROJECT_ROOT, build_database
from aeromux_db.cli import parse_args
from aeromux_db.version import get_db_version
from aeromux_db.downloader import download, extract_tarball, extract_zip, fetch_text
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
from aeromux_db.sources.planealertdb import (
    SOURCE_FILENAME as PLANEALERTDB_SOURCE_FILENAME,
    SOURCE_URL as PLANEALERTDB_SOURCE_URL,
    parse_aircraft as planealertdb_parse_aircraft,
)
from aeromux_db.sources.tar1090db import (
    SOURCE_FILENAME as TAR1090DB_SOURCE_FILENAME,
    SOURCE_URL as TAR1090DB_SOURCE_URL,
    parse_wtc as tar1090db_parse_wtc,
)
from aeromux_db.sources.typelongnames import (
    SOURCE_FILENAME as TYPELONGNAMES_SOURCE_FILENAME,
    SOURCE_URL as TYPELONGNAMES_SOURCE_URL,
    parse_aircraft as typelongnames_parse_aircraft,
)

logger = logging.getLogger("aeromux_db")

_STDERR_IS_TTY = False

PROGRESS_UPDATE_INTERVAL = 0.5  # seconds


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _make_progress_callback():
    """Create a download progress callback that updates in-place on stderr."""
    last_update = 0.0
    has_printed = False

    def callback(downloaded: int, total: int | None) -> None:
        nonlocal last_update, has_printed
        now = time.monotonic()
        if now - last_update < PROGRESS_UPDATE_INTERVAL:
            return
        last_update = now

        dl_str = _format_file_size(downloaded)
        if total:
            total_str = _format_file_size(total)
            pct = downloaded / total * 100
            msg = f"Downloading {dl_str}/{total_str} ({pct:.1f}%)..."
        else:
            msg = f"Downloading {dl_str}..."

        if _STDERR_IS_TTY:
            prefix = "\033[A\r" if has_printed else "\r"
            sys.stderr.write(f"{prefix}  {msg: <60}\n")
            sys.stderr.flush()
            has_printed = True
        else:
            logger.info("PROGRESS: %s", msg)

    return callback


def _clear_progress_line() -> None:
    """Clear the in-place progress line from stderr."""
    if _STDERR_IS_TTY:
        sys.stderr.write(f"\033[A\r{'': <64}\r")
        sys.stderr.flush()


def main() -> None:
    """Run the full database build pipeline: download, extract, parse, and build."""
    global _STDERR_IS_TTY
    _STDERR_IS_TTY = sys.stderr.isatty()

    args = parse_args()

    if args.print_version:
        print(get_db_version(release=args.release))
        return

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    db_version = get_db_version(release=args.release)
    logger.debug("Aeromux Database Builder v%s (db %s)", __version__, db_version)
    start_time = time.monotonic()

    try:
        with tempfile.TemporaryDirectory(prefix="aeromux-db_") as tmp:
            temp_dir = Path(tmp)

            # Step 1: Download Mictronics
            logger.info("Step 1/16: Downloading Mictronics database...")
            result = download(SOURCE_URL, SOURCE_FILENAME, temp_dir, progress_callback=_make_progress_callback())
            _clear_progress_line()
            logger.info("  Downloaded %s", _format_file_size(result.size_bytes))

            # Step 2: Extract Mictronics
            logger.info("Step 2/16: Extracting Mictronics archive...")
            extract = extract_zip(result.path)
            logger.info("  Extracted %d files", extract.file_count)

            # Step 3: Parse Mictronics
            logger.info("Step 3/16: Parsing Mictronics data...")
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
            logger.info("Step 4/16: Downloading ADS-B Exchange database...")
            adsbx_result = download(ADSBX_SOURCE_URL, ADSBX_SOURCE_FILENAME, temp_dir, progress_callback=_make_progress_callback())
            _clear_progress_line()
            logger.info("  Downloaded %s", _format_file_size(adsbx_result.size_bytes))

            # Step 5: Parse ADS-B Exchange
            logger.info("Step 5/16: Parsing ADS-B Exchange data...")
            logger.info("  Parsing aircraft...")
            adsbx_aircraft, adsbx_malformed = adsbx_parse_aircraft(adsbx_result.path)
            logger.info("  Parsed %s aircraft", f"{len(adsbx_aircraft):,}")
            logger.info("  Parsing aircraft details...")
            adsbx_details, _ = adsbx_parse_aircraft_details(adsbx_result.path)
            logger.info("  Parsed %s aircraft details", f"{len(adsbx_details):,}")
            logger.info("  Parsing aircraft fallback data...")
            adsbx_fallback, _ = adsbx_parse_aircraft_fallbackdata(adsbx_result.path)
            logger.info("  Parsed %s aircraft fallback records", f"{len(adsbx_fallback):,}")

            # Step 6: Download OpenSky Network
            logger.info("Step 6/16: Downloading OpenSky Network database...")
            logger.info("  Resolving latest filename...")
            listing_xml = fetch_text(OPENSKY_S3_LISTING_URL)
            opensky_filename = opensky_resolve_latest_filename(listing_xml)
            logger.info("  Latest file: %s", opensky_filename)
            opensky_url = OPENSKY_DOWNLOAD_BASE_URL + opensky_filename
            opensky_result = download(opensky_url, opensky_filename, temp_dir, progress_callback=_make_progress_callback())
            _clear_progress_line()
            logger.info("  Downloaded %s", _format_file_size(opensky_result.size_bytes))

            # Step 7: Parse OpenSky Network
            logger.info("Step 7/16: Parsing OpenSky Network data...")
            logger.info("  Parsing manufacturers...")
            opensky_manufacturers = opensky_parse_manufacturers(opensky_result.path)
            logger.info("  Parsed %s manufacturers", f"{len(opensky_manufacturers):,}")
            logger.info("  Parsing operator IATA mappings...")
            opensky_op_iata = opensky_parse_operator_iata(opensky_result.path)
            logger.info("  Parsed %s operator IATA mappings", f"{len(opensky_op_iata):,}")
            logger.info("  Parsing aircraft enrichment data...")
            opensky_enrichment = opensky_parse_aircraft_enrichment(opensky_result.path)
            logger.info("  Parsed %s aircraft enrichment records", f"{len(opensky_enrichment):,}")

            # Step 8: Download Plane Alert DB
            logger.info("Step 8/16: Downloading Plane Alert DB...")
            planealertdb_result = download(PLANEALERTDB_SOURCE_URL, PLANEALERTDB_SOURCE_FILENAME, temp_dir, progress_callback=_make_progress_callback())
            _clear_progress_line()
            logger.info("  Downloaded %s", _format_file_size(planealertdb_result.size_bytes))

            # Step 9: Parse Plane Alert DB
            logger.info("Step 9/16: Parsing Plane Alert DB data...")
            planealertdb_aircraft = planealertdb_parse_aircraft(planealertdb_result.path)
            logger.info("  Parsed %s aircraft", f"{len(planealertdb_aircraft):,}")

            # Step 10: Download type-longnames
            logger.info("Step 10/16: Downloading type-longnames database...")
            typelongnames_result = download(TYPELONGNAMES_SOURCE_URL, TYPELONGNAMES_SOURCE_FILENAME, temp_dir, progress_callback=_make_progress_callback())
            _clear_progress_line()
            logger.info("  Downloaded %s", _format_file_size(typelongnames_result.size_bytes))

            # Step 11: Extract type-longnames
            logger.info("Step 11/16: Extracting type-longnames archive...")
            typelongnames_extract = extract_tarball(typelongnames_result.path)
            logger.info("  Extracted %d files", typelongnames_extract.file_count)

            # Step 12: Parse type-longnames
            logger.info("Step 12/16: Parsing type-longnames data...")
            typelongnames_aircraft = typelongnames_parse_aircraft(typelongnames_extract.path)
            logger.info("  Parsed %s aircraft", f"{len(typelongnames_aircraft):,}")

            # Step 13: Download tar1090-db
            logger.info("Step 13/16: Downloading tar1090-db...")
            tar1090db_result = download(TAR1090DB_SOURCE_URL, TAR1090DB_SOURCE_FILENAME, temp_dir, progress_callback=_make_progress_callback())
            _clear_progress_line()
            logger.info("  Downloaded %s", _format_file_size(tar1090db_result.size_bytes))

            # Step 14: Extract tar1090-db
            logger.info("Step 14/16: Extracting tar1090-db archive...")
            tar1090db_extract = extract_tarball(tar1090db_result.path)
            logger.info("  Extracted %d files", tar1090db_extract.file_count)

            # Step 15: Parse tar1090-db WTC data
            logger.info("Step 15/16: Parsing tar1090-db WTC data...")
            wtc_map = tar1090db_parse_wtc(tar1090db_extract.path)
            logger.info("  Parsed %s WTC entries", f"{len(wtc_map):,}")

            # Step 16: Build database
            logger.info("Step 16/16: Building database...")
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
                planealertdb_aircraft,
                typelongnames_aircraft,
                wtc_map,
                db_version=db_version,
            )

            # Summary
            elapsed = time.monotonic() - start_time
            types_wtc_count = sum(1 for t in types if t.type_wtc)
            logger.info("Build complete! (%.1fs)", elapsed)
            logger.debug(
                "Output: %s | Aircraft: %s | Types: %s (WTC: %s) | Operators: %s",
                result.path,
                f"{result.total_aircraft:,}",
                f"{len(types):,}",
                f"{types_wtc_count:,}",
                f"{len(operators):,}",
            )

            # Print structured summary to stdout for shell integration
            output_file_size = _format_file_size(os.path.getsize(result.path))
            print(f"DB_VERSION={db_version}")
            print(f"OUTPUT_FILE={result.path.relative_to(PROJECT_ROOT)}")
            print(f"AIRCRAFT_COUNT={result.total_aircraft:,}")
            print(f"TYPES_COUNT={len(types):,}")
            print(f"TYPES_WTC_COUNT={types_wtc_count:,}")
            print(f"OPERATORS_COUNT={len(operators):,}")
            print(f"MICTRONICS_AIRCRAFT_COUNT={len(aircraft):,}")
            print(f"ADSBX_AIRCRAFT_COUNT={len(adsbx_aircraft):,}")
            print(f"ADSBX_DETAILS_COUNT={len(adsbx_details):,}")
            print(f"ADSBX_FALLBACK_COUNT={len(adsbx_fallback):,}")
            print(f"ADSBX_MALFORMED_COUNT={adsbx_malformed:,}")
            print(f"OPENSKY_MANUFACTURERS_COUNT={len(opensky_manufacturers):,}")
            print(f"OPENSKY_ENRICHMENT_COUNT={len(opensky_enrichment):,}")
            print(f"PLANEALERTDB_AIRCRAFT_COUNT={len(planealertdb_aircraft):,}")
            print(f"TYPELONGNAMES_AIRCRAFT_COUNT={len(typelongnames_aircraft):,}")
            print(f"FILE_SIZE={output_file_size}")
    except KeyboardInterrupt:
        _clear_progress_line()
        logger.info("Build interrupted")
        sys.exit(130)
    except Exception:
        logger.exception("Build failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
