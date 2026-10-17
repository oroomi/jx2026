"""Read side of the radar: every page gets its data through this module. Pure functions over a sqlite3.Connection."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from radar import db as db_mod
from radar import labels
from radar import thesis as thesis_mod

# Labels live in radar/labels.py, the one label table; these names stay for the call sites that read them.
SOURCE_LABELS = labels.SOURCE_LABELS
TYPE_LABELS = labels.SIGNAL_LABELS
# Wording follows the docstring of radar/emit.py.
CONFIDENCE_RULES = {
    "high": "the source names the company or its business id directly and states the date.",
    "medium": "matched by an exact legal name or website domain, date stated by the source.",
    "low": "matched by name keyword or industry code only; shown, but never counted in rankings.",
}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}
NO_DB_MESSAGE = "no signals yet. Run python3 -m radar.build"


def open_db(path=None, readonly: bool = True, thesis: dict | None = None):
    """Open the radar database. Path defaults to the thesis database (thesis.db_path; env RADAR_DB for the default thesis).
    Read-only returns None when the file does not exist."""
    if path is None:
        path = thesis_mod.db_path(thesis or thesis_mod.load())
    p = Path(path)
    if not readonly:
        return db_mod.connect(p)
    if not p.is_file():
        return None
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


COOKIE = "radar_thesis"


def _requested_thesis(request) -> tuple[str | None, bool]:
    """(thesis id, from_query). Only ids that exist in thesis.available() survive; nothing else is ever used."""
    if request is None:
        return None, False
    av = thesis_mod.available()
    q = request.query_params.get("thesis")
    if q in av:
        return q, True
    c = request.cookies.get(COOKIE)
    if c in av:
        return c, False
    return None, False


def context(request=None):
    """The ONLY way a route gets its thesis and database: `thesis, conn = store.context(request)`.
    The thesis is picked per request (query `thesis`, then cookie `radar_thesis`, then the default); conn is None
    when that thesis has no database yet (show the empty state)."""
    tid, from_query = _requested_thesis(request)
    th = thesis_mod.load(thesis_mod.resolve(tid))
    if request is not None:
        request.state.thesis = th
        if from_query:
            request.state.set_thesis_cookie = th["id"]
    return th, open_db(thesis=th)


def empty_state_text(thesis: dict) -> str:
    return f"no signals yet for {thesis['title']}. Run python3 -m radar.build --thesis {thesis['_path']}"


def _today(today) -> date:
    if today is None:
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(today) if isinstance(today, str) else today


def _window(thesis, today):
    end = _today(today)
    days = thesis["geography"]["feed_window_days"]
    return end - timedelta(days=days), end, days


def rule_text(thesis: dict) -> str:
    days = thesis["geography"]["feed_window_days"]
    fams = [str(f).strip() for f in thesis.get("code_alone_weak") or [] if str(f).strip()]
    broad = (f"A broad consultancy or research code (industry code families {', '.join(fams)}) is a hint only: it needs a sector word "
             f"in the registered line of business, the source text or a backed legal name as well, otherwise the company is a weak match. ") if fams else ""
    return (f"Companies from outside the declared cohort and portfolio whose earliest public signal in the last {days} days "
            f"is shown, newest first, once each. A company is listed as a match only when we can say why: its industry code "
            f"or registered line of business fits the thesis, a contract or project text states the match, or a thesis word in "
            f"its legal name is backed by a record from a different source family (a PRH notice never backs a PRH register entry). "
            f"{broad}Listed companies (Oyj) are left out. Name-only matches are kept in a closed Weak matches list.")


# Source families for corroboration: these adapters all read the one PRH/YTJ registry, so a second record from any of them
# is the same source again, never independent support for a name word.
REGISTRY_FAMILY = "prh"
SOURCE_FAMILIES = {"prh": REGISTRY_FAMILY, "prh_notices": REGISTRY_FAMILY, "prh_intake": REGISTRY_FAMILY, "prh_recent": REGISTRY_FAMILY,
                   "tax_registers": REGISTRY_FAMILY}


def source_family(adapter: str | None) -> str:
    return SOURCE_FAMILIES.get(adapter or "", adapter or "")


CORROBORATION_RULE = ("A name word counts only when the second record comes from a different source family than the row's own: "
                      "PRH register entries, PRH notices and PRH tax registers are one family (the same registry), so a PRH record never "
                      "corroborates another PRH record; otherwise the row is a weak match.")

# Legal forms of listed companies: never an early-stage discovery, so left out of the feed (counted in the footer).
LISTED_FORM_WORDS = ("oyj", "abp")


def is_listed_company(name: str | None) -> bool:
    words = re.findall(r"[a-zåäö]+", (name or "").casefold())
    return any(w in LISTED_FORM_WORDS for w in words[-2:])


def excluded_code(code: str | None, thesis: dict) -> bool:
    """True when the industry code starts with a prefix the sector file excludes from the feed (feed_exclude_code_prefixes)."""
    c = (code or "").strip()
    return bool(c) and any(c.startswith(str(p)) for p in thesis.get("feed_exclude_code_prefixes") or [])


REASON_IDS = ("industry_code", "line_of_business", "own_text", "corroborated_keyword")
REASON_MEANING = {
    "industry_code": "the PRH industry code is on the thesis list (exact match).",
    "line_of_business": "a thesis word starts a word in the registered line-of-business text.",
    "own_text": "the source's own text (Hilma notice title, CORDIS project title and objective, BlueInvest profile text) contains a thesis word. Our own annotations are never read.",
    "corroborated_keyword": "a thesis word is in the legal name and a record from a different source family also has the company (PRH register entries, PRH notices and PRH tax registers are one registry, so they never corroborate each other).",
}
_WHY_ORDER = ("industry_code", "line_of_business", "own_text", "corroborated_keyword")
# Signal types whose SOURCE text is stored: Hilma notice title (inside detail), CORDIS title and objective (signal_text),
# BlueInvest profile title and description. Other types (Business Finland, patent, job ad) have no stored source text: no own_text path.
_OWN_TEXT_TYPES = ("public_contract", "eu_project", "blueinvest")
OWN_TEXT_SOURCES = ("the Hilma notice title", "the CORDIS project title and objective", "the BlueInvest profile text")


def is_year_only(sig) -> bool:
    """A Business Finland record whose true date is only known to the year: never a feed entry date."""
    if sig["signal_type"] != "bf_funding":
        return False
    detail = (sig["detail"] or "").casefold()
    return "year only" in detail or "year-level" in detail or str(sig["date"] or "")[5:] == "01-01"


def date_label(sig) -> str:
    d = str(sig["date"] or "")
    return f"{d[:4]} (year only)" if is_year_only(sig) else d


def _title_part(detail: str | None) -> str:
    """Hilma detail is 'buyer: title (EUR n)'; only the title is the notice's own wording about the work."""
    d = detail or ""
    d = d.split(": ", 1)[1] if ": " in d else ""
    return re.sub(r"\s*\(EUR [^)]*\)\s*$", "", d)


