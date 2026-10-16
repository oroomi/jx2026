"""GET /method : the rules printed in full, the sources table and the connector slots.
Also owns two cross-page hooks: the thesis switcher helpers for base.html and the radar_thesis cookie."""
from __future__ import annotations

import inspect
from pathlib import Path

from fastapi import APIRouter, Request

from radar import emit, fit, frameworks, matching, store, thesis as thesis_mod
from radar.routes.home import ROOT, _has_route, templates

router = APIRouter()

CONNECTOR_SLOTS = ("LinkedIn", "Dealroom", "Tracxn", "PitchBook", "Crunchbase")
BF_EXPORT = "data/declared/businessfinland.xlsx"
COOKIE_MAX_AGE = 86400


def _current_thesis(request) -> dict:
    th = getattr(getattr(request, "state", None), "thesis", None)
    return th if th is not None else thesis_mod.load()


def _thesis_options() -> list[tuple[str, str]]:
    return [(tid, thesis_mod.load(path)["title"]) for tid, path in thesis_mod.available().items()]


templates.env.globals["current_thesis"] = _current_thesis
templates.env.globals["thesis_options"] = _thesis_options

# store.context() records a valid ?thesis= choice on request.state; the cookie is attached when the page renders.
_orig_template_response = templates.TemplateResponse


def _template_response(request, *args, **kwargs):
    resp = _orig_template_response(request, *args, **kwargs)
    tid = getattr(request.state, "set_thesis_cookie", None)
    if tid:
        resp.set_cookie(store.COOKIE, tid, max_age=COOKIE_MAX_AGE, path="/", samesite="lax", httponly=True)
    return resp


templates.TemplateResponse = _template_response


def sources(conn, adapter_names: list[str]) -> list[dict]:
    rows = []
    for name in adapter_names:
        n, last = (0, None)
        if conn is not None:
            n, last = conn.execute("SELECT COUNT(*), MAX(fetched_at) FROM signals WHERE adapter = ?", (name,)).fetchone()
        note = None
        if name == "businessfinland" and (not n or not (ROOT / BF_EXPORT).is_file()):
            note = f"awaiting export ({BF_EXPORT} not present)"
        rows.append({"name": name, "label": store.SOURCE_LABELS.get(name, name), "signals": n,
                     "last_fetched": (last or "")[:10] or None, "note": note})
    return rows


@router.get("/method")
def method(request: Request):
    th, conn = store.context(request)
    try:
        from radar import build
        names = sorted({n for n, _ in build.discover()})
        src = sources(conn, names)
        counts = store.feed_counts(conn, th) if conn is not None else None
        eco = matching.dataset_summary(conn) if conn is not None else None
    finally:
        if conn is not None:
            conn.close()
    declared = sorted(f.name for f in (ROOT / "data" / "declared").glob("*") if f.is_file())
    rule = [ln.strip() for ln in inspect.cleandoc(emit.__doc__).splitlines()]
    geo = th["geography"]
    return templates.TemplateResponse(request, "method.html", {
        "thesis": th, "rule_lines": rule, "signal_types": emit.SIGNAL_TYPES, "feed_rule": store.rule_text(th), "match_rule": fit.MATCH_RULE, "own_text_sources": ", ".join(store.OWN_TEXT_SOURCES),
        "window_days": geo["feed_window_days"], "age_cut": geo.get("stage_max_company_age_years"),
        "counts": counts, "eco": eco, "partners": store.partner_orgs(), "reasons": [(r, store.REASON_MEANING[r]) for r in store.REASON_IDS],
        "declared": declared, "sources": src, "no_db": conn is None, "connectors": CONNECTOR_SLOTS, "fw": frameworks.assess({}, []),
        "active": "method", "has_route": _has_route(request)})
