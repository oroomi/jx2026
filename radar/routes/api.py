"""Read-only JSON API over the same stores the pages read: GET /api, /api/companies, /api/company/{key}, /api/feed, /api/backtest.
No auth, no CORS, no writes. Listings leave out legal names shaped like a person's name (companies only). The thesis comes only from the `thesis` query parameter (an id from config/thesis*.yaml), never a cookie.
Data only through radar.store, radar.frameworks, radar.earliness and radar.matching; this module only shapes JSON."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from radar import blueinvest, earliness, fit as fit_mod, frameworks, matching, store, thesis as thesis_mod
from radar.routes.company import CONNECTORS, ecosystem as eco_reading

router = APIRouter(prefix="/api")

ENDPOINTS = [
    {"path": "/api/companies?q=&thesis=&limit=&offset=", "what": "search companies by name, key or Y-tunnus; no q lists all by name"},
    {"path": "/api/company/{company_key}?thesis=&limit=", "what": "register facts, signals with sources, readiness levels, who comes next, next step"},
    {"path": "/api/feed?thesis=&window=&type=", "what": "the early-signal feed rows with their reason; window = days (default from the thesis)"},
    {"path": "/api/backtest?thesis=", "what": "the earliness backtest per cohort company"},
]


class _Fail(Exception):
    def __init__(self, status: int, body: dict):
        self.status, self.body = status, body


def _error(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


def _thesis(thesis_id: str | None) -> dict:
    av = thesis_mod.available()
    if thesis_id and thesis_id not in av:
        raise _Fail(400, {"error": f"unknown thesis {thesis_id!r}", "available": sorted(av)})
    return thesis_mod.load(av[thesis_id] if thesis_id else None)


def _open(th: dict):
    conn = store.open_db(thesis=th)
    if conn is None:
        raise _Fail(503, {"error": store.empty_state_text(th), "thesis": th["id"]})
    return conn


def _head(th: dict) -> dict:
    return {"id": th["id"], "title": th["title"]}


def _signal(s: dict) -> dict:
    ev = s.get("evidence") or store.evidence(s)
    return {"id": s.get("id", s.get("signal_id")), "signal_type": s["signal_type"],
            "type_label": store.TYPE_LABELS.get(s["signal_type"], s["signal_type"]), "date": s["date"],
            "date_label": s.get("date_label") or ev["date_label"], "date_precision": s.get("date_precision") or ev["date_precision"],
            "confidence": s["confidence"], "confidence_rule": store.CONFIDENCE_RULES.get(s["confidence"]), "detail": s.get("detail"),
            "amount_eur": s.get("amount_eur"), "source_url": s["source_url"], "source_label": ev["label"], "adapter": s.get("adapter"),
            "fetched_at": s.get("fetched_at")}


def _level(name: str, lv: dict, rules: list[dict], url: str | None) -> dict:
    ev = []
    for s in lv.get("evidence") or []:
        e = s.get("evidence") or {}
        ev.append({"signal_id": s.get("id"), "date": e.get("date_label") or s.get("date"), "source_url": e.get("url") or s.get("source_url"),
                   "source_label": e.get("label")})
    return {"framework": frameworks.LABELS[name], "framework_url": url, "level": lv.get("level"),
            "because": lv.get("because") or "no public evidence", "evidence": ev, "rules": rules}


def _readiness(conn, key: str, c: dict, sigs: list[dict]) -> dict:
    """Rule levels exactly as the company page computes them: declared research signals never enter a rule, a BlueInvest TRL wins."""
    fw = frameworks.assess(c, [s for s in sigs if s["adapter"] != "ecosystem"])
    trl = fw["trl"]
    prof = blueinvest.profile_for(conn, key)
    if prof and prof.get("trl") is not None:
        trl = {"level": prof["trl"], "because": f"the BlueInvest profile states TRL {prof['trl']}",
               "evidence": [{"id": None, "evidence": {"url": prof.get("url"), "label": "BlueInvest pipeline", "date_label": "no date stated"}}]}
    cat = fw["category"]
    return {
        "technology": _level("technology", trl, fw["trl_map"], fw["urls"].get("trl")),
        "business": _level("business", fw["brl"], fw["brl_map"], fw["urls"].get("brl")),
        "investment": _level("investment", fw["irl"], fw["irl_map"], None),
        "ocean_impact": {"framework": frameworks.LABELS["ocean_impact"], "framework_url": fw["urls"].get("navigator"),
                         "category": cat["category"], "keyword": cat["keyword"],
                         "source_url": (cat.get("evidence") or {}).get("url") or (c.get("source_url") if cat.get("industry") else None),
                         "because": f"'{cat['keyword']}' in a signal detail or the industry text" if cat["category"] else "no public evidence"},
        "declared_dataset": eco_reading(conn, key, fw),
        "investment_dimensions": [{"name": d["name"], "evidence_count": d["n"], "note": d["note"],
                                   "evidence": [{"source_url": e.get("url"), "source_label": e.get("label"), "date": e.get("date_label")}
                                                for e in d["evidence"]]} for d in fw["dimensions"]],
    }


def _company_row(r: dict) -> dict:
    keys = ("company_key", "name", "y_tunnus", "country", "founded", "industry_code", "industry_desc", "website", "group_tag",
            "register_status", "source_url", "fetched_at")
    out = {k: r.get(k) for k in keys}
    out["links"] = {"api": f"/api/company/{r['company_key']}", "page": f"/c/{r['company_key']}"}
    return out


def _run(fn):
    try:
        return fn()
    except _Fail as f:
        return JSONResponse(f.body, status_code=f.status)


@router.get("")
def api_index():
    return {"name": "Ocean Opportunity Radar read-only API", "read_only": True, "auth": None,
            "theses": sorted(thesis_mod.available()), "endpoints": ENDPOINTS}


@router.get("/companies")
def api_companies(q: str = "", thesis: str | None = None, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    def body():
        th = _thesis(thesis)
        conn = _open(th)
        try:
            if q.strip():
                rows = [r for r in store.search(conn, q, limit + offset) if not fit_mod.looks_like_person(r["name"] or "", th)][offset:]
                total = None
            else:
                allr = [dict(r) for r in conn.execute("SELECT * FROM companies ORDER BY name, company_key")]
                allr = [r for r in allr if not fit_mod.looks_like_person(r["name"] or "", th)]
                rows, total = allr[offset:offset + limit], len(allr)
        finally:
            conn.close()
        return {"thesis": _head(th), "q": q, "limit": limit, "offset": offset, "total": total, "count": len(rows),
                "companies": [_company_row(r) for r in rows]}
    return _run(body)


@router.get("/company/{company_key:path}")
def api_company(company_key: str, thesis: str | None = None, limit: int = Query(5, ge=1, le=20)):
    def body():
        th = _thesis(thesis)
        conn = _open(th)
        try:
            data = store.company(conn, company_key)
            if data is None:
                raise _Fail(404, {"error": f"no company with key {company_key!r} in this radar", "thesis": th["id"],
                                  "did_you_mean": [_company_row(r) for r in store.search(conn, company_key, 5)]})
            c, sigs = data["company"], data["signals"]
            readiness = _readiness(conn, company_key, c, sigs)
            nxt = matching.who_comes_next(company_key, th, limit, conn=conn)
            step = matching.next_step(company_key, th, conn=conn)
        finally:
            conn.close()
        reasons = [{"kind": r["kind"], "confidence": r["confidence"], "text": r["text"], "source_url": r["evidence"].get("url")}
                   for r in fit_mod.fit(c, sigs, th)]
        return {"thesis": _head(th), "company": _company_row(c), "counts": data["counts"], "signals": [_signal(s) for s in sigs],
                "fit": {"rule": fit_mod.RULE_LINE, "reasons": reasons}, "readiness": readiness,
                "connections": frameworks.connections([s for s in sigs if s["adapter"] != "ecosystem"]),
                "who_comes_next": {**nxt, "rank_rule": matching.RANK_RULE},
                "next_step": {**step, "rule_text": matching.NEXT_RULES[step["rule"] - 1], "rules": list(matching.NEXT_RULES)},
                "connector_slots": {"status": "not connected", "names": list(CONNECTORS)}}
    return _run(body)


@router.get("/feed")
def api_feed(thesis: str | None = None, window: int | None = Query(None, ge=1, le=3650), type: str | None = None,
             limit: int = Query(500, ge=1, le=2000)):
    def body():
        th = _thesis(thesis)
        if window is not None:
            th["geography"] = {**th["geography"], "feed_window_days": window}
        if type is not None and type not in th["feed_signal_types"]:
            raise _Fail(400, {"error": f"type {type!r} is not a feed signal type of this thesis", "feed_signal_types": th["feed_signal_types"]})
        conn = _open(th)
        try:
            counts = store.feed_counts(conn, th)
            rows = store.feed(conn, th, signal_type=type, limit=limit)
        finally:
            conn.close()
        out = []
        for r in rows:
            d = _signal(r)
            d.update(company_key=r["company_key"], name=r["name"], country=r.get("country"), group_tag=r.get("group_tag"),
                     strength=r["strength"], reasons=r["reasons"], why=r["why"], earlier_count=r["earlier_count"],
                     signal_count=r["signal_count"], links={"api": f"/api/company/{r['company_key']}", "page": f"/c/{r['company_key']}"})
            out.append(d)
        return {"thesis": _head(th), "rule": store.rule_text(th), "reason_meaning": store.REASON_MEANING, "counts": counts,
                "count": len(out), "rows": out}
    return _run(body)


@router.get("/backtest")
def api_backtest(thesis: str | None = None):
    def body():
        th = _thesis(thesis)
        conn = _open(th)
        try:
            res = earliness.backtest(conn, th)
            nc = earliness.not_connected(conn, th)
        finally:
            conn.close()
        return {"thesis": _head(th), "rule": earliness.rule_lines(th), "not_connected": nc, **res}
    return _run(body)


@router.get("/{rest:path}", include_in_schema=False)
def api_not_found(rest: str):
    return _error(404, f"no API endpoint /api/{rest}", endpoints=ENDPOINTS)
