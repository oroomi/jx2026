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
Each row also carries `criteria` (impact, trl, brl, irl, fit, verdict as the row prints them) and `facets` (what the filter rail offers).
Memos are the slow part (about 0.1 s each), so the list is cached per thesis and database file modification time,
and every thesis in config/ is warmed in one background thread when the app starts. A request that arrives while its list is
still being built waits 3 seconds at most and then gets the plain feed with a one-line note (D26).
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import date, timedelta

from radar import matching, memo, store

TOP_VERDICTS = ("INVEST", "DUE DILIGENCE", "ACCELERATOR")
VERDICT_ORDER = ("INVEST", "DUE DILIGENCE", "ACCELERATOR", "PARTNER INTRODUCTION", "GRANT SUPPORT", "WATCHLIST")
FIT_ORDER = ("High", "Medium", "Low")
COUNTRY_NAMES = {"FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "EE": "Estonia", "IS": "Iceland",
                 "DE": "Germany", "PL": "Poland", "LV": "Latvia", "LT": "Lithuania", "ES": "Spain", "BG": "Bulgaria", "CH": "Switzerland"}

log = logging.getLogger(__name__)
WAIT_SECONDS = 3.0  # the longest a request waits for a list that is still being built
_DEFAULT_WAIT = object()
_cache: dict[tuple, dict] = {}
_building: dict[tuple, threading.Event] = {}  # lists being built right now, by cache key
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

GAP = "Not yet evidenced"  # an Ocean Impact level with no band (sector-implied only), A'Pelago: missing evidence is not a low score
SCALE_MAX = 9            # TRL, BRL, IRL and the ocean impact level all run 1 to 9
DEADLINE_DAYS = 90       # "has a programme deadline in 90 days"
BANDS = ("Low", "Medium", "High")
NONE = "none"            # facet value for "no public record"


def _band_range(level: int | None, spec: dict | None) -> str:
    """The Low / Medium / High cut of a 1-9 level as the range it covers ('1-3', '4-6', '7-9'), read from the thesis' memo bands."""
    if level is None:
        return NONE
    low, high = (spec or {}).get("low_max", 3), (spec or {}).get("high_min", 7)
    return f"1-{low}" if level <= low else (f"{high}-{SCALE_MAX}" if level >= high else f"{low + 1}-{high - 1}")


def _sources(evidence) -> list[str]:
    """The source names of the records a level rests on, as the company page prints them (deduplicated, first three)."""
    seen: list[str] = []
    for e in evidence or []:
        name = ((e or {}).get("evidence") or {}).get("label")
        if name and name not in seen:
            seen.append(name)
    return seen[:3]


def _level_cell(name: str, scale: str, lv: dict) -> dict:
    """One of TRL, BRL, IRL: 'x of 9' when a level is on record, otherwise a dash with its reason. Never a guessed level."""
    level = lv.get("level")
    if level is None:
        return {"level": None, "text": None, "title": f"{name}: no public record. None of the records that set this level is on file."}
    src = _sources(lv.get("evidence"))
    why = f" Rule: {lv['because']}." if lv.get("because") else ""
    return {"level": level, "text": f"{level} of {SCALE_MAX}",
            "title": f"{name}: level {level} of {SCALE_MAX} ({scale}).{why} Source records: {', '.join(src) if src else 'see the company page'}."}


