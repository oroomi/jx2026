"""Company life-line: every stored signal as a dot on one dated line from founding to today, grouped by stage.
Pure functions over rows already read by radar.store; the median reads company_traction through a Connection."""
from __future__ import annotations

import sqlite3
import statistics
from datetime import date

STAGES = (("formation", "Formation"), ("first_money", "First money"), ("first_team", "First team"), ("validation", "Validation"))
STAGE_OF = {
    "register_entry": "formation", "research_output": "formation", "website_first_seen": "formation", "patent": "formation",
    "blueinvest": "formation",
    "first_sales": "first_money", "sales_ended": "first_money", "bf_funding": "first_money",
    "first_hire": "first_team", "employer_ended": "first_team", "job_ad": "first_team",
    "public_contract": "validation", "eu_project": "validation", "website_milestone": "validation", "site_customer": "validation",
}
NEGATIVE = ("sales_ended", "employer_ended")
MIN_SAMPLE = 30


def build(company: dict, signals: list[dict], today: date | str | None = None) -> dict:
    """{start, end, lanes: [{id, label, dots: [...]}]}. Dots are ordered by date; left is 0-100 along the axis.
    The axis starts at the founding date, or at the earliest signal when that is earlier (research can predate the company).
    Returns {} when there is nothing to draw."""
    end = date.fromisoformat(today) if isinstance(today, str) else (today or date.today())
    days = [s["date"] for s in signals if s.get("date")]
    if company.get("founded"):
        days.append(company["founded"])
    if not days:
        return {}
    start = date.fromisoformat(min(days))
    end = max(end, date.fromisoformat(max(days)))
    span = max((end - start).days, 1)
    lanes = {sid: {"id": sid, "label": label, "dots": []} for sid, label in STAGES}
    for s in sorted(signals, key=lambda s: (s["date"], s.get("id") or 0)):
        left = round((date.fromisoformat(s["date"]) - start).days / span * 100, 2)
        lanes[STAGE_OF.get(s["signal_type"], "validation")]["dots"].append({
            "left": left, "date": s["date"], "date_label": s.get("date_label") or s["date"], "label": s.get("type_label") or s["signal_type"],
            "url": s["source_url"], "negative": s["signal_type"] in NEGATIVE, "detail": s.get("detail"),
            "title": f"{s.get('type_label') or s['signal_type']}, {s.get('date_label') or s['date']}"})
    return {"start": start.isoformat(), "end": end.isoformat(), "founded_left": round((date.fromisoformat(company["founded"]) - start).days / span * 100, 2)
            if company.get("founded") else None, "lanes": list(lanes.values())}


def median_months(conn: sqlite3.Connection, year: str) -> tuple[float | None, int]:
    """(median months to first hire, sample size) over stored companies founded in `year` that have a first hire.
    The median is None when the sample is under MIN_SAMPLE. A database without company_traction gives (None, 0)."""
    try:
        vals = [r[0] for r in conn.execute(
            "SELECT months_to_first_hire FROM company_traction WHERE substr(founded,1,4)=? AND months_to_first_hire IS NOT NULL", (year,))]
    except sqlite3.OperationalError:
        return None, 0
    return (statistics.median(vals) if len(vals) >= MIN_SAMPLE else None), len(vals)


def speed(conn: sqlite3.Connection, company_key: str, founded: str | None) -> dict:
    """The plain-words speed line facts for one company: months, year, median and sample size; every field None when unknown."""
    out = {"months": None, "year": founded[:4] if founded else None, "median": None, "sample": 0}
    try:
        row = conn.execute("SELECT months_to_first_hire FROM company_traction WHERE company_key=?", (company_key,)).fetchone()
    except sqlite3.OperationalError:
        return out
    if row is not None:
        out["months"] = row[0]
    if out["year"]:
        out["median"], out["sample"] = median_months(conn, out["year"])
    return out
