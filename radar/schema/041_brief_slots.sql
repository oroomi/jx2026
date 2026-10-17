-- The AI summary card: six fixed slots per company (what_it_does, thesis_fit, readiness, who_to_meet, what_the_fund_should_do,
-- whats_missing), each {text, cites} or null. Written only by `python3 -m radar.briefs import`; every slot has passed radar/briefs.py.
CREATE TABLE IF NOT EXISTS company_brief_slots (
  company_key TEXT PRIMARY KEY,
  written     TEXT NOT NULL,
  slots_json  TEXT NOT NULL,
  imported_at TEXT NOT NULL
);
