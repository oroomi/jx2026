-- Declared ecosystem dataset (data/declared/ecosystem/blue_economy_fi.sqlite), written only by radar/adapters/ecosystem.py.
-- Capital sources and buyers (supply-side startups become rows in `companies`, group_tag 'ecosystem' when new).
CREATE TABLE IF NOT EXISTS eco_entity (
  entity_id   TEXT PRIMARY KEY,           -- the dataset's id, BE0001 ...
  name        TEXT NOT NULL,
  entity_type TEXT,
  side        TEXT NOT NULL,              -- supply | capital | demand
  business_id TEXT,
  country     TEXT,
  city        TEXT,
  website     TEXT,
  status      TEXT,                       -- active | defunct | acquired_or_renamed | dormant_unverified
  stage       TEXT,
  confidence  TEXT,                       -- the dataset's own word: high | medium | low
  company_key TEXT,                       -- set for supply entities: the row in companies
  source_url  TEXT                        -- website, else the first source the dataset lists
);
CREATE INDEX IF NOT EXISTS idx_eco_entity_company ON eco_entity(company_key);
-- Scored startup-to-target pairs. `why` is the dataset's reason string, verbatim.
CREATE TABLE IF NOT EXISTS eco_match (
  company_key TEXT NOT NULL,
  target_id   TEXT NOT NULL REFERENCES eco_entity(entity_id),
  target_side TEXT NOT NULL,              -- capital | demand
  target_type TEXT,
  score       REAL NOT NULL,
  why         TEXT,
  confidence  TEXT,                       -- the weaker of the two entities' dataset confidence words
  PRIMARY KEY (company_key, target_id)
);
-- Readiness evidence text per company, shown beside the rule-derived levels, never replacing them.
CREATE TABLE IF NOT EXISTS eco_readiness (
  company_key TEXT PRIMARY KEY,
  entity_id   TEXT,
  trl         INTEGER,
  br_score    INTEGER, br_evidence TEXT, br_missing TEXT,
  ir_score    INTEGER, ir_evidence TEXT, ir_missing TEXT,
  oi_score    INTEGER, oir_score INTEGER, oir_evidence TEXT,
  customer_evidence TEXT,
  sources     TEXT,                       -- newline separated http(s) links
  confidence  TEXT,
  last_verified TEXT
);
CREATE TABLE IF NOT EXISTS eco_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
