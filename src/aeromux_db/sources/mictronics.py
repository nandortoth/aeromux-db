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

import json
import logging
from pathlib import Path

from aeromux_db.models import Aircraft, AircraftType, Operator

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.mictronics.de/aircraft-database/indexedDB.php"
SOURCE_FILENAME = "mictronics.zip"


def parse_types(data_dir: Path) -> list[AircraftType]:
    """Parse types.json into AircraftType records.

    The source JSON maps type codes to positional arrays:
    ``{"B738": ["Boeing 737-800", "L2J"], ...}``

    Args:
        data_dir: Directory containing the extracted Mictronics data files.

    Returns:
        List of parsed aircraft type records.
    """
    path = data_dir / "types.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    types = []
    for type_code, values in raw.items():
        types.append(
            AircraftType(
                type_code=type_code,
                type_description=values[0] if len(values) > 0 else None,
                type_icao_class=values[1] if len(values) > 1 else None,
            )
        )
    logger.debug("Parsed %d types from Mictronics", len(types))
    return types


def parse_operators(data_dir: Path) -> list[Operator]:
    """Parse operators.json into Operator records.

    The source JSON maps ICAO airline codes to positional arrays:
    ``{"AAL": ["American Airlines", "United States", "AMERICAN"], ...}``

    Args:
        data_dir: Directory containing the extracted Mictronics data files.

    Returns:
        List of parsed operator records.
    """
    path = data_dir / "operators.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    operators = []
    for operator_icao, values in raw.items():
        operators.append(
            Operator(
                operator_icao=operator_icao,
                operator_name=values[0] if len(values) > 0 else None,
                operator_country=values[1] if len(values) > 1 else None,
                operator_callsign=values[2] if len(values) > 2 else None,
            )
        )
    logger.debug("Parsed %d operators from Mictronics", len(operators))
    return operators


def parse_aircraft(data_dir: Path) -> list[Aircraft]:
    """Parse aircrafts.json into Aircraft records.

    The source JSON maps ICAO 24-bit hex addresses to positional arrays:
    ``{"a00001": ["N1", "B738"], ...}``

    Args:
        data_dir: Directory containing the extracted Mictronics data files.

    Returns:
        List of parsed aircraft records.
    """
    path = data_dir / "aircrafts.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    aircraft = []
    for icao_address, values in raw.items():
        aircraft.append(
            Aircraft(
                # Normalize to uppercase — source data uses mixed-case ICAO addresses
                icao_address=icao_address.upper(),
                registration=values[0] if len(values) > 0 and values[0] else None,
                type_code=values[1] if len(values) > 1 and values[1] else None,
            )
        )
    logger.debug("Parsed %d aircraft from Mictronics", len(aircraft))
    return aircraft
