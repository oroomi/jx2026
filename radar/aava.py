"""Aava: the spoken analyst of one company page or of the feed, as a conversation. Pure functions: no database, no network, no model.

A company page has six questions in a fixed order (QUESTIONS). Each has ONE spoken answer in the first person, at most MAX_ANSWER characters,
built only from the rows the page also shows: the company record, its dated signals, the fund memo (radar.memo), the who-comes-next lists and
the decision table of the thesis file. A fact the records lack is spoken as missing, never filled in. Nothing is said about a named person.
Nothing is read out that a listener cannot use: no web address, no register or record number, no rule or capability id.

A segment is {text, target, action, source_url, sha, q}; q is the question number, sha fingerprints the text (see text_sha) and target is the
id of an element on the rendered page that the player highlights. The scripts are grouped under the old intent names (INTENTS), which stay valid
in the URL and in the voice tool: brief = question 1, why = questions 2 and 3, meet and talk = question 4, next = 5, missing = 6.
The feed has one question (FEED_QUESTIONS)."""
from __future__ import annotations

import hashlib
import itertools
import re
from datetime import date, timedelta

from radar import labels as lbl
from radar import memo as memo_mod
from radar import store

ACTIONS = ("highlight", "scroll", "count_up", "draw_timeline", "fill_level", "none")
INTENTS = ("brief", "why", "meet", "talk", "next", "missing")
# (number, intent group it lives in, the question as the owner says it)
QUESTIONS = (
    (1, "brief", "Aava, what do you think about this company?"),
    (2, "why", "What is their official score on the report?"),
    (3, "why", "How sure are you?"),
    (4, "meet", "Who should we meet, and what do we say?"),
    (5, "next", "What is the next move?"),
    (6, "missing", "What would change your mind?"),
)
FEED_QUESTIONS = ((1, "brief", "Aava, what is new on the radar?"),)
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MAX_ANSWER = 450
MAX_FEED = 600
FEED_DAYS = 7
SHA_LEN = 16
UNKNOWN = memo_mod.UNKNOWN
_DASHES = re.compile(r"\s*[–—]\s*")


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


def text_sha(text: str) -> str:
    """Fingerprint of a segment's spoken text (first 16 hex of SHA-256). The pre-rendered audio manifest (radar.aava_voice) is keyed by it,
    and the player plays a recording only when this value matches, so audio is never played over text it was not rendered from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:SHA_LEN]


def seg(text: str, target: str, action: str = "highlight", source_url: str | None = None, **extra) -> dict:
    assert action in ACTIONS
    spoken = clean(text)
    return {"text": spoken, "target": target, "action": action, "source_url": source_url, "sha": text_sha(spoken), **extra}


# ---- small speaking helpers --------------------------------------------------------------------------------------------------
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_PARENS = re.compile(r"\s*\([^)]*\)")


def _lc(text: str | None) -> str:
    """First letter lower case, unless the text starts with an acronym or a proper name written in capitals."""
    t = (text or "").strip()
    return t[:1].lower() + t[1:] if len(t) < 2 or t[1].islower() else t


def _uc(text: str) -> str:
    return text[:1].upper() + text[1:]


def _list(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else (", ".join(items[:-1]) + " and " + items[-1]) if items else ""


def _dates(text: str) -> str:
    """ISO dates inside a record's own sentence, spoken as dates."""
    return _ISO.sub(lambda m: say_date(m.group()) or m.group(), text)


def _words(band: str | None) -> str:
    return (band or UNKNOWN).lower().replace(UNKNOWN, "not known").replace("implied by sector", "implied by the sector")


def _spoken_name(name: str) -> str:
    """A listed organisation's name as it is said: no bracketed note, no second alias after a slash."""
    return _PARENS.sub("", name or "").split(" / ")[0].strip()


def _fit_parts(parts: list[tuple[int, str]], limit: int) -> str:
    """Join sentences in speaking order. (rank, text): rank 0 is kept always; when the answer is over the limit the highest rank goes first."""
    keep = [True] * len(parts)
    join = lambda: " ".join(t for (r, t), k in zip(parts, keep) if k and t)  # noqa: E731
    while len(join()) > limit:
        live = [i for i, (r, t) in enumerate(parts) if keep[i] and r > 0 and t]
        if not live:
            break
        keep[max(live, key=lambda i: (parts[i][0], i))] = False
    out = join()
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "."


