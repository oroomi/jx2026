"""Catch-all registered last (modules load in name order): unknown GET paths get a styled plain-words 404, not a bare JSON body."""
from __future__ import annotations

from fastapi import APIRouter, Request

from radar.routes.how import error_page

router = APIRouter()


@router.get("/{path:path}", include_in_schema=False)
def not_found(request: Request, path: str):
    return error_page(request, 404, "This page does not exist.", "Use the start page to find a startup, or the search box below. Try the registered company name (ending in Oy).")
