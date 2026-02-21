-- Aeromux Database Builder
-- Copyright (C) 2025-2026 Nandor Toth <dev@nandortoth.com>
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program. If not, see <https://www.gnu.org/licenses/>.

CREATE TABLE types (
    type_code TEXT PRIMARY KEY,
    type_description TEXT,
    type_icao_class TEXT
);

CREATE TABLE operators (
    operator_icao TEXT PRIMARY KEY,
    operator_name TEXT,
    operator_country TEXT,
    operator_callsign TEXT
);

CREATE TABLE aircrafts (
    aircraft_icao_address TEXT PRIMARY KEY,
    aircraft_registration TEXT,
    aircraft_type_code TEXT REFERENCES types(type_code)
);

CREATE TABLE aircraft_details (
    aircraft_icao_address TEXT PRIMARY KEY REFERENCES aircrafts(aircraft_icao_address),
    year TEXT,
    manufacturer TEXT,
    model TEXT,
    owner_operator TEXT,
    faa_pia INTEGER,
    faa_ladd INTEGER,
    military INTEGER
);

CREATE VIEW aircraft_view AS
SELECT
    a.aircraft_icao_address,
    a.aircraft_registration,
    a.aircraft_type_code,
    t.type_description,
    t.type_icao_class,
    d.year,
    d.manufacturer,
    d.model,
    d.owner_operator,
    d.faa_pia,
    d.faa_ladd,
    d.military
FROM aircrafts a
LEFT JOIN types t ON a.aircraft_type_code = t.type_code
LEFT JOIN aircraft_details d ON a.aircraft_icao_address = d.aircraft_icao_address;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
