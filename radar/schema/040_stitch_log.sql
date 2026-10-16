-- Stitcher step log: one row per search query, per event the LLM proposed, per verify decision and per emit.
-- The LLM proposes, plain code decides; every drop keeps its reason so a human can audit what was thrown away.
CREATE TABLE IF NOT EXISTS stitch_log (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id         TEXT NOT NULL,             -- UTC timestamp of the run
  company_key    TEXT NOT NULL,
  step           TEXT NOT NULL CHECK(step IN ('search','read','verify','emit')),
  outcome        TEXT NOT NULL,             -- search: query | llm_query; read: proposed | read_failed; verify: kept | dropped; emit: emitted | duplicate | not_emitted
  reason         TEXT,                      -- why dropped or not emitted, or what matched when kept
  query          TEXT,                      -- search step only
  signal_type    TEXT,                      -- as proposed (an existing radar.emit type, or 'unmapped')
  suggested_type TEXT,                      -- the LLM's own label when signal_type is 'unmapped' (listed in RESULT, never added)
  date           TEXT,                      -- as proposed: YYYY-MM-DD, YYYY-MM or YYYY
  date_precision TEXT,                      -- day | month | year (as proposed; verify rows hold the precision the page supports)
  source_url     TEXT,
  quote          TEXT,                      -- at most 20 words, person-shaped names redacted
  confidence     TEXT,                      -- read rows: the LLM's own; verify/emit rows: computed by the rule in emit.py
  name_match     TEXT,                      -- business_id | legal_name | core_name | domain
  public_since   TEXT,                      -- first 200 capture of source_url in the Internet Archive (YYYY-MM-DD), NULL when not archived
  archive_url    TEXT,
  signal_id      INTEGER,                   -- signals.id when emitted
  ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stitch_log_company ON stitch_log(company_key, run_id);
