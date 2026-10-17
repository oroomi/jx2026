"""Weigh the reasons (PROJECT_RULES D90). The template function `match_weights()` behind radar/templates/_match_weights.html (one include
line in match.html, above a startup's counterparts), and GET /match/weights/rows, which returns the counterparts below the shown cut as the
same list rows, so a new order can bring one of them up. All logic is in radar.match_weights; this module only shapes the page and JSON."""
from __future__ import annotations

import sys

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from jinja2 import pass_context

from radar import match_weights as mw, matchmaker, matchtext, store
from radar.routes.home import templates

router = APIRouter()


@pass_context
def match_weights(ctx) -> dict | None:
    """The panel's data for the company view's result, or None (no panel). Never breaks the page."""
    try:
        res = ctx.get("result")
        if ctx.get("view") != "company" or not res:
            return None
        req = ctx.get("request")
        raw = req.query_params.get("w") if req is not None else None
        th = ctx.get("thesis")
        return mw.panel(res, th, raw) if th else None
    except Exception as e:  # a failed panel must not take the Match page down; the cause goes to the log
        print(f"match_weights: {type(e).__name__}: {e}", file=sys.stderr)
        return None


templates.env.globals["match_weights"] = match_weights


@router.get("/match/weights/rows")
def weights_rows(request: Request, company: str, skip: int = Query(0, ge=0, le=1000)):
    """The listed counterparts after the first `skip`, each as the Match page's list row (same macros), in the server's order."""
    th, conn = store.context(request)
    if conn is None or matchtext.config(th) is None:
        if conn is not None:
            conn.close()
        return JSONResponse({"rows": [], "error": "matchmaking is not set up for this sector"}, status_code=404)
    try:
        res = matchmaker.match_company(company, th, conn=conn, limit=1000)
    finally:
        conn.close()
    if res is None:
        return JSONResponse({"rows": [], "error": f"no company with key {company} in this radar"}, status_code=404)
    row = templates.env.get_template("_match_weights_rows.html").module.row
    return {"listed": res["listed"], "rows": [{"id": r["id"], "rank": r["rank"], "html": str(row(r))} for r in res["counterparts"][skip:]]}
