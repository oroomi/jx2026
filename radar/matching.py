"""Who comes next (question 03) and what should happen next (question 04) for one company. No web code: pure functions over the
radar database, the declared csv lists named in the thesis (`matching:`) and the frameworks levels. Empty stays empty.

Ranking, printed on the page: the dataset's own score first (reason string verbatim), then the nearest open deadline from
programmes_grants.csv, then name. Programmes and public buyers carry no dataset score, so they follow the scored rows."""
from __future__ import annotations

import csv
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from radar import blueinvest, frameworks, store
from radar.store import name_key as fold

ROOT = Path(__file__).resolve().parent.parent
LISTS = ("investors", "funding", "partners")
INVESTOR_TYPES = ("investor_vc", "investor_angel", "investor_corporate")
FUNDING_TYPES = ("public_funder", "accelerator_incubator")
CLOSED_WORDS = ("closed", "no open call", "no call open", "will not reopen", "not read")
GRANT_TYPES = ("bf_funding", "eu_project", "public_funding")
EARLY_STAGES = ("idea", "pre_seed", "seed")
INACTIVE = ("defunct",)
RANK_RULE = ("Rank = the dataset's match score (highest first), then the nearest open deadline from programmes_grants.csv, then name. "
             "Open programmes and public buyers have no dataset score and follow the scored rows. A closed programme, a past deadline, "
             "a TRL outside the programme's stated window or a company older than the programme's age limit is left out. "
             "The last slot of the funding list is kept for the soonest open programme.")
NEXT_RULES = (
    "1. No grant on record, TRL 4 to 6 and an open programme in the funding list: introduce them to that programme before its deadline.",
    "2. A public buyer in the company's category awarded a contract in the last 12 months: ask about that buyer's contract.",
    "3. Readiness gap (TRL 7 or more and investment level 3 or less): meet now to judge a raise, and introduce them to the top investor in the list.",
    "4. Cohort or portfolio company with no dated public event in 12 months: check in.",
    "5. Otherwise: watch; there is not enough public evidence for a next step yet.",
)


def _read_csv(rel: str | None) -> list[dict]:
    if not rel:
        return []
    p = ROOT / rel
    if not p.is_file():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_deadline(cell: str | None) -> dict:
    """{'open': bool, 'date': iso|None, 'text': str}. Only a cell that is a bare ISO date is a deadline; a date inside prose
    (a pilot call, a start date) is not."""
    t = (cell or "").strip()
    low = t.casefold()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return {"open": True, "date": t, "text": t}
    m = re.match(r"(\d{4}-\d{2}-\d{2}) \(continuous", low)
    if m:
        return {"open": True, "date": None, "text": "continuous call"}
    if not t or any(w in low for w in CLOSED_WORDS):
        return {"open": False, "date": None, "text": t}
    return {"open": True, "date": None, "text": t}


def trl_window(cell: str | None) -> tuple[int, int] | None:
    m = re.search(r"TRL\s*(\d)\s*-\s*(\d)", cell or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"TRL\s*(\d)\s*or higher", cell or "")
    if m:
        return int(m.group(1)), 9
    return None


def age_limit(stage_window: str | None) -> int | None:
    m = re.search(r"under\s+(\d+)\s+years", stage_window or "", re.I)
    return int(m.group(1)) if m else None


LATER_STAGES = ("series_a", "series_b_plus", "growth", "established")
_EARLY_WORDS = ("pre-seed", "preseed", "seed", "early", "startup", "start-up", "new startup", "mvp", "idea")
_LATER_WORDS = ("growth", "scale-up", "scaleup", "scale up", "series a", "series b", "venture and growth", "scaling")


