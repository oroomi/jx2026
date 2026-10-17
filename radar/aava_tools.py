"""The tools Aava's reasoning model may call (PROJECT_RULES D61). Read-only: each one is a thin, bounded view over code the site already runs
(the cached home list and its filter rail, the memo, the Ocean Impact Assessment, the matchmaker). The model never sends SQL, never writes,
and never reaches a network. Every company or organisation a tool returns is recorded in the turn's ToolContext, which is what lets
radar.aava_entities decide afterwards which names in the answer are real.

`apply_filters` is the one tool the server does not execute for the page: it validates the filters, tells the model how many rows would remain,
and queues an action that the route streams to the browser.

Result sizes are bounded by design (a handful of rows, the newest signals, the top counterparts) so one tool result stays well under
`limits.tool_result_chars` of config/aava_llm.yaml.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from datetime import date
from urllib.parse import urlencode, urlparse

from radar.aava_entities import fold, short_name, urls_in
from radar import fit as fit_mod, home_config, home_filter, home_list, matching, matchmaker, matchmaker_orgs as orgs_mod, matchtext, memo as memo_mod, store

log = logging.getLogger("aava.tools")
NONE = home_filter.NONE
NO_RECORD = "no public record"
# The order of the home list (radar.home_list.build, `strength`, D48): what "top of the list" means.
ORDER_RULE = ("verdict strength first (" + ", ".join(home_list.VERDICT_ORDER) + "); inside one verdict a declared cohort or portfolio company comes first, then the higher "
              "Ocean Impact level, its confidence (high, medium, low), the business readiness level, the number of dated public records, the newest record, then the name; "
              "a company with no level sorts after one that has a level")


# ---- the turn's state ---------------------------------------------------------------------------------------------------------------------
class ToolContext:
    """What one chat turn knows: the sector file, the page the visitor is on, and every entity a tool has returned so far."""

    def __init__(self, thesis: dict, view: dict | None = None, page_company: str | None = None, limits: dict | None = None):
        self.th = thesis
        self.limits = limits or {}
        self.raw_view = view or {}
        self.page_company = page_company
        self.seen: dict[str, str] = {}          # company_key -> name, from tool results of this turn
        self.seen_orgs: dict[str, str] = {}     # organisation id -> name
        self.actions: list[dict] = []
        self.followups: list[str] = []
        self.calls: list[dict] = []             # {name, ms, ok} for the log
        self.sources: dict[str, list[tuple[str, str]]] = {}     # company_key -> [(label, address)] of the records its tool results cited
        self.org_sources: dict[str, str] = {}                   # organisation id -> its declared page
        self.urls: set[str] = set()             # every address a tool result held: the only external links the answer may keep
        self._home: dict | None = None
        self._conns: dict[int, object] = {}     # one read-only connection per thread: the streaming response may call us from several
        self._view: dict | None = None

    # -- resources, opened on first use --------------------------------------------------------------------------------------------------------
    def home(self) -> dict:
        """The cached home list for the thesis (waits up to `limits.home_wait_s` if it is still being built). Always a dict with `rows`."""
        if self._home is None:
            try:
                self._home = home_list.for_template(self.th, wait=float(self.limits.get("home_wait_s", 15))) or {}
            except Exception:  # noqa: BLE001  (a failing list must not end the chat: the tools then say the list is not available)
                log.exception("home list unavailable")
                self._home = {}
        return self._home

    def rows(self) -> list[dict]:
        return self.home().get("rows") or []

    def conn(self):
        tid = threading.get_ident()
        if tid not in self._conns:
            self._conns[tid] = store.open_db(thesis=self.th)
        return self._conns[tid]

    def close(self) -> None:
        for c in self._conns.values():
            try:
                if c is not None:
                    c.close()
            except Exception:  # noqa: BLE001  (a connection owned by another thread: it is released with that thread)
                pass
        self._conns.clear()

    def see(self, key: str | None, name: str | None) -> None:
        if key and name:
            self.seen[str(key)] = str(name)

    def see_org(self, oid: str | None, name: str | None, url: str | None = None) -> None:
        if oid and name:
            self.seen_orgs[str(oid)] = str(name)
            if url and str(url).startswith("http"):
                self.org_sources.setdefault(str(oid), str(url))

    def add_source(self, key: str, label: str | None, url: str | None) -> None:
        """Remember a record a company's facts came from (the answer's source line is built from these, never from the model's own links)."""
        if key and url and str(url).startswith("http"):
            lst = self.sources.setdefault(key, [])
            if all(u != url for _, u in lst):
                lst.append((str(label or "Source record"), str(url)))

    def by_key(self) -> dict[str, dict]:
        return {r["company_key"]: r for r in self.rows()}

    def view(self) -> dict:
        """The client's view, sanitised: only known facet names with short values, only row keys that exist on the list (names come from the list)."""
        if self._view is None:
            self._view = sanitize_view(self.raw_view, self)
        return self._view


def source_lines(ctx: ToolContext, keys: list[str], text: str, per: int = 4) -> list[dict]:
    """The records behind the answer, for the line printed under it: each company the answer links (its records the tools cited, else its page on this
    site) and each organisation the answer names (its declared page). Every address comes from a tool result, none from the model."""
    out = []
    for k in keys:
        links = (ctx.sources.get(k) or [("The radar's record", f"/c/{k}")])[:per]
        counts = {lb: sum(1 for x, _ in links if x == lb) for lb, _ in links}
        shown = [{"label": lb if counts[lb] == 1 else f"{lb} ({urlparse(u).hostname or 'link'})", "url": u} for lb, u in links]
        out.append({"name": ctx.seen.get(k, k), "links": shown})
    for oid, name in ctx.seen_orgs.items():
        if name in text and ctx.org_sources.get(oid):
            out.append({"name": name, "links": [{"label": "Declared page", "url": ctx.org_sources[oid]}]})
    return out


def sanitize_view(raw: dict, ctx: ToolContext) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    filters: dict[str, list[str]] = {}
    f = raw.get("filters")
    if isinstance(f, dict):
        old = {new: o for o, new in home_filter.ALIAS.items()}     # a parameter's old name is still read
        for p in home_filter.params():
            vals = f.get(p) if p in f else f.get(old.get(p, p))
            vals = [vals] if isinstance(vals, str) else (vals if isinstance(vals, list) else [])
            vals = [v.strip() for v in vals if isinstance(v, str) and v.strip() and len(v) <= home_filter.MAX_LEN][: home_filter.MAX_VALUES]
            if vals:
                filters[p] = list(dict.fromkeys(vals))
    index = ctx.by_key()
    keys = [k for k in (raw.get("rows") if isinstance(raw.get("rows"), list) else []) if isinstance(k, str) and k in index][:20]
    count = raw.get("count")
    group = raw.get("group") if isinstance(raw.get("group"), str) and len(raw.get("group")) <= 20 else ""
    return {"filters": filters, "rows": keys, "count": count if isinstance(count, int) and 0 <= count <= 100000 else None, "group": group}


