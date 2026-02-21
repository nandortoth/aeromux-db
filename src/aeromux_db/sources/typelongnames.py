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
from pathlib import Path

from aeromux_db.models import TypeLongnameData

logger = logging.getLogger(__name__)

SOURCE_URL = "https://github.com/wiedehopf/type-longnames-chrisglobe/archive/refs/heads/master.tar.gz"
SOURCE_FILENAME = "type-longnames-chrisglobe.tar.gz"


def _to_str(value: str | None) -> str | None:
    """Return None for empty strings, otherwise the stripped value."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def parse_aircraft(extract_dir: Path) -> list[TypeLongnameData]:
    """Parse all CSV files from the extracted type-longnames tarball.

    The tarball extracts to a directory containing ``individual-types/``
    with one CSV per type code.  Each CSV has no header and five columns:
    ``icao, registration, type_code, (unused), type_description``.

    Args:
        extract_dir: Path to the extracted tarball directory.

    Returns:
        List of parsed type-longname records.
    """
    aircraft: list[TypeLongnameData] = []

    csv_files = sorted(extract_dir.rglob("individual-types/*.csv"))
    if not csv_files:
        logger.warning("No CSV files found in %s", extract_dir)
        return aircraft

    for csv_file in csv_files:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 5:
                    continue
                icao = _to_str(row[0])
                if icao is None:
                    continue
                aircraft.append(
                    TypeLongnameData(
                        aircraft_icao_address=icao.upper(),
                        aircraft_registration=_to_str(row[1]),
                        aircraft_type_code=_to_str(row[2]),
                        type_description=_to_str(row[4]),
                    )
                )

    logger.debug("Parsed %d aircraft from type-longnames (%d files)", len(aircraft), len(csv_files))
    return aircraft
