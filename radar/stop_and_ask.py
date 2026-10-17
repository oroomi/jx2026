"""The stop-and-ask list (jx40), run over a store and, for company rows, over the live public API. Read-only; prints counts and examples.

Each check is a case where no assumption in PROJECT_RULES.md decides the answer, so it goes to the dataset owner as a question
(QUESTIONS_B<n>.md) instead of being fixed in code:
  conflicts         sources disagree on a company field (radar/candidates.py report; needs `candidates build` first)
  contradictions    a value contradicts an assumption: a website or link on a login-walled site (A27), a malformed
                    Business ID or country code (A29), a founding date or event date after today
  dates_out_of_order  a dated event before the company's own registration date (compared at the event's precision, A18)
  outliers          an amount more than 10 times the median of its signal type, or zero or negative (A19)
  startup_investor  a company in the store that the declared investor list or the ecosystem dataset lists as a capital source
  duplicates        two company keys with one folded name or one website host
  amount_mismatch   a stored amount that differs from the one EUR figure the same row's text states
  amount_shared     one notice and one amount stored on two or more companies (a framework total counted once per winner)
Not run offline: links that redirect to another company (needs a fetch per link).

  python3 -m radar.stop_and_ask --db data/snapshot/radar_redstone_apelago_blue.sqlite
  python3 -m radar.stop_and_ask --api https://jx.hankintaviikko.fi        # company checks on the live store, 1 request per 2 s
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import statistics
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from radar import formats, store
from radar import thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
INVESTORS = ROOT / "data" / "declared" / "investors.csv"
ECO_DB = ROOT / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"
API_CACHE = ROOT / "data" / "cache" / "api_live"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
LOGIN_HOSTS = ("linkedin.com", "dealroom.co", "crunchbase.com", "pitchbook.com", "tracxn.com", "facebook.com")
SHARED_HOSTS = LOGIN_HOSTS + ("instagram.com", "twitter.com", "x.com", "youtube.com", "google.com", "sites.google.com")
OUTLIER_FACTOR = 10
_EUR = re.compile(r"EUR ([\d][\d,.  ]*\d)")


def host(url: str | None) -> str | None:
    h = urlparse(url if (url or "").startswith(("http://", "https://")) else f"http://{url or ''}").netloc.lower()
    return h.removeprefix("www.") or None


def on_login_host(url: str | None) -> bool:
    h = host(url) or ""
    return any(h == d or h.endswith("." + d) for d in LOGIN_HOSTS)


# ---------------------------------------------------------------- company rows (store or API)

def company_checks(rows: list[dict], today: str) -> dict:
    out: dict[str, list] = {"bad_business_id": [], "bad_country": [], "founded_future": [], "login_website": [],
                            "duplicate_name": [], "duplicate_website": []}
    by_name: dict[str, list] = {}
    by_host: dict[str, list] = {}
    for r in rows:
        k = r["company_key"]
        if r.get("y_tunnus") and not formats.business_id_ok(r["y_tunnus"]):
            out["bad_business_id"].append((k, r["name"], r["y_tunnus"]))
        if r.get("country") and not formats.country_ok(r["country"]):
            out["bad_country"].append((k, r["name"], r["country"]))
        if r.get("founded") and r["founded"] > today:
            out["founded_future"].append((k, r["name"], r["founded"]))
        if r.get("website") and on_login_host(r["website"]):
            out["login_website"].append((k, r["name"], r["website"]))
        nk = store.name_key(r["name"] or "")
        if nk:
            by_name.setdefault(nk, []).append(r)
        h = host(r.get("website"))
        if h and not any(h == d or h.endswith("." + d) for d in SHARED_HOSTS):
            by_host.setdefault(h, []).append(r)
    for nk, rs in by_name.items():
        if len(rs) > 1:
            out["duplicate_name"].append([(r["company_key"], r["name"], r.get("group_tag")) for r in rs])
    for h, rs in by_host.items():
        if len(rs) > 1:
            out["duplicate_website"].append((h, [(r["company_key"], r["name"]) for r in rs]))
    return out


def store_companies(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute("SELECT company_key, name, y_tunnus, country, founded, website, group_tag FROM companies")]


def api_companies(base: str, page: int = 500, pause: float = 2.0) -> list[dict]:
    """Every company row of the live store through the public read-only API, cached per page under data/cache/api_live/."""
    import httpx
    API_CACHE.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    offset, total = 0, None
    with httpx.Client(headers={"User-Agent": UA}, timeout=60) as client:
        while total is None or offset < total:
            f = API_CACHE / f"companies_{date.today().isoformat()}_{offset}.json"
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
            else:
                r = client.get(f"{base.rstrip('/')}/api/companies", params={"limit": page, "offset": offset})
                r.raise_for_status()
                data = r.json()
                f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                time.sleep(pause)
            total = data.get("total") or 0
            rows.extend(data.get("companies") or [])
            if not data.get("companies"):
                break
            offset += page
    return rows


# ---------------------------------------------------------------- signal rows (store only)

def signal_checks(conn: sqlite3.Connection, today: str) -> dict:
    conn.row_factory = sqlite3.Row
    prec = {r["signal_id"]: r["date_precision"] for r in conn.execute("SELECT signal_id, date_precision FROM signal_meta")}
    founded = {r["company_key"]: r["founded"] for r in conn.execute("SELECT company_key, founded FROM companies WHERE founded IS NOT NULL")}
    names = {r["company_key"]: r["name"] for r in conn.execute("SELECT company_key, name FROM companies")}
    out: dict[str, list] = {"date_future": [], "before_registration": [], "login_source": [], "amount_nonpositive": [],
                            "amount_outlier": [], "amount_mismatch": []}
    amounts: dict[str, list] = {}
    rows = [dict(r) for r in conn.execute("SELECT id, company_key, signal_type, date, source_url, adapter, detail, amount_eur FROM signals")]
    for s in rows:
        p = prec.get(s["id"], "day")
        if s["date"] > today:
            out["date_future"].append((s["company_key"], names.get(s["company_key"]), s["signal_type"], s["date"]))
        f = founded.get(s["company_key"])
        n = {"year": 4, "month": 7}.get(p, 10)
        if f and s["signal_type"] != "register_entry" and s["date"][:n] < f[:n]:
            out["before_registration"].append((s["company_key"], names.get(s["company_key"]), s["signal_type"], s["date"], p, f, s["source_url"]))
        if on_login_host(s["source_url"]):
            out["login_source"].append((s["company_key"], s["signal_type"], s["source_url"]))
        a = s["amount_eur"]
        if a is not None:
            if a <= 0:
                out["amount_nonpositive"].append((s["company_key"], s["signal_type"], a))
            else:
                amounts.setdefault(s["signal_type"], []).append(s)
            m = _EUR.findall(s["detail"] or "")
            if s["adapter"] in ("hilma", "cordis") and len(m) == 1:
                stated = float(re.sub(r"[^\d.]", "", m[0].replace(",", "")) or 0)
                if a > 0 and abs(stated - a) > 0.5:
                    out["amount_mismatch"].append((s["company_key"], s["signal_type"], a, m[0]))
    shared: dict[tuple, set] = {}
    for t, ss in amounts.items():
        for x in ss:
            if x["adapter"] != "businessfinland":  # every export row links the one dashboard page, by design (A19)
                shared.setdefault((t, x["source_url"], x["amount_eur"]), set()).add(x["company_key"])
    out["amount_shared"] = [(t, url, a, sorted(ks)) for (t, url, a), ks in sorted(shared.items(), key=lambda kv: -kv[0][2]) if len(ks) > 1]
    for t, ss in amounts.items():
        med = statistics.median(x["amount_eur"] for x in ss)
        for x in sorted(ss, key=lambda x: -x["amount_eur"]):
            if x["amount_eur"] > OUTLIER_FACTOR * med:
                out["amount_outlier"].append((t, x["company_key"], names.get(x["company_key"]), x["amount_eur"], med, x["source_url"]))
    return out


def startup_investor(conn: sqlite3.Connection) -> list[tuple]:
    """Store companies that the declared investor list or the ecosystem dataset's capital side also names."""
    conn.row_factory = sqlite3.Row
    comps = store_companies(conn)
    by_key = {store.name_key(c["name"] or ""): c for c in comps if c["name"]}
    by_biz = {c["y_tunnus"]: c for c in comps if c["y_tunnus"]}
    hits: dict[str, tuple] = {}
    if INVESTORS.is_file():
        with open(INVESTORS, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            col = next((c for c in rd.fieldnames or [] if c.lower() in ("name", "investor", "organisation", "organization")), None)
            for r in rd:
                nm = (r.get(col) or "").strip() if col else ""
                c = by_key.get(store.name_key(nm)) if nm else None
                if c:
                    hits[c["company_key"]] = (c["company_key"], c["name"], c["group_tag"], f"investors.csv: {nm}")
    if ECO_DB.is_file():
        src = sqlite3.connect(f"file:{ECO_DB}?mode=ro", uri=True)
        try:
            for eid, nm, typ, biz in src.execute("SELECT id, name, entity_type, business_id FROM entity WHERE side='capital'"):
                c = by_biz.get((biz or "").strip()) or by_key.get(store.name_key(nm or ""))
                if c:
                    hits.setdefault(c["company_key"], (c["company_key"], c["name"], c["group_tag"], f"ecosystem {eid} {typ}: {nm}"))
        finally:
            src.close()
    return sorted(hits.values())


def run(db: Path | None, api: str | None, today: str, examples: int = 5) -> dict:
    res: dict = {"today": today}
    if db:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        res["store"] = {"path": str(db), "companies": company_checks(store_companies(conn), today),
                        "signals": signal_checks(conn, today), "startup_investor": startup_investor(conn)}
        try:
            from radar import candidates
            rows = candidates.load_rows(conn)
            res["store"]["candidate_login_values"] = [(r["company_key"], r["field"], r["value"], r["source"]) for r in rows
                                                      if r["field"] == "website" and on_login_host(r["value"])]
            res["store"]["conflicts"] = {f: len(v) for f, v in candidates.conflicts(rows).items()}
        except sqlite3.OperationalError:
            res["store"]["conflicts"] = "no field_candidates table (run python3 -m radar.candidates build on a copy)"
    if api:
        rows = api_companies(api)
        res["api"] = {"base": api, "companies_read": len(rows), "companies": company_checks(rows, today)}
    return res


def render(res: dict, examples: int = 5) -> str:
    lines = [f"stop-and-ask list, {res['today']}"]
    for where in ("store", "api"):
        part = res.get(where)
        if not part:
            continue
        lines.append(f"[{where}] {part.get('path') or part.get('base')}" + (f", {part['companies_read']:,} companies read" if "companies_read" in part else ""))
        for group in ("companies", "signals"):
            for name, items in (part.get(group) or {}).items():
                lines.append(f"  {name}: {len(items)}")
                for it in items[:examples]:
                    lines.append(f"      {it}")
        for name in ("startup_investor", "candidate_login_values"):
            if name in part:
                lines.append(f"  {name}: {len(part[name])}")
                for it in part[name][:examples]:
                    lines.append(f"      {it}")
        if "conflicts" in part:
            lines.append(f"  conflicts by field: {part['conflicts']}")
    lines.append("not run offline: links that redirect to another company (needs a fetch per link)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.stop_and_ask", description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, help="store to read (read-only); default RADAR_DB or the thesis store")
    ap.add_argument("--api", help="base URL of the live public API for the company checks, e.g. https://jx.hankintaviikko.fi")
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--examples", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    db = a.db or thesis_mod.db_path(thesis_mod.load())
    res = run(db if Path(db).is_file() else None, a.api, a.today, a.examples)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str) if a.json else render(res, a.examples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
