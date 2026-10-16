# STATUS (Fri 16 Oct 2026, written 16:25 UTC / 19:25 Helsinki by the planner)

## What is queued on the farm (2 workers, 3 GB cap each, ARMED)
Four task files in /root/hack/queue, claimed by the 5-minute drain from 16:20 UTC. Branches task/<name>; the chief merges after each rc0 and a hack-verify pass. Check /root/hack/logs/drain.log and /root/hack/done.
| Task | Starts | What | Public check |
|---|---|---|---|
| jx01_skeleton | 16:20 UTC | FastAPI skeleton, Receipts tokens, self-hosted fonts, empty feed, deploy on 8130 | https://jx.hankintaviikko.fi/healthz |
| jx02_prh | 16:20 UTC | declared loader (28 cohort/portfolio companies) and PRH/YTJ adapter with discovery | `python3 -m radar.adapters.prh` counts |
| jx03_hilma | 16:30 UTC, when a worker frees | Hilma first public contracts of young companies, read-only | counts plus link check |
| jx04_businessfinland | 16:40 UTC, when a worker frees | Excel import that waits for data/declared/businessfinland.xlsx | skips cleanly without the file |
Next to queue once 1-3 are merged (task files not yet written, specs are rows 7-9 in TASKS.md): feed page, company page skeleton, thesis wiring. Saturday adapters and screens are rows 13-25.

## In the repo now
CLAUDE.md stack and code contract, DESIGN.md (Receipts), TASKS.md (31 tasks), config/thesis.yaml and a second health-tech thesis for the swap demo, radar/emit.py + schema (4 tests green), data/declared/ with the 28-company list and the four ecosystem CSVs (source_url intact), DEMO_SCRIPT opener and takeaway, DISCLOSURE datasets, README line 1 with "European Tech Renaissance".

## Amir: take this first
Task 6, `amir/stitcher-core`: the agentic stitcher. `python3 -m radar.stitch "<company>"` resolves a company (data/declared list, then PRH), fetches its public pages and returns facts that each carry a source URL and a verbatim snippet validated against the fetched text; no snippet, no fact. Check it against data/declared/cohort_portfolio_companies.csv: the 7 companies with `customers_listed` yes or partners must return those names, the other 21 must return "none found". That check is also your EVAL number. Branch amir/stitcher-core, files radar/stitch/**, radar/schema/020_facts.sql, tests/test_stitch.py. Second: task 18, explainable matching rules (amir/matching). Read CLAUDE.md "Code contract" first; write only through radar/emit.py.

## Cloud builder
Paste /root/hack/CLOUD_FABLE_PROMPT.md with the brief (TASKS.md header). First [cloud] tasks: 17 readiness rules, 19 next-step table, 20 earliness backtest. All three are pure functions with tests, so they need no network. Branches cloud/readiness, cloud/nextstep, cloud/earliness.

## Dayo: two actions that block the build
1. Business Finland export in a browser (task 5, about 30 minutes, before Saturday noon): open https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html, Customers tab, filter period 2024 to 2026 (or everything if the export allows), press the Excel export button, save as data/declared/businessfinland.xlsx in the repo, and write the export date and filter into data/declared/README.md. The adapter prints the headings it saw if they do not map.
2. Design confirmation (task 12): one word, "keep" or a change, after the first screenshots land from jx01 (docs/hero.png or shots/jx01/). Until then Receipts is final.
Also at the desk tonight (task 11): ask Matilda where she first hears of a startup and how long after founding, and for the pipeline entry dates of three cohort companies (task 21). Their yes becomes the backtest.

## Risks to watch
- The farm may be pushed back by the plan limit: dependent tasks use `after:` so they do not run early. Tasks branch from main HEAD, so a dependent task must start by merging its predecessors' task/* branches (the chief merges to main first).
- Business Finland has no machine path; without the export the BF signal source is empty and /method says "awaiting export".
- Espacenet and open-jobs may be BLOCKED on keys; both are written as feasibility-first with a connector-slot fallback.
- Cohort members are thin in public records (recon: 13 of 28 resolve in the register, 0 Hilma wins, 2 CORDIS). The backtest will show blanks; that is the honest result and it stays on the chart.
