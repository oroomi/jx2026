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
RANK_RULE = ("Rank = the dataset's match score (highest first), then the nearest open deadline from the declared programmes list, then name. "
             "Open programmes and public buyers have no dataset score and follow the scored rows. A closed programme, a past deadline, "
             "a TRL outside the programme's stated window or a company older than the programme's age limit is left out. "
             "The last slot of the funding list is kept for the soonest open programme. "
             "The five groups (investors, public funding, buyers, project partners, research institutes) rank the closest evidence "
             "first: a record about this company, then the same project or the same industry code, then the same topic or capability, "
             "then the thesis category; within a level, more records first, then the most recent. Organisations only.")
# The five groups the page shows, in order. investors also keeps its scored dataset rows; funding and partners stay as before.
GROUPS = (("investors", "Investors"), ("public_funding", "Public funding"), ("buyers", "Buyers"),
          ("project_partners", "Project partners"), ("research_institutes", "Research institutes"))
GROUP_RULES = {
    "investors": "Capital sources in the declared ecosystem dataset that fund the company's stage (their stated stages) and its sector: "
                 "they share a capability code with the company or backed a company that does. A stated stage window that excludes the "
                 "company's stage rules the investor out. Organisation records only, never the people table.",
    "public_funding": "Public funders with their own rows: first the funders on this company's own records (Business Finland, EU "
                      "projects), then funders of companies with the same industry code or topic in the store, then public funders in "
                      "the declared dataset that fund the company's capability (for example EMKVR, BlueInvest, Finnvera); a stated "
                      "stage window that does not list the company's stage ranks the funder lower but never removes it.",
    "buyers": "Public buyers from the Hilma award signals of the last 24 months: a buyer that already bought from this company, then "
              "buyers of companies with the same industry code, then the same industry division, then contract titles holding the "
              "company's own topic words (its impact-category words and its keywords in the declared dataset). A thesis-wide word "
              "alone is not enough. The store keeps no CPV code, so the category is read from industry codes and title words.",
    "project_partners": "Organisations in the same EU projects as the company (CORDIS project page), then participants of EU projects "
                        "whose title holds the company's topic words (its category words, its keywords in the declared dataset).",
    "research_institutes": "Universities and research institutes in the declared ecosystem dataset: the dataset's own scored matches "
                           "first, then institutes that work on the company's capability codes. OpenAlex rows in the store name only "
                           "the company's own affiliation, so they add no institute yet.",
}
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
    profile = blueinvest.profile_for(conn, company_key)
    fw = frameworks.page_levels(c, sigs, profile)  # the levels the company page prints; the dataset never sets a rule level
    trl, trl_src = fw["trl"]["level"], "register rule"
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


# ---- the five groups (jx39): investors, public funding, buyers, project partners, research institutes -------------------
BUYER_MONTHS = 24
_PERSON_LINK = ("linkedin.com",)


def _eco_db():
    """The declared ecosystem dataset, read-only, or None. Path from the ecosystem adapter (one place)."""
    from radar.adapters.ecosystem import DB_PATH
    if not Path(DB_PATH).is_file():
        return None
    e = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    e.row_factory = sqlite3.Row
    return e


def _eco_url(eco, entity_id: str, website: str | None) -> str | None:
    w = (website or "").strip()
    if w.startswith("http") and not any(h in w for h in _PERSON_LINK):
        return w
    for (u,) in eco.execute("SELECT url FROM source WHERE entity_id=? ORDER BY id", (entity_id,)):
        if u and u.startswith("http") and not any(h in u for h in _PERSON_LINK):
            return u
    return None


