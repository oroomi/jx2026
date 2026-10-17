"""Unknown /api paths answer a JSON 404 that lists the endpoints. Registered after every other API module (modules load in name order, and
this one starts with zz), so a module added later, such as radar/routes/ask.py (GET /api/ask), is never shadowed by the catch-all."""
from __future__ import annotations

from fastapi import APIRouter

from radar.routes.api import ENDPOINTS, _error

router = APIRouter()


@router.get("/api/{rest:path}", include_in_schema=False)
def api_not_found(rest: str):
    return _error(404, f"no API endpoint /api/{rest}", endpoints=ENDPOINTS)
