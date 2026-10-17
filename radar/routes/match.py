"""Matchmaking. GET /match (page), GET /api/match/company/{key}, GET /api/match/org/{id}, GET /api/match/orgs, and the template
function `match_next(company_key)` behind the company page's "Next steps" block. All logic is in radar.matchmaker; this module only
shapes pages and JSON. Companies and organisations only."""
from __future__ import annotations

import sys
import threading

from fastapi import APIRouter, Query, Request
from jinja2 import pass_context

from radar import matchmaker, matchtext, store, thesis as thesis_mod
from radar.routes.api import _head, _open, _run, _thesis, _Fail
from radar.routes.home import _has_route, templates

router = APIRouter()
FEATURED_GROUPS = ("cohort", "portfolio")


def _cfg_or_fail(th: dict) -> dict:
    cfg = matchtext.config(th)
    if cfg is None:
        raise _Fail(404, {"error": f"matchmaking is not configured for the thesis {th['id']!r} (matching: weights, kinds, keyword_groups)", "thesis": th["id"]})
    return cfg


@router.get("/api/match/company/{company_key:path}")
def api_match_company(company_key: str, thesis: str | None = None, limit: int = Query(10, ge=1, le=50)):
    def body():
        th = _thesis(thesis)
        _cfg_or_fail(th)
        conn = _open(th)
        try:
            res = matchmaker.match_company(company_key, th, conn=conn, limit=limit)
        finally:
            conn.close()
        if res is None:
            raise _Fail(404, {"error": f"no company with key {company_key} in this radar, or it is not matchable", "thesis": th["id"]})
        return {"thesis": _head(th), **res}
    return _run(body)


@router.get("/api/match/org/{org_id}")
def api_match_org(org_id: str, thesis: str | None = None, limit: int | None = Query(None, ge=1, le=1000)):
    def body():
        th = _thesis(thesis)
        _cfg_or_fail(th)
        conn = _open(th)
        try:
            res = matchmaker.match_org(org_id, th, conn=conn, limit=limit)
        finally:
            conn.close()
        if res is None:
            raise _Fail(404, {"error": f"no counterpart with id {org_id}", "thesis": th["id"], "list": "/api/match/orgs"})
        return {"thesis": _head(th), **res}
    return _run(body)


@router.get("/api/match/orgs")
def api_match_orgs(thesis: str | None = None):
    def body():
        th = _thesis(thesis)
        _cfg_or_fail(th)
        conn = _open(th)
        try:
            rows = matchmaker.org_list(th, conn=conn)
        finally:
            conn.close()
        return {"thesis": _head(th), "count": len(rows), "orgs": rows}
    return _run(body)


@pass_context
def match_next(ctx, company_key: str) -> dict | None:
    """Template hook for _match_next.html: the top three counterparts for the company, or None (no block). Never breaks the page."""
    try:
        th = ctx.get("thesis") or thesis_mod.load()
        res = matchmaker.match_company(company_key, th, limit=3)
    except Exception as e:  # a failed block must not take the company page down; the cause goes to the log
        print(f"match_next({company_key}): {type(e).__name__}: {e}", file=sys.stderr)
        return None
    return res


templates.env.globals["match_next"] = match_next


def _page(request: Request, **ctx):
    ctx.update(active="match", has_route=_has_route(request))
    return templates.TemplateResponse(request, "match.html", ctx)


@router.get("/match")
def match_page(request: Request, view: str = "org", org: str = "", company: str = "", q: str = "", kind: str = "", tab: str = ""):
    th, conn = store.context(request)
    cfg = matchtext.config(th)
    if conn is None or cfg is None:
        msg = store.empty_state_text(th) if conn is None else f"Matchmaking is not set up for the sector '{th['title']}': its thesis file has no matching weights, kinds or keyword groups."
        return _page(request, view=view, message=msg, thesis=th)
    try:
        view = "company" if (view == "company" or company or q) else "org"
        orgs = matchmaker.org_list(th, conn=conn)
        kinds = [{"key": k, "label": v["label"], "n": sum(1 for o in orgs if o["kind"] == k)} for k, v in cfg["kinds"].items()]
        kinds = [k for k in kinds if k["n"]]
        shown = [o for o in orgs if not kind or o["kind"] == kind]
        ctx = dict(view=view, thesis=th, orgs=shown, org_total=len(orgs), kinds=kinds, kind=kind, q=q, message=None, rule=matchmaker.RULE,
                   weights=cfg["weights"], labels=matchmaker.LABELS, result=None, selected=None, companies=[], components=matchmaker.COMPONENTS,
                   tab="connected" if tab == "connected" else "fit")
        if view == "org":
            sel = org or max(orgs, key=lambda o: (o["members_in_records"], o["kind"] == "accelerator"))["id"]
            res = matchmaker.match_org(sel, th, conn=conn)         # the default limit is the one the home Top matching tab prints (matching.show_startups)
            ctx.update(selected=sel, result=res, not_found=res is None and bool(org))
        else:
            feat = [dict(r) for r in conn.execute(
                f"SELECT company_key, name, group_tag, country FROM companies WHERE group_tag IN ({','.join('?' * len(FEATURED_GROUPS))}) ORDER BY group_tag, name",
                FEATURED_GROUPS)]
            found = store.search(conn, q, 12) if q.strip() else []
            ctx.update(companies=found if q.strip() else feat, searched=bool(q.strip()), selected=company)
            if company:
                res = matchmaker.match_company(company, th, conn=conn, limit=12)
                ctx.update(result=res, not_found=res is None)
    finally:
        conn.close()
    return _page(request, **ctx)


def _warm() -> None:
    """Build the indexes once in the background so the first visitor does not wait for them."""
    try:
        th = thesis_mod.load()
        conn = store.open_db(thesis=th)
        if conn is None or matchtext.config(th) is None:
            return
        try:
            matchmaker.org_list(th, conn=conn)
            matchmaker.match_company("-", th, conn=conn, limit=1)   # an unknown key still builds both indexes
        finally:
            conn.close()
    except Exception as e:
        print(f"match warm-up: {type(e).__name__}: {e}", file=sys.stderr)


if "pytest" not in sys.modules:
    threading.Thread(target=_warm, name="match-warm", daemon=True).start()