def source_texts(conn, sigs) -> dict:
    """signal id -> list of the source's own text fields. Never the `detail` annotation our adapters write (except Hilma, whose
    detail embeds the notice title, taken apart by _title_part). Missing table or row means no text."""
    out: dict = {}
    ids = [s["id"] for s in sigs if s["signal_type"] == "eu_project"]
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" * len(chunk))
        try:
            for r in conn.execute(f"SELECT signal_id, text FROM signal_text WHERE field IN ('title','objective') AND signal_id IN ({q})", chunk):
                out.setdefault(r[0], []).append(r[1])
        except sqlite3.OperationalError:
            break
    keys = {s["company_key"]: s["id"] for s in sigs if s["signal_type"] == "blueinvest"}
    for key, sid in keys.items():
        try:
            for r in conn.execute("SELECT title, description FROM blueinvest_profiles WHERE company_key=?", (key,)):
                out.setdefault(sid, []).extend(t for t in r if t)
        except sqlite3.OperationalError:
            break
    return out


def _own_text_hit(sig, thesis: dict, texts: dict | None = None) -> str | None:
    """The thesis word found in a signal's SOURCE text, or None when no source text is stored."""
    from radar import fit
    if sig["signal_type"] not in _OWN_TEXT_TYPES:
        return None
    if sig["signal_type"] == "public_contract":
        title = _title_part(sig["detail"]).casefold()
        return next((k for k in thesis.get("hilma_keywords", []) if k.casefold() in title), None)
    hits = fit.matched_keywords(" . ".join((texts or {}).get(sig["id"], [])), thesis)
    return hits[0] if hits else None


