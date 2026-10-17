"""Registers home_list_for() for the design C home view in feed.html. No URL of its own: "/" stays in feed.py."""
from __future__ import annotations

from fastapi import APIRouter

from radar import home_list
from radar.routes.home import templates

router = APIRouter()
templates.env.globals["home_list_for"] = home_list.for_template
templates.env.globals["lifeline_dots"] = home_list.dots
templates.env.globals["cohort_entry_for"] = home_list.cohort_entry
if __import__("os").environ.get("RADAR_NO_WARM") is None:
    home_list.warm_all()  # every thesis in config/, in one background thread
