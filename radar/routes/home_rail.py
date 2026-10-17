"""The home list's filters. `GET /home/list` is the list section alone (templates/_home_list.html), what htmx swaps in when a filter, a group
tab, a country link, a chip, Clear all or an Ask answer changes the state; "/" renders the same section inside the page. Both read the
state the same way (radar.home_filter.parse_state) from the same query, so a refresh or a shared URL renders the view a click produced.

It replaces the `home_list_for` template global registered by radar/routes/home_list.py (imported first, so this assignment wins) with one
that also reads the request's querystring: the cached rows (radar.home_list, built once per cache warm) are filtered here, per request,
by radar.home_filter, and the rail's option counts come back with them. feed.html is not told anything new; it keeps asking for the list."""
from __future__ import annotations

from fastapi import APIRouter, Request
from jinja2 import pass_context

from radar import home_filter, home_list, home_orgs, store, thesis as thesis_mod
from radar.routes import home_list as _registers_first  # noqa: F401  (its template globals must exist before this module overrides one)
from radar.routes.home import templates

router = APIRouter()


def sectors_for(current: dict, current_data: dict) -> list[dict]:
    """The configured theses for the Sector group: id, title, how many rows its list has and which filter values and groups it offers.
    Another sector's list is only read from the cache (never built here): when it is not cached yet its rows and filters are unknown, and
    choosing it carries no filter over."""
    out = []
    for tid, path in thesis_mod.available().items():
        th = current if tid == current["id"] else thesis_mod.load(path)
        data = current_data if tid == current["id"] else home_list.peek(th)
        rows = data.get("rows") if data and not data.get("warming") else None
        out.append({"id": tid, "title": th["title"], "rows": len(rows) if rows is not None else None,
                    "offered": home_filter.offered(rows), "groups": [g[0] for g in (data or {}).get("groups") or []] if rows is not None else None})
    return out


def sector_links(current: dict) -> list[dict]:
    """The configured sectors as plain links, for the page that has no list to filter yet (no store for this sector, or a search result)."""
    return [{"id": tid, "title": home_filter.short_title(thesis_mod.load(path)["title"]), "on": tid == current["id"], "href": f"/?thesis={tid}"}
            for tid, path in thesis_mod.available().items()]


templates.env.globals["sector_links"] = sector_links


def filtered_view(request: Request, thesis: dict) -> dict | None:
    """The cached home list for this thesis with the request's state applied (None when the sector has no store; a list still being
    built comes back as {"warming": True, "rows": []})."""
    data = home_list.for_template(thesis)
    if not data or not data.get("rows"):
        return data
    st = home_filter.parse_state(request.query_params)
    return home_filter.view(data, st, sectors=sectors_for(thesis, data), current=thesis["id"], title=thesis["title"], match=home_orgs.context(thesis, st.org))


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


def _warm_orgs() -> None:
    """After the sectors' lists are built, build the Top matching picker and the default organisation's ranking of every sector that has
    matchmaking, so the tab's first visitor does not wait for the matchmaker (about 1.5 s)."""
    try:
        default = thesis_mod.load()
        todo = [default] + [t for t in (thesis_mod.load(p) for p in thesis_mod.available().values()) if t["id"] != default["id"]]
    except Exception:  # noqa: BLE001
        return
    for th in todo:
        try:
            home_list.warm(th)
            home_orgs.warm(th)
        except Exception:  # noqa: BLE001  (a warm-up failure only means that sector builds on its first request)
            pass


if __import__("os").environ.get("RADAR_NO_WARM") is None and "pytest" not in __import__("sys").modules:
    import threading
    threading.Thread(target=_warm_orgs, name="home-orgs-warm", daemon=True).start()
