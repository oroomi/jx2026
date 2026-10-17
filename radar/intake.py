"""Wide intake: take startup-shaped companies in wide, grade thesis fit by evidence, say plainly when there is none yet.

Pure functions over a sqlite3.Connection and the thesis (read through radar.thesis). Nothing here writes data.
Intake rule (all values from the thesis `intake:` section):
  1. legal form in company_forms (limited companies and cooperatives);
  2. industry code starts with a code_prefix or is a code listed under industry_codes;
  3. at least min_signals startup signals (types in startup_signals, never the register entry); the company ENTERS intake on the
     date of its min_signals-th startup signal.
Rank (for the backtest): among companies registered in the same year in the same two-digit code family that had entered intake by
the reference date, ordered by the number of startup signals dated no later than the reference date (more first), then by the
earlier intake date, then by business id. Rank 1 is the strongest."""
from __future__ import annotations

import sqlite3
import statistics
from datetime import date

from radar import labels
from radar import fit as fit_mod, store, thesis as thesis_mod

PROFILE_TABLE = "intake_profile"


def settings(th: dict) -> dict | None:
    return thesis_mod.intake(th)


def family(code: str | None) -> str | None:
    c = (code or "").strip()
    return c[:2] if len(c) >= 2 and c[:2].isdigit() else None


def code_ok(code: str | None, cfg: dict) -> bool:
    c = (code or "").strip()
    return bool(c) and (any(c.startswith(p) for p in cfg["code_prefixes"]) or c in cfg["thesis_codes"])


def form_ok(form_code: str | None, cfg: dict) -> bool:
    return str(form_code or "") in cfg["company_forms"]


def eligible(form_code: str | None, code: str | None, cfg: dict) -> tuple[bool, str | None]:
    """(ok, reason when not). The reason is a plain sentence that names the stored value that failed."""
    if form_code is None or form_code == "":
        return False, "legal form not in public records"
    if not form_ok(form_code, cfg):
        return False, f"legal form {form_code} is not a limited company or cooperative"
    if not (code or "").strip():
        return False, "industry code not in public records"
    if not code_ok(code, cfg):
        return False, f"industry code {code} is outside the intake code families"
    return True, None


def startup_signals(sigs: list[dict], cfg: dict, until: str | None = None) -> list[dict]:
    """Startup signals in date order, optionally only those dated no later than `until`. Never the register entry."""
    types = set(cfg["startup_signals"]) - {"register_entry"}
    out = [s for s in sigs if s["signal_type"] in types and (until is None or s["date"] <= until)]
    out.sort(key=lambda s: (s["date"], s.get("signal_id", s.get("id")) or 0))
    return out


def entered(sigs: list[dict], cfg: dict, until: str | None = None) -> tuple[str | None, list[dict]]:
    """(intake date, the startup signals up to it). None when fewer than min_signals startup signals exist."""
    ss = startup_signals(sigs, cfg, until)
    if len(ss) < cfg["min_signals"]:
        return None, ss
    return ss[cfg["min_signals"] - 1]["date"], ss


def _has_table(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (PROFILE_TABLE,)).fetchone() is not None


def profile(conn, key: str) -> dict | None:
    if not _has_table(conn):
        return None
    r = conn.execute(f"SELECT * FROM {PROFILE_TABLE} WHERE company_key=?", (key,)).fetchone()
    return dict(r) if r else None


def _signals(conn, key: str) -> list[dict]:
    rows = [dict(r) for r in conn.execute(
        "SELECT id AS signal_id, signal_type, date, source_url, confidence, adapter, detail, fetched_at FROM signals WHERE company_key=? ORDER BY date, id", (key,))]
    store.with_precision(conn, rows)
    for r in rows:
        r["label"] = labels.signal_label(r["signal_type"])
        r["source_label"] = store.evidence(r)["label"]
    return rows


def thesis_evidence(conn, th: dict, company: dict, sigs: list[dict]) -> dict:
    """The feed's own test applied to one company: {strength, reasons, why}. Evidence = at least one reason (industry code, line of business,
    own text, corroborated keyword). The company's registered facts plus its signals are the only input."""
    reg = [s for s in sigs if s["signal_type"] == "register_entry"]
    base = reg[0] if reg else {"signal_type": "register_entry", "adapter": "prh", "date": company.get("founded") or "", "detail": None, "signal_id": 0}
    row = {**{"name": company["name"], "industry_code": company.get("industry_code"), "industry_desc": company.get("industry_desc")}, **base}
    others = [s for s in sigs if s.get("signal_id") != base.get("signal_id")]
    for s in others:
        s.setdefault("id", s.get("signal_id"))
    row["id"] = base.get("signal_id")
    texts = store.source_texts(conn, [{**s, "company_key": company["company_key"], "id": s.get("signal_id")} for s in sigs])
    return store.explain(row, others, th, texts)


