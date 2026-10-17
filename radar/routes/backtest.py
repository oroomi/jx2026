"""GET /backtest : the earliness backtest page. Data comes from radar.earliness; this module only lays out the SVG chart."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Request

from radar import earliness, store
from radar.routes.home import _has_route, templates
from radar.routes.method import CONNECTOR_SLOTS

router = APIRouter()

W, NAME_W, X0, X1 = 680, 0, 200, 668   # viewBox width (drawn 1:1 on a desktop), name column start, track start and end
TOP, LANE_H, HEAD_H = 34, 34, 34        # axis band height, one compact lane, one group header
GROUPS = (("earlier", "Found earlier by live public records"), ("declared", "Found earlier only by declared research"),
          ("later", "Found later"), ("none", "No counted signal"))


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

    lanes, groups, y = [], [], TOP
    for gkey, glabel in GROUPS:  # lanes grouped as the four counts above the chart, each group under its own header
        rows = [r for r in res["rows"] if r.get("group") == gkey]
        if not rows:
            continue
        groups.append({"key": gkey, "label": glabel, "n": len(rows), "y": y + 22, "rule_y": y + 28, "lanes": []})
        y += HEAD_H
        for r in rows:
            lane = {"key": r["company_key"], "name": r["name"], "y": y, "ty": y + 17, "blank": r["first_signal"] is None, "group": gkey}
            n_file = len(r["others"])   # stored records that were not counted; a blank lane says how many are on file (D74)
            lane["blank_label"] = "no counted signal, " + (f"{n_file} record{'s' if n_file != 1 else ''} on file" if n_file else "no record on file")
            f = r["first_signal"]
            if f:
                d = date.fromisoformat(f["date"])
                mx = x(d)
                mon = f"{d.strftime('%b')} {d.year}" if not f["year_only"] else f"{d.year}"
                right = mx < X0 + (X1 - X0) * 0.55  # the label sits inline beside the marker, on the side with room
                lane.update(mx=mx, hollow=f["year_only"], anchor="start" if right else "end",
                            label=f"{mon} / {f['label']}" + (" / year only" if f["year_only"] else ""))
                lane["lx"] = round(mx + 10 if right else mx - 10, 1)
            lanes.append(lane)
            groups[-1]["lanes"].append(lane)
            y += LANE_H
    ticks = [{"x": x(date(y, 1, 1)), "label": str(y)} for y in range(lo.year + (lo.month > 1 or lo.day > 1), hi.year + 1) if lo <= date(y, 1, 1) <= hi and x(date(y, 1, 1)) < X1 - 28]
    return {"w": W, "h": y + 6, "x0": X0, "x1": X1, "name_x": NAME_W, "top": TOP, "lanes": lanes, "groups": groups, "ticks": ticks,
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
