"""EU Funding and Tenders reference data (grantsTenders.json) -> eu_grant signals per Finnish beneficiary per grant.

INSPECTED 16 Oct 2026 (130 MB file, downloaded on the VPS). FINDING: the file is a CALL AND TOPIC CATALOGUE, not a grant
register. Shape: {"fundingData": {"GrantTenderObj": [ ...11224 records ]}}. Record keys: type (1 = grant topic, 10225
records; 0 = tender, 999), identifier (topic id, e.g. EMFAF-2021-PIA-FLAGSHIP-ATLANTIC), title, callIdentifier, callTitle,
frameworkProgramme {id, abbreviation, description} (H2020 3855, HORIZON 3573, ERASMUS2027 283, CEF2027 262, LIFE2027 196
...), programmeDivision, status, deadlineDatesLong, publicationDateLong / plannedOpeningDateLong (epoch ms), tags,
keywords, destination, links, contractingAuthority (tenders only). There is NO beneficiary, participant, organisation,
country, PIC, VAT, start date or amount field anywhere in the file (grep for beneficiar/participant/organisation/country
finds only words inside descriptions). Nothing in it can be joined to a Finnish company. Probed alternatives
(referenceData/projects.json, grants.json) return 404.

So the live run emits zero eu_grant signals and reports `blocked` with this reason, rather than inventing beneficiaries.
The grant-level join needs a source that lists beneficiaries (the Funding and Tenders project/grant search API or the
Financial Transparency System export); neither was reachable as a static file. The matching code below is kept and is
exercised by the synthetic fixture in tests/test_eu_grants.py: it applies unchanged once a file with a `participants`
list (name, country, optional PIC, VAT, amount) per grant record is supplied, e.g. via `run(conn, thesis, path=...)`.

Dates: a full ISO date is day precision; a bare year becomes YYYY-01-01 with signal_meta date_precision 'year', as
jx11 did for Business Finland. Epoch-ms call dates are never used as a grant date (a call opening is not a grant start).

Signals: one per Finnish beneficiary per grant. Confidence high when a VAT number maps to a Y-tunnus we hold,
otherwise medium (exact folded legal name). source_url is the reference file URL plus '#<grant id>'; the grant id is
also in the detail. Unmatched Finnish beneficiaries become discovery companies only when the grant sits in a blue-economy
programme (BLUE_PROGRAMMES) AND the beneficiary name, grant title or acronym hits a thesis keyword; they need a usable
VAT number for a Y-tunnus key, otherwise they are skipped. Dedupe: a company that already has a CORDIS eu_project signal
for the same project acronym or id keeps that one and gets a note appended to its detail instead of a second signal.

Download: data/cache/eu/grantsTenders.json (gitignored), resume-capable curl, never committed. 403/429 means BLOCKED:
the adapter returns counts with `blocked` set and exits cleanly. Parsing streams with ijson when installed.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from radar import emit
from radar.adapters.cordis import fold, parse_amount, vat_to_ytunnus
from radar.fit import matched_keywords

NAME = "eu_grants"
PHASE = 2  # after cordis (phase 1) so the eu_project dedupe sees its rows
ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "data" / "cache" / "eu"
FILE_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
SIGNAL_TYPE = "eu_grant"
BLUE_PROGRAMMES = ("emfaf", "blueinvest", "cl6", "cluster 6")
RECORD_LISTS = ("fundingData.GrantTenderObj", "grants", "projects", "items", "results", "data")

# Aliases tried in order. The real file has "frameworkProgramme" (a dict) and "callIdentifier"/"identifier" only; the
# participant aliases are for a beneficiary-level file (see docstring) and are not present in grantsTenders.json.
FIELDS = {
    "id": ("identifier", "grantId", "grant_id", "id", "projectId", "projectNumber", "grantAgreementNumber"),
    "acronym": ("acronym", "projectAcronym"),
    "title": ("title", "projectTitle", "name"),
    "programme": ("programme", "programmeName", "fundingProgramme", "frameworkProgramme", "programmeAbbreviation"),
    "call": ("callIdentifier", "call", "callId", "topic"),
    "start": ("startDate", "grantStartDate", "signatureDate", "grantSignatureDate", "startYear"),
    "parts": ("participants", "beneficiaries", "organisations", "organizations", "partners"),
    "p_name": ("legalName", "name", "organisationName", "beneficiaryName"),
    "p_country": ("country", "countryCode", "countryIsoCode"),
    "p_pic": ("pic", "picNumber"),
    "p_vat": ("vatNumber", "vat"),
    "p_amount": ("euContribution", "ecContribution", "grantedAmount", "amount", "requestedGrant"),
}


def pick(rec: dict, key: str):
    for a in FIELDS[key]:
        v = rec.get(a)
        if isinstance(v, dict):
            v = v.get("abbreviation") or v.get("description")
        if v not in (None, "", []):
            return v
    return None


def parse_start(v) -> tuple[str | None, str | None]:
    """-> (ISO date, precision) or (None, None). A bare year is year precision; nothing is invented."""
    s = str(v or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "day"
    if re.fullmatch(r"(19|20)\d{2}", s):
        return f"{s}-01-01", "year"
    return None, None


def is_finland(country) -> bool:
    return str(country or "").strip().upper() in ("FI", "FIN", "FINLAND", "SUOMI")


def is_blue(programme, call) -> bool:
    text = f"{programme or ''} {call or ''}".casefold()
    return any(k in text for k in BLUE_PROGRAMMES)


def _dig(d, dotted: str):
    for part in dotted.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d


def iter_grants(path: Path):
    """Yield grant dicts. Streams with ijson when available (top-level array or the first RECORD_LISTS key)."""
    try:
        import ijson
    except ImportError:
        ijson = None
    if ijson:
        for prefix in ("item", *(f"{k}.item" for k in RECORD_LISTS)):
            n = 0
            with open(path, "rb") as f:
                for rec in ijson.items(f, prefix):
                    n += 1
                    yield rec
            if n:
                return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = next((v for k in RECORD_LISTS if isinstance(v := _dig(data, k), list)), [])
    yield from data


def inspect(path: Path) -> str:
    for rec in iter_grants(path):
        return f"first record keys: {sorted(rec)}" + (f"; first participant keys: {sorted(p)}" if isinstance((p := (pick(rec, 'parts') or [None])[0]), dict) else "")
    return "no records found"


def download(cache: Path = CACHE, url: str = FILE_URL) -> dict:
    """Resume-capable curl to data/cache/eu. Never raises: returns {path, blocked, error}."""
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / "grantsTenders.json"
    r = subprocess.run(["curl", "-sS", "-L", "-C", "-", "-A", UA, "-o", str(dest), "-w", "%{http_code}", "--max-time", "900", url],
                       capture_output=True, text=True)
    code = r.stdout.strip()
    if r.returncode != 0 or code in ("403", "429"):
        return {"path": None, "blocked": f"{url}: {(r.stderr or 'HTTP ' + code).strip()}", "error": None}
    return {"path": dest, "blocked": None, "error": None}


def _note_dedupe(conn, key: str, acronym: str | None, gid: str | None) -> bool:
    """True when this company already has a CORDIS eu_project for the same acronym or id; the note goes on that row."""
    for r in conn.execute("SELECT id, detail, source_url FROM signals WHERE company_key=? AND signal_type='eu_project' AND adapter='cordis'", (key,)):
        d = r["detail"] or ""
        same = (acronym and d.startswith(f"{acronym}:")) or (gid and re.search(rf"/project/id/{re.escape(str(gid))}$", r["source_url"]))
        if same:
            note = f" Also listed in EU Funding and Tenders reference data (grant {gid})."
            if note not in d:
                conn.execute("UPDATE signals SET detail=? WHERE id=?", (d + note, r["id"]))
            return True
    return False


def run(conn: sqlite3.Connection, thesis: dict, path: Path | None = None) -> dict:
    t0 = time.time()
    c = {"grants": 0, "grants_with_beneficiaries": 0, "finnish_beneficiaries": 0, "signals": 0, "signals_by_programme": {}, "discovery_companies": 0,
         "deduped_against_cordis": 0, "skipped_no_date": 0, "skipped_no_id": 0, "skipped_unmatched": 0, "blocked": None, "seconds": 0.0}
    if path is None:
        dl = download()
        c["blocked"] = dl["blocked"] or dl["error"]
        path = dl["path"]
    if path is None or not Path(path).exists():
        c["seconds"] = round(time.time() - t0, 1)
        return c
    by_y = {r[0]: r[1] for r in conn.execute("SELECT y_tunnus, company_key FROM companies WHERE y_tunnus IS NOT NULL")}
    by_name: dict[str, str] = {}
    for r in conn.execute("SELECT company_key, name FROM companies"):
        by_name.setdefault(fold(r[1]), r[0])
    disc: set[str] = set()
    new_ids: list[tuple[str, str, str, str]] = []
    for g in iter_grants(Path(path)):
        c["grants"] += 1
        gid = pick(g, "id")
        prog, call = pick(g, "programme"), pick(g, "call")
        acr, title = pick(g, "acronym"), pick(g, "title")
        parts = pick(g, "parts") or []
        c["grants_with_beneficiaries"] += bool(parts)
        for p in parts:
            if not isinstance(p, dict) or not is_finland(pick(p, "p_country")):
                continue
            c["finnish_beneficiaries"] += 1
            name = str(pick(p, "p_name") or "").strip()
            if not gid:
                c["skipped_no_id"] += 1
                continue
            date, prec = parse_start(pick(g, "start"))
            if not date or not name:
                c["skipped_no_date"] += 1
                continue
            ytj = vat_to_ytunnus(pick(p, "p_vat"))
            key, conf = (by_y[ytj], "high") if ytj in by_y else (by_name.get(fold(name)), "medium")
            if key is None:
                hit = None
                if is_blue(prog, call):
                    hit = next(iter(matched_keywords(f"{name} {title or ''} {acr or ''}", thesis)), None)
                if not hit or not ytj:
                    c["skipped_unmatched"] += 1
                    continue
                key, conf = ytj, "medium"
                emit.upsert_company(conn, company_key=key, name=name, source_url=f"{FILE_URL}#{gid}", y_tunnus=ytj, country="FI", group_tag="feed")
                by_y[ytj] = key
                by_name.setdefault(fold(name), key)
                disc.add(key)
            if _note_dedupe(conn, key, acr, gid):
                c["deduped_against_cordis"] += 1
                continue
            amount = parse_amount(pick(p, "p_amount"))
            detail = (f"EU grant {gid}" + (f" {acr}" if acr else "") + (f": {title}" if title else "") +
                      f" ({prog or 'programme not stated'}" + (f", call {call}" if call else "") + f"), EU contribution "
                      f"{'not stated' if amount is None else f'EUR {amount:,.0f}'}, start {pick(g, 'start')}"
                      + (", year only" if prec == "year" else "") + f". Matched by {'VAT number' if conf == 'high' else 'exact legal name'}.")
            url = f"{FILE_URL}#{gid}"
            if emit.emit_signal(conn, company_key=key, signal_type=SIGNAL_TYPE, date=date, source_url=url, confidence=conf,
                                adapter=NAME, detail=detail, amount_eur=amount):
                c["signals"] += 1
                label = str(prog or "unknown")
                c["signals_by_programme"][label] = c["signals_by_programme"].get(label, 0) + 1
                new_ids.append((key, date, url, prec))
    for key, date, url, prec in new_ids:
        if prec == "year":
            conn.execute("INSERT OR REPLACE INTO signal_meta (signal_id, date_precision) SELECT id, 'year' FROM signals "
                         "WHERE company_key=? AND signal_type=? AND date=? AND source_url=?", (key, SIGNAL_TYPE, date, url))
    c["discovery_companies"] = len(disc)
    if c["grants"] and not c["grants_with_beneficiaries"]:
        c["blocked"] = ("grantsTenders.json is a call and topic catalogue: none of its %d records lists beneficiaries, "
                        "so no company can be joined to a grant (see module docstring)" % c["grants"])
    conn.commit()
    c["seconds"] = round(time.time() - t0, 1)
    return c


def main(argv: list[str]) -> int:
    if "--inspect" in argv:
        p = CACHE / "grantsTenders.json"
        print(inspect(p) if p.exists() else f"{p} not downloaded")
        return 0
    from radar import db, thesis as thesis_mod
    th = thesis_mod.load()
    conn = db.connect(thesis_mod.db_path(th))
    c = run(conn, th)
    print(c)
    if c["blocked"]:
        print("BLOCKED:", c["blocked"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
