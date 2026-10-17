"""After generation, before the page trusts a name (PROJECT_RULES D51). Aava writes every company it names as a markdown link to its company
page, [Viva Jets Oy](/c/2962040-6). This module checks the answer against what the tools returned in the same turn:

  - a link to /c/<key> stays only when <key> was returned by a tool this turn and its label is that company's name (or a short form of it);
    otherwise the link is removed, the label stays as plain text, and the name is flagged in the log;
  - a link to anything else stays only when its address appeared in a tool result this turn (a source the records gave), never one the model made up;
  - a company name from this turn's tool results written without a link becomes a link;
  - a company-shaped name (words ending in Oy, Oyj, Ab, Ltd, AS, GmbH ...) that no tool returned and the person did not type is left as text,
    flagged in the log, and listed as `unverified` so the page can say so.

`StreamGuard` applies the link rules to the text while it streams, so the browser never receives a link the final check would remove.
No model call and no database access here: pure functions over the turn's `seen` names.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, unquote

log = logging.getLogger("aava.entities")

LINK = re.compile(r"\[([^\]\n]{1,160})\]\(([^)\s]{1,400})\)")
_PARTIAL = re.compile(r"\[[^\]\n]{0,160}(\]\(?[^)\s]{0,400})?$")   # the tail of a chunk that may still become a link
LEGAL = ("Oyj", "Oy", "Ab", "AB", "Abp", "Ltd", "Ltd.", "AS", "ASA", "A/S", "GmbH", "Inc", "Inc.", "ApS", "Ky", "Plc", "SA", "BV", "Oü", "UAB", "SIA", "AG", "LLC")
_LEGAL_TAIL = re.compile(r"[\s,]+(?:" + "|".join(re.escape(w) for w in sorted(LEGAL, key=len, reverse=True)) + r")\.?$")
_CAP = r"[A-ZÅÄÖÜØÆ][\w&'’\-]*"
_COMPANY_SHAPED = re.compile(r"\b(?:" + _CAP + r"\s+){0,4}" + _CAP + r"[\s,]+(?:" + "|".join(re.escape(w) for w in sorted(LEGAL, key=len, reverse=True)) + r")(?![\w])")
_URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def fold(s: str) -> str:
    return re.sub(r"[^\w]+", " ", (s or "").casefold()).strip()


def short_name(name: str) -> str:
    """'Viva Jets Oy' -> 'Viva Jets' (the legal-form word dropped)."""
    return _LEGAL_TAIL.sub("", name.strip()).strip()


def urls_in(text: str) -> set[str]:
    return {u.rstrip(".,;") for u in _URL.findall(text or "")}


def _label_matches(label: str, name: str) -> bool:
    a, b = fold(short_name(label)), fold(short_name(name))
    return bool(a and b and (a == b or a in b or b in a))


def check_link(label: str, target: str, seen: dict[str, str], urls: set[str]) -> tuple[str, str | None, str | None]:
    """(replacement markdown, company key if it is a company link that stays, flagged name if a company link was removed)."""
    t = target.strip()
    if t.startswith("/c/"):
        key = unquote(t[3:].split("?")[0].split("#")[0])
        name = seen.get(key)
        if name and _label_matches(label, name):
            return f"[{label}](/c/{quote(key, safe='-_.~')})", key, None
        return label, None, label
    if re.match(r"https?://", t, re.I):
        return (f"[{label}]({t})", None, None) if t.rstrip(".,;") in urls else (label, None, None)
    return label, None, None   # javascript:, data:, relative pages the model made up


def _outside_links(text: str):
    """Yield (start, end) spans of text that is not inside a markdown link."""
    pos = 0
    for m in LINK.finditer(text):
        if m.start() > pos:
            yield pos, m.start()
        pos = m.end()
    if pos < len(text):
        yield pos, len(text)


def _link_bare_names(text: str, seen: dict[str, str]) -> str:
    """Make every plain mention of a company this turn's tools returned a link. Longest names first; exact, case-sensitive, whole-word."""
    names: list[tuple[str, str]] = []
    for key, name in seen.items():
        names.append((name, key))
        sn = short_name(name)
        if sn != name and len(sn) >= 4:
            names.append((sn, key))
    names.sort(key=lambda p: -len(p[0]))
    for nm, key in names:
        rx = re.compile(r"(?<![\w/])" + re.escape(nm) + r"(?![\w])")
        out, last = [], 0
        for s, e in list(_outside_links(text)):
            seg = text[s:e]
            for m in rx.finditer(seg):
                out.append(text[last:s + m.start()])
                out.append(f"[{m.group(0)}](/c/{quote(key, safe='-_.~')})")
                last = s + m.end()
        out.append(text[last:])
        text = "".join(out)
    return text


def enforce(text: str, seen: dict[str, str], urls: set[str] | None = None, orgs: dict[str, str] | None = None, user_text: str = "") -> dict:
    """The checked answer: {text, keys (companies linked, first mention order), flagged (company links removed), unverified (company-shaped names no tool returned)}."""
    urls = urls or set()
    flagged: list[str] = []

    def sub(m: re.Match) -> str:
        rep, key, bad = check_link(m.group(1), m.group(2), seen, urls)
        if bad:
            flagged.append(bad)
        return rep

    text = LINK.sub(sub, text or "")
    text = _link_bare_names(text, seen)
    keys: list[str] = []
    for m in LINK.finditer(text):
        if m.group(2).startswith("/c/"):
            k = unquote(m.group(2)[3:])
            if k in seen and k not in keys:
                keys.append(k)
    known = [fold(n) for n in [*seen.values(), *(orgs or {}).values()]]
    user = fold(user_text)
    unverified: list[str] = []
    done: set[str] = set()
    for s, e in _outside_links(text):
        for m in _COMPANY_SHAPED.finditer(text[s:e]):
            nm = m.group(0).strip(" ,")
            f = fold(nm)
            if not f or f in done or any(f in k or k in f for k in known if k) or (user and (f in user or fold(short_name(nm)) in user)):
                continue
            done.add(f)
            unverified.append(nm)
            flagged.append(nm)
    if flagged:
        log.warning("aava answer named companies no tool returned this turn: %s", "; ".join(dict.fromkeys(flagged)))
    return {"text": text, "keys": keys, "flagged": list(dict.fromkeys(flagged)), "unverified": unverified}


class StreamGuard:
    """Applies `check_link` to streamed text. A '[' that may still become a link is held back (at most ~600 characters, never across a line break)
    until the link closes or turns out not to be one; everything else passes straight through."""

    def __init__(self, seen: dict[str, str], urls: set[str]):
        self.seen, self.urls = seen, urls
        self.pending = ""

    def _drain(self, final: bool) -> str:
        out: list[str] = []
        s = self.pending
        while True:
            i = s.find("[")
            if i < 0:
                out.append(s)
                s = ""
                break
            out.append(s[:i])
            s = s[i:]
            m = LINK.match(s)
            if m:
                out.append(check_link(m.group(1), m.group(2), self.seen, self.urls)[0])
                s = s[m.end():]
                continue
            if not final and _PARTIAL.match(s) and "\n" not in s and len(s) < 600:
                break   # wait for more text
            out.append("[")
            s = s[1:]
        self.pending = s
        return "".join(out)

    def feed(self, chunk: str) -> str:
        self.pending += chunk
        return self._drain(False)

    def flush(self) -> str:
        return self._drain(True)
