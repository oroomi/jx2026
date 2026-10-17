"""Wide intake from the PRH/YTJ open data (CC BY 4.0): startup-shaped limited companies, taken in before any thesis test.

Two passes, both from the intake section of the thesis (radar.thesis.intake), 1 request per 2 s, cached under data/cache/prh_intake/:
  live      companies registered in the last 365 days (a company enters intake when its first startup signal is dated inside the feed window)
  backtest  every registration year of the declared cohort and portfolio companies, so each of them competes against every same-year,
            same-family company, not just itself
For each company that passes the form and code test the adapter stores a profile (legal form), the register entry and the tax-register
signals (first_sales, first_hire, ...) read from the same record, through radar.emit. Companies already in the store keep their group;
new ones are stored as group_tag 'intake', which the Main and Weak feed lists never read. Legal names shaped like a private person's
name are not stored. Other startup signals (EU projects, Business Finland, notices) come from the other adapters.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import httpx

from radar import emit, fit as fit_mod, intake, store, thesis as thesis_mod
from radar.adapters import prh, tax_registers
from radar.adapters._fetch import Blocked, cached_get

NAME = "prh_intake"
PHASE = 1  # a discoverer: inserts companies the enrichers (tax_registers, prh_notices, cordis ...) then read
PAGE = 100
MAX_REQUESTS = 1500
LIVE_DAYS = 365
MAX_CONSECUTIVE_FAILURES = 3


def current_form(c: dict) -> tuple[str | None, str | None]:
    """(form code, English description) of the form with no endDate, latest registered; (None, None) when the register states none."""
    forms = [f for f in c.get("companyForms", []) if not f.get("endDate")] or c.get("companyForms", [])
    if not forms:
        return None, None
    f = max(forms, key=lambda f: f.get("registrationDate") or "")
    return str(f.get("type")), prh._desc(f.get("descriptions"))


def queries(cfg: dict) -> list[dict]:
    """One query per code prefix, plus one per thesis code that no prefix already covers."""
    qs = [{"mainBusinessLine": p} for p in cfg["code_prefixes"]]
    qs += [{"mainBusinessLine": c} for c in cfg["thesis_codes"] if not any(c.startswith(p) for p in cfg["code_prefixes"])]
    return qs


def windows(conn, today: date) -> list[tuple[str, str, str]]:
    """(label, start, end). The live window first, then one window per registration year of the cohort and portfolio companies."""
    out = [("live", (today - timedelta(days=LIVE_DAYS)).isoformat(), today.isoformat())]
    years = sorted({(r[0] or "")[:4] for r in conn.execute("SELECT founded FROM companies WHERE group_tag IN ('cohort','portfolio') AND founded IS NOT NULL")} - {""})
    for y in years:
        end = min(date(int(y), 12, 31), today)
        out.append((f"backtest {y}", f"{y}-01-01", end.isoformat()))
    return out


def accept(c: dict, cfg: dict, th: dict, start: str, end: str) -> dict | None:
    """The parsed company when it is startup-shaped and was registered inside the window, else None."""
    p = prh.parse(c)
    if not p["name"] or not p["founded"] or not (start <= p["founded"] <= end):
        return None  # the API date filter also matches later name or form changes: the business id itself must be new
    form, form_desc = current_form(c)
    if not intake.eligible(form, p["industry_code"], cfg)[0]:
        return None
    if fit_mod.looks_like_person(p["name"], th) or store.is_partner_org(p["name"]):
        return None
    return {**p, "form": form, "form_desc": form_desc}


def _store(conn, p: dict, record: dict, stats: dict) -> None:
    key = p["y_tunnus"]
    row = conn.execute("SELECT company_key, y_tunnus, founded, group_tag FROM companies WHERE company_key=?", (key,)).fetchone()
    if row is None:
        emit.upsert_company(conn, company_key=key, name=p["name"], source_url=p["source_url"], y_tunnus=key, country="FI", founded=p["founded"],
                            industry_code=p["industry_code"], industry_desc=p["industry_desc"], website=p["website"], group_tag="intake",
                            register_status=p["register_status"])
        stats["inserted"] += 1
        row = {"company_key": key, "y_tunnus": key, "founded": p["founded"]}
        stats["signals"] += emit.emit_signal(conn, company_key=key, signal_type="register_entry", date=p["founded"], source_url=p["source_url"],
                                             confidence="high", adapter=NAME, detail=f"Registered in PRH/YTJ on {p['founded']} (Y-tunnus {key}).")
    stats["signals"] += tax_registers.emit_for(conn, row, record)
    conn.execute(f"""INSERT INTO {intake.PROFILE_TABLE} (company_key, form_code, form_desc, registered, checked_at) VALUES (?,?,?,?,?)
                     ON CONFLICT(company_key) DO UPDATE SET form_code=excluded.form_code, form_desc=excluded.form_desc,
                       registered=excluded.registered, checked_at=excluded.checked_at""",
                 (key, p["form"], p["form_desc"], p["founded"], emit.now_utc()))
    stats["profiles"] += 1


def _declared(conn, thesis: dict, stats: dict) -> None:
    """Profiles and tax-register signals for the cohort and portfolio companies that have a business id (same record, cached)."""
    for r in conn.execute("SELECT company_key, y_tunnus, founded FROM companies WHERE group_tag IN ('cohort','portfolio') AND y_tunnus IS NOT NULL").fetchall():
        data, _ = prh.fetch({"businessId": r["y_tunnus"]})
        hit = next((c for c in data.get("companies", []) if c["businessId"]["value"] == r["y_tunnus"]), None)
        if hit is None:
            continue
        form, desc = current_form(hit)
        stats["signals"] += tax_registers.emit_for(conn, r, hit)
        conn.execute(f"""INSERT INTO {intake.PROFILE_TABLE} (company_key, form_code, form_desc, registered, checked_at) VALUES (?,?,?,?,?)
                         ON CONFLICT(company_key) DO UPDATE SET form_code=excluded.form_code, form_desc=excluded.form_desc,
                           registered=excluded.registered, checked_at=excluded.checked_at""",
                     (r["company_key"], form, desc, hit["businessId"].get("registrationDate"), emit.now_utc()))
        stats["declared"] += 1


def run(conn: sqlite3.Connection, thesis: dict, today: date | None = None) -> dict:
    cfg = thesis_mod.intake(thesis)
    if cfg is None:
        return {"skipped": "thesis has no intake section"}
    today = today or date.today()
    stats = {"companies": 0, "signals": 0, "skipped": 0, "inserted": 0, "profiles": 0, "declared": 0, "examined": 0, "requests": 0, "blocked": 0}
    try:
        _declared(conn, thesis, stats)
    except httpx.HTTPError:
        stats["blocked"] = 1
    conn.commit()
    failures = 0
    for label, start, end in windows(conn, today):
        for q in queries(cfg):
            page = 1
            while stats["requests"] < MAX_REQUESTS and not stats["blocked"]:
                params = {**q, "registrationDateStart": start, "registrationDateEnd": end, "page": page}
                try:
                    data, net = cached_get(NAME, prh.API, interval=2.0, params=params)
                except Blocked:
                    failures += 1
                    if failures >= MAX_CONSECUTIVE_FAILURES:
                        stats["blocked"] = 1
                    break
                failures = 0
                stats["requests"] += net
                comps = data.get("companies", [])
                for c in comps:
                    stats["examined"] += 1
                    p = accept(c, cfg, thesis, start, end)
                    if p is None:
                        stats["skipped"] += 1
                        continue
                    _store(conn, p, c, stats)
                    stats["companies"] += 1
                conn.commit()
                if len(comps) < PAGE or page * PAGE >= data.get("totalResults", 0):
                    break
                page += 1
            if stats["blocked"] or stats["requests"] >= MAX_REQUESTS:
                break
        if stats["blocked"] or stats["requests"] >= MAX_REQUESTS:
            break
    return stats


if __name__ == "__main__":
    from radar import db
    print(run(db.connect(), prh._load_thesis()))
