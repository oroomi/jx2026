"""SQLite access. One file, data/radar.sqlite. Schema = every radar/schema/*.sql applied in filename order."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("RADAR_DB", ROOT / "data" / "radar.sqlite"))
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    if str(p) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    for f in sorted(SCHEMA_DIR.glob("*.sql")):
        conn.executescript(f.read_text(encoding="utf-8"))
    conn.commit()
