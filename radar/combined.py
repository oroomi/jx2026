"""The combined database: the declared ecosystem file (data/declared/ecosystem/blue_economy_fi.sqlite, Amir's) with the radar's
public-record tables appended beside it, so one SQLite file answers "what public record does the radar hold for each entity
of the dataset".

    python3 -m radar.combined --thesis <thesis id> [--out data/combined/<thesis id>_combined.sqlite]

What happens, in order:
  1. The ecosystem file is copied byte for byte to <out>.building. Every one of its tables (the `person` table included) and
     views arrive unchanged; this module never edits, drops or re-creates any of them. Row counts and a content digest per table
     are compared with the source before and after the append, and the run stops when they differ.
  2. The thesis store is read through a read-only connection and copied to a scratch file (sqlite backup), which gets the
     current schema applied. The live store is never written.
  3. Tables with the `radar_` prefix are appended: radar_companies, radar_signals, radar_readiness (the levels
     frameworks.page_levels gives the company page), radar_verdicts (radar.memo.build), radar_ocean_impact (the Ocean Impact Assessment from the same memo), radar_briefs, radar_meta. The view
     v_entity_public_record joins the dataset's entities to radar_companies by Finnish business id (entity.business_id).
  4. Companies only: nothing from the `person` table is joined, copied or exported. Before the file is moved into place a guard
     scans every text column of every radar_ table for the people's names and the run stops on a hit.
  5. <out>.building is renamed to <out> (atomic), so a reader never sees a half-built file.

The output is for the team only (it carries the person table unchanged). radar_meta says so."""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from radar import blueinvest, db as db_mod, frameworks, memo, store
from radar import thesis as thesis_mod
from radar.adapters.ecosystem import DB_PATH as ECO_PATH

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "combined"
VIEW = "v_entity_public_record"
PROGRESS_EVERY = 2000
TEAM_ONLY = ("Team use only, not for publication or redistribution. This file carries the ecosystem dataset's person table "
             "unchanged, as the dataset's owner built it. No radar_ table and no view reads, joins or copies that table.")

# The company page's readiness levels (frameworks.page_levels) -> the table dimension. The one dimension in frameworks.LABELS that
# has no numeric level is the category reading.
LEVEL_FIELD = {"technology": "trl", "business": "brl", "investment": "irl"}
CATEGORY_DIM = next(k for k in frameworks.LABELS if k not in LEVEL_FIELD)

