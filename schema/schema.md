# Aeromux Database Schema

This document describes the SQLite database schema used by Aeromux. The authoritative schema definition is in `schema.sql`.

## Tables

### `types`

Aircraft type lookup table.

| Column | Type | Description |
|---|---|---|
| `type_code` | TEXT (PK) | Aircraft type designator (e.g. `A320`, `B738`). |
| `type_description` | TEXT | Human-readable type name (e.g. `Airbus A320`). |
| `type_icao_class` | TEXT | ICAO aircraft classification code (e.g. `L2J`). |

### `operators`

Operator lookup table.

| Column | Type | Description |
|---|---|---|
| `operator_icao` | TEXT (PK) | ICAO operator code (e.g. `DLH`, `BAW`). |
| `operator_name` | TEXT | Operator name (e.g. `Lufthansa`). |
| `operator_country` | TEXT | Country of the operator. |
| `operator_callsign` | TEXT | Radio callsign (e.g. `LUFTHANSA`). |

### `aircraft`

One row per aircraft, keyed by ICAO 24-bit address.

| Column | Type | Description |
|---|---|---|
| `icao_address` | TEXT (PK) | ICAO 24-bit address in uppercase hexadecimal (e.g. `3C6753`). |
| `registration` | TEXT | Aircraft registration (e.g. `D-AIZZ`). |
| `type_code` | TEXT (FK) | References `types.type_code`. |

### `metadata`

Build metadata key-value pairs.

| Column | Type | Description |
|---|---|---|
| `key` | TEXT (PK) | Metadata key. |
| `value` | TEXT | Metadata value. |

**Standard metadata keys:**

| Key | Description |
|---|---|
| `build_timestamp` | ISO 8601 UTC timestamp of when the database was generated. |
| `tool_version` | Version of the db-builder tool that produced the database. |
| `schema_version` | Database schema version for compatibility checks. |
| `record_count` | Total number of aircraft records in the database. |

## Relationships

- `aircraft.type_code` references `types.type_code`.
