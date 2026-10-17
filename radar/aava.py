"""Aava: the narration script of one company page or of the feed. Pure functions, no database, no network, no model.

A segment is {text, target, action, source_url, sha[, value, max, points]}; sha fingerprints the text (see text_sha). target is the id of an element on the rendered page.
Every sentence is built from a row the page also shows; a fact the records lack is spoken as "no public record of X".
Numbers appear only when the page prints them (dates are spoken as "13 June 2025" for the ISO date on the page)."""
from __future__ import annotations

import hashlib
import re
from datetime import date

ACTIONS = ("highlight", "scroll", "count_up", "draw_timeline", "fill_level", "none")
INTENTS = ("brief", "next", "talk", "why", "meet", "missing")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MAX_SIGNALS_SPOKEN = 8
MAX_DETAIL = 220
LEVEL_MAX = 9
SHA_LEN = 16
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


def text_sha(text: str) -> str:
    """Fingerprint of a segment's spoken text (first 16 hex of SHA-256). The pre-rendered audio manifest (radar.aava_voice) is keyed by it,
    and the player plays a recording only when this value matches, so audio is never played over text it was not rendered from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:SHA_LEN]


def seg(text: str, target: str, action: str = "highlight", source_url: str | None = None, **extra) -> dict:
    assert action in ACTIONS
    spoken = clean(text)
    return {"text": spoken, "target": target, "action": action, "source_url": source_url, "sha": text_sha(spoken), **extra}


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


LISTS = (("investors", "investor"), ("funding", "programme or funder"), ("partners", "partner or buyer"))
MAX_PER_LIST = 2


_ECO_REASON = re.compile(r"caps \[([^\]]*)\];\s*kw \[([^\]]*)\];\s*stage ([\d.]+)(?:;\s*impact ([\d.]+))?")


def _spoken_eco(m: re.Match) -> str:
    """The ecosystem dataset's terse reason ("caps ['C10']; kw []; stage 1.0") in words, keeping its own codes and numbers."""
    caps = [c.strip(" '\"") for c in m.group(1).split(",") if c.strip(" '\"")]
    kws = [k.strip(" '\"") for k in m.group(2).split(",") if k.strip(" '\"")]
    bits = []
    if caps:
        bits.append("shared capability codes " + " and ".join(caps))
    if kws:
        bits.append("shared keywords " + ", ".join(kws))
    bits.append(f"stage fit {m.group(3)}")
    if m.group(4):
        bits.append(f"impact score {m.group(4)}")
    return "; ".join(bits)


def _reason(text: str | None) -> str:
    return _ECO_REASON.sub(_spoken_eco, _short(text or "")).rstrip(".") if text else ""


def _row_sentence(r: dict, kind: str) -> str:
    """One who-comes-next row as the page prints it: name, kind, the row's own reason, its deadline when the page shows one."""
    text = f"{r['name']}, {(r.get('kind') or kind).strip()}."
    if r.get("reason"):
        text += f" Reason on the page: {_reason(r['reason'])}."
    if r.get("deadline"):
        text += f" Deadline {say_date(r['deadline']) or r['deadline']}."
    return text


def next_investors(nxt: dict | None = None) -> list[dict]:
    """Question three from radar.matching.who_comes_next: the top rows of each list, in the page's order, each with its source."""
    if not nxt or not any(nxt.get(k) for k, _ in LISTS):
        return [seg("Question three, who comes next. No public record of an investor, programme or partner match for this company yet.",
                    "q3", "highlight")]
    counts = [f"{len(nxt[k])} {one if len(nxt[k]) == 1 else one + 's'}" for k, one in (("investors", "investor"), ("funding", "programme"),
                                                                                    ("partners", "partner")) if nxt.get(k)]
    out = [seg(f"Question three, who comes next, from the records on this page: {', '.join(counts)} listed, in priority order.", "q3", "scroll")]
    for k, kind in LISTS:
        for r in (nxt.get(k) or [])[:MAX_PER_LIST]:
            out.append(seg(_row_sentence(r, kind), "q3", "highlight", r.get("source_url")))
    return out


def next_step(step: dict | None = None, memo: dict | None = None) -> list[dict]:
    """Question four from radar.matching.next_step, then the fund memo's verdict and its actions (radar.memo)."""
    if not step:
        return [seg("Question four, what should happen next. No public record of a next step for this company yet.", "q4", "highlight")]
    out = [seg(f"Question four, what should happen next. {clean(step['sentence'])}. Because {clean(step.get('because') or '').rstrip('.')}.",
               "q4", "highlight", step.get("source_url"))]
    if memo:
        out += verdict(memo, short=True)
    return out


