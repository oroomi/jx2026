"""Aava: the narration script of one company page or of the feed. Pure functions, no database, no network, no model.

A segment is {text, target, action, source_url[, value, max, points]}. target is the id of an element on the rendered page.
Every sentence is built from a row the page also shows; a fact the records lack is spoken as "no public record of X".
Numbers appear only when the page prints them (dates are spoken as "13 June 2025" for the ISO date on the page)."""
from __future__ import annotations

import re
from datetime import date

ACTIONS = ("highlight", "scroll", "count_up", "draw_timeline", "fill_level", "none")
INTENTS = ("brief", "next", "talk")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MAX_SIGNALS_SPOKEN = 8
MAX_DETAIL = 220
LEVEL_MAX = 9
_DASHES = re.compile(r"\s*[\u2013\u2014]\s*")


def clean(text: str) -> str:
    """Spoken and written text: no long dashes, one line."""
    return re.sub(r"\s+", " ", _DASHES.sub(", ", text or "")).strip()


def say_date(iso: str | None, year_only: bool = False) -> str | None:
    if not iso or not re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
        return None
    y, m, d = (int(x) for x in iso.split("-"))
    if year_only:
        return f"{y}, year only"
    try:
        date(y, m, d)
    except ValueError:
        return None
    return f"{d} {MONTHS[m - 1]} {y}"


_ISO_IN_TEXT = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_YTUNNUS = re.compile(r"\s*\(Y-tunnus [\d-]+\)")


def _short(detail: str) -> str:
    """The page's own detail sentence, spoken: ISO dates as dates, the business id left to the page."""
    d = _ISO_IN_TEXT.sub(lambda m: say_date(m.group()) or m.group(), _YTUNNUS.sub("", clean(detail))).rstrip(".")
    if len(d) <= MAX_DETAIL:
        return d
    return d[:MAX_DETAIL].rsplit(" ", 1)[0]


def seg(text: str, target: str, action: str = "highlight", source_url: str | None = None, **extra) -> dict:
    assert action in ACTIONS
    return {"text": clean(text), "target": target, "action": action, "source_url": source_url, **extra}


def _source_label(s: dict) -> str:
    return (s.get("evidence") or {}).get("label") or "the source"


def who(c: dict) -> dict:
    parts = [f"{c['name']}."]
    d = say_date(c.get("founded"))
    parts.append(f"Founded {d}." if d else "No public record of its founding date.")
    desc, code = (c.get("industry_desc") or "").strip(), (c.get("industry_code") or "").strip()
    if desc:
        parts.append(f"Registered line of business: {desc}.")
    elif code:
        parts.append(f"Registered industry code {code}, no description stated.")
    else:
        parts.append("No public record of its line of business.")
    parts.append(f"Register status: {c['register_status']}." if c.get("register_status") else "No public record of its register status.")
    return seg(" ".join(parts), "aava-who", "highlight", c.get("source_url"))


def surfaced(signals: list[dict]) -> list[dict]:
    """What surfaced and when. signals are in page order (newest first); ids follow page order, narration is oldest first."""
    if not signals:
        return [seg("No public record of any signal for this company.", "signals", "scroll")]
    order = sorted(range(len(signals)), key=lambda i: (signals[i]["date"], -i))
    out = [seg("What surfaced, oldest first.", "signals", "scroll")]
    for i in order[:MAX_SIGNALS_SPOKEN]:
        s = signals[i]
        when = say_date(s["date"], s.get("date_precision") == "year") or "date not in public records"
        text = f"{when}: {s.get('type_label') or s['signal_type']}."
        text += f" {_short(s['detail'])}." if s.get("detail") else " No detail in the source."
        text += f" Source: {_source_label(s)}."
        out.append(seg(text, f"aava-sig-{i}", "highlight", s["source_url"]))
    if len(signals) > MAX_SIGNALS_SPOKEN:
        out.append(seg("The remaining records are listed on the page.", "signals", "scroll"))
    pts = []
    first, last = signals[order[0]]["date"], signals[order[-1]]["date"]
    span = max((date.fromisoformat(last) - date.fromisoformat(first)).days, 1)
    for i in order:
        pts.append({"left": round((date.fromisoformat(signals[i]["date"]) - date.fromisoformat(first)).days / span * 100, 1),
                    "label": signals[i].get("type_label") or signals[i]["signal_type"], "date": signals[i]["date"]})
    out.append(seg("Here they are on one line.", "signals", "draw_timeline", None, points=pts))
    return out


