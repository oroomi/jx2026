"""Test-only builder: labelled SYNTHETIC rows for the feed precision rule. Never loaded by the app.
Thesis words used: code 30110 and the words 'sea', 'water' (default thesis); code 32500 and 'health' (health thesis)."""
from __future__ import annotations

from datetime import date, timedelta

from radar import db, emit

TODAY = date.today()


def day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def build(path, *, words=("sea", "water"), code="30110", code_note_desc="Fixture shipbuilding",
          hilma_kw="vesi"):
    conn = db.connect(path)
    w1, w2 = words

    def co(key, name, **kw):
        emit.upsert_company(conn, company_key=key, name=name, source_url=f"https://example.test/fixture/{key}", **kw)

    def sig(key, typ, d, adapter="prh", **kw):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=d, confidence=kw.pop("conf", "medium"), adapter=adapter,
                         source_url=f"https://example.test/fixture/{key}/{adapter}/{typ}/{d}", **kw)

    co("F-code", "Fixture Code Oy", industry_code=code, industry_desc=code_note_desc)
    sig("F-code", "register_entry", day(10))
    co("F-lob", "Fixture Lob Oy", industry_code="58290", industry_desc=f"Construction of {w2} projects")
    sig("F-lob", "register_entry", day(11))
    co("F-own", "Fixture Own Oy", industry_code="58290", industry_desc="Software publishing")
    sig("F-own", "public_contract", day(12), adapter="hilma", detail=f"Fixture Buyer: Tutkimus {hilma_kw}n tilasta (EUR 1,000)")
    co("F-corr", f"Fixture {w1.title()} Oy", industry_code="58290", industry_desc="Software publishing")
    sig("F-corr", "register_entry", day(13))
    sig("F-corr", "public_contract", day(400), adapter="hilma", detail="Fixture Buyer: Office chairs (EUR 10)")
    co("F-one", f"Fixture {w1.title()} One Oy", industry_code="58290", industry_desc="Software publishing")
    sig("F-one", "register_entry", day(14))
    sig("F-one", "register_entry", day(300), conf="low")  # same adapter twice: not corroboration
    co("F-weak", f"Fixture {w1.title()} Weak Oy", industry_code="58290", industry_desc="Software publishing")
    sig("F-weak", "register_entry", day(15))
    co("F-year", f"Fixture {w1.title()} Year Oy", industry_code="58290", industry_desc="Software publishing")
    sig("F-year", "register_entry", day(16))
    sig("F-year", "bf_funding", f"{TODAY.year - 1}-06-30", adapter="businessfinland",
        detail="Fixture funding, year only (the export states the year)")
    co("F-yearonly", "Fixture Yearonly Oy", industry_code=code)
    sig("F-yearonly", "bf_funding", f"{TODAY.year}-01-01", adapter="businessfinland", detail="Fixture funding, year only")
    conn.commit()
    return conn