SCHEMA = f"""
CREATE TABLE radar_companies (
  company_key     TEXT PRIMARY KEY,     -- the store's key: Finnish business id when known, else a register slug
  business_id     TEXT,                 -- Finnish business id (Y-tunnus) as the register states it, NULL when none
  name            TEXT NOT NULL,
  town            TEXT,                 -- post office name of the registered address, NULL when the register states none
  country         TEXT,
  founded         TEXT,
  industry_code   TEXT,
  industry_desc   TEXT,
  group_tag       TEXT NOT NULL,
  register_status TEXT,
  website         TEXT,
  source_url      TEXT NOT NULL,        -- the register page a human opens to check the row
  town_source_url TEXT,
  fetched_at      TEXT NOT NULL
);
CREATE INDEX radar_companies_business_id ON radar_companies(business_id);
CREATE TABLE radar_signals (
  signal_id      INTEGER PRIMARY KEY,   -- signals.id in the store
  company_key    TEXT NOT NULL REFERENCES radar_companies(company_key),
  signal_type    TEXT NOT NULL,
  date           TEXT NOT NULL,         -- the event date, not the fetch date
  date_precision TEXT NOT NULL,         -- day | year (a year-only date is stored as 1 January)
  confidence     TEXT NOT NULL,         -- high | medium | low
  source_url     TEXT NOT NULL,
  adapter        TEXT NOT NULL,
  detail         TEXT,
  amount_eur     REAL,
  fetched_at     TEXT NOT NULL
);
CREATE INDEX radar_signals_company ON radar_signals(company_key);
CREATE INDEX radar_signals_type ON radar_signals(signal_type);
CREATE TABLE radar_readiness (
  company_key  TEXT NOT NULL REFERENCES radar_companies(company_key),
  dimension    TEXT NOT NULL,           -- {", ".join(frameworks.LABELS)}
  framework    TEXT NOT NULL,           -- the framework label the company page prints
  level        INTEGER,                 -- 1 to 9; NULL = no public evidence (never a zero)
  category     TEXT,                    -- only for {CATEGORY_DIM}: the category the rule found
  rule         TEXT,                    -- the printed rule that gave the level or category
  evidence_url TEXT,                    -- latest dated evidence record behind it
  evidence_n   INTEGER NOT NULL,        -- how many records back it
  PRIMARY KEY (company_key, dimension)
);
CREATE TABLE radar_verdicts (
  company_key      TEXT PRIMARY KEY REFERENCES radar_companies(company_key),
  decision         TEXT,                -- one of radar.memo.DECISIONS; NULL only when the build failed (see error)
  row_id           TEXT,                -- the decision-table row or rule that matched, NULL when none did
  matched          TEXT,                -- the matched row in words, e.g. "row 3, H/M/L/H"
  kind             TEXT,                -- row | rule | fallback
  table_action     TEXT,
  team_label       TEXT,
  because          TEXT,                -- the four bands in table order
  band_impact      TEXT,
  band_business    TEXT,
  band_investment  TEXT,
  band_fit         TEXT,
  band_technology  TEXT,
  note             TEXT,
  needs            TEXT,                -- JSON list: what public evidence is missing
  fallback_blocked INTEGER,
  as_of            TEXT,
  error            TEXT
);
CREATE TABLE radar_ocean_impact (       -- radar.ocean_impact.assess: evidence readiness from public records (D22), not true impact
  company_key       TEXT PRIMARY KEY REFERENCES radar_companies(company_key),
  area              TEXT,                 -- the impact area in words, NULL when no record names one
  area_basis        TEXT,                 -- own text | corroborated name word | industry code family
  level             INTEGER,              -- 1..level_max, NULL when no rung applies
  level_max         INTEGER NOT NULL,
  level_rule        TEXT NOT NULL,        -- the rung that fired, in words
  band              TEXT,                 -- Low | Medium | High, NULL with the level
  confidence        TEXT NOT NULL,        -- high | medium | low
  confidence_reason TEXT NOT NULL,
  raise_text        TEXT NOT NULL,        -- the one public record that would raise the level or the confidence
  scalability_text  TEXT NOT NULL,        -- "not assessed from public records" when no record shows a wider market
  scalability_basis TEXT,
  evidence_json     TEXT NOT NULL         -- JSON list of {{text, date, source_label, url, family}}
);
CREATE TABLE radar_briefs (
  company_key TEXT PRIMARY KEY REFERENCES radar_companies(company_key),
  written     TEXT NOT NULL,
  slots_json  TEXT NOT NULL,            -- the verified brief slots, JSON text, as the store holds them
  imported_at TEXT NOT NULL
);
CREATE TABLE radar_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# The Finnish business id of an entity in the form the store keeps it (7 digits, dash, check digit); anything else is not joined.
_BID = """CASE WHEN trim(business_id) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9]' THEN trim(business_id)
                 WHEN trim(business_id) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
                      THEN substr(trim(business_id), 1, 7) || '-' || substr(trim(business_id), 8, 1) END"""

VIEW_SQL = f"""
CREATE VIEW {VIEW} AS
WITH ent AS (
  SELECT id, name, entity_type, side, business_id, city, status, {_BID} AS join_business_id FROM entity
), sig AS (
  SELECT company_key, COUNT(*) AS n_signals, COUNT(DISTINCT signal_type) AS n_signal_types, MIN(date) AS first_signal,
         MAX(date) AS last_signal, group_concat(DISTINCT signal_type) AS signal_types
  FROM radar_signals GROUP BY company_key
), lv AS (
  SELECT company_key,
         MAX(CASE WHEN dimension = 'technology' THEN level END) AS technology_level,
         MAX(CASE WHEN dimension = 'business' THEN level END) AS business_level,
         MAX(CASE WHEN dimension = 'investment' THEN level END) AS investment_level,
         MAX(CASE WHEN dimension = '{CATEGORY_DIM}' THEN category END) AS category
  FROM radar_readiness GROUP BY company_key
)
SELECT e.id AS entity_id, e.name AS entity_name, e.entity_type, e.side, e.business_id AS entity_business_id,
       e.join_business_id, e.city AS entity_city, e.status AS entity_status,
       rc.company_key AS radar_company_key, rc.name AS radar_name, rc.town AS radar_town, rc.country AS radar_country,
       rc.founded AS radar_founded, rc.industry_code AS radar_industry_code, rc.industry_desc AS radar_industry_desc,
       rc.group_tag AS radar_group_tag, rc.register_status AS radar_register_status, rc.source_url AS radar_register_url,
       COALESCE(sig.n_signals, 0) AS n_signals, COALESCE(sig.n_signal_types, 0) AS n_signal_types,
       sig.first_signal, sig.last_signal, sig.signal_types,
       lv.technology_level, lv.business_level, lv.investment_level, lv.category AS radar_category,
       v.decision AS radar_decision, v.matched AS radar_decision_row, v.note AS radar_decision_note,
       oi.area AS radar_ocean_area, oi.level AS radar_ocean_level, oi.band AS radar_ocean_band, oi.confidence AS radar_ocean_confidence,
       (b.company_key IS NOT NULL) AS has_brief
