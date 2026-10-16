"""Declared ecosystem dataset: data/declared/ecosystem/blue_economy_fi.sqlite -> companies, capital and buyer entities,
scored matches, readiness evidence text and dated events. This is research output (sources per record), imported as DECLARED data.

Supply-side entities become companies (matched by business id, then folded name, then website domain; new ones get group_tag
'ecosystem'). Capital sources and buyers go to eco_entity. Rows without a date are never signals: they stay as evidence text."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from radar import emit

PHASE = 2
NAME = "ecosystem"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"
ADAPTER_LABEL = "declared ecosystem dataset"

# The shared emit.py lists the live-adapter types; the dataset's typed events are added here at import time.
ECO_TYPES = ("pilot_named", "first_hire", "certification", "programme_entry", "exhibitor", "award", "funding_round",
             "patent", "product_launch", "public_funding", "ecosystem_event")
emit.SIGNAL_TYPES = tuple(dict.fromkeys((*emit.SIGNAL_TYPES, *ECO_TYPES)))

EVENT_TYPE_MAP = {
    "first_customer_or_pilot_named": "pilot_named", "first_hire_or_job_ad": "first_hire",
    "certification_or_type_approval": "certification", "accelerator_or_programme_entry": "programme_entry",
    "exhibitor_or_demo": "exhibitor", "award_or_pitch_win": "award", "funding_round": "funding_round",
    "patent_filed": "patent", "product_launch": "product_launch", "launch": "product_launch",
    "grant_or_public_funding": "public_funding",
}
SKIPPED_EVENT_TYPES = ("founding",)  # the founding is the register entry, not a signal
EVENT_LABELS = {
    "pilot_named": "First customer or pilot named", "first_hire": "First hire or job ad", "certification": "Certification or type approval",
    "programme_entry": "Accelerator or programme entry", "exhibitor": "Exhibitor or demo", "award": "Award or pitch win",
    "funding_round": "Funding round", "patent": "Patent filed", "product_launch": "Product launch",
    "public_funding": "Grant or public funding", "ecosystem_event": "Other dated event",
}
COUNTRIES = {"Finland": "FI", "Sweden": "SE", "Norway": "NO", "Denmark": "DK", "Spain": "ES", "Bulgaria": "BG",
             "Switzerland": "CH", "United States": "US", "Estonia": "EE", "Germany": "DE", "Iceland": "IS"}
_CONF_RANK = {"high": 0, "medium": 1, "low": 2}
_BIZ = re.compile(r"^\d{7}-\d$")
_URL = re.compile(r"https?://[^\s;,|)\]]+")
_PERSON_LINK = re.compile(r"https?://[^\s;,|)\]]*linkedin\.com/in/[^\s;,|)\]]*", re.I)
_PERSON_WORD = re.compile(r"\b(CEO|CTO|CFO|COO|founders?|co-?founders?|co-?founded|founded by|chair(man|woman)?|board member|managing director|named rep\w*)\b", re.I)
_LEGAL = re.compile(r"\b(oy|oyj|ab|as|asa|ltd|ky|gmbh|inc|llc|sl|aps|a/s|bv)\b\.?", re.I)
NOT_A_JOB = re.compile(r"^(no open|open application|open job application|careers page|\d+ open positions)", re.I)


def fold(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = _LEGAL.sub(" ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def name_variants(name: str) -> set[str]:
    parts = [name] + [p for p in re.split(r"\s*/\s*", name) if p and p != name]
    return {f for f in (fold(p) for p in parts) if f}


def domain(url: str | None) -> str | None:
    host = urlparse(url or "").netloc.lower().removeprefix("www.")
    return host or None


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def scrub(text: str | None) -> str | None:
    """Evidence text without links to private individuals and without segments that name a person's role (companies only)."""
    if not text:
        return None
    text = _PERSON_LINK.sub("", text)
    segs = [s.strip() for s in re.split(r";\s+|\n", text) if s.strip()]
    kept = [s for s in segs if not _PERSON_WORD.search(s)]
    out = "; ".join(kept).strip(" ;-")
    return out or None


def links(text: str | None) -> list[str]:
    seen: list[str] = []
    for u in _URL.findall(_PERSON_LINK.sub("", text or "")):
        u = u.rstrip(".")
        if u not in seen:
            seen.append(u)
    return seen


def event_date(raw: str | None, precision: str | None, cap: str) -> tuple[str, str] | None:
    """(ISO date, precision 'day'|'month'|'year') or None. A month-only date is stored as the LAST day of the month (the cautious
    reading for an earliness claim), never later than the dataset's own verification date `cap`."""
    raw = (raw or "").strip()
    if not raw or precision == "none":
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw, "day"
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        y, m = int(raw[:4]), int(raw[5:7])
        if not 1 <= m <= 12:
            return None
        last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).isoformat()
        return min(last, cap), "month"
    if re.fullmatch(r"\d{4}", raw):
        return f"{raw}-01-01", "year"
    return None