def code_alone_family(code: str | None, thesis: dict) -> str | None:
    """The `code_alone_weak` family (a code prefix from the sector file) this industry code belongs to, or None. A dot is ignored,
    so the NACE spelling 71.12 and the stored 7112x are the same family."""
    c = (code or "").replace(".", "").strip()
    for fam in thesis.get("code_alone_weak") or []:
        f = str(fam).replace(".", "").strip()
        if f and c.startswith(f):
            return f
    return None


def explain(row: dict, others: list, thesis: dict, texts: dict | None = None) -> dict:
    """reasons (ids, strongest first), strength and the one-line why for one feed row. Built only from stored values."""
    from radar import fit
    code = (row.get("industry_code") or "").strip()
    desc = (row.get("industry_desc") or "").strip()
    notes = {str(c.get("code")): c.get("note") for c in thesis.get("industry_codes") or []}
    name_hits = fit.matched_keywords(row["name"], thesis)
    lob_hits = fit.matched_keywords(desc, thesis) if desc else []
    reasons, parts = [], {}
    if code and code in notes:
        reasons.append("industry_code")
        parts["industry_code"] = f"industry code {code} ({desc or notes[code]}, PRH) is on the thesis list"
    if lob_hits:
        reasons.append("line_of_business")
        parts["line_of_business"] = f"the registered line of business '{desc}' contains '{lob_hits[0]}'"
    for sig in [row, *others]:
        if sig is row and row["signal_type"] == "register_entry":
            continue
        hit = _own_text_hit(sig, thesis, texts)
        if hit:
            reasons.append("own_text")
            parts["own_text"] = f"the {labels.signal_label(sig['signal_type']).lower()} text contains '{hit}'"
            break
    row_family = source_family(row["adapter"])
    second = next((o for o in others if source_family(o["adapter"]) != row_family), None)
    if name_hits and second is not None:
        reasons.append("corroborated_keyword")
        src = labels.source_label(second["adapter"])
        parts["corroborated_keyword"] = (f"the legal name has '{name_hits[0]}' and a {src} record from "
                                         f"{date_label(second)} supports it")
    reasons.sort(key=_WHY_ORDER.index)
    # A broad consultancy or research code (thesis `code_alone_weak`) is a hint, never enough for the main list: the row also needs
    # a sector word from the line of business, the source's own text or a corroborated name word. Without it the row stays weak.
    family = code_alone_family(code, thesis) if "industry_code" in reasons else None
    if family and not set(reasons) - {"industry_code"}:
        lob = f"'{desc}' ({code})" if desc else f"code {code}"
        why = f"Weak: an industry code in the {family} family alone; a consultancy code needs a sector word. The registered line of business is {lob}."
        return {"reasons": reasons, "strength": "weak", "why": why}
    if family:  # the code is on the list, but something stronger backs it: lead with that, keep the code as a further reason
        reasons.remove("industry_code")
        reasons.append("industry_code")
    if reasons:
        lead = parts[reasons[0]]
        more = len(reasons) - 1
        why = "Why: " + lead[0].upper() + lead[1:]
        why += f"; {more} more reason{'s' if more != 1 else ''}." if more else "."
        return {"reasons": reasons, "strength": "strong", "why": why}
    lob = f"'{desc}' ({code})" if desc and code else (f"'{desc}'" if desc else (f"code {code}" if code else "not in public records"))
    if name_hits:
        why = (f"Weak: only the legal name ('{row['name']}') contains '{name_hits[0]}'; "
               f"the registered line of business is {lob}.")
    else:
        why = f"Weak: the stored record does not show why it matched; the registered line of business is {lob}."
    return {"reasons": [], "strength": "weak", "why": why}


def _date_fields(date_str, precision) -> tuple[str, str]:
    """(precision, label). A year-only signal never prints a day-level date."""
    if precision == "year" and date_str:
        return "year", f"{str(date_str)[:4]} (year only)"
    return "day", date_str


def with_precision(conn, rows):
    """Add date_precision and date_label to row dicts (and their evidence dict). 'day' when signal_meta has no row or no table."""
    ids = [r.get("signal_id", r.get("id")) for r in rows]
    prec: dict = {}
    ids = [i for i in ids if i is not None]
    if ids:
        try:
            q = ",".join("?" * len(ids))
            prec = {m[0]: m[1] for m in conn.execute(f"SELECT signal_id, date_precision FROM signal_meta WHERE signal_id IN ({q})", ids)}
        except sqlite3.OperationalError:
            prec = {}
    for r in rows:
        p, label = _date_fields(r.get("date"), prec.get(r.get("signal_id", r.get("id")), "day"))
        r["date_precision"], r["date_label"] = p, label
        if isinstance(r.get("evidence"), dict):
            r["evidence"].update(date_precision=p, date_label=label)
    return rows