def _impact_cell(m: dict, fw: dict) -> dict:
    """Ocean impact: the Ocean Impact Assessment level 'x of 9' when the memo carries one (memo.ocean_impact), else the Navigator
    category band the memo reads, else a dash. A category match is a band, not a measured impact, and the title says so."""
    oi = m.get("ocean_impact") if isinstance(m.get("ocean_impact"), dict) else None
    rec = m.get("recommendation") or {}
    if oi and (oi.get("level") is not None or oi.get("band") in BANDS):
        level, band = oi.get("level"), oi.get("band") if oi.get("band") in BANDS else None
        src = sorted({e.get("source_label") for e in (oi.get("evidence") or []) if isinstance(e, dict) and e.get("source_label")})[:3]
        text = (f"{level} of {oi.get('level_max') or SCALE_MAX}" if band else GAP) if level is not None else band  # sector-implied only = a gap, never a low score
        return {"level": level, "band": band, "text": text,
                "title": f"Ocean impact: {text}{' (' + band + ')' if level is not None and band else ''}. Ocean Impact Assessment, "
                         f"readiness from public records, not measured impact. Source records: {', '.join(src) if src else 'see the company page'}."}
    band = ((m.get("levels") or {}).get("impact") or {}).get("band")
    cat = fw.get("category") or {}
    if band in BANDS and cat.get("category"):
        src = (cat.get("evidence") or {}).get("label") or ("PRH/YTJ register industry text" if cat.get("industry") else "see the company page")
        return {"level": None, "band": band, "text": band,
                "title": f"Ocean impact: {band}. Ocean Impact Navigator category '{cat['category']}' (keyword '{cat.get('keyword')}') found in "
                         f"{src}. A category match, not a measured impact."}
    implied = " The verdict reads it as Medium, implied by the sector." if rec.get("kind") == "fallback" else ""
    return {"level": None, "band": None, "text": None,
            "title": "Ocean impact: no public record. No Ocean Impact Navigator category is found in the register's line of business "
                     "or the signal texts." + implied}


def _fit_cell(m: dict) -> dict:
    band = ((m.get("levels") or {}).get("fit") or {}).get("band")
    line = next((w for w in m.get("why") or [] if str(w.get("text", "")).startswith("Thesis fit:")), None)
    if band not in BANDS:
        return {"band": None, "text": None, "title": "Thesis fit: no public record. No stored reason ties the company to the thesis."}
    reason = (line["text"].removeprefix("Thesis fit:").strip().rstrip(". ") if line else "no reason line on the company page")
    host = f" Record: {line['url'].split('//')[-1].split('/')[0]}." if line and line.get("url") else ""
    return {"band": band, "text": band, "title": f"Thesis fit {band}: {reason}.{host}"}


def _verdict_cell(m: dict) -> dict:
    rec = m.get("recommendation") or {}
    word = rec.get("decision")
    if not word:
        return {"text": None, "title": "Verdict: no public record."}
    basis = rec.get("matched") or rec.get("note") or "no decision row matched"
    return {"text": word.capitalize(), "title": f"Verdict {word}: {basis}. Source: the team's decision table over the four bands (impact, business, investment, thesis fit)."}


def _age_band(founded: str | None, today: date) -> str:
    """Registration age from the register's founding date: lt1, 1-3, 3-5, gt5, or none when the register states none."""
    f = (founded or "")[:10]
    if len(f) < 4 or not f[:4].isdigit():
        return NONE
    try:
        d = date.fromisoformat(f) if len(f) == 10 else date(int(f[:4]), 1, 1)
    except ValueError:
        return NONE
    years = (today - d).days / 365.25
    return "lt1" if years < 1 else ("1-3" if years < 3 else ("3-5" if years < 5 else "gt5"))


