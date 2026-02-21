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
    operator_iata TEXT,
    operator_country TEXT,
    operator_callsign TEXT
);

CREATE TABLE manufacturers (
    manufacturer_icao TEXT PRIMARY KEY,
    manufacturer_name TEXT
);

CREATE TABLE aircrafts (
    aircraft_icao_address TEXT PRIMARY KEY,
    aircraft_registration TEXT,
    aircraft_country TEXT,
    aircraft_serial_number TEXT,
    aircraft_type_code TEXT REFERENCES types(type_code),
    aircraft_manufacturer_icao TEXT REFERENCES manufacturers(manufacturer_icao),
    aircraft_operator_icao TEXT REFERENCES operators(operator_icao)
);

CREATE TABLE aircraft_details (
    aircraft_icao_address TEXT PRIMARY KEY REFERENCES aircrafts(aircraft_icao_address),
    year TEXT,
    model TEXT,
    owner_operator TEXT,
    faa_pia INTEGER,
    faa_ladd INTEGER,
    military INTEGER
);

CREATE TABLE aircraft_fallbackdata (
    aircraft_icao_address TEXT PRIMARY KEY REFERENCES aircrafts(aircraft_icao_address),
    manufacturer TEXT,
    operator TEXT
);

CREATE VIEW aircraft_view AS
SELECT
    a.aircraft_icao_address,
    a.aircraft_registration,
    a.aircraft_country,
    a.aircraft_serial_number,
    a.aircraft_type_code,
    t.type_description,
    t.type_icao_class,
    a.aircraft_manufacturer_icao,
    CASE WHEN a.aircraft_manufacturer_icao IS NOT NULL THEN m.manufacturer_name ELSE f.manufacturer END AS manufacturer_name,
    a.aircraft_operator_icao,
    CASE WHEN a.aircraft_operator_icao IS NOT NULL THEN o.operator_name ELSE f.operator END AS operator_name,
    o.operator_iata,
    o.operator_country,
    o.operator_callsign,
    d.year,
    d.model,
    d.owner_operator,
    d.faa_pia,
    d.faa_ladd,
    d.military
FROM aircrafts a
LEFT JOIN types t ON a.aircraft_type_code = t.type_code
LEFT JOIN manufacturers m ON a.aircraft_manufacturer_icao = m.manufacturer_icao
LEFT JOIN operators o ON a.aircraft_operator_icao = o.operator_icao
LEFT JOIN aircraft_details d ON a.aircraft_icao_address = d.aircraft_icao_address
LEFT JOIN aircraft_fallbackdata f ON a.aircraft_icao_address = f.aircraft_icao_address;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
