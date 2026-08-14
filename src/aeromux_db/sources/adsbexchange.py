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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from aeromux_db.models import Aircraft, AircraftDetails, AircraftFallbackData

logger = logging.getLogger(__name__)

SOURCE_URL = "http://downloads.adsbexchange.com/downloads/basic-ac-db.json.gz"
SOURCE_FILENAME = "basic-ac-db.json.gz"

MAX_MALFORMED_RATIO = 0.001
MAX_MALFORMED_REPORTED = 5


def _sanitize(value: str | None) -> str | None:
    """Remove stray backslash and dot artifacts from a string value."""
    if value is None:
        return None
    value = value.replace("\\.", "")
    value = value.replace(".", "")
    value = value.replace("\\", "")
    return value or None


class _RecordReader:
    """Iterates the records of a gzipped JSON-lines file, skipping unusable ones.

    Upstream occasionally emits a record that cannot be read: broken string escaping
    makes the line invalid JSON, or ``icao`` is missing. One such record must not fail
    a whole build, so they are skipped and counted (the first MAX_MALFORMED_REPORTED
    of them individually logged), while a file holding no records at all, or more than
    MAX_MALFORMED_RATIO of them unreadable, still raises.

    Iterating to exhaustion is what validates the file — a caller that stops early gets
    no check. All three parse functions below consume it fully and therefore skip
    exactly the same records, so a skipped aircraft cannot leave orphaned detail or
    fallback rows behind.

    Attributes:
        total: Non-blank lines read; valid once iteration completes.
        malformed: Records skipped; valid once iteration completes.
    """

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.total = 0
        self.malformed = 0

    def __iter__(self) -> Iterator[dict[str, Any]]:
        self.total = 0
        self.malformed = 0
        with gzip.open(self.file_path, "rt", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                self.total += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._skip(line_number, str(exc))
                    continue
                if not isinstance(record, dict) or not isinstance(record.get("icao"), str):
                    self._skip(line_number, "missing or non-string 'icao'")
                    continue
                yield record
        self._validate()

    def _skip(self, line_number: int, reason: str) -> None:
        """Count a skipped record, logging the first MAX_MALFORMED_REPORTED of them."""
        self.malformed += 1
        if self.malformed <= MAX_MALFORMED_REPORTED:
            logger.warning("Skipping malformed ADS-B Exchange record on line %d: %s", line_number, reason)

    def _validate(self) -> None:
        """Reject a file that is empty or mostly unreadable.

        Raises:
            ValueError: If the file holds no records, or more than MAX_MALFORMED_RATIO
                of them are unusable.
        """
        if self.total == 0:
            raise ValueError(f"ADS-B Exchange file holds no records: {self.file_path}")
        if self.malformed > self.total * MAX_MALFORMED_RATIO:
            raise ValueError(
                f"ADS-B Exchange file is unusable: {self.malformed:,} of {self.total:,} records are "
                f"malformed (limit {MAX_MALFORMED_RATIO:.1%}) — the source format has probably changed"
            )
        if self.malformed:
            logger.warning(
                "Skipped %s malformed ADS-B Exchange record(s) out of %s",
                f"{self.malformed:,}",
                f"{self.total:,}",
            )


def parse_aircraft(file_path: Path) -> tuple[list[Aircraft], int]:
    """Parse gzipped JSON lines into Aircraft records.

    Each line is a JSON object with at least ``icao``, ``reg``, and
    ``icaotype`` fields. Unreadable records are skipped (see _RecordReader).

    Args:
        file_path: Path to the gzipped JSON file.

    Returns:
        List of parsed aircraft records, and the number of records skipped as malformed.

    Raises:
        ValueError: If the file holds no records or is mostly unreadable.
    """
    reader = _RecordReader(file_path)
    aircraft = []
    for record in reader:
        aircraft.append(
            Aircraft(
                aircraft_icao_address=record["icao"].upper(),
                # Registrations containing only '?' characters are placeholders, not real values
                aircraft_registration=reg if (reg := _sanitize(record.get("reg"))) is None or reg.strip("?") else None,
                aircraft_type_code=_sanitize(record.get("icaotype")),
            )
        )
    logger.debug("Parsed %d aircraft from ADS-B Exchange", len(aircraft))
    return aircraft, reader.malformed


def parse_aircraft_details(file_path: Path) -> tuple[list[AircraftDetails], int]:
    """Parse gzipped JSON lines into AircraftDetails records.

    Each line is a JSON object with extended aircraft information
    such as year, manufacturer, model, owner/operator, and flags.
    Unreadable records are skipped (see _RecordReader).

    Args:
        file_path: Path to the gzipped JSON file.

    Returns:
        List of parsed aircraft detail records, and the number of records skipped as
        malformed.

    Raises:
        ValueError: If the file holds no records or is mostly unreadable.
    """
    reader = _RecordReader(file_path)
    details = []
    for record in reader:
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
    return details, reader.malformed


def parse_aircraft_fallbackdata(file_path: Path) -> tuple[list[AircraftFallbackData], int]:
    """Parse gzipped JSON lines into AircraftFallbackData records.

    Extracts manufacturer names as plain-text fallback data for aircraft
    that may not have a normalized manufacturer reference. Unreadable
    records are skipped (see _RecordReader).

    Args:
        file_path: Path to the gzipped JSON file.

    Returns:
        List of parsed aircraft fallback data records, and the number of records
        skipped as malformed.

    Raises:
        ValueError: If the file holds no records or is mostly unreadable.
    """
    reader = _RecordReader(file_path)
    fallback = []
    for record in reader:
        manufacturer = _sanitize(record.get("manufacturer"))
        if manufacturer:
            fallback.append(
                AircraftFallbackData(
                    aircraft_icao_address=record["icao"].upper(),
                    manufacturer=manufacturer,
                )
            )
    logger.debug("Parsed %d aircraft fallback records from ADS-B Exchange", len(fallback))
    return fallback, reader.malformed
