"""GET /aava/script/{company_key}?intent=brief|why|meet|talk|next|missing and GET /aava/feed: the narration scripts (six questions per
company, one for the feed; the intent names are the old groups, see radar.aava). Data only through radar.store. The same scripts are
embedded in the page (template globals aava_company_json, aava_feed_json), so a tap plays them with no request: mobile browsers only
let speech start inside the tap itself."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from markupsafe import Markup

from radar import aava, matching, memo as memo_mod, store
from radar.routes.home import templates

router = APIRouter()


def _inputs(conn, th: dict, company_key: str) -> dict | None:
    """Everything a company script reads, from the functions the company page itself uses: question 03 (matching.who_comes_next),
    question 04 (matching.next_step) and the memo (memo.build)."""
    data = store.company(conn, company_key)
    if data is None:
        return None
    return {"c": data["company"], "signals": data["signals"],
            "nxt": matching.who_comes_next(company_key, th, 5, conn=conn), "step": matching.next_step(company_key, th, conn=conn),
            "memo": memo_mod.build(conn, th, company_key)}


def _json(obj) -> Markup:
    """JSON safe inside <script type="application/json">."""
    return Markup(json.dumps(obj, ensure_ascii=False).replace("</", "<\\/"))


def company_json(company_key: str, thesis: dict) -> Markup:
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return _json({})
    try:
        x = _inputs(conn, thesis, company_key)
    finally:
        conn.close()
    if x is None:
        return _json({})
    return _json(aava.company_groups(x["c"], x["signals"], nxt=x["nxt"], step=x["step"], memo=x["memo"], thesis=thesis))


def feed_reader(rows: list[dict], thesis: dict | None = None) -> dict:
    """The one reader of the feed: the strong rows, with the sector file's utility code families skipped (D22). The home page's embedded answer,
    GET /aava/feed and the Ask Aava bar's "what is new" all call this, so they say the same thing (D40)."""
    strong = [r for r in rows if r.get("strength") == "strong"]
    return aava.feed_script(strong, skip=aava.code_only_skip(thesis))


def feed_json(rows: list[dict], thesis: dict | None = None) -> Markup:
    """The reader's feed answer, embedded in the home page."""
    return _json({"brief": feed_reader(rows, thesis)["segments"]})


templates.env.globals["aava_company_json"] = company_json
templates.env.globals["aava_feed_json"] = feed_json
templates.env.globals["aava_questions"] = aava.QUESTIONS
templates.env.globals["aava_feed_questions"] = aava.FEED_QUESTIONS


@router.get("/aava/feed")
def feed_script(request: Request):
    th, conn = store.context(request)
    rows = []
    if conn is not None:
        try:
            rows = store.feed(conn, th, limit=50)
        finally:
            conn.close()
    return feed_reader(rows, th)


@router.get("/aava/script/{company_key:path}")
def company_script(request: Request, company_key: str, intent: str = "brief"):
    if intent not in aava.INTENTS:
        raise HTTPException(400, f"intent must be one of {', '.join(aava.INTENTS)}")
    th, conn = store.context(request)
    if conn is None:
        raise HTTPException(503, store.NO_DB_MESSAGE)
    try:
        x = _inputs(conn, th, company_key)
    finally:
        conn.close()
    if x is None:
        raise HTTPException(404, f"no company with key {company_key} in this radar")
    return aava.company_script(x["c"], x["signals"], intent, nxt=x["nxt"], step=x["step"], memo=x["memo"], thesis=th)
