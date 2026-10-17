"""Thesis fit with reasons. Pure functions: no database, no network, no score.

fit() returns an ordered list of reasons. Confidence follows the rule in radar/emit.py:
an industry code alone is low, a name keyword is medium, a feed-type signal keeps its own confidence.
"""
from __future__ import annotations

import re

from radar import labels
from radar import store

RULE_LINE = ("Reasons come from the thesis file and the database only: an industry code on the thesis list is low confidence, "
             "a thesis keyword matching a whole word of the legal name (or the start of a longer word, for thesis words of 5 or more characters) is medium, and each feed signal keeps the confidence its "
             "adapter gave it. There is no score and no ranking.")

_KIND_ORDER = {"industry_code": 0, "name_keyword": 1, "signal": 2}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


MIN_PREFIX = 5  # a keyword shorter than this matches whole words only
MATCH_RULE = ("A thesis word matches only as a whole word, or as the start of a longer word when the thesis word has at least "
              "5 characters; shorter words (under 5) match whole words only, text is compared case-folded, and a short stop "
              "list in the thesis file blocks known false friends.")
_WORD = re.compile(r"\w+", re.UNICODE)

# Legal-name shapes that read as a private person (policy D-N7): 2 or 3 capitalised name words, then only company suffixes.
PERSON_SUFFIXES = ("holding", "invest", "capital", "consulting", "oy", "ab", "ky", "tmi", "as", "asa", "aps")
# A plain "Given Family Oy" is indistinguishable from "Blue Bay Oy", so at least one of these must be present.
PERSON_MARKERS = ("holding", "invest", "capital", "consulting", "tmi", "ky")
_NAME_WORD = re.compile(r"[A-ZÅÄÖ][a-zåäöé'-]+")


def _keywords(thesis: dict) -> list[str]:
    kw = thesis.get("name_keywords") or []
    words = [w for ws in kw.values() for w in ws] if isinstance(kw, dict) else list(kw)
    return [str(w).strip().rstrip("-").casefold() for w in words if str(w).strip().rstrip("-")]


def stop_words(thesis: dict) -> set[str]:
    return {str(w).strip().casefold() for w in thesis.get("keyword_stop_words") or [] if str(w).strip()}


def word_matches(word: str, keyword: str) -> bool:
    """Whole word, or word prefix when the keyword has MIN_PREFIX characters or more. Both already case-folded."""
    return word == keyword or (len(keyword) >= MIN_PREFIX and word.startswith(keyword))


def matched_keywords(text: str, thesis: dict) -> list[str]:
    words = [w for w in _WORD.findall((text or "").casefold())]
    stop = stop_words(thesis)
    words = [w for w in words if w not in stop]
    return [k for k in _keywords(thesis) if any(word_matches(w, k) for w in words)]


def looks_like_person(name: str, thesis: dict) -> bool:
    """True for a legal name shaped like a private person's name followed by company suffixes, e.g. 'Given Family Holding Oy'.
    Words on the thesis keyword lists or in the thesis non_person_words list are business words, never names."""
    parts = (name or "").replace(",", " ").split()
    i = 0
    while i < len(parts) and _NAME_WORD.fullmatch(parts[i]) and parts[i].casefold() not in PERSON_SUFFIXES:
        i += 1
    given, rest = parts[:i], [p.casefold().rstrip(".") for p in parts[i:]]
    if not 2 <= len(given) <= 3 or not rest or any(r not in PERSON_SUFFIXES for r in rest) \
            or not any(r in PERSON_MARKERS for r in rest):
        return False
    biz = {str(w).casefold() for w in thesis.get("non_person_words") or []}
    return not any(g.casefold() in biz for g in given) and not matched_keywords(" ".join(given), thesis)


# Capitalised words that are never part of a private person's name in our texts: months, weekdays, places and sentence words.
GENERIC_CAPS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
                "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "finland", "finnish",
                "europe", "european", "nordic", "baltic", "helsinki", "turku", "espoo", "tampere", "the", "this", "that", "and",
                "for", "with", "from", "news", "press", "release", "business", "blue", "ocean", "sea", "union", "commission",
                "programme", "program", "project", "university", "city", "port", "ministry", "science", "park", "institute", "centre",
                "center", "foundation", "fund", "accelerator", "incubator", "award", "prize", "expo", "summit", "week", "forum",
                "association", "challenge", "innovation", "research", "council", "agency"}
REDACTED = "[name redacted]"
_TOKEN = re.compile(r"\S+")
_EDGE = "\"'()[]{},.;:!?“”‘’«»"


def redact_person_names(text: str | None, company_name: str | None, thesis: dict, also_allowed: tuple[str, ...] = ()) -> str:
    """Replace every run of two or more consecutive capitalised name-shaped words (the looks_like_person word shape) that are not
    part of the company's legal name, a business word of the thesis (non_person_words, keywords, company suffixes) or a generic
    word with "[name redacted]". Over-redaction is the accepted cost: a page never prints a private person's name."""
    text = text or ""
    own = {w.casefold().strip(_EDGE) for n in (company_name or "", *also_allowed) for w in n.split()}
    biz = {str(w).casefold() for w in thesis.get("non_person_words") or []} | set(PERSON_SUFFIXES) | GENERIC_CAPS

    def is_name(core: str) -> bool:
        f = core.casefold()
        return bool(_NAME_WORD.fullmatch(core)) and f not in own and f not in biz and not matched_keywords(core, thesis)

    toks = []
    for m in _TOKEN.finditer(text):
        raw = m.group(0)
        core = raw.strip(_EDGE)
        lead = raw.find(core) if core else 0
        toks.append({"start": m.start() + lead, "end": m.start() + lead + len(core), "name": bool(core) and is_name(core),
                     "lead": lead > 0, "trail": bool(core) and lead + len(core) < len(raw), "gap_ok": True})
    for a, b in zip(toks, toks[1:]):
        b["gap_ok"] = text[a["end"]:b["start"]].strip() == "" and not a["trail"] and not b["lead"]
    spans, run = [], []
    for t in toks + [{"name": False, "gap_ok": False}]:
        if t["name"] and run and t["gap_ok"]:
            run.append(t)
            continue
        if len(run) >= 2:
            spans.append((run[0]["start"], run[-1]["end"]))
        run = [t] if t["name"] else []
    for a, b in reversed(spans):
        text = text[:a] + REDACTED + text[b:]
    return text


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
            label = s.get("type_label") or labels.signal_label(s["signal_type"])
            text = f"{label} on {s.get('date_label') or s.get('date')}" + (f": {s['detail']}" if s.get("detail") else ".")
            reasons.append({"kind": "signal", "confidence": s.get("confidence"), "text": text,
                            "evidence": s.get("evidence") or store.evidence(s)})
    reasons.sort(key=lambda r: (_KIND_ORDER[r["kind"]], _CONF_ORDER.get(r["confidence"], 3)))
    return reasons
