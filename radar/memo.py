"""The fund memo for one company: what the fund or accelerator should do, not only what the company is. Rules only, no LLM, so it
runs live with no API key. Everything is addressed to the fund, never to the company.

One decision per company, exactly one of DECISIONS. It comes from a decision table stored as data in the thesis file
(`memo.decisions.rows`): four cells (impact, business, investment, thesis fit), each Low / Medium / High, first matching row wins,
then pass 3, the fallback (`memo.decisions.fallback`): thesis fit High with no impact evidence reads impact as implied by the sector,
but only when the High fit rests on more than an industry code (`fallback.requires_any`, see SUPPORT_KEYS); no match is WATCHLIST. The Low / Medium / High cells come from exactly the levels question 02 of the company page prints
(radar.frameworks.page_levels) through the bands in `memo.bands`; the impact cell is the exception, it is read from the Ocean Impact
Assessment when the thesis defines one (D46): the ladder's Medium or High is the impact band, a ladder level with no band
("not yet evidenced", sector-implied only) or no level stays unknown so the fallback applies.
A level with no public evidence is "unknown", never Low: a row that names a band does not match it, so the company lands in
WATCHLIST with "more public evidence needed: <level>". REJECT / LOW FIT needs evidence of low fit and low impact.
Nothing is said without a link: a bullet with no source row is an evidence gap and is shown as one."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta

from radar import labels as lbl
from radar import matching, ocean_impact, store

DECISIONS = ("INVEST", "DUE DILIGENCE", "ACCELERATOR", "GRANT SUPPORT", "PARTNER INTRODUCTION", "WATCHLIST", "REJECT / LOW FIT")
BANDS = ("Low", "Medium", "High")
TABLE_DIMS = ("impact", "business", "investment", "fit")
UNKNOWN = "unknown"
MAX_ACTIONS = 3
DEADLINE_DAYS = 120
_ACCEL = ("accelerator", "incubator")
# What can satisfy `fallback.requires_any` (names in the thesis file): the evidence behind a High fit that is more than the industry code.
SUPPORT_KEYS = ("declared_member", "own_text", "line_of_business", "corroborated_signal")


def _cfg(thesis: dict) -> dict:
    m = thesis.get("memo") or {}
    d = m.get("decisions") or {}
    # The impact spec carries the thesis itself (`_thesis`) so a caller that reads only `cfg["bands"]["impact"]` and calls `_impact` (the
    # matchmaker's light verdict) gets the same ladder band as memo.build, with no edit of its own (D46).
    bands = {**(m.get("bands") or {}), "impact": {**((m.get("bands") or {}).get("impact") or {}), "_thesis": thesis}}
    return {"labels": m.get("labels") or {}, "bands": bands, "rows": d.get("rows") or [], "rules": d.get("rules") or [],
            "source": d.get("source") or "", "fallback": d.get("fallback") or {}}


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


def decide(bands: dict[str, str], cfg: dict, support=frozenset()) -> tuple[dict | None, list[str]]:
    """Pass 1: the first table row whose four cells all equal the bands. Pass 2: the first condition rule that holds. Pass 3: the
    fallback, when `support` (what the High fit rests on beyond the industry code) passes its gate. A cell that needs a band never
    matches "unknown". Returns ({kind, id, ...row} or None, unknown dimensions)."""
    for r in cfg["rows"]:
        if all(_cell_matches(r.get(d), bands[d]) for d in TABLE_DIMS):
            return {**r, "kind": "row", "text": f"row {r['id']}, " + "/".join(LETTER[bands[d]] for d in TABLE_DIMS)}, []
    for r in cfg["rules"]:
        if all(_cell_matches(v, bands.get(k, UNKNOWN)) for k, v in (r.get("when") or {}).items()):
            return {**r, "kind": "rule", "text": f"rule {r['id']}"}, []
    fb = fallback(bands, cfg, support)
    if fb is not None:
        return fb, []
    return None, [d for d in (*TABLE_DIMS, "technology") if bands.get(d) == UNKNOWN]


def _fallback_match(bands: dict[str, str], cfg: dict) -> dict | None:
    """The fallback rule the bands reach (thesis fit High and the impact level unknown, impact then read as `implied_impact`), before
    the evidence gate. None when the fallback does not reach this company at all."""
    fb = cfg.get("fallback") or {}
    when = fb.get("when") or {}
    level = fb.get("implied_impact", "Medium")
    measured = bands.get("impact", UNKNOWN) == level   # D53: impact on record at the implied level is never weaker than implied

    def ok(k, v):
        return bands.get(k, UNKNOWN) == v or (k == "impact" and measured)

    if not fb.get("rules") or not all(ok(k, v) for k, v in when.items()):
        return None
    implied = dict(bands, impact=level)
    for r in fb["rules"]:
        if all(_cell_matches(v, implied.get(k, UNKNOWN)) for k, v in (r.get("when") or {}).items()):
            if measured:
                return {**r, "kind": "fallback", "implied_impact": None, "measured_impact": level,
                        "text": f"the High-fit rule, impact {level} on record"}
            return {**r, "kind": "fallback", "implied_impact": implied["impact"],
                    "text": f"fallback {r['id']}, impact implied by sector"}
    return None


def _gate_open(cfg: dict, support) -> bool:
    """True when the fallback has no gate, or at least one `requires_any` evidence is in `support`."""
    need = (cfg.get("fallback") or {}).get("requires_any")
    return not need or any(k in support for k in need)


def fallback(bands: dict[str, str], cfg: dict, support=frozenset()) -> dict | None:
    """Pass 3 (the thesis file's `decisions.fallback`): thesis fit High and the impact level unknown. The impact is then read as
    implied by the sector (`implied_impact`, Medium) and the fallback rules apply, first match wins. The gate `requires_any` keeps it
    from firing on a High fit that is only an industry code: at least one of those evidences must be in `support`. None when it does
    not apply."""
    return _fallback_match(bands, cfg) if _gate_open(cfg, support) else None


def fallback_blocked(bands: dict[str, str], cfg: dict, support=frozenset()) -> bool:
    """True when the fallback would have decided this company but its gate is shut (the High fit rests on the industry code alone)."""
    return not _gate_open(cfg, support) and _fallback_match(bands, cfg) is not None


def _latest(ev: list[dict]) -> str | None:
    return max(ev, key=lambda s: s["date"])["source_url"] if ev else None


def _levels(conn, ctx: dict, key: str, cfg: dict) -> dict:
    """{dimension: {level, because, url}} for technology, business, investment: exactly the levels question 02 of the company page
    prints (radar.frameworks.page_levels: rule levels, plus the TRL a BlueInvest profile states). One source of truth, so the
    memo can never say a level the page does not show. The count of investment dimensions with evidence is a secondary line."""
    fw = ctx["fw"]
    out = {}
    for dim, k in (("technology", "trl"), ("business", "brl"), ("investment", "irl")):
        lv = fw[k]
        url = None
        if lv["level"] is not None:
            ev = lv["evidence"] or []
            url = _latest([e for e in ev if e.get("date")]) if any(e.get("date") for e in ev) else \
                next(((e.get("evidence") or {}).get("url") for e in ev if (e.get("evidence") or {}).get("url")), None)
        out[dim] = {"level": lv["level"], "because": lv["because"], "url": url}
    return out


def dimensions_line(fw: dict) -> dict:
    """'N of 10 investment dimensions have public evidence', the secondary investment line, with the first evidence link."""
    dims = [d for d in fw["dimensions"] if d["n"] > 0]
    url = next((e["url"] for d in dims for e in d["evidence"] if e.get("url")), None)
    return {"n": len(dims), "of": len(fw["dimensions"]), "url": url,
            "text": f"{len(dims)} of {len(fw['dimensions'])} investment dimensions have public evidence"}


def _impact(conn, ctx: dict, key: str, spec: dict, oi: dict | None = None) -> dict:
    """The ocean impact cell of the decision table (D46). When the thesis defines the Ocean Impact Assessment (`oi`, radar.ocean_impact),
    the band is the ladder's: Medium or High is the impact band, and a ladder level with no band (1-2, sector implied only: "not yet
    evidenced") or no level at all stays unknown, so the fallback applies; the page's headline, bullets, ocean block, criteria cell and
    Aava then cannot disagree. Without an assessment (a sector that defines no impact areas) the band is the Navigator-style category
    the frameworks rule finds. The declared dataset's own impact score is declared research, never a level, so it never sets this band."""
    if oi is None and spec.get("_thesis") is not None and ocean_impact.settings(spec["_thesis"]):
        oi = ocean_impact.assess(conn, ctx, key, spec["_thesis"])
    if oi is not None:
        if oi.get("band") in BANDS and oi.get("level") is not None:
            url = next((e["url"] for e in oi.get("evidence") or [] if e.get("url")), None)
            area = (oi.get("area") or "").strip()
            return {"band": oi["band"], "url": url,
                    "text": f"evidence readiness is level {oi['level']} of {oi.get('level_max') or 9}" + (f" ({area[:1].lower() + area[1:]})" if area else "")}
        return {"band": UNKNOWN, "text": None, "url": None}
    cat = ctx["fw"]["category"]
    if cat.get("category") and spec.get("category_band"):
        ev = cat.get("evidence") or {}
        url = ev.get("url") or (ctx["c"].get("source_url") if cat.get("industry") else None)
        if url:
            return {"band": spec["category_band"], "text": f"works in the {cat['category']} category (matched on the word {cat['keyword']})", "url": url}
    return {"band": UNKNOWN, "text": None, "url": None}


def medium_code(code, spec: dict) -> bool:
    """True when the industry code belongs to a family in `memo.bands.fit.medium_codes` (a code prefix from the sector file; a dot is
    ignored, so the NACE spelling 36.00 and the stored 36000 are the same family)."""
    c = str(code or "").replace(".", "").strip()
    return bool(c) and any(c.startswith(str(f).replace(".", "").strip()) for f in spec.get("medium_codes") or [] if str(f).strip())


def code_only_fit(reasons, code, spec: dict) -> bool:
    """True when a feed row's thesis fit rests on an industry code in a `medium_codes` family and on nothing more (D22): the source's own
    text and a name word corroborated by a different source family are the evidence that lifts such a code. The registered line of
    business does not: for these families it is the code's own register label, so it says the same thing twice."""
    return "industry_code" in (reasons or []) and medium_code(code, spec) and not {"own_text", "corroborated_keyword"} & set(reasons)


def _fit(conn, ctx: dict, thesis: dict, spec: dict) -> dict:
    """Thesis fit from the same explain() the feed uses. industry_code or own_text = High; line_of_business or corroborated_keyword =
    Medium; only the legal name = Low; no reason = unknown. A declared cohort or portfolio company has at least the configured floor.
    `support` lists what the fit rests on beyond the industry code (SUPPORT_KEYS): the declared membership, the source's own text, a name
    word corroborated by a different source family (the reason store.explain() gives the feed; the rule is not repeated here)."""
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
    # A code in a `medium_codes` family (D22) is a sector match, not a High fit on the code alone: it counts as Medium. A reason of the
    # source's own text still lifts the fit to High; a corroborated name word or the line of business is Medium anyway.
    code_medium = "industry_code" in reasons and medium_code(c.get("industry_code"), spec)
    if any(r in reasons for r in spec.get("high", []) if not (r == "industry_code" and code_medium)):
        b = "High"
    elif code_medium or any(r in reasons for r in spec.get("medium", [])):
        b = "Medium"
    elif fit_mod.matched_keywords(c.get("name"), thesis) and c.get("source_url"):
        b = "Low"
        bullets.append({"text": ex["why"].removeprefix("Weak: "), "url": c["source_url"]})
    else:
        b = UNKNOWN
    support = {"own_text": "own_text" in reasons, "line_of_business": "line_of_business" in reasons, "corroborated_signal": "corroborated_keyword" in reasons}
    if c["group_tag"] in ("cohort", "portfolio") and c.get("source_url"):
        support["declared_member"] = True
        floor = spec.get("declared_member_band")
        if floor and BANDS.index(floor) > (BANDS.index(b) if b in BANDS else -1):
            b = floor
        bullets.append({"text": f"declared {c['group_tag']} company", "url": c["source_url"]})
    return {"band": b, "bullets": bullets, "support": frozenset(k for k, v in support.items() if v)}


def _why_now(ctx: dict, funding: list[dict], today: date) -> dict | None:
    cands = []
    for r in funding:
        d = r.get("deadline")
        if d and r.get("source_url") and today.isoformat() <= d <= (today + timedelta(days=DEADLINE_DAYS)).isoformat():
            cands.append((abs((date.fromisoformat(d) - today).days), f"{r['name']} closes {d}", r["source_url"], d))
    for s in ctx["sigs"]:
        d = s.get("date")
        if d and s.get("source_url") and (today - timedelta(days=180)).isoformat() <= d <= today.isoformat():
            label = s.get("type_label") or lbl.signal_label(s["signal_type"])
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
    src = lambda r: lbl.origin_label(r.get("origin")) if r.get("origin") else ("ecosystem dataset" if r.get("score") is not None else "declared list")  # noqa: E731
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


_LEVEL_TAG = re.compile(r"\s*\(level \d+\)")
_CODE_TAG = re.compile(r"(?i)\bindustry code\s+[\d.]+\s*\(([^)]*?)(?:,\s*PRH)?\)")
_ID_TAG = re.compile(r"\b\d{7}-\d\b|\b\d{5,}\b")
_MORE_TAG = re.compile(r";\s*\d+ more reasons?\.?")
MAX_BULLETS = 5


def words_only(text: str | None) -> str:
    """A memo line as plain words: no level numbers, industry codes or ids (dates and counts stay)."""
    t = _MORE_TAG.sub("", _LEVEL_TAG.sub("", text or ""))
    t = _CODE_TAG.sub(lambda m: f"registered industry ({m.group(1).strip()})", t)
    t = _ID_TAG.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" ;,")
    return t[:1].upper() + t[1:] if t else t


