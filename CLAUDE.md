# Ocean Opportunity Radar: JunctionX Turku 2026 (Redstone x A'Pelago), team Old Hackers

Team: Dayo (demo, partner desks, docs with the chief) + Amir (GitHub amirhnourian; agentic stitcher with citations, explainable match rules; branches amir/<task>) + cloud builder (Dayo's claude.ai cloud session; branches cloud/<task>) + the chief and the build farm on the VPS (branches task/<name>).
Event window: Fri 16 Oct 18:00 to Sun 18 Oct 18:00 Helsinki. Deadline Sun 11:00 Helsinki (Dayo's schedule for this repo overrides the earlier 10:00).

## Clock

Doors close Fri 22:00 Helsinki (humans leave; the farm and the cloud builder work overnight), open Sat 09:00. Times below are Helsinki (UTC+3 until 25 Oct).
- Sat 21:30: feature freeze. Only bug fixes, copy, docs, screenshots after this point.
- Sun 09:30: ZIP built and submitted; confirm the platform shows receipt. Deadline Sun 11:00.

## Non-negotiables
- Everything in this repo was written during the event. The first commit is the bell. Anything pre-existing that we
  use is declared in DISCLOSURE.md: public datasets, our VPS + domain + tunnel, open-source libraries, and the generic
  process scripts in /root/hack/bin (screenshots, smoke test, deploy). Nothing else from any earlier project.
- No fabricated data. Every number on screen traces to a row in the data. Missing data shows "no data", never a
  placeholder that looks real. No lorem ipsum anywhere, ever.
- Companies only, never named private individuals.
- No secrets in the repo. Environment goes in .env (gitignored), loaded by systemd.
- Secrets: never read, write, rename, copy or overwrite any .env, token, key or credential file outside
  this directory (including /root/orchestrator/.env, /root/.secrets, /root/.config, /root/.claude*). Keys
  reach the app only through an EnvironmentFile that already exists here. If a key is missing, mark that
  item BLOCKED and continue. A task that changes a shared secrets file is detected and reported.
- Finnish copy: no em dashes. Money and dates in Finnish format if shown.

## The loop (every task, no exceptions)
1. Take the task from TASKS.md. Write the concrete check first (a test, or the exact URL + what must be visible).
2. Build the smallest thing that passes. Commit every 20-30 minutes; the message says what works now.
3. Deploy: `/root/hack/bin/deploy.sh <name> <dir> <port> "<start command>"` (see DEPLOY section below).
4. Look: `/root/hack/bin/shot.py <url> --name <task>` then READ desktop.png and mobile.png. Fix what you see.
5. Prove: `/root/hack/bin/smoke.py <url>` prints PASS, and `pytest -q` is green.
6. Done = works on the public URL + both screenshots reviewed + tests green + README section updated.
   End with `RESULT: <one sentence a judge could repeat, with URL and screenshot paths>`.

## Stack (decided Fri 16 Oct, final; do not debate or add a second framework)
- Backend: Python 3.12 + FastAPI + Jinja2 templates + htmx (vendored in radar/static/vendor, no CDN at runtime). Frontend: server-rendered HTML, CSS tokens from DESIGN.md.
- Data: SQLite at data/radar.sqlite (gitignored, rebuilt by `python3 -m radar.build`).   Port: 8130.
- Start: `python3 -m uvicorn app:app --host 127.0.0.1 --port 8130`
- Public URL: https://jx.hankintaviikko.fi (already routed to 8130).  Deploy: `systemctl stop hack-jxhello` once, then `/root/hack/bin/deploy.sh jx2026 /root/hack/jx2026 8130 "python3 -m uvicorn app:app --host 127.0.0.1 --port 8130"`
- Tests: `python3 -m pytest -q`.  Spare ports for builders' own checks: 8150-8159 (one per task, named in the task file).

## What this product is (the partners' words)
Redstone x A'Pelago, "Ocean Opportunity Radar": turn fragmented startup and ecosystem data into decision-ready venture intelligence.
Criteria they named, in order: creativity, usability, scalability and transferability, technical execution, visual appeal.
Three screens, discovery then judgment then matching:
1. Early-signal feed (`/`): blue-economy companies that surfaced in the last 90 days across unusual public sources, newest first. Row = company, the signal that found it, date, source link.
2. Company page (`/c/{company_key}`): their four questions in their order, with sourced facts: 01 Who is most promising (thesis fit with reasons), 02 How ready are they (TRL, business, investment, ocean impact; each a level with the printed rule and evidence links), 03 Who comes next (investors, grants, programmes, buyers in priority order, reason beside each), 04 What should happen next (one sentence from a decision table, "because" plus link).
3. Cohort radar (`/radar`): the 19 Nordic Blue companies and 9 Redstone portfolio companies with the EARLINESS backtest chart (first public signal date versus cohort entry date).
Transferability: everything sector-specific lives in `config/thesis.yaml` (swap with env `RADAR_THESIS=config/thesis_health_turku.yaml`). No sector word in code.

## Code contract (so parallel branches never edit the same file)
- One event shape, written ONLY through `radar/emit.py` (`upsert_company`, `emit_signal`): company, signal_type, date (event date, ISO), source_url (public, human-openable), confidence (high|medium|low, rule in emit.py). Table schema: `radar/schema/001_core.sql`. New tables go in a NEW file `radar/schema/NNN_name.sql`, never in 001.
- Adapter = one module `radar/adapters/<name>.py` exposing `NAME = "<name>"` and `run(conn, thesis) -> dict` (counts: companies, signals, skipped) and a CLI `python3 -m radar.adapters.<name>`. Adapters are discovered by `radar/build.py`; nobody edits a shared list. Network adapters cache raw responses under `data/cache/<name>/` (gitignored), send 1 request per 2 s, and use User-Agent `OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)`.
- Route = one module `radar/routes/<name>.py` exposing `router` (APIRouter). `app.py` includes every module in `radar/routes/` automatically. Templates in `radar/templates/<name>*.html`, extending `base.html`.
- Thesis is read through `radar/thesis.py` (`load()`), never by opening YAML elsewhere.
- Declared datasets (read-only, with source_url columns intact) live in `data/declared/`. A dataset we fetch or export ourselves during the event goes in `data/fetched/` (gitignored if large) and the adapter records the fetch date.
- Hilma awards: read-only `sqlite3.connect("file:/opt/portfolio/tenderhub/data/awards_deep.sqlite?mode=ro", uri=True)`; the adapter copies the rows it uses (id, buyer, title, winner, value, date, link) into signals; the 1.15 GB file is never copied or committed.
- Empty is shown as empty: "not in public records" (hatched chip), never a placeholder that looks real. Nothing about a real startup without a source link. LLM text may summarise sourced facts only and must carry the same links.
- Honesty lines: no scraping behind logins; LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn shown only as "connector slot" (not connected). Companies only.

## Who works where
- Farm tasks: branch `task/<name>`, one task file each in /root/hack/queue; a dependent task starts by merging its predecessors' `task/*` branches into its own worktree.
- Amir: `amir/<task>`, PR to main, tasks tagged [amir] in TASKS.md. Cloud builder: `cloud/<task>`, tasks tagged [cloud]. The chief merges, deploys, screenshots, verifies.
- Only the chief edits README.md (above the cloud section), ARCHITECTURE.md, EVAL.md, DISCLOSURE.md, DEMO_SCRIPT.md, PILOT.md, DESIGN.md and CLAUDE.md. Builders propose doc changes in their RESULT/PR text.

## Files the judges read (JunctionX scores code quality, architecture, documentation)
README.md (30-second summary, hero screenshot, demo path, run in 3 commands), ARCHITECTURE.md (diagram + why),
EVAL.md (held-out set + one measured number), DISCLOSURE.md (brought vs built), PILOT.md (8-week plan for the partner).
Keep them true at all times; they are updated in the same commit as the feature.

## Design
Never unaided design: DESIGN.md names 3 references and one direction before the first screen is built.
Defaults over invention: shadcn/ui or Pico.css, system font stack, one accent colour, generous whitespace.
Real data on every screen. Mobile must not break: every task screenshots both viewports.
Slop tells to avoid: purple gradients, emoji in headings, four identical cards in a row, centered paragraphs,
"Welcome to" headlines, placeholder avatars, animated counters.

## Process safety
Never `pkill -f` or `killall` with a text pattern: the pattern can match your own Claude session and kill it mid-task
(it happened on 1.10.2026). Stop servers by port (`fuser -k 8150/tcp`), by the PID you started, or `systemctl stop hack-<name>`.
Commit every 20-30 minutes; an uncommitted worktree is lost work if the session dies.

## Parallel work
Overnight tasks go to /root/hack/queue as task files (see /root/hack/templates/task_template.md). Each runs in its own
worktree on branch task/<name>. Merge in the morning with `git merge --no-ff task/<name>` after reading its RESULT line
and screenshots. Never work directly on a branch another task owns.
