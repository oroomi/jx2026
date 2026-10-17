"""SQLite access. One file, data/radar.sqlite. Schema = every radar/schema/*.sql applied in filename order."""
from __future__ import annotations

import os
import re
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


_ADD_COLUMN = re.compile(r"^(?:\s*--[^\n]*\n)*\s*ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)\b", re.I)


def init_schema(conn: sqlite3.Connection) -> None:
    for f in sorted(SCHEMA_DIR.glob("*.sql")):
        _apply(conn, f.read_text(encoding="utf-8"))
    conn.commit()


def _apply(conn: sqlite3.Connection, sql: str) -> None:
    """Run one schema file. Every file is applied at every start, so it must be idempotent: CREATE ... IF NOT EXISTS is, and
    ALTER TABLE ... ADD COLUMN (no IF NOT EXISTS in SQLite) is made so here by skipping it when the column is already there."""
    if "add column" not in sql.lower():
        conn.executescript(sql)
        return
    buf = ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if not sqlite3.complete_statement(buf):
            continue
        m = _ADD_COLUMN.match(buf)
        have = {r[1].lower() for r in conn.execute(f"PRAGMA table_info({m.group(1)})")} if m else set()
        if not (m and m.group(2).lower() in have):
            conn.executescript(buf)
        buf = ""
    if buf.strip():
        conn.executescript(buf)
