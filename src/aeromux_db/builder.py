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
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aeromux_db import __version__
from aeromux_db.models import Aircraft, AircraftType, Operator

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schema" / "schema.sql"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def build_database(
    aircraft: list[Aircraft],
    types: list[AircraftType],
    operators: list[Operator],
) -> Path:
    """Build the SQLite database and return the output path.

    Insert parsed aircraft, type, and operator records into a SQLite
    database with schema versioning and build metadata.

    Args:
        aircraft: Parsed aircraft records with ICAO 24-bit addresses.
        types: Parsed aircraft type records keyed by ICAO type designator.
        operators: Parsed operator records keyed by ICAO airline designator.

    Returns:
        Path to the generated SQLite database file in the artifacts directory.

    Raises:
        sqlite3.OperationalError: When the schema file is missing or invalid.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACTS_DIR / f"aeromux-db_{__version__}.sqlite"

    if output_path.exists():
        output_path.unlink()

    logger.info("Creating database at %s", output_path)

    conn = sqlite3.connect(str(output_path))
    try:
        conn.execute("PRAGMA encoding = 'UTF-8'")

        schema_sql = SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)

        logger.info("Inserting %d types", len(types))
        conn.executemany(
            "INSERT INTO types (type_code, type_description, type_icao_class) VALUES (?, ?, ?)",
            [(t.type_code, t.type_description, t.type_icao_class) for t in types],
        )

        logger.info("Inserting %d operators", len(operators))
        conn.executemany(
            "INSERT INTO operators (operator_icao, operator_name, operator_country, operator_callsign) VALUES (?, ?, ?, ?)",
            [
                (o.operator_icao, o.operator_name, o.operator_country, o.operator_callsign)
                for o in operators
            ],
        )

        logger.info("Inserting %d aircraft", len(aircraft))
        conn.executemany(
            "INSERT INTO aircraft (icao_address, registration, type_code) VALUES (?, ?, ?)",
            [(a.icao_address, a.registration, a.type_code) for a in aircraft],
        )

        build_timestamp = datetime.now(timezone.utc).isoformat()
        metadata = [
            ("build_timestamp", build_timestamp),
            ("tool_version", __version__),
            ("schema_version", SCHEMA_VERSION),
            ("record_count", str(len(aircraft))),
        ]
        conn.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            metadata,
        )

        conn.commit()
    finally:
        conn.close()

    logger.info("Database built successfully: %s", output_path)
    return output_path
