"""GET /how : redirects to /method (D73). The 60-second reading guide described a start page that no longer exists and showed screenshots of it;
the rules page is the one description of the current site, so /how keeps old links alive by sending them there, query string included.
Also a last-registered styled 404 for unknown paths and a styled 500 helper."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from radar.routes.home import _has_route, templates

router = APIRouter()


@router.get("/how")
def how(request: Request):
    qs = request.url.query
    return RedirectResponse("/method" + (f"?{qs}" if qs else ""), status_code=302)


def error_page(request: Request, status: int, heading: str, body: str):
    return templates.TemplateResponse(request, "error.html", {"active": "", "has_route": _has_route(request), "heading": heading, "body": body}, status_code=status)