def evidence(row) -> dict:
    r = dict(row)
    p, dlabel = _date_fields(r.get("date"), r.get("date_precision", "day"))
    adapter = r.get("adapter")
    url = r.get("source_url") or r.get("url")
    label = labels.source_label(adapter, url)
    conf = r.get("confidence")
    return {
        "label": label,
        "event_date": r.get("date"),
        "date_precision": p,
        "date_label": dlabel,
        "fetched_at": r.get("fetched_at"),
        "url": url,
        "confidence": conf,
        "confidence_rule": CONFIDENCE_RULES.get(conf),
    }


def _feed_types(thesis, signal_type=None):
    types = list(thesis["feed_signal_types"])
    if signal_type is not None:
        types = [t for t in types if t == signal_type]
    return types


def _in_window_rows(conn, thesis, today, types, group):
    start, end, _ = _window(thesis, today)
    if not types:
        return []
    q = ",".join("?" * len(types))
    sql = f"""SELECT c.company_key, c.name, c.y_tunnus, c.group_tag, c.country, c.industry_code, c.industry_desc,
                     s.id AS signal_id, s.signal_type, s.date, s.confidence, s.detail, s.amount_eur,
                     s.source_url, s.adapter, s.fetched_at
              FROM signals s JOIN companies c USING (company_key)
              WHERE s.signal_type IN ({q}) AND s.date >= ? AND s.date <= ?"""
    args = [*types, start.isoformat(), end.isoformat()]
    if group is not None:
        sql += " AND c.group_tag = ?"
        args.append(group)
    return conn.execute(sql, args).fetchall()


def _others_by_company(conn, keys) -> dict[str, list]:
    out: dict[str, list] = {k: [] for k in keys}
    keys = list(keys)
    for i in range(0, len(keys), 500):
        chunk = keys[i:i + 500]
        q = ",".join("?" * len(chunk))
        for r in conn.execute(f"""SELECT id, company_key, signal_type, date, adapter, detail, source_url
                                  FROM signals WHERE company_key IN ({q}) ORDER BY date, id""", chunk):
            out[r["company_key"]].append(r)
    return out


def feed(conn, thesis, *, today=None, signal_type=None, group="feed", limit=500) -> list[dict]:
    return _feed(conn, thesis, today=today, signal_type=signal_type, group=group, limit=limit)[0]


def _feed(conn, thesis, *, today=None, signal_type=None, group="feed", limit=500) -> tuple[list[dict], int]:
    """(rows, hidden). Hidden = companies left out because the legal name looks like a private person and the company has no
    signal other than a register entry. One row per company: its earliest in-window feed signal (ties: confidence, then lowest id), newest first.
    Year-only Business Finland records are never the entry signal. Each row carries reasons, strength and why."""
    start, _, _ = _window(thesis, today)
    all_types = _feed_types(thesis)
    rows = _in_window_rows(conn, thesis, today, all_types, group)
    per: dict[str, list] = {}
    for r in rows:
        if is_year_only(r):
            continue
        per.setdefault(r["company_key"], []).append(r)
    others = _others_by_company(conn, per.keys())
    texts = source_texts(conn, [o for k in per for o in others[k]])
    out, hidden = [], 0
    from radar import fit
    for key, rs in per.items():
        if is_partner_org(rs[0]["name"]):
            continue
        if is_listed_company(rs[0]["name"]) or excluded_code(rs[0]["industry_code"], thesis):
            continue  # counted in feed_counts as listed / excluded code family
        if fit.looks_like_person(rs[0]["name"], thesis) and all(o["signal_type"] == "register_entry" for o in others[key]):
            hidden += 1
            continue
        best = min(rs, key=lambda r: (r["date"], _CONF_ORDER.get(r["confidence"], 3), r["signal_id"]))
        if signal_type is not None and best["signal_type"] != signal_type:
            continue
        q = ",".join("?" * len(all_types))
        earlier = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE company_key=? AND signal_type IN ({q}) AND date < ?",
            [key, *all_types, start.isoformat()]).fetchone()[0]
        d = dict(best)
        d["type_label"] = labels.signal_label(d["signal_type"])
        d["earlier_count"] = earlier
        d["signal_count"] = len(rs)
        d["evidence"] = evidence(d)
        d["date_label"] = date_label(d)
        d["id"] = d["signal_id"]
        d.update(explain(d, [o for o in others[key] if o["id"] != best["signal_id"]], thesis, texts))
        out.append(d)
    out.sort(key=lambda d: (d["date"], d["signal_id"]), reverse=True)
    return with_precision(conn, out[:limit]), hidden