def fit_segment(reasons: list[dict], entered_via: str) -> dict:
    if not reasons:
        return seg(f"Question one, who is most promising. No public record of a sector match; it entered through {entered_via}.", "q1", "highlight")
    n = len(reasons)
    first = reasons[0]
    return seg(f"Question one, who is most promising. {n} reason{'s' if n != 1 else ''} it fits this sector, from public records. "
               f"First: {_short(first['text'])}.", "q1", "highlight", (first.get("evidence") or {}).get("url"))


def _level_segment(label: str, r: dict) -> dict:
    ev = r.get("evidence") or []
    if not r.get("level"):
        return seg(f"{label}: no public record of a level.", "q2", "highlight")
    shown = min(len(ev), 4)
    url = (ev[0].get("evidence") or {}).get("url") if ev else None
    return seg(f"{label}: level {r['level']} of {LEVEL_MAX}, because {clean(r.get('because') or '')}. "
               f"{shown} source{'s' if shown != 1 else ''} shown on the page.", "q2", "fill_level", url, value=r["level"], max=LEVEL_MAX)


def readiness(fw: dict) -> list[dict]:
    out = [_level_segment("Question two, how ready are they. Technology readiness", fw["trl"]),
           _level_segment("Business readiness", fw["brl"]),
           _level_segment("Investment readiness", fw["irl"])]
    cat = fw.get("category") or {}
    if cat.get("category"):
        out.append(seg(f"Ocean impact: Navigator category {cat['category']}, matched on the word {cat['keyword']}.", "q2", "highlight",
                       (cat.get("evidence") or {}).get("url")))
    else:
        out.append(seg("Ocean impact: no public record of a category.", "q2", "highlight"))
    return out


def next_investors() -> dict:
    return seg("Question three, who comes next. No public record yet: the matching rules are not scored on this page.", "q3", "highlight")


def next_step() -> dict:
    return seg("Question four, what should happen next. No public record yet: the next-step rules are not scored on this page.", "q4", "highlight")


def company_script(c: dict, signals: list[dict], fw: dict, reasons: list[dict], entered_via: str, intent: str = "brief") -> dict:
    """The ordered segments for one company. intent brief = everything; next = question four; talk = question three."""
    if intent == "next":
        segs = [next_step()]
    elif intent == "talk":
        segs = [next_investors()]
    else:
        segs = [who(c), *surfaced(signals), fit_segment(reasons, entered_via), *readiness(fw), next_investors(), next_step(),
                seg("That is everything on this page. Every fact comes from the linked records.", "aava-who", "none")]
    return {"kind": "company", "title": f"Ask Aava about {c['name']}", "intent": intent, "segments": segs}


def feed_script(rows: list[dict], limit: int = 5) -> dict:
    """The top rows of the feed, in page order, each with its date and source."""
    segs = []
    for r in rows[:limit]:
        when = say_date(r["date"], r.get("date_precision") == "year") or "date not in public records"
        why = clean(r.get("why") or "").removeprefix("Why: ").removeprefix("Weak: ").rstrip(".")
        text = f"{r['name']}. {r.get('type_label') or r['signal_type']}, {when}. {why}. Source: {_source_label(r)}."
        segs.append(seg(text, f"aava-feed-{r['company_key']}", "highlight", r["source_url"]))
    if not segs:
        segs = [seg("No public record in this window.", "feed-rows", "none")]
    return {"kind": "feed", "title": "Ask Aava what is new", "intent": "brief", "segments": segs}
