"""Field candidates (jx40): every value a source states for a company field, kept side by side instead of choosing one.

For eight company fields that more than one source can supply (name, founded, industry_code, industry_desc, town, website,
register_status, country) this writes one row per candidate value into `field_candidates` (radar/schema/060_field_candidates.sql):
the value as the source states it, the source adapter, a link a human can open, the date the source was read, the rule that
picks the value live pages show (A1 in PROJECT_RULES.md: the PRH register is the one source of record) and the rule that
defines the field. Candidates are compared under A28; the country code format is A29.

It reads only what the store and the files in this checkout already hold, never the network:
  store            the companies table (the applied value, what live pages show today)
  prh              cached PRH/YTJ API v3 records under data/cache/<adapter>/*.json (any adapter that cached them)
  declared         data/declared/cohort_portfolio_companies.csv (declared name and the YTJ columns)
  universe         data/declared/startups_universe.csv (rows whose company is in the store)
  businessfinland  data/declared/businessfinland.xlsx, organisation name per Business ID
  hilma            the Hilma awards file's company profiles, read-only, when the file exists on this machine
  cordis           the participant name CORDIS states, from the store's eu_project signal details
  ecosystem        data/declared/ecosystem/blue_economy_fi.sqlite, the `entity` table only (organisations); the
                   `person` table and every person column are never read
  blueinvest       the store's blueinvest_profiles rows
  brreg, cvr       data/fetched/nordic/{brreg,cvr}.json, the cohort register matches

Names shaped like a private person's name (fit.looks_like_person) are never written, and a company whose name is
person-shaped gets no rows at all. It changes nothing a page shows: no route or template reads this table, and the
companies table is only read. Run it on a copy of a store:

  RADAR_DB=/tmp/radar_copy.sqlite python3 -m radar.candidates build
  RADAR_DB=/tmp/radar_copy.sqlite python3 -m radar.candidates report      # conflicts by field, with examples and counts
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from radar import emit, fit, store
from radar import thesis as thesis_mod
from radar import town as town_mod

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schema" / "060_field_candidates.sql"
DECLARED = ROOT / "data" / "declared"
COHORT_CSV = DECLARED / "cohort_portfolio_companies.csv"
UNIVERSE_CSV = DECLARED / "startups_universe.csv"
BF_XLSX = DECLARED / "businessfinland.xlsx"
ECO_DB = DECLARED / "ecosystem" / "blue_economy_fi.sqlite"
NORDIC = ROOT / "data" / "fetched" / "nordic"
CACHE = ROOT / "data" / "cache"

FIELDS = ("name", "founded", "industry_code", "industry_desc", "town", "website", "register_status", "country")
# PROJECT_RULES.md ids. A1: one source of record; only the PRH register overwrites company facts, every other source only
# matches an existing company or inserts a new one, so the value live pages show is the register's when it has one.
WINNING_RULE = "A1"
FIELD_RULE = {"name": "A1", "founded": "A18", "industry_code": "A1", "industry_desc": "A1", "town": "A1",
              "website": "A1", "register_status": "A1", "country": "A29"}
COMPARE_RULE = "A28"  # how two candidates of one field are compared (norm, same, clusters below)
SOURCES = ("store", "prh", "declared", "universe", "businessfinland", "hilma", "cordis", "ecosystem", "blueinvest", "brreg", "cvr")
STATUSES = ("applied", "agrees", "differs", "not_comparable", "store_empty", "PENDING_DECISION")
_PREC_LEN = {"year": 4, "month": 7, "day": 10}
_BIZ = re.compile(r"^\d{7}-\d$")
_ISO = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
# Register status words of every source, in the store's vocabulary (A13). A word missing here is kept as the source states it.
STATUS_WORDS = {"active": "active", "registered": "active", "ended": "ended", "defunct": "ended", "bankrupt": "bankrupt",
                "dormant_unverified": "unknown", "unknown": "unknown"}


# ---------------------------------------------------------------- comparison rules (one per field)

def norm(field: str, value: str) -> str:
    """The form two candidates of one field are compared in."""
    v = str(value).strip()
    if field == "name":
        return store.name_key(v)
    if field == "industry_code":
        return re.sub(r"\D", "", v)
    if field == "website":
        host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", v.casefold()).split("/")[0].split("?")[0]
        return host.removeprefix("www.").rstrip(".")
    if field == "register_status":
        return STATUS_WORDS.get(v.casefold(), v.casefold())
    if field == "country":
        return v.upper()
    if field == "founded":
        return v
    if field == "town":  # "Piikkio (Kaarina)" and "Piikkiö" name one post office: diacritics and a bracketed note are dropped
        v = unicodedata.normalize("NFKD", re.sub(r"\s*\([^)]*\)", "", v))
        v = "".join(ch for ch in v if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", v).strip().casefold()


def precision_of(iso: str) -> str | None:
    return {4: "year", 7: "month", 10: "day"}.get(len(iso)) if _ISO.match(iso or "") else None


def same(field: str, a: dict, b: dict) -> bool | None:
    """True when two candidates say the same thing under the field's rule; None when they cannot be compared
    (industry descriptions in two languages)."""
    if field == "founded":
        n = min(_PREC_LEN.get(a.get("precision") or "day", 10), _PREC_LEN.get(b.get("precision") or "day", 10))
        return a["value_norm"][:n] == b["value_norm"][:n]
    if field == "industry_desc" and (a.get("lang") is None or b.get("lang") is None or a["lang"] != b["lang"]):
        return None
    return a["value_norm"] == b["value_norm"]


def clusters(field: str, rows: list[dict]) -> list[list[dict]]:
    """Group candidates that agree. Two or more groups = a conflict on this field."""
    out: list[list[dict]] = []
    for r in rows:
        for g in out:
            if all(same(field, r, x) is not False for x in g) and any(same(field, r, x) for x in g):
                g.append(r)
                break
        else:
            out.append([r])
    if field == "industry_desc":  # only descriptions in one language can disagree
        langs: dict[str, int] = {}
        for g in out:
            lg = g[0].get("lang")
            if lg:
                langs[lg] = langs.get(lg, 0) + 1
        if not any(n > 1 for n in langs.values()):
            return [sum(out, [])] if out else []
    return out


# ---------------------------------------------------------------- helpers

def _http(*values) -> str | None:
    for v in values:
        v = (v or "").strip() if isinstance(v, str) else ""
        if v.startswith(("http://", "https://")):
            return v
    return None


def _file_date(p: Path) -> str | None:
    """The date a declared file was last changed: its last commit date, else its modification date (UTC)."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cs", "--", str(p)], capture_output=True,
                             text=True, timeout=10).stdout.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", out):
            return out
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).date().isoformat()
    except OSError:
        return None


