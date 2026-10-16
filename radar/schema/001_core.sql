-- Core contract. Every adapter writes ONLY through radar.emit. Later schema files add tables, never edit this one.
CREATE TABLE IF NOT EXISTS companies (
  company_key   TEXT PRIMARY KEY,          -- y-tunnus ("3543918-7") when known, else slug "dk-cvr-43933760" or "name:emission-eye"
  name          TEXT NOT NULL,
  y_tunnus      TEXT,
  country       TEXT,                      -- ISO 2 letter, NULL when unknown
  founded       TEXT,                      -- ISO date from a register, NULL when unknown (never guessed)
  industry_code TEXT,                      -- TOL 2008 / NACE code as stated by the register
  industry_desc TEXT,
  website       TEXT,
  group_tag     TEXT NOT NULL DEFAULT 'feed',   -- cohort | portfolio | feed
  register_status TEXT,                    -- active | bankrupt | ended | unknown (derived from companySituations, not top-level status)
  source_url    TEXT NOT NULL,             -- the page a human opens to check the row
  fetched_at    TEXT NOT NULL              -- ISO UTC
);
CREATE TABLE IF NOT EXISTS signals (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_key  TEXT NOT NULL REFERENCES companies(company_key),
  signal_type  TEXT NOT NULL,              -- one of radar.emit.SIGNAL_TYPES
  date         TEXT NOT NULL,              -- ISO date the event happened (not the fetch date)
  source_url   TEXT NOT NULL,              -- public page or file that shows the event
  confidence   TEXT NOT NULL,              -- high | medium | low (rule printed in the UI, see docs in emit.py)
  adapter      TEXT NOT NULL,              -- adapter NAME that emitted it
  detail       TEXT,                       -- one human sentence, facts only, no inference
  amount_eur   REAL,                       -- only when the source states an amount
  fetched_at   TEXT NOT NULL,
  UNIQUE (company_key, signal_type, date, source_url)
);
CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date);
CREATE INDEX IF NOT EXISTS idx_signals_company ON signals(company_key);