# ---- what a record is, and where it came from, in words ----------------------------------------------------------------------
SPOKEN_SIGNAL = {
    "register_entry": "its register entry", "bf_funding": "Business Finland funding", "eu_project": "an EU project", "eu_grant": "an EU grant",
    "blueinvest": "a place in the BlueInvest pipeline", "patent": "a patent filing", "public_contract": "a public contract",
    "job_ad": "an open job ad", "site_customer": "a customer named on its own site", "first_sales": "first sales", "first_hire": "a first hire",
    "sales_ended": "the end of its sales", "employer_ended": "the end of its employer registration", "research_output": "a research output",
    "website_first_seen": "its website first seen", "website_milestone": "a website milestone", "pilot_named": "a first customer or pilot named",
    "certification": "a certification or type approval", "programme_entry": "an accelerator or programme entry",
    "exhibitor": "an exhibitor or demo appearance", "award": "an award or pitch win", "funding_round": "a funding round",
    "product_launch": "a product launch", "public_funding": "a grant or public funding", "ecosystem_event": "another dated event",
    "startup_notice": "a start-up notification", "board_change": "a board change", "equity_event": "a share issue",
    "capital_loss": "a loss of share capital",
}
# adapter -> (class, where it is said). class: register = an official register or public body states it; declared = a member list or a
# programme says it; read = read from a web page by a model and checked by code, or kept in an archive.
SOURCE_SPOKEN = {
    "prh": ("register", "in the Finnish company register"), "prh_intake": ("register", "in the Finnish company register"),
    "prh_recent": ("register", "in the Finnish company register"), "prh_notices": ("register", "in the Finnish company register's notices"),
    "tax_registers": ("register", "in the Finnish tax registers"), "hilma": ("register", "in a Finnish public procurement notice"),
    "businessfinland": ("register", "in Business Finland's funding export"), "cordis": ("register", "in the EU's CORDIS project database"),
    "eu_grants": ("register", "in the EU grants records"), "ted": ("register", "in EU tender award notices"),
    "openalex": ("register", "in OpenAlex research records"), "brreg": ("register", "in the Norwegian business register"),
    "cvr": ("register", "in the Danish business register"), "estonia_register": ("register", "in the Estonian business register"),
    "ecosystem": ("declared", "in the declared ecosystem research"), "declared": ("declared", "in a declared list"),
    "blueinvest": ("declared", "in the BlueInvest pipeline"),
    "stitcher": ("read", "read by an AI from its own pages and checked by code"), "webarchive": ("read", "in the Internet Archive"),
}


def _spoken_eco(m: re.Match) -> str:
    """The ecosystem dataset's terse reason ("caps ['C10']; kw []; stage 1.0") in words: the capabilities by their labels (never the
    codes), keeping the stage and impact numbers."""
    from radar import matching
    caps = [c.strip(" '\"") for c in m.group(1).split(",") if c.strip(" '\"")]
    kws = [k.strip(" '\"") for k in m.group(2).split(",") if k.strip(" '\"")]
    bits = []
    if caps:
        bits.append("shared capabilities " + (matching.plain_list(matching.cap_names(caps)) or "in the declared dataset"))
    if kws:
        bits.append("shared keywords " + ", ".join(kws))
    bits.append(f"stage fit {m.group(3)}")
    if m.group(4):
        bits.append(f"impact score {m.group(4)}")
    return "; ".join(bits)


def _source(s: dict) -> tuple[str, str]:
    known = SOURCE_SPOKEN.get(s.get("adapter") or "")
    return known or ("other", "in " + lbl.source_label(s.get("adapter"), s.get("source_url")))


def _what(s: dict) -> str:
    return SPOKEN_SIGNAL.get(s.get("signal_type") or "") or _lc(s.get("type_label") or lbl.signal_label(s.get("signal_type")))


def _when(s: dict) -> str:
    """The date as the record states it: a day, a month when the source gave only the month, or a year."""
    d = s.get("date") or ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return "at a date not in the records"
    if s.get("date_precision") == "year":
        return f"in {d[:4]}"
    if re.search(r"month only", s.get("detail") or "", re.I):
        return f"in {MONTHS[int(d[5:7]) - 1]} {d[:4]}"
    return f"on {say_date(d)}" if say_date(d) else "at a date not in the records"


def _records(sigs: list[dict], with_source: bool = True) -> str:
    """'a share issue on 17 August 2026 and a first hire in April 2025, both in the Finnish company register'."""
    bits = [f"{_what(s)} {_when(s)}" for s in sigs]
    where = {_source(s)[1] for s in sigs}
    if with_source and len(where) == 1 and len(sigs) > 1:
        return f"{_list(bits)}, {'both' if len(sigs) == 2 else 'all'} {where.pop()}"
    if with_source:
        bits = [f"{b}, {_source(s)[1]}" for b, s in zip(bits, sigs)]
        return "; and ".join(bits) if len(bits) == 2 else "; ".join(bits)
    return _list(bits)


_CONF = ("high", "medium", "low")


def _strongest(signals: list[dict], counted, n: int = 2) -> tuple[str | None, list[dict]]:
    """The records that count most: the newest of each type, from the highest confidence tier that has any. Only the signal types the
    thesis counts (feed_signal_types) are considered; a bare register entry only when nothing else exists."""
    pool = [s for s in signals if s.get("date") and (counted is None or s.get("signal_type") in counted)]
    for conf in _CONF:
        tier = sorted((s for s in pool if s.get("confidence") == conf and s["signal_type"] != "register_entry"), key=lambda s: s["date"], reverse=True)
        if tier:
            out, seen = [], set()
            for s in tier:
                if s["signal_type"] not in seen:
                    seen.add(s["signal_type"])
                    out.append(s)
            return conf, out[:n]
    bare = [s for s in pool if s["signal_type"] == "register_entry"]
    return ("high", bare[:1]) if bare else (None, [])


