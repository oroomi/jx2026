"""The home list's filters: ONE state, parsed once from the URL, and what follows from it. Pure functions over the rows radar.home_list builds
(each row carries `facets`, computed once per cache warm), so a filtered page never opens the database.

The state is the URL query: the filters (verdict, impact, trl, brl, irl, fit, country, sector, age, source, deadline, member; the list
is config/home_filters.yaml), the group tab (`group`) and, for the Top matching tab, the investor (`for`). `/?verdict=ACCELERATOR&trl=4-6` and
`/home/list?verdict=ACCELERATOR&trl=4-6` are the same state: the first renders the whole page, the second only the list section that htmx
swaps in place (radar/routes/home_rail.py). Every control is a link that carries the NEXT state, so a click, a refresh and a shared URL all
land on the same view, with or without scripts. radar/static/filters.js mirrors the same parameters in the browser.

`subsector` (D42) is the sector taxonomy's sub-sectors: a multi-select listed inside the Sector group, under the sector in view (config/home_filters.yaml
`parent: thesis`). A row carries the slugs in `facets["subsector"]` and the words in `subsectors`; a sector with no taxonomy, or a store not yet backfilled,
carries none, so the group has no sub-sector list and the facet hides.

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
from dataclasses import dataclass, field
from urllib.parse import urlencode

from radar import home_config, labels as lbl

NONE = "none"
UNCLASSIFIED = "not_classified"        # the sub-sector slug of a company with no link (radar/sectors.py)
MAX_VALUES = 20
MAX_LEN = 60
PARTIAL = "/home/list"                 # the list section alone (radar/routes/home_rail.py); the address bar always shows "/"
ALIAS = {"src": "source"}              # a parameter's old name, still read so an old shared link keeps working
KEEP = ("group", "for", "thesis")      # querystring keys that are not filters but must survive a click

_BANDS = ("High", "Medium", "Low")
_AGE = (("lt1", "Under 1 year"), ("1-3", "1 to 3 years"), ("3-5", "3 to 5 years"), ("gt5", "Over 5 years"))
_MEMBER = (("cohort", "Declared cohort company"), ("portfolio", "Declared portfolio company"))
_NONE_LABEL = {"verdict": "No verdict", "impact": "No public record", "trl": "No public record", "brl": "No public record",
               "irl": "No public record", "fit": "No public record", "country": "Not stated", "sector": "No category on record",
               "age": "Not on record"}


def facet_list() -> tuple[tuple, ...]:
    """(param, heading, section, open by default, source) in rail order, read from config/home_filters.yaml."""
    return home_config.facets()


def params() -> tuple[str, ...]:
    """The filter parameters (a facet with a `source` is a pseudo-group such as the sector list, not a row filter)."""
    return tuple(f[0] for f in facet_list() if not f[4])


def _slug(v: str) -> str:
    return re.sub("[^a-z0-9]+", "-", v.lower()).strip("-")


# ---- the state ----------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class State:
    """Everything the URL says about the list: the selection, the group tab, the investor of the Top matching tab, the sector asked for."""
    sel: dict = field(default_factory=dict)
    group: str = ""      # "" = the first tab
    org: str = ""        # the `for` parameter as written ("" = not written)
    thesis: str = ""     # the `thesis` parameter as written ("" = not written)

    def extra(self) -> dict[str, str]:
        return {"group": self.group, "for": self.org, "thesis": self.thesis}

    @property
    def url(self) -> str:
        return href(self.sel, self.extra())

    @property
    def partial(self) -> str:
        return href(self.sel, self.extra(), None, PARTIAL)


def _values(params_, name: str) -> list[str]:
    getlist = getattr(params_, "getlist", None)
    return list(getlist(name)) if getlist else ([params_[name]] if name in params_ else [])


def parse(params_) -> dict[str, list[str]]:
    """The selection in a querystring: {facet: [values]} for the facets named here, nothing else. Values are capped in number and length;
    an unknown value simply matches no row. A parameter's old name is read too (`src` for `source`)."""
    out: dict[str, list[str]] = {}
    for p in params():
        vals = _values(params_, p) + [v for old, new in ALIAS.items() if new == p for v in _values(params_, old)]
        vals = [v.strip() for v in vals if v and v.strip() and len(v) <= MAX_LEN]
        if p == "country":
            vals = [v if v.lower() == NONE else v.upper() for v in vals]
        vals = list(dict.fromkeys(vals))[:MAX_VALUES]
        if vals:
            out[p] = vals
    return out


