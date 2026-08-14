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
import shutil
from pathlib import Path

from aeromux_db.sources.tar1090db import parse_wtc


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tar1090db"

EXPECTED_WTC = {"A388": "J", "B748": "H", "C172": "L", "B738": "M"}

# The shape used by the sibling icao_aircraft_types2.js, which must not be picked up
TYPES2_CONTENT = {"A388": ["AIRBUS A-380", "L4J", "J"], "B738": ["BOEING 737-800", "L2J", "M"]}


def _gzipped_types_file(tmp_path: Path) -> Path:
    """Write the fixture as a gzipped .js, the layout upstream switched to."""
    db_dir = tmp_path / "tar1090-db-master" / "db"
    db_dir.mkdir(parents=True)
    raw = (FIXTURE_DIR / "icao_aircraft_types.json").read_bytes()
    (db_dir / "icao_aircraft_types.js").write_bytes(gzip.compress(raw))
    return db_dir


def test_parse_wtc_keeps_valid_letters_and_drops_invalid() -> None:
    result = parse_wtc(FIXTURE_DIR)

    assert result == EXPECTED_WTC
    assert "BADX" not in result  # invalid WTC letter
    assert "BADY" not in result  # empty string
    assert "BADZ" not in result  # missing wtc field


def test_parse_wtc_reads_the_gzipped_js_file(tmp_path: Path) -> None:
    _gzipped_types_file(tmp_path)

    assert parse_wtc(tmp_path) == EXPECTED_WTC


def test_parse_wtc_ignores_the_types2_file(tmp_path: Path) -> None:
    db_dir = _gzipped_types_file(tmp_path)
    (db_dir / "icao_aircraft_types2.js").write_bytes(gzip.compress(json.dumps(TYPES2_CONTENT).encode()))

    assert parse_wtc(tmp_path) == EXPECTED_WTC


def test_parse_wtc_still_reads_a_plain_json_file(tmp_path: Path) -> None:
    shutil.copy(FIXTURE_DIR / "icao_aircraft_types.json", tmp_path / "icao_aircraft_types.json")

    assert parse_wtc(tmp_path) == EXPECTED_WTC


def test_parse_wtc_missing_file_returns_empty(tmp_path: Path) -> None:
    assert parse_wtc(tmp_path) == {}
