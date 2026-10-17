"""The home list (design C, phase 3): every company the radar shows on "/" grouped for the pill tabs.

Rows = the feed's main tier (companies found with a stated reason) plus the declared cohort and portfolio. Each row
carries what the home page prints and nothing more: name, country, the register's line of business, the dated
public records (for the sparkline), the fund memo verdict and its investment band, and the first and latest record
dates. Groups are computed from those fields only:
  new     = first public record inside the feed window (the thesis' window, ending today)
  fit     = memo verdict INVEST, DUE DILIGENCE or ACCELERATOR, or thesis fit High
Every group is ordered by verdict strength (INVEST, DUE DILIGENCE, ACCELERATOR, PARTNER INTRODUCTION, GRANT SUPPORT, WATCHLIST), and inside
a verdict by evidence (D48): declared cohort or portfolio company, Ocean Impact ladder level, its confidence, business readiness level, number
of dated records, newest record; "New this quarter" stays newest record first.
  ready   = memo investment readiness band High
  country = companies.country
Each row also carries `ocean`: the Ocean Impact Assessment's area, level, band and confidence (None when the thesis defines no impact areas).
Each row also carries `criteria` (impact, trl, brl, irl, fit, verdict as the row prints them) and `facets` (what the filter rail offers),
and `subsectors` (the taxonomy's sub-sectors of D42, [] when the thesis has none or the store was not backfilled).
Memos are the slow part (about 0.1 s each), so the list is cached per thesis and database file modification time,
and every thesis in config/ is warmed in one background thread when the app starts. A request that arrives while its list is
still being built waits 3 seconds at most and then gets the plain feed with a one-line note (D26).
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import date, timedelta

from radar import home_config, matching, memo, sectors, store

TOP_VERDICTS = ("INVEST", "DUE DILIGENCE", "ACCELERATOR")
VERDICT_ORDER = ("INVEST", "DUE DILIGENCE", "ACCELERATOR", "PARTNER INTRODUCTION", "GRANT SUPPORT", "WATCHLIST")
FIT_ORDER = ("High", "Medium", "Low")
CONFIDENCE_ORDER = ("high", "medium", "low")
DECLARED_TAGS = ("cohort", "portfolio")

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
REASON_MAX = 110         # the longest first reason a row prints, in characters (D70); the full sentence stays on the company page

# The words the sort line prints. They follow `strength()` in build() term by term (declared member, Ocean Impact level, its confidence,
# business readiness, number of dated records, newest record); tests/test_j3_ui.py checks the real rows against this order.
SORT_TIES = ("declared cohort and portfolio companies first", "a higher ocean impact level", "higher confidence in that level",
             "a higher business readiness level", "more dated public records", "the newest record")


def shorten(text: str | None, limit: int = REASON_MAX) -> str | None:
    """One reason as a single short line: the whole sentence when it fits; otherwise without its long brackets (the row already prints the
    industry and the name); otherwise cut at the last clause that fits ("; " first, then ", "), otherwise at the last word with three dots.
    A bracket left open is cut away. Never mid-word, never a made-up word."""
    t = " ".join((text or "").split())
    if not t:
        return None
    if len(t) <= limit:
        return t
    t = re.sub(r"\s*\([^)]{12,}\)", "", t)   # a long bracket (the industry text, the legal name) is already printed on the row: drop it before cutting
    if len(t) <= limit:
        return t
    head = t[: limit + 1]
    for sep in ("; ", ", "):
        at = head.rfind(sep)
        if at >= limit * 0.4:
            out, tail = t[:at].rstrip(" ,;:"), "."
            break
    else:
        at = head.rfind(" ")
        out, tail = t[: at if at > 0 else limit].rstrip(" ,;:"), "..."
    while out.count("(") > out.count(")") and "(" in out:
        out = out[: out.rfind("(")].rstrip(" ,;:")
    if tail == "..." and len(re.findall(r"(?:^|[\s(])'", out)) > len(re.findall(r"'(?=[\s.,;:)]|$)", out)):
        tail = "...'"   # a quotation cut in the middle is closed, so it reads as a quotation
    return out + ("" if out.endswith(".") else tail)


def first_reason(m: dict | None) -> str | None:
    """The first reason the memo gives for the verdict, in the words the company page prints under "Why this verdict" (memo plain_why, else
    the first why line, else the decision's note), shortened to one line. None when the memo has no reason (the row then prints none)."""
    m = m or {}
    for pool in (m.get("plain_why"), m.get("why")):
        for w in pool or []:
            text = (w or {}).get("text") if isinstance(w, dict) else w
            if text and str(text).strip():
                out = shorten(str(text), REASON_MAX)
                return out + "." if out and out[-1].isalnum() else out
    note = (m.get("recommendation") or {}).get("note")
    out = shorten(note, REASON_MAX) if note else None
    return (out[0].upper() + out[1:] + ("." if out[-1].isalnum() else "")) if out else None


def sort_brief() -> str:
    """The one visible line above a list that is in verdict order; sort_text() is the whole rule behind it."""
    return f"Sorted by verdict, strongest first ({VERDICT_ORDER[0].capitalize()} to {VERDICT_ORDER[-1].capitalize()}), then by evidence."


def sort_text(group: str = "all") -> str:
    """The sort order of a group in words, read from the ordering code in build() (D70). 'new' is newest record first; every other group is
    verdict strength, then the evidence terms in SORT_TIES."""
    if group == "new":
        return "Sorted by the date of each company's newest public record, newest first."
    verdicts = ", ".join(v.capitalize() for v in VERDICT_ORDER)
    return f"Sorted by verdict, strongest first ({verdicts}). Within one verdict: {', then '.join(SORT_TIES)}."


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
        "source": sorted({store.source_family(s["adapter"]) for s in ctx["sigs"] if s.get("adapter")}),
        "deadline": [str(DEADLINE_DAYS)] if due else [],
        "member": [c["group_tag"]] if c.get("group_tag") in ("cohort", "portfolio") else [],
    }
    return crit, facets


