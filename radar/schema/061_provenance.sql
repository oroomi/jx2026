-- Provenance (jx40): a change log of rule-driven transformations. Every entry cites the PROJECT_RULES.md assumption (A<n>)
-- or decision (D<n>) behind it. Written only by radar/provenance.py: `seed` records the decisions already taken in the repo
-- (dates and counts as the repo states them), and a tool that changes records appends one entry per run (radar/candidates.py
-- build). A new table: no existing table or column is changed, and no page reads it yet.
--   at          UTC time of the change: the commit time for a seeded decision, the run time for a tool
--   rule_id     A<n> or D<n>; radar/consistency.py fails when the id is not in PROJECT_RULES.md
--   kind        decision (a dated decision taken in the repo) or run (a tool applied rules to a store)
--   affected    the records affected, in words, as the source states them ("main 36 to 30, weak 86 to 92"); NULL when no
--               count is written anywhere, never estimated
--   evidence    where the count or reason is written (commit sha, file)
CREATE TABLE IF NOT EXISTS provenance (
  id          INTEGER PRIMARY KEY,
  at          TEXT NOT NULL,
  rule_id     TEXT NOT NULL CHECK (rule_id GLOB 'A[0-9]*' OR rule_id GLOB 'D[0-9]*'),
  kind        TEXT NOT NULL CHECK (kind IN ('decision', 'run')),
  action      TEXT NOT NULL,
  scope       TEXT,
  affected    TEXT,
  commit_sha  TEXT,
  evidence    TEXT,
  recorded_at TEXT NOT NULL,
  UNIQUE (rule_id, kind, at, action)
);
CREATE INDEX IF NOT EXISTS ix_provenance_rule ON provenance(rule_id);