def _lc(t: str) -> str:
    """Lower-case the first letter of a clause unless it starts an acronym or a name (second letter upper-case)."""
    return t[:1].lower() + t[1:] if len(t) > 1 and t[1].islower() else t


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _after_colon(line: str) -> str:
    """'Business readiness Medium (level 6): first public contract' -> 'first public contract'."""
    return line.split("): ", 1)[1] if "): " in line else line.split(": ", 1)[-1]


def plain_bullets(rec: dict, why: list[dict], oi: dict | None, labels: dict) -> list[dict]:
    """Three to five plain-word bullets that explain the verdict, from the memo's why lines and its four bands: no ids, no level
    numbers, no scores. Each is {text, url}; the url is the record the line rests on, or None for a gap."""
    band_of = {b["label"]: str(b["band"]).lower().replace("sector,", "the sector,") for b in rec["because_labels"]}
    by_label = {l: w for l in (labels.get("business", "business"), labels.get("investment", "investment"), labels.get("technology", "technology"))
                for w in why if w["text"].startswith(l + " ") and not w["text"].startswith(l + ", secondary")}
    fit_lines = [w for w in why if w["text"].startswith("Thesis fit:")]
    out: list[tuple[str, dict]] = []

    fit_label = labels.get("fit", "Thesis fit")
    if fit_lines:
        reasons = "; ".join(words_only(w["text"].split(": ", 1)[1]).rstrip(".").lower() if i else words_only(w["text"].split(": ", 1)[1]).rstrip(".")
                            for i, w in enumerate(fit_lines[:2]))
        out.append(("fit", {"text": f"{fit_label} is {band_of.get(fit_label, 'unknown')}: {reasons[:1].lower() + reasons[1:]}.", "url": fit_lines[0].get("url")}))
    impact_label = labels.get("impact", "Ocean impact")
    if oi and oi.get("area"):
        basis = {"own text": "the source's own text", "corroborated name word": "a corroborated name word",
                 "industry code family": "the registered industry code family"}.get(oi["area_basis"], oi["area_basis"])
        url = next((e["url"] for e in oi["evidence"] if e.get("url")), None)
        ready = f"evidence readiness is {oi['band'].lower()}" if oi["band"] else "it is not yet evidenced beyond the sector"
        out.append(("impact", {"text": f"{impact_label} area is {oi['area'][:1].lower() + oi['area'][1:]}, found through {basis}; "
                                       f"{ready} and confidence is {oi['confidence']}.", "url": url}))
    elif oi is not None:
        out.append(("impact", {"text": f"No public record names an {impact_label.lower()} area yet.", "url": None}))
    elif band_of.get(impact_label, "unknown") != "unknown":
        out.append(("impact", {"text": f"{impact_label} is {band_of[impact_label]}.", "url": None}))
    for key in ("business", "investment"):
        label = labels.get(key, key)
        w = by_label.get(label)
        if w and band_of.get(label, "unknown") != "unknown":
            out.append((key, {"text": f"{label} is {band_of[label]}: {_lc(words_only(_after_colon(w['text'])).rstrip('.'))}.", "url": w.get("url")}))
    gaps = [n.lower() for n in rec.get("needs") or [] if oi is None or n.lower() != impact_label.lower()]
    if gaps:
        out.append(("missing", {"text": "No public record yet for " + _and(gaps[:3]) + ".", "url": None}))
    now = next((w for w in why if w["text"].startswith("Why now:")), None)
    if now:
        out.append(("now", {"text": words_only(now["text"]).rstrip(".") + ".", "url": now.get("url")}))
    label = labels.get("technology", "technology")
    w = by_label.get(label)
    if w and band_of.get(label, "unknown") != "unknown":
        out.append(("technology", {"text": f"{label} is {band_of[label]}: {_lc(words_only(_after_colon(w['text'])).rstrip('.'))}.", "url": w.get("url")}))
    return [b for _, b in out[:MAX_BULLETS]]


