"""Registers brief_for() for the company_brief.html partial. No URL of its own; the design session decides where the box sits."""
from __future__ import annotations

from fastapi import APIRouter

from radar import briefs
from radar.routes.home import templates

router = APIRouter()
templates.env.globals["brief_for"] = briefs.brief_for
templates.env.globals["brief_one_liners"] = briefs.one_liners
