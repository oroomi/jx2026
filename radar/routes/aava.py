"""GET /aava/script/{company_key}?intent=brief|next|talk and GET /aava/feed: the narration scripts. Data only through radar.store."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from radar import aava, blueinvest, fit as fit_mod, frameworks, store
from radar.routes.company import blueinvest_trl

router = APIRouter()


@router.get("/aava/feed")
def feed_script(request: Request):
    th, conn = store.context(request)
    rows = []
    if conn is not None:
        try:
            rows = store.feed(conn, th, limit=50)
        finally:
            conn.close()
    return aava.feed_script([r for r in rows if r["strength"] == "strong"])


@router.get("/aava/script/{company_key:path}")
def company_script(request: Request, company_key: str, intent: str = "brief"):
    if intent not in aava.INTENTS:
        raise HTTPException(400, f"intent must be one of {', '.join(aava.INTENTS)}")
    th, conn = store.context(request)
    if conn is None:
        raise HTTPException(503, store.NO_DB_MESSAGE)
    try:
        data = store.company(conn, company_key)
        profile = blueinvest.profile_for(conn, company_key) if data else None
    finally:
        conn.close()
    if data is None:
        raise HTTPException(404, f"no company with key {company_key} in this radar")
    c, sigs = data["company"], data["signals"]
    fw = frameworks.assess(c, sigs)
    if profile and profile.get("trl") is not None:
        fw["trl"] = blueinvest_trl(profile)
    entered = ", ".join(sorted({s["evidence"]["label"] for s in sigs}) or [store.evidence(c)["label"]])
    return aava.company_script(c, sigs, fw, fit_mod.fit(c, sigs, th), entered, intent)