# ---- the filter language, the same one the rail speaks ----------------------------------------------------------------------------------
def _facet_options(ctx: ToolContext) -> dict[str, list[dict]]:
    """{param: [{value, label, count}]} over every row of the list: what a filter value can be."""
    rail = home_filter.rail(ctx.rows(), {}, {})
    return {f["param"]: [{"value": o["value"], "label": o["label"], "count": o["count"]} for o in f["options"]] for f in rail["facets"]}


def _canon(param: str, value: str, ctx: ToolContext, present: dict[str, list[dict]]) -> str:
    """Map what a model might write ('accelerator', 'high', 5, 'Finland') to the value the rail uses."""
    v = str(value).strip()
    low = v.casefold()
    if low in ("none", "no public record", "unknown", "not stated", "no verdict", "missing"):
        return NONE
    options = {o["value"].casefold(): o["value"] for o in present.get(param, [])}
    labels = {o["label"].casefold(): o["value"] for o in present.get(param, [])}
    if low in options:
        return options[low]
    if low in labels:
        return labels[low]
    if param == "verdict":
        return v.upper()
    if param in ("impact", "fit"):
        return {"not yet evidenced": home_list.GAP}.get(low, v.capitalize())
    if param in ("trl", "brl"):
        bands = ((ctx.th.get("memo") or {}).get("bands") or {}).get("technology" if param == "trl" else "business") or {}
        lo, hi = bands.get("low_max", 3), bands.get("high_min", 7)
        if low.isdigit() and 1 <= int(low) <= home_list.SCALE_MAX:
            return home_list._band_range(int(low), bands)
        return {"low": f"1-{lo}", "medium": f"{lo + 1}-{hi - 1}", "high": f"{hi}-{home_list.SCALE_MAX}"}.get(low, v.replace(" to ", "-").replace("–", "-"))
    if param == "irl":
        return "known" if low in ("known", "on record", "yes", "evidenced") else v
    if param == "country":
        by_name = {n.casefold(): c for c, n in home_config.country_names().items()}
        return by_name.get(low, v.upper() if len(v) == 2 else v)
    return v


# ---- the sub-sector taxonomy (config/thesis.yaml `taxonomy:`) ----------------------------------------------------------------------------
UNCLASSIFIED = home_filter.UNCLASSIFIED
IMPACT_CATEGORY = "impact_category"        # what the tools call the rail's `sector` facet (the Navigator impact category): it is not the sub-sector
PARAM_ALIAS = {IMPACT_CATEGORY: "sector"}   # a name the model may use -> the rail's own parameter (the page, and so the action, speaks the rail's names)
_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)


def subsector_catalog(th: dict) -> list[dict]:
    """[{slug, label}] of the thesis' sub-sectors, in the taxonomy's order, then 'Not yet classified'. Empty when the sector file has no taxonomy."""
    tx = th.get("taxonomy") if isinstance(th.get("taxonomy"), dict) else None
    if not tx or not tx.get("sectors"):
        return []
    u = tx.get("unclassified") or {}
    return [{"slug": x["slug"], "label": x["label"]} for x in tx["sectors"]] + [{"slug": u.get("slug") or UNCLASSIFIED, "label": u.get("label") or "Not yet classified"}]


def _words(text: str) -> set[str]:
    return set(_WORD.findall(fold(text)))


def _same_word(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)))


def resolve_subsector(value, th: dict) -> list[str]:
    """The sub-sector slugs a model's spelling means: the slug, the label, or words of the label ('aquaculture', 'boats'). More than one slug when
    the words fit several equally well (they are alternatives); an empty list when it means none."""
    cat = subsector_catalog(th)
    v = str(value or "").strip()
    if not v or not cat:
        return []
    low = v.casefold()
    for c in cat:
        if low in (c["slug"].casefold(), c["label"].casefold()) or low.replace(" ", "_").replace("-", "_") == c["slug"].casefold():
            return [c["slug"]]
    q = _words(v)
    if not q:
        return []
    scored = []
    for c in cat[:-1]:                          # the last entry is "Not yet classified": a derived bucket, never asked for by words
        w = _words(c["label"]) | _words(c["slug"].replace("_", " "))
        hit = sum(1 for t in q if any(_same_word(t, x) for x in w))
        if hit == len(q):                       # every word the model wrote is a word of this sub-sector
            scored.append((hit, c["slug"]))
    return [slug for hit, slug in scored if hit == max(h for h, _ in scored)] if scored else []


