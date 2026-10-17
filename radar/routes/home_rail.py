"""The home list's filters. `GET /home/list` is the list section alone (templates/_home_list.html), what htmx swaps in when a filter, a group
tab, a country link, a chip, Clear all or an Ask answer changes the state; "/" renders the same section inside the page. Both read the
state the same way (radar.home_filter.parse_state) from the same query, so a refresh or a shared URL renders the view a click produced.

It replaces the `home_list_for` template global registered by radar/routes/home_list.py (imported first, so this assignment wins) with one
that also reads the request's querystring: the cached rows (radar.home_list, built once per cache warm) are filtered here, per request,
by radar.home_filter, and the rail's option counts come back with them. feed.html is not told anything new; it keeps asking for the list."""
from __future__ import annotations

from fastapi import APIRouter, Request
from jinja2 import pass_context

from radar import home_filter, home_list, store
from radar.routes import home_list as _registers_first  # noqa: F401  (its template globals must exist before this module overrides one)
from radar.routes.home import templates

router = APIRouter()


def filtered_view(request: Request, thesis: dict) -> dict | None:
    """The cached home list for this thesis with the request's state applied (None when the sector has no store; a list still being
    built comes back as {"warming": True, "rows": []})."""
    data = home_list.for_template(thesis)
    if not data or not data.get("rows"):
        return data
    return home_filter.view(data, home_filter.parse_state(request.query_params))


@pass_context
def home_list_filtered(ctx, thesis: dict) -> dict | None:
    request = ctx.get("request")
    return home_list.for_template(thesis) if request is None else filtered_view(request, thesis)


templates.env.globals["home_list_for"] = home_list_filtered


@router.get("/home/list")
def home_list_partial(request: Request):
    """The list section alone, for an in-place swap. The response carries the canonical URL of the state in `HX-Replace-Url`, which htmx
    writes to the address bar with history.replaceState (never a new history entry), and the count line for the live region."""
    th, conn = store.context(request)
    if conn is not None:
        conn.close()
    H = filtered_view(request, th) if conn is not None else None
    ok = bool(H and H.get("rail"))
    resp = templates.TemplateResponse(request, "_home_partial.html" if ok else "_home_none.html", {"thesis": th, "H": H})
    resp.headers["Cache-Control"] = "no-store"
    if ok:
        resp.headers["HX-Replace-Url"] = H["state"].url
    return resp
