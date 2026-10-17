"""The home list's filter rail. No URL of its own: "/" stays in feed.py and answers the same address with or without a filter.

It replaces the `home_list_for` template global registered by radar/routes/home_list.py (imported first, so this assignment wins) with
one that also reads the request's querystring: the cached rows (radar.home_list, built once per cache warm) are filtered here, per request,
by radar.home_filter, and the rail's option counts come back with them. feed.html is not told anything new; it keeps asking for the list."""
from __future__ import annotations

from fastapi import APIRouter, Request
from jinja2 import pass_context

from radar import home_filter, home_list, intake as intake_mod, store
from radar.routes import home_list as _registers_first  # noqa: F401  (its template globals must exist before this module overrides one)
from radar.routes.home import _has_route, templates

router = APIRouter()


@pass_context
def home_list_filtered(ctx, thesis: dict) -> dict | None:
    """The cached home list for this thesis with the request's filters applied, plus `rail` (the filter panel's data)."""
    data = home_list.for_template(thesis)
    request = ctx.get("request")
    if not data or request is None:
        return data
    return home_filter.view(data, request.query_params)


templates.env.globals["home_list_for"] = home_list_filtered


@router.get("/home/list")
def home_list_partial(request: Request):
    """What htmx asks for when a filter option is followed: feed.html with the filters applied but WITHOUT the feed's own query (the 120
    record rows and the 300-row intake tier, about two seconds of the full page), because htmx keeps only the .hc section. The address bar
    still shows "/?...", which is the full page. tests/test_criteria_filters.py checks both return the same .hc section."""
    th, conn = store.context(request)
    if conn is not None:
        conn.close()
    ctx = {"thesis": th, "rows": [], "main_rows": [], "weak_rows": [], "counts": None, "pills": [], "selected": None, "total": 0,
           "selected_label": None, "rule": store.rule_text(th), "no_db": conn is None, "truncated": False, "matches": None, "q": None,
           "active": "feed", "has_route": _has_route(request), "intake_rows": [], "intake_rule": intake_mod.rule_text(th)}
    return templates.TemplateResponse(request, "feed.html", ctx)
