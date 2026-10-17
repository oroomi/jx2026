"""GET /c/{company_key}: the company page, four questions in the partners' order. Data only through radar.store."""
from __future__ import annotations

import re

from fastapi import APIRouter, Request

import sqlite3

from markupsafe import Markup, escape

from radar import blueinvest, fit as fit_mod, frameworks, intake as intake_mod, lifeline, matching, memo, store, thesis as thesis_mod
from radar.adapters import stitcher
from radar.routes.home import _has_route, templates
from radar.routes.radar import EVENT_TYPES as RADAR_EVENT_TYPES


router = APIRouter()

_URL = re.compile(r"https?://[^\s;,)]+")


def linkify(text) -> Markup:
    """Escape the text, then make each http(s) link openable."""
    out = escape(text or "")
    return Markup(_URL.sub(lambda m: f'<a href="{m.group(0)}" target="_blank" rel="noopener">{m.group(0)}</a>', str(out)))


templates.env.filters["linkify"] = linkify

DIMENSIONS = (("technology", "Technology"), ("business", "Business"), ("investment", "Investment"), ("ocean_impact", "Ocean impact"))
CONNECTORS = ("LinkedIn", "Dealroom", "Crunchbase", "PitchBook", "Tracxn")


def _register_ev(c: dict, value_date=None) -> dict:
    url = c.get("source_url")
    return store.evidence({"source_url": url, "fetched_at": c.get("fetched_at"), "date": value_date or (c.get("fetched_at") or "")[:10],
                           "adapter": "prh" if "prh.fi" in (url or "") else None})


def register_rows(c: dict) -> list[dict]:
    rows = []

    def add(label, value, ev_date=None, missing="not in public records"):
        rows.append({"label": label, "value": value, "ev": _register_ev(c, ev_date) if value else None, "missing": missing})

    add("Y-tunnus", c.get("y_tunnus"), missing="not in public records: no Y-tunnus for this company")
    add("Founded", c.get("founded"), c.get("founded"))
    code = c.get("industry_code")
    add("Industry", f"{code} {c.get('industry_desc') or ''}".strip() if code or c.get("industry_desc") else None)
    add("Register status", c.get("register_status"))
    add("Website", c.get("website"))
    add("Country", c.get("country"))
    rows.append({"label": "Source page", "value": c.get("source_url"), "ev": _register_ev(c), "missing": "not in public records"})
    return rows


blueinvest_trl = frameworks.profile_trl  # kept for callers of the old name


def readiness_rows(thesis: dict, signals: list[dict]) -> list[dict]:
    spec = thesis.get("readiness") or {}
    out = []
    for key, label in DIMENSIONS:
        d = spec.get(key)
        if not d:
            out.append({"label": label, "defined": False, "signals": []})
            continue
        classes = set(d.get("source_classes") or [])
        out.append({"label": label, "defined": True, "scale": d.get("scale"),
                    "signals": [s for s in signals if s["signal_type"] in classes]})
    return out


