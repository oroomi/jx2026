"""CORDIS bulk CSV (Horizon Europe and Horizon 2020) -> eu_project signals.

Two jobs. (1) Declared cohort and portfolio companies are matched to CORDIS organisation rows: by VAT number to
Y-tunnus (high), by the project link in the team's recon CSV plus closest organisation name (medium, probable),
or by exact folded name (medium). A declared company with no match gets nothing. (2) Discovery: Finnish private
for-profit SMEs in projects starting on or after 2025-01-01 whose organisation name, or project title, keywords or
objective, hits a thesis keyword. Those are low confidence (a keyword) and keyed by the Y-tunnus built from the VAT
number; organisations without a usable VAT number are skipped. Existing companies only get a signal, never an upsert.
The two zips are downloaded once into data/cache/cordis/ (1 request per 2 s); HTTP 403/429 stops with BLOCKED.
"""
from __future__ import annotations

import csv
import difflib
import io
import json
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from radar import emit
from radar.adapters.declared import slug
from radar.fit import matched_keywords

NAME = "cordis"
PHASE = 1
ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "data" / "cache" / "cordis"
DECLARED_CSV = ROOT / "data" / "declared" / "cohort_portfolio_companies.csv"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
SOURCES = {
    "horizon-europe": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "horizon-2020": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
}
PROGRAMME_LABEL = {"HORIZON": "Horizon Europe", "H2020": "Horizon 2020"}
DISCOVERY_FROM = "2025-01-01"
MIN_RATIO = 0.6
PROJECT_URL = "https://cordis.europa.eu/project/id/{}"
_SUFFIX = re.compile(r"\b(oy|oyj|ab|abp|ltd|limited|as|a/s|aps|gmbh|inc|ky|tmi|sl|s l|sa|bv|b v|srl|spa)\b\.?")
_PROJECT_ID = re.compile(r"/project/id/(\d+)")


def fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", s)).strip()


def vat_to_ytunnus(vat) -> str | None:
    m = re.fullmatch(r"FI(\d{8})", re.sub(r"[\s.\-]", "", str(vat or "")).upper())
    return f"{m.group(1)[:7]}-{m.group(1)[7]}" if m else None


def parse_amount(v) -> float | None:
    s = re.sub(r"[^\d,.]", "", str(v or ""))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def money(x: float | None) -> str:
    return "not stated" if x is None else f"EUR {x:,.0f}"


# ---- download -------------------------------------------------------------------------------------------------

def _valid_zip(p: Path) -> bool:
    try:
        return p.exists() and p.stat().st_size > 0 and zipfile.is_zipfile(p)
    except OSError:
        return False


def download(cache: Path = CACHE, sources: dict | None = None, opener=urllib.request.urlopen, pause: float = 2.0) -> dict:
    """Fetch each zip once. Returns {bytes, blocked, errors, paths}. 403/429 stops at once, no retry."""
    cache.mkdir(parents=True, exist_ok=True)
    meta_path = cache / "fetched.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    out = {"bytes": 0, "blocked": None, "errors": [], "paths": {}}
    first = True
    for key, url in (sources or SOURCES).items():
        dest = cache / f"{key}.zip"
        if _valid_zip(dest):
            out["paths"][key] = dest
            continue
        if not first:
            time.sleep(pause)
        first = False
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with opener(req, timeout=120) as resp:
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    while chunk := resp.read(1 << 20):
                        f.write(chunk)
                        out["bytes"] += len(chunk)
                lm = resp.headers.get("Last-Modified") if getattr(resp, "headers", None) else None
            tmp.replace(dest)
            meta[key] = {"url": url, "last_modified": lm, "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
            meta_path.write_text(json.dumps(meta, indent=1))
            out["paths"][key] = dest
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                out["blocked"] = f"HTTP {e.code} from {url}"
                return out
            out["errors"].append(f"HTTP {e.code} from {url}")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            out["errors"].append(f"{url}: {e}")
    return out


# ---- reading --------------------------------------------------------------------------------------------------

def _rows(zpath: Path, member: str):
    csv.field_size_limit(1 << 28)
    with zipfile.ZipFile(zpath) as z:
        with z.open(member) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""), delimiter=";")