def _distinct_newest(sigs: list[dict], n: int, skip=("board_change", "register_entry")) -> list[dict]:
    out, seen = [], set()
    for s in sorted(sigs, key=lambda s: s["date"], reverse=True):
        if s["signal_type"] not in seen and s["signal_type"] not in skip:
            seen.add(s["signal_type"])
            out.append(s)
    return out[:n]


# ---- the decision table: what would change the verdict ------------------------------------------------------------------------
WHATIF_DIMS = ("fit", "impact", "business", "investment", "technology")
_BANDS = memo_mod.BANDS


def what_if(memo: dict | None, thesis: dict | None) -> dict | None:
    """Re-read the thesis's own decision table (radar.memo.decide) with one band, or two, changed: {current, bands, single, pairs, labels}.
    single = {dimension: {band: decision}}; pairs = [((dim, band), (dim, band), decision)]. None when there is no table, or when the
    table does not reproduce the memo's own verdict (a defunct company, for example), so nothing is claimed that the code does not do."""
    if not memo or not thesis:
        return None
    cfg = memo_mod._cfg(thesis)
    rec = memo["recommendation"]
    lv = {d: ((memo.get("levels") or {}).get(d) or {}).get("band", UNKNOWN) for d in WHATIF_DIMS}
    support = frozenset((cfg.get("fallback") or {}).get("requires_any") or ["declared_member"]) if rec.get("kind") == "fallback" else frozenset()

    def decision(bands: dict) -> str:
        row, _ = memo_mod.decide(bands, cfg, support)
        return row["decision"] if row else "WATCHLIST"

    if decision(lv) != rec["decision"]:
        return None
    single = {d: {b: decision({**lv, d: b}) for b in _BANDS if b != lv[d]} for d in WHATIF_DIMS}
    pairs = [((d1, b1), (d2, b2), decision({**lv, d1: b1, d2: b2}))
             for d1, d2 in itertools.combinations(WHATIF_DIMS, 2) for b1 in _BANDS for b2 in _BANDS if b1 != lv[d1] and b2 != lv[d2]]
    return {"current": rec["decision"], "bands": lv, "single": single, "pairs": pairs,
            "labels": {d: (cfg["labels"].get(d) or d) for d in WHATIF_DIMS}}


_RANK = {d: i for i, d in enumerate(memo_mod.DECISIONS)}


def _closeness(cur: str, b: str) -> int:
    return abs(_BANDS.index(b) - _BANDS.index(cur)) if cur in _BANDS else 2 - _BANDS.index(b)  # an unknown level: High is tried first


def _cond(wi: dict, changes: list[tuple[str, str]]) -> str:
    """The changes as a clause that follows 'if': 'thesis fit fell to medium', 'a record put ocean impact at high'."""
    known, unknown = [], []
    for dim, b in changes:
        label, cur = _lc(wi["labels"][dim]), wi["bands"][dim]
        if cur == UNKNOWN:
            unknown.append(f"{label} at {b.lower()}")
        else:
            known.append(f"{label} {'fell' if _BANDS.index(b) < _BANDS.index(cur) else 'rose'} to {b.lower()}")
    out = ([("a record put " if len(unknown) == 1 else "records put ") + " and ".join(unknown)] if unknown else []) + known
    return " and ".join(out)


def _moves(wi: dict, better: bool) -> list[tuple[list[tuple[str, str]], str]]:
    """Changes that move the verdict down (or up), fewest changes first, then dimension priority and the smallest step; one per new verdict."""
    cur = _RANK[wi["current"]]
    found = []
    for dim in WHATIF_DIMS:
        for b, dec in sorted(wi["single"][dim].items(), key=lambda kv: _closeness(wi["bands"][dim], kv[0])):
            if (_RANK[dec] < cur) if better else (_RANK[dec] > cur):
                found.append(([(dim, b)], dec))
    if not found:
        for a, b, dec in wi["pairs"]:
            if (_RANK[dec] < cur) if better else (_RANK[dec] > cur):
                found.append(([a, b], dec))
    out, seen = [], set()
    for ch, dec in found:
        if dec not in seen:
            seen.add(dec)
            out.append((ch, dec))
    return out


