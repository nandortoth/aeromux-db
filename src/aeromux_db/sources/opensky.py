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
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

from aeromux_db.models import Manufacturer, OpenSkyAircraftData

logger = logging.getLogger(__name__)

csv.field_size_limit(sys.maxsize)

S3_LISTING_URL = "https://s3.opensky-network.org/data-samples?list-type=2&prefix=metadata/"
DOWNLOAD_BASE_URL = "https://opensky-network.org/datasets/metadata/"

_FILENAME_PATTERN = re.compile(r"aircraft-database-complete-(\d{4}-\d{2})\.csv")
_UNKNOWN_PATTERN = re.compile(r"unknown", re.IGNORECASE)


def _to_str(value: str | None) -> str | None:
    """Return None for empty strings, otherwise the stripped value."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def resolve_latest_filename(listing_xml: str) -> str:
    """Parse S3 listing XML and return the latest aircraft-database-complete CSV filename.

    Args:
        listing_xml: Raw XML text from the S3 listing endpoint.

    Returns:
        Filename of the latest complete database CSV.

    Raises:
        ValueError: When no matching files are found in the listing.
    """
    root = ElementTree.fromstring(listing_xml)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

    matches: list[tuple[str, str]] = []
    for contents in root.findall("s3:Contents", ns):
        key_elem = contents.find("s3:Key", ns)
        if key_elem is None or key_elem.text is None:
            continue
        filename = key_elem.text.split("/")[-1]
        match = _FILENAME_PATTERN.match(filename)
        if match:
            matches.append((match.group(1), filename))

    if not matches:
        raise ValueError("No aircraft-database-complete CSV files found in S3 listing")

    matches.sort(key=lambda x: x[0])
    latest = matches[-1][1]
    logger.debug("Resolved latest OpenSky file: %s", latest)
    return latest


def parse_manufacturers(file_path: Path) -> list[Manufacturer]:
    """Parse CSV and extract unique manufacturers with ICAO codes.

    Args:
        file_path: Path to the OpenSky CSV file.

    Returns:
        List of unique manufacturer records.
    """
    manufacturers: dict[str, Manufacturer] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, quotechar="'")
        for row in reader:
            icao = _to_str(row.get("manufacturerIcao"))
            if icao is None:
                continue
            name = _to_str(row.get("manufacturerName"))
            if icao in manufacturers:
                if name and manufacturers[icao].manufacturer_name != name:
                    manufacturers[icao].manufacturer_name = name
            else:
                manufacturers[icao] = Manufacturer(
                    manufacturer_icao=icao,
                    manufacturer_name=name,
                )
    logger.debug("Parsed %d manufacturers from OpenSky", len(manufacturers))
    return list(manufacturers.values())


def parse_operator_iata(file_path: Path) -> dict[str, str]:
    """Parse CSV and extract operator ICAO to IATA mappings.

    Args:
        file_path: Path to the OpenSky CSV file.

    Returns:
        Dictionary mapping operator ICAO codes to IATA codes.
    """
    mappings: dict[str, str] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, quotechar="'")
        for row in reader:
            icao = _to_str(row.get("operatorIcao"))
            iata = _to_str(row.get("operatorIata"))
            if icao and iata and icao not in mappings:
                mappings[icao] = iata
    logger.debug("Parsed %d operator IATA mappings from OpenSky", len(mappings))
    return mappings


def parse_aircraft_enrichment(file_path: Path) -> list[OpenSkyAircraftData]:
    """Parse CSV and extract aircraft enrichment data.

    Args:
        file_path: Path to the OpenSky CSV file.

    Returns:
        List of aircraft enrichment records.
    """
    enrichment = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, quotechar="'")
        for row in reader:
            icao24 = _to_str(row.get("icao24"))
            if icao24 is None:
                continue

            model = _to_str(row.get("model"))
            if model and _UNKNOWN_PATTERN.search(model):
                model = None

            enrichment.append(
                OpenSkyAircraftData(
                    icao24=icao24.upper(),
                    registration=_to_str(row.get("registration")),
                    country=_to_str(row.get("country")),
                    serial_number=_to_str(row.get("serialNumber")),
                    model=model,
                    manufacturer_icao=_to_str(row.get("manufacturerIcao")),
                    manufacturer_name=_to_str(row.get("manufacturerName")),
                    operator_icao=_to_str(row.get("operatorIcao")),
                    operator=_to_str(row.get("operator")),
                    owner=_to_str(row.get("owner")),
                )
            )
    logger.debug("Parsed %d aircraft enrichment records from OpenSky", len(enrichment))
    return enrichment
