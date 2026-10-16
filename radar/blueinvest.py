"""Read helper for the BlueInvest profile of a company. Returns None when there is no table or no row."""
from __future__ import annotations

import sqlite3


def profile_for(conn: sqlite3.Connection, company_key: str) -> dict | None:
    try:
        row = conn.execute(
            "SELECT * FROM blueinvest_profiles WHERE company_key=? ORDER BY profile_id LIMIT 1", (company_key,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    cols = [d[0] for d in conn.execute("SELECT * FROM blueinvest_profiles LIMIT 0").description]
    return dict(zip(cols, row))
