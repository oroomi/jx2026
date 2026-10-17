-- Sector taxonomy (D42): the top-level sector and its sub-sectors, and the links from companies to sub-sectors. Written only by
-- radar/sectors.py (`python3 -m radar.sectors backfill --db <path>`), from the `taxonomy:` block of the thesis file; nothing here is set by hand.
-- A new pair of tables: no existing table or column is changed (D21).
--   sector          one row per taxonomy entry. parent_id is NULL for the top-level sector ("Blue economy") and points to it for a sub-sector.
--                   "Not yet classified" has a row here, but no company_sector row: a company belongs to it when it has no link at all.
--   company_sector  one row per (company, sub-sector, basis). A company can have many sub-sectors, and one sub-sector can rest on several bases.
--                   basis = the evidence kind: code (industry code), own_text (the company's own text), name_corroborated (a legal-name word
--                   backed by a record from a different source family), declared (the declared ecosystem dataset or a declared list),
--                   notice (a public procurement notice title).
--                   source_url is the public page a human opens to check the link (A27), source_label says in words what that page shows.
CREATE TABLE IF NOT EXISTS sector (
  id        INTEGER PRIMARY KEY,
  slug      TEXT NOT NULL UNIQUE,
  label     TEXT NOT NULL,
  parent_id INTEGER REFERENCES sector(id)
);
CREATE INDEX IF NOT EXISTS ix_sector_parent ON sector(parent_id);
CREATE TABLE IF NOT EXISTS company_sector (
  company_key  TEXT NOT NULL REFERENCES companies(company_key),
  sector_id    INTEGER NOT NULL REFERENCES sector(id),
  basis        TEXT NOT NULL CHECK (basis IN ('code', 'own_text', 'name_corroborated', 'declared', 'notice')),
  source_url   TEXT NOT NULL CHECK (source_url GLOB 'http*'),
  source_label TEXT NOT NULL,
  assigned_at  TEXT NOT NULL,
  PRIMARY KEY (company_key, sector_id, basis)
);
CREATE INDEX IF NOT EXISTS ix_company_sector_sector ON company_sector(sector_id);
CREATE INDEX IF NOT EXISTS ix_company_sector_company ON company_sector(company_key);