FROM ent e
LEFT JOIN radar_companies rc ON rc.company_key = (SELECT MIN(r.company_key) FROM radar_companies r WHERE r.business_id = e.join_business_id)
LEFT JOIN sig ON sig.company_key = rc.company_key
LEFT JOIN lv ON lv.company_key = rc.company_key
LEFT JOIN radar_verdicts v ON v.company_key = rc.company_key
LEFT JOIN radar_ocean_impact oi ON oi.company_key = rc.company_key
LEFT JOIN radar_briefs b ON b.company_key = rc.company_key
ORDER BY e.id
"""


def _say(msg: str) -> None:
    print(msg, flush=True)


# ---- helpers ------------------------------------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _ro(path: Path, immutable: bool = False) -> sqlite3.Connection:
    """A read-only connection. immutable=1 also skips the -shm/-wal side files, for a file that nobody is writing."""
    conn = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro" + ("&immutable=1" if immutable else ""), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _digests(conn: sqlite3.Connection) -> dict[str, tuple[int, str]]:
    """{table: (row count, sha256 of every row in rowid order)} for each table of the file."""
    out = {}
    for t in _tables(conn):
        h, n = hashlib.sha256(), 0
        try:
            rows = conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid')
        except sqlite3.OperationalError:  # WITHOUT ROWID
            rows = iter(sorted(conn.execute(f'SELECT * FROM "{t}"'), key=repr))
        for r in rows:
            h.update(repr(tuple(r)).encode("utf-8"))
            n += 1
        out[t] = (n, h.hexdigest())
    return out


@contextmanager
def _memoised_partner_checks():
    """radar.memo.build asks store.is_partner_org about every EU-project partner in the store for every company, and each answer
    re-folds the same 70 partner names (about 40 minutes for 17,000 companies). Both functions are pure over the partner lists,
    so the answers are cached for the length of this run and the original functions are put back afterwards. Same output."""
    orig = (store.name_key, store.is_partner_org)
    store.name_key = functools.lru_cache(maxsize=None)(orig[0])
    store.is_partner_org = functools.lru_cache(maxsize=None)(orig[1])
    try:
        yield
    finally:
        store.name_key, store.is_partner_org = orig


def _evidence_url(lv: dict) -> str | None:
    """The latest dated evidence record behind a level, else the first evidence link (the rule radar.memo uses)."""
    ev = lv.get("evidence") or []
    dated = [e for e in ev if e.get("date")]
    if dated:
        return max(dated, key=lambda s: s["date"])["source_url"]
    return next(((e.get("evidence") or {}).get("url") for e in ev if (e.get("evidence") or {}).get("url")), None)


# ---- readers: store -> rows -----------------------------------------------------------------------------------------
def company_rows(conn: sqlite3.Connection):
    cols = ("company_key", "y_tunnus", "name", "town", "country", "founded", "industry_code", "industry_desc", "group_tag",
            "register_status", "website", "source_url", "town_source_url", "fetched_at")
    for r in conn.execute(f"SELECT {', '.join(cols)} FROM companies ORDER BY company_key"):
        yield tuple(r)


def signal_rows(conn: sqlite3.Connection):
    yield from (tuple(r) for r in conn.execute(
        """SELECT s.id, s.company_key, s.signal_type, s.date, COALESCE(m.date_precision, 'day'), s.confidence, s.source_url, s.adapter,
                  s.detail, s.amount_eur, s.fetched_at
           FROM signals s LEFT JOIN signal_meta m ON m.signal_id = s.id ORDER BY s.id"""))


def readiness_rows(conn: sqlite3.Connection, key: str) -> list[tuple]:
    """Four rows for one company, from frameworks.page_levels: the function the company page and the memo bands read."""
    data = store.company(conn, key)
    c, sigs = data["company"], data["signals"]
    fw = frameworks.page_levels(c, sigs, blueinvest.profile_for(conn, key))
    out = []
    for dim, field in LEVEL_FIELD.items():
        lv = fw[field]
        out.append((key, dim, fw["labels"][dim], lv["level"], None, lv["because"], _evidence_url(lv), len(lv["evidence"] or [])))
    cat = fw["category"]
    if cat.get("category"):
        ev = cat.get("evidence") or {}
        url = ev.get("url") or (c.get("source_url") if cat.get("industry") else None)
        rule = f"keyword '{cat['keyword']}' in " + ("the register industry text" if cat.get("industry") else "a record's text")
        out.append((key, CATEGORY_DIM, fw["labels"][CATEGORY_DIM], None, cat["category"], rule, url, 1 if url else 0))
    else:
        out.append((key, CATEGORY_DIM, fw["labels"][CATEGORY_DIM], None, None, None, None, 0))
    return out


def memo_rows(conn: sqlite3.Connection, thesis: dict, key: str) -> tuple[tuple, tuple | None]:
    """(the radar_verdicts row, the radar_ocean_impact row or None) from one memo.build."""
    try:
        m = memo.build(conn, thesis, key)
    except Exception as e:  # noqa: BLE001  (one bad company must not lose the other 17,000; the row says what happened)
        return (key,) + (None,) * 16 + (f"memo build failed: {type(e).__name__}: {e}",), None
    rec, lv = m["recommendation"], m["levels"]
    v = (key, rec["decision"], None if rec["row_id"] is None else str(rec["row_id"]), rec["matched"], rec["kind"], rec["table_action"],
         rec["team_label"], rec["because"], lv["impact"]["band"], lv["business"]["band"], lv["investment"]["band"], lv["fit"]["band"],
         lv["technology"]["band"], rec.get("note"), json.dumps(rec["needs"], ensure_ascii=False),
         int(bool(rec["fallback_blocked"])), m["as_of"], None)
    oi = m.get("ocean_impact")
    if oi is None:
        return v, None
    return v, (key, oi["area"], oi["area_basis"], oi["level"], oi["level_max"], oi["level_rule"], oi["band"], oi["confidence"],
               oi["confidence_reason"], oi["raise"], oi["scalability"]["text"], oi["scalability"]["basis"],
               json.dumps(oi["evidence"], ensure_ascii=False))


def verdict_row(conn: sqlite3.Connection, thesis: dict, key: str) -> tuple:
    return memo_rows(conn, thesis, key)[0]


def brief_rows(conn: sqlite3.Connection):
    try:
        yield from (tuple(r) for r in conn.execute("SELECT company_key, written, slots_json, imported_at FROM company_brief_slots ORDER BY company_key"))
    except sqlite3.OperationalError:
        return


# ---- the guard ---------------------------------------------------------------------------------------------------
def person_names(eco: sqlite3.Connection) -> list[str]:
    """The names in the dataset's person table, folded, only to be looked for. They are never written anywhere."""
    try:
        rows = eco.execute("SELECT name FROM person").fetchall()
    except sqlite3.OperationalError:
        return []
    return sorted({" ".join(r[0].split()).casefold() for r in rows if r[0] and len(r[0].split()) >= 2})