def human_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def _first_url(*texts) -> str | None:
    for t in texts:
        for u in links(t):
            return u
    return None


def _match_company(conn, ent, by_biz, by_name, by_dom) -> str | None:
    biz = (ent["business_id"] or "").strip()
    if biz and biz in by_biz:
        return by_biz[biz]
    for v in name_variants(ent["name"]):
        if v in by_name:
            return by_name[v]
    d = domain(ent["website"])
    if d and d in by_dom:
        return by_dom[d]
    return None


def run(conn: sqlite3.Connection, thesis: dict | None = None, *, path: Path | str | None = None) -> dict:
    src_path = Path(path) if path else DB_PATH
    if not src_path.is_file():
        return {"companies": 0, "signals": 0, "skipped": 0, "note": "dataset file missing"}
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        return _import(conn, src)
    finally:
        src.close()


def _import(conn, src) -> dict:
    ents = src.execute("SELECT * FROM entity").fetchall()
    urls: dict[str, list[str]] = {}
    for r in src.execute("SELECT entity_id, url FROM source ORDER BY id"):
        urls.setdefault(r["entity_id"], []).append(r["url"])
    verified = src.execute("SELECT MAX(last_verified) FROM entity").fetchone()[0] or ""
    cap = verified if re.fullmatch(r"\d{4}-\d{2}-\d{2}", verified) else date.today().isoformat()
    label = f"declared research ({human_date(cap)})"

    by_biz, by_name, by_dom = {}, {}, {}
    for c in conn.execute("SELECT company_key, name, y_tunnus, website FROM companies ORDER BY (group_tag IN ('cohort','portfolio')) DESC"):
        if c["y_tunnus"]:
            by_biz.setdefault(c["y_tunnus"], c["company_key"])
        for v in name_variants(c["name"]):
            by_name.setdefault(v, c["company_key"])
        d = domain(c["website"])
        if d:
            by_dom.setdefault(d, c["company_key"])

    counts = {"companies": 0, "matched_existing": 0, "new_companies": 0, "capital_buyers": 0, "matches": 0, "readiness": 0,
              "signals": 0, "skipped": 0}
    conn.execute("DELETE FROM eco_match")
    conn.execute("DELETE FROM eco_readiness")
    conn.execute("DELETE FROM eco_entity")
    key_of: dict[str, str] = {}
    conf_of: dict[str, str | None] = {}
    side_of: dict[str, str] = {}
    for e in ents:
        eid = e["id"]
        conf_of[eid], side_of[eid] = e["confidence"], e["side"]
        web = e["website"] if (e["website"] or "").startswith(("http://", "https://")) else None
        link = web or (urls.get(eid) or [None])[0]
        company_key = None
        if e["side"] == "supply":
            company_key = _match_company(conn, e, by_biz, by_name, by_dom)
            if company_key:
                counts["matched_existing"] += 1
            elif link:
                biz = (e["business_id"] or "").strip()
                company_key = biz if _BIZ.match(biz) else f"name:{slug(e['name'])}"
                status = {"defunct": "ended", "dormant_unverified": "unknown"}.get(e["status"] or "")
                emit.upsert_company(conn, company_key=company_key, name=e["name"], source_url=link,
                                    y_tunnus=biz if _BIZ.match(biz) else None, country=COUNTRIES.get(e["country"] or "Finland"),
                                    website=web, group_tag="ecosystem", register_status=status)
                for v in name_variants(e["name"]):
                    by_name.setdefault(v, company_key)
                counts["new_companies"] += 1
            else:
                counts["skipped"] += 1
                continue
            key_of[eid] = company_key
            counts["companies"] += 1
        else:
            counts["capital_buyers"] += 1
        conn.execute("INSERT INTO eco_entity VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (eid, e["name"], e["entity_type"], e["side"], e["business_id"], e["country"], e["city"], web, e["status"],
                      e["stage"], e["confidence"], company_key, link))

    # matches: startup -> capital source or buyer. Two dataset entities for one company merge; the better score is kept.
    for m in src.execute("SELECT * FROM match ORDER BY score DESC, id"):
        ck = key_of.get(m["supply_id"])
        tgt = conn.execute("SELECT source_url, status FROM eco_entity WHERE entity_id=?", (m["target_id"],)).fetchone()
        if ck is None or tgt is None or not tgt["source_url"] or (tgt["status"] or "active") in ("defunct", "dormant_unverified"):
            counts["skipped"] += 1
            continue
        confs = [c for c in (conf_of.get(m["supply_id"]), conf_of.get(m["target_id"])) if c in _CONF_RANK]
        weaker = max(confs, key=_CONF_RANK.get) if confs else None
        cur = conn.execute("INSERT OR IGNORE INTO eco_match VALUES (?,?,?,?,?,?,?)",
                           (ck, m["target_id"], m["target_side"], m["target_type"], m["score"], m["why"], weaker))
        counts["matches"] += cur.rowcount

    for r in src.execute("SELECT * FROM readiness"):
        ck = key_of.get(r["entity_id"])
        if ck is None:
            counts["skipped"] += 1
            continue
        srcs = "\n".join(links(r["sources"]))
        cur = conn.execute(
            "INSERT OR REPLACE INTO eco_readiness VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ck, r["entity_id"], r["trl"], r["br_score"], scrub(r["br_evidence"]), scrub(r["br_missing"]), r["ir_score"],
             scrub(r["ir_evidence"]), scrub(r["ir_missing"]), r["oi_score"], r["oir_score"], scrub(r["oir_evidence"]),
             scrub(r["customer_evidence"]), srcs or None, r["confidence"], r["last_verified"]))
        counts["readiness"] += cur.rowcount

    def put(ck, sig_type, raw, precision, url, conf, detail, amount=None):
        d = event_date(raw, precision, cap)
        if d is None or not url or conf not in emit.CONFIDENCE:
            counts["skipped"] += 1
            return
        iso, prec = d
        detail = f"{detail} [{label}; dataset confidence {conf}{'; month only, stored as the last day of the month' if prec == 'month' else ''}]"
        if emit.emit_signal(conn, company_key=ck, signal_type=sig_type, date=iso, source_url=url, confidence=conf,
                            adapter=NAME, detail=detail, amount_eur=amount or None):
            counts["signals"] += 1
        if prec == "year":
            sid = conn.execute("SELECT id FROM signals WHERE company_key=? AND signal_type=? AND date=? AND source_url=?",
                               (ck, sig_type, iso, url)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO signal_meta (signal_id, date_precision) VALUES (?, 'year')", (sid,))

    for ev in src.execute("SELECT * FROM event ORDER BY id"):
        ck = key_of.get(ev["entity_id"])
        if ck is None or ev["event_type"] in SKIPPED_EVENT_TYPES:
            continue
        sig = EVENT_TYPE_MAP.get(ev["event_type"], "ecosystem_event")
        summary = ev["summary"] or ""  # read only to recognise the cohort entry; never stored
        if sig == "programme_entry" and "nordic blue" in summary.casefold() and (ev["date"] or "") >= "2026-01-01":
            sig = "ecosystem_event"  # the cohort entry itself is the thing the backtest measures against, never a discovery signal
        # The dataset's free text names private individuals (founders, angels) in many rows, so only the event kind and the
        # amount are stored; the source link carries the facts. Companies only.
        text = EVENT_LABELS[sig] + (f" ({ev['event_type']})" if sig == "ecosystem_event" else "")
        if ev["amount_eur"]:
            text += f", amount EUR {ev['amount_eur']:,.0f}".replace(",", " ")
        text += ". Open the source link for the details"
        put(ck, sig, ev["date"], ev["date_precision"], _first_url(ev["sources"]), ev["confidence"], text, ev["amount_eur"])

    for j in src.execute("SELECT * FROM job_signal ORDER BY id"):
        ck = key_of.get(j["entity_id"])
        if ck is None or not j["date"] or NOT_A_JOB.match(j["role"] or "") or "stale" in (j["role"] or "").casefold():
            continue
        put(ck, "job_ad", j["date"], "month" if len(j["date"]) == 7 else None, j["url"], "medium", f"Open role: {j['role']}")

    conf_split = {c: n for c, n in src.execute("SELECT confidence, COUNT(*) FROM entity WHERE confidence IS NOT NULL GROUP BY 1")}
    meta = {"built": cap, "label": label, "entities": str(len(ents)), "matches_in_dataset": str(src.execute("SELECT COUNT(*) FROM match").fetchone()[0]),
            "readiness_in_dataset": str(src.execute("SELECT COUNT(*) FROM readiness").fetchone()[0]),
            "conf_high": str(conf_split.get("high", 0)), "conf_medium": str(conf_split.get("medium", 0)), "conf_low": str(conf_split.get("low", 0)),
            "supply": str(sum(1 for e in ents if e["side"] == "supply")), "capital": str(sum(1 for e in ents if e["side"] == "capital")),
            "demand": str(sum(1 for e in ents if e["side"] == "demand"))}
    conn.executemany("INSERT OR REPLACE INTO eco_meta VALUES (?,?)", meta.items())
    conn.commit()
    return counts


if __name__ == "__main__":
    from radar import db
    print(run(db.connect()))