def normalize_filters(raw, ctx: ToolContext, leftovers: list[str] | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """(selection, notes). Unknown facet names are dropped with a note; a value no row carries stays in the selection (the empty result says so) and
    gets a note listing the values that exist. A `subsector` that is not one of the taxonomy's sub-sectors is appended to `leftovers` when the caller
    passes one (search turns it into a text search); a sector word written as an impact category is moved to `subsector` with a note."""
    sel: dict[str, list[str]] = {}
    notes: list[str] = []
    if not isinstance(raw, dict):
        return sel, notes
    present = _facet_options(ctx)
    th = ctx.th
    catalog = {c["slug"]: c["label"] for c in subsector_catalog(th)}
    moved: list[str] = []
    for key, vals in raw.items():
        param = home_filter.ALIAS.get(PARAM_ALIAS.get(key, key), PARAM_ALIAS.get(key, key))
        if param not in home_filter.params():
            if key not in ("text", "limit", "group"):
                notes.append(f"'{key}' is not a filter; the filters are {', '.join(shown_name(p) for p in home_filter.params())}")
            continue
        vals = [vals] if not isinstance(vals, (list, tuple)) else list(vals)
        out = []
        for v in vals:
            if not (isinstance(v, (str, int)) and str(v).strip()):
                continue
            if param == "subsector":
                slugs = resolve_subsector(v, th)
                if not slugs:
                    if leftovers is not None:
                        leftovers.append(str(v).strip())
                        notes.append(f"'{v}' is not a sub-sector, so it was searched as words in the company name, line of business and sub-sector labels instead")
                    else:
                        notes.append(f"'{v}' is not a sub-sector; the sub-sectors are {', '.join(f'{k} ({lb})' for k, lb in catalog.items())}")
                    continue
                if str(v).strip().casefold() not in (x.casefold() for x in slugs):
                    notes.append(f"'{v}' read as subsector {', '.join(slugs)}")
                out.extend(slugs)
                continue
            c = _canon(param, str(v), ctx, present)
            if param == "sector" and c not in {o["value"] for o in present.get("sector", [])} and c != NONE:
                slugs = resolve_subsector(v, th)         # 'Aquaculture' written as an impact category: it is a sub-sector
                if slugs:
                    moved.extend(slugs)
                    notes.append(f"'{v}' is a sub-sector, not an impact category: used subsector={', '.join(slugs)} (impact_category values are {', '.join(o['value'] for o in present.get('sector', []) if o['value'] != NONE) or 'none'})")
                    continue
            out.append(c)
            if c not in {o["value"] for o in present.get(param, [])}:
                have = ", ".join(f"{o['value']} ({o['count']})" for o in present.get(param, [])[:12]) or "none"
                notes.append(f"no company on the list has {shown_name(param)}={c}; values on the list: {have}")
        out = list(dict.fromkeys(out))[: home_filter.MAX_VALUES]
        if out:
            sel[param] = list(dict.fromkeys([*sel.get(param, []), *out]))
    if moved:
        sel["subsector"] = list(dict.fromkeys([*sel.get("subsector", []), *moved]))[: home_filter.MAX_VALUES]
    for slug in sel.get("subsector", []):
        if slug not in {o["value"] for o in present.get("subsector", [])}:
            have = ", ".join(f"{o['value']} ({o['count']})" for o in present.get("subsector", [])[:12]) or "none"
            note = f"no company on the list has subsector={slug}; sub-sectors on the list: {have}"
            if note not in notes:
                notes.append(note)
    return sel, notes


def shown_name(param: str) -> str:
    """The name the model reads for a rail parameter (the rail's `sector` facet is called impact_category in the tools)."""
    return IMPACT_CATEGORY if param == "sector" else param


def shown_filters(sel: dict) -> dict:
    return {shown_name(k): v for k, v in sel.items()}


# ---- row summaries ---------------------------------------------------------------------------------------------------------------------
def _level(cell: dict | None) -> str:
    return (cell or {}).get("text") or NO_RECORD


def row_summary(r: dict) -> dict:
    c = r.get("criteria") or {}
    ocean = r.get("ocean") or {}
    return {
        "company_key": r["company_key"], "name": r["name"], "country": r.get("country") or "not stated",
        "register_line_of_business": r.get("sector") or "not stated",
        "registered_year": str(r["founded"])[:4] if r.get("founded") else "not stated",
        "sub_sectors": [x["label"] for x in r.get("subsectors") or [] if x.get("slug") != UNCLASSIFIED] or "not yet classified",
        "verdict": r.get("verdict") or "no verdict", "thesis_fit": r.get("fit") or NO_RECORD,
        "ocean_impact": ({"area": ocean.get("area"), "level": f"{ocean['level']} of 9" if ocean.get("level") else NO_RECORD,
                          "band": ocean.get("band") or home_list.GAP, "confidence": ocean.get("confidence")} if ocean else NO_RECORD),
        "technology_readiness": _level(c.get("trl")), "business_readiness": _level(c.get("brl")), "investment_readiness": _level(c.get("irl")),
        "first_public_record": r.get("first"), "latest_public_record": r.get("latest"),
        "declared_group": r.get("group_tag") if r.get("group_tag") in ("cohort", "portfolio") else None,
        "public_record_checks_covered": f"{r.get('covered', 0)} of {r.get('checks', 0)}",
        "page": f"/c/{r['company_key']}",
    }


def _text_hit(r: dict, text: str) -> bool:
    """Every word of `text` is in the company name, the register's line of business, the impact area, the country or a sub-sector label."""
    t = text.casefold()
    subs = [x.get("label") for x in r.get("subsectors") or [] if x.get("slug") != UNCLASSIFIED]
    hay = " ".join(str(x or "") for x in (r.get("name"), r.get("sector"), (r.get("ocean") or {}).get("area"), *subs,
                                         home_config.country_name(r.get("country") or "") if r.get("country") else "", r.get("company_key"))).casefold()
    return all(w in hay for w in t.split())


# ---- the tools ------------------------------------------------------------------------------------------------------------------------
def search_startups(ctx: ToolContext, a: dict) -> dict:
    lim = ctx.limits
    rows = ctx.rows()
    if not rows:
        return {"error": "the home list is not available right now (it is still being prepared); try again in a moment, or use get_startup with a company_key"}
    words: list[str] = []
    sel, notes = normalize_filters({k: v for k, v in a.items() if k not in ("text", "limit")}, ctx, leftovers=words)
    hits = home_filter.apply(rows, sel)
    text = " ".join([str(a.get("text") or "").strip(), *words]).strip()
    if text:
        hits = [r for r in hits if _text_hit(r, text)]
    try:
        n = int(a["limit"]) if a.get("limit") is not None else lim.get("search_default", 10)
    except (TypeError, ValueError):
        n = lim.get("search_default", 10)
    n = max(0, min(n, lim.get("search_max", 25)))
    shown = hits[:n]
    for r in shown:
        ctx.see(r["company_key"], r["name"])
    out = {"matches": len(hits), "companies_on_the_list": len(rows), "showing": len(shown), "ordered_by": ORDER_RULE,
           "applied_filters": shown_filters(sel), "results": [row_summary(r) for r in shown]}
    if text:
        out["applied_text"] = text
    if notes:
        out["notes"] = notes[:6]
    if not hits or n == 0:
        out["values_on_the_list"] = {shown_name(p): [f"{o['value']} ({o['count']})" for o in opts[:12]] for p, opts in _facet_options(ctx).items()}
    if text and not hits:
        conn = ctx.conn()
        found = store.search(conn, text, 5) if conn is not None else []
        if found:
            for c in found:
                ctx.see(c["company_key"], c["name"])
            out["also_in_the_register_but_not_on_the_list"] = [{"company_key": c["company_key"], "name": c["name"], "country": c.get("country"),
                                                                "line_of_business": c.get("industry_desc"), "page": f"/c/{c['company_key']}"} for c in found]
            out["hint"] = "These exist in the trade register but are not on the home list; call get_startup for what the radar holds on one."
    return out


def _levels(api: dict) -> dict:
    out = {}
    for k in ("technology", "business", "investment"):
        lv = (api.get("readiness") or {}).get(k) or {}
        out[k] = {"framework": lv.get("framework"), "level": f"{lv['level']} of 9" if lv.get("level") else NO_RECORD, "because": lv.get("because"),
                  "evidence": [{"date": e.get("date"), "source": e.get("source_label"), "url": e.get("source_url")} for e in (lv.get("evidence") or [])[:3]]}
    return out


def _cut(text, cap: int) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= cap else t[: cap - 1].rstrip() + "…"


def _clean(text, company_name: str, th: dict, cap: int = 170) -> str:
    return _cut(fit_mod.redact_person_names(text or "", company_name, th) if text else "", cap)


def _counterparts(ctx: ToolContext, key: str, k: int = 3) -> dict | None:
    cfg = matchtext.config(ctx.th)
    if cfg is None:
        return None
    res = matchmaker.match_company(key, ctx.th, conn=ctx.conn(), limit=k)
    if res is None:
        return None
    out = []
    for c in res["counterparts"]:
        ctx.see_org(c["id"], c["name"], c.get("url"))
        met, link = [], None
        for x in c["components"]:
            if x["met"] and x.get("reason"):
                met.append(f"{x['label']}: {_cut(x['reason'], 200)}")
                link = link or next((l.get("url") for l in x.get("links") or [] if l.get("url")), None)
        out.append({"org_id": c["id"], "name": c["name"], "kind": c["kind_label"], "declared_focus": _cut(c.get("focus"), 160), "demand": c.get("demand"),
                    "website": c.get("url"), "deadline": c.get("deadline") or c.get("deadline_text") or "none stated", "geography": c.get("geography"),
                    "reasons_that_hold": met, "reasons_met": f"{c['met']} of {c['of']}", "record": link})
    for x in res.get("connected") or []:
        ctx.see_org(x["id"], x["name"])
    return {"counterparts_listed": res["listed"], "top": out, "already_connected": [{"org_id": x["id"], "name": x["name"], "why": x["why"]} for x in res.get("connected") or []],
            "rule": "kind fits the verdict path, geography includes the startup's country, programme open, at least one sector/word/lookalike reason"}


def _company_named(ctx: ToolContext, ref: str) -> str | None:
    """The company_key of the one company whose name is `ref` (case, punctuation and the legal-form word ignored), on the list first, then in the register;
    None when no company or several are called that. 'viva' is not 'Viva Jets Oy': a part of a name is a guess and is left to did_you_mean."""
    want = fold(ref)
    if not want:
        return None

    def named(name: str) -> bool:
        return want in (fold(name), fold(short_name(name)))

    hits = [r["company_key"] for r in ctx.rows() if named(r["name"])]
    if len(hits) == 1:
        return hits[0]
    conn = ctx.conn()
    found = [c["company_key"] for c in (store.search(conn, ref, 8) if conn is not None else []) if named(c["name"])]
    return found[0] if len(found) == 1 else None


def _position(ctx: ToolContext, key: str):
    """Where the company stands on the home list and the values the list's order reads, so "why is it at the top?" can be answered from the record."""
    rows = ctx.rows()
    i = next((n for n, r in enumerate(rows) if r["company_key"] == key), None)
    if i is None:
        return "not on the home list (it exists in the register; the list holds the companies the radar surfaces plus the declared cohort and portfolio)"
    r = rows[i]
    oi = r.get("ocean") or {}
    brl = ((r.get("criteria") or {}).get("brl") or {}).get("level")
    return {"rank": i + 1, "of": len(rows), "ordered_by": ORDER_RULE,
            "this_company": {"verdict": r.get("verdict") or "no verdict", "declared_group": r.get("group_tag") if r.get("group_tag") in ("cohort", "portfolio") else None,
                             "ocean_impact_level": f"{oi['level']} of 9" if oi.get("level") else NO_RECORD, "ocean_impact_confidence": oi.get("confidence"),
                             "business_readiness_level": f"{brl} of 9" if brl else NO_RECORD, "dated_public_records": len(r.get("signals") or []), "newest_record": r.get("latest")},
            "companies_ahead_with_the_same_verdict": sum(1 for x in rows[:i] if x.get("verdict") == r.get("verdict"))}


def get_startup(ctx: ToolContext, a: dict) -> dict:
    from radar.routes import api as api_routes   # the company page's own assembly, so a number here is the number on the page

    key = str(a.get("company_key") or a.get("name") or "").strip()
    conn = ctx.conn()
    if conn is None:
        return {"error": "no data is loaded"}
    data = store.company(conn, key) if key else None
    resolved_from = None
    if data is None and key:
        named = _company_named(ctx, key)          # 'Viva Jets' written where the key goes: the one company with exactly that name
        if named:
            resolved_from, key = key, named
            data = store.company(conn, key)
    if data is None:
        guess = store.search(conn, key, 5) if key else []
        for c in guess:
            ctx.see(c["company_key"], c["name"])
        return {"error": f"no company with key {key!r} in this radar", "did_you_mean": [{"company_key": c["company_key"], "name": c["name"]} for c in guess]}
    th = ctx.th
    c = data["company"]
    api = api_routes.api_company(key, th["id"], 5)
    if not isinstance(api, dict):   # a JSONResponse means the page itself would fail
        return {"error": "the record could not be assembled"}
    m = memo_mod.build(conn, th, key) or {}
    rec = m.get("recommendation") or {}
    ctx.see(key, c["name"])
    nm = c["name"]
    n_sig = int(ctx.limits.get("signals_in_memo", 10))
    signals = [{"date": s.get("date_label") or s.get("date"), "type": s.get("type_label"), "what": _clean(s.get("detail"), nm, th), "source": s.get("source_label"),
                "url": s.get("source_url"), "confidence": s.get("confidence")} for s in (api.get("signals") or [])[:n_sig]]
    oi = m.get("ocean_impact") or {}
    ctx.add_source(key, "Trade register record", c.get("source_url"))
    for sg in (api.get("signals") or [])[:n_sig]:
        ctx.add_source(key, sg.get("source_label"), sg.get("source_url"))
    for lv in (api.get("readiness") or {}).values():
        for e in (lv.get("evidence") or [])[:3] if isinstance(lv, dict) else []:
            ctx.add_source(key, e.get("source_label"), e.get("source_url"))
    for e in (oi.get("evidence") or [])[:4]:
        ctx.add_source(key, e.get("source_label"), e.get("url"))
    declared = (api.get("readiness") or {}).get("declared_dataset") or {}
    ready = declared.get("ready") or {}
    out = {
        **({"resolved_from_name": resolved_from} if resolved_from else {}),
        "company": {"company_key": key, "name": nm, "business_id": c.get("y_tunnus"), "country": c.get("country") or "not stated", "founded": c.get("founded") or "not stated",
                    "industry": f"{c.get('industry_code') or '?'} {c.get('industry_desc') or ''}".strip(), "website": c.get("website"),
                    "declared_group": c.get("group_tag") if c.get("group_tag") in ("cohort", "portfolio") else None,
                    "register_status": c.get("register_status"), "register_record": c.get("source_url"), "page": f"/c/{key}"},
        "verdict": {"decision": rec.get("decision"), "plain_meaning": rec.get("table_action"), "bands": rec.get("because_labels"), "note": rec.get("note"),
                    "rule_matched": rec.get("matched"), "still_needed": rec.get("needs") or [],
                    "why": [{"text": x.get("text"), "url": x.get("url")} for x in (m.get("plain_why") or [])[:6]],
                    "risks": [{"text": x.get("text")} for x in (m.get("risks") or [])[:4]],
                    "suggested_actions": [{"text": x.get("text"), "url": x.get("url")} for x in (m.get("actions") or [])[:4]]},
        "readiness": _levels(api),
        "ocean_impact_assessment": ({"area": oi.get("area"), "area_basis": oi.get("area_basis"), "level": f"{oi['level']} of 9" if oi.get("level") else "not yet evidenced",
                                     "band": oi.get("band") or home_list.GAP, "confidence": oi.get("confidence"), "confidence_reason": oi.get("confidence_reason"),
                                     "what_would_raise_it": oi.get("raise"), "scalability": (oi.get("scalability") or {}).get("text"),
                                     "evidence": [{"text": e.get("text"), "date": e.get("date"), "source": e.get("source_label"), "url": e.get("url")} for e in (oi.get("evidence") or [])[:4]],
                                     "measures": "how well the area is evidenced, not true impact"} if oi else "no record names an impact area yet"),
        "public_records": {"counts": api.get("counts"), "newest_first": signals},
        "declared_research_gaps": (f"declared research (confidence {declared.get('confidence')}) lists as missing: {ready.get('br_missing')}" if ready.get("br_missing") else None),
        "next_step_rule": {"sentence": (api.get("next_step") or {}).get("sentence"), "because": (api.get("next_step") or {}).get("because"),
                           "url": (api.get("next_step") or {}).get("source_url")},
    }
    out["position_on_the_home_list"] = _position(ctx, key)
    try:
        out["who_to_meet"] = _counterparts(ctx, key) or "matchmaking is not configured for this sector file"
    except Exception:  # noqa: BLE001  (the memo is still useful without the counterparts)
        log.exception("counterparts failed for %s", key)
        out["who_to_meet"] = "the counterpart list could not be built just now"
    return out


def explain_match(ctx: ToolContext, a: dict) -> dict:
    key, oid = str(a.get("company_key") or "").strip(), str(a.get("org_id") or "").strip()
    cfg = matchtext.config(ctx.th)
    if cfg is None:
        return {"error": "matchmaking is not configured for this sector file"}
    conn = ctx.conn()
    today = date.today()
    reg = orgs_mod.registry(conn, ctx.th)
    org = next((o for o in reg["orgs"] if o["id"] == oid), None)
    if org is None:
        near = [o for o in reg["orgs"] if oid.casefold() in o["name"].casefold()][:5] if oid else []
        return {"error": f"no organisation with id {oid!r}; call list_organisations", "did_you_mean": [{"org_id": o["id"], "name": o["name"]} for o in near]}
    ctx.see_org(org["id"], org["name"], org.get("url"))
    idx = matchmaker._index(conn, ctx.th, cfg, today)
    sp = matchmaker.startup(conn, ctx.th, cfg, key, today)
    if sp is None:
        return {"error": f"no matchable company with key {key!r}"}
    ctx.see(key, sp.get("name") or (store.company(conn, key) or {}).get("company", {}).get("name") or key)
    if key in org["members"]:
        return {"company_key": key, "org_id": oid, "org": org["name"], "already_connected": True, "why": org["members"][key]["basis"]}
    ev = matchmaker.evaluate(sp, org, cfg, idx, reg["df"], today)
    row = matchmaker._org_row(org, cfg)
    closed = matchmaker._open(org, today)       # match_company leaves a closed call out before it weighs a reason (D76)
    excluded = matching.closed_words(row["deadline_text"] or closed) if closed else ev["excluded"]
    if not excluded and sp.get("not_startup") and org["kind"] in matchmaker.startup_kinds(cfg):     # D83: the match pages offer startups only
        excluded = f"not a startup on the thesis' rule ({sp['not_startup']}), so no {row['kind_label'].lower()} is offered to it"
    return {"company_key": key, "org_id": oid, "organisation": {"name": org["name"], "kind": row["kind_label"], "declared_focus": row["focus"], "demand": row["demand"],
                                                              "website": row["url"], "deadline": row["deadline"] or row["deadline_text"] or "none stated", "geography": row["geography"]},
            "listed_as_a_counterpart": not excluded, "excluded_because": excluded, "reasons_met": f"{ev['met']} of {ev['of']}",
            "components": [{"component": x["label"], "holds": x["met"], "weight": x["weight"], "reason": x["reason"], "note": x["note"],
                            "links": [{"text": l.get("text"), "url": l.get("url")} for l in (x.get("links") or [])[:2]]} for x in ev["components"]],
            "weights_note": "component weights are a stated hypothesis for the partners to rate; the page shows the reasons, never one score"}


def _call(row: dict) -> str | None:
    """D76: why a counterpart row (matchmaker._org_row) takes no startup today, said the only way a closed call may be said; None when open."""
    closed = matching.call_closed({"open": row.get("open", True), "date": row.get("deadline"), "text": row.get("deadline_text")}, store._today(None))
    return matching.closed_words(row.get("deadline_text") or closed) if closed else None


def _org_named(rows: list[dict], ref: str) -> tuple[dict | None, list[dict]]:
    """(the counterpart `ref` names, near misses). `ref` is an org_id or a name as the person wrote it ("A'Pelago", "redstone blue"): the id, then
    the same name (case, punctuation, legal-form words ignored), then the one counterpart whose name starts with it."""
    ref = str(ref or "").strip()
    if not ref:
        return None, []
    by_id = next((r for r in rows if r["id"] == ref or r["id"] == orgs_mod.slug(ref)), None)
    if by_id:
        return by_id, []
    want = orgs_mod.okey(ref)
    same = [r for r in rows if want and orgs_mod.okey(r["name"]) == want]
    starts = [r for r in rows if len(want) >= 4 and orgs_mod.okey(r["name"]).startswith(want)]
    hit = same or starts
    if len(hit) == 1:
        return hit[0], []
    near = hit or [r for r in rows if fold(ref) and fold(ref) in fold(r["name"])]
    return None, near[:5]


_org_lock = threading.Lock()
_org_cache: dict[tuple, dict] = {}      # (sector id, store version, org id) -> matchmaker.match_org result; a rebuilt store gets a new version


def _match_org(ctx: ToolContext, org_id: str) -> dict | None:
    """matchmaker.match_org(org_id) with the page's default limit, kept once per store version (it takes about 1.5 s per organisation)."""
    try:
        stamp = home_list.stamp(ctx.th)
    except Exception:  # noqa: BLE001  (no version to key on: build it, keep nothing)
        stamp = None
    key = (ctx.th.get("id"), stamp, org_id)
    with _org_lock:
        hit = _org_cache.get(key) if stamp is not None else None
    if hit is not None:
        return hit
    res = matchmaker.match_org(org_id, ctx.th, conn=ctx.conn())
    if res is not None and stamp is not None:
        with _org_lock:
            if len(_org_cache) >= 16:
                _org_cache.clear()
            _org_cache[key] = res
    return res


def get_org_matches(ctx: ToolContext, a: dict) -> dict:
    """The /match?org=<id> page as data (D77): matchmaker.match_org with the page's own default limit, so the order, the reasons and the verdict
    path are the ones that page prints. Only the first `limit` rows are returned; the page holds the rest."""
    cfg = matchtext.config(ctx.th)
    if cfg is None:
        return {"error": "matchmaking is not configured for this sector file"}
    rows = matchmaker.org_list(ctx.th, conn=ctx.conn()) or []
    org, near = _org_named(rows, a.get("org") or a.get("org_id") or a.get("name"))
    if org is None:
        return {"error": f"no organisation called {a.get('org')!r}; call list_organisations", "did_you_mean": [{"org_id": r["id"], "name": r["name"]} for r in near]}
    res = _match_org(ctx, org["id"])
    if res is None:
        return {"error": f"the match list for {org['name']} could not be built"}
    try:
        n = int(a["limit"]) if a.get("limit") is not None else int(ctx.limits.get("org_matches_default", 5))
    except (TypeError, ValueError):
        n = int(ctx.limits.get("org_matches_default", 5))
    n = max(1, min(n, int(ctx.limits.get("org_matches_max", 10))))
    o, pipe = res["org"], res.get("pipeline") or {}
    page = "/match?" + urlencode({"org": o["id"]})
    ctx.see_org(o["id"], o["name"], o.get("url"))
    ctx.urls.add(page)                  # the one site page an answer may link besides /c/<key> (aava_entities.check_link)
    shown = res["startups"][:n]
    out_rows = []
    for s in shown:
        ctx.see(s["key"], s["name"])
        held = [c for c in s["components"] if c["met"] and c.get("chip")]
        path = s.get("verdict") or "no verdict"
        if s.get("early") and pipe.get("early_label"):
            path += f", {pipe['early_label']}"
        out_rows.append({"rank": s["rank"], "company_key": s["key"], "name": s["name"], "country": s.get("country") or "not stated", "verdict_path": path,
                         "reasons_that_hold": [c["chip"] for c in held], "reasons_met": f"{s['met']} of {sum(1 for c in s['components'] if c['met'] is not None)}",
                         "page": s["url"]})
    connected = res.get("connected") or []
    for s in connected[:5]:
        ctx.see(s["key"], s["name"])
    out = {"organisation": {"org_id": o["id"], "name": o["name"], "kind": o["kind_label"], "declared_focus": _cut(o.get("focus"), 160), "demand": o.get("demand"),
                            "deadline": o.get("deadline") or o.get("deadline_text") or "none stated", "geography": o.get("geography")},
           "match_page": page, "startups_listed": res["listed"], "showing": len(out_rows),
           "ordered_by": "the matchmaker's order on the match page: how many reasons hold and the weight the sector file gives each, early pipeline after the ready ones",
           "startups": out_rows,
           "already_connected": {"count": len(connected), "first": [{"company_key": s["key"], "name": s["name"]} for s in connected[:5]],
                                 "note": "its declared cohort or portfolio in our records: not ranked, it already knows them"}}
    if pipe.get("note"):
        out["pipeline_note"] = pipe["note"]
    if res.get("not_startups"):     # D83: the page's line on the companies an investor or accelerator is not offered
        out["not_offered"] = (f"{res['not_startups']:,} companies on the radar are not startups on the thesis' rule (founded more than "
                              f"{(ctx.th.get('geography') or {}).get('stage_max_company_age_years')} years ago, or listed as a counterpart organisation) "
                              f"and are not offered to {o['name']}")
    if o.get("closed_note"):
        out["closed"] = matching.closed_words(o["closed_note"])
    if not out_rows and o.get("empty_reason"):
        out["why_none"] = o["empty_reason"]
    return out


def list_organisations(ctx: ToolContext, a: dict) -> dict:
    cfg = matchtext.config(ctx.th)
    if cfg is None:
        return {"error": "matchmaking is not configured for this sector file"}
    rows = matchmaker.org_list(ctx.th, conn=ctx.conn()) or []
    kind, text = str(a.get("kind") or "").strip().casefold(), str(a.get("text") or "").strip().casefold()
    kinds = {k: v["label"] for k, v in cfg["kinds"].items()}
    if kind:
        by_label = {v.casefold(): k for k, v in kinds.items()}
        kind = by_label.get(kind, kind)
        rows = [r for r in rows if r["kind"].casefold() == kind]
    if text:
        rows = [r for r in rows if all(w in f"{r['name']} {r['focus']}".casefold() for w in text.split())]
    shown = rows[:15]
    for r in shown:
        ctx.see_org(r["id"], r["name"], r.get("url"))
    return {"matches": len(rows), "showing": len(shown), "kinds": kinds,
            "organisations": [{"org_id": r["id"], "name": r["name"], "kind": r["kind_label"], "declared_focus": r["focus"], "demand": r["demand"], "website": r["url"],
                               "deadline": r["deadline"] or r["deadline_text"] or "none stated", "geography": r["geography"], "companies_of_theirs_in_our_records": r["members_in_records"],
                               **({"call": _call(r)} if _call(r) else {})}
                              for r in shown]}


def get_current_view(ctx: ToolContext, a: dict) -> dict:
    v = ctx.view()
    index = ctx.by_key()
    rows = [row_summary(index[k]) for k in v["rows"][:15]]
    for r in rows:
        ctx.see(r["company_key"], r["name"])
    page = None
    if ctx.page_company:
        conn = ctx.conn()
        d = store.company(conn, ctx.page_company) if conn is not None else None
        if d:
            page = {"company_key": ctx.page_company, "name": d["company"]["name"]}
            ctx.see(ctx.page_company, page["name"])
    return {"on_company_page": page, "list_filters": v["filters"] or "none (the full list)", "group_tab": v["group"] or "all",
            "rows_visible": v["count"], "first_visible_rows": rows,
            "companies_on_the_list": len(index) or None}


def apply_filters(ctx: ToolContext, a: dict) -> dict:
    raw = a.get("filters") if isinstance(a.get("filters"), dict) else {}
    sel, notes = normalize_filters(raw, ctx)
    group = a.get("group").strip() if isinstance(a.get("group"), str) else ""
    if group.startswith("cc-"):        # an old country tab is the country filter now
        sel["country"] = list(dict.fromkeys([*sel.get("country", []), group[3:].upper()]))
        group = ""
    H = ctx.home()
    groups = {g[0]: g for g in (H.get("groups") or [])}
    if group in ("", "all"):
        group = ""
    elif group not in groups:
        notes.append(f"group '{group}' does not exist; groups: {', '.join(groups)}")
        group = ""
    org = str(a.get("top_matching_for") or "").strip()
    org_name = None
    if org:                              # the Top matching tab for one investor or accelerator (D35): the matchmaker's ranking of the list
        from radar import home_orgs
        pick = next((o for o in home_orgs.organisations(ctx.th) if o["id"] == org), None)
        if pick is None:
            notes.append(f"'{org}' is not an organisation the Top matching tab offers; use an org_id from list_organisations of kind investor or accelerator")
            org = ""
        else:
            org_name, group = pick["name"], "fit"
            ctx.see_org(org, org_name)
    base = groups[group][2] if group else ctx.rows()
    remain = len(home_filter.apply(base, sel))
    action = {"type": "apply_filters", "filters": sel, "group": group, "matches": None if org else remain, **({"for": org} if org else {})}
    ctx.actions.append(action)
    out = {"queued_for_the_page": True, "filters": shown_filters(sel) or "cleared", "rows_that_will_remain": remain, "of": len(base)}
    if org:
        out.pop("rows_that_will_remain")
        out["top_matching_for"] = org_name
        out["note"] = f"the Top matching tab now ranks the list for {org_name} with the matchmaker's reasons; the page shows how many rows remain"
    if group:
        out["group_tab"] = group
    if notes:
        out["notes"] = notes[:6]
    return out


def clean_followups(qs, limits: dict) -> list[str]:
    cap, n = int(limits.get("followup_chars", 90)), int(limits.get("followups_max", 3))
    out = []
    for q in qs if isinstance(qs, list) else []:
        t = " ".join(str(q).split()).strip(" -*_\u2022\"'")[:cap].strip()
        if isinstance(q, str) and t and t not in out:
            out.append(t)
    return out[:n]


_FOLLOWUP_HEAD = re.compile(r"^[\s>*_#-]*follow[- ]?ups?(?:\s+questions?)?[\s*_]*:[\s*_]*(.*)$", re.IGNORECASE)


def split_followups(text: str, limits: dict | None = None) -> tuple[str, list[str]]:
    """(answer without its follow-up line, the questions). The model ends its answer with `Follow-ups: a? | b? | c?` (or the same as a short bullet list under
    that heading); the page shows them as buttons, not as text. Only a heading in the last five lines counts. Nothing found: (text unchanged, [])."""
    lines = (text or "").rstrip().split("\n")
    for i in range(len(lines) - 1, max(-1, len(lines) - 6), -1):
        m = _FOLLOWUP_HEAD.match(lines[i])
        if not m:
            continue
        items = [x for x in re.split(r"\s*\|\s*", m.group(1)) if x.strip()]
        items += [re.sub(r"^[\s>*_\d.)\u2022-]+", "", ln) for ln in lines[i + 1:] if ln.strip()]
        qs = clean_followups(items, limits or {})
        if not qs:
            return text, []
        return "\n".join(lines[:i]).rstrip(), qs
    return text, []


def suggest_followups(ctx: ToolContext, a: dict) -> dict:
    """Not in the schema any more (the model closes its answer with a `Follow-ups:` line, see split_followups); kept so a model that still calls it is served."""
    ctx.followups = clean_followups(a.get("questions"), ctx.limits)
    return {"ok": True, "shown_to_the_person": len(ctx.followups)}


# ---- the schema Claude sees ---------------------------------------------------------------------------------------------------------
def _facet_prop(desc: str, enum: list[str] | None = None) -> dict:
    return {"type": "array", "items": {"type": "string", **({"enum": enum} if enum else {})}, "description": desc}


def _filters(th: dict | None) -> dict:
    """The filter properties. `subsector` carries the sector file's own sub-sector slugs as an enum (their labels are in the description); a sector
    file without a taxonomy has no such property. The rail's `sector` facet is called impact_category here, so it is not mistaken for the sub-sector."""
    cat = subsector_catalog(th or {})
    out = {}
    if cat:
        listing = "; ".join(f"{c['slug']} = {c['label']}" for c in cat)
        out["subsector"] = _facet_prop(
            "THE way to ask for a sector or industry: one or more sub-sectors of the blue economy (alternatives). Example: {\"subsector\": [\"aquaculture_fisheries\"]} "
            f"finds aquaculture and fisheries startups. Slug = label: {listing}.", [c["slug"] for c in cat])
    out.update({
        "verdict": _facet_prop("Verdicts (any of): INVEST, DUE DILIGENCE, ACCELERATOR, PARTNER INTRODUCTION, GRANT SUPPORT, PORTFOLIO SUPPORT, WATCHLIST, REJECT / LOW FIT, or none for no verdict."),
        "impact": _facet_prop("Ocean impact band (any of): High, Medium, Low, 'Not yet evidenced' (sector implied only), or none for no public record."),
        "trl": _facet_prop("Technology readiness band (any of): 1-3, 4-6, 7-9, or none for no public record. A single level 1 to 9 is mapped to its band."),
        "brl": _facet_prop("Business readiness band (any of): 1-3, 4-6, 7-9, or none."),
        "irl": _facet_prop("Investment readiness: known (a level is on record) or none."),
        "fit": _facet_prop("Thesis fit band (any of): High, Medium, Low, or none."),
        "country": _facet_prop("Country, ISO-2 code (FI, SE, NO, DK, EE ...) or the name."),
        IMPACT_CATEGORY: _facet_prop("The Navigator impact category (for example Aquatech or Ocean data), or none. NOT the sub-sector and rarely needed: to ask for a sector use `subsector`. "
                                     "The values that exist are listed in values_on_the_list (call with limit 0)."),
        "age": _facet_prop("Registered age: lt1, 1-3, 3-5, gt5, or none."),
        "deadline": _facet_prop("Programme deadline: '90' for a deadline within 90 days."),
        "member": _facet_prop("Declared company: cohort or portfolio."),
    })
    return out


def tools_for(th: dict | None) -> list[dict]:
    """The tool schemas for one sector file (the sub-sector enum is that file's taxonomy)."""
    F = _filters(th)
    return [
        {"name": "search_startups",
         "description": ("Search the companies on the home list (the radar's cached list: companies surfaced with a stated reason plus the declared cohort and portfolio) "
                         "with the same filters as the page's filter rail: several values of one filter are alternatives, different filters all have to hold. "
                         "For a sector or industry use `subsector` (for example subsector [\"aquaculture_fisheries\"]); `impact_category` is a different, Navigator facet. "
                         "`text` searches words in the company name, the register's line of business and the sub-sector labels. "
                         "Returns each match with its line of business, sub-sectors, registration year, verdict, thesis fit, ocean impact, readiness levels and latest public record, "
                         "strongest verdict first. With no filters it returns the top of the list and, when nothing matches, the values that exist."),
         "input_schema": {"type": "object", "properties": {
             **F,
             "text": {"type": "string", "description": "Words that must all appear in the company name, the register's line of business, the impact area, the country or a sub-sector label. "
                                                       "If nothing on the list matches, the register is searched by name."},
             "limit": {"type": "integer", "description": "How many rows to return (default 10, at most 25); 0 returns only the count and the values that exist."}}}},
        {"name": "get_startup",
         "description": ("Everything the radar holds on one company: register facts, the verdict with its plain reasons, risks and suggested actions, technology, business and "
                         "investment readiness each with its evidence, the Ocean Impact Assessment (area, level of 9, confidence and what record would raise it), the newest dated "
                         "public records with source labels and links, who to meet (ranked organisations with the reasons that hold) and the next-step rule. "
                         "Takes the company_key from a search result, or the company's name as the person wrote it (for example 'Viva Jets'), so a named company needs no search first. "
                         "Several companies: call it once for each, together in one round."),
         "input_schema": {"type": "object", "properties": {"company_key": {"type": "string", "description": "The company_key, for example 2962040-6, or the exact company name, for example Viva Jets"}}, "required": ["company_key"]}},
        {"name": "explain_match",
         "description": ("Why one organisation does or does not fit one company: the matchmaker's six reasons (sector or impact area, portfolio lookalike, shared words, readiness window, timing, "
                         "geography), each with the sentence and record behind it, and the hard filter that excluded the pair if there is one. Use an org_id from get_startup or list_organisations."),
         "input_schema": {"type": "object", "properties": {"company_key": {"type": "string"}, "org_id": {"type": "string"}}, "required": ["company_key", "org_id"]}},
        {"name": "get_org_matches",
         "description": ("THE answer to 'who should <organisation> meet', 'which startups fit <organisation>' or 'who should <organisation> invest in or accept': the ranked list "
                         "the site's match page /match?org=<org_id> prints for that investor, accelerator, programme, funder or pilot partner, in its order, each startup "
                         "with its verdict path and the reasons that hold, plus how many are listed, the companies it is already connected to, and the match_page address "
                         "to link. Takes the organisation's name as the person wrote it (for example A'Pelago or Redstone Blue) or its org_id."),
         "input_schema": {"type": "object", "properties": {"org": {"type": "string", "description": "The organisation's name or org_id, for example A'Pelago or redstone-blue"},
                                                           "limit": {"type": "integer", "description": "How many of the ranked startups to return (default 5, at most 10)."}},
                          "required": ["org"]}},
        {"name": "list_organisations",
         "description": ("The investors, accelerators, programmes, public funders, clusters, corporates and ports the matchmaker knows, with their declared focus, demand, deadline and geography. "
                         "Filter by kind and by words in the name or focus. Returns org_id values for explain_match. A row with `call` takes no application now: never a next step."),
         "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "description": "A kind id or label, for example investor, accelerator, funder; omit for all."},
                                                           "text": {"type": "string", "description": "Words that must appear in the name or declared focus."}}}},
        {"name": "get_current_view",
         "description": ("What the person has on screen right now: the filters set on the home list, the group tab, how many rows are visible, the first visible rows, "
                         "and the company page they are on if any. Call it when they say 'these', 'this list' or 'narrow it'."),
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "apply_filters",
         "description": ("Change the home page's filters for the person (the page updates in place). Same values as search_startups (a sector is `subsector`). The server does not run it; it checks the values, "
                         "tells you how many rows will remain, and the browser applies it. An empty filters object clears every filter. Use it when they ask to show, filter, narrow or clear the list."),
         "input_schema": {"type": "object", "properties": {"filters": {"type": "object", "properties": {k: {"type": "array", "items": v["items"]} for k, v in F.items()},
                                                                      "description": "The complete filter state to show (it replaces the current one). Same filters and values as search_startups."},
                                                           "group": {"type": "string", "description": "Optional group tab: all, fit (Top fits), ready (Investor-ready) or new (New this quarter). Countries are the country filter."},
                                                           "top_matching_for": {"type": "string", "description": "Optional org_id of an investor or accelerator (from list_organisations): the page shows its Top matching tab, the list ranked for that organisation."}},
                          "required": ["filters"]}},
    ]


