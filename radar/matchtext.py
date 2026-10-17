"""Matchmaking text tools: the matching config read from the thesis, word stems, keyword groups. No sector word lives here: the groups,
stop words and region words all come from `matching:` in the thesis file (PROJECT_RULES D22 to D24).

A stem is the first `stem_len` letters of a longer word, so aquaculture and aquacultural share one. A keyword-group stem matches a word that
starts with it (5 letters or more) or equals it (shorter), and a stem with a space is a phrase."""
from __future__ import annotations

import re
from datetime import date

_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)
REQUIRED = ("weights", "kinds", "kind_by_type", "path_kinds", "keyword_groups")


def config(thesis: dict) -> dict | None:
    """The matching config of a thesis, normalised once, or None when the thesis has no matchmaking section."""
    m = thesis.get("matching") or {}
    if not all(m.get(k) for k in REQUIRED):
        return None
    hit = m.get("_cfg")
    if hit is not None:
        return hit
    cfg = dict(m)
    cfg["stop"] = {str(w).casefold() for w in m.get("stop_words") or []} | {str(w).casefold() for w in thesis.get("keyword_stop_words") or []}
    cfg["stem_len"] = int(m.get("stem_len", 6))
    cfg["min_word_len"] = int(m.get("min_word_len", 4))
    cfg["groups"] = {g["id"]: g for g in m["keyword_groups"]}
    cfg["_rx"] = {g["id"]: [(s, _stem_regex(str(s).casefold())) for s in g["stems"]] for g in m["keyword_groups"]}
    cfg["region_rx"] = sorted(((str(k).casefold(), re.compile(rf"(?<!\w){re.escape(str(k).casefold())}(?!\w)"), v)
                               for k, v in (m.get("regions") or {}).items()), key=lambda t: -len(t[0]))
    m["_cfg"] = cfg
    return cfg


def _stem_regex(s: str) -> re.Pattern:
    last = re.split(r"[\s-]+", s)[-1]
    tail = r"\w*" if len(last) >= 5 else r"(?!\w)"
    return re.compile(rf"(?<!\w){re.escape(s)}{tail}", re.UNICODE)


def words(text: str | None) -> list[str]:
    return [w for w in _WORD.findall((text or "").casefold())]


def stem(word: str, cfg: dict) -> str:
    return word[: cfg["stem_len"]]


def stems(text: str | None, cfg: dict) -> dict[str, str]:
    """{stem: first full word seen} for the words of a text, leaving out stop words and words shorter than min_word_len."""
    out: dict[str, str] = {}
    for w in words(text):
        if len(w) < cfg["min_word_len"] or w in cfg["stop"] or w.endswith("-"):
            continue
        out.setdefault(stem(w, cfg), w)
    return out


def group_hits(text: str | None, cfg: dict) -> dict[str, list[str]]:
    """{group id: the words or phrases of the text that start a group stem}, for the groups the text touches."""
    t = " ".join(words(text))
    out: dict[str, list[str]] = {}
    for gid, rxs in cfg["_rx"].items():
        found = []
        for s, rx in rxs:
            m = rx.search(t)
            if m and m.group(0) not in found:
                found.append(m.group(0))
        if found:
            out[gid] = found
    return out


def trigger_stems(hits: dict[str, list[str]], cfg: dict) -> set[str]:
    """The stems of every word that started a group stem, so raw shared words are not the same evidence counted twice."""
    return {stem(w, cfg) for found in hits.values() for phrase in found for w in words(phrase)}


def countries(geo_text: str | None, cfg: dict) -> set[str]:
    """Country codes a declared geography text names ('*' = anywhere). The longest region words match first and are used up, so
    'northern europe' does not also count as 'europe'. An empty set means the text names no place we can read."""
    t = " ".join(words(geo_text))
    out: set[str] = set()
    for _k, rx, codes in cfg.get("region_rx") or []:
        if rx.search(t):
            out |= {str(c) for c in codes}
            t = rx.sub(" ", t)
    return out


def code_family(code: str | None, cfg: dict) -> str | None:
    """The industry family of a code: its first `family_digits` digits (3 = the NACE group, so ship building 301 is not aircraft 303)."""
    digits = re.sub(r"\D", "", code or "")
    return digits[: int(cfg.get("family_digits", 3))] or None


def age_years(founded: str | None, today: date) -> float | None:
    try:
        d = date.fromisoformat((founded or "")[:10])
    except ValueError:
        return None
    return round((today - d).days / 365.25, 2)


def age_band(years: float | None, cfg: dict) -> dict | None:
    if years is None:
        return None
    for b in cfg.get("age_bands") or []:
        if years < b["max_years"]:
            return b
    return None


def plain_list(items: list[str], last: str = "and") -> str:
    items = [str(i) for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {last} " + items[-1]
