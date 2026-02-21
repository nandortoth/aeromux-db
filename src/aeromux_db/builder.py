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

import csv
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aeromux_db import __version__
from aeromux_db.models import Aircraft, AircraftDetails, AircraftType, Operator

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"


@dataclass
class BuildResult:
    """Result of a database build operation."""

    path: Path
    total_aircraft: int

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schema" / "schema.sql"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def build_database(
    aircraft: list[Aircraft],
    types: list[AircraftType],
    operators: list[Operator],
    adsbx_aircraft: list[Aircraft] | None = None,
    aircraft_details: list[AircraftDetails] | None = None,
) -> BuildResult:
    """Build the SQLite database and return the output path.

    Insert parsed aircraft, type, and operator records into a SQLite
    database with schema versioning and build metadata.  When ADS-B
    Exchange data is provided, merge additional aircraft into the table
    and populate the aircraft_details table.

    Args:
        aircraft: Parsed aircraft records with ICAO 24-bit addresses.
        types: Parsed aircraft type records keyed by ICAO type designator.
        operators: Parsed operator records keyed by ICAO airline designator.
        adsbx_aircraft: ADS-B Exchange aircraft records to merge after
            the primary source.
        aircraft_details: Extended aircraft detail records from ADS-B
            Exchange.

    Returns:
        BuildResult with path and total aircraft count.

    Raises:
        sqlite3.OperationalError: When the schema file is missing or invalid.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACTS_DIR / f"aeromux-db_{__version__}.sqlite"

    if output_path.exists():
        output_path.unlink()

    logger.debug("Creating database at %s", output_path)

    conn = sqlite3.connect(str(output_path))
    try:
        conn.execute("PRAGMA encoding = 'UTF-8'")

        schema_sql = SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)

        logger.debug("Inserting %d types", len(types))
        conn.executemany(
            "INSERT INTO types (type_code, type_description, type_icao_class) VALUES (?, ?, ?)",
            [(t.type_code, t.type_description, t.type_icao_class) for t in types],
        )

        logger.debug("Inserting %d operators", len(operators))
        conn.executemany(
            "INSERT INTO operators (operator_icao, operator_name, operator_country, operator_callsign) VALUES (?, ?, ?, ?)",
            [
                (o.operator_icao, o.operator_name, o.operator_country, o.operator_callsign)
                for o in operators
            ],
        )

        logger.debug("Inserting %d aircraft", len(aircraft))
        conn.executemany(
            "INSERT INTO aircrafts (aircraft_icao_address, aircraft_registration, aircraft_type_code) VALUES (?, ?, ?)",
            [(a.aircraft_icao_address, a.aircraft_registration, a.aircraft_type_code) for a in aircraft],
        )

        # Merge ADS-B Exchange aircraft
        total_aircraft = len(aircraft)
        if adsbx_aircraft:
            existing_with_reg = {
                row[0]: row[1]
                for row in conn.execute("SELECT aircraft_icao_address, aircraft_registration FROM aircrafts")
            }

            new_aircraft = []
            reg_mismatches = []
            for a in adsbx_aircraft:
                if a.aircraft_icao_address in existing_with_reg:
                    existing_reg = existing_with_reg[a.aircraft_icao_address]
                    if a.aircraft_registration and existing_reg and a.aircraft_registration != existing_reg:
                        reg_mismatches.append((a.aircraft_icao_address, existing_reg, a.aircraft_registration))
                else:
                    new_aircraft.append(a)

            if new_aircraft:
                logger.debug("Inserting %d new aircraft from ADS-B Exchange", len(new_aircraft))
                conn.executemany(
                    "INSERT INTO aircrafts (aircraft_icao_address, aircraft_registration, aircraft_type_code) VALUES (?, ?, ?)",
                    [(a.aircraft_icao_address, a.aircraft_registration, a.aircraft_type_code) for a in new_aircraft],
                )

            total_aircraft += len(new_aircraft)

            if reg_mismatches:
                mismatch_path = ARTIFACTS_DIR / "reg_mismatches.csv"
                with open(mismatch_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["icao_address", "mictronics_reg", "adsbx_reg"])
                    writer.writerows(reg_mismatches)
                logger.info("  Wrote %s registration mismatches to %s", f"{len(reg_mismatches):,}", mismatch_path.relative_to(PROJECT_ROOT))

            logger.info(
                "  ADS-B Exchange merge: %s new aircraft, %s registration mismatches",
                f"{len(new_aircraft):,}",
                f"{len(reg_mismatches):,}",
            )

        # Insert aircraft details
        if aircraft_details:
            logger.debug("Inserting %d aircraft details", len(aircraft_details))
            conn.executemany(
                "INSERT INTO aircraft_details "
                "(aircraft_icao_address, year, manufacturer, model, owner_operator, faa_pia, faa_ladd, military) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        d.aircraft_icao_address,
                        d.year,
                        d.manufacturer,
                        d.model,
                        d.owner_operator,
                        int(d.faa_pia),
                        int(d.faa_ladd),
                        int(d.military),
                    )
                    for d in aircraft_details
                ],
            )

        logger.debug("Writing metadata")
        build_timestamp = datetime.now(timezone.utc).isoformat()
        metadata = [
            ("build_timestamp", build_timestamp),
            ("tool_version", __version__),
            ("schema_version", SCHEMA_VERSION),
            ("record_count", str(total_aircraft)),
        ]
        conn.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            metadata,
        )

        conn.commit()
    finally:
        conn.close()

    logger.debug("Database built successfully: %s", output_path)
    return BuildResult(path=output_path, total_aircraft=total_aircraft)
