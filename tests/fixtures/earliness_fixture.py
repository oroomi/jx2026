"""Test-only builder: labelled SYNTHETIC cohort for the earliness backtest. Never loaded by the app.
Reference date is the default 2026-01-01; the age cut is the thesis value (5 years)."""
from __future__ import annotations

from radar import db, emit


def build(path):
    conn = db.connect(path)

    def co(key, name, group="cohort", **kw):
        emit.upsert_company(conn, company_key=key, name=name, group_tag=group, country="FI", source_url=f"https://example.test/fixture/{key}", **kw)

    def sig(key, typ, d, adapter="prh", conf="high", year_only=False):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=d, confidence=conf, adapter=adapter,
                         source_url=f"https://example.test/fixture/{key}/{typ}/{d}", detail="synthetic fixture row")
        if year_only:
            sid = conn.execute("SELECT id FROM signals WHERE company_key=? AND signal_type=? AND date=?", (key, typ, d)).fetchone()[0]
            conn.execute("INSERT INTO signal_meta (signal_id, date_precision) VALUES (?, 'year')", (sid,))

    co("F-early", "Fixture Early Oy")
    sig("F-early", "register_entry", "2025-06-01")            # 214 days before: 7 months
    co("F-earlier", "Fixture Earlier Oy")
    sig("F-earlier", "register_entry", "2025-09-01")
    sig("F-earlier", "eu_project", "2024-03-01", adapter="cordis", conf="medium")  # first = 2024-03-01
    co("F-later", "Fixture Later Oy")
    sig("F-later", "eu_project", "2026-06-01", adapter="cordis", conf="medium")
    co("F-same", "Fixture Same Day Oy")
    sig("F-same", "eu_project", "2026-01-01", adapter="cordis", conf="medium")
    co("F-yearafter", "Fixture Year After Oy")
    sig("F-yearafter", "bf_funding", "2026-01-01", adapter="businessfinland", conf="medium", year_only=True)
    co("F-yearbefore", "Fixture Year Before Oy")
    sig("F-yearbefore", "bf_funding", "2024-01-01", adapter="businessfinland", conf="medium", year_only=True)
    co("F-old", "Fixture Old Oy")
    sig("F-old", "register_entry", "2015-05-05")              # older than the 5-year cut: listed, not counted
    co("F-none", "Fixture Blank Oy")
    co("F-bi", "Fixture Pipeline Oy")
    conn.execute("INSERT INTO blueinvest_profiles (profile_id, company_key, title, url, trl, fetched_at) VALUES ('fx1','F-bi','Fixture project',"
                 "'https://example.test/fixture/bi',5,'2026-10-16T00:00:00Z')")
    co("F-csv", "Fixture Csv Oy")
    sig("F-csv", "eu_project", "2025-11-01", adapter="cordis", conf="medium")
    co("F-feed", "Fixture Not Cohort Oy", group="feed")
    sig("F-feed", "register_entry", "2025-01-01")
    conn.commit()
    return conn