def company_view(conn, th: dict, company: dict, sigs: list[dict]) -> dict:
    """What the company page needs: whether thesis evidence exists, and the startup signals that brought the company in."""
    ex = thesis_evidence(conn, th, company, [dict(s, signal_id=s.get("signal_id", s.get("id"))) for s in sigs])
    cfg = settings(th)
    out = {"evidence": ex["strength"] == "strong", "why": ex["why"], "intake": False, "signals": [], "intake_date": None, "reason": None}
    if cfg is None:
        return out
    prof = profile(conn, company["company_key"])
    ok, reason = eligible(prof["form_code"] if prof else None, company.get("industry_code"), cfg)
    out["reason"] = reason
    if ok:
        d, ss = entered([dict(s, signal_id=s.get("signal_id", s.get("id"))) for s in sigs], cfg)
        out.update(intake=d is not None, signals=ss if d else [], intake_date=d)
    return out


def _cohort_year(c) -> str | None:
    return (c["founded"] or "")[:4] or None


def pool(conn, cfg: dict, year: str, fam: str, ref: str) -> list[dict]:
    """Every stored company registered in `year` in code family `fam` that had entered intake by `ref`, each with its startup
    signals dated no later than ref. Strongest first (ranking rule in the module docstring)."""
    if not _has_table(conn):
        return []
    rows = conn.execute(
        f"""SELECT c.company_key, c.name, c.industry_code, p.form_code FROM companies c JOIN {PROFILE_TABLE} p USING (company_key)
            WHERE substr(c.founded,1,4)=? AND substr(c.industry_code,1,2)=?""", (year, fam)).fetchall()
    out = []
    for r in rows:
        if not eligible(r["form_code"], r["industry_code"], cfg)[0]:
            continue
        d, ss = entered(_signals(conn, r["company_key"]), cfg, ref)
        if d is not None:
            out.append({"company_key": r["company_key"], "name": r["name"], "intake_date": d, "n": len(ss)})
    out.sort(key=lambda p: (-p["n"], p["intake_date"], p["company_key"]))
    return out


def cohort_row(conn, th: dict, c, ref: str, first_evidence: str | None) -> dict:
    """The intake facts of one cohort company for the backtest. `c` has company_key, name, founded, industry_code.
    Never reports the company as found early without its rank and the intake size beside it."""
    cfg = settings(th)
    out = {"state": "not_computed", "reason": "no intake rule in this thesis", "intake_date": None, "signal": None, "rank": None,
           "size": None, "year": None, "family": None, "first_evidence": first_evidence, "before_entry": False, "pool_note": None}
    if cfg is None:
        return out
    prof = profile(conn, c["company_key"])
    if prof is None:
        return {**out, "state": "not_in_register", "reason": "not checked against the Finnish register (no business id)"}
    ok, why = eligible(prof["form_code"], c["industry_code"], cfg)
    if not ok:
        return {**out, "state": "ineligible", "reason": why}
    sigs = _signals(conn, c["company_key"])
    d, ss = entered(sigs, cfg)
    if d is None:
        return {**out, "state": "no_startup_signal", "reason": f"fewer than {cfg['min_signals']} startup signal(s) in public records"}
    year, fam = _cohort_year(c), family(c["industry_code"])
    out.update(state="entered", reason=None, intake_date=d, signal=ss[cfg["min_signals"] - 1], year=year, family=fam,
               before_entry=d < ref)
    if year and fam:
        p = pool(conn, cfg, year, fam, ref)
        out["size"] = len(p)
        pos = next((i for i, x in enumerate(p) if x["company_key"] == c["company_key"]), None)
        out["rank"] = pos + 1 if pos is not None else None
        out["n_signals"] = p[pos]["n"] if pos is not None else None
        out["pool_note"] = f"{len(p)} new {year} companies in code family {fam} had entered intake by {ref}"
    return out


def summary(rows: list[dict]) -> dict:
    """Headline numbers over the per-company intake dicts: how many entered before cohort entry, median rank and intake size of those."""
    early = [r for r in rows if r["state"] == "entered" and r["before_entry"] and r["rank"] and r["size"]]
    ranks = [r["rank"] for r in early]
    sizes = [r["size"] for r in early]
    return {"total": len(rows), "entered": sum(1 for r in rows if r["state"] == "entered"), "before": len([r for r in rows if r["state"] == "entered" and r["before_entry"]]),
            "with_rank": len(early), "median_rank": statistics.median(ranks) if ranks else None, "median_size": statistics.median(sizes) if sizes else None}


