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

from dataclasses import dataclass


@dataclass
class AircraftType:
    """ICAO aircraft type designator with description and wake category."""

    type_code: str
    type_description: str | None = None
    type_icao_class: str | None = None


@dataclass
class Operator:
    """Airline or operator identified by ICAO three-letter designator."""

    operator_icao: str
    operator_name: str | None = None
    operator_country: str | None = None
    operator_callsign: str | None = None


@dataclass
class Aircraft:
    """Individual aircraft identified by ICAO 24-bit hex address."""

    aircraft_icao_address: str
    aircraft_registration: str | None = None
    aircraft_type_code: str | None = None


@dataclass
class AircraftDetails:
    """Extended aircraft information from ADS-B Exchange."""

    aircraft_icao_address: str
    year: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    owner_operator: str | None = None
    faa_pia: bool = False
    faa_ladd: bool = False
    military: bool = False