def feed_counts(conn, thesis, *, today=None) -> dict:
    start, end, days = _window(thesis, today)
    types = list(thesis["feed_signal_types"])
    rows, hidden = _feed(conn, thesis, today=today, limit=10**9)
    by_type = {t: 0 for t in types}
    by_conf = {c: 0 for c in ("high", "medium", "low")}
    for r in rows:
        by_type[r["signal_type"]] = by_type.get(r["signal_type"], 0) + 1
        by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1
    by_reason = {r: 0 for r in REASON_IDS}
    for r in rows:
        if r["strength"] != "strong":
            continue  # a weak row can carry the code reason it was not admitted on (code_alone_weak): only the main list is counted
        for rid in r["reasons"]:
            by_reason[rid] += 1
    main = sum(1 for r in rows if r["strength"] == "strong")
    year_only = 0
    excluded = 0
    future = 0
    if types:
        year_only = sum(1 for r in conn.execute(
            """SELECT s.signal_type, s.date, s.detail FROM signals s JOIN companies c USING (company_key)
               WHERE s.signal_type = 'bf_funding' AND c.group_tag = 'feed'""") if is_year_only(r))
        q = ",".join("?" * len(types))
        excluded = conn.execute(
            f"""SELECT COUNT(DISTINCT c.company_key) FROM signals s JOIN companies c USING (company_key)
                WHERE c.group_tag IN ('cohort','portfolio') AND s.signal_type IN ({q}) AND s.date >= ? AND s.date <= ?""",
            [*types, start.isoformat(), end.isoformat()]).fetchone()[0]
        future = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE signal_type IN ({q}) AND date > ?", [*types, end.isoformat()]).fetchone()[0]
    listed, excluded_codes = _left_out(conn, thesis, today)
    last = conn.execute("SELECT MAX(fetched_at) FROM signals").fetchone()[0]
    return {"window_start": start.isoformat(), "window_end": end.isoformat(), "window_days": days,
            "companies": len(rows), "hidden_personal": hidden, "main": main, "weak": len(rows) - main, "by_reason": by_reason,
            "year_only_not_entry": year_only, "by_type": by_type, "by_confidence": by_conf,
            "excluded_declared": excluded, "future_dated": future, "last_fetched": last,
            "excluded_listed": listed, "excluded_codes": excluded_codes,
            "excluded_code_prefixes": [str(p) for p in thesis.get("feed_exclude_code_prefixes") or []]}


def _left_out(conn, thesis, today) -> tuple[int, int]:
    """(listed companies, companies in an excluded code family) that had an in-window feed signal and were left out."""
    seen: dict[str, tuple[str, str | None]] = {}
    for r in _in_window_rows(conn, thesis, today, _feed_types(thesis), "feed"):
        if not is_year_only(r):
            seen[r["company_key"]] = (r["name"], r["industry_code"])
    listed = sum(1 for n, _ in seen.values() if is_listed_company(n) and not is_partner_org(n))
    codes = sum(1 for n, c in seen.values() if not is_listed_company(n) and excluded_code(c, thesis) and not is_partner_org(n))
    return listed, codes


def _fold(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(ch)).casefold()


# ---- partner organisations: never shown as discovered startups ---------------------------------------------------------
PARTNER_PREFIXES = ("A'Pelago", "APelago", "Redstone", "Turku Science Park")
PARTNER_LISTS = ("data/declared/investors.csv", "data/declared/programmes_grants.csv")
_LEGAL_SUFFIX = re.compile(r"\b(oy|oyj|ab|abp|as|asa|ltd|ky|gmbh|inc|llc|aps)\b", re.I)
_partner_state: tuple | None = None
_partner_checked = [0.0]  # monotonic time of the last look at the list files


def name_key(name: str) -> str:
    """Folded name for comparisons: diacritics, case, legal-form words, punctuation and spaces removed."""
    return re.sub(r"[^a-z0-9]+", "", _LEGAL_SUFFIX.sub(" ", _fold(name)))


