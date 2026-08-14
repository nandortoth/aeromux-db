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
from pathlib import Path

import pytest

from aeromux_db.sources.adsbexchange import parse_aircraft, parse_aircraft_details, parse_aircraft_fallbackdata


# The escaping fault seen upstream: the doubled backslashes end the `ownop` string
# early, so the line is not valid JSON.
MALFORMED_LINE = (
    '{"icao":"7c3c56","reg":"VH-L7C","icaotype":"A319","year":"2002","manufacturer":"AIRBUS",'
    '"model":"A-319","ownop":"UAB \\\\"EXAMPLE OPS\\\\", SOME AIRLINE PTY LTD",'
    '"faa_pia":false,"faa_ladd":false,"short_type":"L2J","mil":false}'
)

# Records placed either side of a bad one, enough that it stays under MAX_MALFORMED_RATIO
FILLER_HALF = 600


def _record(icao: str, **fields: object) -> str:
    """Build one valid JSON-lines record, overriding fields as needed."""
    payload: dict[str, object] = {
        "icao": icao,
        "reg": f"N{icao.upper()}",
        "icaotype": "B738",
        "year": "2015",
        "manufacturer": "BOEING",
        "model": "737-800",
        "ownop": "SOME AIRLINE",
        "faa_pia": False,
        "faa_ladd": False,
        "mil": False,
    }
    payload.update(fields)
    return json.dumps(payload)


def _filler(count: int, start: int = 0) -> list[str]:
    """Build `count` valid records with distinct ICAO addresses."""
    return [_record(f"{0xA00000 + index:06x}") for index in range(start, start + count)]


def _write_gz(tmp_path: Path, lines: list[str]) -> Path:
    """Write JSON lines to a gzipped file and return its path."""
    file_path = tmp_path / "basic-ac-db.json.gz"
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return file_path


def _surround(bad_line: str) -> list[str]:
    """Place a bad record in the middle of a realistically sized run of good ones."""
    return [*_filler(FILLER_HALF), bad_line, "", *_filler(FILLER_HALF, start=FILLER_HALF)]


def test_parse_aircraft_skips_malformed_line_and_keeps_parsing(tmp_path: Path) -> None:
    path = _write_gz(tmp_path, _surround(MALFORMED_LINE))

    aircraft, malformed = parse_aircraft(path)

    assert malformed == 1
    assert len(aircraft) == FILLER_HALF * 2
    addresses = {a.aircraft_icao_address for a in aircraft}
    assert "7C3C56" not in addresses
    # The last record of the file proves parsing resumed after the bad line
    assert f"{0xA00000 + FILLER_HALF * 2 - 1:06X}" in addresses


def test_all_parsers_skip_the_same_record(tmp_path: Path) -> None:
    path = _write_gz(tmp_path, _surround(MALFORMED_LINE))

    aircraft, aircraft_malformed = parse_aircraft(path)
    details, details_malformed = parse_aircraft_details(path)
    fallback, fallback_malformed = parse_aircraft_fallbackdata(path)

    # A skipped aircraft must not leave orphaned detail or fallback rows behind
    assert aircraft_malformed == details_malformed == fallback_malformed == 1
    assert len(aircraft) == len(details) == len(fallback) == FILLER_HALF * 2
    assert "7C3C56" not in {d.aircraft_icao_address for d in details}
    assert "7C3C56" not in {f.aircraft_icao_address for f in fallback}


@pytest.mark.parametrize(
    "bad_line",
    [
        '{"reg":"N12345","icaotype":"B738"}',  # no icao at all
        '{"icao":null,"reg":"N12345"}',  # icao present but null
        '"a bare string, not an object"',  # valid JSON, wrong shape
    ],
)
def test_parse_aircraft_skips_records_without_usable_icao(tmp_path: Path, bad_line: str) -> None:
    path = _write_gz(tmp_path, _surround(bad_line))

    aircraft, malformed = parse_aircraft(path)

    assert malformed == 1
    assert len(aircraft) == FILLER_HALF * 2


def test_parse_aircraft_raises_when_mostly_malformed(tmp_path: Path) -> None:
    lines = [MALFORMED_LINE if index % 2 else _record(f"{0xA00000 + index:06x}") for index in range(10)]
    path = _write_gz(tmp_path, lines)

    with pytest.raises(ValueError, match="unusable"):
        parse_aircraft(path)


def test_parse_aircraft_raises_on_empty_file(tmp_path: Path) -> None:
    path = _write_gz(tmp_path, [""])

    with pytest.raises(ValueError, match="no records"):
        parse_aircraft(path)


def test_parse_aircraft_ignores_blank_lines(tmp_path: Path) -> None:
    path = _write_gz(tmp_path, ["", _record("4d2145"), "", "", _record("a12345"), ""])

    aircraft, malformed = parse_aircraft(path)

    assert malformed == 0
    assert [a.aircraft_icao_address for a in aircraft] == ["4D2145", "A12345"]
