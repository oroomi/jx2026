"""Estonian e-Business Register open data (avaandmed.ariregister.rik.ee) -> register_entry signals.

The register publishes the basic data of every Estonian business as a CSV download (semicolon separated, zipped) with the
registry code, legal name, legal form, status, first-entry date and the main EMTAK activity code. EMTAK 2008 follows NACE
Rev. 2, so the thesis `industry_codes` list is compared with it as written (an assumption: a code outside that list is
simply not a match). Companies (OU, AS) first entered in the last 365 days are kept when the EMTAK code is in the thesis
(LOW: a coarse code) or a legal-name word starts with a thesis keyword (MEDIUM). Never high: this is the same rule as PRH.
Each signal links to the company's public page in the register. Licence and terms: the register's open-data terms of use,
re-use with attribution (CHECK the terms page named in DISCLOSURE.md).

The download goes to data/cache/estonia_register/ once (1 request per 2 s); HTTP 403/429 returns BLOCKED, never a crash.
Run: python3 -m radar.adapters.estonia_register
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import httpx

from radar import emit
from radar import thesis as thesis_mod
from radar.fit import matched_keywords

NAME = "estonia_register"
PHASE = 1
COUNTRY = "EE"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
DOWNLOAD_URL = "https://avaandmed.ariregister.rik.ee/sites/default/files/avaandmed/ettevotja_rekvisiidid__lihtandmed.csv.zip"
COMPANY_URL = "https://ariregister.rik.ee/eng/company/{}"
FORMS = ("OÜ", "AS")
ACTIVE = ("R", "registrisse kantud", "entered into the register")
# Column names are looked up through aliases; a file that lacks a required column reports `bad_header`, it never guesses.
COLUMNS = {
    "name": ("nimi", "ettevotja_nimi", "name"),
    "code": ("ariregistri_kood", "registrikood", "registry_code"),
    "form": ("ettevotja_oiguslik_vorm", "oiguslik_vorm", "legal_form"),
    "status": ("ettevotja_staatus", "staatus", "status"),
    "first": ("ettevotja_esmakande_kpv", "esmakande_kpv", "first_entry_date", "registered"),
    "emtak": ("emtak_kood", "emtak", "evrk_kood", "tegevusala_kood", "main_activity_code"),
    "emtak_text": ("emtak_tekstina", "tegevusala_tekstina", "main_activity"),
}
_DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_DATE_EE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})")


class Blocked(Exception):
    pass


def cache_dir() -> Path:
    return thesis_mod.data_dir() / "cache" / NAME


def parse_date(v) -> str | None:
    """ISO date from 'YYYY-MM-DD...' or 'DD.MM.YYYY'; anything else is None (never guessed)."""
    s = str(v or "").strip()
    m = _DATE_ISO.match(s)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = _DATE_EE.match(s)
    return f"{m[3]}-{m[2]}-{m[1]}" if m else None


def _col(header: list[str], key: str) -> str | None:
    low = {h.strip().lower().lstrip("﻿"): h for h in header}
    return next((low[a] for a in COLUMNS[key] if a in low), None)


def download(dest_dir: Path | None = None, url: str = DOWNLOAD_URL, client: httpx.Client | None = None) -> Path:
    """Fetch the zip once. Raises Blocked on 403/429 and OSError on network trouble."""
    dest_dir = dest_dir or cache_dir()
    dest = dest_dir / "lihtandmed.csv.zip"
    if dest.exists() and zipfile.is_zipfile(dest):
        return dest
    dest_dir.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=300, follow_redirects=True)
    try:
        r = client.get(url)
    finally:
        if own:
            client.close()
    if r.status_code in (403, 429):
        raise Blocked(f"HTTP {r.status_code} from {url}")
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def read_rows(path: Path):
    """Yield dict rows of the first CSV inside the zip (or of a plain CSV)."""
    csv.field_size_limit(1 << 26)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(member) as raw:
                yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), delimiter=";")
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f, delimiter=";")


def run(conn: sqlite3.Connection, thesis: dict, path: Path | None = None, today: date | None = None) -> dict:
    res = {"companies": 0, "signals": 0, "skipped": 0, "examined": 0, "blocked": "", "bad_header": ""}
    if COUNTRY not in thesis_mod.countries(thesis):
        res["note"] = "EE is not an active country of this thesis"
        return res
    if path is None:
        try:
            path = download()
        except Blocked as e:
            res["blocked"] = str(e)
            return res
        except (httpx.HTTPError, OSError) as e:
            res["blocked"] = f"{type(e).__name__}: {e}"
            return res
    today = today or date.today()
    start = (today - timedelta(days=365)).isoformat()
    codes = {str(c["code"]) for c in thesis.get("industry_codes", [])}
    for row_no, r in enumerate(read_rows(Path(path))):
        if row_no == 0:
            cols = {k: _col(list(r), k) for k in COLUMNS}
            missing = [k for k in ("name", "code", "first") if cols[k] is None]
            if missing:
                res["bad_header"] = f"missing columns {missing} in {sorted(r)}"
                return res
        get = lambda k: (r.get(cols[k]) or "").strip() if cols[k] else ""  # noqa: E731
        res["examined"] += 1
        first = parse_date(get("first"))
        if not first or first < start or first > today.isoformat():
            continue
        form, status = get("form"), get("status")
        if (cols["form"] and form not in FORMS) or (cols["status"] and status.lower() not in tuple(a.lower() for a in ACTIVE)):
            continue
        name, code = get("name"), get("code")
        if not name or not re.fullmatch(r"\d{6,10}", code):
            res["skipped"] += 1
            continue
        emtak = get("emtak")
        by_code = emtak in codes
        hits = matched_keywords(name, thesis)
        if not by_code and not hits:
            continue
        key = f"ee-{code}"
        if conn.execute("SELECT 1 FROM signals WHERE company_key=? AND signal_type='register_entry'", (key,)).fetchone():
            continue
        url = COMPANY_URL.format(code)
        why = (f"legal name starts a word with thesis keyword '{hits[0]}'" if hits else f"EMTAK code {emtak} is in the thesis")
        emit.upsert_company(conn, company_key=key, name=name, source_url=url, y_tunnus=None, country=COUNTRY, founded=first,
                            industry_code=emtak or None, industry_desc=get("emtak_text") or None, group_tag="feed",
                            register_status="active")
        if emit.emit_signal(conn, company_key=key, signal_type="register_entry", date=first, source_url=url,
                            confidence="medium" if hits else "low", adapter=NAME,
                            detail=f"Registered in the Estonian e-Business Register on {first} (registry code {code}); matched because {why}."):
            res["signals"] += 1
            res["companies"] += 1
    conn.commit()
    return res


if __name__ == "__main__":
    from radar import db

    th = thesis_mod.load()
    out = run(db.connect(thesis_mod.db_path(th)), th)
    print(out)
    if out["blocked"] or out["bad_header"]:
        print("BLOCKED:", out["blocked"] or out["bad_header"])
