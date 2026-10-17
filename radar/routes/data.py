"""GET /data : the radar database as the pages see it (read-only), and POST /data/refresh : the guarded refresh button.
Only the radar tables companies and signals are shown, never the ecosystem tables; legal names shaped like a private person's name are hidden."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from radar import fit, refresh, store
from radar.routes.home import _has_route, templates

router = APIRouter()

PAGE_SIZE = 25
VIEWS = ("companies", "signals")


def _hidden_keys(conn, th: dict) -> list[str]:
    return [r[0] for r in conn.execute("SELECT company_key, name FROM companies") if fit.looks_like_person(r[1], th)]


def _visible(conn, th: dict) -> None:
    """A temp table of the person-shaped company keys, so SQL can leave them out (temp tables work on a read-only connection)."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS hidden_co (company_key TEXT PRIMARY KEY)")
    conn.execute("DELETE FROM hidden_co")
    conn.executemany("INSERT OR IGNORE INTO hidden_co VALUES (?)", [(k,) for k in _hidden_keys(conn, th)])


def source_rows(conn, today: str) -> list[dict]:
    """Per source (adapter): rows stored, companies, newest event date (not in the future) and last fetch."""
    rows = conn.execute(
        """SELECT adapter, COUNT(*) AS n, COUNT(DISTINCT company_key) AS cos,
                  MAX(CASE WHEN date <= ? THEN date END) AS newest, MAX(fetched_at) AS last_run
           FROM signals WHERE company_key NOT IN (SELECT company_key FROM hidden_co)
           GROUP BY adapter ORDER BY n DESC, adapter""", (today,)).fetchall()
    return [{"adapter": r["adapter"], "label": store.SOURCE_LABELS.get(r["adapter"], r["adapter"]), "rows": r["n"], "companies": r["cos"],
             "newest": r["newest"], "last_run": (r["last_run"] or "")[:16].replace("T", " ") or None} for r in rows]


def _where(view: str, source: str | None, typ: str | None) -> tuple[str, list]:
    cond, args = ["c.company_key NOT IN (SELECT company_key FROM hidden_co)"], []
    if view == "signals":
        if source:
            cond.append("s.adapter = ?")
            args.append(source)
        if typ:
            cond.append("s.signal_type = ?")
            args.append(typ)
    elif source:
        cond.append("c.company_key IN (SELECT company_key FROM signals WHERE adapter = ?)")
        args.append(source)
    return " AND ".join(cond), args


def table(conn, view: str, source: str | None, typ: str | None, page: int) -> dict:
    where, args = _where(view, source, typ)
    if view == "signals":
        total = conn.execute(f"SELECT COUNT(*) FROM signals s JOIN companies c USING (company_key) WHERE {where}", args).fetchone()[0]
        rows = conn.execute(
            f"""SELECT c.company_key, c.name, s.signal_type, s.date, s.confidence, s.adapter, s.source_url, s.detail
                FROM signals s JOIN companies c USING (company_key) WHERE {where}
                ORDER BY s.date DESC, s.id DESC LIMIT ? OFFSET ?""", [*args, PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
    else:
        total = conn.execute(f"SELECT COUNT(*) FROM companies c WHERE {where}", args).fetchone()[0]
        rows = conn.execute(
            f"""SELECT c.company_key, c.name, c.country, c.group_tag, c.founded, c.industry_code, c.industry_desc, c.source_url,
                       (SELECT COUNT(*) FROM signals s WHERE s.company_key = c.company_key) AS signals
                FROM companies c WHERE {where} ORDER BY c.name COLLATE NOCASE LIMIT ? OFFSET ?""",
            [*args, PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
    return {"total": total, "rows": [dict(r) for r in rows], "pages": max(1, -(-total // PAGE_SIZE))}


def _refresh_view(th: dict, now: datetime) -> dict:
    st = refresh.status(now)
    run = refresh.load_state().get("runs", {}).get(th["id"])
    return {"state": st, "run": run, "steps_configured": th.get("refresh_adapters") or [], "enabled": refresh.enabled(),
            "disabled_message": refresh.DISABLED_MESSAGE,
            "next_at": st["cooldown_until"].strftime("%H:%M") if st["cooldown_until"] else None,
            "cooldown_minutes": refresh.COOLDOWN_SECONDS // 60}


@router.get("/data")
def data_page(request: Request, view: str = "companies", source: str | None = None, type: str | None = None, page: int = 1, msg: str | None = None):
    th, conn = store.context(request)
    view = view if view in VIEWS else "companies"
    now = datetime.now(timezone.utc)
    ctx = {"thesis": th, "view": view, "source": source or "", "typ": type or "", "msg": msg, "active": "data", "has_route": _has_route(request),
           "no_db": conn is None, "refresh": _refresh_view(th, now), "sources": [], "tbl": None, "page": 1, "types": [], "totals": None,
           "pager": {}}
    if conn is not None:
        try:
            _visible(conn, th)
            ctx["sources"] = source_rows(conn, now.date().isoformat())
            ctx["types"] = [r[0] for r in conn.execute("SELECT DISTINCT signal_type FROM signals ORDER BY 1")]
            ctx["totals"] = {
                "companies": conn.execute("SELECT COUNT(*) FROM companies WHERE company_key NOT IN (SELECT company_key FROM hidden_co)").fetchone()[0],
                "signals": conn.execute("SELECT COUNT(*) FROM signals WHERE company_key NOT IN (SELECT company_key FROM hidden_co)").fetchone()[0],
                "hidden": conn.execute("SELECT COUNT(*) FROM hidden_co").fetchone()[0]}
            known_sources = {s["adapter"] for s in ctx["sources"]}
            src = source if source in known_sources else None
            typ = type if type in ctx["types"] else None
            page = max(1, page)
            tbl = table(conn, view, src, typ, page)
            if page > tbl["pages"]:
                page = tbl["pages"]
                tbl = table(conn, view, src, typ, page)
            ctx.update(tbl=tbl, page=page, source=src or "", typ=typ or "")
            base = {"view": view, **({"source": src} if src else {}), **({"type": typ} if typ else {})}
            ctx["pager"] = {"prev": "/data?" + urlencode({**base, "page": page - 1}) if page > 1 else None,
                            "next": "/data?" + urlencode({**base, "page": page + 1}) if page < tbl["pages"] else None}
            ctx["view_links"] = {v: "/data?" + urlencode({**base, "view": v, "page": 1}) for v in VIEWS}
        finally:
            conn.close()
    return templates.TemplateResponse(request, "data.html", ctx)


@router.post("/data/refresh")
def data_refresh(request: Request):
    if not refresh.enabled():
        return PlainTextResponse(refresh.DISABLED_MESSAGE, status_code=403)
    th, conn = store.context(request)
    if conn is not None:
        conn.close()
    ok, message = refresh.start_in_background(th)
    return RedirectResponse("/data?" + urlencode({"msg": message}) + "#refresh", status_code=303)