def _one(params_, name: str) -> str:
    v = (params_.get(name) or "").strip()
    return v if len(v) <= MAX_LEN else ""


def parse_state(params_) -> State:
    """The whole state of a request, parsed once. An old country link (`group=cc-FI`) becomes the country filter."""
    sel = parse(params_)
    group = _one(params_, "group")
    if group.startswith("cc-") and "country" in params():
        code = group[3:].upper()
        if code and code not in sel.get("country", []):
            sel["country"] = [*sel.get("country", []), code][:MAX_VALUES]
        group = ""
    return State(sel, "" if group == "all" else group, _one(params_, "for"), _one(params_, "thesis"))


def passes(row: dict, sel: dict[str, list[str]], skip: str | None = None) -> bool:
    """True when the row satisfies every selected facet (except `skip`): at least one of its values is among the selected ones."""
    facets = row.get("facets") or {}
    return all(set(facets.get(p) or ()) & set(vs) for p, vs in sel.items() if p != skip)


def apply(rows: list[dict], sel: dict[str, list[str]]) -> list[dict]:
    return [r for r in rows if passes(r, sel)] if sel else list(rows)


def href(sel: dict[str, list[str]], extra: dict[str, str], toggle: tuple[str, str] | None = None, path: str = "/") -> str:
    """The URL of a view: the selection (with one value switched on or off), plus the group, investor and sector the visitor is in."""
    new = {p: list(vs) for p, vs in sel.items()}
    if toggle:
        p, v = toggle
        cur = new.get(p, [])
        new[p] = [x for x in cur if x != v] if v in cur else [*cur, v]
    pairs = [(k, v) for k, v in extra.items() if v and not (k == "group" and v == "all")] + [(p, v) for p in params() for v in new.get(p, [])]
    return f"{path}?{urlencode(pairs)}" if pairs else path


# ---- labels and order ---------------------------------------------------------------------------------------------------------------

def sub_labels(rows: list[dict] | None) -> dict[str, str]:
    """{sub-sector slug: label} from the rows' `subsectors` (the words the store's taxonomy gave them): what the sub-sector options and chips print."""
    out: dict[str, str] = {}
    for r in rows or []:
        for x in r.get("subsectors") or []:
            out.setdefault(x["slug"], x["label"])
    return out


def _label(param: str, value: str, labels: dict[str, str] | None = None) -> str:
    if param == "subsector":
        return (labels or {}).get(value) or lbl.plain(value).capitalize()
    if value == NONE:
        return _NONE_LABEL.get(param, "None")
    if param == "verdict":
        return value.capitalize()
    if param in ("trl", "brl"):
        return value.replace("-", " to ")
    if param == "irl":
        return "On record"
    if param == "country":
        return home_config.country_name(value)
    if param == "age":
        return dict(_AGE).get(value, value)
    if param == "source":
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
    if param == "subsector":
        return sorted(vals, key=lambda v: (v == UNCLASSIFIED, -present[v], v))      # "Not yet classified" last, the rest by how many startups
    return sorted(vals, key=lambda v: (v == NONE, -present[v], _label(param, v).casefold()))


# ---- the sector (thesis) group -------------------------------------------------------------------------------------------------------

def short_title(title: str) -> str:
    """A thesis title without its trailing bracket ('Blue economy, Finland and Nordics (Redstone Blue x A'Pelago)' reads 'Blue economy, Finland
    and Nordics'): what the sector chip and the Sector group print."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title or "").strip() or (title or "")


def offered(rows: list[dict] | None) -> dict[str, set[str]] | None:
    """{param: the values some row carries} for a list's rows: what a sector offers. None when its rows are not known yet."""
    if rows is None:
        return None
    out: dict[str, set[str]] = {}
    for r in rows:
        for p, vals in (r.get("facets") or {}).items():
            out.setdefault(p, set()).update(vals or ())
    return out


def _carried(st: State, sector: dict) -> tuple[dict[str, list[str]], str]:
    """The selection and group that survive a switch to `sector`: only what that sector's rows offer. When its rows are not known yet
    nothing is carried (a reset is the safe answer: a filter it does not offer would only show an empty list)."""
    have = sector.get("offered")
    if have is None:
        return {}, ""
    keep = {p: [v for v in vs if v in have.get(p, ())] for p, vs in st.sel.items()}
    groups = sector.get("groups") or ()
    return {p: vs for p, vs in keep.items() if vs}, (st.group if st.group in groups else "")


