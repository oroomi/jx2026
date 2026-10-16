CLOUD SESSION VERSION. You are a claude.ai/code cloud session on the oroomi/jx2026 repo, not the VPS farm. Differences from the text below: ignore every /root/hack path, worktree, spare port, shot.py and deploy instruction; work on the current checkout; create branch cloud/<task name without the jx number> (for example cloud/prh_notices); check your pages with pytest and a local uvicorn plus curl; commit often with messages that say what works; push the branch to origin when the RESULT line is true. Everything else below (rules, sources, build steps, tests, RESULT) applies unchanged. The repo's CLAUDE.md is the code contract.


TASK jx22: EU Funding and Tenders grants reference data adapter: EMFAF, LIFE and Horizon beneficiaries in Finland as dated eu_grant signals

Context: you are a farm builder for team Old Hackers at JunctionX Turku (Redstone x A'Pelago "Ocean Opportunity Radar"). This is the second overnight chain (the Saturday build). Read CLAUDE.md (especially "Code contract"), TASKS.md, DESIGN.md, STATUS.md and radar/emit.py first. The stack is decided: Python 3.12, FastAPI, Jinja2, htmx (vendored), SQLite. Do not change the stack, the shared contract files (radar/emit.py, radar/db.py, radar/schema/001_core.sql, config/thesis*.yaml) or any file not listed under "You own". Your worktree is created from main HEAD, which does NOT contain the predecessor branches: the "Start by merging" step below is mandatory and comes before any other work. Test fixtures that imitate a source must live under tests/fixtures/ (or be built inside the test), be named as fixtures, and are never loaded by the app.

Why this chain exists: the partner judges CREATIVITY first, usability second, visuals last. Night one shipped a working feed, but 81 of its 82 rows are "new register entry" matches on a name keyword only ("meri", "sea", for example a software publisher called Meridian Vector Oy), which reads as noise, and the stronger sources (Business Finland, CORDIS, BlueInvest) hold 0 signals. This chain adds those sources, makes the feed precise and explainable, and builds the earliness backtest (would the radar have found the Nordic Blue 2026 cohort before January 2026) and the cohort radar. Honest blanks are part of the product: a company with no public signal is shown as empty, never filled.

FARM RULES (non-negotiable, the chief greps for violations afterwards):
- Never read, open, grep, cat, copy or edit any .env, token, key or credential file, anywhere (including /root/.secrets, /root/.config, /root/orchestrator, /root/.claude*). If something needs a key you do not hold, write BLOCKED in your RESULT and continue without it.
- Never run pkill, killall or any text-pattern kill. Stop a server only by port (fuser -k 8151/tcp) or by the PID you started.
- Never touch crontab (no crontab -e, no cron files) and never touch /root/notify/decisions.json.
- No fabricated data. Every number on a page traces to a row in the database, and every row to a source_url a human can open. Missing stays NULL and is shown as "not in public records" or "no public evidence". No lorem ipsum, no placeholder avatars, no hard-coded company facts in code or templates.
- No em dashes (the long dash character) in any file, template, test, commit message or printed output. Use a colon, comma or hyphen.
- Companies only. No named private individuals in data, copy, tests, fixtures or logs.
- Declared data lives only under data/declared/ and is read only for you. Data you fetch goes to data/cache/ or data/fetched/ (both gitignored).
- Commit on your own branch every 20-30 minutes with a message that says what works now. An uncommitted worktree is lost work.
- Never touch port 8130 or the hack-jx2026 service unless this task says so. Use only the spare port named below.
- Never invent a fact about a real company. A name, date, amount, TRL, customer or relationship appears only if a row in the database or a fetched source states it, and its source_url is stored with it. Empty shows as empty: NULL stays NULL, and the page says "not in public records" or "no public evidence". When two readings of a source are possible, store the cautious one and say so in the detail text.
- A fixture that imitates a source uses obviously synthetic names (for example "Fixture Oy") and never a real company's facts.
- Exit cleanly: later tasks wait for a done file with rc0 from you. Part of your task being BLOCKED (no key, a 403, a missing file) goes in your RESULT line, never in a crash, a hang or a non-zero exit. Commit whatever passes first.
- Docs are chief-owned: do not edit README.md, ARCHITECTURE.md, EVAL.md, DISCLOSURE.md, DEMO_SCRIPT.md, PILOT.md, DESIGN.md, CLAUDE.md or TASKS.md. Put a paragraph starting "DOCS NOTE:" in the body of your last commit message with the facts the chief should copy (counts, sources, rules, limits).
- Git hygiene: add files by explicit path. Never run git add -A, git add . or git add data/ . data/declared/businessfinland.xlsx and data/declared/README.md are untracked in the main checkout on purpose and must stay out of every commit. Never write into /root/hack/jx2026/data (the main checkout's data directory).
- Finish with exactly one last line starting with "RESULT:" (one sentence a judge could repeat, with URL or local URL, counts and screenshot paths). If part of the task is blocked, say BLOCKED and why inside that sentence; still commit whatever passes.

Why: CORDIS (jx13) covers Horizon only. The EU Funding and Tenders portal publishes one reference file with every grant and its beneficiaries across programmes, including EMFAF (fisheries and maritime fund) and LIFE, which are blue-economy money nobody joins to Finnish companies.

Source (tested from this server 16 Oct): https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json (about 83 MB). Download once to data/cache/eu/ with a resume-capable curl, never commit it. Parse streaming (ijson if installed, else json with care for memory: the builder cap is 3 GB).

Start: worktree from main HEAD after jx17. Branch task/jx22_eu_grants. Spare port 8158. Do not deploy. You own radar/adapters/eu_grants.py (new), tests/test_eu_grants.py (new), DISCLOSURE.md (additive), one phase line in radar/build.py.

Build:
1. Inspect the file's structure first and write what you found into the adapter docstring (field names for programme, call, grant start date, beneficiaries with country and name, amounts). Do not assume.
2. Emit one "eu_grant" signal per Finnish beneficiary per grant: date = grant start or signature date as given (if only a year exists, set precision year as jx11 did), amount if given, programme name in detail, source_url = the portal's grant page if the file carries an ID that maps to one, else the reference file URL plus the grant ID in the detail. Confidence medium (name match) unless a PIC or VAT maps to a business ID we hold (then high).
3. Match beneficiaries to companies in the store by folded legal name; unmatched Finnish SMEs in blue-economy programmes (EMFAF, BlueInvest-related calls, Horizon cluster 6) enter as discovery companies with the thesis keyword check, as jx13 did.
4. Dedupe against jx13's eu_project signals (same company, same project acronym or ID: keep one, note the other source in detail).
5. Tests on a 20-record synthetic fixture: parsing, year-only precision, dedupe, country filter.
Commit on this branch. Finish with: RESULT: <one sentence with grants parsed, Finnish beneficiaries, eu_grant signals by programme, discovery companies added, pytest count>.