def _because(rec: dict) -> str:
    parts = ", ".join(f"{x['label']} {x['band']}" for x in rec.get("because_labels") or [])
    return (f"{rec['matched']}: " if rec.get("matched") else "") + parts


def verdict(memo: dict | None, short: bool = False) -> list[dict]:
    """Why this verdict: the memo's decision, the matched rule and the four bands, then its linked reasons and actions."""
    if not memo:
        return [seg("No memo for this company in this radar.", "memo", "highlight")]
    rec = memo["recommendation"]
    first = next((w.get("url") for w in memo.get("why") or [] if w.get("url")), None)
    out = [seg(f"The memo for the fund, from the records on this page, recommends {rec['decision']}. Because {_because(rec)}.",
               "memo", "highlight", first)]
    if rec.get("note"):
        out.append(seg(rec["note"], "memo", "highlight"))
    if not short:
        for w in (memo.get("why") or [])[:4]:
            out.append(seg(f"{_reason(w['text'])}.", "memo", "highlight", w.get("url")))
    for a in (memo.get("actions") or [])[:2 if short else 3]:
        out.append(seg(f"Action for the fund: {_reason(a['text'])}.", "memo", "highlight", a.get("url")))
    return out


def meet(nxt: dict | None, memo: dict | None) -> list[dict]:
    """Who should we meet: the memo's actions that name someone, then the top rows of question three."""
    out = []
    for a in (memo or {}).get("actions") or []:
        if a.get("url"):
            out.append(seg(f"The memo says: {_reason(a['text'])}.", "memo", "highlight", a["url"]))
    out += next_investors(nxt)
    return out


def missing(memo: dict | None, fw: dict) -> list[dict]:
    """What's missing: the memo's evidence gaps and the readiness rows with no public record, as the page prints them."""
    out = []
    rec = (memo or {}).get("recommendation") or {}
    if rec.get("needs"):
        out.append(seg(f"The memo needs more public evidence for: {', '.join(rec['needs'])}.", "memo", "highlight"))
    for k in (memo or {}).get("risks") or []:
        out.append(seg(f"{_reason(k['text'])}.", "memo", "highlight", k.get("url")))
    dims = [d["name"] for d in fw.get("dimensions") or [] if not d.get("evidence")]
    if dims:
        out.append(seg(f"Investment dimensions with no public record on this page: {', '.join(dims)}.", "q2", "highlight"))
    if rec.get("dimensions"):
        out.append(seg(f"{rec['dimensions']['text']}.", "memo", "highlight", rec["dimensions"].get("url")))
    if not out:
        out = [seg("The memo lists no evidence gap against the levels this sector reads.", "memo", "highlight")]
    return out


QUESTIONS = (("why", "Why this verdict?"), ("meet", "Who should we meet?"), ("missing", "What's missing?"))


def company_script(c: dict, signals: list[dict], fw: dict, reasons: list[dict], entered_via: str, intent: str = "brief", *,
                   nxt: dict | None = None, step: dict | None = None, memo: dict | None = None) -> dict:
    """The ordered segments for one company. brief = everything; next = question four; talk = question three; why = the memo's
    verdict; meet = who to meet; missing = the evidence gaps. No model, no network: every segment is built from the same rows the
    page renders (radar.matching.who_comes_next, radar.matching.next_step, radar.memo.build)."""
    if intent == "next":
        segs = next_step(step, memo)
    elif intent == "talk":
        segs = next_investors(nxt)
    elif intent == "why":
        segs = verdict(memo)
    elif intent == "meet":
        segs = meet(nxt, memo)
    elif intent == "missing":
        segs = missing(memo, fw)
    else:
        segs = [who(c), *surfaced(signals), fit_segment(reasons, entered_via), *readiness(fw), *next_investors(nxt), *next_step(step, memo),
                seg("That is everything on this page. Every fact comes from the linked records.", "aava-who", "none")]
    return {"kind": "company", "title": f"Ask Aava about {c['name']}", "intent": intent, "segments": segs}


def company_groups(c: dict, signals: list[dict], fw: dict, reasons: list[dict], entered_via: str, *, nxt=None, step=None, memo=None) -> dict:
    """Every intent's segments at once, embedded in the page so a tap plays them with no request (speech starts inside the tap)."""
    return {i: company_script(c, signals, fw, reasons, entered_via, i, nxt=nxt, step=step, memo=memo)["segments"] for i in INTENTS}


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