def _outcomes(wi: dict, dim: str) -> str:
    """What a record on one level would do: bands grouped by the verdict they lead to."""
    groups: dict[str, list[str]] = {}
    for b in reversed(_BANDS):
        if b in wi["single"][dim]:
            groups.setdefault(wi["single"][dim][b], []).append(b.lower())
    if len(groups) == 1 and wi["current"] in groups:
        return f"a record on {_lc(wi['labels'][dim])} would not change the verdict by itself"
    cur = _RANK[wi["current"]]
    bits = []
    for dec, bands in groups.items():
        where = "at any level" if len(bands) == 3 else "at " + " or ".join(bands)
        verb = f"it stays {_dec(dec)}" if dec == wi["current"] else f"it {'moves up to' if _RANK[dec] < cur else 'drops to'} {_dec(dec)}"
        bits.append(f"{where} {verb}")
    return f"a record on {_lc(wi['labels'][dim])} would settle it: " + "; ".join(bits)


# ---- the verdict in words ------------------------------------------------------------------------------------------------------
OPINION = {
    "INVEST": "it deserves an investment conversation",
    "DUE DILIGENCE": "it deserves a proper due diligence look",
    "ACCELERATOR": "it is a good accelerator candidate",
    "GRANT SUPPORT": "it is a case for grants and incubation support",
    "PARTNER INTRODUCTION": "it needs introductions to pilot customers and strategic partners",
    "WATCHLIST": "we should watch, not call",
    "REJECT / LOW FIT": "we should pass, because it does not fit the thesis",
}


def _dec(decision: str) -> str:
    return "reject for low fit" if decision == "REJECT / LOW FIT" else decision.lower()


def _target(memo: dict | None, alt: str = "q2") -> str:
    return "memo" if memo else alt


def _first_url(memo: dict | None) -> str | None:
    return next((w.get("url") for w in (memo or {}).get("why") or [] if w.get("url")), None)


def _gap_clause(text: str) -> str:
    """One memo risk as a short spoken clause: 'No public evidence for ocean impact (note)' -> 'no evidence for ocean impact'."""
    t = clean(_PARENS.sub("", text or "")).rstrip(".")
    t = re.sub(r"^No public evidence for ", "no evidence for ", t)
    t = re.sub(r"^No public (.+?) evidence$", r"no \1 evidence", t)
    t = re.sub(r"^(.+?) is Low on the stored evidence$", lambda m: f"{_lc(m.group(1))} is only low", t)
    return _lc(t)


def _gaps(memo: dict | None, limit: int = 3) -> list[str]:
    """The memo's evidence gaps as short spoken clauses, in its own order, without the bracketed notes."""
    rec = (memo or {}).get("recommendation") or {}
    if rec.get("needs"):
        return ["no evidence yet for " + _list([_lc(n) for n in rec["needs"]])]
    out = []
    for k in (memo or {}).get("risks") or []:
        t = _gap_clause(k.get("text") or "")
        if t and t not in out:
            out.append(t)
    return out[:limit]


# ---- the six answers -----------------------------------------------------------------------------------------------------------
def _line_of_business(c: dict) -> str:
    desc = (c.get("industry_desc") or "").strip()
    year = (c.get("founded") or "")[:4]
    year = year if re.match(r"^\d{4}$", year) else ""
    if desc and year:
        return f"Its registered line of business is {_lc(desc)}, and it has been on the register since {year}."
    if desc:
        return f"Its registered line of business is {_lc(desc)}. No public record of when it was registered."
    if year:
        return f"No public record of its line of business. It has been on the register since {year}."
    return "No public record of its line of business or of when it was registered."


def think(c: dict, signals: list[dict], memo: dict | None, counted=None) -> dict:
    """1. What do you think about this company: the verdict as an opinion, with the facts behind it."""
    rec = (memo or {}).get("recommendation") or {}
    opinion = OPINION.get(rec.get("decision"), "the record is too thin for me to give a verdict")
    conf, top = _strongest(signals, counted)
    watch = rec.get("decision") == "WATCHLIST"
    parts: list[tuple[int, str]] = [(0, f"Based on what the radar holds on {c['name']}, I think {opinion}{', and here is why:' if watch else '.'}")]
    if watch:
        bits = []
        if rec.get("needs"):
            bits.append("there is no public evidence yet for " + _list([_lc(n) for n in rec["needs"]]))
        lows = [_lc(x["label"]) for x in rec.get("because_labels") or [] if x.get("band") == "Low"]
        if lows:
            bits.append(f"{_list(lows)} {'is' if len(lows) == 1 else 'are'} only low")
        if not bits and rec.get("note"):
            bits.append(_lc(_plain(clean(rec["note"]).rstrip("."))))
        if bits:
            parts[0] = (0, parts[0][1] + " " + ", and ".join(bits) + ".")
        else:
            parts[0] = (0, f"Based on what the radar holds on {c['name']}, I think {opinion}.")
    parts.append((0, _line_of_business(c)))
    if top:
        one = len(top) == 1
        lead = ("The strongest record is" if one else "The strongest records are") if conf == "high" else \
            f"Only {conf}-confidence {'record' if one else 'records'} so far:"
        parts.append((1, f"{lead} {_records(top)}."))
    else:
        parts.append((1, "The radar holds no dated signal for it yet."))
    dated = [s for s in signals if s.get("date")]
    last = max(dated, key=lambda s: s["date"], default=None)
    if last and not any(s["date"] == last["date"] for s in top):
        parts.append((2, f"The latest record on file is {_what(last)} {_when(last)}."))
    url = (top[0].get("source_url") if top else None) or c.get("source_url")
    return seg(_fit_parts(parts, MAX_ANSWER), "aava-who", "highlight", url, q=1)