def stage_mismatch(stage: str | None, window: str | None) -> str | None:
    """Two-way stage check. A text reason when the programme's stated stage window excludes a company at this stage, else None.
    An early-stage company is not offered a growth-only programme, and a later-stage company (series A and beyond) is not
    offered a programme that names only early stages. A window that names both, or neither, rules nobody out."""
    sw = (window or "").casefold()
    if not stage or not sw:
        return None
    early, later = any(w in sw for w in _EARLY_WORDS), any(w in sw for w in _LATER_WORDS)
    if stage in EARLY_STAGES and later and not early:
        return f"the dataset puts the company at {stage.replace('_', ' ')} stage and the programme names only growth stages ({window})"
    if stage in LATER_STAGES and early and not later:
        return f"the dataset puts the company at {stage.replace('_', ' ')} stage and the programme names only early stages ({window})"
    return None


def company_context(conn, company_key: str) -> dict | None:
    """The company, its signals and the levels the page prints (rule levels from frameworks, never the dataset's)."""
    data = store.company(conn, company_key)
    if data is None:
        return None
    c, sigs = data["company"], data["signals"]
    fw = frameworks.assess(c, [x for x in sigs if x["adapter"] != "ecosystem"])  # the dataset never sets a rule level
    trl, trl_src = fw["trl"]["level"], "register rule"
    profile = blueinvest.profile_for(conn, company_key)
    if profile and profile.get("trl") is not None:
        trl, trl_src = profile["trl"], "BlueInvest profile"
    if trl is None:
        try:
            row = conn.execute("SELECT trl FROM eco_readiness WHERE company_key=?", (company_key,)).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row and row[0] is not None:
            trl, trl_src = row[0], "declared research"
    try:
        st = conn.execute("SELECT stage, status FROM eco_entity WHERE company_key=? ORDER BY (stage IS NULL) LIMIT 1", (company_key,)).fetchone()
    except sqlite3.OperationalError:
        st = None
    return {"c": c, "sigs": sigs, "fw": fw, "trl": trl, "trl_src": trl_src, "irl": fw["irl"]["level"],
            "category": fw["category"]["category"], "stage": st[0] if st else None, "status": st[1] if st else None}


