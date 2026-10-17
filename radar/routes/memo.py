"""Registers the fund memo for the company page template (company_memo.html). No URL of its own: the memo is built from its own
read-only connection, so radar/routes/company.py needs no edit."""
from __future__ import annotations

from fastapi import APIRouter

from radar import memo
from radar.routes.home import templates

router = APIRouter()
templates.env.globals["memo_for"] = memo.for_template