def _plain(text: str) -> str:
    """A memo sentence in spoken form: band words in lower case, no 'declared dataset', no rule ids."""
    t = re.sub(r"\b(High|Medium|Low)\b", lambda m: m.group().lower(), text)
    return t.replace("declared dataset", "declared list")


_LEVEL_OF = 9  # the Ocean Impact Navigator and the other readiness scales on the page run 1 to 9


def _ocean_area(oi: dict) -> str:
    v = oi.get("area_label") or oi.get("area") or oi.get("area_name") or oi.get("category_label") or oi.get("category")
    if isinstance(v, dict):
        v = v.get("label") or v.get("name")
    t = re.sub(r"^[A-Za-z]{0,3}\d+(?:\.\d+)*\s+", "", clean(_PARENS.sub("", str(v or ""))))
    return "" if not t or re.fullmatch(r"[\w.\-]*\d[\w.\-]*", t) else _lc(t)


def _ocean_words(memo: dict, bands: dict) -> str:
    """Ocean impact first. The parallel branch's memo["ocean_impact"] (area, level, band, confidence) when it exists, else the impact band."""
    oi = memo.get("ocean_impact") if isinstance(memo.get("ocean_impact"), dict) else None
    plain = (bands.get("impact") or {}).get("band")
    if oi:
        area, level, band = _ocean_area(oi), oi.get("level"), oi.get("band") or plain
        conf = oi.get("confidence")
        conf = conf.strip().lower() if isinstance(conf, str) and re.fullmatch(r"[A-Za-z ]+", conf.strip()) else ""
        if isinstance(level, int) and not isinstance(level, bool):
            rating = f"level {level} of {_LEVEL_OF}" + ("" if oi.get("band") else ", not yet evidenced")
        elif band and band != UNKNOWN:
            rating = f"the {_words(band)} band, with no level on record"
        else:
            rating = "no level on record"
        return (f"On ocean impact the report puts it {'in ' + area + ', ' if area else ''}at {rating}"
                + (f", with {conf} confidence" if conf else "") + ".")
    if not plain or plain == UNKNOWN:
        return "On ocean impact there is no public evidence, so the report has no level for it."
    if "implied" in plain:
        return f"On ocean impact the band is {plain.split(',')[0].lower()}, implied by the sector, since nothing was measured."
    return f"On ocean impact the report puts it at the {_words(plain)} band."


def _plain_rule(rec: dict) -> str:
    """Which rule fired, said plainly from the memo's own sentence, with its id left out."""
    note = clean(rec.get("note") or "").rstrip(".")
    kind = rec.get("kind")
    if kind == "fallback":
        core = re.sub(r",?\s*(?:and )?fallback \S+ of the decision rules applies$", "", note)
        core = re.sub(r",\s*so impact is read as .*$", "", core).replace("; ", ", and ")
        return "The rule that fired is the table's fallback: " + _lc(_plain(core)) + "."
    if kind == "row":
        return "The rule that fired is a row of the team's decision table that matches all four bands exactly."
    if kind == "rule":
        cond = _lc(_plain((rec.get("table_action") or "").rstrip(".")))
        return "The rule that fired is a condition rule of the team's decision table" + (f": {cond}." if cond else ".")
    m = re.match(r"more public evidence needed: (.*)$", note)
    if m:
        body, extra = m.group(1), ""
        paren = re.search(r"\s*\((.*)\)$", body)
        if paren:
            body, extra = body[:paren.start()], f", and {_lc(paren.group(1))}"
        needs = [_lc(n.strip()) for n in body.split(",")]
        return f"No row or rule of the table matched, because the code still needs public evidence for {_list(needs)}{extra}."
    if note:
        return _uc(_plain(note)) + "."
    return ""


def score(memo: dict | None) -> dict:
    """2. What is their official score on the report: there is no single number, so ocean impact first, then the verdict, the bands and the rule."""
    if not memo:
        return seg("There is no report for this company in this radar, so there is no verdict or score for me to read.", "q2", "highlight", None, q=2)
    rec = memo["recommendation"]
    bands = {d: x for d, x in zip(memo_mod.TABLE_DIMS, rec.get("because_labels") or [])}
    pick = lambda d: f"{_lc(bands[d]['label'])} is {_words(bands[d]['band'])}" if d in bands else None  # noqa: E731
    action = (rec.get("table_action") or "").rstrip(".")
    verdict = f"The verdict is {_dec(rec['decision'])}" + (f": {_lc(action)}." if action and rec.get("kind") != "rule" else ".")
    got = [p for p in (pick("fit"), pick("business")) if p]
    parts = [(0, _ocean_words(memo, bands)), (0, verdict),
             (0, (_uc(_list(got)) + ".") if got else ""),
             (0, _plain_rule(rec)),
             (0, "It is a rule the code checks, not my mood, and the report has no single number by design.")]
    return seg(_fit_parts(parts, MAX_ANSWER), _target(memo), "highlight", _first_url(memo), q=2)