def person_guard(out: sqlite3.Connection, names: list[str]) -> list[str]:
    """['radar_signals.detail', ...]: every text column of a radar_ table in which one of the names occurs. Empty = clean."""
    hits = []
    for t in (t for t in _tables(out) if t.startswith("radar_")):
        for _, col, typ, *_ in out.execute(f'PRAGMA table_info("{t}")'):
            if typ.upper() != "TEXT":
                continue
            blob = "\n".join(v.casefold() for (v,) in out.execute(f'SELECT "{col}" FROM "{t}" WHERE "{col}" IS NOT NULL'))
            if any(n in blob for n in names):
                hits.append(f"{t}.{col}")
    return hits


# ---- the build ---------------------------------------------------------------------------------------------------
def _scratch_copy(store_path: Path, dest: Path) -> None:
    """A consistent copy of the store (sqlite backup, read-only source) with the current schema applied, so an older store reads too."""
    src = _ro(store_path)
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    db_mod.connect(dest).close()


def _copy_dataset(eco_path: Path, dest: Path) -> str:
    """Byte-for-byte file copy. With a non-empty -wal beside the source a plain copy would miss rows, so the backup API is used then."""
    wal = Path(str(eco_path) + "-wal")
    if wal.is_file() and wal.stat().st_size > 0:
        src = _ro(eco_path)
        try:
            dst = sqlite3.connect(str(dest))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        return "sqlite backup (the source had a non-empty -wal file)"
    shutil.copyfile(eco_path, dest)
    return "file copy"


