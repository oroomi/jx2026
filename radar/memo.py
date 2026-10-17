"""The fund memo for one company: what the fund or accelerator should do, not only what the company is. Rules only, no LLM, so it
runs live with no API key. Everything is addressed to the fund, never to the company.

One decision per company, exactly one of DECISIONS. It comes from a decision table stored as data in the thesis file
(`memo.decisions.rows`): four cells (impact, business, investment, thesis fit), each Low / Medium / High, first matching row wins,
no match is WATCHLIST. The Low / Medium / High cells come from the sponsor-framework levels through the bands in `memo.bands`.
A level with no public evidence is "unknown", never Low: a row that names a band does not match it, so the company lands in
WATCHLIST with "more public evidence needed: <level>". REJECT / LOW FIT needs evidence of low fit and low impact.
Nothing is said without a link: a bullet with no source row is an evidence gap and is shown as one."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from radar import labels
from radar import blueinvest, frameworks, matching, store

DECISIONS = ("INVEST", "DUE DILIGENCE", "ACCELERATOR", "GRANT SUPPORT", "PARTNER INTRODUCTION", "WATCHLIST", "REJECT / LOW FIT")
BANDS = ("Low", "Medium", "High")
TABLE_DIMS = ("impact", "business", "investment", "fit")
UNKNOWN = "unknown"
MAX_ACTIONS = 3
DEADLINE_DAYS = 120
_ACCEL = ("accelerator", "incubator")


def _cfg(thesis: dict) -> dict:
    m = thesis.get("memo") or {}
    d = m.get("decisions") or {}
    return {"labels": m.get("labels") or {}, "bands": m.get("bands") or {}, "rows": d.get("rows") or [], "rules": d.get("rules") or [],
            "source": d.get("source") or ""}


def band(value, spec: dict | None) -> str:
    """Low / Medium / High for a numeric level; unknown when there is no level."""
    if value is None or not spec:
        return UNKNOWN
    if value <= spec.get("low_max", 0):
        return "Low"
    return "High" if value >= spec.get("high_min", 10) else "Medium"


LETTER = {"High": "H", "Medium": "M", "Low": "L", UNKNOWN: "?"}


def _cell_matches(cell, value: str) -> bool:
    if cell in (None, "any"):
        return True
    cells = cell if isinstance(cell, list) else [cell]
    return value in cells  # "unknown" is never in a concrete list


def decide(bands: dict[str, str], cfg: dict) -> tuple[dict | None, list[str]]:
    """Pass 1: the first table row whose four cells all equal the bands. Pass 2: the first condition rule that holds. A cell that
    needs a band never matches "unknown". Returns ({kind, id, ...row} or None, unknown dimensions)."""
    for r in cfg["rows"]:
        if all(_cell_matches(r.get(d), bands[d]) for d in TABLE_DIMS):
            return {**r, "kind": "row", "text": f"row {r['id']}, " + "/".join(LETTER[bands[d]] for d in TABLE_DIMS)}, []
    for r in cfg["rules"]:
        if all(_cell_matches(v, bands.get(k, UNKNOWN)) for k, v in (r.get("when") or {}).items()):
            return {**r, "kind": "rule", "text": f"rule {r['id']}"}, []
    return None, [d for d in (*TABLE_DIMS, "technology") if bands.get(d) == UNKNOWN]


def _latest(ev: list[dict]) -> str | None:
    return max(ev, key=lambda s: s["date"])["source_url"] if ev else None


def _levels(conn, ctx: dict, key: str, cfg: dict) -> dict:
    """{dimension: {level, because, url}} for technology, business, investment: rule levels, with the BlueInvest or dataset TRL."""
    fw = ctx["fw"]
    out = {}
    for dim, k in (("technology", "trl"), ("business", "brl"), ("investment", "irl")):
        lv = fw[k]
        out[dim] = {"level": lv["level"], "because": lv["because"], "url": _latest(lv["evidence"]) if lv["level"] is not None else None}
    if ctx["trl"] is not None and ctx["trl_src"] != "register rule":
        if ctx["trl_src"] == "BlueInvest profile":
            url = (blueinvest.profile_for(conn, key) or {}).get("url")
            out["technology"] = {"level": ctx["trl"], "because": f"the BlueInvest profile states TRL {ctx['trl']}", "url": url}
        else:
            out["technology"] = {"level": ctx["trl"], "because": f"the declared research dataset reads TRL {ctx['trl']}", "url": _dataset_url(conn, key)}
    dims = [d for d in ctx["fw"]["dimensions"] if d["n"] > 0]
    url = next((e["url"] for d in dims for e in d["evidence"] if e.get("url")), None)
    out["investment"] = {"level": len(dims) or None, "url": url if dims else None,
                         "because": f"{len(dims)} of the {len(ctx['fw']['dimensions'])} investment dimensions have public evidence"}
    return out


def _dataset_url(conn, key: str) -> str | None:
    try:
        row = conn.execute("SELECT sources FROM eco_readiness WHERE company_key=?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    for u in ((row[0] if row else "") or "").split():
        if u.startswith("http"):
            return u
    return None


def _impact(conn, ctx: dict, key: str, spec: dict) -> dict:
    """Ocean impact (or the thesis's impact dimension): a Navigator-style category found by the rule, or the dataset's reading."""
    try:
        r = conn.execute("SELECT oir_score, oir_evidence FROM eco_readiness WHERE company_key=?", (key,)).fetchone()
    except sqlite3.OperationalError:
        r = None
    url = _dataset_url(conn, key)
    if r and r[0] is not None and url:
        b = "Low" if r[0] <= spec.get("dataset_low_max", -1) else ("High" if r[0] >= spec.get("dataset_high_min", 99) else "Medium")
        return {"band": b, "text": f"the declared dataset reads impact readiness {r[0]}" + (f": {r[1]}" if r[1] else ""), "url": url}
    cat = ctx["fw"]["category"]
    if cat.get("category") and spec.get("category_band"):
        ev = cat.get("evidence") or {}
        url = ev.get("url") or (ctx["c"].get("source_url") if cat.get("industry") else None)
        if url:
            return {"band": spec["category_band"], "text": f"works in the '{cat['category']}' category (keyword '{cat['keyword']}')", "url": url}
    return {"band": UNKNOWN, "text": None, "url": None}


def _fit(conn, ctx: dict, thesis: dict, spec: dict) -> dict:
    """Thesis fit from the same explain() the feed uses. industry_code or own_text = High; line_of_business or corroborated_keyword =
    Medium; only the legal name = Low; no reason = unknown. A declared cohort or portfolio company has at least the configured floor."""
    from radar import fit as fit_mod
    c, sigs = ctx["c"], ctx["sigs"]
    feed_types = set(thesis.get("feed_signal_types") or [])
    own = [s for s in sigs if s["adapter"] != "ecosystem" and s["signal_type"] in feed_types]
    first = own[0] if own else {"signal_type": "register_entry", "adapter": "prh", "detail": None, "date": c.get("founded") or "", "id": -1}
    row = {**c, **first}
    ex = store.explain(row, [s for s in own if s is not own[0]] if own else [], thesis, store.source_texts(conn, own))
    reasons = ex["reasons"]
    bullets = []
    if ex["strength"] == "strong":
        shared = ("industry_code", "line_of_business", "corroborated_keyword")
        bullets.append({"text": ex["why"].removeprefix("Why: "),
                        "url": c.get("source_url") if reasons[0] in shared else (own[0]["source_url"] if own else c.get("source_url"))})
    if any(r in reasons for r in spec.get("high", [])):
        b = "High"
    elif any(r in reasons for r in spec.get("medium", [])):
        b = "Medium"
    elif fit_mod.matched_keywords(c.get("name"), thesis) and c.get("source_url"):
        b = "Low"
        bullets.append({"text": ex["why"].removeprefix("Weak: "), "url": c["source_url"]})
    else:
        b = UNKNOWN
    if c["group_tag"] in ("cohort", "portfolio") and c.get("source_url"):
        floor = spec.get("declared_member_band")
        if floor and BANDS.index(floor) > (BANDS.index(b) if b in BANDS else -1):
            b = floor
        bullets.append({"text": f"declared {c['group_tag']} company", "url": c["source_url"]})
    return {"band": b, "bullets": bullets}


def _why_now(ctx: dict, funding: list[dict], today: date) -> dict | None:
    cands = []
    for r in funding:
        d = r.get("deadline")
        if d and r.get("source_url") and today.isoformat() <= d <= (today + timedelta(days=DEADLINE_DAYS)).isoformat():
            cands.append((abs((date.fromisoformat(d) - today).days), f"{r['name']} closes {d}", r["source_url"], d))
    for s in ctx["sigs"]:
        d = s.get("date")
        if d and s.get("source_url") and (today - timedelta(days=180)).isoformat() <= d <= today.isoformat():
            label = s.get("type_label") or labels.signal_label(s["signal_type"])
            cands.append((abs((date.fromisoformat(d) - today).days), f"{label} on {s.get('date_label') or d}", s["source_url"], d))
    if not cands:
        return None
    _, text, url, d = min(cands)
    return {"text": text, "url": url, "date": d}


def _actions(decision: str, nxt: dict, step: dict, unknown: list[str], labels: dict, c: dict, sigs: list[dict]) -> list[dict]:
    """1 to 3 actions for the fund, named from the who-comes-next lists, each with its source row."""
    out: list[dict] = []

    def add(text, url, source):
        if url and not any(a["text"] == text for a in out):
            out.append({"text": text, "url": url, "source": source})

    inv, fund, part = nxt["investors"], nxt["funding"], nxt["partners"]
    src = lambda r: labels.origin_label(r.get("origin")) if r.get("origin") else ("ecosystem dataset" if r.get("score") is not None else "declared list")  # noqa: E731
    if decision in ("INVEST", "DUE DILIGENCE"):
        for r in inv[:2]:
            add(f"Introduce them to {r['name']}: {r['reason']}", r["source_url"], src(r))
    elif decision == "ACCELERATOR":
        for r in [f for f in fund if any(w in (f["kind"] or "") for w in _ACCEL)][:2] or fund[:1]:
            when = f" before {r['deadline']}" if r.get("deadline") else f" (deadline: {r.get('deadline_text') or 'not stated'})"
            add(f"Put them forward for {r['name']}{when}", r["source_url"], src(r))
    elif decision == "GRANT SUPPORT":
        for r in [f for f in fund if not any(w in (f["kind"] or "") for w in _ACCEL)][:3] or fund[:2]:
            when = f" before {r['deadline']}" if r.get("deadline") else f" (deadline: {r.get('deadline_text') or 'not stated'})"
            add(f"Point them to {r['name']}{when}", r["source_url"], src(r))
    elif decision == "PARTNER INTRODUCTION":
        for r in part[:3]:
            add(f"Introduce them to {r['name']}: {r['reason']}", r["source_url"], src(r) if r.get("origin") else "Hilma notice")
    elif decision == "WATCHLIST":
        if unknown:
            add("Revisit when the radar finds public evidence for: " + ", ".join(labels.get(d, d) for d in unknown), c.get("source_url"), "company record")
        if step["rule"] != 5 and step.get("source_url"):
            add(step["sentence"], step["source_url"], f"decision table, rule {step['rule']}")
        last = max((x for x in sigs if x.get("source_url")), key=lambda x: x["date"], default=None)
        if last and not unknown:
            add(f"Watch: reassess when the next public record appears (latest on file: {last['date']})", last["source_url"], "latest record on file")
    if decision in ("INVEST", "DUE DILIGENCE") and step["rule"] in (1, 2) and step.get("source_url"):
        add(step["sentence"], step["source_url"], f"decision table, rule {step['rule']}")
    return out[:MAX_ACTIONS]


def build(conn: sqlite3.Connection, thesis: dict, company_key: str, *, today=None) -> dict | None:
    """The memo, or None when the company is not in the database."""
    ctx = matching.company_context(conn, company_key)
    if ctx is None:
        return None
    cfg = _cfg(thesis)
    t = store._today(today)
    c = ctx["c"]
    lv = _levels(conn, ctx, company_key, cfg)
    imp = _impact(conn, ctx, company_key, cfg["bands"].get("impact") or {})
    fit = _fit(conn, ctx, thesis, cfg["bands"].get("fit") or {})
    bands = {"impact": imp["band"], "business": band(lv["business"]["level"], cfg["bands"].get("business")),
             "investment": band(lv["investment"]["level"], cfg["bands"].get("investment")), "fit": fit["band"]}
    tech_band = band(lv["technology"]["level"], cfg["bands"].get("technology"))
    bands["technology"] = tech_band
    nxt = matching.who_comes_next(company_key, thesis, 5, conn=conn, today=t)
    step = matching.next_step(company_key, thesis, conn=conn, today=t)

    if ctx["status"] in matching.INACTIVE:
        row, unknown, decision = None, [], "WATCHLIST"
    else:
        row, unknown = decide(bands, cfg)
        decision = row["decision"] if row else "WATCHLIST"
    labels = cfg["labels"]
    needed = [d for d in unknown]  # dimensions with no public evidence while no row matched
    because = " / ".join(f"{bands[d]}" for d in TABLE_DIMS)
    rec = {"decision": decision, "row_id": row["id"] if row else None, "table_action": row.get("action") if row else None,
           "matched": row["text"] if row else None, "team_label": row.get("team") if row else None,
           "because": because, "because_labels": [{"label": labels.get(d, d), "band": bands[d]} for d in TABLE_DIMS],
           "table_source": cfg["source"], "needs": [labels.get(d, d) for d in needed]}
    if row is None:
        rec["note"] = ("The company has defunct status in the declared dataset." if ctx["status"] in matching.INACTIVE else
                       ("more public evidence needed: " + ", ".join(rec["needs"]) if needed else "no decision row or rule matches these levels, so the company stays on the watchlist"))

    why = []
    for dim, label in (("impact", labels.get("impact", "impact")),):
        if imp["url"]:
            why.append({"text": f"{label} {imp['band']}: {imp['text']}", "url": imp["url"]})
    for dim in ("business", "investment", "technology"):
        v = lv[dim]
        if v["level"] is not None and v["url"]:
            b = bands.get(dim) or tech_band
            why.append({"text": f"{labels.get(dim, dim)} {b} (level {v['level']}): {v['because']}", "url": v["url"]})
    why += [{"text": f"Thesis fit: {b['text']}", "url": b["url"]} for b in fit["bullets"] if b.get("url")]
    wn = _why_now(ctx, nxt["funding"], t)
    if wn:
        why.append({"text": f"Why now: {wn['text']}", "url": wn["url"]})

    risks = []
    for d in TABLE_DIMS:
        if bands[d] == UNKNOWN:
            risks.append({"text": f"No public evidence for {labels.get(d, d).lower()}", "url": None})
        elif bands[d] == "Low":
            src = {"business": lv["business"], "investment": lv["investment"]}.get(d) or (imp if d == "impact" else None)
            risks.append({"text": f"{labels.get(d, d)} is Low on the stored evidence", "url": (src or {}).get("url") or c.get("source_url")})
    for dim in ctx["fw"]["dimensions"]:
        if dim["name"] in ("Market", "Financials") and not dim["evidence"]:
            risks.append({"text": f"No public {dim['name'].lower()} evidence ({dim['note']})", "url": None})
    if tech_band == UNKNOWN:
        risks.append({"text": f"No public evidence for {labels.get('technology', 'technology').lower()}", "url": None})

    return {"company_key": company_key, "name": c["name"], "recommendation": rec, "why": why, "risks": risks,
            "actions": _actions(decision, nxt, step, unknown, labels, c, ctx["sigs"]),
            "levels": {**{d: {"band": bands[d]} for d in TABLE_DIMS}, "technology": {"band": tech_band}}, "as_of": t.isoformat()}


def for_template(company_key: str, thesis: dict) -> dict | None:
    """Template hook: the memo from its own read-only connection, so the company route needs no edit."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        return build(conn, thesis, company_key)
    finally:
        conn.close()
