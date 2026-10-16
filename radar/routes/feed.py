"""GET / : the early-signal feed (screen 1). GET /feed/rows : htmx partial. GET /search : company lookup.
All data comes through radar.store; this module never opens the database or the thesis file itself."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from radar import store
from radar.routes.home import _has_route, templates

router = APIRouter()

ROW_LIMIT = 500


def _view(request: Request, signal_type: str | None):
    """Everything the feed templates need. conn is None or empty -> empty state, never a populated look."""
    th, conn = store.context(request)
    types = list(th["feed_signal_types"])
    if signal_type not in types:
        signal_type = None
    rows, counts, matches = [], None, None
    if conn is not None:
        try:
            counts = store.feed_counts(conn, th)
            rows = store.feed(conn, th, signal_type=signal_type, limit=ROW_LIMIT)
        finally:
            conn.close()
    by_type = (counts or {}).get("by_type", {})
    pills = [{"key": t, "label": store.TYPE_LABELS.get(t, t), "count": by_type.get(t, 0), "href": f"/?type={quote(t)}"} for t in types]
    total = (counts or {}).get("companies", 0)
    return {
        "thesis": th, "rows": rows, "counts": counts, "pills": pills, "selected": signal_type, "total": total,
        "selected_label": store.TYPE_LABELS.get(signal_type, signal_type) if signal_type else None,
        "rule": store.rule_text(th), "no_db": conn is None, "truncated": total > ROW_LIMIT and signal_type is None,
        "matches": matches, "q": None, "active": "feed", "has_route": _has_route(request),
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
    return templates.TemplateResponse(request, "feed.html", ctx)
