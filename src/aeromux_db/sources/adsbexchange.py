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

import gzip
import json
import logging
from pathlib import Path

from aeromux_db.models import Aircraft, AircraftDetails, AircraftFallbackData

logger = logging.getLogger(__name__)

SOURCE_URL = "http://downloads.adsbexchange.com/downloads/basic-ac-db.json.gz"
SOURCE_FILENAME = "basic-ac-db.json.gz"


def _sanitize(value: str | None) -> str | None:
    """Remove stray backslash and dot artifacts from a string value."""
    if value is None:
        return None
    value = value.replace("\\.", "")
    value = value.replace(".", "")
    value = value.replace("\\", "")
    return value or None


def parse_aircraft(file_path: Path) -> list[Aircraft]:
    """Parse gzipped JSON lines into Aircraft records.

    Each line is a JSON object with at least ``icao``, ``reg``, and
    ``icaotype`` fields.

    Args:
        file_path: Path to the gzipped JSON file.

    Returns:
        List of parsed aircraft records.
    """
    aircraft = []
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            aircraft.append(
                Aircraft(
                    aircraft_icao_address=record["icao"].upper(),
                    aircraft_registration=_sanitize(record.get("reg")),
                    aircraft_type_code=_sanitize(record.get("icaotype")),
                )
            )
    logger.debug("Parsed %d aircraft from ADS-B Exchange", len(aircraft))
    return aircraft


def parse_aircraft_details(file_path: Path) -> list[AircraftDetails]:
    """Parse gzipped JSON lines into AircraftDetails records.

    Each line is a JSON object with extended aircraft information
    such as year, manufacturer, model, owner/operator, and flags.

    Args:
        file_path: Path to the gzipped JSON file.

    Returns:
        List of parsed aircraft detail records.
    """
    details = []
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            details.append(
                AircraftDetails(
                    aircraft_icao_address=record["icao"].upper(),
                    year=_sanitize(record.get("year")),
                    model=_sanitize(record.get("model")),
                    owner_operator=_sanitize(record.get("ownop")),
                    faa_pia=bool(record.get("faa_pia", False)),
                    faa_ladd=bool(record.get("faa_ladd", False)),
                    military=bool(record.get("mil", False)),
                )
            )
    logger.debug("Parsed %d aircraft details from ADS-B Exchange", len(details))
    return details


def parse_aircraft_fallbackdata(file_path: Path) -> list[AircraftFallbackData]:
    """Parse gzipped JSON lines into AircraftFallbackData records.

    Extracts manufacturer names as plain-text fallback data for aircraft
    that may not have a normalized manufacturer reference.

    Args:
        file_path: Path to the gzipped JSON file.

    Returns:
        List of parsed aircraft fallback data records.
    """
    fallback = []
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            manufacturer = _sanitize(record.get("manufacturer"))
            if manufacturer:
                fallback.append(
                    AircraftFallbackData(
                        aircraft_icao_address=record["icao"].upper(),
                        manufacturer=manufacturer,
                    )
                )
    logger.debug("Parsed %d aircraft fallback records from ADS-B Exchange", len(fallback))
    return fallback
