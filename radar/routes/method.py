"""GET /method : the rules printed in full, the sources table and the connector slots.
Also owns two cross-page hooks: the thesis switcher helpers for base.html and the radar_thesis cookie."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from radar import emit, fit, frameworks, labels, intake as intake_mod, matching, store, thesis as thesis_mod
from radar.routes.home import ROOT, _has_route, templates

router = APIRouter()

CONNECTOR_SLOTS = ("LinkedIn", "Dealroom", "Tracxn", "PitchBook", "Crunchbase")
BF_EXPORT = "data/declared/businessfinland.xlsx"
COOKIE_MAX_AGE = 86400


def _current_thesis(request) -> dict:
    th = getattr(getattr(request, "state", None), "thesis", None)
    return th if th is not None else thesis_mod.load()


def _country_info(th: dict) -> dict:
    """Active countries and the depth we hold for each, for the header, the feed note and /method."""
    depth = thesis_mod.country_depth(th)
    eu_only = [c for c, d in depth.items() if d == thesis_mod.DEFAULT_DEPTH]
    national = [(c, d) for c, d in depth.items() if d != thesis_mod.DEFAULT_DEPTH]
    note = "; ".join(f"{c} {d}" for c, d in national)
    if eu_only:
        note += ("; " if note else "") + f"{', '.join(eu_only)} {thesis_mod.DEFAULT_DEPTH}"
    return {"codes": list(depth), "multi": len(depth) > 1, "depth": list(depth.items()), "eu_only": eu_only, "note": note}


templates.env.globals["country_info"] = _country_info
templates.env.globals["current_thesis"] = _current_thesis

# store.context() records a valid ?thesis= choice on request.state; the cookie is attached when the page renders.
_orig_template_response = templates.TemplateResponse


def _template_response(request, *args, **kwargs):
    resp = _orig_template_response(request, *args, **kwargs)
    tid = getattr(request.state, "set_thesis_cookie", None)
    if tid:
        resp.set_cookie(store.COOKIE, tid, max_age=COOKIE_MAX_AGE, path="/", samesite="lax", httponly=True)
    return resp


templates.TemplateResponse = _template_response


SOURCE_NAMES = {
    "prh": "PRH/YTJ company register", "prh_notices": "PRH registered notices (share issues, board changes)",
    "hilma": "Hilma public contracts", "businessfinland": "Business Finland funding export", "cordis": "CORDIS EU projects",
    "blueinvest": "BlueInvest pipeline", "declared": "Declared cohort and portfolio list",
}
DATASET_NAMES = {
    "cohort_portfolio_companies.csv": "Cohort and portfolio company list", "corporates_clients.csv": "Corporate buyers list",
    "investors.csv": "Investor list", "programmes_grants.csv": "Programmes and grants list",
    "startups_universe.csv": "Startup universe list", "businessfinland.xlsx": "Business Finland funding export",
}


def _table_count(conn, sql: str) -> int | None:
    try:
        return conn.execute(sql).fetchone()[0]
    except Exception:
        return None


def sources(conn, adapter_names: list[str]) -> list[dict]:
    """One plain sentence per source, from counts in the database. A source with nothing says it is not loaded in this build."""
    rows = []
    for name in adapter_names:
        n, last = (0, None)
        if conn is not None:
            n, last = conn.execute("SELECT COUNT(*), MAX(fetched_at) FROM signals WHERE adapter = ?", (name,)).fetchone()
        extra = None
        if conn is not None and name == "blueinvest":
            k = _table_count(conn, "SELECT COUNT(*) FROM blueinvest_profiles")
            extra = f"{k} Finnish profiles, no dated events" if k else None
        elif conn is not None and name == "declared":
            k = _table_count(conn, "SELECT COUNT(*) FROM companies WHERE group_tag IN ('cohort','portfolio')")
            extra = f"{k} declared companies, no dated events" if k else None
        if n:
            text = f"{n} signal{'s' if n != 1 else ''}"
            if extra:
                text = f"{extra}; {text}"
        elif extra:
            text = extra
        else:
            text = "not loaded in this build"
        rows.append({"name": name, "label": SOURCE_NAMES.get(name) or labels.source_label(name), "signals": n,
                     "text": text, "last_fetched": (last or "")[:10] or None})
    return rows


def datasets() -> list[str]:
    files = sorted(f.name for f in (ROOT / "data" / "declared").glob("*") if f.is_file())
    return [DATASET_NAMES[f] for f in files if f in DATASET_NAMES]


@router.get("/method")
def method(request: Request):
    th, conn = store.context(request)
    try:
        from radar import build
        names = sorted({n for n, _ in build.discover()})
        src = sources(conn, names)
        counts = store.feed_counts(conn, th) if conn is not None else None
        # The home page lists the main matches AND the declared cohort and portfolio companies; /method names both parts (D41).
        declared_n = conn.execute("SELECT COUNT(*) FROM companies WHERE group_tag IN ('cohort','portfolio')").fetchone()[0] if conn is not None else 0
        eco = matching.dataset_summary(conn) if conn is not None else None
    finally:
        if conn is not None:
            conn.close()
    declared = datasets()
    kinds = [labels.signal_label(t) for t in emit.SIGNAL_TYPES]
    geo = th["geography"]
    return templates.TemplateResponse(request, "method.html", {
        "thesis": th, "confidence_rules": store.CONFIDENCE_RULES, "kinds": kinds, "feed_rule": store.rule_text(th), "corroboration_rule": store.CORROBORATION_RULE, "match_rule": fit.MATCH_RULE, "own_text_sources": ", ".join(store.OWN_TEXT_SOURCES),
        "window_days": geo["feed_window_days"], "age_cut": geo.get("stage_max_company_age_years"),
        "counts": counts, "declared_n": declared_n, "eco": eco, "partners": store.partner_orgs(), "reasons": [(r, store.REASON_MEANING[r]) for r in store.REASON_IDS],
        "declared": declared, "sources": src, "no_db": conn is None, "connectors": CONNECTOR_SLOTS, "fw": frameworks.assess({}, []),
        "intake_rule": intake_mod.rule_text(th), "intake_note": intake_mod.tuning_note(th),
        "active": "method", "has_route": _has_route(request)})
