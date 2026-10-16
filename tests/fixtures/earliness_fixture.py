"""Test-only builder: labelled SYNTHETIC cohort for the earliness backtest. Never loaded by the app.
Reference date is the default 2026-01-01; the age cut is the thesis value (5 years)."""
from __future__ import annotations

from radar import db, emit


NO_CODE = {"F-outside", "F-corrob", "F-name-only"}


def build(path):
    conn = db.connect(path)

    def co(key, name, group="cohort", **kw):
        if group == "cohort" and "industry_code" not in kw and key not in NO_CODE:
            kw["industry_code"] = "03211"  # on the thesis list, so the live signals of these fixture companies pass the feed rule
        emit.upsert_company(conn, company_key=key, name=name, group_tag=group, country="FI", source_url=f"https://example.test/fixture/{key}", **kw)

    def sig(key, typ, d, adapter="prh", conf="high", year_only=False, detail="synthetic fixture row"):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=d, confidence=conf, adapter=adapter,
                         source_url=f"https://example.test/fixture/{key}/{typ}/{d}", detail=detail)
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
    # thesis-test cases: registered facts decide, not the register date alone
    co("F-outside", "Fixture Outside Oy", industry_code="62100", industry_desc="Computer programming activities")
    sig("F-outside", "register_entry", "2025-06-01")            # early register entry, code not on the thesis list: outside the rule
    co("F-corrob", "Fixture Marine Works Oy")
    sig("F-corrob", "register_entry", "2025-05-01")             # name word 'marine' alone is not enough ...
    sig("F-corrob", "eu_project", "2025-07-01", adapter="cordis", conf="medium")  # ... a second source on the later date backs it
    co("F-name-only", "Fixture Marine Only Oy")
    sig("F-name-only", "register_entry", "2025-05-01")          # name word only, no second source: outside the rule
    co("F-research", "Fixture Research Oy", industry_code="03211")
    sig("F-research", "site_customer", "2025-03-01", adapter="declared", conf="medium", detail="declared research: pilot with a named harbour")
    sig("F-research", "eu_project", "2026-03-01", adapter="cordis", conf="medium")
    co("F-research-low", "Fixture Research Low Oy", industry_code="03211")
    sig("F-research-low", "site_customer", "2025-03-01", adapter="declared", conf="low", detail="declared research: unverified pilot")
    co("F-feed", "Fixture Not Cohort Oy", group="feed")
    sig("F-feed", "register_entry", "2025-01-01")
    conn.commit()
    return conn