def _default_tools() -> list[dict]:
    try:
        from radar import thesis as thesis_mod
        return tools_for(thesis_mod.load())
    except Exception:  # noqa: BLE001  (no readable sector file at import time: the schema without the sub-sector enum)
        return tools_for(None)


TOOLS: list[dict] = _default_tools()      # the default sector file's schema; a Turn asks tools_for(its own sector file)

HANDLERS = {"search_startups": search_startups, "get_startup": get_startup, "explain_match": explain_match, "get_org_matches": get_org_matches,
            "list_organisations": list_organisations, "get_current_view": get_current_view, "apply_filters": apply_filters, "suggest_followups": suggest_followups}


# ---- warm-up: no tool call should wait for a cold cache ------------------------------------------------------------------------------
_warm_lock = threading.Lock()
_warmed: dict[str, tuple] = {}      # sector id -> the store version (home_list.stamp) already warmed or being warmed


def warm(th: dict) -> float:
    """Build, on this thread, what the tools would otherwise build on their first call: the cached home list (the rows every search reads), and the
    memo, counterpart and organisation indexes behind get_startup and list_organisations (one company opened and discarded), and the match lists
    get_org_matches reads for the picker's organisations (D77). Returns the seconds taken;
    a cache that is already warm costs a few milliseconds. Never raises."""
    t0 = time.monotonic()
    ctx = ToolContext(th)
    try:
        home_list.warm(th)
        rows = ctx.rows()
        if rows:
            get_startup(ctx, {"company_key": rows[0]["company_key"]})
            list_organisations(ctx, {})
            from radar import home_orgs      # the match lists a partner question reads first: the default organisation and the first of each picker kind
            orgs = home_orgs.organisations(th)
            for oid in dict.fromkeys([home_orgs.default_org(orgs), *{o["kind"]: o["id"] for o in reversed(orgs)}.values()]):
                if oid:
                    _match_org(ctx, oid)
    except Exception:  # noqa: BLE001  (a failed warm-up only means the first tool call builds the cache itself)
        log.exception("aava warm-up failed")
    finally:
        ctx.close()
    return time.monotonic() - t0


