"""Registers home_list_for() for the design C home view in feed.html. No URL of its own: "/" stays in feed.py."""
from __future__ import annotations

from fastapi import APIRouter

from radar import home_list, thesis as thesis_mod
from radar.routes.home import templates

router = APIRouter()
templates.env.globals["home_list_for"] = home_list.for_template
if __import__("os").environ.get("RADAR_NO_WARM") is None:
    try:
        home_list.warm(thesis_mod.load())
    except Exception:  # noqa: BLE001  (no store yet: the page shows the existing empty state)
        pass
