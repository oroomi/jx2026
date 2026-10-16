-- BlueInvest Project Pipeline profiles (public pages). One row per profile; written only by radar/adapters/blueinvest.py.
CREATE TABLE IF NOT EXISTS blueinvest_profiles (
  profile_id   TEXT PRIMARY KEY,     -- the other_id of the detail page
  company_key  TEXT,                 -- set only when matched to or inserted as a company
  title        TEXT,                 -- project title as printed
  company_name TEXT,                 -- "Company behind project" as printed (often a project name)
  country      TEXT,                 -- country text as printed
  trl          INTEGER,              -- NULL when the page states none
  sector       TEXT,
  description  TEXT,                 -- verbatim page text, whitespace trimmed
  url          TEXT NOT NULL,        -- public detail page
  listed_date  TEXT,                 -- ISO date, only when the page states a listing/creation/publication date
  fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blueinvest_company ON blueinvest_profiles(company_key);
