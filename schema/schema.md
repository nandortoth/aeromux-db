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

### `aircrafts`

One row per aircraft, keyed by ICAO 24-bit address.

| Column | Type | Description |
|---|---|---|
| `aircraft_icao_address` | TEXT (PK) | ICAO 24-bit address in uppercase hexadecimal (e.g. `3C6753`). |
| `aircraft_registration` | TEXT | Aircraft registration (e.g. `D-AIZZ`). |
| `aircraft_type_code` | TEXT (FK) | References `types.type_code`. |

### `aircraft_details`

Extended aircraft information from ADS-B Exchange, linked to the `aircrafts` table.

| Column | Type | Description |
|---|---|---|
| `aircraft_icao_address` | TEXT (PK, FK) | ICAO 24-bit address. References `aircrafts.aircraft_icao_address`. |
| `year` | TEXT | Year of manufacture. |
| `manufacturer` | TEXT | Aircraft manufacturer name. |
| `model` | TEXT | Full aircraft model name (e.g. `Boeing 777-36N`). |
| `owner_operator` | TEXT | Owner or operator name. |
| `faa_pia` | INTEGER | FAA Privacy ICAO Address flag (0 or 1). |
| `faa_ladd` | INTEGER | FAA Limiting Aircraft Data Displayed flag (0 or 1). |
| `military` | INTEGER | Military aircraft flag (0 or 1). |

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

## Views

### `aircraft_view`

Consolidated view of all aircraft information. Joins `aircrafts`, `types`, and `aircraft_details` using LEFT JOINs so columns from missing related records appear as NULL.

| Column | Source | Description |
|---|---|---|
| `aircraft_icao_address` | `aircrafts` | ICAO 24-bit address. |
| `aircraft_registration` | `aircrafts` | Aircraft registration. |
| `aircraft_type_code` | `aircrafts` | ICAO type designator. |
| `type_description` | `types` | Human-readable type name. |
| `type_icao_class` | `types` | ICAO aircraft classification code. |
| `year` | `aircraft_details` | Year of manufacture. |
| `manufacturer` | `aircraft_details` | Aircraft manufacturer name. |
| `model` | `aircraft_details` | Full aircraft model name. |
| `owner_operator` | `aircraft_details` | Owner or operator name. |
| `faa_pia` | `aircraft_details` | FAA Privacy ICAO Address flag. |
| `faa_ladd` | `aircraft_details` | FAA Limiting Aircraft Data Displayed flag. |
| `military` | `aircraft_details` | Military aircraft flag. |

**Example query:**

```sql
SELECT * FROM aircraft_view WHERE aircraft_icao_address = '406590';
```

## Relationships

- `aircrafts.aircraft_type_code` references `types.type_code`.
- `aircraft_details.aircraft_icao_address` references `aircrafts.aircraft_icao_address`.