def ensure_warm(th: dict) -> bool:
    """Start `warm` in the background once per sector file and store version (a rebuilt store gets a new version, so it is warmed again on the next
    turn). Returns True when a warm-up was started. Not run under pytest or with RADAR_NO_WARM set."""
    if "pytest" in sys.modules or os.environ.get("RADAR_NO_WARM") is not None:
        return False
    try:
        stamp = home_list.stamp(th)
    except Exception:  # noqa: BLE001
        return False
    with _warm_lock:
        if stamp is None or _warmed.get(th.get("id")) == stamp:
            return False
        _warmed[th.get("id")] = stamp
    threading.Thread(target=warm, args=(th,), name="aava-warm", daemon=True).start()
    return True


def run_tool(ctx: ToolContext, name: str, args) -> tuple[str, bool]:
    """(result text for the model, ok). Unknown tool names and failures come back as an error the model can read; nothing here raises."""
    t0 = time.monotonic()
    ok = True
    try:
        fn = HANDLERS.get(name)
        if fn is None:
            res, ok = {"error": f"no tool named {name}; the tools are {', '.join(HANDLERS)}"}, False
        else:
            res = fn(ctx, args if isinstance(args, dict) else {})
            ok = not (isinstance(res, dict) and "error" in res and len(res) <= 3)
    except Exception as e:  # noqa: BLE001  (the model gets the message and can try something else)
        log.exception("tool %s failed", name)
        res, ok = {"error": f"{name} failed: {type(e).__name__}"}, False
    text = json.dumps(res, ensure_ascii=False, default=str)
    cap = int(ctx.limits.get("tool_result_chars", 7000))
    if len(text) > cap and isinstance(res, dict):
        # shrink the longest list (rows, signals) until it fits, so the model and the tests always get valid JSON
        lists = sorted(((k, v) for k, v in res.items() if isinstance(v, list) and v), key=lambda kv: -len(json.dumps(kv[1], default=str)))
        res = dict(res)
        while len(text) > cap and lists:
            k, v = lists[0]
            if len(v) <= 1:
                lists.pop(0)
                continue
            v = v[: max(1, len(v) * 2 // 3)]
            lists[0] = (k, v)
            res[k] = v
            res["note"] = "list shortened to fit; ask for fewer rows or one company for the rest"
            text = json.dumps(res, ensure_ascii=False, default=str)
    if len(text) > cap:
        text = json.dumps({"error": "result too long; ask for fewer rows or one company"})
    ctx.urls |= urls_in(text)
    ctx.calls.append({"name": name, "ms": round((time.monotonic() - t0) * 1000), "ok": ok})
    return text, ok
