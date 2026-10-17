"""The AI box on each company page: "What the public record says". A batch, so no live API key and no cost at page time.

    export  facts the page already shows, one JSON per company, pure Python, no person names (radar.briefs export)
    (write) a model writes six fixed slots per company from that JSON, each {text, cites} or null, cites taken only from that export
    verify  code checks every sentence before it is stored; a failing sentence is dropped and logged, a brief with fewer than
            MIN_SLOTS slots left is dropped
    import  loads the verified briefs into company_briefs (radar/schema/040_briefs.sql)

Brief file: {"company_key": "...", "written": "YYYY-MM-DD", "slots": {"what_it_does": {"text": "...", "cites": ["https://..."]} | null, "thesis_fit": ..., "readiness": ..., "who_to_meet": ..., "what_the_fund_should_do": ..., "whats_missing": ...}}.
CLI: python3 -m radar.briefs export --keys FILE --out DIR | verify --dir DIR [--exports DIR] | import --dir DIR [--exports DIR]"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from radar import db, fit as fit_mod, frameworks, matching, store, thesis as thesis_mod, words

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "data" / "fetched" / "briefs"
MIN_SENTENCES, MAX_SENTENCES, MAX_CHARS = 2, 6, 420
PRAISE = ("strong team", "market leader", "market-leading", "leading", "world-class", "best-in-class", "outstanding", "excellent", "impressive",
          "unicorn", "game-changing", "game changing", "revolutionary", "top-tier", "cutting-edge", "promising", "exceptional", "disrupt")
# Capitalised words a sentence may use without them appearing in the export: months, weekdays and country or area words.
GENERIC = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
           "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Finland", "Finnish", "Europe", "European",
           "EU", "Nordic", "Baltic", "The", "This", "That", "These", "It", "Its", "They", "There", "No", "Not", "Public", "For", "In", "On",
           "At", "A", "An", "As", "By", "With", "From", "Since", "Only", "One", "Two", "Three", "Four", "Five", "Six", "If", "So", "But", "And"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12}
_CAP = re.compile(r"[A-ZÅÄÖ][\w'’-]*")
_NUM = re.compile(r"\d[\d  ,.]*\d|\d")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
_MONTH_YEAR = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", re.I)
_URL = re.compile(r"https?://[^\s\"'<>)]+")
_RAW_TOKEN = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|\b(?:caps|kw|stage) ?[\[\d]")


def slug(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]+", "_", key)


# ---- export -------------------------------------------------------------------------------------------------

def _words_flagged(text: str, allowed: set[str]) -> list[str]:
    """Capitalised words in free text that are not in the allowed vocabulary and sit next to another capitalised word: a name shape."""
    toks = list(_CAP.finditer(text or ""))
    out = []
    for a, b in zip(toks, toks[1:]):
        if b.start() - a.end() == 1 and (a.group() not in allowed or b.group() not in allowed):
            out.append(f"{a.group()} {b.group()}")
    return out


def _clean(text: str | None, allowed: set[str]) -> str | None:
    """Free text goes into the export only if no capitalised pair looks like a name; otherwise it is left out (the facts stay)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t or _words_flagged(t, allowed):
        return None
    return t


