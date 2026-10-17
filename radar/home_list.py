"""The home list (design C, phase 3): every company the radar shows on "/" grouped for the pill tabs.

Rows = the feed's main tier (companies found with a stated reason) plus the declared cohort and portfolio. Each row
carries what the home page prints and nothing more: name, country, the register's line of business, the dated
public records (for the sparkline), the fund memo verdict and its investment band, and the first and latest record
dates. Groups are computed from those fields only:
  new     = first public record inside the feed window (the thesis' window, ending today)
  fit     = memo verdict INVEST, DUE DILIGENCE or ACCELERATOR, or thesis fit High
Every group is ordered by verdict strength (INVEST, DUE DILIGENCE, ACCELERATOR, PARTNER INTRODUCTION, GRANT SUPPORT,
WATCHLIST), then thesis-fit band, then the latest record; "New this quarter" stays newest record first.
  ready   = memo investment readiness band High
  country = companies.country
Each row also carries `ocean`: the Ocean Impact Assessment's area, level, band and confidence (None when the thesis defines no impact areas).
Memos are the slow part (about 0.1 s each), so the list is cached per thesis and database file modification time,
and warmed once in a background thread when the app starts.
"""
from __future__ import annotations

import os
import threading
from datetime import date, timedelta

from radar import matching, memo, store

TOP_VERDICTS = ("INVEST", "DUE DILIGENCE", "ACCELERATOR")
VERDICT_ORDER = ("INVEST", "DUE DILIGENCE", "ACCELERATOR", "PARTNER INTRODUCTION", "GRANT SUPPORT", "WATCHLIST")
FIT_ORDER = ("High", "Medium", "Low")
COUNTRY_NAMES = {"FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "EE": "Estonia", "IS": "Iceland",
                 "DE": "Germany", "PL": "Poland", "LV": "Latvia", "LT": "Lithuania", "ES": "Spain", "BG": "Bulgaria", "CH": "Switzerland"}

_cache: dict[tuple, dict] = {}
_lock = threading.Lock()


def _db_stamp(conn) -> str:
    try:
        path = conn.execute("PRAGMA database_list").fetchone()[2]
        return f"{path}:{os.path.getmtime(path)}" if path else "memory"
    except Exception:  # noqa: BLE001
        return "unknown"


def _window(thesis: dict, today: date) -> tuple[str, str]:
    days = int((thesis.get("geography") or {}).get("feed_window_days") or 90)
    return (today - timedelta(days=days)).isoformat(), today.isoformat()


def build(conn, thesis: dict, today: date | None = None) -> dict:
    """Rows and groups for one thesis store. Pure read; no row is invented, empty fields stay None."""
    today = store._today(today)
    start, end = _window(thesis, today)
    month = (today - timedelta(days=30)).isoformat()
    main = [r for r in store.feed(conn, thesis, limit=500) if r["strength"] == "strong"]
    declared = [k for (k,) in conn.execute("SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio')")]
    keys = list(dict.fromkeys([r["company_key"] for r in main] + declared))
    rows = []
    for key in keys:
        c = conn.execute("SELECT company_key, name, country, industry_desc, group_tag FROM companies WHERE company_key=?", (key,)).fetchone()
        if c is None:
            continue
        sig = conn.execute("SELECT date, signal_type FROM signals WHERE company_key=? AND date IS NOT NULL ORDER BY date", (key,)).fetchall()
        dates = [d for d, _ in sig]
        types = {t for _, t in sig}
        m = memo.build(conn, thesis, key, today=today) or {}
        rec = m.get("recommendation") or {}
        bands = {b["label"]: b["band"] for b in rec.get("because_labels", [])}
        nxt = matching.who_comes_next(key, thesis, 5, conn=conn, today=today) or {}
        checks = [  # the same six checks the company page counts in its coverage line
            "register_entry" in types,
            bool(types & {"bf_funding", "eu_grant", "public_funding"}),
            "eu_project" in types,
            bool(types & {"public_contract", "first_sales", "pilot_named"}),
            ((m.get("levels") or {}).get("impact") or {}).get("band") not in (None, "unknown"),
            bool(nxt.get("investors")),
        ]
        year_ago = (today - timedelta(days=365)).isoformat()
        tape = [round((date.fromisoformat(d[:10]) - (today - timedelta(days=365))).days / 365 * 100, 1) for d in dates if d[:10] >= year_ago and d[:10] <= today.isoformat()]
        rows.append({
            "company_key": key, "name": c["name"], "country": c["country"], "sector": c["industry_desc"], "group_tag": c["group_tag"],
            "signals": [{"date": d} for d in dates], "first": dates[0] if dates else None, "latest": dates[-1] if dates else None,
            "verdict": rec.get("decision"), "fit": bands.get("Thesis fit"),
            "investment": ((m.get("levels") or {}).get("investment") or {}).get("band"),
            "covered": sum(checks), "checks": len(checks), "tape": tape,
            "ocean": {k: (m.get("ocean_impact") or {}).get(k) for k in ("area", "level", "band", "confidence")} if m.get("ocean_impact") else None,
        })
    def strength(r):
        """Verdict strength, then thesis-fit band, then the latest record (newest first), then name."""
        v = VERDICT_ORDER.index(r["verdict"]) if r["verdict"] in VERDICT_ORDER else len(VERDICT_ORDER)
        f = FIT_ORDER.index(r["fit"]) if r["fit"] in FIT_ORDER else len(FIT_ORDER)
        return (v, f, -int((r["latest"] or "0000-00-00").replace("-", "")[:8] or 0), r["name"])

    by_date = sorted(rows, key=lambda r: (r["latest"] or "", r["name"]), reverse=True)
    rows.sort(key=strength)
    fit = [r for r in rows if r["verdict"] in TOP_VERDICTS or r["fit"] == "High"]
    groups = [("all", "All startups", rows),
              ("fit", "Top fits", fit),
              ("ready", "Investor-ready", [r for r in rows if r["investment"] == "High"]),
              ("new", "New this quarter", [r for r in by_date if r["first"] and r["first"] >= start])]
    countries = {}
    for r in rows:
        if r["country"]:
            countries.setdefault(r["country"], []).append(r)
    country_groups = [(f"cc-{cc}", COUNTRY_NAMES.get(cc, cc), rs) for cc, rs in sorted(countries.items(), key=lambda x: (-len(x[1]), x[0]))]
    new = [r for r in rows if r["first"] and r["first"] >= start]
    return {
        "rows": rows,
        "groups": [g for g in groups if g[2]],
        "countries": country_groups if len(country_groups) > 1 else [],
        "headline": {"new": len(new), "month": sum(1 for r in new if r["first"] >= month)},
        "window": (start, end), "fetched": ((store.feed_counts(conn, thesis) or {}).get("last_fetched") or "")[:10],
    }