def _eco_profile(eco, ctx: dict) -> dict | None:
    """The company's own record in the dataset (business id, then folded name): stage, capability codes, keywords."""
    c = ctx["c"]
    r = None
    if c.get("y_tunnus"):
        r = eco.execute("SELECT * FROM entity WHERE TRIM(business_id)=?", (c["y_tunnus"],)).fetchone()
    if r is None:
        want = fold(c["name"])
        r = next((x for x in eco.execute("SELECT * FROM entity WHERE side='supply'") if fold(x["name"]) == want), None)
    if r is None:
        return None
    caps = [x[0] for x in eco.execute("SELECT code FROM entity_capability WHERE entity_id=? ORDER BY code", (r["id"],))]
    labels = {x[0]: x[1] for x in eco.execute("SELECT code, label FROM capability")}
    words = [x[0] for x in eco.execute("SELECT keyword FROM entity_keyword WHERE entity_id=?", (r["id"],))]
    words += [x[0] for x in eco.execute("SELECT segment FROM entity_segment WHERE entity_id=?", (r["id"],))]
    return {"id": r["id"], "stage": r["stage"], "caps": caps, "labels": labels, "words": words, "verified": r["last_verified"]}


def _is_partner(name: str) -> bool:
    """The partner organisations themselves (store.PARTNER_PREFIXES: the accelerator and the fund), not every investor listed in
    investors.csv: a cohort company already works with the partners, but any other investor is a real next step."""
    key = fold(name)
    return any(key.startswith(fold(p)) for p in store.PARTNER_PREFIXES)


def _cap_text(prof: dict, codes) -> str:
    return "; ".join(f"{c} {prof['labels'].get(c, '')}".strip() for c in sorted(codes))


def _topic_words(ctx: dict, thesis: dict, prof: dict | None) -> list[str]:
    """Folded words that say what the company works on: its impact-category words, the thesis's buyer words for that category,
    thesis words in its registered line of business, and its keywords and segments in the dataset. Short words are dropped."""
    from radar import fit
    cat = ctx.get("category")
    words = list(frameworks.CATEGORIES.get(cat, [])) if cat else []
    words += ((thesis.get("matching") or {}).get("buyer_keywords") or {}).get(cat, []) if cat else []
    words += fit.matched_keywords(ctx["c"].get("industry_desc") or "", thesis)
    if prof:
        words += [w.replace("_", " ") for w in prof["words"]]
    out = []
    for w in words:
        f = " ".join(re.findall(r"\w+", str(w).casefold()))
        if len(f) >= 5 and f not in out and not f.endswith("portfolio") and not f.startswith("nordic blue"):
            out.append(f)
    return out


def _hit(words: list[str], text: str) -> str | None:
    t = " " + " ".join(re.findall(r"\w+", (text or "").casefold())) + " "
    return next((w for w in words if f" {w}" in t), None)


def _grow(name, kind, reason, url, day, origin, *, confidence=None, key=(9,)) -> dict:
    return {"name": name, "kind": kind, "reason": reason, "score": None, "source_url": url, "confidence": confidence,
            "deadline": None, "origin": origin, "facts": None, "date": day, "_key": key}


def _finish(rows: list[dict], limit: int) -> list[dict]:
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["_key"]):
        f = fold(r["name"])
        if f in seen or not r.get("source_url"):
            continue
        seen.add(f)
        out.append(r)
    for i, r in enumerate(out[:limit], 1):
        r["rank"] = i
        del r["_key"]
    return out[:limit]


def _stage_fits(stages: str | None, stage: str | None) -> str | None:
    """'fits' | 'unknown' | None (outside the stated window)."""
    if not stages or not stage:
        return "unknown"
    return "fits" if stage in {x.strip() for x in re.split(r"[;,]", stages)} else None