def _titles(conn, sig_ids: list[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for i in range(0, len(sig_ids), 500):
        chunk = sig_ids[i:i + 500]
        try:
            for r in conn.execute(f"SELECT signal_id, text FROM signal_text WHERE field='title' AND signal_id IN ({','.join('?' * len(chunk))})", chunk):
                out[r[0]] = r[1]
        except sqlite3.OperationalError:
            break
    return out


def export_one(conn: sqlite3.Connection, thesis: dict, key: str, *, today=None) -> dict | None:
    """The facts the company page shows, for one company, with every URL a sentence may cite. None when the company is unknown."""
    from radar import memo as memo_mod
    ctx = matching.company_context(conn, key)
    if ctx is None:
        return None
    c, sigs = ctx["c"], ctx["sigs"]
    own_name_words = set(_CAP.findall(c["name"]))
    allowed = set(GENERIC) | own_name_words | {"Oy", "Oyj", "Ab", "Ltd"}
    titles = _titles(conn, [s["id"] for s in sigs])
    fw = ctx["fw"]
    nxt = matching.who_comes_next(key, thesis, 5, conn=conn, today=today)
    for lst in nxt.values():
        for r in lst:
            allowed |= set(_CAP.findall(r["name"]))
    signals = []
    for n, s in enumerate(sigs, 1):
        title = titles.get(s["id"])
        if s["signal_type"] == "public_contract":
            title = title or store._title_part(s.get("detail"))
        signals.append({"ref": f"S{n}", "type": s["signal_type"], "type_label": s["type_label"], "date": s["date"], "date_label": s.get("date_label") or s["date"],
                        "source_url": s["source_url"], "source_label": s["evidence"]["label"], "confidence": s["confidence"], "adapter": s["adapter"],
                        "title": _clean(title, allowed), "note": _clean(re.sub(r"\s*\[[^\]]*\]\s*$", "", s.get("detail") or ""), allowed),
                        "amount_eur": s.get("amount_eur")})
    levels = {}
    for dim, k, label in (("technology", "trl", "Technology readiness level (Aalto TRL, 1-9)"), ("business", "brl", "Business readiness level (KTH BRL, 1-9)"),
                          ("investment", "irl", "Investment readiness level (1-9)")):
        lv = fw[k]
        ev = lv["evidence"]
        levels[dim] = {"label": label, "level": lv["level"], "rule": lv["because"],
                       "url": (max(ev, key=lambda x: x["date"])["source_url"] if all(x.get("date") for x in ev)
                               else next(((x.get("evidence") or {}).get("url") for x in ev if (x.get("evidence") or {}).get("url")), None)) if ev else None}
    if ctx["trl"] is not None and ctx["trl_src"] != "register rule":
        levels["technology"] = {**levels["technology"], "level": ctx["trl"], "rule": f"stated by the {ctx['trl_src']}"}
    cat = fw["category"]
    levels["impact_category"] = {"category": cat.get("category"), "keyword": cat.get("keyword"),
                                 "url": (cat.get("evidence") or {}).get("url") or (c.get("source_url") if cat.get("category") else None)}
    reasons = [{"text": _clean(r["text"], allowed), "confidence": r["confidence"], "url": (r.get("evidence") or {}).get("url")}
               for r in fit_mod.fit(c, sigs, thesis) if (r.get("evidence") or {}).get("url") and _clean(r["text"], allowed)]
    m = memo_mod.build(conn, thesis, key, today=today)
    memo = None
    if m:
        rec = m["recommendation"]
        memo = {"decision": rec["decision"], "matched": rec.get("matched"), "because": rec["because"], "note": rec.get("note"),
                "why": [{"text": _clean(w["text"], allowed), "url": w["url"]} for w in m["why"] if _clean(w["text"], allowed)],
                "risks": [{"text": _clean(w["text"], allowed), "url": w["url"]} for w in m["risks"] if _clean(w["text"], allowed)],
                "actions": [{"text": _clean(w["text"], allowed), "url": w["url"]} for w in m["actions"] if _clean(w["text"], allowed)]}
    next_names = {k: [{"name": r["name"], "kind": r["kind"], "reason": _clean(r["reason"], allowed), "url": r["source_url"]} for r in v] for k, v in nxt.items()}
    by_type: dict[str, int] = {}
    for s in sigs:
        by_type[s["signal_type"]] = by_type.get(s["signal_type"], 0) + 1
    exp = {"company_key": key, "name": c["name"], "business_id": c.get("y_tunnus"), "founded": c.get("founded"), "country": c.get("country"),
           "group": c["group_tag"], "register_status": c.get("register_status"),
           "industry": {"code": c.get("industry_code"), "description": c.get("industry_desc")}, "company_url": c.get("source_url"),
           "signals": signals, "levels": levels, "fit_reasons": reasons, "memo": memo, "next": next_names,
           "counts": {"signals": len(sigs), "by_type": by_type, **{f"next_{k}": len(v) for k, v in nxt.items()}},
           "exported": (today.isoformat() if hasattr(today, "isoformat") else str(today or date.today().isoformat()))}
    exp["urls"] = sorted({u for u in _URL.findall(json.dumps(exp)) if u})
    return exp


def export(conn: sqlite3.Connection, thesis: dict, keys: list[str], *, today=None) -> list[dict]:
    return [e for e in (export_one(conn, thesis, k, today=today) for k in keys) if e]


# ---- verify -------------------------------------------------------------------------------------------------

def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, float) and obj.is_integer():
        yield str(int(obj))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield str(obj)


class Facts:
    """What a sentence may rely on: URLs, numbers, dates and capitalised words of one company's export."""

    def __init__(self, exp: dict):
        self.exp = exp
        self.urls = set(exp.get("urls") or [])
        blob = "\n".join(_strings({k: v for k, v in exp.items() if k != "urls"}))
        self.blob = blob.casefold()
        self.dates = set(_ISO.findall(blob))
        self.iso = {"-".join(d) for d in self.dates}
        self.months = {(y, m) for y, m, _ in self.dates}
        self.numbers = {re.sub(r"\D", "", n) for n in _NUM.findall(blob)}
        self.numbers |= {str(int(x)) for x in self.numbers if x}
        self.counts = {v for v in _count_values(exp.get("counts") or {})}
        self.caps = set(_CAP.findall("\n".join(_strings({k: v for k, v in exp.items() if k != "urls"})))) | GENERIC
        self.cited_text = {s["source_url"]: ((s.get("title") or "") + " " + (s.get("note") or "")).casefold() for s in exp.get("signals", [])}


def _count_values(d) -> list[int]:
    out = []
    for v in d.values():
        if isinstance(v, dict):
            out += _count_values(v)
        elif isinstance(v, int):
            out.append(v)
    return out


def verify_sentence(sent: dict, facts: Facts, thesis: dict | None = None) -> str | None:
    """None when the sentence passes, else the reason it fails."""
    text, cites = (sent.get("text") or "").strip(), sent.get("cites") or []
    if not text:
        return "empty sentence"
    if len(text) > MAX_CHARS:
        return f"longer than {MAX_CHARS} characters"
    if not cites:
        return "no cited url"
    raw = _RAW_TOKEN.search(_URL.sub(" ", text))
    if raw:
        return f"raw token in the sentence: {raw.group()}"
    foreign = [u for u in cites if u not in facts.urls]
    if foreign:
        return f"cited url not in the export: {foreign[0]}"
    text_wo_urls = _URL.sub(" ", text)
    for y, m, d in _ISO.findall(text_wo_urls):
        if f"{y}-{m}-{d}" not in facts.iso:
            return f"date not in the export: {y}-{m}-{d}"
    stripped = _ISO.sub(" ", text_wo_urls)
    for mname, y in _MONTH_YEAR.findall(stripped):
        if (y, f"{_MONTHS[mname.lower()]:02d}") not in facts.months:
            return f"month not in the export: {mname} {y}"
    stripped = _MONTH_YEAR.sub(lambda m: f" {m.group(2)} ", stripped)
    for n in _NUM.findall(stripped):
        digits = re.sub(r"\D", "", n)
        if digits and digits not in facts.numbers and str(int(digits)) not in facts.numbers:
            return f"number not in the export: {n.strip()}"
    for w, v in NUMBER_WORDS.items():
        if re.search(rf"\b{w}\b", text, re.I) and v not in facts.counts and str(v) not in facts.numbers:
            return f"number word not supported by the export: {w}"
    low = text.casefold()
    cited_titles = " ".join(facts.cited_text.get(u, "") for u in cites)
    for p in PRAISE:
        if re.search(rf"\b{re.escape(p)}", low) and p not in cited_titles:
            return f"praise without a source title: {p}"
    toks = list(_CAP.finditer(text_wo_urls))
    for i, t in enumerate(toks):
        w = t.group()
        first = not text_wo_urls[:t.start()].strip() or text_wo_urls[:t.start()].rstrip().endswith((".", "!", "?", ":"))
        if w not in facts.caps and not w.isupper() and not first:
            return f"capitalised word not in the export (possible name): {w}"
    for a, b in zip(toks, toks[1:]):
        if b.start() - a.end() == 1:
            if thesis is not None and (a.group() not in facts.caps or b.group() not in facts.caps) and a.group() not in GENERIC and b.group() not in GENERIC \
                    and fit_mod.looks_like_person(f"{a.group()} {b.group()} Holding Oy", thesis):
                return f"person-shaped name: {a.group()} {b.group()}"
            if a.group() not in facts.caps or b.group() not in facts.caps:
                return f"person-shaped name: {a.group()} {b.group()}"
    return None


SLOTS = (("what_it_does", "What it does"), ("thesis_fit", "Thesis fit"), ("readiness", "Readiness"), ("who_to_meet", "Who to meet"),
         ("what_the_fund_should_do", "What the fund should do"), ("whats_missing", "What's missing"))
SLOT_KEYS = tuple(k for k, _ in SLOTS)
MAX_SENTENCES_IN_SLOT = {"what_it_does": 1, "readiness": 1}      # every other slot may use two
MIN_SLOTS = 2
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_LEVEL_PAIR = re.compile(r"\b(technology|business|investment)\b[^.;\d]{0,60}?\b(\d)\b", re.I)
_DECISION_WORD = {"PORTFOLIO SUPPORT": r"portfolio support", "INVEST": r"\binvest\b", "DUE DILIGENCE": r"due diligence", "ACCELERATOR": r"accelerator", "GRANT SUPPORT": r"grant",
                  "PARTNER INTRODUCTION": r"partner", "WATCHLIST": r"watch ?list", "REJECT / LOW FIT": r"low fit|reject"}
_NEVER_AGAINST = ("PORTFOLIO SUPPORT", "INVEST", "DUE DILIGENCE", "WATCHLIST", "REJECT / LOW FIT")   # words that contradict a different verdict


def _next_names(exp: dict) -> list[str]:
    names = []
    for lst in (exp.get("next") or {}).values():
        for r in lst:
            names.append(r["name"])
            names += [p.strip() for p in re.split(r"[()/]", r["name"]) if p.strip()]
    return sorted(set(names), key=len, reverse=True)


def _check_levels(text: str, exp: dict, strict: bool) -> str | None:
    """A slot's numbers must be the export's framework levels, never recomputed."""
    levels = {d: (exp.get("levels") or {}).get(d, {}).get("level") for d in ("technology", "business", "investment")}
    for dim, n in _LEVEL_PAIR.findall(text):
        have = levels.get(dim.lower())
        if have is None:
            return f"level not in the export: {dim} has no level"
        if int(n) != have:
            return f"level differs from the export: {dim} {n}, export {have}"
    if strict:
        valid = {str(v) for v in levels.values() if v is not None}
        stripped = _MONTH_YEAR.sub(" ", _ISO.sub(" ", _URL.sub(" ", text)))
        for n in _NUM.findall(stripped):
            if re.fullmatch(r"[1-9]", n.strip()) and n.strip() not in valid:
                return f"level differs from the export: {n.strip()} is not a framework level here"
    return None


def verify_slot(name: str, slot: dict, exp: dict, facts: "Facts", thesis: dict | None = None) -> str | None:
    """None when the slot passes. Every sentence rule applies, plus the slot rules."""
    why = verify_sentence(slot, facts, thesis)
    if why:
        return why
    text = slot["text"].strip()
    pieces = [x for x in _SENT_SPLIT.split(text) if x.strip()]
    if len(pieces) > MAX_SENTENCES_IN_SLOT.get(name, 2):
        return f"slot {name} is longer than {MAX_SENTENCES_IN_SLOT.get(name, 2)} sentence(s)"
    why = _check_levels(text, exp, strict=(name == "readiness"))
    if why:
        return why
    if name == "who_to_meet":
        names = _next_names(exp)
        if not names:
            return "who_to_meet: the export has no who-comes-next names"
        rest = text
        for n in names + [exp.get("name") or ""]:
            rest = rest.replace(n, " ")
        if rest == text:
            return "who_to_meet: names none of the who-comes-next list"
        toks = list(_CAP.finditer(_URL.sub(" ", rest)))
        for t in toks:
            w = t.group()
            first = not rest[:t.start()].strip() or rest[:t.start()].rstrip().endswith((".", "!", "?", ":"))
            if w not in GENERIC and not w.isupper() and not first:
                return f"who_to_meet: name not from the who-comes-next list: {w}"
        allowed_urls = {r["url"] for lst in (exp.get("next") or {}).values() for r in lst}
        if any(u not in allowed_urls for u in slot["cites"]):
            return "who_to_meet: cited url is not a who-comes-next source"
    if name == "what_the_fund_should_do":
        dec = ((exp.get("memo") or {}).get("decision"))
        if dec:
            low = text.casefold()
            if not re.search(_DECISION_WORD[dec], low):
                return f"memo verdict {dec} is not stated"
            m = re.match(r"(row \d+|rule \w+|fallback \w+)", (exp.get("memo") or {}).get("matched") or "")
            if m and m.group(1).casefold() not in low:
                return f"memo rule not cited: {m.group(1)}"
            for other in _NEVER_AGAINST:
                if other != dec and re.search(_DECISION_WORD[other], low):
                    return f"contradicts the memo verdict {dec}: mentions {other.lower()}"
    return None


def verify_brief(brief: dict, exp: dict, thesis: dict | None = None) -> tuple[dict | None, list[dict]]:
    """(cleaned brief or None, drops [{slot, sentence, reason}]). Failing slots become null; fewer than MIN_SLOTS slots left drops the brief."""
    facts = Facts(exp)
    slots, drops = {}, []
    given = brief.get("slots") or {}
    for key in given:
        if key not in SLOT_KEYS:
            drops.append({"slot": key, "sentence": None, "reason": f"unknown slot: {key}"})
    for key in SLOT_KEYS:
        s = given.get(key)
        if s is None:
            slots[key] = None
            continue
        why = verify_slot(key, s, exp, facts, thesis)
        if why:
            drops.append({"slot": key, "sentence": s.get("text"), "reason": why})
            slots[key] = None
        else:
            slots[key] = {"text": s["text"].strip(), "cites": list(dict.fromkeys(s["cites"]))}
    if sum(1 for v in slots.values() if v) < MIN_SLOTS:
        drops.append({"slot": None, "sentence": None, "reason": f"brief dropped: {sum(1 for v in slots.values() if v)} slot(s) pass, minimum {MIN_SLOTS}"})
        return None, drops
    return {"company_key": brief["company_key"], "written": brief.get("written"), "slots": slots}, drops


# ---- store and read -----------------------------------------------------------------------------------------

def store_brief(conn: sqlite3.Connection, brief: dict) -> None:
    conn.execute("INSERT OR REPLACE INTO company_brief_slots (company_key, written, slots_json, imported_at) VALUES (?,?,?,datetime('now'))",
                 (brief["company_key"], brief.get("written") or date.today().isoformat(), json.dumps(brief["slots"], ensure_ascii=False)))


# ---- keep a stored brief true to the page (D50) ---------------------------------------------------------------
# A brief is written once and stored; the memo moves (a new rule, a new record, a new band). A stored sentence that names a verdict or
# a band level different from the memo the page shows now is dropped when the brief is rendered, and a rule id is never printed.
_RULE_AFTER_UNDER = re.compile(r"\s+under\s+(?:the\s+)?(?:fallback|rule|row|decision table row)\s+\w{1,3}\b", re.I)
_RULE_ID_LEFT = re.compile(r"\b(?:fallback|rule)\s+[a-z]\d?\b|\brow\s+\d+\b", re.I)
_BAND_WORD = r"(low|medium|high|unknown)"
_LEVEL_SAID = re.compile(r"\b(technology|business|investment) readiness\b[^.;:()\d]{0,25}?\blevel (\d)\b", re.I)


def _memo_now(memo: dict | None, thesis: dict | None) -> dict | None:
    """What the page states now: the verdict, whether it came from the fallback, and each dimension's band as the page prints it."""
    if not memo or not memo.get("recommendation"):
        return None
    rec = memo["recommendation"]
    labels = ((thesis or {}).get("memo") or {}).get("labels") or {}
    bands = {b["label"].casefold(): str(b["band"]).split(",")[0].strip().casefold() for b in rec.get("because_labels") or []}
    tech = ((memo.get("levels") or {}).get("technology") or {}).get("band")
    bands[(labels.get("technology") or "technology readiness").casefold()] = str(tech or "unknown").casefold()
    first = (rec.get("because_labels") or [{}])[0].get("label")
    specs = ((thesis or {}).get("memo") or {}).get("bands") or {}
    dims = {d: (labels.get(d) or f"{d} readiness").casefold() for d in ("technology", "business", "investment")}
    return {"decision": rec.get("decision"), "fallback": rec.get("kind") == "fallback", "bands": bands, "impact": (first or "").casefold(),
            "closed": matching.closed_calls(thesis, store._today(None)) if thesis else [],
            "dims": dims, "specs": {dims[d]: specs.get(d) for d in dims}}


def _verdict_named(sentence: str) -> str | None:
    """The verdict a sentence about the memo names: the first verdict word in it (a programme called 'accelerator' later in the
    sentence does not matter), or None."""
    low = sentence.casefold()
    hits = [(m.start(), dec) for dec, rx in _DECISION_WORD.items() if (m := re.search(rx, low))]
    return min(hits)[1] if hits else None


def stale_reason(sentence: str, slot: str, now: dict | None) -> str | None:
    """Why a stored sentence no longer matches the memo (None when it does): a different verdict, a different band for a dimension,
    'no evidence' for a dimension that now has a band, 'implied by the sector' when the verdict no longer rests on the fallback, or a
    rule id that cannot be taken out cleanly, or a who-to-meet sentence naming a programme whose call is now closed (D76)."""
    if _RULE_ID_LEFT.search(sentence):
        return "names a rule id"
    if now is None:
        return None
    low = sentence.casefold()
    if slot == "who_to_meet":
        hit = next((n for n in now.get("closed") or [] if re.search(r"(?<!\w)" + re.escape(n.casefold()) + r"(?!\w)", low)), None)
        if hit:
            return f"names {hit}, whose call is closed"
    if slot == "what_the_fund_should_do" or "memo" in low:
        named = _verdict_named(sentence)
        if named and now["decision"] and named != now["decision"]:
            return f"names verdict {named}, the memo now says {now['decision']}"
    for label, band in now["bands"].items():
        lab = re.escape(label)
        for m in re.finditer(lab + r"\b[^.;:()]{0,25}?\b" + _BAND_WORD + r"\b", low):
            if m.group(1) != band:
                return f"names {label} {m.group(1)}, the memo now says {band}"
            if label == now["impact"] and now["fallback"] and "implied" not in low:  # an evidenced Medium is not the sector-implied one
                return f"states {label} {band} without saying the memo reads it as implied by the sector"
        if band != "unknown" and re.search(r"no (?:public )?evidence for " + lab, low):
            return f"says there is no evidence for {label}, the memo now has a band"
    from radar import memo as memo_mod
    for dim, n in _LEVEL_SAID.findall(sentence):     # a level the page no longer prints (D84: a public contract sets no TRL)
        label = (now.get("dims") or {}).get(dim.casefold())
        have = now["bands"].get(label) if label else None
        spec = (now.get("specs") or {}).get(label)
        if have is None or not spec:
            continue
        said = memo_mod.band(int(n), spec).casefold()
        if said != have:
            return f"names {label} level {n}, the memo now says {have}"
    if "implied by the sector" in low and not now["fallback"]:
        return "says the impact is implied by the sector, the memo no longer reads it so"
    return None


def current_text(text: str, slot: str, now: dict | None) -> str | None:
    """A stored slot text as the page may print it: rule ids stripped where they follow 'under', every sentence that no longer matches the
    memo dropped. None when no sentence is left."""
    cleaned = _RULE_AFTER_UNDER.sub("", text or "")
    keep = [s for s in _SENT_SPLIT.split(cleaned) if s.strip() and not stale_reason(s, slot, now)]
    return " ".join(keep) or None


def current_slots(data: dict, memo: dict | None, thesis: dict | None) -> dict:
    """The stored slots {key: {text, cites} | None} with the stale sentences taken out; a slot with nothing left becomes None."""
    now = _memo_now(memo, thesis)
    out = {}
    for key, v in data.items():
        text = current_text(v["text"], key, now) if v else None
        out[key] = {"text": text, "cites": v["cites"]} if text else None
    return out


def brief_for(company_key: str, thesis: dict, memo: dict | None = None) -> dict | None:
    """Template hook: the six slots in order, each text/cites with numbers restarting at 1 per row, or None ("No summary yet").
    Sentences that contradict the memo shown now are left out (a slot that loses all of them is marked `stale` and not drawn); fewer than
    MIN_SLOTS slots left means no brief. `memo` is the page's memo (built here when the caller has none)."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        row = conn.execute("SELECT written, slots_json FROM company_brief_slots WHERE company_key=?", (company_key,)).fetchone()
        if row is not None and memo is None:
            from radar import memo as memo_mod
            memo = memo_mod.build(conn, thesis, company_key)
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    stored = json.loads(row[1])
    data = current_slots(stored, memo, thesis)
    if sum(1 for v in data.values() if v) < MIN_SLOTS:
        return None
    slots = []
    for key, label in SLOTS:
        v = data.get(key)
        slots.append({"key": key, "label": label, "text": words.rule_words(v["text"], thesis) if v else None, "stale": bool(stored.get(key)) and not v,   # rule ids in words (D36)
                      "cites": [{"n": i, "url": u} for i, u in enumerate(v["cites"], 1)] if v else []})
    return {"written": row[0], "slots": slots}


def one_liners(thesis: dict) -> dict[str, str]:
    """company_key -> the what_it_does sentence, for the one-liner on the home list. Empty when nothing is imported. No rule id is printed."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return {}
    try:
        rows = conn.execute("SELECT company_key, slots_json FROM company_brief_slots").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    out = {}
    for k, js in rows:
        v = json.loads(js).get("what_it_does")
        text = current_text(v["text"], "what_it_does", None) if v else None
        if text:
            out[k] = words.rule_words(text, thesis)
    return out


# ---- CLI ----------------------------------------------------------------------------------------------------

def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def run_dir(dir_out: Path, dir_in: Path, thesis: dict, *, conn=None, log=print) -> dict:
    """Verify every brief in dir_out against its export in dir_in; store the survivors when conn is given."""
    res = {"briefs": 0, "kept": 0, "dropped_briefs": 0, "dropped_slots": 0, "slots_kept": 0, "reasons": {}}
    for p in sorted(Path(dir_out).glob("*.json")):
        res["briefs"] += 1
        b = _load(p)
        ep = Path(dir_in) / f"{slug(b['company_key'])}.json"
        if not ep.is_file():
            log(f"DROP brief {b['company_key']}: no export {ep.name}")
            res["dropped_briefs"] += 1
            res["reasons"]["no export"] = res["reasons"].get("no export", 0) + 1
            continue
        clean, drops = verify_brief(b, _load(ep), thesis)
        for d in drops:
            kind = d["reason"].split(":")[0]
            res["reasons"][kind] = res["reasons"].get(kind, 0) + 1
            if d["slot"] is not None:
                res["dropped_slots"] += 1
            log(f"DROP {b['company_key']} [{d['slot']}]: {d['reason']}" + (f" | {d['sentence']}" if d["sentence"] else ""))
        if clean is None:
            res["dropped_briefs"] += 1
            continue
        res["kept"] += 1
        res["slots_kept"] += sum(1 for v in clean["slots"].values() if v)
        if conn is not None:
            store_brief(conn, clean)
    if conn is not None:
        conn.commit()
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.briefs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--keys", required=True, help="file with one company key per line, or 'all'")
    e.add_argument("--out", default=str(BRIEFS / "in"))
    e.add_argument("--thesis")
    for name in ("verify", "import"):
        v = sub.add_parser(name)
        v.add_argument("--dir", default=str(BRIEFS / "out"))
        v.add_argument("--exports", default=str(BRIEFS / "in"))
        v.add_argument("--thesis")
    a = ap.parse_args(argv)
    th = thesis_mod.load(thesis_mod.available().get(a.thesis, a.thesis)) if a.thesis else thesis_mod.load()
    if a.cmd == "export":
        conn = store.open_db(thesis=th)
        if conn is None:
            print(store.empty_state_text(th))
            return 1
        keys = [r[0] for r in conn.execute("SELECT company_key FROM companies ORDER BY company_key")] if a.keys == "all" else \
            [k.strip() for k in Path(a.keys).read_text().splitlines() if k.strip()]
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        n = 0
        for exp in export(conn, th, keys):
            (out / f"{slug(exp['company_key'])}.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
        print(f"exported {n} of {len(keys)} companies to {out}")
        return 0
    conn = db.connect(thesis_mod.db_path(th)) if a.cmd == "import" else None
    res = run_dir(Path(a.dir), Path(a.exports), th, conn=conn)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
