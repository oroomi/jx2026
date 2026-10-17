"""Danish CVR register through cvrapi.dk (terms of 24 May 2019: free use of the data, 50 free lookups per day per IP, a descriptive
User-Agent required, never circumvent the limit by changing IP or hiding the User-Agent) -> register_entry signals.

  cohort lookup  every declared Danish cohort or portfolio company is looked up by the CVR number its declared note states, else by name.
                 The API returns ONE best match per name, so an exact normalised name is found, a near name is ambiguous, nothing is guessed.
  live window    BLOCKED by design: cvrapi.dk has no search by registration date or industry code, and the open Virk CVR index (Elasticsearch)
                 needs credentials we do not hold. Denmark therefore contributes dated cohort companies only.
The run stops at the first QUOTA_EXCEEDED or BANNED answer (the shared egress IP of a cloud session may already be over quota: the
remaining companies are recorded as `blocked`, never retried from another address). Rows go to data/fetched/nordic/cvr.json; when the API
is blocked that file is imported instead. Run: python3 -m radar.adapters.cvr
Sweden (Bolagsverket) has no free API: it is a connector slot, not connected.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import time
from datetime import date
from pathlib import Path

import httpx

from radar import nordic
from radar.adapters import prh
from radar.adapters._fetch import CACHE_ROOT, UA, Blocked

NAME = "cvr"
PHASE = 1
COUNTRY = "DK"
REGISTER = "the Danish CVR register (start date as stated by the register)"
API = "https://cvrapi.dk/api"
PAGE_URL = "https://datacvr.virk.dk/enhed/virksomhed/{}"
DECLARED = nordic.ROOT / "data" / "declared" / "cohort_portfolio_companies.csv"
MAX_LOOKUPS = 40  # of the 50 free per day
JSON_NAME = "cvr.json"
LIVE_BLOCKED = ("cvrapi.dk looks up one company by name or CVR number and has no search by registration date or industry code; "
                "the open Virk CVR index needs credentials we do not hold")
_CVR = re.compile(r"\bCVR\s*(\d{8})\b")
_START = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s*-\s*(\d{4})\s*$")
_last_call = 0.0


def declared_numbers(path: Path = DECLARED) -> dict[str, str]:
    """{casefolded company name: CVR number} for the declared rows whose note states one."""
    out = {}
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                m = _CVR.search(r.get("hq_note") or "")
                if m:
                    out[(r.get("company") or "").strip().casefold()] = m.group(1)
    return out


def parse_start(v) -> str | None:
    """ISO date from cvrapi's 'dd/mm - yyyy'; anything else is None (never guessed)."""
    m = _START.match(str(v or ""))
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    except ValueError:
        return None


def normalise(d: dict) -> dict:
    """One cvrapi answer as the radar stores it; None for a sole proprietorship (not a company)."""
    desc = (d.get("companydesc") or "").strip()
    if "enkeltmand" in desc.casefold() or str(d.get("companycode")) == "10":
        return {}
    start = parse_start(d.get("startdate"))
    ended = bool(d.get("enddate")) or bool(d.get("creditbankrupt"))
    return {"id": str(d["vat"]), "name": d["name"], "form": desc or None, "registered": start, "founded": start,
            "code": str(d["industrycode"]) if d.get("industrycode") else None, "code_desc": d.get("industrydesc"), "website": None,
            "url": PAGE_URL.format(d["vat"]), "status": "ended" if ended else "active", "city": d.get("city")}


def fetch(params: dict, client: httpx.Client | None = None) -> dict | None:
    """One cached lookup. Returns the answer, None when the register has no such company, raises Blocked on a limit or a ban."""
    global _last_call
    q = {**params, "country": "dk", "format": "json"}
    f = CACHE_ROOT / NAME / (hashlib.sha1(json.dumps(q, sort_keys=True).encode()).hexdigest()[:16] + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")) or None
    wait = 2.0 - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=30)
    try:
        try:
            r = client.get(API, params=q)
        except httpx.HTTPError as e:
            raise Blocked(f"{type(e).__name__}: {e}")
        _last_call = time.monotonic()
    finally:
        if own:
            client.close()
    try:
        body = r.json()
    except ValueError:
        raise Blocked(f"HTTP {r.status_code}, not JSON")
    err = body.get("error") if isinstance(body, dict) else None
    if err in ("QUOTA_EXCEEDED", "BANNED"):
        raise Blocked(f"cvrapi.dk answered {err}: {body.get('message', '')}".strip())
    if err == "NOT_FOUND":
        data = None
    elif err:
        raise Blocked(f"cvrapi.dk answered {err}")
    else:
        data = body
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data), encoding="utf-8")
    return data


def lookup(target: dict, numbers: dict[str, str], stats: dict) -> dict:
    cvr = numbers.get(target["name"].casefold())
    raw = fetch({"vat": cvr} if cvr else {"name": target["name"]})
    stats["requests"] += 1
    unit = normalise(raw) if raw else {}
    res = nordic.decide(target["name"], [unit] if unit else [])
    if cvr and unit:
        res["by_number"] = cvr
        if res["status"] != "found":  # the declared number names a company whose register name differs: say so, choose nothing
            res = {"status": "ambiguous", "match": None, "candidates": [unit], "by_number": cvr}
    return res


def collect(conn: sqlite3.Connection, stats: dict) -> dict:
    numbers = declared_numbers()
    cohort, reason = [], None
    for t in nordic.targets(conn, COUNTRY):
        item = {"company_key": t["company_key"], "name": t["name"], "group": t["group_tag"]}
        if reason is None and stats["requests"] < MAX_LOOKUPS:
            try:
                item.update(lookup(t, numbers, stats))
            except Blocked as e:
                reason = str(e)
        if "status" not in item:
            item.update(status="blocked", match=None, candidates=[], blocked=reason or "lookup budget used")
        cohort.append(item)
    return {"register": NAME, "fetched_at": nordic.now(), "cohort": cohort, "rows": [], "live_window_run": False,
            "live_window_blocked": LIVE_BLOCKED, "blocked": reason}


def run(conn: sqlite3.Connection, thesis: dict, today: date | None = None, path=None, offline: bool = False) -> dict:
    path = path or nordic.fetched_dir() / JSON_NAME
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "blocked": 0, "found": 0, "not_found": 0, "ambiguous": 0, "source": "register"}
    data = None
    if not offline:
        data = collect(conn, stats)
        stats["blocked"] = 1 if data["blocked"] else 0
        old = nordic.read_json(path)  # keep an earlier answer when today's run is cut short by the daily limit
        if old:
            prior = {c["company_key"]: c for c in old.get("cohort", []) if c["status"] != "blocked"}
            data["cohort"] = [prior[c["company_key"]] if c["status"] == "blocked" and c["company_key"] in prior else c for c in data["cohort"]]
        if old is None or any(c["status"] != "blocked" for c in data["cohort"]):
            nordic.write_json(path, data)
    if data is None:
        data = nordic.read_json(path)
        stats["source"] = "committed JSON" if data else "none"
        if data is None:
            return stats
    c = nordic.import_cohort(conn, data, NAME, REGISTER, COUNTRY)
    stats.update(found=c["found"], not_found=c["not_found"], ambiguous=c["ambiguous"], companies=c["found"], signals=c["signals"],
                 skipped=c["blocked"])
    return stats


if __name__ == "__main__":
    from radar import db
    print(run(db.connect(), prh._load_thesis()))
