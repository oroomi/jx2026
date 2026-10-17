"""GET /api/ask?q=&thesis= : the answer behind the home page's "Ask Aava" bar -> {intent, say, url, action, label, segments, audio_dir, items, count, total}.
Deterministic: rules over the question's words (radar.ask, vocabulary in the thesis file's `ask:` block), the cached home list and the Aava scripts;
no model and no network call. Also registers the template globals the bar reads (`ask_examples`, `has_route`)."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from radar import ask, store
from radar.routes.aava import _inputs
from radar.routes.home import _has_route, templates

router = APIRouter()
templates.env.globals["ask_examples"] = ask.examples


@router.get("/api/ask")
def ask_api(request: Request, q: str = Query("", max_length=400), thesis: str | None = None):
    th, conn = store.context(request)
    try:
        out = ask.resolve(q, th, conn, inputs=_inputs, has_match=_has_route(request)("/match"), thesis_id=th["id"] if thesis else None)
    finally:
        if conn is not None:
            conn.close()
    return JSONResponse(out, headers={"Cache-Control": "no-store"})
