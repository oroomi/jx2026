"""Pre-delivery consistency check (jx40): the store against PROJECT_RULES.md. Read-only; prints PASS or FAIL with counts per check.

  1 pending       no PENDING_DECISION on an applied value: no applied candidate row is pending, no pending value has reached
                  the companies table, and every pending row names an issue that is still open (A31)
  2 confidence    every signal's confidence is high, medium or low, and equals what its adapter's rule gives for the match the
                  row records (A9); rows whose match basis the row does not record are counted as membership-only
  3 labels        every signal type and every source in the store has a label in radar/labels.py (taxonomy)
  4 dates         every event and founding date is a real ISO 8601 date, and every stated precision is day, month or year (A18)
  5 business_ids  every Business ID (y_tunnus, and every key shaped like one) has the pattern and a valid check digit (A30)
  6 countries     every country code is ISO 3166-1 alpha-2 (A29)
  7 amounts       every amount is a number in amount_eur, and no row with an amount names another currency (A19)
  8 provenance    every provenance entry cites an A or D id that PROJECT_RULES.md defines (A32)

  python3 -m radar.consistency --db /tmp/radar_copy.sqlite        # exit 0 on PASS, 1 on FAIL
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

from radar import formats, labels
from radar import thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "PROJECT_RULES.md"
CONFIDENCE = ("high", "medium", "low")
_OTHER_CURRENCY = re.compile(r"\b(SEK|NOK|DKK|USD|GBP|CHF|PLN)\s?[\d]")
_KEY_LIKE_ID = re.compile(r"^\d{7}-\d$")
FIELD_COLUMN = {"name": "name", "founded": "founded", "industry_code": "industry_code", "industry_desc": "industry_desc",
                "town": "town", "website": "website", "register_status": "register_status", "country": "country"}

# Per adapter: the confidence its rule gives, read from what the row records. A set means the row does not record the
# match basis, so only membership is checked. Rules: radar/emit.py and each adapter (PROJECT_RULES.md A9).
_FIXED_HIGH = ("hilma", "prh_intake", "prh_notices", "tax_registers", "ted")
_FIXED_MEDIUM = ("openalex", "webarchive")


def expected_confidence(adapter: str, detail: str, has_business_id: bool) -> set[str] | None:
    """The confidences the rule allows for this row; None when the row does not record its match basis."""
    d = detail or ""
    if adapter in _FIXED_HIGH:
        return {"high"}
    if adapter in _FIXED_MEDIUM:
        return {"medium"}
    if adapter in ("prh", "prh_recent"):
        if "matched because legal name" in d:
            return {"medium"}
        if "matched because industry code" in d:
            return {"low"}
        if "(Y-tunnus" in d:
            return {"high"}
        return None
    if adapter == "cordis":
        if d.startswith("Matched by VAT number"):
            return {"high"}
        if "similarity" in d:
            return {"medium"}
        if d.startswith("Matched on "):
            return {"low"}
        return None
    if adapter == "businessfinland":  # high only for a Business ID match; a name match makes the year's aggregate medium
        return {"high", "medium"} if has_business_id else {"medium"}
    if adapter == "stitcher" and "Year only" in d:
        return {"medium", "low"}  # high needs a day or month on the page
    return None


def rule_ids(path: Path = RULES) -> set[str]:
    if not path.is_file():
        return set()
    return set(re.findall(r"^\*\*([AD]\d+)\.", path.read_text(encoding="utf-8"), re.M))


def _has(conn, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def check(conn: sqlite3.Connection, rules_path: Path = RULES) -> list[dict]:
    """[{name, ok, checked, failed, note, examples}] for the eight checks."""
    conn.row_factory = sqlite3.Row
    out: list[dict] = []
    comp_cols = {r[1] for r in conn.execute("PRAGMA table_info(companies)")}
    companies = {r["company_key"]: dict(r) for r in conn.execute("SELECT * FROM companies")}
    signals = [dict(r) for r in conn.execute("SELECT id, company_key, signal_type, date, confidence, adapter, detail, amount_eur FROM signals")]
    prec = {r[0]: r[1] for r in conn.execute("SELECT signal_id, date_precision FROM signal_meta")} if _has(conn, "signal_meta") else {}

    def add(name, checked, bad, note=""):
        out.append({"name": name, "ok": not bad, "checked": checked, "failed": len(bad), "note": note, "examples": list(bad)[:5]})

    # 1 pending
    if _has(conn, "field_candidates"):
        from radar.candidates import OPEN_ISSUES, norm
        rows = [dict(r) for r in conn.execute("SELECT company_key, field, value, value_norm, applied, status, issue_id FROM field_candidates")]
        pend = [r for r in rows if r["status"] == "PENDING_DECISION"]
        bad = [("applied row pending", r["company_key"], r["field"]) for r in pend if r["applied"]]
        bad += [("issue not open", r["company_key"], r["issue_id"]) for r in pend if r["issue_id"] not in OPEN_ISSUES]
        for r in pend:
            col = FIELD_COLUMN[r["field"]]
            cur = companies.get(r["company_key"], {}).get(col) if col in comp_cols else None
            if cur is not None and r["field"] != "founded" and norm(r["field"], str(cur)) == r["value_norm"]:
                bad.append(("pending value is live", r["company_key"], r["field"]))
        add("pending", len(rows), bad, f"{len(pend)} rows PENDING_DECISION under {len({r['issue_id'] for r in pend})} open issues, none applied")
    else:
        add("pending", 0, [], "no field_candidates table: nothing is pending")

    # 2 confidence
    bad, ruled, member = [], 0, 0
    for s in signals:
        if s["confidence"] not in CONFIDENCE:
            bad.append((s["id"], s["adapter"], s["confidence"]))
            continue
        c = companies.get(s["company_key"]) or {}
        allowed = expected_confidence(s["adapter"] or "", s["detail"] or "", formats.business_id_ok(c.get("y_tunnus")))
        if allowed is None:
            member += 1
        else:
            ruled += 1
            if s["confidence"] not in allowed:
                bad.append((s["id"], s["adapter"], s["confidence"], sorted(allowed)))
    add("confidence", len(signals), bad, f"{ruled} checked against the adapter rule, {member} membership only (the row does not record its match basis)")

    # 3 labels
    types = {s["signal_type"] for s in signals}
    sources = {s["adapter"] for s in signals if s["adapter"]}
    bad = [("signal type", t) for t in sorted(types) if t not in labels.SIGNAL_LABELS]
    bad += [("source", a) for a in sorted(sources) if a not in labels.SOURCE_LABELS]
    add("labels", len(types) + len(sources), bad, f"{len(types)} signal types, {len(sources)} sources in the store")

    # 4 dates
    bad, n = [], 0
    for s in signals:
        n += 1
        if not formats.date_ok(s["date"]):
            bad.append(("signal date", s["id"], s["date"]))
        p = prec.get(s["id"])
        if p is not None and p not in formats.PRECISIONS:
            bad.append(("precision", s["id"], p))
    for k, c in companies.items():
        if c.get("founded") is not None:
            n += 1
            if not formats.date_ok(c["founded"]):
                bad.append(("founded", k, c["founded"]))
    if _has(conn, "field_candidates"):
        for r in conn.execute("SELECT company_key, value, precision, observed FROM field_candidates WHERE field='founded'"):
            n += 1
            if r["precision"] not in formats.PRECISIONS or not formats.date_ok(r["value"] + {"year": "-01-01", "month": "-01"}.get(r["precision"], "")):
                bad.append(("candidate founded", r["company_key"], r["value"], r["precision"]))
    add("dates", n, bad, f"{sum(1 for p in prec.values() if p != 'day')} signal dates carry a year or month precision; all others are day")

    # 5 business ids
    bad, n = [], 0
    for k, c in companies.items():
        for v in {c.get("y_tunnus"), k if _KEY_LIKE_ID.match(k) else None} - {None}:
            n += 1
            if not formats.business_id_ok(v):
                bad.append((k, v))
    add("business_ids", n, bad)

    # 6 countries
    vals = [(k, c["country"]) for k, c in companies.items() if c.get("country")]
    if _has(conn, "field_candidates"):
        vals += [(r[0], r[1]) for r in conn.execute("SELECT company_key, value FROM field_candidates WHERE field='country'")]
    add("countries", len(vals), [(k, v) for k, v in vals if not formats.country_ok(v)])

    # 7 amounts
    amount_cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)") if "amount" in r[1].lower()}
    bad = [("column", c) for c in sorted(amount_cols - {"amount_eur"})]
    amts = [s for s in signals if s["amount_eur"] is not None]
    bad += [(s["id"], "not a number", s["amount_eur"]) for s in amts if not isinstance(s["amount_eur"], (int, float))]
    bad += [(s["id"], "other currency named", s["adapter"]) for s in amts if _OTHER_CURRENCY.search(s["detail"] or "")]
    zero = sum(1 for s in amts if isinstance(s["amount_eur"], (int, float)) and s["amount_eur"] <= 0)
    add("amounts", len(amts), bad, f"{len(amts)} amounts, all in amount_eur; {zero} are zero (QUESTIONS_B1.md B1-15)")

    # 8 provenance
    ids = rule_ids(rules_path)
    if _has(conn, "provenance"):
        rows = [dict(r) for r in conn.execute("SELECT id, rule_id FROM provenance")]
        add("provenance", len(rows), [(r["id"], r["rule_id"]) for r in rows if r["rule_id"] not in ids],
            f"{len(ids)} ids in PROJECT_RULES.md ({sum(i.startswith('A') for i in ids)} A, {sum(i.startswith('D') for i in ids)} D)")
    else:
        add("provenance", 0, [] if ids else [("PROJECT_RULES.md", "missing")], "no provenance table in this store")
    return out


def render(results: list[dict], path) -> str:
    ok = all(r["ok"] for r in results)
    lines = [f"consistency check: {path}"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i} {r['name']:<13} {'PASS' if r['ok'] else 'FAIL'}  checked {r['checked']:,}, failed {r['failed']:,}"
                     + (f"; {r['note']}" if r["note"] else ""))
        for e in r["examples"]:
            lines.append(f"      {e}")
    lines.append(f"RESULT {'PASS' if ok else 'FAIL'}: {sum(r['ok'] for r in results)} of {len(results)} checks pass")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.consistency", description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, help="store to check, opened read-only (default RADAR_DB, else the thesis store)")
    ap.add_argument("--thesis", help="thesis file whose store to check")
    ap.add_argument("--rules", type=Path, default=RULES)
    a = ap.parse_args(argv)
    path = a.db or thesis_mod.db_path(thesis_mod.load(a.thesis))
    if not Path(path).is_file():
        print(f"no store at {path}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    results = check(conn, a.rules)
    print(render(results, path))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
