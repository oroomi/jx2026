"""GET /method : the rules printed in full. Skeleton: thesis identity and the confidence rule from emit.py."""
from __future__ import annotations

import inspect

from fastapi import APIRouter, Request

from radar import emit, thesis as thesis_mod
from radar.routes.home import templates

router = APIRouter()


@router.get("/method")
def method(request: Request):
    th = thesis_mod.load()
    rule = [ln.strip() for ln in inspect.cleandoc(emit.__doc__).splitlines()]
    return templates.TemplateResponse(request, "method.html", {"thesis": th, "rule_lines": rule, "signal_types": emit.SIGNAL_TYPES, "active": "method"})