def _coverage(out: sqlite3.Connection) -> dict:
    one = lambda q: out.execute(q).fetchone()[0]  # noqa: E731
    q = f"SELECT {{}} FROM {VIEW}"
    cov = {"entities": one(q.format("COUNT(*)")), "with_finnish_business_id": one(q.format("COUNT(join_business_id)")),
           "matched": one(q.format("COUNT(radar_company_key)")), "matched_radar_companies": one(q.format("COUNT(DISTINCT radar_company_key)")),
           "matched_with_signals": one(q.format("SUM(n_signals > 0)")) or 0}
    cov["without_finnish_business_id"] = cov["entities"] - cov["with_finnish_business_id"]
    cov["id_not_in_store"] = cov["with_finnish_business_id"] - cov["matched"]
    cov["signals_on_matched_companies"] = one(f"SELECT COUNT(*) FROM radar_signals WHERE company_key IN (SELECT radar_company_key FROM {VIEW})")
    cov["signals_in_store"] = one("SELECT COUNT(*) FROM radar_signals")
    cov["by_side"] = {r[0] or "none": {"entities": r[1], "matched": r[2]} for r in
                      out.execute(f"SELECT side, COUNT(*), COUNT(radar_company_key) FROM {VIEW} GROUP BY side ORDER BY side")}
    return cov


