"""GET /how : the 60-second reading guide. Also a last-registered styled 404 for unknown paths and a styled 500 helper."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from radar.routes.home import _has_route, templates

router = APIRouter()


@router.get("/how")
def how(request: Request):
    return templates.TemplateResponse(request, "how.html", {"active": "how", "has_route": _has_route(request)})


def error_page(request: Request, status: int, heading: str, body: str):
    return templates.TemplateResponse(request, "error.html", {"active": "", "has_route": _has_route(request), "heading": heading, "body": body}, status_code=status)