def first_seen(first: str | None, start: str) -> bool:
    """A company is 'first seen' in the window when its first dated public record, of any kind, falls on or after the window start (D72).
    The one test behind the home page's "N companies first seen in the last 90 days" and the New this quarter tab."""
    return bool(first) and first >= start


def window_counts(conn, thesis: dict, today: date | None = None) -> dict:
    """The counts the home page and /method both print, from the same keys the list is built from (D72): `main` = companies found by the feed
    rule (outside the declared cohort and portfolio), `declared` = cohort and portfolio companies, `on_list` = both, `first_seen` = those of
    them whose first dated public record of any kind is inside the window. No memo is built, so it is cheap."""
    today = store._today(today)
    start, end = _window(thesis, today)
    main = [r["company_key"] for r in store.feed(conn, thesis, limit=500) if r["strength"] == "strong"]
    declared = [k for (k,) in conn.execute("SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio')")]
    firsts = dict(conn.execute("SELECT company_key, MIN(date) FROM signals WHERE date IS NOT NULL GROUP BY company_key").fetchall())
    keys = [k for k in dict.fromkeys(main + declared) if conn.execute("SELECT 1 FROM companies WHERE company_key=?", (k,)).fetchone()]
    in_main = set(main)
    new = [k for k in keys if first_seen(firsts.get(k), start)]
    return {"window_days": int((thesis.get("geography") or {}).get("feed_window_days") or 90), "window_start": start, "window_end": end,
            "main": len(main), "declared": sum(1 for k in keys if k not in in_main), "on_list": len(keys),
            "first_seen": len(new), "first_seen_main": sum(1 for k in new if k in in_main),
            "first_seen_declared": sum(1 for k in new if k not in in_main)}