def run(thesis_id: str, out_path: Path | str | None = None, *, store_path: Path | str | None = None,
        eco_path: Path | str | None = None, progress=_say) -> dict:
    """Build the combined file and return a summary {out, bytes, counts, coverage, ...}. Raises ValueError for a bad request."""
    av = thesis_mod.available()
    if thesis_id not in av:
        raise ValueError(f"unknown thesis id {thesis_id!r}; available: {', '.join(sorted(av))}")
    thesis = thesis_mod.load(av[thesis_id])
    store_path = Path(store_path) if store_path else thesis_mod.db_path(thesis)
    eco_path = Path(eco_path) if eco_path else Path(ECO_PATH)
    out_path = Path(out_path) if out_path else OUT_DIR / f"{thesis_id}_combined.sqlite"
    if not store_path.is_file():
        raise ValueError(f"no store for thesis {thesis_id} at {store_path}; run python3 -m radar.build first")
    if not eco_path.is_file():
        raise ValueError(f"ecosystem dataset not found at {eco_path}")
    out_path = out_path.resolve()
    for p in (store_path, eco_path):
        if out_path == p.resolve():
            raise ValueError(f"--out must not be {p}: that file is read only here")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    building = out_path.with_name(out_path.name + ".building")
    sidecars = [Path(str(building) + s) for s in ("", "-wal", "-shm", "-journal")]
    for p in sidecars:
        p.unlink(missing_ok=True)

    t0 = time.time()
    out = None
    try:
        # 1. the dataset, unchanged
        method = _copy_dataset(eco_path, building)
        eco = _ro(eco_path, immutable=True)
        try:
            src_digests = _digests(eco)
            names = person_names(eco)
        finally:
            eco.close()
        out = sqlite3.connect(str(building))
        before = _digests(out)
        if before != src_digests:
            raise RuntimeError("the copy of the ecosystem dataset differs from its source; nothing written")
        if any(t.startswith("radar_") for t in before) or VIEW in {r[0] for r in out.execute("SELECT name FROM sqlite_master")}:
            raise RuntimeError("the ecosystem dataset already has radar_ objects; it is not the file this module expects")

        # 2. the store, read once
        with tempfile.TemporaryDirectory(prefix="combined_") as tmp:
            scratch = Path(tmp) / "store.sqlite"
            _scratch_copy(store_path, scratch)
            conn = db_mod.connect(scratch)
            try:
                out.executescript(SCHEMA)
                out.executemany("INSERT INTO radar_companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", company_rows(conn))
                out.executemany("INSERT INTO radar_signals VALUES (?,?,?,?,?,?,?,?,?,?,?)", signal_rows(conn))
                out.executemany("INSERT INTO radar_briefs VALUES (?,?,?,?)", brief_rows(conn))
                keys = [r[0] for r in conn.execute("SELECT company_key FROM companies ORDER BY company_key")]
                progress(f"companies {len(keys)}, signals {out.execute('SELECT COUNT(*) FROM radar_signals').fetchone()[0]}; building readiness and memo verdicts")
                errors = []
                with _memoised_partner_checks():
                    for i, key in enumerate(keys, 1):
                        out.executemany("INSERT INTO radar_readiness VALUES (?,?,?,?,?,?,?,?)", readiness_rows(conn, key))
                        v, oi_row = memo_rows(conn, thesis, key)
                        out.execute("INSERT INTO radar_verdicts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", v)
                        if oi_row:
                            out.execute("INSERT INTO radar_ocean_impact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", oi_row)
                        if v[-1]:
                            errors.append(f"{key}: {v[-1]}")
                        if i % PROGRESS_EVERY == 0 or i == len(keys):
                            progress(f"memo {i}/{len(keys)} rows, {time.time() - t0:.0f} s")
                linked = None
                try:  # the store's own import of the dataset (by name or id), for the coverage note only
                    linked = {r[0] for r in conn.execute("SELECT entity_id FROM eco_entity WHERE company_key IS NOT NULL")}
                except sqlite3.OperationalError:
                    pass
            finally:
                conn.close()

        # 3. the view, the coverage, the guard
        out.executescript(VIEW_SQL)
        cov = _coverage(out)
        if linked is not None:
            joined = {r[0] for r in out.execute(f"SELECT entity_id FROM {VIEW} WHERE radar_company_key IS NOT NULL")}
            cov["linked_by_store_import_not_by_business_id"] = len(linked - joined)
        hits = person_guard(out, names)
        if hits:
            raise RuntimeError("a name from the person table occurs in " + ", ".join(hits) + "; nothing written")
        out.commit()

        # 4. the meta table
        counts = {t: out.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                  ("radar_companies", "radar_signals", "radar_readiness", "radar_verdicts", "radar_ocean_impact", "radar_briefs")}
        st = store_path.stat()
        meta = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "thesis_id": thesis["id"],
                "thesis_file": thesis["_path"], "source_store_path": str(store_path.resolve()), "source_store_bytes": str(st.st_size),
                "source_store_modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "ecosystem_source_path": str(eco_path), "ecosystem_source_sha256": _sha256(eco_path), "ecosystem_copy_method": method,
                "ecosystem_tables": json.dumps({t: n for t, (n, _) in sorted(before.items())}),
                "ecosystem_tables_unchanged": "row counts and content digests equal before and after the append",
                "git_sha": _git("rev-parse", "HEAD") or "unknown", "git_dirty": "yes" if _git("status", "--porcelain") else "no",
                "command": f"python3 -m radar.combined --thesis {thesis['id']}", "memo_errors": str(len(errors)),
                "person_guard": f"passed: {len(names)} names looked for in every text column of every radar_ table, none found",
                "audience": TEAM_ONLY, "join": f"{VIEW}: entity.business_id = radar_companies.business_id (Finnish business ids only)",
                "coverage": json.dumps(cov, ensure_ascii=False, sort_keys=True)}
        meta.update({f"rows_{t}": str(n) for t, n in counts.items()})
        out.executemany("INSERT INTO radar_meta VALUES (?,?)", meta.items())
        out.commit()

        # 5. the dataset's own tables must be exactly as they arrived
        after = {t: d for t, d in _digests(out).items() if not t.startswith("radar_")}
        if after != before:
            raise RuntimeError("an ecosystem dataset table changed during the append; nothing written")
        if out.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("integrity_check failed on the combined file; nothing written")
        counts["radar_meta"] = out.execute("SELECT COUNT(*) FROM radar_meta").fetchone()[0]
        out.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        out.close()
        out = None
        for p in sidecars[1:]:  # a clean close removes the -wal and -shm files; anything left would be unwritten data
            if p.exists():
                if p.stat().st_size:
                    raise RuntimeError(f"{p.name} still holds data after the checkpoint; nothing written")
                p.unlink()
        os.replace(building, out_path)
    except BaseException:
        if out is not None:
            out.close()
        for p in sidecars:
            p.unlink(missing_ok=True)
        raise
    return {"out": str(out_path), "bytes": out_path.stat().st_size, "counts": counts, "coverage": cov, "memo_errors": errors,
            "ecosystem_tables": {t: n for t, (n, _) in before.items()}, "seconds": round(time.time() - t0)}


