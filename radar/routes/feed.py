"""GET / : the early-signal feed (screen 1). GET /feed/rows : htmx partial. GET /search : company lookup.
All data comes through radar.store; this module never opens the database or the thesis file itself."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from radar import intake as intake_mod, store, thesis as thesis_mod
from radar.routes.home import _has_route, templates

router = APIRouter()

ROW_LIMIT = 500
COUNTRY_NAMES = {"FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "EE": "Estonia", "IS": "Iceland"}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}
_BASIS = {"industry_code": "industry code", "line_of_business": "registered line of business",
          "own_text": "the source text", "corroborated_keyword": "company name plus a second source"}


def sure_text(r: dict) -> str:
    """The confidence word in plain language, built from the stored confidence and reasons only."""
    c = r["confidence"]
    if c == "high":
        return "high, the source names the company and states the date"
    if c == "medium":
        return "medium, matched on exact name or website, date stated by the source"
    basis = [_BASIS[x] for x in r.get("reasons", []) if x in _BASIS]
    return "low, matched on " + (" and ".join(basis[:2]) if basis else "company name") + " only"


def _view(request: Request, signal_type: str | None):
    """Everything the feed templates need. conn is None or empty -> empty state, never a populated look."""
    th, conn = store.context(request)
    types = list(th["feed_signal_types"])
    if signal_type not in types:
        signal_type = None
    rows, counts, matches, intake_rows = [], None, None, []
    if conn is not None:
        try:
            counts = store.feed_counts(conn, th)
            rows = store.feed(conn, th, signal_type=signal_type, limit=ROW_LIMIT)
            if signal_type is None:  # the third tier is part of the unfiltered feed only
                intake_rows = intake_mod.tier(conn, th, exclude={r["company_key"] for r in rows})
        finally:
            conn.close()
    for r in rows:
        r["sure_text"] = sure_text(r)
    by_type = (counts or {}).get("by_type", {})
    pills = [{"key": t, "label": store.TYPE_LABELS.get(t, t), "count": by_type.get(t, 0), "href": f"/?type={quote(t)}"} for t in types]
    total = (counts or {}).get("companies", 0)
    return {
        "thesis": th, "rows": rows, "main_rows": sorted((r for r in rows if r["strength"] == "strong"), key=lambda r: (_CONF_ORDER.get(r["confidence"], 3), -int(r["date"].replace("-", "")), r["name"])),
        "weak_rows": [r for r in rows if r["strength"] == "weak"], "counts": counts, "pills": pills, "selected": signal_type, "total": total,
        "selected_label": store.TYPE_LABELS.get(signal_type, signal_type) if signal_type else None,
        "rule": store.rule_text(th), "no_db": conn is None, "truncated": total > ROW_LIMIT and signal_type is None,
        "matches": matches, "q": None, "active": "feed", "has_route": _has_route(request),
        "intake_rows": intake_rows, "intake_rule": intake_mod.rule_text(th),
    }


@router.get("/")
def feed_page(request: Request, type: str | None = None):
    return templates.TemplateResponse(request, "feed.html", _view(request, type))


@router.get("/feed/rows")
def feed_rows(request: Request, type: str | None = None):
    return templates.TemplateResponse(request, "feed_rows.html", _view(request, type))


@router.get("/search")
def search(request: Request, q: str = ""):
    th, conn = store.context(request)
    hits = []
    if conn is not None:
        try:
            hits = store.search(conn, q)
        finally:
            conn.close()
    if len(hits) == 1:
        return RedirectResponse(f"/c/{quote(hits[0]['company_key'])}", status_code=302)
    ctx = _view(request, None)
    ctx["q"] = q.strip()
    ctx["matches"] = hits
    ctx["searching"] = True
    ctx["countries"] = ", ".join(COUNTRY_NAMES.get(c, c) for c in th["geography"].get("countries", [])) or "the active sector's countries"
    ctx["other_sectors"] = [(tid, thesis_mod.load(path)) for tid, path in thesis_mod.available().items() if tid != th["id"]]
    return templates.TemplateResponse(request, "feed.html", ctx)
