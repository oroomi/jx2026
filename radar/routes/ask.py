"""GET /api/ask?q=&thesis= : the answer behind the home page's "Ask Aava" bar -> {intent, say, url, action, label, segments, audio_dir, items, count, total}.
Deterministic: rules over the question's words (radar.ask, vocabulary in the thesis file's `ask:` block), the cached home list and the Aava scripts;
no model and no network call. Also registers the template globals the bar and the site menu read (`ask_examples`, `site_pages`)."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from radar import ask, store
from radar.routes import api as api_routes
from radar.routes.aava import _inputs, feed_reader
from radar.routes.home import templates

router = APIRouter()


def ask_examples(th: dict) -> list[str]:
    """The example chips: the thesis' example questions whose answer is not empty in this thesis' store (D40)."""
    conn = store.open_db(thesis=th)
    try:
        return ask.live_examples(th, conn)
    finally:
        if conn is not None:
            conn.close()


templates.env.globals["ask_examples"] = ask_examples
api_routes.ENDPOINTS.append({"path": "/api/ask?q=&thesis=", "what": "the answer behind the home page's Ask Aava bar: {intent, say, url, action}, deterministic, no model"})

def _paths(routes):
    """Every route path of the app, through the routers that include_router wraps (FastAPI 0.14x keeps them as objects without a `path`)."""
    for r in routes:
        if getattr(r, "path", None):
            yield r.path
        inner = getattr(r, "original_router", None)
        if inner is not None:
            yield from _paths(inner.routes)


def has_page(request: Request, path: str) -> bool:
    return path in set(_paths(request.app.routes))


# The pages the header's tab row used to list. The Menu sheet (header) and the footer both read this one list. A page whose route is not in
# this build (Match, from the matchmaking branch) is listed only when the route exists, so no link ever points at a missing page.
SITE_PAGES = (("/", "New this quarter", "feed", False), ("/radar", None, "radar", False), ("/match", "Match", "match", True),
              ("/backtest", "Earliness test", "backtest", False), ("/method", "Rules", "method", False), ("/data", "Data", "data", False))


def site_pages(request: Request, cur: dict) -> list[tuple[str, str, str]]:
    paths = set(_paths(request.app.routes))
    return [(href, label or cur.get("cohort_label") or "Cohort radar", key) for href, label, key, optional in SITE_PAGES if not optional or href in paths]


templates.env.globals["site_pages"] = site_pages


@router.get("/api/ask")
def ask_api(request: Request, q: str = Query("", max_length=400), thesis: str | None = None):
    th, conn = store.context(request)
    try:
        out = ask.resolve(q, th, conn, inputs=_inputs, has_match=has_page(request, "/match"), thesis_id=th["id"] if thesis else None,
                          feed_reader=feed_reader)
    finally:
        if conn is not None:
            conn.close()
    return JSONResponse(out, headers={"Cache-Control": "no-store"})
