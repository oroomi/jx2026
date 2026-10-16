-- Extra facts about a signal that the core table does not carry. Written by adapters after emit_signal.
CREATE TABLE IF NOT EXISTS signal_meta (
  signal_id      INTEGER PRIMARY KEY REFERENCES signals(id),
  date_precision TEXT NOT NULL DEFAULT 'day' CHECK(date_precision IN ('day','year')),
  funding_types  TEXT,
  rows_aggregated INTEGER
);
