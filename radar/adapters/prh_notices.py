"""PRH registered-notices feed (open data, no key): dated equity events, board changes and start-up notices.

An equity round in a Finnish company is registered here within weeks, long before a financial statement or press.
Window mode: national notices per entry code for the last 180 days, kept only for young companies (founded within
the thesis stage_max_company_age_years) whose industry code or line-of-business text matches the thesis.
Company mode: every company already in the store gets its own notices for the last 5 years.
Rows without a day-level registrationDate are skipped, never dated by guess. Spec: .../v3/schema?lang=en
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
PHASE = 2  # after the register discoverers, so company mode sees the companies they found
API = "https://avoindata.prh.fi/opendata-registerednotices-api/v3/"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "prh_notices"
PAGE_SIZE = 50
MAX_PAGES_PER_CODE = 40
WINDOW_DAYS = 180
HISTORY_YEARS = 5
BACKOFF_SECONDS = 60
MIN_GAP_SECONDS = 1.0

# entry code -> (signal_type, English description used when the code list is not fetched)
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
_last_call = 0.0


def register_signal_types() -> None:
    """radar/emit.py is a shared contract file this task does not edit: add the new types to its tuple at import."""
    missing = tuple(t for t in NEW_TYPES if t not in emit.SIGNAL_TYPES)
    if missing:
        emit.SIGNAL_TYPES = emit.SIGNAL_TYPES + missing


register_signal_types()


def notice_url(business_id: str) -> str:
    return f"{API}{business_id}"


def _cache_file(url: str) -> Path:
    return CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")


def fetch(params: dict, path: str = "", client: httpx.Client | None = None, sleep=time.sleep) -> dict:
    """GET one page, cached under data/cache/prh_notices/. 1 request per second; on 429 wait 60 s and retry once more."""
    global _last_call
    url = API + path + (("?" + urlencode(params)) if params else "")
    f = _cache_file(url)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=30)
    try:
        for attempt in range(3):
            gap = MIN_GAP_SECONDS - (time.monotonic() - _last_call)
            if gap > 0:
                sleep(gap)
            r = client.get(url)
            _last_call = time.monotonic()
            if r.status_code == 429:
                if attempt == 2:
                    raise RuntimeError("PRH notices API kept answering 429")
                sleep(BACKOFF_SECONDS)
                continue
            r.raise_for_status()
            data = r.json()
            break
    finally:
        if own:
            client.close()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _first(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None


def items_of(page: dict | list) -> list[dict]:
    """The notice list of one response page. The envelope key is not pinned down offline, so look for a list of objects."""
    if isinstance(page, list):
        return [x for x in page if isinstance(x, dict)]
    for k in ("results", "notices", "items", "data", "companies"):
        if isinstance(page.get(k), list):
            return [x for x in page[k] if isinstance(x, dict)]
    return []


def _day(value) -> str | None:
    """YYYY-MM-DD from a day-level value only; a bare year or month stays None."""
    s = str(value or "")[:10]
    try:
        return date.fromisoformat(s).isoformat() if len(s) == 10 else None
    except ValueError:
        return None


def parse_notice(item: dict, code: str | None = None) -> dict | None:
    """One normalised notice, or None when it has no business id or no day-level registration date."""
    bid = _first(item, "businessId", "business_id", "yTunnus")
    if isinstance(bid, dict):
        bid = bid.get("value")
    reg = _day(_first(item, "registrationDate", "noticeRegistrationDate"))
    if not bid or not reg:
        return None
    entries = item.get("entryCodes") or item.get("entries") or []
    codes = [str(e.get("code") if isinstance(e, dict) else e) for e in entries]
    if code:
        codes = [code] if not codes else codes
    kind = str(_first(item, "typeOfRegistration", "registrationType") or "")
    industry = _first(item, "industryCode", "mainBusinessLineCode", "toimialaKoodi")
    desc = _first(item, "industryDescription", "mainBusinessLineDescription", "lineOfBusiness")
    return {"business_id": str(bid), "name": _first(item, "name", "companyName"), "date": reg, "codes": codes,
            "kind": kind, "founded": _day(_first(item, "foundingDate", "companyRegistrationDate", "registrationDateOfCompany")),
            "industry_code": str(industry) if industry else None, "industry_desc": desc,
            "record": _first(item, "noticeNumber", "recordNumber", "registrationNumber")}


def classify(n: dict) -> list[tuple[str, str, str]]:
    """(signal_type, code, description) for each entry code of one notice; start-up notices by registration type."""
    out = [(CODES[c][0], c, CODES[c][1]) for c in n["codes"] if c in CODES]
    if n["kind"] == STARTUP_TYPE:
        out.append(("startup_notice", STARTUP_TYPE, "Start-up notification"))
    return out


def _is_young(founded: str | None, today: date, years: int) -> bool:
    if not founded:
        return False
    try:
        cutoff = today.replace(year=today.year - years)
    except ValueError:  # 29 Feb
        cutoff = today.replace(year=today.year - years, day=28)
    return founded >= cutoff.isoformat()


def matches_thesis(n: dict, thesis: dict) -> bool:
    """jx12 precision rule: the industry code is on the thesis list, or a thesis word starts a word in the line of business."""
    codes = {str(c.get("code")) for c in thesis.get("industry_codes") or []}
    if n["industry_code"] and n["industry_code"] in codes:
        return True
    return bool(n["industry_desc"] and fit.matched_keywords(str(n["industry_desc"]), thesis))


def emit_notice(conn, n: dict, adapter: str = NAME) -> int:
    new = 0
    for stype, code, desc in classify(n):
        rec = f" Record {n['record']}." if n["record"] else ""
        if emit.emit_signal(conn, company_key=n["business_id"], signal_type=stype, date=n["date"],
                            source_url=notice_url(n["business_id"]), confidence="high", adapter=adapter,
                            detail=f"{desc} ({code}), registered {n['date']} (PRH).{rec}"):
            new += 1
    return new


def _pages(params: dict, fetcher, stats: dict):
    for page in range(1, MAX_PAGES_PER_CODE + 1):
        data = fetcher({**params, "page": page} if page > 1 else params)
        stats["requests"] += 1
        items = items_of(data)
        yield from items
        if len(items) < PAGE_SIZE:
            return


def _window(conn, thesis, stats, today, fetcher) -> None:
    start = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    age = int((thesis.get("geography") or {}).get("stage_max_company_age_years", HISTORY_YEARS))
    base = {"noticeRegistrationDateStart": start, "noticeRegistrationDateEnd": today.isoformat()}
    queries = [{**base, "entryCode": c} for c in CODES] + [{**base, "typeOfRegistration": STARTUP_TYPE}]
    for q in queries:
        for item in _pages(q, fetcher, stats):
            n = parse_notice(item, q.get("entryCode"))
            if n is None:
                stats["skipped"] += 1
                continue
            if not _is_young(n["founded"], today, age) or not matches_thesis(n, thesis):
                stats["skipped"] += 1
                continue
            if not n["name"]:
                stats["skipped"] += 1
                continue
            known = conn.execute("SELECT 1 FROM companies WHERE company_key=?", (n["business_id"],)).fetchone()
            emit.upsert_company(conn, company_key=n["business_id"], name=n["name"], source_url=notice_url(n["business_id"]),
                                y_tunnus=n["business_id"], country="FI", founded=n["founded"],
                                industry_code=n["industry_code"], industry_desc=n["industry_desc"])
            stats["signals"] += emit_notice(conn, n)
            if not known:
                stats["companies"] += 1
            stats["touched"].add(n["business_id"])


def _company_mode(conn, stats, today, fetcher) -> None:
    start = today.replace(year=today.year - HISTORY_YEARS, day=min(today.day, 28)).isoformat()
    rows = conn.execute("SELECT company_key, y_tunnus FROM companies WHERE y_tunnus IS NOT NULL").fetchall()
    for r in rows:
        q = {"businessId": r["y_tunnus"], "noticeRegistrationDateStart": start, "noticeRegistrationDateEnd": today.isoformat()}
        for item in _pages(q, fetcher, stats):
            n = parse_notice({**item, "businessId": r["y_tunnus"]} if not _first(item, "businessId", "business_id", "yTunnus") else item)
            if n is None or n["business_id"] != r["y_tunnus"] or n["date"] < start:
                stats["skipped"] += 1
                continue
            stats["signals"] += emit_notice(conn, n)
            stats["touched"].add(r["company_key"])


def run(conn: sqlite3.Connection, thesis: dict, today: date | None = None, fetcher=None) -> dict:
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "touched": set(), "blocked": 0}
    fetcher = fetcher or (lambda params: fetch(params))
    today = today or date.today()
    try:
        _window(conn, thesis, stats, today, fetcher)
        conn.commit()
        _company_mode(conn, stats, today, fetcher)
    except (httpx.HTTPError, RuntimeError, OSError) as e:  # offline or refused: report, never crash the build
        stats["blocked"] = 1
        stats["error"] = f"{type(e).__name__}: {e}"
    conn.commit()
    stats["touched"] = len(stats["touched"])
    return stats


if __name__ == "__main__":
    from radar import db, thesis as thesis_mod
    c = db.connect()
    print(run(c, thesis_mod.load()))
    for r in c.execute("SELECT signal_type, count(*) n FROM signals WHERE adapter=? GROUP BY 1", (NAME,)):
        print(r["signal_type"], r["n"])
    q = """SELECT k.name, k.founded, s.date FROM signals s JOIN companies k USING(company_key)
           WHERE s.adapter=? AND s.signal_type='equity_event' AND k.founded IS NOT NULL ORDER BY k.founded DESC, s.date LIMIT 5"""
    for r in c.execute(q, (NAME,)):
        print("youngest equity event:", r["name"], "founded", r["founded"], "event", r["date"])