def _mtime_date(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).date().isoformat()


class Index:
    """The store's companies, looked up by Business ID, folded name and website host."""

    def __init__(self, conn: sqlite3.Connection, th: dict):
        from radar.adapters import ecosystem as eco
        self.eco = eco
        cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
        extra = ", town, town_source_url" if {"town", "town_source_url"} <= cols else ""
        self.rows = {r["company_key"]: dict(r) for r in conn.execute(
            f"SELECT company_key, name, y_tunnus, country, founded, industry_code, industry_desc, website, register_status, "
            f"source_url, fetched_at, group_tag{extra} FROM companies")}
        self.th = th
        self.person = {k for k, r in self.rows.items() if fit.looks_like_person(r["name"] or "", th)}
        self.by_biz, self.by_name, self.by_dom = {}, {}, {}
        for k, r in sorted(self.rows.items(), key=lambda kv: kv[1]["group_tag"] not in ("cohort", "portfolio")):
            if r["y_tunnus"]:
                self.by_biz.setdefault(r["y_tunnus"], k)
            for v in eco.name_variants(r["name"] or ""):
                self.by_name.setdefault(v, k)
            d = eco.domain(r["website"])
            if d:
                self.by_dom.setdefault(d, k)

    def match(self, biz: str | None = None, name: str | None = None, website: str | None = None) -> str | None:
        return self.eco._match_company(None, {"business_id": biz, "name": name or "", "website": website},
                                       self.by_biz, self.by_name, self.by_dom)

    def person_name(self, name: str | None) -> bool:
        return bool(name) and fit.looks_like_person(name, self.th)


def _row(key, field, value, source, url, observed, basis, precision=None, lang=None) -> dict | None:
    if value is None or str(value).strip() == "" or not url or not basis:
        return None
    value = str(value).strip()
    if field == "founded":
        if not _ISO.match(value):
            return None
        precision = precision or precision_of(value)
    return {"company_key": key, "field": field, "value": value, "value_norm": norm(field, value), "precision": precision,
            "lang": lang, "source": source, "source_url": url, "observed": observed, "basis": basis}