def report(res: dict) -> str:
    c, cov = res["counts"], res["coverage"]
    lines = [f"wrote {res['out']} ({res['bytes'] / 1e6:.1f} MB, {res['seconds']} s)", "appended tables:"]
    lines += [f"  {t}: {n:,}" for t, n in c.items()]
    lines.append(f"ecosystem dataset tables carried unchanged: {len(res['ecosystem_tables'])} ({sum(res['ecosystem_tables'].values()):,} rows)")
    lines += [f"join coverage ({VIEW}, by Finnish business id):",
              f"  {cov['entities']} entities; {cov['with_finnish_business_id']} carry a Finnish business id, {cov['without_finnish_business_id']} do not",
              f"  {cov['matched']} entities have a radar row ({cov['matched_radar_companies']} distinct radar companies); "
              f"{cov['id_not_in_store']} ids are not in the store",
              f"  {cov['matched_with_signals']} of the matched entities have at least one signal; "
              f"{cov['signals_on_matched_companies']:,} signals land on them (the store holds {cov['signals_in_store']:,})"]
    lines += [f"  side {s}: {v['matched']} of {v['entities']} matched" for s, v in cov["by_side"].items()]
    if "linked_by_store_import_not_by_business_id" in cov:
        lines.append(f"  {cov['linked_by_store_import_not_by_business_id']} more entities are linked by the store's own import of the dataset "
                     "(by name), not joined here")
    if res["memo_errors"]:
        lines.append(f"memo build failed for {len(res['memo_errors'])} companies (error column of radar_verdicts); first: {res['memo_errors'][0]}")
    lines.append("team use only: the file carries the dataset's person table unchanged; nothing from it is joined or copied into radar_ tables")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.combined", description="Append the radar's public-record tables to a copy of the ecosystem dataset.")
    ap.add_argument("--thesis", help="thesis id (default: the default thesis)")
    ap.add_argument("--out", help="output file (default: data/combined/<thesis id>_combined.sqlite)")
    a = ap.parse_args(argv)
    try:
        tid = a.thesis or thesis_mod.load()["id"]
        res = run(tid, a.out)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    print(report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
