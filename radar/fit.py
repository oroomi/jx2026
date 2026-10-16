"""Thesis fit with reasons. Pure functions: no database, no network, no score.

fit() returns an ordered list of reasons. Confidence follows the rule in radar/emit.py:
an industry code alone is low, a name keyword is medium, a feed-type signal keeps its own confidence.
"""
from __future__ import annotations

import re

from radar import store

RULE_LINE = ("Reasons come from the thesis file and the database only: an industry code on the thesis list is low confidence, "
             "a thesis keyword at the start of a word in the legal name is medium, and each feed signal keeps the confidence its "
             "adapter gave it. There is no score and no ranking.")

_KIND_ORDER = {"industry_code": 0, "name_keyword": 1, "signal": 2}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def _keywords(thesis: dict) -> list[str]:
    kw = thesis.get("name_keywords") or []
    words = [w for ws in kw.values() for w in ws] if isinstance(kw, dict) else list(kw)
    return [str(w).strip().rstrip("-").casefold() for w in words if str(w).strip().rstrip("-")]


def matched_keywords(name: str, thesis: dict) -> list[str]:
    name = (name or "").casefold()
    return [w for w in _keywords(thesis) if re.search(r"(?<!\w)" + re.escape(w), name)]


def _company_evidence(company: dict) -> dict:
    return store.evidence({"source_url": company.get("source_url"), "fetched_at": company.get("fetched_at"),
                           "date": company.get("founded") or (company.get("fetched_at") or "")[:10],
                           "adapter": "prh" if "prh.fi" in (company.get("source_url") or "") else None,
                           "confidence": "low"})


def fit(company: dict, signals: list[dict], thesis: dict) -> list[dict]:
    reasons: list[dict] = []
    code = (company.get("industry_code") or "").strip()
    notes = {str(c.get("code")): c.get("note") for c in thesis.get("industry_codes") or []}
    if code and code in notes:
        ev = _company_evidence(company)
        ev["confidence"], ev["confidence_rule"] = "low", store.CONFIDENCE_RULES["low"]
        reasons.append({"kind": "industry_code", "confidence": "low", "evidence": ev,
                        "text": f"Industry code {code} is on the thesis list ({notes[code]})."})
    hits = matched_keywords(company.get("name"), thesis)
    if hits:
        ev = _company_evidence(company)
        ev["confidence"], ev["confidence_rule"] = "medium", store.CONFIDENCE_RULES["medium"]
        reasons.append({"kind": "name_keyword", "confidence": "medium", "evidence": ev,
                        "text": "Legal name contains thesis keyword: " + ", ".join(hits) + "."})
    feed_types = set(thesis.get("feed_signal_types") or [])
    for s in signals:
        if s.get("signal_type") in feed_types:
            label = s.get("type_label") or store.TYPE_LABELS.get(s["signal_type"], s["signal_type"])
            text = f"{label} on {s.get('date')}" + (f": {s['detail']}" if s.get("detail") else ".")
            reasons.append({"kind": "signal", "confidence": s.get("confidence"), "text": text,
                            "evidence": s.get("evidence") or store.evidence(s)})
    reasons.sort(key=lambda r: (_KIND_ORDER[r["kind"]], _CONF_ORDER.get(r["confidence"], 3)))
    return reasons
