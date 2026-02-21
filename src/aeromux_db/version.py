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

from datetime import datetime, timezone


def get_db_version(release: int = 1) -> str:
    """Build a calendar-based database version string.

    Format: ``YYYY.Q.wWW_rR`` where *YYYY* is the year, *Q* is the
    quarter (1–4), *WW* is the ISO 8601 week number (zero-padded), and
    *R* is the release number within that week.

    Args:
        release: Release number for the current week (default 1).

    Returns:
        Version string, e.g. ``2026.1.w08_r1``.
    """
    today = datetime.now(timezone.utc).date()
    year = today.year
    quarter = (today.month - 1) // 3 + 1
    week = today.isocalendar()[1]
    return f"{year}.{quarter}.w{week:02d}_r{release}"
