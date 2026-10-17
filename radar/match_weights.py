"""Weigh the reasons (PROJECT_RULES D90): the Match page's weight simulator for a startup's counterparts.

The owner's brief names seven factors with weights. Six of them map onto a reason the matchmaker already checks; ticket size has no reason
because a startup's funding ask is not in public records (matchmaker.LIMITS), so it is drawn as a disabled slot and never counted. In the
browser the counterparts are ordered by the sum of the visitor's weights over the reasons that hold, ties kept in the server's order. With
the thesis file's weights that is exactly the server's order (matchmaker._sort_key ranks by the same sum first). No total is ever shown:
the weights change the order, and each row shows which reasons hold. Pure functions; no web code."""
from __future__ import annotations

import re

from radar import matchmaker, matchtext

# The owner's seven factors, in the brief's order. `engine` is the matchmaker component behind each; None = nothing in public records.
FACTORS = (
    {"key": "sector", "label": "Sector and thesis", "engine": "sector",
     "gloss": "the same in both records"},
    {"key": "readiness", "label": "Stage", "engine": "readiness",
     "gloss": "the stage, TRL or age it states fits"},
    {"key": "geography", "label": "Geography", "engine": "geography",
     "gloss": "the place it declares covers the startup"},
    {"key": "ticket", "label": "Ticket size", "engine": None,
     "gloss": "Not in public records: a startup's funding ask is not published (connector slot)"},
    {"key": "lookalike", "label": "Portfolio similarity", "engine": "lookalike",
     "gloss": "same industry group in its portfolio"},
    {"key": "timing", "label": "Recent activity", "engine": "timing",
     "gloss": "an open deadline within {days} days"},
    {"key": "keywords", "label": "Strategic fit", "engine": "keywords",
     "gloss": "in its declared focus and the startup's text"},
)
# The brief's weights (the "Investor Matching Metrics Table"). Ticket size's 15 cannot be counted, so the other six are rescaled.
BRIEF = {"sector": 25, "readiness": 20, "geography": 15, "ticket": 15, "lookalike": 10, "timing": 5, "keywords": 10}
SLIDER_MAX = 50
STATES = {"thesis": "The thesis file's weights", "brief": "The brief's weights", "custom": "Your weights"}
_PAIR = re.compile(r"^([a-z]+)-(\d{1,3})$")


def scorable(weights: dict) -> list[str]:
    """The factor keys the engine can score under this thesis, in the brief's order."""
    return [f["key"] for f in FACTORS if f["engine"] and f["engine"] in (weights or {})]


