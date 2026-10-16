"""Test-only builder: inserts labelled SYNTHETIC rows through radar.emit. Never loaded by the app."""
from __future__ import annotations

from datetime import date, timedelta

from radar import db, emit

TODAY = date(2026, 10, 16)


def day(n: int) -> str:
    """ISO date n days before TODAY."""
    return (TODAY - timedelta(days=n)).isoformat()


def build(path):
    conn = db.connect(path)
    co = lambda key, name, group="feed", **kw: emit.upsert_company(
        conn, company_key=key, name=name, source_url=f"https://example.test/synthetic/{key}", group_tag=group, **kw)
    sig = lambda key, typ, d, conf="high", adapter="prh", url=None, **kw: emit.emit_signal(
        conn, company_key=key, signal_type=typ, date=d, confidence=conf, adapter=adapter,
        source_url=url or f"https://example.test/synthetic/{key}/{typ}/{d}", **kw)
    co("T-edge90", "Synthetic Edge Ninety", y_tunnus="0000001-1")
    sig("T-edge90", "register_entry", day(90))
    co("T-edge91", "Synthetic Edge Ninetyone")
    sig("T-edge91", "register_entry", day(91))
    co("T-future", "Synthetic Future")
    sig("T-future", "register_entry", (TODAY + timedelta(days=3)).isoformat())
    co("T-cohort", "Synthetic Cohort", group="cohort")
    sig("T-cohort", "register_entry", day(10))
    co("T-port", "Synthetic Portfolio", group="portfolio")
    sig("T-port", "bf_funding", day(12))
    co("T-multi", "Synthetic Multi")
    sig("T-multi", "bf_funding", day(5), adapter="businessfinland")
    sig("T-multi", "register_entry", day(40))
    sig("T-multi", "patent", day(120))
    co("T-offlist", "Synthetic Offlist")
    sig("T-offlist", "site_customer", day(3))
    co("T-tie", "Synthetic Tie")
    sig("T-tie", "register_entry", day(20), conf="low")
    sig("T-tie", "public_contract", day(20), conf="high", adapter="hilma")
    co("T-low", "Synthetic Low", )
    sig("T-low", "job_ad", day(8), conf="low", adapter="somewhere", url="https://jobs.example.test/x")
    co("T-ita", "Itämeri Synthetic Oy", y_tunnus="0000009-9")
    sig("T-ita", "eu_project", day(30), adapter="cordis")
    conn.commit()
    return conn