def criteria(m: dict, ctx: dict, nxt: dict, thesis: dict, today: date) -> tuple[dict, dict]:
    """(criteria, facets) for one company, from the memo, the page levels and the who-comes-next lists, so the home row shows exactly
    what the company page shows. criteria = what the row prints (impact, trl, brl, irl, fit, verdict); facets = what the left rail
    filters on, as lists of option values. A level with no record is None / 'none', never a number."""
    fw, c = ctx["fw"], ctx["c"]
    bands = ((thesis.get("memo") or {}).get("bands") or {})
    crit = {"impact": _impact_cell(m, fw),
            "trl": _level_cell("Technology readiness", "Aalto TRL 1-9", fw["trl"]),
            "brl": _level_cell("Business readiness", "KTH BRL 1-9", fw["brl"]),
            "irl": _level_cell("Investment readiness", "Investment Readiness 1-9", fw["irl"]),
            "fit": _fit_cell(m), "verdict": _verdict_cell(m)}
    end = (today + timedelta(days=DEADLINE_DAYS)).isoformat()
    due = any(f.get("deadline") and today.isoformat() <= f["deadline"] <= end for f in (nxt.get("funding") or []))
    cat = (fw.get("category") or {}).get("category")
    facets = {
        "verdict": [(m.get("recommendation") or {}).get("decision") or NONE],
        "impact": [crit["impact"]["band"] or (GAP if crit["impact"]["level"] is not None else NONE)],
        "trl": [_band_range(crit["trl"]["level"], bands.get("technology"))],
        "brl": [_band_range(crit["brl"]["level"], bands.get("business"))],
        "irl": ["known" if crit["irl"]["level"] is not None else NONE],
        "fit": [crit["fit"]["band"] or NONE],
        "country": [c.get("country") or NONE],
        "sector": [cat.capitalize() if cat else NONE],
        "age": [_age_band(c.get("founded"), today)],
        "src": sorted({store.source_family(s["adapter"]) for s in ctx["sigs"] if s.get("adapter")}),
        "deadline": [str(DEADLINE_DAYS)] if due else [],
        "member": [c["group_tag"]] if c.get("group_tag") in ("cohort", "portfolio") else [],
    }
    return crit, facets


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
        # the five judging criteria plus the verdict, and the rail's facets (computed once per cache warm, from the same memo)
        rows[-1]["criteria"], rows[-1]["facets"] = criteria(m, matching.company_context(conn, key), nxt, thesis, today)
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


def _cache_key(conn, thesis: dict) -> tuple:
    return (thesis.get("id"), _db_stamp(conn), store._today(None).isoformat())


def _build_and_store(thesis: dict, key: tuple, done: threading.Event) -> dict | None:
    """Build the list on its own read-only connection, cache it, and release everyone waiting for it. A failure caches nothing."""
    conn = store.open_db(thesis=thesis)
    try:
        data = build(conn, thesis) if conn is not None else None
        if data is not None:
            with _lock:
                _cache.clear() if len(_cache) > 8 else None
                _cache[key] = data
        return data
    except Exception:  # noqa: BLE001  (the page shows the plain feed; the next request tries again)
        log.exception("home list for thesis %s could not be built", thesis.get("id"))
        return None
    finally:
        if conn is not None:
            conn.close()
        with _lock:
            _building.pop(key, None)
        done.set()


def for_template(thesis: dict, wait=_DEFAULT_WAIT) -> dict | None:
    """Template hook: the cached list for this thesis. A list that is not cached is built in a background thread (once, however many
    requests ask) and the caller waits for it at most `wait` seconds (D26); after that it gets {"warming": True, "rows": []}, which the
    page prints as the plain feed with a one-line note. `wait=None` builds here and blocks (the warm-up thread, tests)."""
    if wait is _DEFAULT_WAIT:
        wait = WAIT_SECONDS
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        key = _cache_key(conn, thesis)
    finally:
        conn.close()
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            return hit
        done = _building.get(key)
        mine = done is None
        if mine:
            done = _building[key] = threading.Event()
    if mine and wait is None:
        return _build_and_store(thesis, key, done)
    if mine:
        threading.Thread(target=_build_and_store, args=(thesis, key, done), name=f"home-list-{thesis.get('id')}", daemon=True).start()
    done.wait(wait)
    with _lock:
        hit = _cache.get(key)
        busy = key in _building
    if hit is not None:
        return hit
    return {"warming": True, "rows": []} if busy else None  # not cached and not building: the build failed, the page shows the plain feed


def warm(thesis: dict) -> None:
    """Build one thesis' list now, on this thread (skips what is cached; waits for a build another thread already started)."""
    for_template(thesis, wait=None)


def warm_all() -> None:
    """Warm every thesis in config/ in one background thread, the default thesis first, so no sector's first visitor waits for the
    memos (D26). One thread, not one per thesis: the server has two CPUs."""
    def run():
        from radar import thesis as thesis_mod
        try:
            default = thesis_mod.load()
            todo = [default] + [t for t in (thesis_mod.load(p) for p in thesis_mod.available().values()) if t["id"] != default["id"]]
        except Exception:  # noqa: BLE001  (no readable thesis: nothing to warm)
            return
        for th in todo:
            try:
                warm(th)
            except Exception:  # noqa: BLE001  (a warm-up failure only means that sector builds on its first request)
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
