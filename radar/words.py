"""Words for what a page must not show as an id or a gap (PROJECT_RULES D36). Pure functions, no database.

Three jobs:
  rule_words        a stored sentence that names a decision rule by its id ("under fallback c2", "rule e", "row 7") says the rule's words
                    instead, read from the sector file's decision table (labels from memo.labels, rows from memo.decisions);
  drop_marked_quotes  a quoted passage that holds a redaction marker ("[name]") is dropped whole, because a quote with a gap is no
                    longer a quote (the same rule as D31 for an organisation's text);
  drop_marked_terms   the same for a search query: the OR-term that holds a marker goes, and a query that is not made of OR-terms goes
                    whole.
No sector word lives here: every label comes from the thesis file."""
from __future__ import annotations

import re

MARKER = re.compile(r"\[name(?: redacted)?\]")
_QUOTED = re.compile(r'"[^"]*"|“[^”]*”')
QUOTE_GONE = "(quote not shown: it names a person or place we do not print)"


def drop_marked_quotes(text: str | None) -> str:
    """Every quoted passage that holds a redaction marker is replaced by a short note; a marker outside any quote drops its clause."""
    t = text or ""
    if not MARKER.search(t):
        return t
    t = _QUOTED.sub(lambda m: QUOTE_GONE if MARKER.search(m.group(0)) else m.group(0), t)
    if MARKER.search(t):
        from radar import fit  # imported here: radar.fit imports radar.labels, which calls this module
        t = fit.drop_redacted_clauses(t) or QUOTE_GONE
    return t


def reason_without_marker(text: str | None) -> str:
    """A machine-written drop reason ("the quote is not on the page: [name redacted]") without the hidden name: a trailing ': [name]' goes, any
    other clause that holds a marker is dropped (D31); when nothing is left the reason says that it names someone we do not print."""
    t = re.sub(r"\s*[:,]\s*" + MARKER.pattern + r"\s*$", "", text or "").strip()
    if MARKER.search(t):
        from radar import fit  # imported here: radar.fit imports radar.labels, which calls this module
        t = fit.drop_redacted_clauses(t).strip()
    return t or "the reason names a person or place we do not print"


def drop_marked_terms(query: str | None) -> str | None:
    """A search query without its marked parts: split on OR, drop the terms that hold a marker; None when nothing sensible is left
    (a query of one term, or one whose remaining terms are not whole quoted phrases)."""
    q = query or ""
    if not MARKER.search(q):
        return q
    terms = re.split(r"\s+OR\s+", q)
    if len(terms) < 2:
        return None
    keep = [x for x in terms if not MARKER.search(x)]
    return " OR ".join(keep) if keep and all(x.strip().startswith(('"', "“")) and x.strip().endswith(('"', "”")) for x in keep) else None


# ---- decision rules in words -------------------------------------------------------------------------------------------------

def _or(values) -> str:
    vals = [str(v) for v in (values if isinstance(values, (list, tuple)) else [values])]
    return " or ".join(vals)


def _when(when: dict, labels: dict) -> str:
    """{technology: High, business: [Low, Medium]} -> 'technology readiness High and business readiness Low or Medium'."""
    return " and ".join(f"{str(labels.get(k, k)).lower()} {_or(v)}" for k, v in (when or {}).items())


def condition_words(when: dict | None, labels: dict) -> str:
    """The cells of a condition rule in words, the same phrase rule_phrases uses (the memo names a matched rule this way, D79)."""
    return _when(when or {}, labels)


def rule_phrases(thesis: dict) -> dict[tuple[str, str], str]:
    """{('row', '7'): 'the Watchlist row of the decision table', ('rule', 'e'): 'the rule for technology readiness High and business
    readiness Low or Medium', ('fallback', 'c2'): 'the fallback rule for business readiness Low or Medium'} from the thesis file."""
    memo = thesis.get("memo") or {}
    labels = memo.get("labels") or {}
    dec = memo.get("decisions") or {}
    out: dict[tuple[str, str], str] = {}
    for r in dec.get("rows") or []:
        team = str(r.get("team") or r.get("decision") or "").strip()
        out[("row", str(r["id"]).lower())] = f"the {team} row of the decision table" if team else "a row of the decision table"
    for r in dec.get("rules") or []:
        w = _when(r.get("when"), labels)
        out[("rule", str(r["id"]).lower())] = f"the rule for {w}" if w else "a rule of the decision table"
    for r in (dec.get("fallback") or {}).get("rules") or []:
        w = _when(r.get("when"), labels)
        out[("fallback", str(r["id"]).lower())] = f"the fallback rule for {w}" if w else "the fallback rule"
    return out


# An id counts only where a rule is being named: after "under" / "by" / "via" / "from", or before punctuation or a connective, so the
# article in "a rule a company must follow" is left alone.
_RULE_ID = re.compile(r"\b(row|rule|fallback)\s+([a-z]\d?|\d{1,2})\b(?:\s+of\s+the\s+decision\s+(?:rules|table))?"
                      r"(?=\s*(?:[,.;:)(]|$)|\s+(?:but|and|because|which|so|since|as|applies|fired|matched)\b)", re.I)


def rule_words(text: str | None, thesis: dict | None) -> str:
    """A stored sentence with each rule id ("fallback c2", "rule e", "row 7") said in the rule's words. An id the thesis file does not
    hold is left as it is (nothing is invented)."""
    t = text or ""
    if not t or not _RULE_ID.search(t) or not thesis:
        return t
    phrases = rule_phrases(thesis)

    def one(m: re.Match) -> str:
        return phrases.get((m.group(1).lower(), m.group(2).lower())) or m.group(0)

    return _RULE_ID.sub(one, t)
