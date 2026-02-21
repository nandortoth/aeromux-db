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
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aeromux_db import __version__
from aeromux_db.models import (
    Aircraft,
    AircraftDetails,
    AircraftFallbackData,
    AircraftType,
    Manufacturer,
    OpenSkyAircraftData,
    Operator,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"


@dataclass
class BuildResult:
    """Result of a database build operation."""

    path: Path
    total_aircraft: int

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schema" / "schema.sql"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

_FAA_N_RE = re.compile(r"^N[0-9]{1,5}[A-Z]{0,2}$")
_IATA_RE = re.compile(r"^[A-Z0-9]{1,4}-[A-Z0-9]{1,4}$")


def _resolve_registration(
    mic: str | None, adsbx: str | None, opensky: str | None,
) -> tuple[str, str, str]:
    """Pick the winning registration from up to three sources.

    Returns (value, source_name, reason).
    """
    candidates: list[tuple[str, str]] = []
    if mic:
        candidates.append((mic, "mictronics"))
    if adsbx:
        candidates.append((adsbx, "adsbx"))
    if opensky:
        candidates.append((opensky, "opensky"))

    if len(candidates) <= 1:
        val, src = candidates[0] if candidates else ("", "none")
        return val, src, "only_value"

    # Rule 1: majority (2+ agree)
    counts = Counter(v for v, _ in candidates)
    majority = [v for v, c in counts.items() if c >= 2]
    if majority:
        winner_val = majority[0]
        priority = {"adsbx": 3, "opensky": 2, "mictronics": 1}
        winner_src = max(
            (s for v, s in candidates if v == winner_val),
            key=lambda s: priority[s],
        )
        return winner_val, winner_src, "majority"

    # Rule 2: FAA N-number (unique match only)
    faa = [(v, s) for v, s in candidates if _FAA_N_RE.match(v)]
    if len(faa) == 1:
        return faa[0][0], faa[0][1], "faa_n_number"

    # Rule 3: IATA-style XX-YY pattern (unique match only)
    iata = [(v, s) for v, s in candidates if _IATA_RE.match(v)]
    if len(iata) == 1:
        return iata[0][0], iata[0][1], "iata_pattern"

    # Rule 4: has dash (unique match only)
    dash = [(v, s) for v, s in candidates if "-" in v]
    if len(dash) == 1:
        return dash[0][0], dash[0][1], "has_dash"

    # Rule 5: default priority opensky > adsbx > mictronics
    default = {"opensky": 3, "adsbx": 2, "mictronics": 1}
    winner = max(candidates, key=lambda c: default[c[1]])
    return winner[0], winner[1], "default_priority"


def build_database(
    aircraft: list[Aircraft],
    types: list[AircraftType],
    operators: list[Operator],
    adsbx_aircraft: list[Aircraft] | None = None,
    aircraft_details: list[AircraftDetails] | None = None,
    aircraft_fallbackdata: list[AircraftFallbackData] | None = None,
    manufacturers: list[Manufacturer] | None = None,
    opensky_operator_iata: dict[str, str] | None = None,
    opensky_aircraft: list[OpenSkyAircraftData] | None = None,
) -> BuildResult:
    """Build the SQLite database and return the output path.

    Insert parsed aircraft, type, and operator records into a SQLite
    database with schema versioning and build metadata.  When ADS-B
    Exchange data is provided, merge additional aircraft into the table
    and populate the aircraft_details table.  When OpenSky Network data
    is provided, enrich existing aircraft with additional metadata.

    Args:
        aircraft: Parsed aircraft records with ICAO 24-bit addresses.
        types: Parsed aircraft type records keyed by ICAO type designator.
        operators: Parsed operator records keyed by ICAO airline designator.
        adsbx_aircraft: ADS-B Exchange aircraft records to merge after
            the primary source.
        aircraft_details: Extended aircraft detail records from ADS-B
            Exchange.
        aircraft_fallbackdata: Fallback manufacturer data from ADS-B
            Exchange.
        manufacturers: Manufacturer records from OpenSky Network.
        opensky_operator_iata: Mapping of operator ICAO to IATA codes
            from OpenSky Network.
        opensky_aircraft: Aircraft enrichment data from OpenSky Network.

    Returns:
        BuildResult with path and total aircraft count.

    Raises:
        sqlite3.OperationalError: When the schema file is missing or invalid.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACTS_DIR / f"aeromux-db_{__version__}.sqlite"

    if output_path.exists():
        output_path.unlink()

    logger.debug("Creating database at %s", output_path)

    conn = sqlite3.connect(str(output_path))
    try:
        conn.execute("PRAGMA encoding = 'UTF-8'")

        schema_sql = SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)

        logger.debug("Inserting %d types", len(types))
        conn.executemany(
            "INSERT INTO types (type_code, type_description, type_icao_class) VALUES (?, ?, ?)",
            [(t.type_code, t.type_description, t.type_icao_class) for t in types],
        )

        logger.debug("Inserting %d operators", len(operators))
        conn.executemany(
            "INSERT INTO operators (operator_icao, operator_name, operator_iata, operator_country, operator_callsign) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (o.operator_icao, o.operator_name, o.operator_iata, o.operator_country, o.operator_callsign)
                for o in operators
            ],
        )

        logger.debug("Inserting %d aircraft", len(aircraft))
        conn.executemany(
            "INSERT INTO aircrafts "
            "(aircraft_icao_address, aircraft_registration, aircraft_country, aircraft_serial_number, "
            "aircraft_type_code, aircraft_manufacturer_icao, aircraft_operator_icao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    a.aircraft_icao_address, a.aircraft_registration, a.aircraft_country,
                    a.aircraft_serial_number, a.aircraft_type_code,
                    a.aircraft_manufacturer_icao, a.aircraft_operator_icao,
                )
                for a in aircraft
            ],
        )

        # Merge ADS-B Exchange aircraft
        total_aircraft = len(aircraft)
        mictronics_regs: dict[str, str | None] = {
            row[0]: row[1]
            for row in conn.execute("SELECT aircraft_icao_address, aircraft_registration FROM aircrafts")
        }
        adsbx_regs: dict[str, str | None] = {
            a.aircraft_icao_address: a.aircraft_registration
            for a in (adsbx_aircraft or [])
        }
        reg_mismatches: dict[str, tuple[str | None, str | None, str | None]] = {}
        adsbx_mismatch_count = 0
        opensky_mismatch_count = 0
        if adsbx_aircraft:
            new_aircraft = []
            for a in adsbx_aircraft:
                if a.aircraft_icao_address in mictronics_regs:
                    existing_reg = mictronics_regs[a.aircraft_icao_address]
                    if a.aircraft_registration and existing_reg and a.aircraft_registration != existing_reg:
                        reg_mismatches[a.aircraft_icao_address] = (existing_reg, a.aircraft_registration, None)
                        adsbx_mismatch_count += 1
                    elif a.aircraft_registration and not existing_reg:
                        conn.execute(
                            "UPDATE aircrafts SET aircraft_registration = ? "
                            "WHERE aircraft_icao_address = ? AND aircraft_registration IS NULL",
                            (a.aircraft_registration, a.aircraft_icao_address),
                        )
                else:
                    new_aircraft.append(a)

            if new_aircraft:
                logger.debug("Inserting %d new aircraft from ADS-B Exchange", len(new_aircraft))
                conn.executemany(
                    "INSERT INTO aircrafts "
                    "(aircraft_icao_address, aircraft_registration, aircraft_country, aircraft_serial_number, "
                    "aircraft_type_code, aircraft_manufacturer_icao, aircraft_operator_icao) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            a.aircraft_icao_address, a.aircraft_registration, a.aircraft_country,
                            a.aircraft_serial_number, a.aircraft_type_code,
                            a.aircraft_manufacturer_icao, a.aircraft_operator_icao,
                        )
                        for a in new_aircraft
                    ],
                )

            total_aircraft += len(new_aircraft)

            logger.info(
                "  ADS-B Exchange merge: %s new aircraft, %s registration mismatches",
                f"{len(new_aircraft):,}",
                f"{adsbx_mismatch_count:,}",
            )

        # Insert aircraft details
        if aircraft_details:
            logger.debug("Inserting %d aircraft details", len(aircraft_details))
            conn.executemany(
                "INSERT INTO aircraft_details "
                "(aircraft_icao_address, year, model, owner_operator, faa_pia, faa_ladd, military) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        d.aircraft_icao_address,
                        d.year,
                        d.model,
                        d.owner_operator,
                        int(d.faa_pia),
                        int(d.faa_ladd),
                        int(d.military),
                    )
                    for d in aircraft_details
                ],
            )

        # Insert aircraft fallback data
        if aircraft_fallbackdata:
            logger.debug("Inserting %d aircraft fallback records", len(aircraft_fallbackdata))
            conn.executemany(
                "INSERT INTO aircraft_fallbackdata (aircraft_icao_address, manufacturer, operator) "
                "VALUES (?, ?, ?)",
                [
                    (f.aircraft_icao_address, f.manufacturer, f.operator)
                    for f in aircraft_fallbackdata
                ],
            )

        # Insert manufacturers from OpenSky
        if manufacturers:
            logger.debug("Inserting %d manufacturers", len(manufacturers))
            conn.executemany(
                "INSERT INTO manufacturers (manufacturer_icao, manufacturer_name) VALUES (?, ?)",
                [(m.manufacturer_icao, m.manufacturer_name) for m in manufacturers],
            )

        # Enrich operators with IATA codes from OpenSky
        if opensky_operator_iata:
            updated = 0
            for icao, iata in opensky_operator_iata.items():
                cursor = conn.execute(
                    "UPDATE operators SET operator_iata = ? "
                    "WHERE operator_icao = ? AND operator_iata IS NULL",
                    (iata, icao),
                )
                updated += cursor.rowcount
            logger.info("  OpenSky: enriched %s operators with IATA codes", f"{updated:,}")

        # Enrich aircraft from OpenSky
        if opensky_aircraft:
            existing_with_reg = {
                row[0]: row[1]
                for row in conn.execute("SELECT aircraft_icao_address, aircraft_registration FROM aircrafts")
            }

            enriched = 0
            seen: set[str] = set()
            for oa in opensky_aircraft:
                if oa.icao24 not in existing_with_reg or oa.icao24 in seen:
                    continue
                seen.add(oa.icao24)

                enriched += 1

                # Update country and serial number (always)
                conn.execute(
                    "UPDATE aircrafts SET aircraft_country = ?, aircraft_serial_number = ? "
                    "WHERE aircraft_icao_address = ?",
                    (oa.country, oa.serial_number, oa.icao24),
                )

                # Update registration if currently null, track mismatches
                if oa.registration:
                    existing_reg = existing_with_reg[oa.icao24]
                    if existing_reg and oa.registration != existing_reg:
                        opensky_mismatch_count += 1
                        if oa.icao24 in reg_mismatches:
                            prev = reg_mismatches[oa.icao24]
                            reg_mismatches[oa.icao24] = (prev[0], prev[1], oa.registration)
                        else:
                            reg_mismatches[oa.icao24] = (
                                mictronics_regs.get(oa.icao24),
                                adsbx_regs.get(oa.icao24),
                                oa.registration,
                            )
                    else:
                        conn.execute(
                            "UPDATE aircrafts SET aircraft_registration = ? "
                            "WHERE aircraft_icao_address = ? AND aircraft_registration IS NULL",
                            (oa.registration, oa.icao24),
                        )

                # Operator: reference or fallback
                if oa.operator_icao:
                    conn.execute(
                        "UPDATE aircrafts SET aircraft_operator_icao = ? "
                        "WHERE aircraft_icao_address = ?",
                        (oa.operator_icao, oa.icao24),
                    )
                elif oa.operator:
                    conn.execute(
                        "INSERT INTO aircraft_fallbackdata (aircraft_icao_address, operator) "
                        "VALUES (?, ?) "
                        "ON CONFLICT(aircraft_icao_address) DO UPDATE SET operator = ?",
                        (oa.icao24, oa.operator, oa.operator),
                    )

                # Owner enrichment
                if oa.owner:
                    conn.execute(
                        "UPDATE aircraft_details SET owner_operator = ? "
                        "WHERE aircraft_icao_address = ? AND owner_operator IS NULL",
                        (oa.owner, oa.icao24),
                    )

                # Model enrichment
                if oa.model:
                    conn.execute(
                        "UPDATE aircraft_details SET model = ? "
                        "WHERE aircraft_icao_address = ? AND model IS NULL",
                        (oa.model, oa.icao24),
                    )

                # Manufacturer: reference or fallback
                if oa.manufacturer_icao:
                    conn.execute(
                        "UPDATE aircrafts SET aircraft_manufacturer_icao = ? "
                        "WHERE aircraft_icao_address = ?",
                        (oa.manufacturer_icao, oa.icao24),
                    )
                elif oa.manufacturer_name:
                    conn.execute(
                        "INSERT INTO aircraft_fallbackdata (aircraft_icao_address, manufacturer) "
                        "VALUES (?, ?) "
                        "ON CONFLICT(aircraft_icao_address) DO UPDATE SET manufacturer = ?",
                        (oa.icao24, oa.manufacturer_name, oa.manufacturer_name),
                    )

            logger.info(
                "  OpenSky: enriched %s aircraft, %s registration mismatches",
                f"{enriched:,}",
                f"{opensky_mismatch_count:,}",
            )

        # Resolve registration mismatches and update the database
        if reg_mismatches:
            resolved: dict[str, tuple[str | None, str | None, str | None, str, str]] = {}
            for icao, (mic_reg, adsbx_r, osky_reg) in reg_mismatches.items():
                winner_val, winner_src, reason = _resolve_registration(mic_reg, adsbx_r, osky_reg)
                resolved[icao] = (mic_reg, adsbx_r, osky_reg, winner_src, reason)
                conn.execute(
                    "UPDATE aircrafts SET aircraft_registration = ? WHERE aircraft_icao_address = ?",
                    (winner_val, icao),
                )

            mismatch_path = ARTIFACTS_DIR / "reg_conflicts_resolutions.csv"
            with open(mismatch_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["icao_address", "mictronics_reg", "adsbx_reg", "opensky_reg", "selected_source", "reason"])
                for icao, (mic_reg, adsbx_reg, osky_reg, sel_src, reason) in resolved.items():
                    writer.writerow([icao, mic_reg or "", adsbx_reg or "", osky_reg or "", sel_src, reason])
            logger.info(
                "  Registration mismatches: %s total (adsbx: %s, opensky: %s)",
                f"{len(reg_mismatches):,}",
                f"{adsbx_mismatch_count:,}",
                f"{opensky_mismatch_count:,}",
            )
            logger.info(
                "    Wrote to %s",
                mismatch_path.relative_to(PROJECT_ROOT),
            )

        logger.debug("Writing metadata")
        build_timestamp = datetime.now(timezone.utc).isoformat()
        metadata = [
            ("build_timestamp", build_timestamp),
            ("tool_version", __version__),
            ("schema_version", SCHEMA_VERSION),
            ("record_count", str(total_aircraft)),
        ]
        conn.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            metadata,
        )

        conn.commit()
    finally:
        conn.close()

    logger.debug("Database built successfully: %s", output_path)
    return BuildResult(path=output_path, total_aircraft=total_aircraft)