def build(conn: sqlite3.Connection, thesis: dict, company_key: str, *, today=None) -> dict | None:
    """The memo, or None when the company is not in the database."""
    ctx = matching.company_context(conn, company_key)
    if ctx is None:
        return None
    cfg = _cfg(thesis)
    t = store._today(today)
    c = ctx["c"]
    lv = _levels(conn, ctx, company_key, cfg)
    oi = ocean_impact.assess(conn, ctx, company_key, thesis) if ocean_impact.settings(thesis) else None
    imp = _impact(conn, ctx, company_key, cfg["bands"].get("impact") or {}, oi)
    fit = _fit(conn, ctx, thesis, cfg["bands"].get("fit") or {})
    bands = {"impact": imp["band"], "business": band(lv["business"]["level"], cfg["bands"].get("business")),
             "investment": band(lv["investment"]["level"], cfg["bands"].get("investment")), "fit": fit["band"]}
    tech_band = band(lv["technology"]["level"], cfg["bands"].get("technology"))
    bands["technology"] = tech_band
    nxt = matching.who_comes_next(company_key, thesis, 5, conn=conn, today=t)
    step = matching.next_step(company_key, thesis, conn=conn, today=t)

    blocked = False
    if ctx["status"] in matching.INACTIVE:
        row, unknown, decision = None, [], "WATCHLIST"
    else:
        row, unknown = decide(bands, cfg, fit["support"])
        decision = row["decision"] if row else "WATCHLIST"
        blocked = row is None and fallback_blocked(bands, cfg, fit["support"])
        if blocked:
            unknown = ["impact"]  # the one missing piece: the evidence the fallback would have implied by the sector
    labels = cfg["labels"]
    needed = [d for d in unknown]  # dimensions with no public evidence while no row matched
    shown = dict(bands)
    if row and row.get("kind") == "fallback" and row.get("implied_impact"):
        shown["impact"] = f"{row['implied_impact']}, implied by sector"
    because = " / ".join(f"{shown[d]}" for d in TABLE_DIMS)
    rec = {"decision": decision, "row_id": row["id"] if row else None, "table_action": row.get("action") if row else None,
           "matched": row["text"] if row else None, "team_label": row.get("team") if row else None, "kind": row.get("kind") if row else None,
           "because": because, "because_labels": [{"label": labels.get(d, d), "band": shown[d]} for d in TABLE_DIMS],
           "table_source": cfg["source"], "needs": [labels.get(d, d) for d in needed],
           "dimensions": dimensions_line(ctx["fw"]), "fallback_blocked": blocked}
    if row and row.get("kind") == "fallback" and not row.get("implied_impact"):
        rec["note"] = (f"Ocean impact {str(row['measured_impact']).lower()} on record; thesis fit is High, so the decision table's "
                       f"High-fit rule applies.")
    elif row and row.get("kind") == "fallback":
        rec["note"] = (f"Impact not yet evidenced; thesis fit is High, so impact is read as {row['implied_impact']}, implied by the "
                       f"sector, and fallback {row['id']} of the decision rules applies.")
    if row is None:
        why_blocked = f" ({cfg['fallback'].get('blocked_note') or 'the fallback gate is not met'})" if blocked else ""
        rec["note"] = ("The company has defunct status in the declared dataset." if ctx["status"] in matching.INACTIVE else
                       ("more public evidence needed: " + ", ".join(rec["needs"]) + why_blocked
                        if needed else "no row or rule of the decision table covers " + _and([f"{b['label'].lower()} {str(b['band']).lower()}" for b in rec["because_labels"]])
                        + ", so the company stays on the watchlist"))

    why = []
    for dim, label in (("impact", labels.get("impact", "impact")),):
        if imp["url"]:
            why.append({"text": f"{label} {imp['band']}: {imp['text']}", "url": imp["url"]})
    for dim in ("business", "investment", "technology"):
        v = lv[dim]
        if v["level"] is not None and v["url"]:
            b = bands.get(dim) or tech_band
            why.append({"text": f"{labels.get(dim, dim)} {b} (level {v['level']}): {v['because']}", "url": v["url"]})
    dl = rec["dimensions"]
    if dl["n"] and dl["url"]:
        why.append({"text": f"{labels.get('investment', 'investment')}, secondary: {dl['text']}", "url": dl["url"]})
    why += [{"text": f"Thesis fit: {b['text']}", "url": b["url"]} for b in fit["bullets"] if b.get("url")]
    wn = _why_now(ctx, nxt["funding"], t)
    if wn:
        why.append({"text": f"Why now: {wn['text']}", "url": wn["url"]})

    risks = []
    for d in TABLE_DIMS:
        if bands[d] == UNKNOWN:
            implied = " (read as implied by the sector for this decision)" if d == "impact" and rec.get("kind") == "fallback" else ""
            if d == "impact" and oi is not None:  # the ladder is the source of the impact band: say what it holds (D46)
                url = next((e["url"] for e in oi.get("evidence") or [] if e.get("url")), None)
                risks.append({"text": (f"{labels.get(d, d)} is not yet evidenced beyond the sector (level {oi['level']} of {oi['level_max']}){implied}"
                                       if oi.get("level") is not None else f"No public record names an {labels.get(d, d).lower()} area yet{implied}"), "url": url})
            else:
                risks.append({"text": f"No public evidence for {labels.get(d, d).lower()}{implied}", "url": None})
        elif bands[d] == "Low":
            src = {"business": lv["business"], "investment": lv["investment"]}.get(d) or (imp if d == "impact" else None)
            risks.append({"text": f"{labels.get(d, d)} is Low on the stored evidence", "url": (src or {}).get("url") or c.get("source_url")})
    for dim in ctx["fw"]["dimensions"]:
        if dim["name"] in ("Market", "Financials") and not dim["evidence"]:
            risks.append({"text": f"No public {dim['name'].lower()} evidence ({dim['note']})", "url": None})
    if tech_band == UNKNOWN:
        risks.append({"text": f"No public evidence for {labels.get('technology', 'technology').lower()}", "url": None})

    out = {"company_key": company_key, "name": c["name"], "recommendation": rec, "why": why, "risks": risks,
           "actions": _actions(decision, nxt, step, unknown, labels, c, ctx["sigs"]),
           "levels": {**{d: {"band": bands[d]} for d in TABLE_DIMS}, "technology": {"band": tech_band}}, "as_of": t.isoformat(),
           "plain_why": plain_bullets(rec, why, oi, labels)}
    if oi is not None:  # a thesis that defines no impact areas (the health swap) has no assessment and no such key
        out["ocean_impact"] = oi
    return out


