"""Read side of the radar: every page gets its data through this module. Pure functions over a sqlite3.Connection."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from radar import db as db_mod
from radar import thesis as thesis_mod

# Adapter NAME -> human source name. Anything else falls back to the url host, never a guess.
SOURCE_LABELS = {
    "prh": "PRH/YTJ register",
    "hilma": "Hilma notice",
    "businessfinland": "Business Finland export",
    "cordis": "CORDIS",
    "declared": "declared list",
}
TYPE_LABELS = {
    "register_entry": "New register entry",
    "bf_funding": "Business Finland funding",
    "eu_project": "EU project",
    "blueinvest": "BlueInvest pipeline",
    "patent": "Patent filing",
    "public_contract": "Public contract",
    "job_ad": "Open job ad",
    "site_customer": "Customer on own site",
}
# Wording follows the docstring of radar/emit.py.
CONFIDENCE_RULES = {
    "high": "the source names the company or its business id directly and states the date.",
    "medium": "matched by an exact legal name or website domain, date stated by the source.",
    "low": "matched by name keyword or industry code only; shown, but never counted in rankings.",
}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}
NO_DB_MESSAGE = "no signals yet. Run python3 -m radar.build"


def open_db(path=None, readonly: bool = True, thesis: dict | None = None):
    """Open the radar database. Path defaults to the thesis database (thesis.db_path; env RADAR_DB for the default thesis).
    Read-only returns None when the file does not exist."""
    if path is None:
        path = thesis_mod.db_path(thesis or thesis_mod.load())
    p = Path(path)
    if not readonly:
        return db_mod.connect(p)
    if not p.is_file():
        return None
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


COOKIE = "radar_thesis"


def _requested_thesis(request) -> tuple[str | None, bool]:
    """(thesis id, from_query). Only ids that exist in thesis.available() survive; nothing else is ever used."""
    if request is None:
        return None, False
    av = thesis_mod.available()
    q = request.query_params.get("thesis")
    if q in av:
        return q, True
    c = request.cookies.get(COOKIE)
    if c in av:
        return c, False
    return None, False


def context(request=None):
    """The ONLY way a route gets its thesis and database: `thesis, conn = store.context(request)`.
    The thesis is picked per request (query `thesis`, then cookie `radar_thesis`, then the default); conn is None
    when that thesis has no database yet (show the empty state)."""
    tid, from_query = _requested_thesis(request)
    th = thesis_mod.load(thesis_mod.resolve(tid))
    if request is not None:
        request.state.thesis = th
        if from_query:
            request.state.set_thesis_cookie = th["id"]
    return th, open_db(thesis=th)


def empty_state_text(thesis: dict) -> str:
    return f"no signals yet for {thesis['title']}. Run python3 -m radar.build --thesis {thesis['_path']}"


def _today(today) -> date:
    if today is None:
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(today) if isinstance(today, str) else today


def _window(thesis, today):
    end = _today(today)
    days = thesis["geography"]["feed_window_days"]
    return end - timedelta(days=days), end, days


def rule_text(thesis: dict) -> str:
    days = thesis["geography"]["feed_window_days"]
    return (f"Companies from outside the declared cohort and portfolio whose earliest public signal in the last {days} days "
            f"is shown, newest first. Each company appears once, with that earliest signal and its source link.")


def evidence(row) -> dict:
    r = dict(row)
    adapter = r.get("adapter")
    url = r.get("source_url") or r.get("url")
    label = SOURCE_LABELS.get(adapter)
    if label is None:
        host = urlparse(url or "").netloc
        label = host or "unknown source"
    conf = r.get("confidence")
    return {
        "label": label,
        "event_date": r.get("date"),
        "fetched_at": r.get("fetched_at"),
        "url": url,
        "confidence": conf,
        "confidence_rule": CONFIDENCE_RULES.get(conf),
    }


def _feed_types(thesis, signal_type=None):
    types = list(thesis["feed_signal_types"])
    if signal_type is not None:
        types = [t for t in types if t == signal_type]
    return types


def _in_window_rows(conn, thesis, today, types, group):
    start, end, _ = _window(thesis, today)
    if not types:
        return []
    q = ",".join("?" * len(types))
    sql = f"""SELECT c.company_key, c.name, c.y_tunnus, c.group_tag, c.country,
                     s.id AS signal_id, s.signal_type, s.date, s.confidence, s.detail, s.amount_eur,
                     s.source_url, s.adapter, s.fetched_at
              FROM signals s JOIN companies c USING (company_key)
              WHERE s.signal_type IN ({q}) AND s.date >= ? AND s.date <= ?"""
    args = [*types, start.isoformat(), end.isoformat()]
    if group is not None:
        sql += " AND c.group_tag = ?"
        args.append(group)
    return conn.execute(sql, args).fetchall()


def feed(conn, thesis, *, today=None, signal_type=None, group="feed", limit=500) -> list[dict]:
    """One row per company: its earliest in-window feed signal (ties: confidence, then lowest id), newest first."""
    start, _, _ = _window(thesis, today)
    all_types = _feed_types(thesis)
    rows = _in_window_rows(conn, thesis, today, all_types, group)
    per: dict[str, list] = {}
    for r in rows:
        per.setdefault(r["company_key"], []).append(r)
    out = []
    for key, rs in per.items():
        best = min(rs, key=lambda r: (r["date"], _CONF_ORDER.get(r["confidence"], 3), r["signal_id"]))
        if signal_type is not None and best["signal_type"] != signal_type:
            continue
        q = ",".join("?" * len(all_types))
        earlier = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE company_key=? AND signal_type IN ({q}) AND date < ?",
            [key, *all_types, start.isoformat()]).fetchone()[0]
        d = dict(best)
        d["type_label"] = TYPE_LABELS.get(d["signal_type"], d["signal_type"])
        d["earlier_count"] = earlier
        d["signal_count"] = len(rs)
        d["evidence"] = evidence(d)
        out.append(d)
    out.sort(key=lambda d: (d["date"], d["signal_id"]), reverse=True)
    return out[:limit]


def feed_counts(conn, thesis, *, today=None) -> dict:
    start, end, days = _window(thesis, today)
    types = list(thesis["feed_signal_types"])
    rows = feed(conn, thesis, today=today, limit=10**9)
    by_type = {t: 0 for t in types}
    by_conf = {c: 0 for c in ("high", "medium", "low")}
    for r in rows:
        by_type[r["signal_type"]] = by_type.get(r["signal_type"], 0) + 1
        by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1
    excluded = 0
    future = 0
    if types:
        q = ",".join("?" * len(types))
        excluded = conn.execute(
            f"""SELECT COUNT(DISTINCT c.company_key) FROM signals s JOIN companies c USING (company_key)
                WHERE c.group_tag IN ('cohort','portfolio') AND s.signal_type IN ({q}) AND s.date >= ? AND s.date <= ?""",
            [*types, start.isoformat(), end.isoformat()]).fetchone()[0]
        future = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE signal_type IN ({q}) AND date > ?", [*types, end.isoformat()]).fetchone()[0]
    last = conn.execute("SELECT MAX(fetched_at) FROM signals").fetchone()[0]
    return {"window_start": start.isoformat(), "window_end": end.isoformat(), "window_days": days,
            "companies": len(rows), "by_type": by_type, "by_confidence": by_conf,
            "excluded_declared": excluded, "future_dated": future, "last_fetched": last}


def _fold(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(ch)).casefold()


def search(conn, q, limit=20) -> list[dict]:
    q = _fold((q or "").strip())
    if not q:
        return []
    hits = []
    for r in conn.execute("SELECT * FROM companies ORDER BY name"):
        name, key, yt = _fold(r["name"]), _fold(r["company_key"]), _fold(r["y_tunnus"] or "")
        if q in name or q in key or q in yt:
            hits.append((0 if name.startswith(q) else 1, name, dict(r)))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [h[2] for h in hits[:limit]]


def company(conn, key) -> dict | None:
    row = conn.execute("SELECT * FROM companies WHERE company_key = ?", (key,)).fetchone()
    if row is None:
        return None
    sigs = []
    for s in conn.execute("SELECT * FROM signals WHERE company_key = ? ORDER BY date DESC, id DESC", (key,)):
        d = dict(s)
        d["type_label"] = TYPE_LABELS.get(d["signal_type"], d["signal_type"])
        d["evidence"] = evidence(d)
        sigs.append(d)
    by_type: dict[str, int] = {}
    for s in sigs:
        by_type[s["signal_type"]] = by_type.get(s["signal_type"], 0) + 1
    return {"company": dict(row), "signals": sigs,
            "counts": {"signals": len(sigs), "by_type": by_type,
                       "first_signal": sigs[-1]["date"] if sigs else None,
                       "last_signal": sigs[0]["date"] if sigs else None}}


def cohort_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM companies WHERE group_tag = 'cohort'").fetchone()[0]


def _main(argv) -> int:
    if len(argv) < 2 or argv[1] not in ("feed", "company"):
        print("usage: python3 -m radar.store feed | company <key>")
        return 2
    conn = open_db()
    if conn is None:
        print(NO_DB_MESSAGE)
        return 1
    th = thesis_mod.load()
    if argv[1] == "feed":
        print(rule_text(th))
        print(json.dumps(feed_counts(conn, th), indent=2))
        for r in feed(conn, th, limit=20):
            print(f"{r['date']}  {r['confidence']:<6} {r['type_label']:<26} {r['name']} [{r['company_key']}]  {r['source_url']}")
    else:
        if len(argv) < 3:
            print("usage: python3 -m radar.store company <key>")
            return 2
        c = company(conn, argv[2])
        if c is None:
            print("no such company")
            return 1
        print(json.dumps(c["company"], indent=2, ensure_ascii=False))
        print(json.dumps(c["counts"], indent=2))
        for s in c["signals"]:
            print(f"{s['date']}  {s['confidence']:<6} {s['type_label']:<26} {s['source_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
