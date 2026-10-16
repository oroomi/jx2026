"""GET /backtest : the earliness backtest page. Data comes from radar.earliness; this module only lays out the SVG chart."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Request

from radar import earliness, store
from radar.routes.home import _has_route, templates
from radar.routes.method import CONNECTOR_SLOTS

router = APIRouter()

W, X0, X1 = 420, 12, 408          # viewBox width, track start and end
TOP, LANE_H = 34, 58              # axis band height, lane height


def _months_back(d: date, n: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    return date(y, m + 1, 1)


def chart(res: dict) -> dict:
    """Geometry for the inline SVG. One lane per company on a shared axis; blank lanes carry no marker."""
    ref = date.fromisoformat(res["reference_date"])
    firsts = [date.fromisoformat(r["first_signal"]["date"]) for r in res["rows"] if r["first_signal"]]
    lo = min([_months_back(ref, 12), *firsts])
    hi = _months_back(ref, -12)
    span = (hi - lo).days or 1

    def x(d: date) -> float:
        return round(X0 + (X1 - X0) * (d - lo).days / span, 1)

    lanes = []
    for i, r in enumerate(res["rows"]):
        y = TOP + i * LANE_H
        lane = {"key": r["company_key"], "name": r["name"], "y": y, "ty": y + 34, "blank": r["first_signal"] is None}
        f = r["first_signal"]
        if f:
            d = date.fromisoformat(f["date"])
            mx = x(d)
            mon = f"{d.strftime('%b')} {d.year}" if not f["year_only"] else f"{d.year}"
            lane.update(mx=mx, hollow=f["year_only"], anchor="end" if mx > W * 0.55 else "start",
                        label=f"{mon} / {f['label']}" + (" / year only" if f["year_only"] else ""))
            lane["lx"] = round(min(max(mx, X0 + 4), X1 - 4), 1)
        lanes.append(lane)
    ticks = [{"x": x(date(y, 1, 1)), "label": str(y)} for y in range(lo.year + (lo.month > 1 or lo.day > 1), hi.year + 1) if lo <= date(y, 1, 1) <= hi and x(date(y, 1, 1)) < X1 - 28]
    return {"w": W, "h": TOP + len(lanes) * LANE_H + 6, "x0": X0, "x1": X1, "top": TOP, "lanes": lanes, "ticks": ticks,
            "ref_x": x(ref), "ref_label": res["reference_date"], "ref_anchor": "end" if x(ref) > W * 0.6 else "start"}


@router.get("/backtest")
def backtest_page(request: Request):
    th, conn = store.context(request)
    res, ch, nc, rule = None, None, [], earliness.rule_lines(th)
    if conn is not None:
        try:
            res = earliness.backtest(conn, th)
            nc = earliness.not_connected(conn, th)
        finally:
            conn.close()
    if res is not None and res["total"] == 0:
        res = None
        reason = "this thesis has no cohort group, nothing to backtest"
    else:
        reason = None if res is not None else store.empty_state_text(th)
    if res is not None:
        ch = chart(res)
    return templates.TemplateResponse(request, "backtest.html", {
        "thesis": th, "res": res, "chart": ch, "rule": rule, "reason": reason, "not_connected": nc,
        "type_labels": store.TYPE_LABELS, "slots": CONNECTOR_SLOTS, "active": "backtest", "has_route": _has_route(request),
        "no_signal": [r for r in res["rows"] if r["group"] == "none"] if res else [],
    })