def _dataset_investors(eco, prof: dict | None, ctx: dict) -> list[dict]:
    if not prof or not prof["caps"]:
        return []
    caps = set(prof["caps"])
    q = ",".join("?" * len(caps))
    similar = {x[0]: x[1] for x in eco.execute(
        f"""SELECT DISTINCT e.id, e.name FROM entity e JOIN entity_capability c ON c.entity_id=e.id
            WHERE e.side='supply' AND c.code IN ({q}) AND e.id<>?""", (*caps, prof["id"]))}
    backed: dict[str, list[str]] = {}
    for ei in eco.execute("SELECT entity_id, investor_name FROM entity_investor"):
        if ei["entity_id"] in similar:
            backed.setdefault(fold(ei["investor_name"]), []).append(similar[ei["entity_id"]])
    declared_member = ctx["c"]["group_tag"] in ("cohort", "portfolio")
    out = []
    for e in eco.execute("SELECT * FROM entity WHERE side='capital' AND entity_type IN ('investor_vc','investor_angel','investor_corporate')"):
        if e["status"] in INACTIVE or (declared_member and _is_partner(e["name"])):
            continue
        fit_stage = _stage_fits(e["inv_stages"], prof["stage"])
        if fit_stage is None:
            continue
        own = {x[0] for x in eco.execute("SELECT code FROM entity_capability WHERE entity_id=?", (e["id"],))} & caps
        names = backed.get(fold(e["name"]), [])
        if not own and not names:
            continue
        bits = []
        if fit_stage == "fits":
            bits.append(f"funds the company's stage ({prof['stage'].replace('_', ' ')}; stated stages: {e['inv_stages']})")
        else:
            bits.append("stage window not stated")
        if own:
            bits.append(f"funds capability {_cap_text(prof, own)}")
        if names:
            bits.append(f"backed {len(names)} company{'ies' if len(names) != 1 else ''} with the same capability: {', '.join(sorted(set(names))[:3])}")
        out.append(_grow(e["name"], (e["entity_type"] or "").replace("_", " "), "; ".join(bits) + " (declared ecosystem dataset).",
                         _eco_url(eco, e["id"], e["website"]), e["last_verified"], "ecosystem dataset",
                         confidence=e["confidence"], key=(0 if fit_stage == "fits" else 1, -len(names), -len(own), e["name"].casefold())))
    return out


_FUNDERS = {"bf_funding": "Business Finland", "public_funding": "Public grant", "eu_project": None}


def _programme(detail: str | None) -> str:
    m = re.search(r"\((Horizon Europe|H2020|Horizon 2020|LIFE|Interreg|EMFAF|Digital Europe)\b", detail or "")
    return m.group(1) if m else "EU programme"


def _year_label(s: dict) -> str:
    return s.get("date_label") or s["date"]