def rule_label(rec: dict) -> str:
    """Which entry of the decision table decided, in words: 'decision table row 7', 'rule c2: impact implied by the sector' (fallback),
    'decision table condition rule e', or that none matched."""
    kind, matched = rec.get("kind"), rec.get("matched") or ""
    if kind == "row":
        return matched.replace("row ", "decision table row ", 1)
    if kind == "rule":
        return matched.replace("rule ", "decision table condition rule ", 1)
    if kind == "fallback":
        return matched.replace("fallback ", "rule ", 1).replace(", impact implied by sector", ": impact implied by the sector")
    return "no row or rule of the decision table matched"


def table_lines(thesis: dict) -> list[str]:
    """The whole decision table as plain lines for the page: the rows, the condition rules and the fallback text, all from the thesis file."""
    cfg = _cfg(thesis)
    lb = cfg["labels"]
    out = []
    for r in cfg["rows"]:
        cells = ", ".join(f"{lb.get(d, d).lower()} {r.get(d)}" for d in TABLE_DIMS)
        out.append(f"Row {r['id']}: {cells} gives {r['decision'].lower()}.")
    out += [f"Condition rule {r['id']}: {str(r.get('action') or '').rstrip('.')} gives {r['decision'].lower()}." for r in cfg["rules"]]
    text = ((thesis.get("memo") or {}).get("decisions") or {}).get("fallback_text")
    if text:
        out.append(text)
    return out


