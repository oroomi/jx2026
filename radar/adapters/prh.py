"""PRH/YTJ open data API v3 (CC BY 4.0, https://ytj.fi/en/index/opendata.html).

(a) refresh every company that has a Y-tunnus, emit one register_entry signal each (confidence high);
(b) discovery: Finnish companies registered in the last 365 days whose TOL code is in the thesis or whose legal name
    starts a word with a thesis keyword. Never high confidence: name keyword = medium, code only = low.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx

from radar import emit, town as town_mod

NAME = "prh"
API = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "prh"
MAX_DISCOVERY_REQUESTS = 400
PAGE_SIZE = 100
_last_call = 0.0
_ENGLISH_FIRST = ("3", "1", "2")  # languageCode: 3 en, 1 fi, 2 sv
_NON_BUSINESS_PREFIX = re.compile(r"^(asunto oy|asunto-oy|bostads ab|bostadsaktiebolaget|kiinteistö oy|fastighets ab)\b", re.I)


def _url(params: dict) -> str:
    return f"{API}?{urlencode(params)}"


def fetch(params: dict, client: httpx.Client | None = None) -> tuple[dict, bool]:
    """GET one API page, cached under data/cache/prh/. Returns (json, was_network_call). 1 request per 2 s."""
    global _last_call
    url = _url(params)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")), False
    wait = 2.0 - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=30)
    try:
        r = client.get(url)
        _last_call = time.monotonic()
        r.raise_for_status()
        data = r.json()
    finally:
        if own:
            client.close()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data, True


def _desc(descs: list, fallback_order=_ENGLISH_FIRST) -> str | None:
    by = {str(d.get("languageCode")): d.get("description") for d in descs or []}
    for code in fallback_order:
        if by.get(code):
            return by[code]
    return None


def legal_name(c: dict) -> str | None:
    """Current legal name: type 1, no endDate; else any type 1."""
    names = [n for n in c.get("names", []) if str(n.get("type")) == "1"]
    cur = [n for n in names if not n.get("endDate")] or names
    return cur[0]["name"] if cur else None


def derive_status(c: dict) -> str:
    """From companySituations and registeredEntries endDate, never the top-level status field."""
    sit = {str(s.get("type")) for s in c.get("companySituations", []) if not s.get("endDate")}
    if "KONK" in sit:
        return "bankrupt"
    if "SELV" in sit:
        return "ended"
    reg = [e for e in c.get("registeredEntries", []) if str(e.get("type")) == "1"]
    if reg:
        return "active" if any(not e.get("endDate") for e in reg) else "ended"
    return "unknown"


def parse(c: dict) -> dict:
    bid = c["businessId"]["value"]
    mbl = c.get("mainBusinessLine") or {}
    return dict(
        y_tunnus=bid, name=legal_name(c), founded=c["businessId"].get("registrationDate"),
        industry_code=mbl.get("type"), industry_desc=_desc(mbl.get("descriptions")),
        website=(c.get("website") or {}).get("url"), register_status=derive_status(c),
        source_url=_url({"businessId": bid}))


def _words_start_with(text: str, keywords: list[str]) -> list[str]:
    t = text.lower()
    return [k for k in keywords if re.search(r"(?<![^\W\d_])" + re.escape(k.lower()), t)]


def thesis_keywords(thesis: dict) -> list[str]:
    seen, out = set(), []
    for words in (thesis.get("name_keywords") or {}).values():
        for w in words:
            w = str(w).strip().lower()
            if w and w not in seen:
                seen.add(w)
                out.append(w)
    return out


def _refresh(conn, thesis, stats) -> None:
    rows = conn.execute("SELECT company_key, y_tunnus, name, group_tag FROM companies WHERE y_tunnus IS NOT NULL").fetchall()
    for r in rows:
        data, net = fetch({"businessId": r["y_tunnus"]})
        stats["requests"] += net
        hits = [c for c in data.get("companies", []) if c["businessId"]["value"] == r["y_tunnus"]]
        if not hits:
            stats["skipped"] += 1
            continue
        p = parse(hits[0])
        emit.upsert_company(conn, company_key=r["company_key"], name=p["name"] or r["name"], source_url=p["source_url"],
                            y_tunnus=p["y_tunnus"], country="FI", founded=p["founded"], industry_code=p["industry_code"],
                            industry_desc=p["industry_desc"], website=p["website"], register_status=p["register_status"],
                            group_tag=r["group_tag"])
        town_mod.record_town(conn, r["company_key"], hits[0])
        stats["companies"] += 1
        if p["register_status"] == "bankrupt" or not p["founded"]:
            continue  # a bankrupt company is not a new-company signal
        if emit.emit_signal(conn, company_key=r["company_key"], signal_type="register_entry", date=p["founded"],
                            source_url=p["source_url"], confidence="high", adapter=NAME,
                            detail=f"Registered in PRH/YTJ on {p['founded']} (Y-tunnus {p['y_tunnus']})."):
            stats["signals"] += 1


def _discover(conn, thesis, stats, today: date) -> None:
    start = (today - timedelta(days=365)).isoformat()
    window = {"registrationDateStart": start, "registrationDateEnd": today.isoformat()}
    codes = {str(c["code"]) for c in thesis.get("industry_codes", [])}
    kws = thesis_keywords(thesis)
    queries = [{"mainBusinessLine": c} for c in sorted(codes)] + [{"name": k} for k in kws]
    seen: set[str] = set()
    for q in queries:
        page = 1
        while stats["examined_requests"] < MAX_DISCOVERY_REQUESTS:
            params = {**q, **window}
            if page > 1:
                params["page"] = page
            data, _ = fetch(params)
            stats["examined_requests"] += 1
            comps = data.get("companies", [])
            for c in comps:
                bid = c["businessId"]["value"]
                if bid in seen:
                    continue
                seen.add(bid)
                stats["examined"] += 1
                _consider(conn, c, codes, kws, start, stats)
            if len(comps) < PAGE_SIZE or page * PAGE_SIZE >= data.get("totalResults", 0):
                break
            page += 1
        if stats["examined_requests"] >= MAX_DISCOVERY_REQUESTS:
            break


def _consider(conn, c, codes, kws, start, stats) -> None:
    p = parse(c)
    name = p["name"]
    # the API date filter also matches later name/form changes, so the Y-tunnus itself must be new
    if not name or not p["founded"] or p["founded"] < start or p["register_status"] != "active":
        return
    if any("housing" in (_desc(f.get("descriptions")) or "").lower() for f in c.get("companyForms", [])) or _NON_BUSINESS_PREFIX.match(name):
        return
    matched = _words_start_with(name, kws)
    by_code = p["industry_code"] in codes
    if not matched and not by_code:
        return
    if conn.execute("SELECT 1 FROM companies WHERE company_key=?", (p["y_tunnus"],)).fetchone():
        return  # already known (cohort, portfolio or earlier run); refresh handles those
    conf = "medium" if matched else "low"
    why = (f"legal name starts a word with thesis keyword '{matched[0]}'" if matched else f"industry code {p['industry_code']} is in the thesis")
    emit.upsert_company(conn, company_key=p["y_tunnus"], name=name, source_url=p["source_url"], y_tunnus=p["y_tunnus"],
                        country="FI", founded=p["founded"], industry_code=p["industry_code"], industry_desc=p["industry_desc"],
                        website=p["website"], group_tag="feed", register_status=p["register_status"])
    town_mod.record_town(conn, p["y_tunnus"], c)
    emit.emit_signal(conn, company_key=p["y_tunnus"], signal_type="register_entry", date=p["founded"], source_url=p["source_url"],
                     confidence=conf, adapter=NAME, detail=f"Registered in PRH/YTJ on {p['founded']}; matched because {why}.")
    stats["discovered"] += 1
    stats["signals"] += 1
    stats["samples"].append({"y_tunnus": p["y_tunnus"], "name": name, "confidence": conf, "why": why})


def run(conn: sqlite3.Connection, thesis: dict, today: date | None = None) -> dict:
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "examined": 0, "examined_requests": 0,
             "discovered": 0, "samples": []}
    _refresh(conn, thesis, stats)
    conn.commit()
    _discover(conn, thesis, stats, today or date.today())
    conn.commit()
    stats["companies"] += stats["discovered"]
    return stats


def _load_thesis() -> dict:
    try:
        from radar import thesis as t
        return t.load()
    except ImportError:
        import os
        import yaml
        root = Path(__file__).resolve().parents[2]
        return yaml.safe_load((root / os.environ.get("RADAR_THESIS", "config/thesis.yaml")).read_text(encoding="utf-8"))


if __name__ == "__main__":
    from radar import db
    res = run(db.connect(), _load_thesis())
    samples = res.pop("samples")
    print(res)
    for s in samples[:5]:
        print(s)