def _public_funding(conn, eco, prof: dict | None, ctx: dict, topic: list[str], t: date) -> list[dict]:
    out, c = [], ctx["c"]
    own: dict[str, list] = {}
    for s in ctx["sigs"]:
        if s["signal_type"] in _FUNDERS:
            own.setdefault(_FUNDERS[s["signal_type"]] or _programme(s.get("detail")), []).append(s)
    for funder, sigs in own.items():
        last = max(sigs, key=lambda s: s["date"])
        out.append(_grow(funder, "public funder", f"Funded this company {len(sigs)} time{'s' if len(sigs) != 1 else ''}, latest "
                         f"{_year_label(last)} ({store.SOURCE_LABELS.get(last['adapter'], last['adapter'])}).", last["source_url"],
                         last["date"], "this company's records", confidence=last["confidence"], key=(0, -len(sigs))))
    since = (t - timedelta(days=3 * 365)).isoformat()
    code = (c.get("industry_code") or "").strip()
    if code:
        rows = conn.execute("""SELECT s.date, s.source_url, s.company_key FROM signals s JOIN companies co USING (company_key)
                               WHERE s.signal_type='bf_funding' AND co.industry_code=? AND s.company_key<>? AND s.date>=?""",
                            (code, c["company_key"], since)).fetchall()
        firms = {r["company_key"] for r in rows}
        if firms and "Business Finland" not in own:
            last = max(rows, key=lambda r: r["date"])
            out.append(_grow("Business Finland", "public funder", f"Funded {len(firms)} other compan{'ies' if len(firms) != 1 else 'y'} "
                             f"with the same industry code {code} ({c.get('industry_desc') or 'line of business not stated'}) since {since[:4]}.",
                             last["source_url"], last["date"], "Business Finland export", confidence="high", key=(1, -len(firms))))
    if topic:
        per: dict[str, list] = {}
        for s in conn.execute("SELECT detail, date, source_url FROM signals WHERE signal_type='eu_project' AND company_key<>? AND date>=?",
                              (c["company_key"], since)):
            w = _hit(topic, _project_text(s["detail"]))
            if w:
                per.setdefault(_programme(s["detail"]), []).append((s, w))
        for prog, hits in per.items():
            if prog in own:
                continue
            s, w = max(hits, key=lambda h: h[0]["date"])
            out.append(_grow(prog, "EU funding programme", f"Funded {len(hits)} project{'s' if len(hits) != 1 else ''} since {since[:4]} "
                             f"whose title holds the company's topic word '{w}'; latest started {s['date']} (CORDIS).", s["source_url"],
                             s["date"], "CORDIS", confidence="medium", key=(2, -len(hits))))
    profile = blueinvest.profile_for(conn, c["company_key"])
    if profile and profile.get("url"):
        out.append(_grow("EU BlueInvest", "public programme", "Lists this company in the BlueInvest project pipeline"
                         + (f" (TRL {profile['trl']} stated)." if profile.get("trl") is not None else "."), profile["url"],
                         profile.get("listed_date"), "BlueInvest pipeline", confidence="high", key=(0, 0)))
    if eco is not None and prof and prof["caps"]:
        q = ",".join("?" * len(prof["caps"]))
        scores = {m[0]: m[1] for m in eco.execute("SELECT target_id, score FROM match WHERE supply_id=?", (prof["id"],))}
        for e in eco.execute(f"""SELECT e.*, group_concat(c.code) AS shared FROM entity e JOIN entity_capability c ON c.entity_id=e.id
                                 WHERE e.entity_type='public_funder' AND c.code IN ({q}) GROUP BY e.id""", prof["caps"]):
            fit_stage = _stage_fits(e["inv_stages"], prof["stage"])
            if e["status"] in INACTIVE:
                continue
            shared = set(e["shared"].split(","))
            bits = [f"funds capability {_cap_text(prof, shared)}"]
            if fit_stage == "fits":
                bits.append(f"funds the company's stage ({prof['stage'].replace('_', ' ')}; stated stages: {e['inv_stages']})")
            elif fit_stage is None:  # a public funder's stated stages rank, never exclude: grants serve every stage
                bits.append(f"stated stages {e['inv_stages']} do not list the company's stage ({prof['stage'].replace('_', ' ')})")
            if e["id"] in scores:
                bits.append(f"dataset match score {scores[e['id']]:g}")
            reason = "; ".join(bits)
            out.append(_grow(e["name"], "public funder", reason[0].upper() + reason[1:] + " (declared ecosystem dataset).",
                             _eco_url(eco, e["id"], e["website"]), e["last_verified"], "ecosystem dataset", confidence=e["confidence"],
                             key=(3, {"fits": 0, "unknown": 1}.get(fit_stage, 2), -len(shared), -scores.get(e["id"], 0), e["name"].casefold())))
    return out


def _contract(detail: str | None) -> tuple[str | None, str, float | None]:
    d = detail or ""
    if ": " not in d:
        return None, "", None
    buyer, rest = d.split(": ", 1)
    m = re.search(r" \(EUR ([\d,\.]+)\)$", rest)
    value = float(m.group(1).replace(",", "")) if m else None
    title = re.sub(r" \(EUR [^)]*\)$", "", rest).strip()
    buyer = buyer.strip()
    return (None if not buyer or buyer == "buyer not stated" else buyer), title, value


