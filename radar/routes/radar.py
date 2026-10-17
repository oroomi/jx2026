"""GET /radar : the cohort radar. Ranks companies by the number of distinct dated public events stored for them. No score."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Request

from radar import labels
from radar import blueinvest, store
from radar.routes.home import _has_route, templates
from radar.routes.method import CONNECTOR_SLOTS

router = APIRouter()

# Event types named in the printed rule. Low confidence (name keyword only) is never counted, as printed in store.CONFIDENCE_RULES.
EVENT_TYPES = ("register_entry", "bf_funding", "eu_project", "public_contract", "blueinvest", "patent", "job_ad")
SVG_W, SVG_X0, SVG_X1 = 120, 4, 116


def rule_text(thesis: dict) -> str:
    cut = (thesis.get("geography") or {}).get("stage_max_company_age_years")
    return ("Rank = the number of distinct dated public events in the database (register entry, Business Finland funding year, "
            "EU project start, public contract, BlueInvest listing date, patent, job ad). Equal counts: the most recent event first, "
            "then alphabetical. A year-only date counts as one event on 1 January of that year and is labelled. A register entry older "
            f"than the thesis's young-company cut ({cut} years, stage_max_company_age_years) still counts as an event here; the backtest "
            "page applies a stricter rule. A low confidence name-keyword match is never counted. No weighting, no score, no prediction.")


def _events(conn: sqlite3.Connection, key: str) -> list[dict]:
    q = ",".join("?" * len(EVENT_TYPES))
    rows = [dict(r) for r in conn.execute(
        f"SELECT id AS signal_id, signal_type, date, source_url, confidence, adapter, detail, fetched_at FROM signals "
        f"WHERE company_key=? AND signal_type IN ({q}) AND confidence != 'low' ORDER BY date DESC, id DESC", (key, *EVENT_TYPES))]
    store.with_precision(conn, rows)
    return rows


def _sort_key(r: dict):
    # count desc, latest date desc, name asc
    return (-r["event_count"], "".join(chr(255 - ord(ch)) for ch in (r["latest_date"] or "")), r["name"].casefold())


def _strip(events: list[dict], lo: date, hi: date) -> list[dict]:
    span = max((hi - lo).days, 1)
    out = []
    for e in events:
        d = date.fromisoformat(e["date"])
        out.append({"x": round(SVG_X0 + (SVG_X1 - SVG_X0) * (d - lo).days / span, 1), "hollow": e["date_precision"] == "year",
                    "title": f"{labels.signal_label(e['signal_type'])}, {e['date_label']}"})
    return out


def radar_rows(conn: sqlite3.Connection, thesis: dict, group: str) -> list[dict]:
    """One dict per company of the group: counts and latest event from stored signals only. Zero-event companies come last."""
    comps = conn.execute("SELECT company_key, name, country, group_tag, register_status FROM companies WHERE group_tag=?", (group,)).fetchall()
    rows = []
    for c in comps:
        if store.is_partner_org(c["name"]):
            continue
        ev = _events(conn, c["company_key"])
        latest = ev[0] if ev else None
        types = []
        for e in ev:
            if e["signal_type"] not in types:
                types.append(e["signal_type"])
        rows.append({
            "company_key": c["company_key"], "name": c["name"], "country": c["country"], "group_tag": c["group_tag"],
            "register_status": c["register_status"], "event_count": len(ev), "events": ev,
            "latest_date": latest["date"] if latest else None,
            "latest": None if latest is None else {
                "date_label": latest["date_label"], "type": latest["signal_type"],
                "type_label": labels.signal_label(latest["signal_type"]),
                "source_url": latest["source_url"], "confidence": latest["confidence"], "evidence": store.evidence(latest)},
            "types": [labels.signal_label(t) for t in types],
            "profile": blueinvest.profile_for(conn, c["company_key"]),
        })
    rows.sort(key=_sort_key)
    alld = [date.fromisoformat(e["date"]) for r in rows for e in r["events"]]
    if alld:
        lo, hi = min(alld), max(alld)
        for r in rows:
            r["strip"] = _strip(r["events"], lo, hi)
    return rows


@router.get("/radar")
def radar_page(request: Request):
    th, conn = store.context(request)
    cohort, portfolio = [], []
    if conn is not None:
        try:
            cohort, portfolio = radar_rows(conn, th, "cohort"), radar_rows(conn, th, "portfolio")
        finally:
            conn.close()
    if conn is None:
        reason = store.empty_state_text(th)
    elif not cohort and not portfolio:
        reason = "this thesis has no declared cohort"
    else:
        reason = None
    nonfi = sorted({r["country"] for r in cohort + portfolio if r["country"] and r["country"] != "FI"})
    return templates.TemplateResponse(request, "radar.html", {
        "thesis": th, "reason": reason, "rule": rule_text(th), "slots": CONNECTOR_SLOTS, "nonfi": nonfi,
        "blocks": [("cohort", "Cohort", cohort), ("portfolio", "Portfolio", portfolio)],
        "cohort": cohort, "cohort_with": sum(1 for r in cohort if r["event_count"]),
        "active": "radar", "has_route": _has_route(request)})
