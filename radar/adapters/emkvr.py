"""Finnish EMKVR / EMKR (EU fisheries and maritime fund) beneficiary lists -> eu_grant signals.

Source, checked 16 Oct 2026: merijakalatalous.fi/emkvr/rahoitetut-hankkeet/ points to Kaju (Kalatalouden tukien
julkaisujarjestelma, ministry of agriculture and forestry, MMM), https://kaju.mmm.fi/kaju2020/ . Kaju is a public Angular page over a
public JSON service; no login. The adapter reads the same two calls the page makes:
  GET https://kaju.mmm.fi/kaju2020/haku/ohjelmat      programme definitions, column ids, reference lists (list refreshed 2026-10-08)
  GET https://kaju.mmm.fi/kaju2020/haku/hae?ok=3      EMKVR 2021-2027 rows (2005 rows when checked)
  GET https://kaju.mmm.fi/kaju2020/haku/hae?ok=2      EMKR 2014-2020 rows, for history (3296 rows when checked)
(ok=1 is the 2007-2013 programme: end year only, no start date, not read.) Responses are cached in data/cache/emkvr/
(gitignored, never committed); 1 request per 2 s; HTTP 403/429 stops with BLOCKED. Every row is also a public page:
https://kaju.mmm.fi/kaju2020/?ok=<programme>&_<project number column>=<project number> (the project number is searchable).

Row shape: {"id", "aikaleima", "arvot": {column id: value}, "viitteet": {reference type: reference id}}. Columns (ids differ
by programme, see COLUMNS): beneficiary, project number, project name, description, start and end date (ISO timestamps in UTC,
converted to the Helsinki calendar day), support granted, EU share, total expenses, municipality, measure, priority, status.
THE LIST HAS NO BUSINESS ID: matching is by folded legal name only (medium). Ambiguous names (two store companies with the
same folded name) are not matched. Status "Hylatty" (rejected) and "Peruttu" (cancelled) rows are not grants and are skipped.

Date: the project start date, day precision; a bare year (not present in these two programmes, handled for other exports)
becomes YYYY-01-01 with signal_meta date_precision 'year'. A row without a start date is skipped and counted, never dated
from its end date.

Beneficiary types by legal-form words: company (Oy, Oyj, Ab, Abp, Ltd), cooperative, sole_or_partnership (Ky, Tmi, Kb,
toiminimi), association (ry, rf, saatio, liitto), public (municipality, ELY centre, university, state bodies), other
(including private persons, never stored). Only companies match or enter; discovery additionally needs a thesis keyword
(whole word) in the project name, description or measure, a name that does not look like a private person's, and
confidence low. Existing companies get a signal, never an upsert.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from radar import emit
from radar.adapters.cordis import fold
from radar.adapters.declared import slug
from radar.fit import looks_like_person, matched_keywords

NAME = "emkvr"
PHASE = 1
ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "data" / "cache" / "emkvr"
BASE = "https://kaju.mmm.fi/kaju2020/"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
PROGRAMMES = {3: "EMKVR 2021-2027", 2: "EMKR 2014-2020"}
# column ids per programme: name, number, project, descr, start, end, granted, eu, total
COLUMNS = {
    3: {"name": "34", "number": "26", "project": "28", "descr": "29", "start": "36", "end": "37", "granted": "38", "eu": "40", "total": "39"},
    2: {"name": "9", "number": "18", "project": "10", "descr": "24", "start": "14", "end": "15", "granted": "19", "eu": "17", "total": "16"},
}
NUMBER_FILTER = {3: "_26", 2: "_18"}
SKIP_STATUS = {"hylätty", "peruttu"}
HELSINKI = ZoneInfo("Europe/Helsinki")

_W = r"(?<![\w])(?:{})(?![\w])"
TYPE_RULES = (
    ("company", re.compile(_W.format(r"oy|oyj|ab|abp|ltd|as|gmbh"), re.I)),
    ("cooperative", re.compile(r"osuuskunta|andelslag|osk\b", re.I)),
    ("sole_or_partnership", re.compile(_W.format(r"ky|kb|tmi|toiminimi|firma"), re.I)),
    ("association", re.compile(r"(?<![\w])(?:ry|rf|r\.y\.)(?![\w])|säätiö|stiftelse|yhdistys|förening|liitto|förbund|seura\b|kalastuskunta|vesialue", re.I)),
    ("public", re.compile(r"kunta|kaupunki|kommun|stad\b|ely-keskus|elinvoimakeskus|yliopisto|universitet|ammattikorkeakoulu|korkeakoulu|"
                          r"luonnonvarakeskus|ministeriö|virasto|metsähallitus|valtio|maakunta|kuntayhtymä|kalatalouskeskus|kehittämiskeskus|"
                          r"kalatalousryhmä|leader|tutkimuslaitos|oppilaitos|koulu\b", re.I)),
)


STRONG_PUBLIC = re.compile(r"ely-keskus|elinvoimakeskus|(?<![\w])kunta|kaupunki|kommun|yliopisto|universitet|luonnonvarakeskus|ministeriö|metsähallitus|ammattikorkeakoulu", re.I)


def beneficiary_type(name: str) -> str:
    """Strong public markers first, then a company legal form (so 'Kalatalous Oy' is a company), then the weaker kinds."""
    n, rules = name or "", dict(TYPE_RULES)
    if STRONG_PUBLIC.search(n):
        return "public"
    for t in ("company", "cooperative", "sole_or_partnership", "association", "public"):
        if rules[t].search(n):
            return t
    return "other"


def parse_day(v) -> tuple[str | None, str | None]:
    """-> (ISO date, precision). Timestamps are UTC instants; the day is the Helsinki calendar day. Bare year -> year precision."""
    s = str(v or "").strip()
    if re.fullmatch(r"(19|20)\d{2}", s):
        return f"{s}-01-01", "year"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s, "day"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(HELSINKI).strftime("%Y-%m-%d"), "day"


def money(x) -> str:
    return "not stated" if x in (None, "") else f"EUR {float(x):,.0f}"


def num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


# ---- download -----------------------------------------------------------------------------------------------

def download(cache: Path = CACHE, opener=urllib.request.urlopen, pause: float = 2.0) -> dict:
    """Fetch the programme definitions and the rows of each programme once. Returns {paths, blocked, errors, bytes}."""
    cache.mkdir(parents=True, exist_ok=True)
    out = {"paths": {}, "blocked": None, "errors": [], "bytes": 0}
    jobs = [("ohjelmat", BASE + "haku/ohjelmat", cache / "ohjelmat.json")] + \
           [(f"rows_{ok}", f"{BASE}haku/hae?ok={ok}", cache / f"rows_{ok}.json") for ok in PROGRAMMES]
    first = True
    for key, url, dest in jobs:
        if dest.exists() and dest.stat().st_size > 0:
            out["paths"][key] = dest
            continue
        if not first:
            time.sleep(pause)
        first = False
        try:
            with opener(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
                body = r.read()
            json.loads(body)
            dest.write_bytes(body)
            out["bytes"] += len(body)
            out["paths"][key] = dest
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                out["blocked"] = f"HTTP {e.code} from {url}"
                return out
            out["errors"].append(f"HTTP {e.code} from {url}")
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            out["errors"].append(f"{url}: {e}")
    return out


# ---- reference lists ------------------------------------------------------------------------------------------

def reference_names(defs: list[dict]) -> dict[int, dict[str, str]]:
    """{programme id: {reference id (as str): Finnish name}} from the definitions (measures, priorities, municipalities, status)."""
    out: dict[int, dict[str, str]] = {}
    for p in defs:
        m: dict[str, str] = {}
        for lst in ("kunnat", "hanketilanteet", "maat"):
            for r in p.get(lst) or []:
                m[str(r["id"])] = (r.get("nimi") or {}).get("FI") or ""
        for tl in p.get("toimintalinjat") or []:
            m[str(tl["id"])] = (tl.get("nimi") or {}).get("FI") or ""
            for t in tl.get("toimenpiteet") or []:
                m[str(t["id"])] = (t.get("nimi") or {}).get("FI") or ""
        out[p["id"]] = m
    return out


# ---- run ------------------------------------------------------------------------------------------------------

def run(conn: sqlite3.Connection, thesis: dict, files: dict | None = None) -> dict:
    t0 = time.time()
    c = {"rows_parsed": 0, "beneficiaries_by_type": {}, "skipped_status": 0, "skipped_no_date": 0, "skipped_no_name": 0,
         "skipped_not_company": 0, "skipped_ambiguous": 0, "skipped_person_like": 0, "skipped_no_keyword": 0,
         "matched_companies": 0, "discovery_companies": 0, "signals": 0, "signals_by_year": {}, "total_eur": 0.0,
         "bytes_downloaded": 0, "blocked": None, "seconds": 0.0}
    if files is None:
        dl = download()
        c["bytes_downloaded"], c["blocked"] = dl["bytes"], dl["blocked"] or ("; ".join(dl["errors"]) or None)
        files = dl["paths"]
    if "ohjelmat" not in files:
        c["seconds"] = round(time.time() - t0, 1)
        return c
    refs = reference_names(json.loads(Path(files["ohjelmat"]).read_text()))
    by_name: dict[str, str | None] = {}
    for key, name in conn.execute("SELECT company_key, name FROM companies"):
        f = fold(name)
        by_name[f] = key if f not in by_name else None  # None marks an ambiguous folded name
    matched: set[str] = set()
    disc: set[str] = set()
    new_ids: list[tuple] = []
    for ok, label in PROGRAMMES.items():
        fp = files.get(f"rows_{ok}")
        if not fp:
            continue
        col, ref = COLUMNS[ok], refs.get(ok, {})
        for row in json.loads(Path(fp).read_text()):
            c["rows_parsed"] += 1
            v, vr = row.get("arvot") or {}, row.get("viitteet") or {}
            name = str(v.get(col["name"]) or "").strip()
            if not name:
                c["skipped_no_name"] += 1
                continue
            btype = beneficiary_type(name)
            c["beneficiaries_by_type"][btype] = c["beneficiaries_by_type"].get(btype, 0) + 1
            if ref.get(str(vr.get("HANKETILANNE")), "").casefold() in SKIP_STATUS:
                c["skipped_status"] += 1
                continue
            if btype != "company":
                c["skipped_not_company"] += 1
                continue
            date, prec = parse_day(v.get(col["start"]))
            if not date:
                c["skipped_no_date"] += 1
                continue
            number = v.get(col["number"])
            project, descr = str(v.get(col["project"]) or "").strip(), str(v.get(col["descr"]) or "")
            measure = ref.get(str(vr.get("TOIMENPIDE")), "")
            url = f"{BASE}?ok={ok}&{NUMBER_FILTER[ok]}={number}"
            key, how, conf = by_name.get(fold(name)), "exact legal name", "medium"
            if key is None and fold(name) in by_name:
                c["skipped_ambiguous"] += 1
                continue
            if key is None:
                hit = next(iter(matched_keywords(f"{project} {descr} {measure}", thesis)), None)
                if not hit:
                    c["skipped_no_keyword"] += 1
                    continue
                if looks_like_person(name, thesis):
                    c["skipped_person_like"] += 1
                    continue
                key = slug("fi", name)
                emit.upsert_company(conn, company_key=key, name=name, source_url=url, country="FI", group_tag="feed")
                by_name[fold(name)] = key
                how, conf = f"thesis keyword '{hit}' in the operation text", "low"
                disc.add(key)
            else:
                matched.add(key)
            granted, eu, total = num(v.get(col["granted"])), num(v.get(col["eu"])), num(v.get(col["total"]))
            detail = (f"{label} operation {number}: {project or 'name not stated'}; measure {measure or 'not stated'}; "
                      f"support granted {money(granted)}, EU share {money(eu)}, total expenses {money(total)}; "
                      f"municipality {ref.get(str(vr.get('KUNTA')), '') or 'not stated'}; start {date}"
                      f"{' (year only)' if prec == 'year' else ''}. Beneficiary '{name}' matched by {how}; the list has no business id. "
                      f"Open the row at {url}")
            if emit.emit_signal(conn, company_key=key, signal_type="eu_grant", date=date, source_url=url, confidence=conf,
                                adapter=NAME, detail=detail, amount_eur=granted):
                c["signals"] += 1
                c["total_eur"] += granted or 0.0
                y = date[:4]
                c["signals_by_year"][y] = c["signals_by_year"].get(y, 0) + 1
                new_ids.append((key, date, url, prec))
    for key, date, url, prec in new_ids:
        if prec == "year":
            conn.execute("INSERT OR REPLACE INTO signal_meta (signal_id, date_precision) SELECT id, 'year' FROM signals "
                         "WHERE company_key=? AND signal_type='eu_grant' AND date=? AND source_url=?", (key, date, url))
    c["matched_companies"], c["discovery_companies"] = len(matched), len(disc)
    c["signals_by_year"] = dict(sorted(c["signals_by_year"].items()))
    conn.commit()
    c["seconds"] = round(time.time() - t0, 1)
    return c


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
