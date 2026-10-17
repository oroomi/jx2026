"""The home list's filter rail: which facets exist, how a querystring selects them, which cached rows pass, and the counts beside
each option. Pure functions over the rows radar.home_list builds (each row carries `facets`, computed once per cache warm), so a
filtered page never opens the database. A selection lives in the URL (`/?verdict=ACCELERATOR&trl=4-6`), so every view is shareable.

Rules:
  - Several values of one facet are alternatives (OR); different facets all have to hold (AND).
  - The number beside an option is how many rows of the current group would show if that option were switched on while every OTHER
    facet keeps its selection, so a click never leads to a surprise empty list unless the count said 0.
  - An option is offered only for values that exist in the current group's rows (plus anything already selected).
  - "none" is the value for "no public record": it is a real option, never hidden, because a missing level is information.
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlencode

from radar import labels as lbl

NONE = "none"
MAX_VALUES = 20
MAX_LEN = 60

# (param, heading, section, open by default). Order = the order of the rail. "criteria" = what the judges score.
FACETS = (
    ("verdict", "Verdict", "criteria", True),
    ("impact", "Ocean impact", "criteria", True),
    ("trl", "Technology readiness (TRL)", "criteria", True),
    ("brl", "Business readiness (BRL)", "criteria", True),
    ("irl", "Investment readiness (IRL)", "criteria", True),
    ("fit", "Thesis fit", "criteria", True),
    ("country", "Country", "more", True),
    ("sector", "Sector", "more", False),
    ("age", "Registered", "more", False),
    ("src", "Source records", "more", False),
    ("deadline", "Programme deadline", "more", False),
    ("member", "Declared company", "more", False),
)
PARAMS = tuple(f[0] for f in FACETS)
KEEP = ("group", "thesis")          # querystring keys that are not filters but must survive a click

_BANDS = ("High", "Medium", "Low")
_AGE = (("lt1", "Under 1 year"), ("1-3", "1 to 3 years"), ("3-5", "3 to 5 years"), ("gt5", "Over 5 years"))
_MEMBER = (("cohort", "Declared cohort company"), ("portfolio", "Declared portfolio company"))
_NONE_LABEL = {"verdict": "No verdict", "impact": "No public record", "trl": "No public record", "brl": "No public record",
               "irl": "No public record", "fit": "No public record", "country": "Not stated", "sector": "No category on record",
               "age": "Not on record"}


def parse(params) -> dict[str, list[str]]:
    """The selection in a querystring: {facet: [values]} for the facets named here, nothing else. Values are capped in number and length;
    an unknown value simply matches no row."""
    getlist = getattr(params, "getlist", None)
    out: dict[str, list[str]] = {}
    for p in PARAMS:
        vals = getlist(p) if getlist else ([params[p]] if p in params else [])
        vals = list(dict.fromkeys(v.strip() for v in vals if v and v.strip() and len(v) <= MAX_LEN))[:MAX_VALUES]
        if vals:
            out[p] = vals
    return out


def passes(row: dict, sel: dict[str, list[str]], skip: str | None = None) -> bool:
    """True when the row satisfies every selected facet (except `skip`): at least one of its values is among the selected ones."""
    facets = row.get("facets") or {}
    return all(set(facets.get(p) or ()) & set(vs) for p, vs in sel.items() if p != skip)


def apply(rows: list[dict], sel: dict[str, list[str]]) -> list[dict]:
    return [r for r in rows if passes(r, sel)] if sel else list(rows)


PARTIAL = "/home/list"   # the lean twin of "/" that htmx asks for (radar/routes/home_rail.py); the address bar always shows "/"


def href(sel: dict[str, list[str]], extra: dict[str, str], toggle: tuple[str, str] | None = None, path: str = "/") -> str:
    """The URL of a view: the selection (with one value switched on or off), plus the group and thesis the visitor is in."""
    new = {p: list(vs) for p, vs in sel.items()}
    if toggle:
        p, v = toggle
        cur = new.get(p, [])
        new[p] = [x for x in cur if x != v] if v in cur else [*cur, v]
    pairs = [(k, v) for k, v in extra.items() if v] + [(p, v) for p in PARAMS for v in new.get(p, [])]
    return f"{path}?{urlencode(pairs)}" if pairs else path


def _label(param: str, value: str) -> str:
    if value == NONE:
        return _NONE_LABEL.get(param, "None")
    if param == "verdict":
        return value.capitalize()
    if param in ("trl", "brl"):
        return value.replace("-", " to ")
    if param == "irl":
        return "On record"
    if param == "country":
        from radar.home_list import COUNTRY_NAMES
        return COUNTRY_NAMES.get(value, value)
    if param == "age":
        return dict(_AGE).get(value, value)
    if param == "src":
        return lbl.SOURCE_LABELS.get(value) or lbl.source_label(value)
    if param == "deadline":
        return f"Within {value} days"
    if param == "member":
        return dict(_MEMBER).get(value, value)
    return value


def _order(param: str, present: Counter) -> list[str]:
    """Option order: fixed scales first (strongest first, 'none' last); open lists by count, then name."""
    vals = list(present)
    if param == "verdict":
        from radar.home_list import VERDICT_ORDER
        rank = {v: i for i, v in enumerate((*VERDICT_ORDER, "REJECT / LOW FIT"))}
        return sorted(vals, key=lambda v: (v == NONE, rank.get(v, 99), v))
    if param in ("impact", "fit"):
        return sorted(vals, key=lambda v: (_BANDS.index(v) if v in _BANDS else 9, v))
    if param in ("trl", "brl"):
        return sorted(vals, key=lambda v: (v == NONE, -int(v.split("-")[0]) if v[:1].isdigit() else 0, v))
    if param == "irl":
        return sorted(vals, key=lambda v: v == NONE)
    if param == "age":
        order = [k for k, _ in _AGE] + [NONE]
        return sorted(vals, key=lambda v: order.index(v) if v in order else 99)
    if param == "member":
        order = [k for k, _ in _MEMBER]
        return sorted(vals, key=lambda v: order.index(v) if v in order else 99)
    return sorted(vals, key=lambda v: (v == NONE, -present[v], _label(param, v).casefold()))


def rail(rows: list[dict], sel: dict[str, list[str]], extra: dict[str, str]) -> dict:
    """Everything the rail prints for one group's (unfiltered) rows and the current selection."""
    shown = apply(rows, sel)
    facets = []
    for param, heading, section, is_open in FACETS:
        present: Counter = Counter()      # values in the group's rows, whatever the other facets say
        count: Counter = Counter()        # rows that would show with this value on and the other facets as selected
        for r in rows:
            vals = (r.get("facets") or {}).get(param) or []
            ok = passes(r, sel, skip=param)
            for v in vals:
                present[v] += 1
                if ok:
                    count[v] += 1
        for v in sel.get(param, []):
            present.setdefault(v, 0)
        options = [{"value": v, "label": _label(param, v), "count": count[v], "on": v in sel.get(param, []),
                    "href": href(sel, extra, (param, v)), "hx": href(sel, extra, (param, v), PARTIAL), "id": f"f-{param}-{re.sub('[^a-z0-9]+', '-', v.lower()).strip('-')}"}
                   for v in _order(param, present)]
        if not options:
            continue
        facets.append({"param": param, "heading": heading, "section": section, "options": options,
                       "active": len(sel.get(param, [])), "open": is_open or bool(sel.get(param))})
    return {"facets": facets, "shown": len(shown), "of": len(rows), "n_active": sum(len(v) for v in sel.values()),
            "clear_href": href({}, extra), "clear_hx": href({}, extra, None, PARTIAL), "selection": sel}


def view(H: dict, params) -> dict:
    """The cached home list for this request: every group's rows filtered by the querystring, plus `rail` for the group in view.
    The cached dict is never modified; with no filter the rows are the cached ones."""
    sel = parse(params)
    extra = {"group": params.get("group") if params.get("group") not in (None, "", "all") else "", "thesis": params.get("thesis") or ""}
    groups, countries = H.get("groups") or [], H.get("countries") or []
    gkey = params.get("group") or "all"
    cur = next((g for g in groups + countries if g[0] == gkey), None) or (groups[0] if groups else None)
    out = dict(H)
    out["groups"] = [(k, label, apply(rs, sel)) for k, label, rs in groups]
    out["countries"] = [(k, label, apply(rs, sel)) for k, label, rs in countries]
    out["rail"] = rail(cur[2], sel, extra) if cur else None
    return out