# ---------------------------------------------------------------- sources

def from_store(ix: Index):
    for k, r in ix.rows.items():
        obs = (r["fetched_at"] or "")[:10] or None
        url = r["source_url"]
        for f in ("name", "founded", "industry_code", "industry_desc", "website", "register_status", "country"):
            yield _row(k, f, r[f], "store", url, obs, "value in the companies table")
        if r.get("town"):
            yield _row(k, "town", r["town"], "store", r.get("town_source_url") or url, obs, "value in the companies table")


def prh_records(cache_dirs: list[Path], wanted: set[str]) -> dict[str, tuple[dict, str]]:
    """Business ID -> (latest cached PRH company record, fetch date), for the IDs in `wanted` only."""
    best: dict[str, tuple[dict, str, float]] = {}
    for d in cache_dirs:
        for f in sorted(d.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict) or not isinstance(data.get("companies"), list):
                continue
            mt = f.stat().st_mtime
            for c in data["companies"]:
                bid = ((c or {}).get("businessId") or {}).get("value")
                if bid in wanted and (bid not in best or mt > best[bid][2]):
                    best[bid] = (c, _mtime_date(f), mt)
    return {k: (c, d) for k, (c, d, _) in best.items()}


def from_prh(ix: Index, cache_dirs: list[Path]):
    from radar.adapters import prh
    keys = {r["y_tunnus"]: k for k, r in ix.rows.items() if r["y_tunnus"]}
    for bid, (c, obs) in prh_records(cache_dirs, set(keys)).items():
        k = keys[bid]
        url = prh._url({"businessId": bid})
        p = prh.parse(c)
        yield _row(k, "name", p["name"], "prh", url, obs, "legal name (main name, PRH)")
        for n in c.get("names") or []:
            if str(n.get("type")) in ("2", "3") and not n.get("endDate") and not ix.person_name(n.get("name")):
                yield _row(k, "name", n.get("name"), "prh", url, obs,
                           "parallel name (PRH)" if str(n.get("type")) == "2" else "auxiliary name (PRH)")
        yield _row(k, "founded", p["founded"], "prh", url, obs, "Business ID registration date (PRH)", "day")
        mbl = c.get("mainBusinessLine") or {}
        code_set = mbl.get("typeCodeSet")
        yield _row(k, "industry_code", p["industry_code"], "prh", url, obs,
                   f"main business line (PRH, code set {code_set})" if code_set else "main business line (PRH)")
        descs = {str(d.get("languageCode")): d.get("description") for d in mbl.get("descriptions") or []}
        lang = next((lg for code, lg in (("3", "en"), ("1", "fi"), ("2", "sv")) if descs.get(code) == p["industry_desc"]), None)
        yield _row(k, "industry_desc", p["industry_desc"], "prh", url, obs, "main business line description (PRH)", lang=lang)
        town, kind = town_mod.of(c)
        yield _row(k, "town", town, "prh", url, obs, f"post office of the {kind} address (PRH)" if kind else None)
        yield _row(k, "website", p["website"], "prh", url, obs, "website field (PRH)")
        yield _row(k, "register_status", p["register_status"], "prh", url, obs, "derived from situations and register entries (PRH)")
        # the store's description language, when it equals one of the register's three descriptions
        yield {"_lang_hint": True, "company_key": k, "descs": {lg: descs.get(code) for code, lg in (("3", "en"), ("1", "fi"), ("2", "sv"))}}


