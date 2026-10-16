"""Test-only builder: labelled SYNTHETIC rows written through radar.emit. Never loaded by the app."""
from __future__ import annotations

from datetime import date, timedelta

from radar import db, emit

TODAY = date.today()


def day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def build(path):
    """Feed rows (newest first): Alpha d5 bf_funding 250000 EUR, Beta d10 register_entry, Gamma d20 register_entry low.
    Plus a cohort company (excluded) and a company with an older signal (earlier_count 1)."""
    conn = db.connect(path)
    co = lambda key, name, group="feed": emit.upsert_company(
        conn, company_key=key, name=name, source_url=f"https://example.test/synthetic/{key}", group_tag=group)
    sig = lambda key, typ, d, conf="high", **kw: emit.emit_signal(
        conn, company_key=key, signal_type=typ, date=d, confidence=conf, adapter="prh",
        source_url=f"https://example.test/synthetic/{key}/{typ}", **kw)
    co("T-alpha", "Synthetic Alpha")
    sig("T-alpha", "bf_funding", day(5), detail="Synthetic funding decision", amount_eur=250000)
    sig("T-alpha", "patent", day(200))
    co("T-beta", "Synthetic Beta")
    sig("T-beta", "register_entry", day(10), detail="Synthetic registration")
    co("T-gamma", "Synthetic Gamma")
    sig("T-gamma", "register_entry", day(20), conf="low")
    co("T-cohort", "Synthetic Cohort", group="cohort")
    sig("T-cohort", "register_entry", day(3))
    conn.commit()
    conn.close()