def _declared(conn) -> list[dict]:
    """Declared companies: database rows tagged cohort/portfolio, plus the recon cordis_url from the declared CSV."""
    db = {r[0]: {"key": r[0], "name": r[1], "y": r[2]} for r in conn.execute(
        "SELECT company_key,name,y_tunnus FROM companies WHERE group_tag IN ('cohort','portfolio')")}
    recon = {}
    if DECLARED_CSV.exists():
        with open(DECLARED_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = r["company"].strip()
                ytj = r["y_tunnus"].strip() or None
                country = r["country"].strip()[:2].upper() or "xx"
                key = ytj or slug(country, name)
                m = _PROJECT_ID.search(r.get("cordis_url") or "")
                if key in db:
                    db[key]["declared_name"] = name
                    if m:
                        recon[key] = m.group(1)
    for k, pid in recon.items():
        db[k]["recon_project"] = pid
    return list(db.values())


def run(conn: sqlite3.Connection, thesis: dict, zips: dict | None = None) -> dict:
    t0 = time.time()
    counts = {"projects_read": 0, "fi_org_rows": 0, "declared_matched": {"vat": 0, "recon_link": 0, "exact_name": 0},
              "discovery_companies": 0, "signals": 0, "signals_by_programme": {}, "skipped_no_vat": 0,
              "bytes_downloaded": 0, "blocked": None, "seconds": 0.0}
    if zips is None:
        dl = download()
        counts["bytes_downloaded"] = dl["bytes"]
        counts["blocked"] = dl["blocked"] or ("; ".join(dl["errors"]) or None)
        zips = dl["paths"]
    if not zips:
        counts["seconds"] = round(time.time() - t0, 1)
        return counts

    declared = _declared(conn)
    by_y = {d["y"]: d for d in declared if d.get("y")}
    by_name: dict[str, dict] = {}
    for d in declared:
        for n in (d["name"], d.get("declared_name")):
            if n:
                by_name.setdefault(fold(n), d)
    recon_ids = {d["recon_project"] for d in declared if d.get("recon_project")}
    existing = {r[0] for r in conn.execute("SELECT company_key FROM companies")}

    # pass 1: organisation rows worth keeping, per programme zip
    kept: list[tuple[str, dict]] = []
    for prog, zp in zips.items():
        for o in _rows(zp, "organization.csv"):
            ytj = vat_to_ytunnus(o.get("vatNumber"))
            is_fi = (o.get("country") or "").strip().upper() == "FI"
            if is_fi:
                counts["fi_org_rows"] += 1
            if is_fi or (ytj and ytj in by_y) or o.get("projectID") in recon_ids or fold(o.get("name")) in by_name:
                kept.append((prog, o))
    need = {o["projectID"] for _, o in kept}
    projects: dict[str, dict] = {}
    for prog, zp in zips.items():
        for p in _rows(zp, "project.csv"):
            counts["projects_read"] += 1
            if p["id"] in need:
                projects[p["id"]] = p

    def project_detail(p, o) -> str:
        fp = (p.get("frameworkProgramme") or "").strip()
        label = PROGRAMME_LABEL.get(fp, fp or "programme not stated")
        return (f"{p.get('acronym')}: {p.get('title')} ({label}, {p.get('fundingScheme') or 'scheme not stated'}), "
                f"role {o.get('role') or 'not stated'}, EC contribution {money(parse_amount(o.get('ecContribution')))}, "
                f"project start {p.get('startDate')}, end {p.get('endDate') or 'not stated'}")

    def emit_for(key: str, p: dict, o: dict, conf: str, how: str) -> bool:
        start = (p.get("startDate") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start):
            return False
        new = emit.emit_signal(conn, company_key=key, signal_type="eu_project", date=start,
                               source_url=PROJECT_URL.format(p["id"]), confidence=conf, adapter=NAME,
                               detail=f"{how}. {project_detail(p, o)}", amount_eur=parse_amount(o.get("ecContribution")))
        if new:
            counts["signals"] += 1
            fp = (p.get("frameworkProgramme") or "unknown").strip() or "unknown"
            counts["signals_by_programme"][fp] = counts["signals_by_programme"].get(fp, 0) + 1
        return new

    # declared companies
    matched_pairs: set[tuple[str, str]] = set()
    declared_keys = {d["key"] for d in declared}
    for prog, o in kept:
        p = projects.get(o["projectID"])
        if not p:
            continue
        ytj = vat_to_ytunnus(o.get("vatNumber"))
        if ytj and ytj in by_y:
            d = by_y[ytj]
            if (d["key"], p["id"]) not in matched_pairs:
                matched_pairs.add((d["key"], p["id"]))
                counts["declared_matched"]["vat"] += 1
                emit_for(d["key"], p, o, "high", f"Matched by VAT number {o.get('vatNumber')} to Y-tunnus {ytj}")
    for d in declared:  # recon link
        pid = d.get("recon_project")
        if not pid or (d["key"], pid) in matched_pairs or pid not in projects:
            continue
        cands = [o for _, o in kept if o["projectID"] == pid]
        if not cands:
            continue
        label = d.get("declared_name") or d["name"]
        best = max(cands, key=lambda o: difflib.SequenceMatcher(None, fold(o.get("name")), fold(label)).ratio())
        ratio = difflib.SequenceMatcher(None, fold(best.get("name")), fold(label)).ratio()
        if ratio >= MIN_RATIO:
            matched_pairs.add((d["key"], pid))
            counts["declared_matched"]["recon_link"] += 1
            emit_for(d["key"], projects[pid], best, "medium",
                     f"Matched from the team's recon link, name '{best.get('name')}' in CORDIS vs '{label}' declared "
                     f"(similarity {ratio:.2f}), treat as probable, not certain")
    for prog, o in kept:
        d = by_name.get(fold(o.get("name")))
        p = projects.get(o["projectID"])
        if d and p and (d["key"], p["id"]) not in matched_pairs:
            matched_pairs.add((d["key"], p["id"]))
            counts["declared_matched"]["exact_name"] += 1
            emit_for(d["key"], p, o, "medium", f"Matched by exact organisation name '{o.get('name')}'")

    # discovery
    disc: set[str] = set()
    for prog, o in kept:
        p = projects.get(o["projectID"])
        if not p or (p.get("startDate") or "") < DISCOVERY_FROM:
            continue
        if (o.get("country") or "").strip().upper() != "FI" or (o.get("activityType") or "").strip().upper() != "PRC" \
                or (o.get("SME") or "").strip().lower() not in ("true", "yes", "1"):
            continue
        field = kw = None
        for label, text in (("organisation name", o.get("name")), ("project title", p.get("title")),
                            ("project keywords", p.get("keywords")), ("project objective", p.get("objective"))):
            hits = matched_keywords(text or "", thesis)
            if hits:
                field, kw = label, hits[0]
                break
        if not field:
            continue
        key = vat_to_ytunnus(o.get("vatNumber"))
        if not key:
            counts["skipped_no_vat"] += 1
            continue
        if key in declared_keys:
            continue
        if key not in existing:
            emit.upsert_company(conn, company_key=key, name=o["name"], source_url=PROJECT_URL.format(p["id"]),
                                y_tunnus=key, country="FI", group_tag="feed")
            existing.add(key)
        if emit_for(key, p, o, "low", f"Matched on {field}: '{kw}'"):
            disc.add(key)
    counts["discovery_companies"] = len(disc)
    conn.commit()
    counts["seconds"] = round(time.time() - t0, 1)
    return counts


def main() -> int:
    from radar import db, thesis as thesis_mod
    th = thesis_mod.load()
    conn = db.connect(thesis_mod.db_path(th))
    c = run(conn, th)
    print(c)
    if c["blocked"]:
        print("BLOCKED:", c["blocked"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
