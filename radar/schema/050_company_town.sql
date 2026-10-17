-- Home town of a company: the post office name of its current registered address in PRH/YTJ (visiting address first, else postal),
-- title-cased, e.g. "Turku". NULL when the register states no Finnish address. Written by radar/town.py (set_town), never by hand.
-- town_source_url is the page a human opens to check it. SQLite has no ADD COLUMN IF NOT EXISTS, so radar/db.py skips an
-- ALTER TABLE ... ADD COLUMN whose column already exists; this file is safe to apply at every start.
ALTER TABLE companies ADD COLUMN town TEXT;
ALTER TABLE companies ADD COLUMN town_source_url TEXT;
