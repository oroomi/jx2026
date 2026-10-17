-- Field candidates (jx40): every value a source states for a company field, kept side by side instead of choosing one.
-- One row per (company, field, source, compared value). Written only by radar/candidates.py (`python3 -m radar.candidates build`),
-- rebuilt in full on each run. A new table: no existing table or column is changed, and no page reads it yet.
--   source      adapter NAME that states the value (prh, declared, universe, businessfinland, hilma, cordis, ecosystem,
--               blueinvest, brreg, cvr), or 'store' for the value the companies table holds today (what live pages show)
--   value       as the source states it; value_norm is the form two candidates are compared in (rules in radar/candidates.py)
--   basis       what the value is in that source, in words ("legal name (main name, PRH)", "city in the ecosystem dataset")
--   precision   founded only: day, month or year
--   lang        industry_desc only: ISO 639-1 code of the description language, NULL when unknown
--   observed    ISO date the source was read (fetch date, dataset verification date, or export import date)
--   rule_id     the PROJECT_RULES.md assumption that picks the value live pages show today (A1: the PRH register is the one
--               source of record; every other source only matches or inserts)
--   field_rule  the PROJECT_RULES.md assumption that defines the field (A1, A18 date precision, A29 country code)
--   applied     1 when value_norm equals the store's value under the field's comparison rule
--   status      applied (the store row), agrees, differs, not_comparable (descriptions in two languages), store_empty (the
--               store holds NULL), PENDING_DECISION (an open
--               question in QUESTIONS_B<n>.md names this row; issue_id says which). Never set on an applied row.
CREATE TABLE IF NOT EXISTS field_candidates (
  id           INTEGER PRIMARY KEY,
  company_key  TEXT NOT NULL,
  field        TEXT NOT NULL CHECK (field IN ('name','founded','industry_code','industry_desc','town','website','register_status','country')),
  value        TEXT NOT NULL,
  value_norm   TEXT NOT NULL,
  basis        TEXT NOT NULL,
  precision    TEXT CHECK (precision IS NULL OR precision IN ('day','month','year')),
  lang         TEXT,
  source       TEXT NOT NULL,
  source_url   TEXT NOT NULL CHECK (source_url LIKE 'http://%' OR source_url LIKE 'https://%'),
  observed     TEXT,
  rule_id      TEXT NOT NULL,
  field_rule   TEXT NOT NULL,
  applied      INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0,1)),
  status       TEXT NOT NULL CHECK (status IN ('applied','agrees','differs','not_comparable','store_empty','PENDING_DECISION')),
  issue_id     TEXT,
  built_at     TEXT NOT NULL,
  UNIQUE (company_key, field, source, value_norm),
  CHECK (NOT (applied = 1 AND status = 'PENDING_DECISION'))
);
CREATE INDEX IF NOT EXISTS ix_field_candidates_company ON field_candidates(company_key, field);
CREATE INDEX IF NOT EXISTS ix_field_candidates_status ON field_candidates(status, issue_id);
