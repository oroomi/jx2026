"""Web archive (Wayback CDX, free): the first archived capture of a company's website and of milestone pages.

website_first_seen   earliest 200 capture of the domain
website_milestone    earliest capture of a URL whose path has a milestone word (customers, careers, pricing ...)
Honest limit: the archive misses small sites, so absence is never a signal. Source URL = the archived capture.
"""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import urlparse

from radar import emit
from radar.adapters._fetch import Blocked, cached_get

NAME = "webarchive"
PHASE = 2
CDX = "https://web.archive.org/cdx/search/cdx"
MILESTONES = ("customers", "asiakkaat", "references", "referenssit", "cases", "careers", "rekry", "jobs", "pricing", "hinnat")
NOT_A_COMPANY_SITE = ("linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "github.com")
MAX_CAPTURES = 5000
MAX_CONSECUTIVE_FAILURES = 2


def domain_of(website: str | None) -> str | None:
    """Bare host of a company website, or None for an empty value or a social profile."""
    if not website:
        return None
    host = (urlparse(website if "//" in website else "//" + website).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    if not host or "." not in host or any(host == d or host.endswith("." + d) for d in NOT_A_COMPANY_SITE):
        return None
    return host


def _day(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def archive_url(ts: str, original: str) -> str:
    return f"https://web.archive.org/web/{ts}/{original}"


def milestone_word(original: str) -> str | None:
    """The milestone word found in a URL path segment (whole word between separators), else None."""
    path = urlparse(original).path.lower()
    parts = set(re.split(r"[^a-z0-9]+", path))
    return next((m for m in MILESTONES if m in parts), None)


def captures(rows: list) -> list[tuple[str, str]]:
    """CDX json rows (first row is the header) to [(timestamp, original)], 200 captures only."""
    if not rows or rows[0][:2] != ["timestamp", "original"]:
        return []
    return [(r[0], r[1]) for r in rows[1:] if len(r) >= 3 and r[2] == "200" and re.match(r"^\d{14}$", r[0])]


def derive(caps: list[tuple[str, str]]) -> list[tuple[str, str, str, str]]:
    """[(signal_type, date, archived_url, detail)]: one first_seen, and the first capture per milestone word."""
    if not caps:
        return []
    first_ts, first_url = min(caps)
    out = [("website_first_seen", _day(first_ts), archive_url(first_ts, first_url),
            f"First 200 capture in the Internet Archive: {first_url}")]
    best: dict[str, tuple[str, str]] = {}
    for ts, original in sorted(caps):
        w = milestone_word(original)
        if w and w not in best:
            best[w] = (ts, original)
    for w, (ts, original) in sorted(best.items(), key=lambda kv: kv[1][0]):
        out.append(("website_milestone", _day(ts), archive_url(ts, original),
                    f"First archived capture of a '{w}' page: {original}"))
    return out


def run(conn: sqlite3.Connection, thesis: dict) -> dict:
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "blocked": 0}
    rows = conn.execute("SELECT company_key, website FROM companies WHERE website IS NOT NULL ORDER BY company_key").fetchall()
    failures = 0
    for r in rows:
        host = domain_of(r["website"])
        if host is None:
            continue
        params = {"url": f"{host}/*", "output": "json", "fl": "timestamp,original,statuscode",
                  "filter": "statuscode:200", "collapse": "urlkey", "limit": str(MAX_CAPTURES)}
        try:
            data, net = cached_get(NAME, CDX, interval=2.0, params=params)
        except Blocked:
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES:
                stats["blocked"] = 1
                break
            continue
        failures = 0
        stats["requests"] += net
        stats["companies"] += 1
        for kind, day, url, detail in derive(captures(data)):
            stats["signals"] += emit.emit_signal(conn, company_key=r["company_key"], signal_type=kind, date=day, source_url=url,
                                                 confidence="medium", adapter=NAME, detail=detail)
    stats["skipped"] = len(rows) - stats["companies"]
    return stats


if __name__ == "__main__":
    from radar import db
    print(run(db.connect(), {}))
