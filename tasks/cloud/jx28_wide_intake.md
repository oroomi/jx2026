# jx28_wide_intake [cloud]: catch startups wide, prove blue later

Branch: `cloud/wide_intake`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first (it has the earliness audit, the tax-register data, the modules API and the TOL 2025 code fix).

## Why
The backtest says live public records alone show 1 of 19 Nordic Blue companies before cohort entry. Most of the 19 ARE in the registers we read (Kelluu: first sales 2018-03-09), but the feed rule only lets a company in when its industry code, line of business or legal name already sounds blue. Sireness is 72100 (general R&D) and never qualifies. The fix: take startup-shaped companies in wide, then grade thesis fit by evidence, and say plainly when there is none yet.

## What to build
1. Config, not code: add an `intake:` section to config/thesis.yaml, thesis_baltic_blue.yaml and thesis_health_turku.yaml: `company_forms` (limited companies and cooperatives only, never sole traders), `code_prefixes` (TOL 2025 families where tech startups register: 26, 27, 28, 29, 30, 62, 63, 71, 72, plus the thesis codes already listed), and `min_signals` (default 1 startup signal beyond the register entry: first_sales, first_hire, eu_project, eu_grant, research_output, bf_funding, startup_notice, equity_event, public_funding). No sector word in code; read it through radar/thesis.py.
2. Fetch: extend or add an adapter (prefer a NEW file radar/adapters/prh_intake.py) that pulls companies by registration date window and code prefix from the PRH/YTJ v3 API, 1 request per 2 s, cached under data/cache/prh_intake/. Two windows: the live feed window (last 90 days) and a backtest pass over the registration years of the 28 cohort companies (so each cohort company competes against every same-year, same-family company, not just itself). Hide legal names shaped like a person's name (radar/fit.py looks_like_person).
3. Feed: a third tier under Main and Weak: "New startups, no thesis evidence yet", closed by default, ranked by startup signals, each row saying which signal put it there. Main and Weak stay exactly as they are.
4. Company page Q01: when there is no thesis evidence, a hatched chip "Thesis fit: no public evidence yet" plus the startup signals that brought it in. When evidence appears (code, line of business, own text, corroborated keyword, or later the stitcher), the existing reasons show as today.
5. Backtest (radar/earliness.py and /backtest): per cohort company add two dates: "entered intake" (first date the company met the intake rule) and "first thesis evidence". Headline: how many of 19 entered intake before cohort entry, AND the precision line: for each, its rank among that year's intake companies (e.g. "Kelluu: 1 of 214 new 2018 tech-family companies, rank 37 by signals"). Never count a company as found early without its rank and the intake size next to it.

## Rules
- radar/schema/001_core.sql frozen; new tables in a new NNN file. Signals only through radar/emit.py. Companies only.
- Do not touch radar/routes/api.py, radar/adapters/stitcher.py (Amir's), app.py, or the chief's docs. Propose doc lines in your RESULT.
- Tests on data/snapshot plus new tests for the intake rule, the third tier, the Q01 chip and the backtest precision line. The health thesis must still render with no blue wording.
- Run the adapter against a COPY of the store with RADAR_DB set (CLI defaults to data/radar.sqlite) and report counts; the chief swaps data.

RESULT line must give: intake size (live window), how many of 19 entered intake before cohort entry, the median rank and intake size for those, pytest count.