def thesis_values(weights: dict) -> dict[str, int]:
    """The thesis file's weights on the slider scale: multiplied by a whole number so the shares, the ties and the order are unchanged."""
    keys = scorable(weights)
    top = max([int(weights[k]) for k in keys] or [1]) or 1
    k = max(1, (SLIDER_MAX // 2) // top)
    return {key: int(weights[key]) * k for key in keys}


def brief_values(weights: dict) -> dict[str, int]:
    return {key: BRIEF[key] for key in scorable(weights)}


def slider_max(weights: dict) -> int:
    return max([SLIDER_MAX, *thesis_values(weights).values(), *brief_values(weights).values()])


def parse_w(raw: str | None, weights: dict) -> dict[str, int] | None:
    """The `w` query value, e.g. "sector-25,readiness-20,geography-15,lookalike-10,timing-5,keywords-10", as slider values.
    Unknown factors and malformed pairs are ignored; a factor the link leaves out keeps the thesis file's value; values are clamped to the
    slider. None when nothing usable is given (the page then starts from the thesis file's weights)."""
    if not raw:
        return None
    keys, top = scorable(weights), slider_max(weights)
    got: dict[str, int] = {}
    for part in str(raw)[:400].split(","):
        m = _PAIR.match(part.strip().lower())
        if m and m.group(1) in keys:
            got[m.group(1)] = min(int(m.group(2)), top)
    if not got:
        return None
    return {**thesis_values(weights), **got}


def format_w(values: dict[str, int], weights: dict) -> str:
    """The inverse of parse_w, in the brief's order (what the page writes into the URL)."""
    return ",".join(f"{k}-{int(values[k])}" for k in scorable(weights) if k in values)


def shares(values: dict[str, int]) -> dict[str, int]:
    """Each factor's share of the weight in whole percent (the sliders' labels). All zero when every weight is zero."""
    total = sum(values.values())
    return {k: (round(100 * v / total) if total else 0) for k, v in values.items()}


def order(rows: list[dict], values: dict[str, int]) -> list[str]:
    """The browser's ranking rule, kept here so it is tested in Python too: the sum of the weights over the reasons that hold
    (no record counts 0), ties in the server's order. `rows` are in the server's order, each with `id` and `met` (list of factor keys)."""
    if not sum(values.values()):
        return [r["id"] for r in rows]
    return [r["id"] for _, r in sorted(enumerate(rows), key=lambda p: (-sum(values.get(k, 0) for k in p[1]["met"]), p[0]))]


def _row(r: dict, eng_to_key: dict) -> dict:
    met, none, no = [], [], []
    for c in r.get("components") or []:
        key = eng_to_key.get(c.get("id"))
        if key is None:
            continue
        (met if c.get("met") else none if c.get("met") is None else no).append(key)
    return {"id": r["id"], "name": r["name"], "kind": r.get("kind_label") or "", "met": met, "none": none, "no": no}


def panel(result: dict | None, thesis: dict, raw_w: str | None = None, *, conn=None) -> dict | None:
    """Everything the panel template needs, or None (no panel): the factors with their slider values, the two presets, and every listed
    counterpart (not only the shown ones) with the reasons that hold, so a new order can bring a counterpart from below the cut."""
    if not result or not result.get("counterparts"):
        return None
    cfg = matchtext.config(thesis)
    weights = (cfg or {}).get("weights") or result.get("weights") or {}
    keys = scorable(weights)
    if not keys:
        return None
    eng_to_key = {f["engine"]: f["key"] for f in FACTORS if f["engine"] in weights}
    rows = [_row(r, eng_to_key) for r in result["counterparts"]]
    listed = int(result.get("listed") or len(rows))
    if listed > len(rows):
        key = (result.get("company") or {}).get("key")
        full = matchmaker.match_company(key, thesis, conn=conn, limit=max(listed, 1)) if key else None
        if full and [r["id"] for r in full["counterparts"][:len(rows)]] == [r["id"] for r in rows]:
            rows = [_row(r, eng_to_key) for r in full["counterparts"]]
        # otherwise the two calls disagree (a day rolled over between them): keep the shown rows only, never a mixed order
    base = thesis_values(weights)
    brief = brief_values(weights)
    start = parse_w(raw_w, weights) or dict(base)
    preset = "thesis" if start == base else "brief" if start == brief else "custom"
    days = int((cfg or {}).get("deadline_days", 90))
    factors = []
    for f in FACTORS:
        on = f["key"] in keys
        engine = matchmaker.LABELS.get(f["engine"]) if f["engine"] else None
        factors.append({"key": f["key"], "label": f["label"], "on": on, "engine": engine, "gloss": f["gloss"].format(days=days),
                        "value": start.get(f["key"], 0), "brief": BRIEF.get(f["key"])})
    shown = len(result["counterparts"])
    company = (result.get("company") or {}).get("key")
    data = {"keys": keys, "labels": {f["key"]: f["label"] for f in FACTORS}, "presets": {"thesis": base, "brief": brief},
            "states": STATES, "shown": shown, "company": company, "rows": rows}
    return {"factors": factors, "factor_keys": keys, "max": slider_max(weights), "start": start, "shares": shares(start), "preset": preset,
            "state": STATES[preset], "presets": {"thesis": base, "brief": brief}, "shown": shown, "listed": listed, "rows": rows,
            "company": company, "data": data}