def _member(c: dict) -> str | None:
    return {"cohort": "a Nordic Blue cohort company", "portfolio": "a Redstone portfolio company"}.get(c.get("group_tag") or "")


def sure(c: dict, signals: list[dict], memo: dict | None, wi: dict | None, counted=None) -> dict:
    """3. How sure are you: verified in a register, declared by a member list or programme, weak or missing, and what would drop the verdict."""
    pool = [s for s in signals if s.get("date") and (counted is None or s.get("signal_type") in counted)]
    official = _distinct_newest([s for s in pool if _source(s)[0] == "register" and s.get("confidence") == "high"], 2)
    declared = _distinct_newest([s for s in pool if _source(s)[0] == "declared" and s.get("confidence") in ("high", "medium")], 1)
    weak = _distinct_newest([s for s in pool if s.get("confidence") == "low"], 1)
    parts: list[tuple[int, str]] = []
    status = (c.get("register_status") or "").strip()
    if status or official:
        head = f"it is {status}" if status else "they hold records"
        parts.append((0, f"I am surest of what the registers state: {head}" + (f", with {_records(official, False)}." if official else ".")))
    else:
        parts.append((0, "I am not sure of much: nothing here is verified in an official register."))
    said = ([_member(c)] if _member(c) else [])
    if said or declared:
        parts.append((1, "Only declared: " + (f"it is {said[0]}" if said else "the records say")
                      + (f", with {_records(declared, False)}." if declared else ".")))
    gaps = _gaps(memo, 2)
    if gaps:
        parts.append((1, "Weak or missing: " + _list(gaps) + "."))
    if weak:
        parts.append((2, _uc(f"{_records(weak, False)} is only low confidence") + "."))
    if wi:
        down = _moves(wi, better=False)[:2]
        if down:
            first = f"I would drop it to {_dec(down[0][1])} if {_cond(wi, down[0][0])}"
            second = f", or to {_dec(down[1][1])} if {_cond(wi, down[1][0])}" if len(down) > 1 else ""
            parts.append((0, first + second + "."))
        else:
            parts.append((0, "I see no change in the table that would drop the verdict further."))
    else:
        parts.append((0, "I have no decision table to test the verdict against."))
    url = (official[0].get("source_url") if official else None) or c.get("source_url")
    return seg(_fit_parts(parts, MAX_ANSWER), "signals", "highlight", url, q=3)


_KIND = {"vc": "venture capital", "org": "organisation"}


def _kind_words(kind: str | None) -> str:
    """The list's own kind ('investor vc', 'public funder') as a noun phrase with its article."""
    toks = [_KIND.get(t, t) for t in (kind or "").split()]
    if len(toks) > 1 and toks[0] == "investor":
        toks = toks[1:] + ["investor"]
    phrase = " and ".join(toks) if len(toks) > 1 and set(toks) <= {"accelerator", "incubator"} else " ".join(toks)
    return f"{'an' if phrase[:1] in 'aeiou' else 'a'} {phrase}" if phrase else "a listed organisation"


def _talking_point(reason: str | None) -> str:
    """What to say, from the row's own reason: the shared focus and the stage fit. The dataset's capability codes and match scores stay out."""
    t = clean(reason or "")
    m = re.match(r"Shares (.+?) with the company(.*)$", t)
    if m:
        caps = [_lc(re.sub(r"^C\d+\s+", "", p).strip()) for p in re.split(r"\s+and\s+(?=C\d+\b)", m.group(1))][:2]
        bits = ["open with the shared focus on " + (caps[0] if len(caps) == 1 else f"{caps[0]}, and also {caps[1]}")]
        if "stage fits" in m.group(2):
            bits.append("say the company's stage fits what they back")
        elif "stage overlap partial" in m.group(2):
            bits.append("note that its stage only partly overlaps theirs")
        elif "stage does not overlap" in m.group(2):
            bits.append("test the stage first, because it does not overlap theirs")
        return _uc(", and ".join(bits)) + "."
    t = _dates(t).rstrip(".")
    return _uc(t) + "." if t and not re.search(r"\d{3,}|dataset|keyword", t) else ""