def for_template(thesis: dict) -> dict | None:
    """Template hook: the cached list for this thesis, built from its own read-only connection."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        key = (thesis.get("id"), _db_stamp(conn), store._today(None).isoformat())
        with _lock:
            hit = _cache.get(key)
        if hit is not None:
            return hit
        data = build(conn, thesis)
    finally:
        conn.close()
    with _lock:
        _cache.clear() if len(_cache) > 8 else None
        _cache[key] = data
    return data


def warm(thesis: dict) -> None:
    """Build the default thesis' list once in the background so the first visitor does not wait for the memos."""
    def run():
        try:
            for_template(thesis)
        except Exception:  # noqa: BLE001  (a warm-up failure only means the first request builds it)
            pass
    threading.Thread(target=run, name="home-list-warm", daemon=True).start()


def dots(dates: list[str], today: str | None = None, entry: str | None = None) -> dict | None:
    """One time axis from the first dated public record to today: each record as a dot (percent along the axis),
    the latest marked, year ticks, and the cohort-entry marker when a declared entry date exists. Used by the
    editorial skin on both pages, so the mark is one identity across home and company."""
    ds = sorted(d[:10] for d in dates if d and len(d) >= 4)
    if not ds:
        return None
    def day(s):
        p = (s + "-01-01")[:10].split("-")
        return date(int(p[0]), int(p[1] or 1), int(p[2] or 1)).toordinal()
    t1 = day(today or store._today(None).isoformat())
    t0 = min(day(ds[0]), t1 - 365)
    span = max(1, t1 - t0)
    pct = lambda s: round((day(s) - t0) / span * 100, 2)  # noqa: E731
    years = [{"label": str(y), "x": pct(f"{y}-01-01")} for y in range(date.fromordinal(t0).year + 1, date.fromordinal(t1).year + 1)]
    step = max(1, len(years) // 4 + (1 if len(years) % 4 else 0)) if len(years) > 4 else 1
    return {"dots": [pct(d) for d in ds], "latest": pct(ds[-1]), "years": years[::-1][::step][::-1],
            "entry": pct(entry) if entry else None, "first": ds[0], "n": len(ds)}


def cohort_entry(company_key: str, name: str | None) -> str | None:
    """The declared cohort-entry date (data/declared/cohort_entry_dates.csv), when that file has the company."""
    from radar import earliness
    e = earliness._entry_dates(earliness.ENTRY_DATES_CSV)
    hit = e.get((company_key or "").casefold()) or e.get((name or "").casefold())
    return hit[0] if hit else None
