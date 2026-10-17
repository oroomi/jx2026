"""Shared template environment and helpers for page routes. The feed itself is served by radar/routes/feed.py."""
from __future__ import annotations

import subprocess
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from radar import db, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=ROOT / "radar" / "templates")
router = APIRouter()


def _build_line() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        sha = ""
    return f"build {sha}" if sha else "build unknown"


BUILD = _build_line()
templates.env.globals["build_line"] = BUILD


def asset_version() -> str:
    """Cache-buster for /static links (the edge caches static files for hours)."""
    return str(int(max((f.stat().st_mtime for f in (ROOT / "radar" / "static").rglob("*") if f.is_file()), default=0)))


templates.env.globals["asset_v"] = asset_version()

from radar import labels as _labels  # noqa: E402

templates.env.filters["signal_label"] = _labels.signal_label
templates.env.filters["source_label"] = _labels.source_label
templates.env.filters["plain"] = _labels.plain
templates.env.filters["origin_label"] = _labels.origin_label
templates.env.filters["plain_text"] = _labels.plain_text


def feed_rows(conn, th: dict) -> list[dict]:
    """First feed-type signal per company, inside the window, newest first."""
    types = th["feed_signal_types"]
    since = (date.today() - timedelta(days=th["geography"]["feed_window_days"])).isoformat()
    if not types:
        return []
    q = ",".join("?" * len(types))
    rows = conn.execute(
        f"""SELECT c.company_key, c.name, s.signal_type, s.date, s.source_url, s.confidence
            FROM signals s JOIN companies c USING (company_key)
            WHERE s.signal_type IN ({q})
              AND s.date = (SELECT MIN(date) FROM signals s2 WHERE s2.company_key = s.company_key AND s2.signal_type IN ({q}))
              AND s.date >= ?
            GROUP BY c.company_key ORDER BY s.date DESC, c.name""",
        [*types, *types, since],
    ).fetchall()
    return [dict(r) for r in rows]


def _has_route(request: Request):
    return lambda path: any(getattr(r, "path", None) == path for r in request.app.routes)
