"""OpenAlex co-publications (free API, CC0): research output that names the company in an author's affiliation.

Only cohort, portfolio and ecosystem companies are looked up: a name search over every register hit gives false matches.
A work counts only if a raw affiliation string contains the company's folded legal name as whole words; the API's own
fuzzy search is never trusted. Founders' personal names are never searched. One request per second.
"""
from __future__ import annotations

import os
import re
import sqlite3
import unicodedata

from radar import emit
from radar.adapters._fetch import Blocked, cached_get

NAME = "openalex"
PHASE = 2
API = "https://api.openalex.org/works"
GROUPS = ("cohort", "portfolio", "ecosystem")
MIN_NAME_CHARS = 5
MAX_CONSECUTIVE_FAILURES = 3
_LEGAL = re.compile(r"\b(oy|oyj|ab|as|asa|a/s|aps|ltd|limited|gmbh|inc|llc|bv|sa|plc|ky|tmi)\b", re.I)


def fold(text: str) -> str:
    """Lower case, accents removed, anything but letters and digits as single spaces."""
    t = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def core_name(name: str) -> str:
    """Folded name without the legal-form suffix; '' when too short to be a safe match."""
    core = re.sub(r"\s+", " ", _LEGAL.sub(" ", fold(name))).strip()
    return core if len(core) >= MIN_NAME_CHARS else ""


def affiliation_matches(core: str, work: dict) -> bool:
    """True when a raw affiliation string of the work contains the folded name as whole words."""
    if not core:
        return False
    pat = re.compile(r"(?<![a-z0-9])" + re.escape(core) + r"(?![a-z0-9])")
    for a in work.get("authorships") or []:
        for raw in a.get("raw_affiliation_strings") or []:
            if pat.search(fold(raw)):
                return True
    return False


def work_signal(work: dict) -> tuple[str, str, str, str] | None:
    """(date, url, title, venue) of a work, or None when the date or id is missing."""
    day, url = work.get("publication_date"), work.get("id")
    if not day or not url or not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        return None
    venue = ((work.get("primary_location") or {}).get("source") or {}).get("display_name")
    return day, url, (work.get("title") or "title not stated").strip(), venue or "venue not stated"


def run(conn: sqlite3.Connection, thesis: dict) -> dict:
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "blocked": 0}
    rows = conn.execute(f"SELECT company_key, name FROM companies WHERE group_tag IN ({','.join('?' * len(GROUPS))}) ORDER BY name",
                        GROUPS).fetchall()
    mailto = os.environ.get("OPENALEX_MAILTO")  # optional polite-pool address; never stored in the repo
    failures = 0
    for r in rows:
        core = core_name(r["name"])
        if not core:
            stats["skipped"] += 1
            continue
        params = {"filter": f"raw_affiliation_strings.search:{core}", "per-page": "50",
                  "select": "id,publication_date,title,primary_location,authorships"}
        if mailto:
            params["mailto"] = mailto
        try:
            data, net = cached_get(NAME, API, interval=1.0, params=params)
        except Blocked:
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES:
                stats["blocked"] = 1
                break
            continue
        failures = 0
        stats["requests"] += net
        stats["companies"] += 1
        for w in data.get("results", []):
            if not affiliation_matches(core, w):
                continue
            s = work_signal(w)
            if s is None:
                continue
            day, url, title, venue = s
            stats["signals"] += emit.emit_signal(
                conn, company_key=r["company_key"], signal_type="research_output", date=day, source_url=url, confidence="medium",
                adapter=NAME, detail=f"{title} ({venue}); an author affiliation names '{r['name']}'.")
    stats["skipped"] = len(rows) - stats["companies"]
    return stats


if __name__ == "__main__":
    from radar import db
    print(run(db.connect(), {}))
