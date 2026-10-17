-- Verified AI summaries of a company's public record. Written only by `python3 -m radar.briefs import`; every sentence carries
-- cites (urls from that company's own export) and has passed the code checks in radar/briefs.py.
CREATE TABLE IF NOT EXISTS company_briefs (
  company_key    TEXT PRIMARY KEY,
  written        TEXT NOT NULL,      -- ISO date the brief was written
  sentences_json TEXT NOT NULL,      -- [{"text": "...", "cites": ["https://..."]}]
  imported_at    TEXT NOT NULL
);
