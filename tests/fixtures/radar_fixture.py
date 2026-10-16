"""Test-only builder: labelled SYNTHETIC cohort and portfolio for the cohort radar. Never loaded by the app."""
from __future__ import annotations

from radar import db, emit


def build(path):
    conn = db.connect(path)

    def co(key, name, group="cohort", country="FI"):
        emit.upsert_company(conn, company_key=key, name=name, group_tag=group, country=country, source_url=f"https://example.test/fixture/{key}")

    def sig(key, typ, d, conf="high", year_only=False):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=d, confidence=conf, adapter="prh",
                         source_url=f"https://example.test/fixture/{key}/{typ}/{d}", detail="synthetic fixture row")
        if year_only:
            sid = conn.execute("SELECT id FROM signals WHERE company_key=? AND signal_type=? AND date=?", (key, typ, d)).fetchone()[0]
            conn.execute("INSERT INTO signal_meta (signal_id, date_precision) VALUES (?, 'year')", (sid,))

    co("F-top", "Fixture Top Oy")
    sig("F-top", "register_entry", "2024-02-01"); sig("F-top", "eu_project", "2025-03-01"); sig("F-top", "public_contract", "2025-05-01")
    co("F-b", "Fixture Bravo Oy")                    # 2 events, latest 2025-09-01
    sig("F-b", "register_entry", "2023-01-01"); sig("F-b", "eu_project", "2025-09-01")
    co("F-a", "Fixture Alpha Oy")                    # 2 events, latest 2025-09-01: ties with Bravo, alphabetical
    sig("F-a", "register_entry", "2022-01-01"); sig("F-a", "eu_project", "2025-09-01")
    co("F-c", "Fixture Charlie Oy")                  # 2 events, latest 2024-06-01: loses the tie on date
    sig("F-c", "register_entry", "2020-01-01"); sig("F-c", "eu_project", "2024-06-01")
    co("F-one", "Fixture Single Oy")
    sig("F-one", "bf_funding", "2024-01-01", year_only=True)
    co("F-low", "Fixture Keyword Oy")                # only a low confidence match: not counted
    sig("F-low", "register_entry", "2025-01-01", conf="low")
    co("F-none", "Fixture Blank Oy", country="DK")
    co("P-1", "Fixture Portfolio Oy", group="portfolio")
    sig("P-1", "register_entry", "2024-04-04")
    co("P-2", "Fixture Portfolio Blank Oy", group="portfolio")
    co("X-feed", "Fixture Feed Oy", group="feed")
    sig("X-feed", "register_entry", "2026-09-01")
    conn.commit()
    return conn