def headline(s: dict) -> str:
    base = (f"Entered wide intake before cohort entry: {s['before']} of {s['total']}. ")
    if s["with_rank"]:
        base += (f"Their median rank among same-year, same-family intake companies is {_n(s['median_rank'])} of {_n(s['median_size'])}. ")
    else:
        base += "No rank can be shown yet. "
    return base + "A company is never counted as found early without its rank and the intake size beside it."


def _n(x) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


# ---- the third feed tier ---------------------------------------------------------------------------------------------

def tier(conn, th: dict, *, today=None, exclude: set[str] | None = None, limit: int = 300) -> list[dict]:
    """Companies that met the intake rule inside the feed window and are not already in the Main or Weak lists (`exclude` keys),
    ranked by their number of startup signals, then newest intake first. Each row says which signal put it there.
    Companies with thesis evidence are left to the Main list; person-shaped legal names, partner organisations and sole traders are hidden."""
    cfg = settings(th)
    if cfg is None or not _has_table(conn):
        return []
    start, end, _ = store._window(th, today)
    exclude = exclude or set()
    types = sorted(set(cfg["startup_signals"]) - {"register_entry"})
    q = ",".join("?" * len(types))
    by_company: dict[str, list[dict]] = {}
    for r in conn.execute(
            f"""SELECT s.id AS signal_id, s.company_key, s.signal_type, s.date, s.source_url, s.confidence, s.adapter, s.detail, s.fetched_at
                FROM signals s JOIN companies c USING (company_key) JOIN {PROFILE_TABLE} p USING (company_key)
                WHERE s.signal_type IN ({q}) AND c.group_tag NOT IN ('cohort','portfolio') ORDER BY s.date, s.id""", types):
        by_company.setdefault(r["company_key"], []).append(dict(r))
    cands = []
    for key, ss in by_company.items():
        if key in exclude or len(ss) < cfg["min_signals"]:
            continue
        d = ss[cfg["min_signals"] - 1]["date"]
        if start.isoformat() <= d <= end.isoformat():
            cands.append((key, d, ss))
    names = {r["company_key"]: r for r in conn.execute(
        f"SELECT c.*, p.form_code FROM companies c JOIN {PROFILE_TABLE} p USING (company_key)")}
    cands.sort(key=lambda c: (-len(c[2]), -int(c[1].replace("-", "")), names[c[0]]["name"]))
    out = []
    for key, d, ss in cands:
        r = names[key]
        if not eligible(r["form_code"], r["industry_code"], cfg)[0] or r["register_status"] in ("bankrupt", "ended"):
            continue
        if fit_mod.looks_like_person(r["name"], th) or store.is_partner_org(r["name"]):
            continue
        if store.is_listed_company(r["name"]) or store.excluded_code(r["industry_code"], th):
            continue
        if thesis_evidence(conn, th, dict(r), _signals(conn, key))["strength"] == "strong":
            continue
        out.append({"company_key": key, "name": r["name"], "industry_code": r["industry_code"], "industry_desc": r["industry_desc"],
                    "date": d, "n": len(ss), "signals": ss})
        if len(out) >= limit:
            break
    flat = [s for o in out for s in o["signals"]]
    store.with_precision(conn, flat)
    for s in flat:
        s["label"] = labels.signal_label(s["signal_type"])
        s["source_label"] = store.evidence(s)["label"]
    for o in out:
        first = o["signals"][cfg["min_signals"] - 1]
        more = o["n"] - 1
        o["signal"] = first
        o["why"] = f"{first['label']} on {first.get('date_label') or first['date']} put it here" + (f"; {more} more startup signal{'s' if more != 1 else ''}." if more else ".")
        o["evidence"] = store.evidence(first)
    return out


def tuning_note(th: dict) -> str | None:
    """The sector file's note on code families added after the backtest (None when it has none): results for those are in-sample."""
    cfg = settings(th)
    return (cfg or {}).get("tuning_note") or None


def rule_text(th: dict) -> str | None:
    """One plain paragraph of the intake rule, built from the thesis section."""
    cfg = settings(th)
    if cfg is None:
        return None
    forms = " or ".join(f.split(" (")[0].lower() for f in cfg["company_forms"].values())
    types = ", ".join(labels.signal_label(t).lower() for t in cfg["startup_signals"])
    n = cfg["min_signals"]
    return (f"A company is taken in when it is a {forms}, its industry code starts with {', '.join(cfg['code_prefixes'])} (or is a code on the sector list), "
            f"and public records show at least {n} startup signal{'s' if n != 1 else ''} beyond its register entry ({types}). "
            "Nothing here says the company fits the sector: no industry code, line of business, source text or second source supports that yet.")