def sector_options(st: State, sectors: list[dict], current: str) -> list[dict]:
    """The Sector group's options, one per configured thesis. Choosing one asks for that thesis' list with the filters it also offers (the
    others are reset); the investor of the Top matching tab is reset to that sector's default."""
    out = []
    for s in sectors:
        sel, group = _carried(st, s) if s["id"] != current else (st.sel, st.group)
        extra = {"group": group, "for": st.org if s["id"] == current else "", "thesis": s["id"]}
        out.append({"value": s["id"], "label": short_title(s["title"]), "count": s.get("rows"), "on": s["id"] == current,
                    "href": href(sel, extra), "hx": href(sel, extra, None, PARTIAL), "id": f"f-thesis-{_slug(s['id'])}"})
    return out


# ---- what the page prints -----------------------------------------------------------------------------------------------------------

def rail(rows: list[dict], sel: dict[str, list[str]], extra: dict[str, str], sector_opts: list[dict] | None = None) -> dict:
    """Everything the rail prints for one group's (unfiltered) rows and the current selection. `sector_opts` (sector_options) fills the
    Sector group; it takes one choice, so it is neither a filter nor counted among the active ones, but a facet nested in it (the sub-sectors,
    `parent: thesis`) is listed inside the group and its selected values are counted on the group."""
    shown = apply(rows, sel)
    facets = []
    parents = home_config.parents()
    names = sub_labels(rows)
    nested: list[tuple[int, dict]] = []
    for param, heading, section, is_open, source in facet_list():
        if source:
            if source == "theses" and sector_opts and len(sector_opts) > 1:
                facets.append({"param": param, "heading": heading, "section": section, "options": sector_opts, "active": 0, "open": is_open, "single": True})
            continue
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
        options = [{"value": v, "label": _label(param, v, names), "count": count[v], "on": v in sel.get(param, []),
                    "href": href(sel, extra, (param, v)), "hx": href(sel, extra, (param, v), PARTIAL), "id": f"f-{param}-{_slug(v)}",
                    "flag": home_config.flag_url(v) if param == "country" and v != NONE else None}
                   for v in _order(param, present)]
        if not options:
            continue
        facet = {"param": param, "heading": heading, "section": section, "options": options,
                 "active": len(sel.get(param, [])), "open": is_open or bool(sel.get(param))}
        if param in parents:
            nested.append((len(facets), facet))
        else:
            facets.append(facet)
    for at, kid in nested:
        host = next((f for f in facets if f["param"] == parents[kid["param"]]), None)
        if host is None:                    # the parent group is not on the rail (a lone sector): the facet stands on its own
            facets.insert(min(at, len(facets)), kid)
            continue
        host.setdefault("nested", []).append({**kid, "sector": next((o["label"] for o in host["options"] if o["on"]), "")})
        host["active"] += kid["active"]
        host["open"] = host["open"] or kid["active"] > 0
    return {"facets": facets, "shown": len(shown), "of": len(rows), "n_active": sum(len(v) for v in sel.values()),
            "clear_href": href({}, extra), "clear_hx": href({}, extra, None, PARTIAL), "selection": sel,
            "sections": home_config.sections()}


def chips(sel: dict[str, list[str]], extra: dict[str, str], names: dict[str, str] | None = None) -> list[dict]:
    """One removable chip per selected value: its words, and the URL of the view without it."""
    heading = {f[0]: f[1] for f in facet_list()}
    return [{"param": p, "value": v, "heading": heading.get(p, p), "label": _label(p, v, names), "id": f"chip-{p}-{_slug(v)}",
             "flag": home_config.flag_url(v) if p == "country" and v != NONE else None,
             "href": href(sel, extra, (p, v)), "hx": href(sel, extra, (p, v), PARTIAL)}
            for p in params() for v in sel.get(p, [])]


def top_matching(H: dict, groups: list[tuple], match: dict | None) -> list[tuple]:
    """The groups with the Top matching tab (`fit`) made for the organisation in view. Its rows are the matchmaker's ranking for that
    organisation (radar.home_orgs), all of them, in its order and with its reasons in `why` (D70). A startup that is also on the home
    list keeps that row's facts, so the rail's filters narrow the ranking to the startups that carry them; the others have no facts for
    the rail and drop out only when a filter is chosen. Without an organisation or a ranking the tab is the plain list under its plain label."""
    rank = (match or {}).get("rank")
    if not match or not match.get("org") or rank is None:
        return groups
    by_key = {r["company_key"]: r for r in H.get("rows") or []}
    rows = [{**(by_key.get(m["key"]) or {"facets": {}}), "company_key": m["key"], "name": m["name"], "why": m["why"], "match": m} for m in rank["rows"]]
    entry = ("fit", home_config.group_label_for("fit", match["name"]), rows)
    at = next((i for i, g in enumerate(groups) if g[0] == "fit"), None)
    return [*groups[:at], entry, *groups[at + 1:]] if at is not None else [*groups[:1], entry, *groups[1:]]


