"""PRH registered-notices API v3 (CC BY 4.0, https://avoindata.prh.fi/opendata-registerednotices-api/v3/).

An equity round in a Finnish limited company is registered in the trade register within weeks, long before a financial
statement or press. This adapter turns dated register notices into signals:
  equity_event  ANTIP ANTIK OANTI OANKO KOROI OPTIO   (share issue, new shares, capital increase, option rights)
  board_change  HAL
  capital_loss  OPOMEN                                 (negative signal, shown as such)
  startup_notice  notice type U (start-up notification)
(a) window mode: national notices of the last WINDOW_DAYS days; a company is kept only if it was founded within 5 years
    and fits the thesis by industry code or by a thesis word in its registered line of business (never by name alone);
(b) company mode: for every company in the store with a Y-tunnus, its notices of the last 5 years.
One signal per company, type and registration day; detail lists the codes and record numbers. A notice without a
registrationDate is skipped: no day is ever invented.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx

from radar import emit, fit

NAME = "prh_notices"
PHASE = 2  # after the register discoverer, so company mode sees the companies it found
API = "https://avoindata.prh.fi/opendata-registerednotices-api/v3"
PUBLIC_PAGE = "https://tietopalvelu.ytj.fi/yritys/"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "prh_notices"
WINDOW_DAYS = 180
HISTORY_YEARS = 5
FOUNDED_WITHIN_YEARS = 5
PAGE_SIZE = 50
MAX_PAGES_PER_QUERY = 80
MIN_INTERVAL = 1.0
BACKOFF_429 = 60.0
MAX_429 = 3

# entry code -> (signal_type, English description from /description?code=EC&lang=EN)
CODES = {
    "ANTIP": ("equity_event", "Decision to issue shares"),
    "ANTIK": ("equity_event", "New shares"),
    "OANTI": ("equity_event", "New shares"),
    "OANKO": ("equity_event", "New shares and increase of share capital"),
    "KOROI": ("equity_event", "Capital increase"),
    "OPTIO": ("equity_event", "Option rights"),
    "HAL": ("board_change", "Board of directors"),
    "OPOMEN": ("capital_loss", "Loss of share capital"),
}
STARTUP_TYPE = "U"
NEW_TYPES = ("equity_event", "board_change", "capital_loss", "startup_notice")
# emit.py is a shared contract file this task may not edit: register the new types on the shared tuple at import.
emit.SIGNAL_TYPES = tuple(dict.fromkeys((*emit.SIGNAL_TYPES, *NEW_TYPES)))

_last_call = 0.0


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _cache_file(url: str) -> Path:
    return CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")


def fetch(url: str, client: httpx.Client | None = None, stats: dict | None = None) -> tuple[dict | None, bool]:
    """GET one URL, cached under data/cache/prh_notices/. 1 request per second; on 429 wait 60 s and retry.
    Returns (json or None when the source refuses or fails, was_network_call). Never raises on HTTP errors."""
    global _last_call
    f = _cache_file(url)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")), False
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=30)
    try:
        for attempt in range(MAX_429 + 1):
            wait = MIN_INTERVAL - (time.monotonic() - _last_call)
            if wait > 0:
                _sleep(wait)
            try:
                r = client.get(url)
            except httpx.HTTPError:
                _last_call = time.monotonic()
                if stats is not None:
                    stats["errors"] = stats.get("errors", 0) + 1
                return None, True
            _last_call = time.monotonic()
            if r.status_code == 429:
                if stats is not None:
                    stats["backoffs"] = stats.get("backoffs", 0) + 1
                if attempt == MAX_429:
                    return None, True
                _sleep(BACKOFF_429)
                continue
            if r.status_code != 200:
                if stats is not None:
                    stats["errors"] = stats.get("errors", 0) + 1
                return None, True
            try:
                data = r.json()
            except ValueError:
                return None, True
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data, True
    finally:
        if own:
            client.close()
    return None, True


def company_url(bid: str) -> str:
    return f"{API}/{bid}"


def window_url(start: str, end: str, *, code: str | None = None, ntype: str | None = None, page: int = 1) -> str:
    q = {"noticeRegistrationDateStart": start, "noticeRegistrationDateEnd": end}
    if code:
        q["entryCode"] = code
    if ntype:
        q["noticeRegistrationType"] = ntype
    if page > 1:
        q["page"] = page
    return f"{API}/?{urlencode(q)}"


def fetch_all_pages(start: str, end: str, *, code=None, ntype=None, client=None, stats=None):
    """Yield every company object of a window query, following the page parameter until a short or empty page."""
    for page in range(1, MAX_PAGES_PER_QUERY + 1):
        data, _ = fetch(window_url(start, end, code=code, ntype=ntype, page=page), client, stats)
        comps = (data or {}).get("companies") or []
        yield from comps
        total = (data or {}).get("totalResults") or 0
        if len(comps) < PAGE_SIZE or page * PAGE_SIZE >= total:
            return


def _desc(descs: list | None) -> str | None:
    by = {str(d.get("languageCode")): d.get("description") for d in descs or []}
    return next((by[c] for c in ("3", "1", "2") if by.get(c)), None)


def company_facts(c: dict) -> dict:
    mbl = c.get("mainBusinessLine") or {}
    names = [n for n in c.get("names", []) if str(n.get("type")) == "1"]
    cur = [n for n in names if not n.get("endDate")] or names
    bid = (c.get("businessId") or {}).get("value")
    return {"bid": bid, "name": cur[0]["name"] if cur else None,
            "founded": (c.get("businessId") or {}).get("registrationDate"),
            "code": mbl.get("type"), "desc": _desc(mbl.get("descriptions")),
            "website": (c.get("website") or {}).get("url")}


def interpret(notices: list[dict], since: str) -> list[dict]:
    """Collapse raw publicNotices into events: one per (signal_type, day). Rows without a registrationDate, rows before
    `since` and rows with no mapped code are dropped. Duplicate copies of one notice (the API repeats them) count once."""
    seen: set[tuple] = set()
    events: dict[tuple, dict] = {}
    for n in notices or []:
        day = n.get("registrationDate")
        rec = n.get("recordNumber")
        if not day or len(day) != 10 or day < since:
            continue
        key = (day, rec, tuple(n.get("entryCodes") or []), n.get("typeOfRegistration"))
        if key in seen:
            continue
        seen.add(key)
        hits = []
        for code in n.get("entryCodes") or []:
            if code in CODES:
                hits.append((CODES[code][0], code))
        if n.get("typeOfRegistration") == STARTUP_TYPE:
            hits.append(("startup_notice", "U"))
        for stype, code in hits:
            ev = events.setdefault((stype, day), {"signal_type": stype, "date": day, "codes": [], "records": []})
            if code not in ev["codes"]:
                ev["codes"].append(code)
            if rec and rec not in ev["records"]:
                ev["records"].append(rec)
    return sorted(events.values(), key=lambda e: (e["date"], e["signal_type"]))


def _code_text(code: str) -> str:
    return "Start-up notification" if code == "U" else f"{CODES[code][1]} ({code})"


def detail_for(ev: dict) -> str:
    codes = ", ".join(_code_text(c) for c in ev["codes"])
    recs = ", ".join(ev["records"]) or "record number not in public records"
    if ev["signal_type"] == "equity_event":
        lead = f"Share issue registered {ev['date']} (PRH)."
    elif ev["signal_type"] == "board_change":
        lead = f"Board change registered {ev['date']} (PRH)."
    elif ev["signal_type"] == "capital_loss":
        lead = f"Loss of share capital registered {ev['date']} (PRH). Negative signal."
    else:
        lead = f"Start-up notification registered {ev['date']} (PRH)."
    return f"{lead} Register entries: {codes}. Record number: {recs}."


def _years_before(today: date, years: int) -> str:
    try:
        return today.replace(year=today.year - years).isoformat()
    except ValueError:  # 29 Feb
        return today.replace(year=today.year - years, day=28).isoformat()


def thesis_fit(facts: dict, thesis: dict) -> bool:
    """jx12 precision rule: industry code on the thesis list, or a thesis word starting a word in the line of business.
    A thesis word in the legal name alone never qualifies."""
    codes = {str(c.get("code")) for c in thesis.get("industry_codes") or []}
    if facts["code"] and str(facts["code"]) in codes:
        return True
    return bool(facts["desc"] and fit.matched_keywords(facts["desc"], thesis))


def _emit_events(conn, company_key: str, bid: str, notices: list[dict], since: str, stats: dict) -> list[dict]:
    out = []
    for ev in interpret(notices, since):
        if emit.emit_signal(conn, company_key=company_key, signal_type=ev["signal_type"], date=ev["date"],
                            source_url=company_url(bid), confidence="high", adapter=NAME, detail=detail_for(ev)):
            stats["signals"] += 1
            stats["by_type"][ev["signal_type"]] = stats["by_type"].get(ev["signal_type"], 0) + 1
        out.append(ev)
    return out


def _window_mode(conn, thesis, stats, today, client):
    start, end = (today - timedelta(days=WINDOW_DAYS)).isoformat(), today.isoformat()
    founded_min = _years_before(today, FOUNDED_WITHIN_YEARS)
    queries = [dict(code=c) for c in CODES] + [dict(ntype=STARTUP_TYPE)]
    seen: dict[str, dict] = {}
    rejected: set[str] = set()
    for q in queries:
        for c in fetch_all_pages(start, end, client=client, stats=stats, **q):
            f = company_facts(c)
            # a window hit lists all of that company's notices in the window, so the first sighting is enough
            if not f["bid"] or f["bid"] in seen or f["bid"] in rejected:
                continue
            stats["examined"] += 1
            if not f["name"] or not f["founded"] or f["founded"] < founded_min:
                stats["skipped"] += 1
                rejected.add(f["bid"])
                continue
            if not thesis_fit(f, thesis):
                stats["skipped"] += 1
                rejected.add(f["bid"])
                continue
            seen[f["bid"]] = {"facts": f, "raw": c}
    for bid, item in seen.items():
        f = item["facts"]
        known = conn.execute("SELECT company_key FROM companies WHERE y_tunnus=? OR company_key=?", (bid, bid)).fetchone()
        key = known["company_key"] if known else bid
        # the window query lists only that company's notices of the window; the page for one company is the full record
        if not known:
            emit.upsert_company(conn, company_key=key, name=f["name"], source_url=company_url(bid), y_tunnus=bid, country="FI",
                                founded=f["founded"], industry_code=f["code"], industry_desc=f["desc"], website=f["website"],
                                group_tag="feed")
            stats["companies"] += 1
        evs = _emit_events(conn, key, bid, item["raw"].get("publicNotices"), start, stats)
        if not evs:
            continue
        stats["window_companies"] += 1
        for e in evs:
            if e["signal_type"] == "equity_event":
                stats["equity"].append({"company_key": key, "name": f["name"], "founded": f["founded"], "date": e["date"]})


def _company_mode(conn, stats, today, client):
    since = _years_before(today, HISTORY_YEARS)
    rows = conn.execute("SELECT company_key, y_tunnus FROM companies WHERE y_tunnus IS NOT NULL ORDER BY company_key").fetchall()
    for r in rows:
        data, _ = fetch(company_url(r["y_tunnus"]), client, stats)
        if not data:
            stats["skipped"] += 1
            continue
        # tolerate both a bare company object and a {"companies": [...]} wrapper
        comp = data if "publicNotices" in data else next(
            (c for c in data.get("companies", []) if (c.get("businessId") or {}).get("value") == r["y_tunnus"]), None)
        if not comp:
            stats["skipped"] += 1
            continue
        if _emit_events(conn, r["company_key"], r["y_tunnus"], comp.get("publicNotices"), since, stats):
            stats["company_mode_companies"] += 1


def run(conn: sqlite3.Connection, thesis: dict, today: date | None = None, client: httpx.Client | None = None) -> dict:
    today = today or date.today()
    stats = {"companies": 0, "signals": 0, "skipped": 0, "examined": 0, "window_companies": 0,
             "company_mode_companies": 0, "backoffs": 0, "errors": 0, "by_type": {}, "equity": []}
    _window_mode(conn, thesis, stats, today, client)
    conn.commit()
    _company_mode(conn, stats, today, client)
    conn.commit()
    for t in NEW_TYPES:
        stats[f"signals_{t}"] = stats["by_type"].get(t, 0)
    return stats


if __name__ == "__main__":
    from radar import db, thesis as thesis_mod
    th = thesis_mod.load()
    conn = db.connect(thesis_mod.db_path(th))
    res = run(conn, th)
    eq = sorted(res.pop("equity"), key=lambda e: (e["founded"], e["date"]), reverse=True)
    res.pop("by_type")
    print(res)
    print("youngest companies with an equity_event:")
    for e in eq[:5]:
        print(f"  {e['name']} founded {e['founded']} equity event {e['date']}")
