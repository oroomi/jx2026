"""Names the person-name redactor must leave alone (D23): every company in the store, in any spelling the store holds, and the
organisations on the thesis's declared lists. Read-only; the base index is cached per database file version.

  known_names(conn, thesis, company_key)  the index for one page: the base plus that company's own names, always protected

A name enters `radar.fit.NameIndex` from:
  companies.name                          every company in the store (cohort, portfolio, ecosystem and feed companies always protected;
                                          a register-intake name that could be a person's only when its legal-form word stands beside it)
  field_candidates (field = name)         the other names sources give THIS company: a former name (SNOWSUS OY for Viva Jets Oy), a trade name
  thesis `matching` lists                 the declared investor, buyer and programme names (data/declared/*.csv)
"""
from __future__ import annotations

import csv
import sqlite3
import threading
from pathlib import Path

from radar import fit

ROOT = Path(__file__).resolve().parent.parent
CURATED_TAGS = ("cohort", "portfolio", "ecosystem", "feed")  # declared by the programme, the dataset or the feed: companies the radar itself shows.
# "intake" (16,385 register names, mostly unreviewed) is the one tag that is not: see fit.NameIndex for how its person-shaped names are held
_cache: dict[tuple, fit.NameIndex] = {}
_lock = threading.Lock()


def _db_stamp(conn: sqlite3.Connection) -> tuple | None:
    """(path, modification time) of the database file, or None for a database with no file (never cached)."""
    try:
        path = conn.execute("PRAGMA database_list").fetchone()[2]
        return (path, Path(path).stat().st_mtime_ns) if path else None
    except Exception:  # noqa: BLE001
        return None


def declared_names(thesis: dict) -> list[str]:
    """The `name` column of every CSV the thesis's `matching` section lists (investors, corporates, programmes)."""
    out: list[str] = []
    for rel in (thesis.get("matching") or {}).values():
        if isinstance(rel, str) and rel.endswith(".csv") and (ROOT / rel).is_file():
            with (ROOT / rel).open(encoding="utf-8", newline="") as f:
                out += [r["name"].strip() for r in csv.DictReader(f) if (r.get("name") or "").strip()]
    return out


def _base(conn: sqlite3.Connection, thesis: dict) -> fit.NameIndex:
    idx = fit.NameIndex()
    for name, tag in conn.execute("SELECT name, group_tag FROM companies"):
        idx.add(name, thesis, always=tag in CURATED_TAGS)
    for name in declared_names(thesis):
        idx.add(name, thesis, always=True)
    return idx


def company_names(conn: sqlite3.Connection, company_key: str) -> list[str]:
    """Every name the store holds for one company: the applied legal name and each name a source gave it."""
    names = [r[0] for r in conn.execute("SELECT name FROM companies WHERE company_key=?", (company_key,))]
    try:
        names += [r[0] for r in conn.execute("SELECT DISTINCT value FROM field_candidates WHERE company_key=? AND field='name'", (company_key,))]
    except sqlite3.OperationalError:  # a store without the candidates table
        pass
    return [n for n in names if n]


def known_names(conn: sqlite3.Connection, thesis: dict, company_key: str | None = None) -> fit.NameIndex:
    """The names to protect on the page of `company_key` (or everywhere, when None)."""
    stamp = _db_stamp(conn)
    key = (stamp, thesis.get("id"))
    with _lock:
        base = _cache.get(key) if stamp else None
    if base is None:
        base = _base(conn, thesis)
        if stamp:
            with _lock:
                _cache.clear() if len(_cache) > 6 else None
                _cache[key] = base
    return base.with_names(company_names(conn, company_key), thesis) if company_key else base