ANY_VALUE = "any"      # the `for` value of "no organisation" (radar.home_orgs.ANY)


def _hidden(st: State) -> list[tuple[str, str]]:
    """The state the investor picker's form carries besides its own choice, so a change of investor keeps the tab, the sector and the filters."""
    pairs = [("group", st.group or "fit")]
    if st.thesis:
        pairs.append(("thesis", st.thesis))
    return pairs + [(p, v) for p in params() for v in st.sel.get(p, [])]


def view(H: dict, params_, *, sectors: list[dict] | None = None, current: str = "", title: str = "", match: dict | None = None) -> dict:
    """The cached home list for this request: every group's rows filtered by the state, plus what the list section prints for the group in
    view (`cur`, `rail`, `chips`, `count`). `sectors` are the configured theses ({id, title, rows, offered, groups}), `current` the one in
    view, `match` the Top matching context (radar.home_orgs.context). The cached dict is never modified; with no filter the rows are the
    cached ones."""
    st = params_ if isinstance(params_, State) else parse_state(params_)
    sel, extra = st.sel, st.extra()
    base = H.get("groups") or []
    groups = top_matching(H, [(k, home_config.group_label(k, label), rs) for k, label, rs in base], match)
    cur_unfiltered = next((g for g in groups if g[0] == (st.group or "all")), None) or (groups[0] if groups else None)
    out = dict(H)
    out["groups"] = [(k, label, apply(rs, sel)) for k, label, rs in groups]
    out["countries"] = []                       # the country links are the rail's Country facet (one source), not a second list
    cur = next((g for g in out["groups"] if cur_unfiltered and g[0] == cur_unfiltered[0]), None)
    out["cur"] = cur
    out["params"] = list(params())
    out["picker"] = None
    if match and match.get("orgs") and cur and cur[0] == "fit":
        kinds: dict[str, list[dict]] = {}
        for o in match["orgs"]:                  # already in the configured kind order: investors first, then accelerators
            kinds.setdefault(o["kind_label"], []).append(o)
        out["picker"] = {"orgs": match["orgs"], "kinds": list(kinds.items()), "org": match.get("org"), "name": match.get("name"), "any_label": match.get("any_label"), "pending": match.get("pending"),
                         "any": ANY_VALUE, "hidden": [(k, v) for k, v in _hidden(st)]}
    out["match_view"] = None
    rank = (match or {}).get("rank")
    if match and match.get("org") and rank is not None and cur and cur[0] == "fit":
        out["match_view"] = {"org": match["org"], "name": match["name"], "ranked": len(rank["rows"]), "listed": rank["listed"], "note": rank["note"],
                             "early_label": rank["early_label"], "empty_reason": rank["empty_reason"], "closed_note": rank["closed_note"],
                             "connected": rank["connected"], "filtered": bool(sel), "shown": len(cur[2]),
                             "match_href": "/match?" + urlencode({"org": match["org"]}),
                             "connected_href": "/match?" + urlencode({"org": match["org"], "tab": "connected"})}
    out["tabs"] = [{"key": k, "label": label, "n": len(rs), "on": bool(cur) and cur[0] == k,
                    "href": href(sel, {**extra, "group": "" if k == "all" else k}), "hx": href(sel, {**extra, "group": "" if k == "all" else k}, None, PARTIAL)}
                   for k, label, rs in out["groups"]]
    S = sector_options(st, sectors, current) if sectors else None
    R = rail(cur_unfiltered[2], sel, extra, S) if cur_unfiltered else None
    if R is not None:
        R["total"] = len(H.get("rows") or [])
        mv = out["match_view"]
        R["count_text"] = (f"{R['shown']} of the {mv['ranked']} startups ranked for {mv['name']}" if sel else f"{mv['ranked']} startups ranked for {mv['name']}") \
            if mv else f"{R['shown']} of {R['total']} startups"
        R["chips"] = chips(sel, extra, sub_labels(H.get("rows")))
        R["state_url"] = st.url
        R["country"] = next((f for f in R["facets"] if f["param"] == "country"), None)
        R["sector_chip"] = short_title(title) if title else None
    out["rail"] = R
    out["state"] = st
    return out
