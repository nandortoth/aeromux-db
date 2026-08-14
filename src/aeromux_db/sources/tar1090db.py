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

logger = logging.getLogger(__name__)

SOURCE_URL = "https://github.com/wiedehopf/tar1090-db/archive/refs/heads/master.tar.gz"
SOURCE_FILENAME = "tar1090-db.tar.gz"

_VALID_WTC = frozenset({"L", "M", "H", "J"})

_TYPES_FILENAMES = ("icao_aircraft_types.js", "icao_aircraft_types.json")
_GZIP_MAGIC = b"\x1f\x8b"


def _load_json(path: Path) -> dict:
    """Load JSON from a file that may be gzip-compressed whatever its extension."""
    data = path.read_bytes()
    if data.startswith(_GZIP_MAGIC):
        data = gzip.decompress(data)
    return json.loads(data)


def parse_wtc(extract_dir: Path) -> dict[str, str]:
    """Parse per-type Wake Turbulence Categories from tar1090-db.

    The tarball extracts to a directory containing the ICAO aircraft types file
    (under a single repo-named top-level directory created by the GitHub archive
    endpoint).  That file has had two names upstream — ``icao_aircraft_types.json``
    at the repo root, and ``db/icao_aircraft_types.js``, the same JSON but
    gzip-compressed despite the extension — so both names in _TYPES_FILENAMES are
    accepted and compression is detected by content.  The sibling
    ``icao_aircraft_types2.js`` carries the same types in a different shape and is
    deliberately not matched.  The JSON is a flat object of shape::

        {"A388": {"desc": "L4J", "wtc": "J"}, ...}

    Only the ``wtc`` field is consumed here — ``desc`` overlaps with
    Mictronics's ``type_icao_class`` and is intentionally ignored so
    Mictronics stays the single authority for that column.

    Args:
        extract_dir: Path to the extracted tarball directory.

    Returns:
        Dict mapping ICAO type designator to validated WTC letter.
        Entries whose ``wtc`` value is not one of ``{L, M, H, J}`` are
        dropped (and counted in the log).
    """
    candidates = [match for name in _TYPES_FILENAMES for match in sorted(extract_dir.rglob(name))]
    if not candidates:
        logger.warning("None of %s found under %s", " / ".join(_TYPES_FILENAMES), extract_dir)
        return {}

    raw = _load_json(candidates[0])

    out: dict[str, str] = {}
    dropped = 0
    for type_code, entry in raw.items():
        if not isinstance(entry, dict):
            dropped += 1
            continue
        wtc = entry.get("wtc")
        if isinstance(wtc, str) and wtc in _VALID_WTC:
            out[type_code] = wtc
        else:
            dropped += 1

    logger.debug(
        "Parsed %d WTC entries from tar1090-db (%d dropped)",
        len(out),
        dropped,
    )
    return out
