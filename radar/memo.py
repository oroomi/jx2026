"""The fund memo for one company: what the investor should do, not only what the company is. Rules only, no LLM, so it runs
live with no API key. Every sentence is addressed to the fund or accelerator, never to the company.

Inputs are what the company page already computes: the readiness levels (radar.matching.company_context), the fit reasons
(radar.fit), the ranked leads (radar.matching.who_comes_next) and the decision table (radar.matching.next_step).
Thresholds and the gap table live in the thesis file, section `memo:`; nothing sector specific is in this module.
Nothing is shown without a link: a part with no source row is returned as None and the page draws a hatched chip."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from radar import blueinvest, fit as fit_mod, matching, store

VERDICTS = ("Meet now", "Introduce", "Watch", "Check in", "Not enough evidence yet")
DIMS = (("technology", "trl"), ("business", "brl"), ("investment", "irl"))
MAX_ACTIONS = 3


def _cfg(thesis: dict) -> dict:
    m = thesis.get("memo") or {}
    v = m.get("verdict") or {}
    return {"min_gap": int(m.get("min_gap") or 2), "labels": m.get("labels") or {k: k.title() for k, _ in DIMS}, "gaps": m.get("gaps") or [],
            "min_records": int(v.get("min_records") or 2), "min_levels": int(v.get("min_levels") or 2),
            "min_fit": int(v.get("min_fit_reasons") or 1), "deadline_days": int(v.get("deadline_days") or 90),
            "recent_days": int(v.get("recent_days") or 180), "stale_days": int(v.get("stale_days") or 365)}


def verdict_rules(cfg: dict) -> dict[str, str]:
    """The printed rule behind each verdict, built from the thresholds."""
    return {
        "Check in": f"A declared cohort or portfolio company with no dated public record in the last {cfg['stale_days']} days.",
        "Not enough evidence yet": f"Fewer than {cfg['min_records']} linked public records.",
        "Meet now": (f"At least {cfg['min_fit']} fit reason of medium or high confidence, readiness evidence on at least {cfg['min_levels']} levels, "
                     f"and a dated reason: an open deadline within {cfg['deadline_days']} days or a public record within the last {cfg['recent_days']} days."),
        "Introduce": "Not yet a meeting, but the lists hold a ranked investor or an open programme with a stated reason and a link.",
        "Watch": "Evidence exists, but no ranked investor or open programme fits yet; the radar keeps watching the records.",
    }


def _levels(conn, ctx: dict, key: str) -> dict:
    """{dimension: {level, because, url, source}} for technology, business, investment. Level None means no evidence."""
    fw = ctx["fw"]
    out = {}
    for dim, k in DIMS:
        lv = fw[k]
        ev = lv["evidence"]
        url = max(ev, key=lambda s: s["date"])["source_url"] if ev else None
        because, level, src = lv["because"], lv["level"], "register rule"
        if dim == "technology" and ctx["trl"] is not None and (level is None or ctx["trl_src"] != "register rule"):
            level, src = ctx["trl"], ctx["trl_src"]
            if ctx["trl_src"] == "BlueInvest profile":
                prof = blueinvest.profile_for(conn, key)
                url, because = (prof or {}).get("url"), f"the BlueInvest profile states TRL {ctx['trl']}"
            else:
                url, because = None, f"the declared research dataset reads TRL {ctx['trl']}"
        out[dim] = {"level": level, "because": because, "url": url if level is not None else None, "source": src}
    return out


def _gap(levels: dict, cfg: dict) -> dict | None:
    """The biggest difference between two levels as one diagnosis line, from the gap table in the thesis file."""
    have = {d: v["level"] for d, v in levels.items() if v["level"] is not None}
    miss = [cfg["labels"].get(d, d) for d in levels if levels[d]["level"] is None]
    best = None
    for a in have:
        for b in have:
            diff = have[a] - have[b]
            if diff >= cfg["min_gap"] and (best is None or diff > best[0]):
                best = (diff, a, b)
    if best:
        diff, a, b = best
        row = next((g for g in cfg["gaps"] if g["ahead"] == a and g["behind"] == b), None)
        if row:
            src = levels[a]["url"]
            return {"text": f"{row['text']} ({cfg['labels'].get(a, a)} level {have[a]}, {cfg['labels'].get(b, b)} level {have[b]}.)",
                    "action": row.get("action"), "ahead": a, "behind": b, "url": src}
        return None
    if have and miss:
        return {"text": f"No public evidence yet for: {', '.join(miss)}.", "action": None, "ahead": None, "behind": None,
                "url": next((levels[d]["url"] for d in have if levels[d]["url"]), None)}
    if have:
        return {"text": f"No gap of {cfg['min_gap']} or more levels between technology, business and investment.", "action": None,
                "ahead": None, "behind": None, "url": next((levels[d]["url"] for d in have if levels[d]["url"]), None)}
    return None


def _strength(levels: dict, reasons: list[dict], cfg: dict) -> dict | None:
    cands = [(v["level"], -i, d, v) for i, (d, v) in enumerate(levels.items()) if v["level"] is not None and v["url"]]
    if cands:
        lv, _, d, v = max(cands, key=lambda c: (c[0], c[1]))
        return {"text": f"{cfg['labels'].get(d, d)} is the strongest level: {lv} ({v['because']}).", "url": v["url"], "kind": "level"}
    for r in reasons:
        url = (r.get("evidence") or {}).get("url")
        if url:
            return {"text": r["text"], "url": url, "kind": "fit"}
    return None


def _why_now(ctx: dict, funding: list[dict], today: date, cfg: dict) -> dict | None:
    """The nearest dated reason: an open deadline soon, or a recent public record. Always with its date and link."""
    cands = []
    for r in funding:
        d = r.get("deadline")
        if d and r.get("source_url") and today.isoformat() <= d <= (today + timedelta(days=cfg["deadline_days"])).isoformat():
            cands.append((abs((date.fromisoformat(d) - today).days), d, f"{r['name']} closes {d}", r["source_url"], "deadline"))
    for s in ctx["sigs"]:
        d = s.get("date")
        if d and s.get("source_url") and (today - timedelta(days=cfg["recent_days"])).isoformat() <= d <= today.isoformat():
            label = s.get("type_label") or store.TYPE_LABELS.get(s["signal_type"], s["signal_type"])
            cands.append((abs((date.fromisoformat(d) - today).days), d, f"{label} on {s.get('date_label') or d}", s["source_url"], "record"))
    if not cands:
        return None
    _, d, text, url, kind = min(cands, key=lambda c: (c[0], c[2]))
    return {"text": text, "date": d, "url": url, "kind": kind}


def _declared(c: dict) -> bool:
    return c["group_tag"] in ("cohort", "portfolio")


def _stale(ctx: dict, today: date, cfg: dict) -> tuple[bool, str | None, str | None]:
    dated = [s for s in ctx["sigs"] if s["date"] <= today.isoformat()]
    last = max(dated, key=lambda s: s["date"], default=None)
    cut = (today - timedelta(days=cfg["stale_days"])).isoformat()
    if last is None:
        return True, None, ctx["c"]["source_url"]
    return last["date"] < cut, last["date"], last["source_url"]


def build(conn: sqlite3.Connection, thesis: dict, company_key: str, *, today=None) -> dict | None:
    """The memo, or None when the company is not in the database. Every part is None or empty when no source row supports it."""
    ctx = matching.company_context(conn, company_key)
    if ctx is None:
        return None
    cfg = _cfg(thesis)
    t = store._today(today)
    c, sigs = ctx["c"], ctx["sigs"]
    levels = _levels(conn, ctx, company_key)
    reasons = fit_mod.fit(c, sigs, thesis)
    good = [r for r in reasons if r.get("confidence") in ("high", "medium")]
    if _declared(c) and c.get("source_url"):
        good.append({"kind": "declared", "confidence": "high", "text": f"Declared {c['group_tag']} company.", "evidence": {"url": c["source_url"]}})
    nxt = matching.who_comes_next(company_key, thesis, 5, conn=conn, today=t)
    step = matching.next_step(company_key, thesis, conn=conn, today=t)
    records = [s for s in sigs if s.get("source_url")]
    present = [d for d, v in levels.items() if v["level"] is not None]
    gap = _gap(levels, cfg)
    strength = _strength(levels, reasons, cfg)
    why = _why_now(ctx, nxt["funding"], t, cfg)
    stale, last_date, last_url = _stale(ctx, t, cfg)
    rules = verdict_rules(cfg)

    if ctx["status"] in matching.INACTIVE:
        label, because = "Not enough evidence yet", "The declared ecosystem dataset marks this company as defunct."
    elif _declared(c) and stale:
        label = "Check in"
        because = f"Latest dated public record: {last_date}." if last_date else "No dated public record on file."
    elif len(records) < cfg["min_records"]:
        label, because = "Not enough evidence yet", f"{len(records)} linked public record{'s' if len(records) != 1 else ''} on file."
    elif len(good) >= cfg["min_fit"] and len(present) >= cfg["min_levels"] and why:
        label, because = "Meet now", f"{len(good)} fit reason(s), {len(present)} levels with evidence, and a dated reason: {why['text']}."
    elif nxt["investors"] or nxt["funding"]:
        label, because = "Introduce", f"{len(nxt['investors'])} ranked investor(s) and {len(nxt['funding'])} open programme(s) with reasons and links."
    else:
        label, because = "Watch", "No ranked investor or open programme fits on the stored records."
    verdict = {"label": label, "rule": rules[label], "because": because, "all_rules": [{"label": k, "rule": rules[k]} for k in
               ("Meet now", "Introduce", "Watch", "Check in", "Not enough evidence yet")]}

    actions: list[dict] = []

    def add(text, url, source):
        if url and text and not any(a["text"] == text for a in actions):
            actions.append({"text": text, "url": url, "source": source})

    if step["rule"] != 5 and step.get("source_url"):
        add(step["sentence"], step["source_url"], f"decision table, rule {step['rule']}")
    if label == "Check in":
        add(f"Check in: latest public record is from {last_date}" if last_date else "Check in: no dated public record on file", last_url, "latest record on file")
    inv = nxt["investors"][0] if nxt["investors"] else None
    if inv and inv["source_url"] and inv["name"] not in " ".join(a["text"] for a in actions):
        add(f"Introduce them to {inv['name']} ({inv['reason']})", inv["source_url"], "ecosystem dataset match" if inv.get("score") is not None else "declared list")
    prog = next((r for r in nxt["funding"] if r.get("deadline")), nxt["funding"][0] if nxt["funding"] else None)
    if prog and prog["source_url"] and prog["name"] not in " ".join(a["text"] for a in actions):
        when = f" before {prog['deadline']}" if prog.get("deadline") else f" (deadline: {prog.get('deadline_text') or 'not stated'})"
        add(f"Introduce them to {prog['name']}{when}", prog["source_url"], prog.get("origin") or "declared list")
    buyer = next((b for b in nxt["partners"] if b.get("kind") == "public buyer"), None)
    if buyer and buyer["name"] not in " ".join(a["text"] for a in actions):
        add(f"Ask about their {buyer['category']} contract with {buyer['name']} ({buyer['date']})", buyer["source_url"], "Hilma notice")
    if gap and gap.get("action"):
        add(gap["action"], gap["url"] or c.get("source_url"), "level gap table")
    actions = actions[:MAX_ACTIONS]

    return {"company_key": company_key, "name": c["name"], "verdict": verdict, "strength": strength, "gap": gap, "why_now": why, "actions": actions,
            "levels": {d: {"level": v["level"], "url": v["url"], "label": cfg["labels"].get(d, d)} for d, v in levels.items()},
            "as_of": t.isoformat()}


def for_template(company_key: str, thesis: dict) -> dict | None:
    """Template hook: the memo from its own read-only connection, so the company route needs no edit."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        return build(conn, thesis, company_key)
    finally:
        conn.close()
