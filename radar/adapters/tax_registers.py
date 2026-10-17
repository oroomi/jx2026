"""Tax Administration registers in the PRH/YTJ open data (CC BY 4.0): the earliest public traces of a company trading.

registeredEntries carry register (1 trade, 4 Tax Administration, 5 prepayment, 6 VAT liability, 7 employer), type,
registrationDate and endDate. Per company:
  first_sales    earliest of the VAT-liable entry (register 6, code 6_80, API type 80 in register 6) and the prepayment register entry (5)
  first_hire     earliest employer register (7) entry: the day the company could first pay a salary
  sales_ended / employer_ended  only when every entry of that kind has an endDate (the latest one is the date)
Months from founding to first hire are stored in company_traction, a derived field, never as a signal.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

import httpx

from radar import emit
from radar.adapters import prh

NAME = "tax_registers"
PHASE = 2  # enricher: only companies that prh and the declared loader already inserted
YTJ_PAGE = "https://tietopalvelu.ytj.fi/yritys/"
VAT_REGISTER, PREPAYMENT_REGISTER, EMPLOYER_REGISTER = "6", "5", "7"
VAT_LIABLE_TYPE = "6_80"
MAX_REQUESTS = 600
MAX_CONSECUTIVE_FAILURES = 3
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def months_between(start: str, end: str) -> int | None:
    """Whole calendar months from start to end (2022-01-31 to 2022-09-01 is 7). None if either is missing or end is earlier."""
    if not start or not end or not _ISO.match(start) or not _ISO.match(end):
        return None
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if b < a:
        return None
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def _code(register: str, type_) -> str:
    """REK_KDI code. The live API gives type "80" inside register "6"; the code list writes it "6_80". Both forms map to "6_80"."""
    t = str(type_)
    return t if "_" in t else f"{register}_{t}"


def _entries(company: dict, register: str, type_: str | None = None) -> list[dict]:
    out = []
    for e in company.get("registeredEntries", []) or []:
        if str(e.get("register")) != register or not _ISO.match(str(e.get("registrationDate") or "")):
            continue
        code = _code(register, e.get("type"))
        if code.endswith("_99") or (type_ is not None and code != type_):  # x_99 = "Incorrect line" in REK_KDI
            continue
        out.append(e)
    return out


def _ended(entries: list[dict]) -> str | None:
    """The latest endDate, only when every entry has one; a still-open entry means the activity has not ended."""
    ends = [e.get("endDate") for e in entries]
    if not entries or not all(ends) or not all(_ISO.match(str(d)) for d in ends):
        return None
    return max(ends)


def extract(company: dict) -> dict:
    """Pure: the traction facts of one YTJ company record. Keys absent from the register stay None."""
    vat = _entries(company, VAT_REGISTER, VAT_LIABLE_TYPE)
    pre = _entries(company, PREPAYMENT_REGISTER)
    emp = _entries(company, EMPLOYER_REGISTER)
    first_sales = None
    cands = [(min(e["registrationDate"] for e in vat), "VAT liability register")] if vat else []
    if pre:
        cands.append((min(e["registrationDate"] for e in pre), "prepayment register"))
    if cands:
        first_sales = min(cands)  # (date, register name); a tie names the VAT register
    return {
        "first_sales": first_sales,
        "first_hire": min(e["registrationDate"] for e in emp) if emp else None,
        "sales_ended": _ended(vat + pre),
        "employer_ended": _ended(emp),
    }


def _urls(y_tunnus: str) -> tuple[str, str]:
    return YTJ_PAGE + y_tunnus, prh._url({"businessId": y_tunnus})


def emit_for(conn: sqlite3.Connection, row, company: dict) -> int:
    """Emit the signals and the derived row for one stored company from its YTJ record. Returns the number of new signals."""
    key, yt, founded = row["company_key"], row["y_tunnus"], row["founded"]
    page, api = _urls(yt)
    t = extract(company)
    new = 0

    def sig(kind, day, detail):
        nonlocal new
        new += emit.emit_signal(conn, company_key=key, signal_type=kind, date=day, source_url=page, confidence="high",
                                adapter=NAME, detail=f"{detail} Source: PRH/YTJ open data {api}")

    if t["first_sales"]:
        day, reg = t["first_sales"]
        sig("first_sales", day, f"Entered the {reg} on {day}: the company is invoicing.")
    months = months_between(founded, t["first_hire"])
    if t["first_hire"]:
        after = f", {months} months after founding" if months is not None else ""
        sig("first_hire", t["first_hire"], f"Entered the employer register {t['first_hire']}{after} (PRH).")
    if t["sales_ended"]:
        sig("sales_ended", t["sales_ended"], f"Left the VAT liability and prepayment registers on {t['sales_ended']}.")
    if t["employer_ended"]:
        sig("employer_ended", t["employer_ended"], f"Left the employer register on {t['employer_ended']}.")
    conn.execute(
        """INSERT INTO company_traction (company_key, founded, first_hire_date, months_to_first_hire, checked_at) VALUES (?,?,?,?,?)
           ON CONFLICT(company_key) DO UPDATE SET founded=excluded.founded, first_hire_date=excluded.first_hire_date,
             months_to_first_hire=excluded.months_to_first_hire, checked_at=excluded.checked_at""",
        (key, founded, t["first_hire"], months, emit.now_utc()))
    return new


def run(conn: sqlite3.Connection, thesis: dict) -> dict:
    stats = {"companies": 0, "signals": 0, "skipped": 0, "requests": 0, "blocked": 0}
    rows = conn.execute(
        """SELECT company_key, y_tunnus, founded FROM companies WHERE y_tunnus IS NOT NULL
           ORDER BY CASE group_tag WHEN 'cohort' THEN 0 WHEN 'portfolio' THEN 1 ELSE 2 END, founded DESC""").fetchall()
    failures = 0
    for r in rows:
        if stats["requests"] >= MAX_REQUESTS:
            break
        try:
            data, net = prh.fetch({"businessId": r["y_tunnus"]})
        except httpx.HTTPError:
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES:
                stats["blocked"] = 1  # source unreachable: stop cleanly, keep what was written
                break
            continue
        failures = 0
        stats["requests"] += net
        hit = next((c for c in data.get("companies", []) if c["businessId"]["value"] == r["y_tunnus"]), None)
        if hit is None:
            continue
        stats["signals"] += emit_for(conn, r, hit)
        stats["companies"] += 1
    stats["skipped"] = len(rows) - stats["companies"]
    return stats


if __name__ == "__main__":
    from radar import db
    print(run(db.connect(), prh._load_thesis()))