def from_declared(ix: Index):
    from radar.adapters import declared
    if not COHORT_CSV.is_file():
        return
    obs = _file_date(COHORT_CSV)
    with open(COHORT_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r["company"].strip()
            ytj = r["y_tunnus"].strip() or None
            country = r["country"].strip()[:2].upper() or None
            key = ytj or declared.slug(country or "xx", name)
            url = _http(r["ytj_source"], r["website"], r["customers_url"])
            if key not in ix.rows or not url:
                continue
            if not ix.person_name(name):
                yield _row(key, "name", name, "declared", url, obs, "name as declared")
            if r["ytj_name"].strip() and not ix.person_name(r["ytj_name"]):
                yield _row(key, "name", r["ytj_name"], "declared", url, obs, "legal name as declared (from YTJ)")
            reg = r["ytj_registration_date"].strip()
            yield _row(key, "founded", reg if re.fullmatch(r"\d{4}-\d{2}-\d{2}", reg) else None, "declared", url, obs,
                       "registration date as declared (from YTJ)", "day")
            yield _row(key, "industry_code", r["ytj_industry_code"], "declared", url, obs, "industry code as declared (from YTJ)")
            yield _row(key, "industry_desc", r["ytj_industry_desc"], "declared", url, obs, "industry as declared (from YTJ)", lang="en")
            m = re.search(r"\b\d{5}\s+(.+)$", r["ytj_address"].strip())
            yield _row(key, "town", town_mod.clean_city(m.group(1)) if m else None, "declared", url, obs, "town in the declared YTJ address")
            yield _row(key, "website", _http(r["website"]), "declared", url, obs, "website as declared")
            yield _row(key, "register_status", declared._status(r["ytj_status"]), "declared", url, obs, "status as declared (from YTJ)")
            yield _row(key, "country", country, "declared", url, obs, "country as declared")


def from_universe(ix: Index):
    if not UNIVERSE_CSV.is_file():
        return
    obs = _file_date(UNIVERSE_CSV)
    with open(UNIVERSE_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            biz = (r.get("y_tunnus_if_found") or "").strip()
            key = ix.match(biz if _BIZ.match(biz) else None, r["name"], r.get("website"))
            url = _http(r.get("source_url"), r.get("website"))
            if not key or not url or ix.person_name(r["name"]):
                continue
            yield _row(key, "name", r["name"], "universe", url, obs, "name in the startup universe list")
            yield _row(key, "founded", (r.get("founded") or "").strip() or None, "universe", url, obs, "founded in the startup universe list")
            yield _row(key, "town", (r.get("city") or "").strip() or None, "universe", url, obs, "city in the startup universe list")
            yield _row(key, "website", _http(r.get("website")), "universe", url, obs, "website in the startup universe list")


def from_businessfinland(ix: Index, path: Path = BF_XLSX):
    from radar.adapters import businessfinland as bf
    if not path.is_file():
        return
    keys = {r["y_tunnus"]: k for k, r in ix.rows.items() if r["y_tunnus"]}
    obs = _file_date(path)
    rows = bf._read_rows(path)
    cols = None
    for row in rows:
        m = bf.map_headings(row)
        if "name" in m and "y_tunnus" in m:
            cols = m
            break
    if cols is None:
        return
    seen: set[tuple[str, str]] = set()
    for row in rows:
        bid = bf.norm_ytunnus(row[cols["y_tunnus"]] if cols["y_tunnus"] < len(row) else None)
        name = row[cols["name"]] if cols["name"] < len(row) else None
        if bid not in keys or not name or (bid, str(name)) in seen or ix.person_name(str(name)):
            continue
        seen.add((bid, str(name)))
        yield _row(keys[bid], "name", str(name), "businessfinland", bf.DASHBOARD_URL, obs, "organisation name in the funding export")


def from_hilma(ix: Index, conn: sqlite3.Connection):
    """Company profiles in the Hilma awards file (read-only), for companies with a Hilma signal; skipped when the file is absent."""
    from radar.adapters import hilma
    links = {}
    for r in conn.execute("SELECT company_key, MIN(source_url) FROM signals WHERE adapter='hilma' GROUP BY company_key"):
        links[r[0]] = r[1]
    keys = {ix.rows[k]["y_tunnus"]: k for k in links if k in ix.rows and ix.rows[k]["y_tunnus"]}
    if not keys:
        return
    try:
        src = hilma.open_awards_ro()
        obs = _mtime_date(Path(hilma.AWARDS_DB_URI.split("file:", 1)[1].split("?", 1)[0]))
        prof = src.execute("SELECT businessId, name, officialName, tolCode, tolDesc, website, registered FROM companies").fetchall()
    except (sqlite3.Error, OSError):
        return
    for p in prof:
        k = keys.get(p["businessId"])
        if not k:
            continue
        url = links[k]
        for n, basis in ((p["officialName"], "official name (Hilma company profile)"), (p["name"], "name (Hilma company profile)")):
            if n and not ix.person_name(n):
                yield _row(k, "name", n, "hilma", url, obs, basis)
        reg = str(p["registered"] or "")[:10]
        yield _row(k, "founded", reg if re.fullmatch(r"\d{4}-\d{2}-\d{2}", reg) else None, "hilma", url, obs, "registered (Hilma company profile)", "day")
        yield _row(k, "industry_code", p["tolCode"], "hilma", url, obs, "TOL code (Hilma company profile)")
        yield _row(k, "industry_desc", p["tolDesc"], "hilma", url, obs, "TOL description (Hilma company profile)")
        yield _row(k, "website", _http(p["website"]), "hilma", url, obs, "website (Hilma company profile)")


_CORDIS_NAME = re.compile(r"name '([^']+)' in CORDIS")


def from_cordis(ix: Index, conn: sqlite3.Connection):
    for r in conn.execute("SELECT company_key, source_url, detail, fetched_at FROM signals WHERE adapter='cordis' AND detail LIKE '%in CORDIS%'"):
        m = _CORDIS_NAME.search(r["detail"] or "")
        if m and r["company_key"] in ix.rows and not ix.person_name(m.group(1)):
            yield _row(r["company_key"], "name", m.group(1), "cordis", r["source_url"], (r["fetched_at"] or "")[:10] or None,
                       "participant name (CORDIS)")


def from_ecosystem(ix: Index, path: Path = ECO_DB):
    """Organisations in the declared ecosystem dataset (the entity table only)."""
    if not path.is_file():
        return
    eco = ix.eco
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        urls: dict[str, str] = {}
        for r in src.execute("SELECT entity_id, url FROM source ORDER BY id"):
            urls.setdefault(r["entity_id"], r["url"])
        ents = src.execute("SELECT id, name, business_id, country, city, founded, website, status, last_verified FROM entity").fetchall()
    finally:
        src.close()
    for e in ents:
        biz = (e["business_id"] or "").strip()
        key = ix.match(biz if _BIZ.match(biz) else None, e["name"], e["website"])
        web = _http(e["website"])
        url = web or _http(urls.get(e["id"]))
        if not key or not url or ix.person_name(e["name"]):
            continue
        obs = e["last_verified"]
        yield _row(key, "name", e["name"], "ecosystem", url, obs, "name in the ecosystem dataset")
        yield _row(key, "founded", str(e["founded"]) if e["founded"] else None, "ecosystem", url, obs, "founding year in the ecosystem dataset", "year")
        yield _row(key, "town", e["city"], "ecosystem", url, obs, "city in the ecosystem dataset")
        yield _row(key, "website", web, "ecosystem", url, obs, "website in the ecosystem dataset")
        yield _row(key, "register_status", e["status"], "ecosystem", url, obs, "status in the ecosystem dataset")
        cc = eco.COUNTRIES.get(e["country"] or "Finland")
        yield _row(key, "country", cc, "ecosystem", url, obs,
                   "country in the ecosystem dataset" if e["country"] else "country in the ecosystem dataset (empty, read as Finland)")


def from_blueinvest(ix: Index, conn: sqlite3.Connection):
    from radar.adapters import ecosystem as eco
    for r in conn.execute("SELECT company_key, company_name, country, url, fetched_at FROM blueinvest_profiles"):
        k = r["company_key"]
        if k not in ix.rows or not _http(r["url"]):
            continue
        obs = (r["fetched_at"] or "")[:10] or None
        if not ix.person_name(r["company_name"]):
            yield _row(k, "name", r["company_name"], "blueinvest", r["url"], obs, "company name in the BlueInvest pipeline")
        yield _row(k, "country", eco.COUNTRIES.get(r["country"] or ""), "blueinvest", r["url"], obs, "country in the BlueInvest pipeline")


def from_nordic(ix: Index):
    for adapter, country in (("brreg", "NO"), ("cvr", "DK")):
        p = NORDIC / f"{adapter}.json"
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        obs = (data.get("fetched_at") or "")[:10] or None
        lang = {"brreg": "nb", "cvr": "da"}[adapter]
        for item in data.get("cohort") or []:
            m, k = item.get("match"), item.get("company_key")
            if not m or k not in ix.rows or not _http(m.get("url")) or ix.person_name(m.get("name")):
                continue
            url, reg = m["url"], f"{adapter} register"
            yield _row(k, "name", m.get("name"), adapter, url, obs, f"legal name ({reg})")
            yield _row(k, "founded", m.get("founded"), adapter, url, obs, f"founding date ({reg})", "day")
            yield _row(k, "industry_code", m.get("code"), adapter, url, obs, f"NACE code ({reg})")
            yield _row(k, "industry_desc", m.get("code_desc"), adapter, url, obs, f"NACE description ({reg})", lang=lang)
            yield _row(k, "town", town_mod.clean_city(m.get("city")), adapter, url, obs, f"city ({reg})")
            yield _row(k, "website", _http(m.get("website")), adapter, url, obs, f"website ({reg})")
            yield _row(k, "register_status", m.get("status"), adapter, url, obs, f"status ({reg})")
            yield _row(k, "country", country, adapter, url, obs, f"country of the {reg}")


# ---------------------------------------------------------------- open questions (QUESTIONS_B1.md)

# Issue id -> the question, in a few words. A candidate row that disagrees with the applied value (or stands in for an empty
# store value) and falls under an open issue is marked PENDING_DECISION with that id. Live pages keep A1 until a decision
# (D-id in PROJECT_RULES.md) closes the issue; then the issue leaves OPEN_ISSUES and the decision is recorded in provenance.
# QUESTIONS_B1.md also asks B1-12 to B1-15 (duplicates, dates, amounts, from radar/stop_and_ask.py): no candidate row carries those.
OPEN_ISSUES = {
    "B1-01": "name: the Business Finland export names an organisation differently from the register's current legal name",
    "B1-02": "name: a trading, auxiliary or declared brand name differs from the legal name",
    "B1-03": "name: a bracketed note or a tagline inside a name in a declared list or the BlueInvest pipeline",
    "B1-04": "name: no register record; the CORDIS legal name differs from the declared name",
    "B1-05": "town: the register's post office is a village or postal district, another source names the municipality",
    "B1-06": "town and country: the ecosystem dataset describes a parent company abroad",
    "B1-07": "website: the register's website differs from another source's site",
    "B1-08": "website: a login-walled page (LinkedIn, Facebook) given as a company website",
    "B1-09": "founded: no register record, and two declared lists disagree",
    "B1-10": "industry: a code or description from another code set or source differs from the register's",
    "B1-11": "register status: a declared list's status differs from the register's",
}
_LOGIN = ("linkedin.com", "facebook.com", "dealroom.co", "crunchbase.com", "pitchbook.com", "tracxn.com")


def issue_of(r: dict, group: list[dict]) -> str | None:
    """The open issue a disagreeing candidate row falls under."""
    f, src, v = r["field"], r["source"], r["value"]
    if f == "name":
        if src == "businessfinland":
            return "B1-01"
        if src == "cordis":
            return "B1-04"
        if "(" in v or " - " in v:
            return "B1-03"
        return "B1-02"
    if f in ("town", "country"):
        home = next((x["value_norm"] for x in group if x["field"] == "country" and x["source"] == "store"), None)
        abroad = any(x["field"] == "country" and x["source"] == "ecosystem" and home and x["value_norm"] != home for x in group)
        return "B1-06" if abroad else "B1-05"
    if f == "website":
        h = norm("website", v)
        return "B1-08" if any(h == d or h.endswith("." + d) for d in _LOGIN) else "B1-07"
    return {"founded": "B1-09", "industry_code": "B1-10", "industry_desc": "B1-10", "register_status": "B1-11"}.get(f)


def mark(rows: list[dict]) -> int:
    """Mark PENDING_DECISION on candidate rows in a conflict that an open issue covers. Applied rows are never marked."""
    by: dict[tuple, list[dict]] = {}
    for r in rows:
        by.setdefault((r["company_key"], r["field"]), []).append(r)
    every = [r for g in by.values() for r in g]
    n = 0
    for (key, field), group in by.items():
        gs = clusters(field, group)
        if len(gs) < 2:
            continue
        # the group live pages show: the store's value, else the register's (A1 writes it on the next build)
        applied_group = next((g for g in gs if any(r["applied"] and r["source"] == "store" for r in g)), None) \
            or next((g for g in gs if any(r["source"] in ("prh", "brreg", "cvr") for r in g)), None)
        country_rows = [x for x in every if x["company_key"] == key]
        for g in gs:
            if g is applied_group:
                continue
            for r in g:
                if r["applied"] or r["status"] not in ("differs", "store_empty", "PENDING_DECISION"):
                    continue
                iid = issue_of(r, country_rows)
                if iid in OPEN_ISSUES:
                    r["status"], r["issue_id"] = "PENDING_DECISION", iid
                    n += 1
    return n


# ---------------------------------------------------------------- build

def cache_dirs(extra: list[Path] | None = None) -> list[Path]:
    dirs = [d for d in sorted(CACHE.glob("*")) if d.is_dir()] if CACHE.is_dir() else []
    return dirs + [Path(d) for d in extra or []]


def collect(conn: sqlite3.Connection, th: dict, *, caches: list[Path] | None = None, bf_path: Path = BF_XLSX,
            eco_path: Path = ECO_DB, skip: tuple[str, ...] = ()) -> tuple[list[dict], dict]:
    """Every candidate row, with status set and open questions marked. `skip` leaves sources out (tests skip the
    machine-local ones: prh cache, hilma)."""
    conn.row_factory = sqlite3.Row
    ix = Index(conn, th)
    rows: dict[tuple, dict] = {}
    hints: dict[str, dict] = {}
    read = {s: 0 for s in SOURCES}
    gens = {"store": lambda: from_store(ix), "prh": lambda: from_prh(ix, cache_dirs() if caches is None else caches),
            "declared": lambda: from_declared(ix), "universe": lambda: from_universe(ix),
            "businessfinland": lambda: from_businessfinland(ix, bf_path), "hilma": lambda: from_hilma(ix, conn),
            "cordis": lambda: from_cordis(ix, conn), "ecosystem": lambda: from_ecosystem(ix, eco_path),
            "blueinvest": lambda: from_blueinvest(ix, conn), "nordic": lambda: from_nordic(ix)}
    for g in (make() for name, make in gens.items() if name not in skip):
        for r in g:
            if not r:
                continue
            if r.get("_lang_hint"):
                hints[r["company_key"]] = r["descs"]
                continue
            if r["company_key"] in ix.person:
                continue
            read[r["source"]] += 1
            rows.setdefault((r["company_key"], r["field"], r["source"], r["value_norm"]), r)
    out = list(rows.values())
    for r in out:  # the store's description language, when the register states the same text in one of its languages
        if r["field"] == "industry_desc" and r["source"] == "store":
            for lg, txt in (hints.get(r["company_key"]) or {}).items():
                if txt and norm("industry_desc", txt) == r["value_norm"]:
                    r["lang"] = lg
                    break
    _status(out)
    pending = mark(out)
    return out, {"read": read, "companies": len({r["company_key"] for r in out}), "person_shaped_skipped": len(ix.person),
                 "pending": pending}


def _status(rows: list[dict]) -> None:
    by: dict[tuple, list[dict]] = {}
    for r in rows:
        by.setdefault((r["company_key"], r["field"]), []).append(r)
    for (_, field), group in by.items():
        applied = next((r for r in group if r["source"] == "store"), None)
        for r in group:
            r["rule_id"], r["field_rule"], r["issue_id"] = WINNING_RULE, FIELD_RULE[field], None
            if r is applied:
                r["applied"], r["status"] = 1, "applied"
            elif applied is None:
                r["applied"], r["status"] = 0, "store_empty"
            else:
                s = same(field, r, applied)
                r["applied"] = 1 if s else 0
                r["status"] = "not_comparable" if s is None else "agrees" if s else "differs"


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


def write(conn: sqlite3.Connection, rows: list[dict]) -> int:
    apply_schema(conn)
    now = emit.now_utc()
    conn.execute("DELETE FROM field_candidates")
    conn.executemany(
        """INSERT INTO field_candidates (company_key, field, value, value_norm, basis, precision, lang, source, source_url, observed,
           rule_id, field_rule, applied, status, issue_id, built_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(r["company_key"], r["field"], r["value"], r["value_norm"], r["basis"], r["precision"], r["lang"], r["source"], r["source_url"],
          r["observed"], r["rule_id"], r["field_rule"], r["applied"], r["status"], r["issue_id"], now) for r in rows])
    conn.commit()
    return len(rows)


def load_rows(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute("SELECT * FROM field_candidates ORDER BY company_key, field, source, value")]


def conflicts(rows: list[dict]) -> dict[str, list[dict]]:
    """Field -> [{company_key, groups: [[candidate, ...], ...]}] for every company field with two or more distinct candidates."""
    by: dict[tuple, list[dict]] = {}
    for r in rows:
        by.setdefault((r["company_key"], r["field"]), []).append(r)
    out: dict[str, list[dict]] = {f: [] for f in FIELDS}
    for (key, field), group in sorted(by.items()):
        gs = clusters(field, group)
        if len(gs) >= 2:
            out[field].append({"company_key": key, "groups": gs})
    return out


def report(rows: list[dict], names: dict[str, str] | None = None, examples: int = 3) -> str:
    names = names or {}
    c = conflicts(rows)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    lines = [f"field_candidates: {len(rows):,} rows, {len({r['company_key'] for r in rows}):,} companies; "
             + ", ".join(f"{s} {by_status.get(s, 0):,}" for s in STATUSES),
             "rows by source: " + ", ".join(f"{s} {n:,}" for s, n in sorted(_count(rows, 'source').items(), key=lambda kv: -kv[1])),
             "conflicts (a company field with 2+ distinct candidates; founded compared at the coarser precision, "
             "industry descriptions only within one language):"]
    for f in FIELDS:
        items = c[f]
        pairs: dict[str, int] = {}
        for it in items:
            srcs = " vs ".join(sorted({"+".join(sorted({r["source"] for r in g})) for g in it["groups"]}))
            pairs[srcs] = pairs.get(srcs, 0) + 1
        lines.append(f"  {f}: {len(items):,} companies" + (" (" + "; ".join(f"{p} {n}" for p, n in
                     sorted(pairs.items(), key=lambda kv: -kv[1])[:4]) + ")" if pairs else ""))
        for it in items[:examples]:
            label = names.get(it["company_key"]) or it["company_key"]
            vals = " | ".join(f"{g[0]['value']} [{', '.join(sorted({r['source'] for r in g}))}]" for g in it["groups"])
            lines.append(f"      {it['company_key']} {label}: {vals}")
    pend = _count([r for r in rows if r["status"] == "PENDING_DECISION"], "issue_id")
    lines.append("PENDING_DECISION rows by open issue: " + (", ".join(f"{i} {pend[i]}" for i in sorted(pend)) or "none"))
    total = sum(len(v) for v in c.values())
    lines.append(f"total: {total:,} conflicting company fields on {len({it['company_key'] for v in c.values() for it in v}):,} companies")
    return "\n".join(lines)


def _count(rows, key) -> dict:
    out: dict = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


def _guard(path: Path, allow_live: bool) -> None:
    """Writes go to copies only: refuse the live store files under data/ unless asked in so many words."""
    p = path.resolve()
    if not allow_live and p.parent == (ROOT / "data").resolve() and p.name.startswith("radar"):
        raise SystemExit(f"refusing to write {p}: run on a copy, e.g. cp {p} /tmp/copy.sqlite && RADAR_DB=/tmp/copy.sqlite "
                         "python3 -m radar.candidates build")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.candidates", description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["build", "report"])
    ap.add_argument("--db", type=Path, help="store to read and write (default: RADAR_DB, else the thesis store)")
    ap.add_argument("--thesis", help="thesis file (default: RADAR_THESIS or config/thesis.yaml)")
    ap.add_argument("--cache-dir", action="append", type=Path, help="extra directory of cached PRH JSON (repeatable)")
    ap.add_argument("--examples", type=int, default=3)
    ap.add_argument("--allow-live", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    th = thesis_mod.load(a.thesis)
    path = a.db or thesis_mod.db_path(th)
    if not Path(path).is_file():
        print(f"no store at {path}", file=sys.stderr)
        return 2
    if a.cmd == "build":
        _guard(Path(path), a.allow_live)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    names = {r[0]: r[1] for r in conn.execute("SELECT company_key, name FROM companies")}
    if a.cmd == "build":
        rows, stats = collect(conn, th, caches=cache_dirs(a.cache_dir))
        n = write(conn, rows)
        print(f"wrote {n:,} candidate rows for {stats['companies']:,} companies into {path} "
              f"({stats['person_shaped_skipped']:,} companies with a person-shaped name left out; "
              f"{stats['pending']:,} rows PENDING_DECISION under {len(OPEN_ISSUES)} open issues)")
        print("candidates read per source: " + ", ".join(f"{s} {c:,}" for s, c in stats["read"].items()))
    try:
        rows = load_rows(conn)
    except sqlite3.OperationalError:
        print("no field_candidates table: run `build` first", file=sys.stderr)
        return 2
    print(report(rows, names, a.examples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
