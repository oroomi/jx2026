"""GET /c/{company_key}: the company page, four questions in the partners' order. Data only through radar.store."""
from __future__ import annotations

import re

from fastapi import APIRouter, Request

import sqlite3

from markupsafe import Markup, escape

from radar import blueinvest, fit as fit_mod, frameworks, lifeline, matching, store
from radar.adapters import stitcher
from radar.routes.home import _has_route, templates


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


def blueinvest_trl(profile: dict) -> dict:
    """The TRL a BlueInvest profile states, in the shape frameworks._level returns, with its profile page as the evidence chip."""
    ev = {"label": "BlueInvest pipeline", "event_date": None, "date_precision": "day", "date_label": "no date stated",
          "fetched_at": profile.get("fetched_at"), "url": profile.get("url"), "confidence": None, "confidence_rule": None}
    return {"level": profile["trl"], "evidence": [{"evidence": ev}], "because": f"the BlueInvest profile states TRL {profile['trl']}"}


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


@router.get("/c/{company_key:path}")
def company_page(request: Request, company_key: str):
    thesis, conn = store.context(request)
    if conn is None:
        return _page(request, "company_404.html", 503, key=company_key, message=store.NO_DB_MESSAGE, hits=[])
    try:
        data = store.company(conn, company_key)
        if data is None:
            return _page(request, "company_404.html", 404, key=company_key,
                         message=f"no company with key {company_key} in this radar", hits=store.search(conn, company_key, 5))
        c, sigs = data["company"], data["signals"]
        n = store.cohort_count(conn)
        profile = blueinvest.profile_for(conn, company_key)
        speed = lifeline.speed(conn, company_key, c.get("founded"))
        rule_sigs = [x for x in sigs if x["adapter"] != "ecosystem"]  # declared research is shown beside a level, never inside the rule
        fw = frameworks.assess(c, rule_sigs)
        if profile and profile.get("trl") is not None:
            fw["trl"] = blueinvest_trl(profile)
        eco = ecosystem(conn, company_key, fw)
        nxt = matching.who_comes_next(company_key, thesis, 5, conn=conn)
        step = matching.next_step(company_key, thesis, conn=conn)
        stitch = stitcher.page_view(conn, company_key)
    finally:
        conn.close()
    reasons = fit_mod.fit(c, sigs, thesis)
    entered = sorted({s["evidence"]["label"] for s in sigs}) or [store.evidence(c)["label"]]
    return _page(request, "company.html", c=c, signals=sigs, counts=data["counts"], thesis=thesis,
                 register=register_rows(c), reasons=reasons, fit_rule=fit_mod.RULE_LINE, entered_via=", ".join(entered),
                 readiness=readiness_rows(thesis, sigs), sources=sources(c, sigs), connectors=CONNECTORS,
                 cohort_n=n, radar_exists=_has_route(request)("/radar"),
                 fw=fw, connections=frameworks.connections(rule_sigs),
                 nxt=nxt, step=step, step_rule=matching.NEXT_RULES[step["rule"] - 1], step_rules=matching.NEXT_RULES, rank_rule=matching.RANK_RULE, eco=eco,
                 type_labels=store.TYPE_LABELS, lifeline=lifeline.build(c, sigs), speed=speed, min_sample=lifeline.MIN_SAMPLE,
                 stitch=stitch)


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