def _buyers(conn, ctx: dict, thesis: dict, topic: list[str], t: date) -> list[dict]:
    c = ctx["c"]
    code = (c.get("industry_code") or "").strip()
    since = (t - timedelta(days=BUYER_MONTHS * 30)).isoformat()
    best: dict[str, dict] = {}
    for s in conn.execute("""SELECT s.company_key, s.date, s.detail, s.source_url, co.industry_code, co.name AS winner
                             FROM signals s JOIN companies co USING (company_key)
                             WHERE s.signal_type='public_contract' AND s.date>=? AND s.date<=? ORDER BY s.date DESC""",
                          (since, t.isoformat())):
        buyer, title, value = _contract(s["detail"])
        if buyer is None:
            continue
        ic = (s["industry_code"] or "").strip()
        if s["company_key"] == c["company_key"]:
            tier, why = 0, "already bought from this company"
        elif code and ic == code:
            tier, why = 1, f"bought from a company with the same industry code {code}"
        elif code and ic[:2] == code[:2]:
            tier, why = 2, f"bought from a company in the same industry division {code[:2]}"
        elif _hit(topic, title):
            tier, why = 3, f"contract title holds the company's topic word '{_hit(topic, title)}'"
        else:
            continue  # a thesis-wide word alone (Finnish compounds: 'vesi' is also in 'vesikatto', a roof) is not the company's category
        b = best.get(buyer)
        if b is None or tier < b["tier"]:
            best[buyer] = {"tier": tier, "why": why, "n": 1, "value": value or 0, "last": s, "title": title, "lv": value}
        elif tier == b["tier"]:
            b["n"] += 1
            b["value"] += value or 0
    out = []
    for buyer, b in best.items():
        s = b["last"]
        val = f", EUR {b['lv']:,.0f}" if b["lv"] else ""
        total = f"; EUR {b['value']:,.0f} in total" if b["n"] > 1 and b["value"] else ""
        out.append(_grow(buyer, "public buyer", f"Awarded {b['n']} contract{'s' if b['n'] != 1 else ''} since {since[:7]}: {b['why']}{total}. "
                         f"Latest {s['date']}: {b['title'][:120]}{val} (Hilma).", s["source_url"], s["date"], "Hilma notices",
                         confidence="high" if b["tier"] == 0 else "medium" if b["tier"] <= 2 else "low",
                         key=(b["tier"], -b["n"], "".join(chr(255 - ord(ch)) for ch in s["date"]))))
    return out


def _project_text(detail: str | None) -> str:
    """The CORDIS part of an eu_project detail (acronym, title, programme), without our own 'Matched ...' annotation."""
    d = detail or ""
    if d.startswith("Matched"):
        d = d.split(". ", 1)[1] if ". " in d else ""
    return d


def _project_partners(conn, ctx: dict, thesis: dict, topic: list[str]) -> list[dict]:
    from radar import fit
    c = ctx["c"]
    mine = {s["source_url"]: s for s in ctx["sigs"] if s["signal_type"] == "eu_project"}
    out = []
    for s in conn.execute("""SELECT s.company_key, s.date, s.detail, s.source_url, co.name FROM signals s JOIN companies co USING (company_key)
                             WHERE s.signal_type='eu_project' AND s.company_key<>? ORDER BY s.date DESC""", (c["company_key"],)):
        if fit.looks_like_person(s["name"], thesis) or store.is_partner_org(s["name"]):
            continue
        text = _project_text(s["detail"])
        project = text.split(" (")[0][:120] or "the project"
        role = re.search(r"role (\w+)", text)
        role = f", role {role.group(1)}" if role else ""
        if s["source_url"] in mine:
            out.append(_grow(s["name"], "project partner", f"In the same EU project as this company: {project}{role}, start {s['date']} (CORDIS).",
                             s["source_url"], s["date"], "CORDIS", confidence="high", key=(0, "".join(chr(255 - ord(ch)) for ch in s["date"]))))
            continue
        w = _hit(topic, text)
        if w:
            out.append(_grow(s["name"], "project partner", f"Took part in an EU project whose title holds the company's topic word '{w}': "
                             f"{project}{role}, start {s['date']} (CORDIS).", s["source_url"], s["date"], "CORDIS", confidence="low",
                             key=(1, "".join(chr(255 - ord(ch)) for ch in s["date"]))))
    return out