def ecosystem(conn, key: str, fw: dict) -> dict | None:
    """The declared dataset's readiness reading for one company, beside (never instead of) the rule levels. None when the
    dataset has no row for it."""
    try:
        r = conn.execute("SELECT * FROM eco_readiness WHERE company_key=?", (key,)).fetchone()
        meta = {k: v for k, v in conn.execute("SELECT key, value FROM eco_meta")}
        st = conn.execute("SELECT status FROM eco_entity WHERE company_key=? AND status IS NOT NULL LIMIT 1", (key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    status = st[0] if st else None
    if r is None:
        return {"status": status, "ready": None, "label": meta.get("label")} if status and status != "active" else None
    r = dict(r)
    for k in ("br_missing", "ir_missing"):
        if r[k] and re.fullmatch(r"[a-e](\s*[;,]\s*[a-e])*", r[k].strip()):
            r[k] = "checklist items " + r[k].strip()
    rule_trl = fw["trl"]["level"]
    trl_note = None
    if r["trl"] is not None:
        if rule_trl is None:
            trl_note = f"The dataset reads TRL {r['trl']}; the register rule gives no level. The page keeps the rule: no level."
        elif rule_trl != r["trl"]:
            trl_note = f"The dataset reads TRL {r['trl']}; the register rule gives level {rule_trl}. The page keeps the rule level."
        else:
            trl_note = f"The dataset reads TRL {r['trl']}, the same as the register rule."
    return {"status": status, "label": meta.get("label"), "confidence": r["confidence"], "ready": r, "trl_note": trl_note,
            "sources": [u for u in (r["sources"] or "").split("\n") if u]}


def sources(c: dict, signals: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for url, fetched, label in [(c.get("source_url"), c.get("fetched_at"), _register_ev(c)["label"])] + \
            [(s["source_url"], s.get("fetched_at"), s["evidence"]["label"]) for s in signals]:
        if url and url not in seen:
            seen[url] = {"url": url, "fetched": (fetched or "")[:10], "label": label}
    return list(seen.values())


def _page(request, name, status=200, **ctx):
    ctx.update(active="", has_route=_has_route(request))
    return templates.TemplateResponse(request, name, ctx, status_code=status)


def held_elsewhere(request: Request, key: str, current_id: str):
    """The company is missing from the sector the cookie or query picked: the first other configured sector whose store holds it, as
    (thesis, open connection, company data), else None. The page then renders with that sector and the cookie follows it, so a link to
    a company never lands on a 404 because of a sector chosen earlier (D39)."""
    for tid, path in thesis_mod.available().items():
        if tid == current_id:
            continue
        th = thesis_mod.load(path)
        conn = store.open_db(thesis=th)
        if conn is None:
            continue
        data = store.company(conn, key)
        if data is not None:
            request.state.thesis = th
            request.state.set_thesis_cookie = th["id"]
            return th, conn, data
        conn.close()
    return None


@router.get("/c/{company_key:path}")
def company_page(request: Request, company_key: str):
    thesis, conn = store.context(request)
    if conn is None:
        return _page(request, "company_404.html", 503, key=company_key, message=store.NO_DB_MESSAGE, hits=[])
    try:
        data = store.company(conn, company_key)
        if data is None:
            other = held_elsewhere(request, company_key, thesis["id"])
            if other is not None:
                conn.close()
                thesis, conn, data = other
        if data is None:
            return _page(request, "company_404.html", 404, key=company_key,
                         message=f"no company with key {company_key} in this radar", hits=store.search(conn, company_key, 5))
        c, sigs = data["company"], data["signals"]
        n = store.cohort_count(conn)
        profile = blueinvest.profile_for(conn, company_key)
        speed = lifeline.speed(conn, company_key, c.get("founded"))
        wide = intake_mod.company_view(conn, thesis, c, sigs)
        rule_sigs = [x for x in sigs if x["adapter"] != "ecosystem"]  # declared research is shown beside a level, never inside the rule
        fw = frameworks.page_levels(c, sigs, profile)  # the same levels the memo bands read
        eco = ecosystem(conn, company_key, fw)
        nxt = matching.who_comes_next(company_key, thesis, 5, conn=conn)
        step = matching.next_step(company_key, thesis, conn=conn)
        stitch = stitcher.page_view(conn, company_key, thesis)
        record_checks = memo.checks_for(conn, thesis, c, sigs, (fw.get("category") or {}).get("category"), nxt)
    finally:
        conn.close()
    # The page counts every dated signal; the cohort radar ranks seven kinds and skips name-only matches. Both numbers are printed, each named (D41).
    radar_n = sum(1 for x in sigs if x["signal_type"] in RADAR_EVENT_TYPES and x.get("confidence") != "low")
    reasons = fit_mod.fit(c, sigs, thesis)
    entered = sorted({s["evidence"]["label"] for s in sigs}) or [store.evidence(c)["label"]]
    return _page(request, "company.html", c=c, signals=sigs, counts=data["counts"], thesis=thesis,
                 register=register_rows(c), reasons=reasons, intake=wide, fit_rule=fit_mod.RULE_LINE, entered_via=", ".join(entered),
                 readiness=readiness_rows(thesis, sigs), sources=sources(c, sigs), connectors=CONNECTORS,
                 cohort_n=n, radar_exists=_has_route(request)("/radar"),
                 fw=fw, connections=frameworks.connections(rule_sigs),
                 nxt=nxt, step=step, rank_rule=matching.RANK_RULE, eco=eco,
                 type_labels=store.TYPE_LABELS, lifeline=lifeline.build(c, sigs), speed=speed, min_sample=lifeline.MIN_SAMPLE,
                 stitch=stitch, radar_n=radar_n,
                 record_checks=record_checks)


@router.get("/company-search")
def company_search(request: Request, q: str = ""):
    thesis, conn = store.context(request)
    hits = []
    if conn is not None:
        try:
            hits = store.search(conn, q, 20)
        finally:
            conn.close()
    return _page(request, "company_search.html", q=q, hits=hits, db_ok=conn is not None)