def meet(nxt: dict | None, memo: dict | None) -> dict:
    """4. Who should we meet, and what do we say: the organisations the memo's actions name, else the best matches, with a talking point each."""
    rows = [(r, kind) for key, kind in (("investors", "investor"), ("funding", "programme or funder"), ("partners", "partner")) for r in (nxt or {}).get(key) or []]
    rec = (memo or {}).get("recommendation") or {}
    picks: list[dict] = []
    for a in (memo or {}).get("actions") or []:
        hit = max((r for r, _ in rows if r["name"] in a.get("text", "") and r not in picks), key=lambda r: len(r["name"]), default=None)
        if hit:
            picks.append(hit)
    watching = rec.get("decision") in ("WATCHLIST", "REJECT / LOW FIT")
    if not picks or watching:
        scored = sorted((r for r, _ in rows if r.get("score") is not None), key=lambda r: -r["score"])
        picks = scored[:2] or [r for r, _ in rows][:2]
    picks = picks[:2]
    if not picks:
        return seg("The radar has no investor, programme or partner match for this company yet, so I have nobody to point you to.", "q3", "highlight", None, q=4)
    parts: list[tuple[int, str]] = []
    if watching:
        parts.append((0, "I would not take a meeting yet."))
    for i, r in enumerate(picks):
        lead = ("When the evidence arrives, the closest match is" if i == 0 else "Then") if watching else ("I would start with" if i == 0 else "Then")
        say = _talking_point(r.get("reason"))
        parts.append((0 if i == 0 else 1, f"{lead} {_spoken_name(r['name'])}, {_kind_words(r.get('kind'))}." + (f" What to say: {_lc(say)}" if say else "")))
        if r.get("deadline"):
            parts.append((1, f"Its deadline is {say_date(r['deadline']) or r['deadline']}."))
    return seg(_fit_parts(parts, MAX_ANSWER), "q3", "highlight", picks[0].get("source_url"), q=4)


def _action_words(text: str, names: list[str]) -> str:
    """One of the memo's actions or the table's next step as an imperative clause: organisation names without their brackets, dates as dates."""
    for n in sorted(names, key=len, reverse=True):
        text = text.replace(n, _spoken_name(n))
    text = re.sub(r"\s*\(deadline: ([^)]*)\)", lambda m: ", which states no deadline" if m.group(1) == "not stated" else f", deadline {m.group(1)}", text)
    text = re.sub(r"\s*\((\d{4}-\d{2}-\d{2})\)", r", dated \1", text)
    text = re.sub(r"\s*\(latest on file: (\d{4}-\d{2}-\d{2})\)", r", the latest on file being \1", text)
    text = re.sub(r"^Watch: ", "", text)
    text = re.sub(r"^Check in: ", "Check in, with ", text)
    text = re.sub(r"^Meet now: judge", "Meet now to judge", text)
    text = _PARENS.sub("", text) if "Revisit" not in text else text
    if re.match(r"(Introduce|Point) them to ", text):
        text = text.split(": ", 1)[0]
    m = re.match(r"(Revisit when the radar finds public evidence for): (.*)$", text)
    if m:
        text = f"{m.group(1)} {_list([_lc(x.strip()) for x in m.group(2).split(',')])}"
    return _dates(clean(text)).rstrip(".")


def next_move(step: dict | None, memo: dict | None, nxt: dict | None) -> dict:
    """5. What is the next move: the decision table's step when it has one (rules 1 to 4), then the memo's actions, the dated one first."""
    names = [r["name"] for k in ("investors", "funding", "partners") for r in (nxt or {}).get(k) or []]
    rec = (memo or {}).get("recommendation") or {}
    acts = [(_action_words(a["text"], names), a.get("url")) for a in (memo or {}).get("actions") or [] if a.get("text")]
    acts.sort(key=lambda a: 0 if re.search(r"before .*\d{4}|deadline \d", a[0]) else 1)
    moves: list[tuple[str, str | None]] = []
    if step and step.get("rule") in (1, 2, 3, 4) and step.get("sentence"):
        moves.append((_action_words(step["sentence"], names), step.get("source_url")))
    for text, u in acts:
        if text.lower() not in {m[0].lower() for m in moves}:
            moves.append((text, u))
    moves = moves[:2]
    parts: list[tuple[int, str]] = []
    if rec.get("decision") == "WATCHLIST":
        parts.append((0, "No call yet."))
    for i, (text, _u) in enumerate(moves):
        parts.append((0 if i == 0 else 1, f"{'The next move is to' if i == 0 else 'After that,'} {_lc(text)}."))
    url = next((u for _t, u in moves if u), None)
    dated = any(re.search(r"\b\d{4}\b", t) for t, _ in moves)
    why_now = next((w for w in (memo or {}).get("why") or [] if w.get("text", "").startswith("Why now: ")), None)
    if not moves:
        parts.append((0, "The records give no sourced next step yet" + (", so I would not invent one." if not why_now else ".")))
    if why_now and not dated:
        parts.append((1, "One dated item is on file: " + _dates(clean(_PARENS.sub("", why_now["text"].removeprefix("Why now: ")))) + "."))
        url = url or why_now.get("url")
    return seg(_fit_parts(parts, MAX_ANSWER), "q4", "highlight", url, q=5)