def _research_institutes(eco, prof: dict | None) -> list[dict]:
    if eco is None or not prof:
        return []
    out = []
    for m in eco.execute("""SELECT m.target_id, m.score, m.why, e.name, e.website, e.last_verified, e.confidence, e.status FROM match m
                            JOIN entity e ON e.id=m.target_id WHERE m.supply_id=? AND e.entity_type='research_org'""", (prof["id"],)):
        if m["status"] in INACTIVE or not (m["why"] or "").strip():
            continue
        out.append(_grow(m["name"], "research institute", f"Dataset match score {m['score']:g}: {m['why'].strip()} (declared ecosystem dataset).",
                         _eco_url(eco, m["target_id"], m["website"]), m["last_verified"], "ecosystem dataset", confidence=m["confidence"],
                         key=(0, -m["score"])))
    if prof["caps"]:
        q = ",".join("?" * len(prof["caps"]))
        for e in eco.execute(f"""SELECT e.*, group_concat(c.code) AS shared FROM entity e JOIN entity_capability c ON c.entity_id=e.id
                                 WHERE e.entity_type='research_org' AND c.code IN ({q}) GROUP BY e.id""", prof["caps"]):
            if e["status"] in INACTIVE:
                continue
            shared = set(e["shared"].split(","))
            out.append(_grow(e["name"], "research institute", f"Works on capability {_cap_text(prof, shared)} (declared ecosystem dataset).",
                             _eco_url(eco, e["id"], e["website"]), e["last_verified"], "ecosystem dataset", confidence=e["confidence"],
                             key=(1, -len(shared), e["name"].casefold())))
    return out


def wider_groups(conn, thesis: dict, ctx: dict, t: date, limit: int = 5) -> dict:
    """The four added groups plus the dataset investors that widen 'investors'. Each row {name, kind, reason, source_url, date,
    rank, confidence, origin}. Empty stays empty."""
    eco = _eco_db()
    try:
        prof = _eco_profile(eco, ctx) if eco is not None else None
        topic = _topic_words(ctx, thesis, prof)
        return {
            "investors_extra": _finish(_dataset_investors(eco, prof, ctx) if eco is not None else [], 10**6),
            "public_funding": _finish(_public_funding(conn, eco, prof, ctx, topic, t), limit),
            "buyers": _finish(_buyers(conn, ctx, thesis, topic, t), limit),
            "project_partners": _finish(_project_partners(conn, ctx, thesis, topic), limit),
            "research_institutes": _finish(_research_institutes(eco, prof), limit),
        }
    finally:
        if eco is not None:
            eco.close()


def who_comes_next(company_key: str, thesis: dict, limit: int = 5, *, conn: sqlite3.Connection | None = None, today=None) -> dict:
    """{"investors", "funding", "partners"} as before, plus the added groups "public_funding", "buyers", "project_partners" and
    "research_institutes" (GROUPS gives the page order). Each row {name, kind, reason, source_url, date, rank, confidence, ...}.
    investors keeps the dataset's scored matches first and adds the capital sources whose stage and sector fit."""
    own = conn is None
    conn = conn or store.open_db(thesis=thesis)
    empty = {k: [] for k in (*LISTS, *(g for g, _ in GROUPS))}
    if conn is None:
        return empty
    try:
        ctx = company_context(conn, company_key)
        if ctx is None:
            return empty
        if ctx["status"] in INACTIVE:
            return empty  # a defunct company is not given leads
        t = store._today(today)
        full = _assemble(conn, thesis, company_key, ctx, t)
        out = {k: _rank(full[k], limit, reserve_programme=(k == "funding")) for k in LISTS}
        wide = wider_groups(conn, thesis, ctx, t, limit)
        have = {fold(r["name"]) for r in out["investors"]}
        extra = [r for r in wide.pop("investors_extra") if fold(r["name"]) not in have]
        out["investors"] = (out["investors"] + extra)[:limit]
        for i, r in enumerate(out["investors"], 1):
            r["rank"] = i
        for k in LISTS:
            for r in out[k]:
                r.setdefault("date", r.get("deadline"))
        out.update(wide)
        return out
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
