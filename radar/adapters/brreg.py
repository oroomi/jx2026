"""Norwegian Enhetsregisteret (Brønnøysundregistrene open API, NLOD licence, no key) -> register_entry signals.

  cohort lookup  every declared Norwegian cohort or portfolio company without a business id is searched by name; an exact normalised
                 name that matches one limited company is found, several or near names are ambiguous and listed, nothing is guessed
  live window    (only when NO is an active country of the thesis) limited companies registered in the last 365 days whose NACE code
                 starts with a thesis `nace_codes` entry (low) or whose legal name has a thesis keyword (medium)
Sole proprietorships (ENK) and every non-company form are skipped; bankrupt or dissolving units are skipped. 1 request per 2 s, cached under
data/cache/brreg/. The fetched rows are written to data/fetched/nordic/brreg.json; when the register is unreachable that file is imported
instead, so a machine without network gets the same rows. Run: python3 -m radar.adapters.brreg
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from radar import fit as fit_mod, nordic, thesis as thesis_mod
from radar.adapters import prh
from radar.adapters._fetch import Blocked, cached_get

NAME = "brreg"
PHASE = 1
COUNTRY = "NO"
REGISTER = "the Norwegian Enhetsregisteret"
API = "https://data.brreg.no/enhetsregisteret/api/enheter"
PAGE_URL = "https://data.brreg.no/enhetsregisteret/oppslag/enheter/{}"
FORMS = ("AS", "ASA")  # limited companies; ENK, ANS, DA, NUF, stiftelse and the rest are not companies in the radar's sense
SIZE = 100
MAX_PAGES = 12
MAX_REQUESTS = 400
MAX_CONSECUTIVE_FAILURES = 3
JSON_NAME = "brreg.json"


def normalise(e: dict) -> dict:
    """One register unit as the radar stores it. Missing values stay None; nothing is inferred."""
    site = (e.get("hjemmeside") or "").strip()
    status = "active"
    if e.get("konkurs"):
        status = "bankrupt"
    elif e.get("underAvvikling") or e.get("underTvangsavviklingEllerTvangsopplosning"):
        status = "ended"
    nk = e.get("naeringskode1") or {}
    return {"id": e["organisasjonsnummer"], "name": e["navn"], "form": (e.get("organisasjonsform") or {}).get("kode"),
            "registered": e.get("registreringsdatoEnhetsregisteret"), "founded": e.get("stiftelsesdato"),
            "code": nk.get("kode"), "code_desc": nk.get("beskrivelse"),
            "website": (site if site.startswith(("http://", "https://")) else f"https://{site}") if site else None,
            "url": PAGE_URL.format(e["organisasjonsnummer"]), "status": status,
            "city": (e.get("forretningsadresse") or {}).get("kommune")}


def search(params: dict, stats: dict) -> tuple[list[dict], int]:
    """(units, total pages) of one result page; raises Blocked when the register cannot be reached."""
    data, net = cached_get(NAME, API, interval=2.0, params=params)
    stats["requests"] += net
    return (data.get("_embedded") or {}).get("enheter", []), (data.get("page") or {}).get("totalPages", 0)


def lookup(wanted: str, stats: dict) -> dict:
    """Cohort lookup of one name. Candidates are limited companies only."""
    units, _ = search({"navn": wanted, "size": 20}, stats)
    cands = [normalise(u) for u in units if (u.get("organisasjonsform") or {}).get("kode") in FORMS]
    return nordic.decide(wanted, cands)


def _reason(u: dict, thesis: dict, prefixes: list[str]) -> tuple[str, str] | None:
    hits = fit_mod.matched_keywords(u["name"], thesis)
    if hits:
        return f"the legal name has the thesis word '{hits[0]}'", "medium"
    if u["code"] and any(u["code"].startswith(p) for p in prefixes):
        return f"NACE code {u['code']} ({u['code_desc']}) is on the thesis list", "low"
    return None


def live_window(thesis: dict, today: date, stats: dict) -> list[dict]:
    """Limited companies registered in the last 365 days under the thesis NACE prefixes or name keywords."""
    prefixes = [str(c["code"]) for c in thesis.get("nace_codes") or []]
    window = {"fraRegistreringsdatoEnhetsregisteret": (today - timedelta(days=365)).isoformat(),
              "tilRegistreringsdatoEnhetsregisteret": today.isoformat()}
    queries = [{"naeringskode": p} for p in prefixes] + [{"navn": k} for k in prh.thesis_keywords(thesis)]
    seen: dict[str, dict] = {}
    failures = 0
    for q in queries:
        for page in range(MAX_PAGES):
            if stats["requests"] >= MAX_REQUESTS:
                return list(seen.values())
            try:
                units, pages = search({**q, **window, "size": SIZE, "page": page}, stats)
            except Blocked:
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    stats["blocked"] = 1
                    return list(seen.values())
                break
            failures = 0
            for e in units:
                u = normalise(e)
                if u["form"] not in FORMS or u["status"] != "active" or not u["registered"] or u["id"] in seen:
                    continue
                if "TVANGSAVVIKLINGSBO" in u["name"].upper() or nordic.person_or_partner(u["name"], thesis):
                    continue
                r = _reason(u, thesis, prefixes)
                if r:
                    seen[u["id"]] = {**u, "reason": r[0], "confidence": r[1]}
            if page + 1 >= pages:
                break
    return list(seen.values())


def collect(conn: sqlite3.Connection, thesis: dict, today: date, stats: dict) -> dict:
    cohort = []
    for t in nordic.targets(conn, COUNTRY):
        res = lookup(t["name"], stats)
        cohort.append({"company_key": t["company_key"], "name": t["name"], "group": t["group_tag"], **res})
    rows = live_window(thesis, today, stats) if COUNTRY in thesis_mod.countries(thesis) else None
    return {"register": NAME, "fetched_at": nordic.now(), "window": {"start": (today - timedelta(days=365)).isoformat(), "end": today.isoformat()},
            "cohort": cohort, "rows": rows or [], "live_window_run": rows is not None}


def run(conn: sqlite3.Connection, thesis: dict, today: date | None = None, path=None, offline: bool = False) -> dict:
    path = path or nordic.fetched_dir() / JSON_NAME
    today = today or date.today()
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "blocked": 0, "found": 0, "not_found": 0, "ambiguous": 0, "source": "register"}
    data = None
    if not offline:
        try:
            data = collect(conn, thesis, today, stats)
        except Blocked:
            stats["blocked"] = 1
        if data is not None and not stats["blocked"]:
            nordic.write_json(path, data)
    if data is None or stats["blocked"] and not data.get("cohort"):
        data = nordic.read_json(path)
        stats["source"] = "committed JSON" if data else "none"
        if data is None:
            return stats
    c = nordic.import_cohort(conn, data, NAME, REGISTER, COUNTRY)
    r = nordic.import_rows(conn, thesis, data, NAME, REGISTER, COUNTRY, "no")
    stats.update(found=c["found"], not_found=c["not_found"], ambiguous=c["ambiguous"], companies=r["companies"] + c["found"],
                 signals=c["signals"] + r["signals"], skipped=r["skipped"])
    return stats


if __name__ == "__main__":
    from radar import db
    print(run(db.connect(), prh._load_thesis()))