def _alone(labels: list[str]) -> str:
    return f"A record on {' or '.join(labels)} alone would not change the verdict." if len(labels) <= 2 else \
        "A record on any one of the others alone would not change the verdict."


def change(memo: dict | None, wi: dict | None) -> dict:
    """6. What would change your mind: the records that are missing, and what a new record would do to the verdict."""
    if not memo:
        return seg("With no report on this company, any new record would start the reading from nothing.", "q2", "highlight", None, q=6)
    gaps = _gaps(memo, 3)
    parts: list[tuple[int, str]] = []
    missing = [g for g in gaps if g.startswith("no ")]
    if missing:
        parts.append((0, "What I am missing: " + _list(missing) + "."))
    weak = [g for g in gaps if not g.startswith("no ")]
    if weak:
        parts.append((1, _uc(_list(weak)) + "."))
    if wi:
        unk = [d for d in WHATIF_DIMS if wi["bands"][d] == UNKNOWN]
        moves = [d for d in unk if any(_RANK[v] != _RANK[wi["current"]] for v in wi["single"][d].values())]
        inert = [_lc(wi["labels"][d]) for d in unk if d not in moves]
        for n, dim in enumerate(moves[:2]):
            parts.append((0 if n == 0 else 1, _uc(_outcomes(wi, dim)) + "."))
        if inert and moves:
            parts.append((2, _alone(inert)))
        if not moves:
            up = _moves(wi, better=True)[:1]
            if up and len(up[0][0]) > 1:
                parts.append((0, "No single new record would change the verdict by itself."))
            if up:
                parts.append((0, f"It would move to {_dec(up[0][1])} if {_cond(wi, up[0][0])}."))
            elif _RANK[wi["current"]] == 0:
                parts.append((0, "It already has the strongest verdict the table gives, so only a fall would change my mind."))
            else:
                parts.append((0, "No single new record would move the verdict under this table."))
    if not parts:
        parts.append((0, "The memo lists no evidence gap against the levels this sector reads."))
    return seg(_fit_parts(parts, MAX_ANSWER), _target(memo), "highlight", next((k.get("url") for k in memo.get("risks") or [] if k.get("url")), None), q=6)


def company_groups(c: dict, signals: list[dict], *, nxt: dict | None = None, step: dict | None = None, memo: dict | None = None,
                   thesis: dict | None = None) -> dict:
    """Every intent group at once, embedded in the page so a tap plays it with no request (speech starts inside the tap)."""
    counted = frozenset(thesis.get("feed_signal_types") or []) if thesis and thesis.get("feed_signal_types") else None
    wi = what_if(memo, thesis)
    q1, q2 = think(c, signals, memo, counted), score(memo)
    q3, q4 = sure(c, signals, memo, wi, counted), meet(nxt, memo)
    q5, q6 = next_move(step, memo, nxt), change(memo, wi)
    return {"brief": [q1], "why": [q2, q3], "meet": [q4], "talk": [q4], "next": [q5], "missing": [q6]}


def company_script(c: dict, signals: list[dict], intent: str = "brief", **kw) -> dict:
    """The segments of one intent group (the endpoint /aava/script/<key>?intent=)."""
    return {"kind": "company", "title": f"Ask Aava about {c['name']}", "intent": intent, "segments": company_groups(c, signals, **kw)[intent]}


# ---- the feed ----------------------------------------------------------------------------------------------------------------------
def feed_script(rows: list[dict], limit: int = 5, today=None) -> dict:
    """'What is new this week': four or five companies of the feed, newest first, each with its line of business in words and the date of its
    record. Only records from the last FEED_DAYS days are called this week; when there are none the answer says so and names the newest."""
    t = store._today(today)
    if not rows:
        return {"kind": "feed", "title": "Ask Aava what is new", "intent": "brief",
                "segments": [seg("No public record in this window.", "feed-rows", "none", None, q=1)]}
    cut = (t - timedelta(days=FEED_DAYS)).isoformat()
    fresh = [r for r in rows if (r.get("date") or "") >= cut]
    newest = say_date(rows[0].get("date")) or "an earlier date"
    if fresh:
        opener = "Here is what is new this week."
    else:
        opener = f"Here are the newest records on the radar, the latest from {newest}."
    chosen = (fresh + [r for r in rows if r not in fresh])[:limit]
    out, used = [], 0
    for r in chosen:
        desc = _lc((r.get("industry_desc") or "").strip())
        where = f", in {desc}" if desc else ", with no line of business on record"
        text = f"{r['name']}{where}: {_what(r)} {_when(r)}."
        text = f"{opener} {text}" if not out else text
        if out and used + len(text) > MAX_FEED:
            break
        used += len(text) + (1 if out else 0)
        out.append(seg(text, f"aava-feed-{r['company_key']}", "highlight", r.get("source_url"), q=1))
    return {"kind": "feed", "title": "Ask Aava what is new", "intent": "brief", "segments": out}
