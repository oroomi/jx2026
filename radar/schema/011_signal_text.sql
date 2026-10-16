-- The source's own words for a signal (a project title or objective as the source printed it), kept apart from the
-- `detail` annotation our adapters write. The feed reads thesis words only from here, never from `detail`.
CREATE TABLE IF NOT EXISTS signal_text (
  signal_id INTEGER NOT NULL,
  field     TEXT NOT NULL,      -- 'title' | 'objective' | 'keywords'
  text      TEXT NOT NULL,
  PRIMARY KEY (signal_id, field)
);