def build(conn, thesis: dict, today: date | None = None) -> dict:
    """Rows and groups for one thesis store. Pure read; no row is invented, empty fields stay None."""
    today = store._today(today)
    start, end = _window(thesis, today)
    month = (today - timedelta(days=30)).isoformat()
    main = [r for r in store.feed(conn, thesis, limit=500) if r["strength"] == "strong"]
    declared = [k for (k,) in conn.execute("SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio')")]
    keys = list(dict.fromkeys([r["company_key"] for r in main] + declared))
    smap = sectors.home_map(conn, thesis)   # sub-sectors per company (D42); None when the thesis has no taxonomy or the store is not backfilled
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
        rows[-1]["reason"] = first_reason(m)   # the one-line first reason a row prints (D70)
        rows[-1]["subsectors"] = sectors.row_subsectors(smap, thesis, key)   # [{slug, label, basis}]; "Not yet classified" when no link
        rows[-1]["facets"]["subsector"] = [x["slug"] for x in rows[-1]["subsectors"]]
    def strength(r):
        """Verdict strength first (the verdict rules are untouched). Inside one verdict, evidence decides (D48): a declared cohort or
        portfolio company first, then the Ocean Impact ladder level (higher first), then its confidence (high, medium, low), then the
        business readiness level, then the number of dated public records, then the newest record, then the name. A company with no
        level sorts after one that has a level; it is never ranked as if it had a low one."""
        v = VERDICT_ORDER.index(r["verdict"]) if r["verdict"] in VERDICT_ORDER else len(VERDICT_ORDER)
        oi = r.get("ocean") or {}
        level = oi.get("level")
        conf = CONFIDENCE_ORDER.index(oi["confidence"]) if oi.get("confidence") in CONFIDENCE_ORDER else len(CONFIDENCE_ORDER)
        brl = ((r.get("criteria") or {}).get("brl") or {}).get("level")
        return (v, 0 if r["group_tag"] in DECLARED_TAGS else 1, -(level if level is not None else -1), conf, -(brl if brl is not None else -1),
                -len(r["signals"]), -int((r["latest"] or "0000-00-00").replace("-", "")[:8] or 0), r["name"])

    by_date = sorted(rows, key=lambda r: (r["latest"] or "", r["name"]), reverse=True)
    rows.sort(key=strength)
    fit = [r for r in rows if r["verdict"] in TOP_VERDICTS or r["fit"] == "High"]
    groups = [("all", home_config.group_label("all"), rows),
              ("fit", home_config.group_label("fit"), fit),
              ("ready", home_config.group_label("ready"), [r for r in rows if r["investment"] == "High"]),
              ("new", home_config.group_label("new"), [r for r in by_date if first_seen(r["first"], start)])]
    countries = {}
    for r in rows:
        if r["country"]:
            countries.setdefault(r["country"], []).append(r)
    country_groups = [(f"cc-{cc}", home_config.country_name(cc), rs) for cc, rs in sorted(countries.items(), key=lambda x: (-len(x[1]), x[0]))]
    new = [r for r in rows if first_seen(r["first"], start)]
    return {
        "rows": rows,
        "groups": [g for g in groups if g[2]],
        "countries": country_groups if len(country_groups) > 1 else [],
        "headline": {"new": len(new), "month": sum(1 for r in new if r["first"] >= month)},
        "sort": {k: sort_text(k) for k, _, _ in groups}, "sort_brief": sort_brief(), "window": (start, end), "fetched": ((store.feed_counts(conn, thesis) or {}).get("last_fetched") or "")[:10],
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


def stamp(thesis: dict) -> tuple | None:
    """The key a list (or anything derived from it, such as the Top matching ranking) is cached under: thesis, store file version, day.
    None when the sector has no store."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        return _cache_key(conn, thesis)
    finally:
        conn.close()


def peek(thesis: dict) -> dict | None:
    """The cached list for this thesis if there is one, else None. Never builds and never waits (the sector links use it to see which
    filters another sector offers)."""
    key = stamp(thesis)
    if key is None:
        return None
    with _lock:
        return _cache.get(key)


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
