# jx32_data_refresh [cloud]: see the database, refresh it from the web app

Branch: `cloud/data_refresh`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first.

## Why
Amir's architecture notes: SQL database underneath, a web app on top that can preview it, separate modules (dataset build + external APIs, web app, matching), and a button that refreshes the sources, so the pitch can say "we update the database whenever we like" without spending AI tokens. The modules already exist (MODULES.md); two things are missing: a page that shows the database, and a refresh button.

## Build
1. `/data` page (new route radar/routes/data.py, new template radar/templates/data.html): per source (adapter), rows stored, companies, newest event date, last run time; then browsable tables of companies and signals (paginated, filter by source and signal type, every row linking its source_url and its company page). Radar tables only: never the ecosystem dataset's person table or any eco_* table with people in it; hide legal names shaped like a person's name (radar/fit.py looks_like_person). Read-only.
2. Refresh: `radar/refresh.py` + a POST `/data/refresh` and a button on /data. It runs only the adapters listed in a new thesis yaml key `refresh_adapters` (start with the fast live ones: prh_notices and prh new registrations for the last 7 days). Safety, all required:
   - one global run at a time (lock file under data/), and a cooldown of 10 minutes between runs, shown on the page ("next refresh possible at HH:MM");
   - it works on a COPY of the thesis store and swaps it in with os.replace only when the run finishes and a quick_check passes; the live file is never written in place;
   - per-adapter timeout, 1 request per 2 s as every adapter already does, cached responses reused;
   - the page shows a step log for the last run (adapter, new rows, skipped, duration, errors) and "+N new companies since the last refresh" with links to them.
   No secrets, no new keys, no LLM.
3. Do not edit base.html (another session styles it); the chief adds the nav link at merge. Do not touch radar/routes/api.py, store.py feed logic, matching.py, company*.html, feed*.html, or the chief's docs. Propose a README line and a MODULES.md line in RESULT.

## Done
Tests on data/snapshot: /data renders counts that equal SQL counts; person-shaped names absent; refresh refuses during cooldown and while locked; a refresh on a temp copy swaps atomically and a failed run leaves the original file untouched (simulate an adapter error). RESULT: counts on /data for the snapshot, one refresh run's step log, pytest count. First slice (the /data page) by Sat 09:00 UTC; feature freeze Sat 18:30 UTC.