def _partner_current() -> tuple:
    """(file signature, {'prefixes', 'names'}, folded prefixes, folded names) for the current version of the declared lists. The lists are
    read and every name folded once per file version; the files are looked at once a second (the home list asks 66,000 times in a
    build). The tuple is replaced whole, so a thread never sees a half-built state."""
    import csv
    import time
    global _partner_state
    st, now = _partner_state, time.monotonic()
    if st is not None and now - _partner_checked[0] < 1.0:
        return st
    _partner_checked[0] = now
    root = Path(__file__).resolve().parent.parent
    sig = tuple((rel, (root / rel).stat().st_mtime_ns if (root / rel).is_file() else 0) for rel in PARTNER_LISTS)
    if st is None or st[0] != sig:
        names: list[str] = []
        for rel in PARTNER_LISTS:
            p = root / rel
            if p.is_file():
                with p.open(encoding="utf-8", newline="") as f:
                    names += [r["name"].strip() for r in csv.DictReader(f) if (r.get("name") or "").strip()]
        hit = {"prefixes": list(PARTNER_PREFIXES), "names": sorted(set(names), key=str.casefold)}
        keys = frozenset(name_key(n) for n in hit["names"]) | frozenset(name_key(re.sub(r"\s*\([^)]*\)", "", n)) for n in hit["names"])
        st = _partner_state = (sig, hit, tuple(name_key(p) for p in hit["prefixes"]), keys)
    return st


def partner_orgs() -> dict:
    """{'prefixes': [...], 'names': [...]}: the organisations excluded from the feed and the radar. The names come from the
    declared investor and programme lists, read here once per file version."""
    return _partner_current()[1]


def is_partner_org(name: str) -> bool:
    _, _, prefix_keys, name_keys = _partner_current()
    key = name_key(name)
    return any(key.startswith(p) for p in prefix_keys) or key in name_keys


def search(conn, q, limit=20) -> list[dict]:
    q = _fold((q or "").strip())
    if not q:
        return []
    hits = []
    for r in conn.execute("SELECT * FROM companies ORDER BY name"):
        name, key, yt = _fold(r["name"]), _fold(r["company_key"]), _fold(r["y_tunnus"] or "")
        if q in name or q in key or q in yt:
            hits.append((0 if name.startswith(q) else 1, name, dict(r)))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [h[2] for h in hits[:limit]]


def company(conn, key) -> dict | None:
    row = conn.execute("SELECT * FROM companies WHERE company_key = ?", (key,)).fetchone()
    if row is None:
        return None
    sigs = []
    for s in conn.execute("SELECT * FROM signals WHERE company_key = ? ORDER BY date DESC, id DESC", (key,)):
        d = dict(s)
        d["type_label"] = labels.signal_label(d["signal_type"])
        d["detail"] = labels.plain_text(d["detail"]) if d.get("detail") else d.get("detail")  # no register type code or snake_case id on a page
        d["evidence"] = evidence(d)
        sigs.append(d)
    with_precision(conn, sigs)
    by_type: dict[str, int] = {}
    for s in sigs:
        by_type[s["signal_type"]] = by_type.get(s["signal_type"], 0) + 1
    return {"company": dict(row), "signals": sigs,
            "counts": {"signals": len(sigs), "by_type": by_type,
                       "first_signal": sigs[-1]["date"] if sigs else None,
                       "last_signal": sigs[0]["date"] if sigs else None}}


def cohort_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM companies WHERE group_tag = 'cohort'").fetchone()[0]


def _main(argv) -> int:
    if len(argv) < 2 or argv[1] not in ("feed", "company"):
        print("usage: python3 -m radar.store feed | company <key>")
        return 2
    conn = open_db()
    if conn is None:
        print(NO_DB_MESSAGE)
        return 1
    th = thesis_mod.load()
    if argv[1] == "feed":
        print(rule_text(th))
        print(json.dumps(feed_counts(conn, th), indent=2))
        for r in feed(conn, th, limit=20):
            print(f"{r['date']}  {r['confidence']:<6} {r['type_label']:<26} {r['name']} [{r['company_key']}]  {r['source_url']}")
    else:
        if len(argv) < 3:
            print("usage: python3 -m radar.store company <key>")
            return 2
        c = company(conn, argv[2])
        if c is None:
            print("no such company")
            return 1
        print(json.dumps(c["company"], indent=2, ensure_ascii=False))
        print(json.dumps(c["counts"], indent=2))
        for s in c["signals"]:
            print(f"{s['date']}  {s['confidence']:<6} {s['type_label']:<26} {s['source_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