def _eco_rows(conn, key: str) -> list[dict]:
    try:
        rows = conn.execute(
            """SELECT m.target_id, m.target_side, m.target_type, m.score, m.why, m.confidence, e.name, e.source_url, e.status
               FROM eco_match m JOIN eco_entity e ON e.entity_id = m.target_id WHERE m.company_key = ?""", (key,)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


def _eligibility(r: dict, ctx: dict) -> tuple[bool, list[str]]:
    """(eligible, notes) for one programmes_grants.csv row: TRL window, two-way stage check, age limit."""
    founded = (ctx["c"].get("founded") or "")[:4]
    today_year = ctx.get("year") or date.today().year
    notes = []
    win = trl_window(r.get("TRL_window_if_stated"))
    if win:
        if ctx["trl"] is None:
            notes.append(f"TRL window {win[0]} to {win[1]}; company TRL not in public records")
        elif not win[0] <= ctx["trl"] <= win[1]:
            return False, []
        else:
            notes.append(f"TRL {ctx['trl']} ({ctx['trl_src']}) is inside the stated window {win[0]} to {win[1]}")
    if stage_mismatch(ctx.get("stage"), r.get("stage_window")):
        return False, []
    lim = age_limit(r.get("stage_window"))
    if lim and founded.isdigit():
        if today_year - int(founded) >= lim:
            return False, []
        notes.append(f"founded {founded}, inside the age limit of {lim} years")
    elif lim:
        notes.append(f"age limit {lim} years; founding year not in public records")
    return True, notes


def _programme_rows(thesis: dict) -> list[dict]:
    return _read_csv((thesis.get("matching") or {}).get("programmes"))


def _programmes(thesis: dict, ctx: dict, today: date) -> list[dict]:
    """Open programmes from the declared list that the company is not ruled out of."""
    out = []
    ctx = dict(ctx, year=today.year)
    for r in _programme_rows(thesis):
        dl = parse_deadline(r.get("next_deadline"))
        if not dl["open"] or (dl["date"] and dl["date"] < today.isoformat()):
            continue
        url = (r.get("source_url") or r.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        ok, notes = _eligibility(r, ctx)
        if not ok:
            continue
        reason = f"Open: {r['stage_window'] or 'eligibility not stated'}; deadline: {dl['text']}"
        if r.get("amount_eur"):
            reason += f"; amount: {r['amount_eur']}"
        if notes:
            reason += ". " + "; ".join(notes)
        out.append({"name": r["name"], "kind": r["type"], "reason": reason, "score": None, "source_url": url,
                    "confidence": None, "deadline": dl["date"], "deadline_text": dl["text"]})
    return out


def _declared_programme(name: str, rows: list[dict]) -> dict | None:
    """The programmes_grants.csv row an ecosystem funding row names (same name, or the csv name starts with it)."""
    f = fold(name)
    return next((r for r in rows if fold(r["name"]) == f), None) or next((r for r in rows if f and fold(r["name"]).startswith(f)), None)


def _investor_facts(thesis: dict) -> dict[str, dict]:
    return {fold(r["name"]): r for r in _read_csv((thesis.get("matching") or {}).get("investors"))}


def _deadline_for(name: str, programmes: list[dict]) -> str | None:
    f = fold(name)
    ds = [p["deadline"] for p in programmes if p["deadline"] and fold(p["name"]).startswith(f)]
    return min(ds) if ds else None


def _public_buyers(conn, thesis: dict, ctx: dict, today: date) -> list[dict]:
    """Buyers that awarded a contract in the company's category: title matches a category word (English from frameworks, plus
    the thesis's own buyer_keywords). One row per buyer, latest contract."""
    cat = ctx["category"]
    if not cat:
        return []
    words = list(frameworks.CATEGORIES.get(cat, []))
    words += [w.casefold() for w in ((thesis.get("matching") or {}).get("buyer_keywords") or {}).get(cat, [])]
    if not words:
        return []
    best: dict[str, dict] = {}
    for s in conn.execute("SELECT date, detail, source_url, confidence FROM signals WHERE signal_type='public_contract' AND adapter='hilma' ORDER BY date DESC"):
        detail = s["detail"] or ""
        if ": " not in detail:
            continue
        buyer, title = detail.split(": ", 1)
        hit = next((w for w in words if w in title.casefold()), None)
        if hit and buyer not in best:
            best[buyer] = {"name": buyer, "kind": "public buyer", "score": None, "source_url": s["source_url"], "confidence": s["confidence"],
                           "date": s["date"], "reason": f"Bought {cat} on {s['date']}: {re.sub(r' [(]EUR [^)]*[)]$', '', title)[:160]} (matched '{hit}')",
                           "category": cat}
    return list(best.values())


def _sort(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["score"] is None, -(r["score"] or 0), r.get("deadline") or "9999", r["name"].casefold()))


def dataset_summary(conn) -> dict | None:
    """Counts and build date of the declared ecosystem dataset as imported, or None when it was not imported."""
    try:
        meta = {k: v for k, v in conn.execute("SELECT key, value FROM eco_meta")}
    except sqlite3.OperationalError:
        return None
    if not meta:
        return None
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    meta.update(
        imported_companies=q("SELECT COUNT(*) FROM eco_entity WHERE side='supply'"),
        imported_targets=q("SELECT COUNT(*) FROM eco_entity WHERE side!='supply'"),
        imported_matches=q("SELECT COUNT(*) FROM eco_match"),
        companies_with_matches=q("SELECT COUNT(DISTINCT company_key) FROM eco_match"),
        imported_readiness=q("SELECT COUNT(*) FROM eco_readiness"),
        signals=q("SELECT COUNT(*) FROM signals WHERE adapter='ecosystem'"))
    return meta


def _assemble(conn, thesis: dict, company_key: str, ctx: dict, t: date) -> dict:
    """Every candidate row, unranked and uncut."""
    facts = _investor_facts(thesis)
    eco_rows = _eco_rows(conn, company_key)
    # Open programmes are listed for companies the dataset or the declared cohort knows; a register-only company gets no generic list.
    known = bool(eco_rows) or ctx["c"]["group_tag"] in ("cohort", "portfolio", "ecosystem")
    programmes = _programmes(thesis, ctx, t) if known else []
    inv, fund, part = [], [], []
    declared_member = ctx["c"]["group_tag"] in ("cohort", "portfolio")
    prog_rows = _programme_rows(thesis)
    ectx = dict(ctx, year=t.year)
    for r in eco_rows:
        if declared_member and store.is_partner_org(r["name"]):
            continue  # a cohort or portfolio company already works with the partner organisations
        if not (r["why"] or "").strip():
            continue  # a row without a stated reason is hidden, never shown with a placeholder
        row = {"name": r["name"], "kind": (r["target_type"] or "").replace("_", " "), "reason": r["why"].strip(),
               "score": r["score"], "source_url": r["source_url"], "confidence": r["confidence"], "deadline": None,
               "origin": "ecosystem dataset", "facts": None}
        if r["target_type"] in INVESTOR_TYPES:
            f = facts.get(fold(r["name"]))
            if f:
                bits = [b for b in (f"stage {f['stage']}" if f.get("stage") else "",
                                    f"ticket EUR {f['ticket_eur_min'] or '?'} to {f['ticket_eur_max'] or '?'}" if f.get("ticket_eur_min") or f.get("ticket_eur_max") else "") if b]
                row["facts"] = "investors.csv: " + ", ".join(bits) if bits else None
            inv.append(row)
        elif r["target_type"] in FUNDING_TYPES:
            decl = _declared_programme(r["name"], prog_rows)
            if decl is not None:  # the declared programme's own window, deadline and stage apply to this row too
                dl = parse_deadline(decl.get("next_deadline"))
                if not dl["open"] or (dl["date"] and dl["date"] < t.isoformat()):
                    continue
                ok, notes = _eligibility(decl, ectx)
                if not ok:
                    continue
                if notes:
                    row["reason"] += ". " + "; ".join(notes)
            row["deadline"] = _deadline_for(r["name"], programmes)
            fund.append(row)
        elif r["target_side"] == "demand":
            part.append(row)
    scored_names = {fold(r["name"]) for r in fund}
    for p in programmes:
        if fold(p["name"]) in scored_names or p["kind"] == "equity":
            continue
        p["origin"] = "programmes_grants.csv"
        p["facts"] = None
        fund.append(p)
    part += _public_buyers(conn, thesis, ctx, t)
    return {"investors": inv, "funding": fund, "partners": part}


def _rank(rows: list[dict], limit: int, reserve_programme: bool = False) -> list[dict]:
    ranked = _sort(rows)
    top = ranked[:limit]
    if reserve_programme and limit > 1 and not any(r.get("origin") == "programmes_grants.csv" for r in top):
        prog = next((r for r in sorted((r for r in ranked if r.get("origin") == "programmes_grants.csv"),
                                       key=lambda r: (r.get("deadline") or "9999", r["name"].casefold()))), None)
        if prog:
            top = top[:limit - 1] + [prog]  # the last slot is kept for the soonest open programme
    for i, r in enumerate(top, 1):
        r["rank"] = i
    return top


def who_comes_next(company_key: str, thesis: dict, limit: int = 5, *, conn: sqlite3.Connection | None = None, today=None) -> dict:
    """{"investors": [...], "funding": [...], "partners": [...]}, each row {name, kind, reason, rank, source_url, confidence, ...}."""
    own = conn is None
    conn = conn or store.open_db(thesis=thesis)
    if conn is None:
        return {k: [] for k in LISTS}
    try:
        ctx = company_context(conn, company_key)
        if ctx is None:
            return {k: [] for k in LISTS}
        if ctx["status"] in INACTIVE:
            return {k: [] for k in LISTS}  # a defunct company is not given leads
        full = _assemble(conn, thesis, company_key, ctx, store._today(today))
        return {k: _rank(full[k], limit, reserve_programme=(k == "funding")) for k in LISTS}
    finally:
        if own:
            conn.close()


def next_step(company_key: str, thesis: dict, *, conn: sqlite3.Connection | None = None, today=None) -> dict:
    """{sentence, because, source_url, rule}: the first rule of NEXT_RULES that the stored facts satisfy."""
    own = conn is None
    conn = conn or store.open_db(thesis=thesis)
    none = {"sentence": "Watch: not enough public evidence for a next step yet", "because": "no company with this key in the database",
            "source_url": None, "rule": 5}
    if conn is None:
        return none
    try:
        ctx = company_context(conn, company_key)
        if ctx is None:
            return none
        t = store._today(today)
        if ctx["status"] in INACTIVE:
            return {"sentence": "Watch: not enough public evidence for a next step yet", "rule": 5, "source_url": None,
                    "because": "the declared ecosystem dataset marks this company as defunct"}
        full = _assemble(conn, thesis, company_key, ctx, t)
        lists = {k: _rank(v, 10**6) for k, v in full.items()}
        sigs, trl, irl = ctx["sigs"], ctx["trl"], ctx["irl"]
        grants = [s for s in sigs if s["signal_type"] in GRANT_TYPES]
        if not grants and trl is not None and 4 <= trl <= 6:
            prog = next((r for r in lists["funding"] if r.get("origin") == "programmes_grants.csv" and r.get("deadline")), None) \
                or next((r for r in lists["funding"] if r.get("origin") == "programmes_grants.csv"), None)
            if prog:
                dl = prog.get("deadline")
                sentence = f"Introduce them to {prog['name']} before {dl}" if dl else f"Introduce them to {prog['name']} (open, deadline: {prog['deadline_text']})"
                return {"sentence": sentence, "rule": 1, "source_url": prog["source_url"],
                        "because": f"no grant or EU project record, TRL {trl} ({ctx['trl_src']}), and the programme is open: {prog['reason']}"}
        year_ago = (t - timedelta(days=365)).isoformat()
        buyer = max((b for b in lists["partners"] if b.get("kind") == "public buyer" and b["date"] >= year_ago), key=lambda b: b["date"], default=None)
        if buyer:
            return {"sentence": f"Ask about their {buyer['category']} contract with {buyer['name']} ({buyer['date']})", "rule": 2,
                    "source_url": buyer["source_url"], "because": f"a public buyer in the company's category ({buyer['category']}) awarded a contract within the last 12 months: {buyer['reason']}"}
        if trl is not None and trl >= 7 and irl is not None and irl <= 3 and lists["investors"]:
            top = lists["investors"][0]
            return {"sentence": f"Meet now: judge a raise, and introduce them to {top['name']}", "rule": 3, "source_url": top["source_url"],
                    "because": f"TRL {trl} ({ctx['trl_src']}) with investment level {irl} is a readiness gap; top investor by dataset score {top['score']}: {top['reason']}"}
        if ctx["c"]["group_tag"] in ("cohort", "portfolio"):
            dated = [s for s in sigs if s["date"] <= t.isoformat()]
            last = max(dated, key=lambda s: s["date"], default=None)
            if last is None:
                return {"sentence": "Check in: no dated public signal on record", "rule": 4, "source_url": ctx["c"]["source_url"],
                        "because": f"{ctx['c']['group_tag']} company with no dated public event in the database"}
            if last["date"] < year_ago:
                return {"sentence": f"Check in: no public signal since {last['date']}", "rule": 4, "source_url": last["source_url"],
                        "because": f"{ctx['c']['group_tag']} company whose latest dated public event is older than 12 months"}
        return {"sentence": "Watch: not enough public evidence for a next step yet", "rule": 5, "source_url": None,
                "because": "none of rules 1 to 4 is satisfied by the records stored for this company"}
    finally:
        if own:
            conn.close()