def next_step_view(m: dict | None, step: dict | None, thesis: dict | None = None) -> dict | None:
    """Question 04 as the verdict says it (D46). The older next-step rules (matching.next_step) are a list of concrete leads: an open
    programme, a buyer's contract, a readiness gap, a check-in. They never state a verdict, so the verdict sentence comes from the memo's
    decision table, and a concrete lead (rules 1 to 4) is added beside it. Rule 5 of the old list ("watch; not enough public evidence")
    says nothing the verdict does not say better and is not shown. {sentence, because, source_url, rule, decision, table, concrete}."""
    if not m or not m.get("recommendation"):
        return None
    rec = m["recommendation"]
    cfg = _cfg(thesis) if thesis else {"rows": [], "labels": {}}
    action = rec.get("table_action") if rec.get("kind") in ("row", "fallback") else None
    if not action:  # a condition rule or no match: the table's own action for this verdict
        action = next((r.get("action") for r in cfg["rows"] if r.get("decision") == rec["decision"] and r.get("action")), None)
    word = rec["decision"][:1] + rec["decision"][1:].lower()
    sentence = f"{word}: {action[:1].lower() + action[1:]}" if action else word
    cells = ", ".join(f"{x['label'].lower()} {str(x['band']).lower()}" for x in rec.get("because_labels") or [])
    note = rec.get("note") or ""
    because = (note[:1].upper() + note[1:]) if rec.get("kind") is None and note else f"{rule_label(rec)}: {cells}"
    url = next((w["url"] for w in m.get("why") or [] if w.get("url")), None)
    concrete = None
    if step and step.get("rule") in (1, 2, 3, 4) and step.get("sentence"):
        concrete = {"sentence": step["sentence"], "because": step.get("because"), "source_url": step.get("source_url")}
    return {"sentence": sentence.rstrip(".") + ".", "because": because, "source_url": url, "rule": rule_label(rec), "decision": rec["decision"], "concrete": concrete,
            "table": table_lines(thesis) if thesis else []}


def for_template(company_key: str, thesis: dict) -> dict | None:
    """Template hook: the memo from its own read-only connection, so the company route needs no edit."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        return build(conn, thesis, company_key)
    finally:
        conn.close()

