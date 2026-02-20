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

CREATE TABLE aircraft (
    icao_address TEXT PRIMARY KEY,
    registration TEXT,
    type_code TEXT REFERENCES types(type_code)
);

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
