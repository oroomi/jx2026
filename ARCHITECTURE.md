# Architecture

One Python process serves server-rendered pages and a read-only JSON API over one SQLite file per thesis. Adapters fill that
file from public sources, and they write only through `radar/emit.py`. Rules that turn rows into answers are pure functions,
so the pages, the API and the tests call the same code. The module map with a command to run each piece alone is
[MODULES.md](MODULES.md); the stitcher's method is [METHOD.md](METHOD.md).

## One picture

```
 PUBLIC SOURCES (no login, cached)                 DECLARED RESEARCH (data/declared/, read only)
 PRH/YTJ register, tax registers, PRH notices,     cohort_portfolio_companies.csv (19 cohort + 9 portfolio),
 PRH wide intake, Hilma awards (read-only copy),   investors.csv, programmes_grants.csv, corporates_clients.csv,
 CORDIS, EU grants, TED, Business Finland export,  ecosystem/blue_economy_fi.sqlite
 BlueInvest, OpenAlex, Internet Archive, Estonia
            |                                                   |
            v                                                   v
 ADAPTERS   radar/adapters/*.py, one module per source, found by radar/build.py (pkgutil), run in PHASE order:
            0 declared lists -> 1 discoverers (insert companies) -> 2 enrichers (match existing companies)
            raw responses cached in data/cache/{adapter}/, 1 request per 2 s, one User-Agent naming the project
            |
            v
 ONE WRITER radar/emit.py: upsert_company(), emit_signal()
            one event shape = company, signal_type, event date, source_url, confidence (rule in the module docstring)
            |
            v
 STORES     data/radar_redstone_apelago_blue.sqlite | data/radar_health_tech_turku.sqlite | data/radar_baltic_blue.sqlite
            one SQLite file per thesis file; schema = radar/schema/*.sql applied in filename order
            |                                     ^
            |                                     | AI STITCHER radar/adapters/stitcher.py (run by hand, never by the build)
            |                                     | LLM proposes an event with URL and quote
            |                                     |  -> check 1, code: the fetched page names the company and prints the date
            |                                     |  -> check 2, code: fresh fetch, quote word for word, name near the quote,
            |                                     |     the quote states an event of that type
            |                                     |  -> Wayback first capture of the URL = public_since -> emit.py
            |                                     | every verdict is a row in stitch_log
            v
 READ SIDE  radar/store.py      feed, company, search, and the one-line "why" (store.explain)
 AND RULES  radar/fit.py        thesis fit with ordered reasons
            radar/frameworks.py readiness: TRL (Aalto), BRL (KTH), investment readiness, ocean impact category
            radar/ocean_impact.py Ocean Impact Assessment: area, evidence, scalability, rung 1-9, confidence (D27)
            radar/earliness.py  the backtest: first counted public signal against the cohort reference date
            radar/intake.py     wide intake: startup-shaped companies first, sector fit graded by evidence
            radar/matching.py   who comes next (investors, funding, partners) and what should happen next
            radar/matchmaker.py, matchmaker_orgs.py, matchtext.py   two-sided matchmaking: filters, then reasons in words (D28-D30)
            radar/memo.py       the fund memo: one decision from the team's decision table
            radar/lifeline.py   every dated record on one line from founding to today
            radar/sectors.py    the sector taxonomy: sub-sectors derived from evidence, each link with its basis and source (D45)
            radar/home_list.py, home_filter.py, home_orgs.py   the home rows with their criteria box, the 14-filter rail (cached per store file), and the Top matching tab (D35)
            radar/aava.py       the six-question conversation, built from the same rows; radar/aava_voice.py pre-renders it (build time)
            radar/aava_llm.py, aava_tools.py, aava_entities.py   OPTIONAL, behind the demo flag, on since 17:37 UTC: Aava on a reasoning model with read-only tools, names and links checked after generation (D61)
            |
            +-----------------------------------+-------------------------------------+
            v                                   v                                     v
 WEB        FastAPI + Jinja2 + htmx    JSON API radar/routes/api.py          DATASETTE deploy/datasette/
            radar/routes/*.py, all     GET only, no auth, errors as JSON     raw tables read-only on 127.0.0.1:8170,
            included by app.py         /api, /api/companies, /api/company,   person tables denied, not deployed
            radar/templates, static    /api/feed, /api/backtest, /api/match  to a public URL
            Ask Aava bar + /api/ask (live since 12:54 UTC, 17 Oct): a deterministic router over the same functions
            /home/list (filters in place, D32), /api/aava/chat (SSE, off) with the deterministic answer as its fallback

 config/thesis*.yaml, read only through radar/thesis.py, drives every layer above:
 sector words, industry codes, intake families, feed signal types, countries, matching lists and weights, impact areas and ladder,
 backtest population, memo table
```

## Components and why we chose them

| Component | What it does | Why this choice | Files |
|---|---|---|---|
| Thesis file | Holds everything sector-specific: sector label, industry codes, name keywords and stop words, feed signal types, Hilma and TED categories, countries, matching lists, backtest population, the memo's bands and decision table, the intake families, which sources the refresh re-reads | The partners judge scalability and transferability. A new sector, region or fund is a new YAML file, not a code change. Three files ship: blue economy Finland, blue economy Baltic Sea, health tech Turku | `config/thesis.yaml`, `config/thesis_baltic_blue.yaml`, `config/thesis_health_turku.yaml`, `radar/thesis.py` |
| Adapters | One module per source, each exposing `NAME` and `run(conn, thesis)` plus its own CLI | Discovered by module, so a farm task, a cloud session and Amir each add one file and never edit a shared list. Phases make the declared companies exist before enrichers try to match them. A failing adapter is reported and the others still run | `radar/adapters/*.py`, `radar/build.py`, `radar/adapters/_fetch.py` |
| `emit.py` | The only code that writes companies and signals | One event shape means the feed, the company page, the backtest and the API read one table. The confidence rule lives in one place. The stored date is the event date, never the fetch date, and a missing value stays NULL | `radar/emit.py`, `radar/schema/001_core.sql` |
| SQLite per thesis | One database file per thesis file | A sector swap is one environment variable (`RADAR_THESIS`) or one `?thesis=` parameter, and the two stores never mix. A file can be copied, checked with `PRAGMA quick_check` and swapped with `os.replace`, which is how the refresh works. No database server to run; a judge can open the file | `radar/db.py`, `radar/thesis.py` (`db_path`), `radar/schema/*.sql` |
| Numbered schema files | A new table goes in a new numbered file | Parallel branches add tables without touching each other's files | `radar/schema/005` to `062` |
| Read side and rules | Pure functions over a connection and the thesis | No web code inside, so each one imports and tests alone, and the pages and the API cannot disagree | `radar/store.py`, `fit.py`, `frameworks.py`, `ocean_impact.py`, `earliness.py`, `intake.py`, `matching.py`, `matchmaker.py`, `memo.py`, `lifeline.py`, `sectors.py`, `home_list.py` (the home page's list and tabs), `home_filter.py`, `home_orgs.py` |
| Fund memo | One decision per company from the team's decision table | The table is data in the thesis file, so the partners can change it without code. Rules only, no LLM, so it runs with no API key. A level with no public evidence is "unknown", never Low | `radar/memo.py`, `memo:` in `config/thesis.yaml` |
| Ocean Impact Assessment | One block per company: impact area in words, the records that name it (each with its link), scalability from records only, a rung 1 to 9 of evidence readiness, a confidence with its reason, and the record that would raise it | The partners asked that ocean impact not be "just another score", and the Navigator that names the framework is login-walled and defines KPIs, not levels (D1, D27). So the ladder says which kind of record must be on file for each rung and code applies it. Rungs 1 and 2 (sector implied only) carry no band and read "not yet evidenced": a gap is information, not a low score. It is attached to the memo and the API, and no decision-table band, verdict or other level changes (D21) | `radar/ocean_impact.py`, `impact_readiness:` in `config/thesis.yaml`, `/method#ocean-impact` |
| Home list, criteria box and filter rail | The rows of `/`, each with its criteria (impact, TRL, BRL, IRL, thesis fit, verdict) and a `facets` record; the rail's 14 filters read the facets (Sector with its Sub-sector, six criteria, six "Narrow down") and every control filters in place | The criteria are the memo's own cells, so a row cannot disagree with its company page, and the impact cell is the Ocean Impact ladder's (D46). Facets are computed once per cache warm, so a click filters cached rows and never opens the database. The filter state is the URL query (`radar.home_filter.parse_state`): every control asks `GET /home/list`, only the list section (`#hc-list`) and the count line are swapped with htmx, and the response's `HX-Replace-Url` rewrites the address with no history entry and no page load (D32); with scripts off every control is a link to the same URL, so every view is shareable. The number beside an option is how many rows would remain, so no click leads to a surprise empty list. The facet list, group labels, country names and the Top matching settings live in `config/home_filters.yaml`; a facet whose values the rows carry is offered with no code change. Every sector's list is built in one background thread at start, and a request waits at most 3 seconds for a list still being built (D26) | `radar/home_list.py`, `radar/home_filter.py`, `radar/home_config.py`, `radar/routes/home_list.py`, `radar/routes/home_rail.py`, `radar/static/filters.js`, `config/home_filters.yaml`, `tests/test_criteria_filters.py`, `tests/test_filters_inplace.py` |
| Matchmaking | For a startup, the counterparts that are its next step; for a counterpart, the startups that fit it; on the home page, "Top matching startups for {investor or accelerator}" | Filter first (kind by verdict path, declared geography, open and inside its stated windows), then rank by reasons in words. Counterpart demand is declared (its own text, stages, geography, window) plus revealed (the companies it has chosen); keywords are read on both sides through the thesis file's keyword groups plus raw shared word stems. A counterpart's own companies are listed apart as "Already connected" and never ranked (D38). The home tab prints the same ranking, its first 25, one organisation at a time in a background thread (D35, D63; the tab no longer intersects it with the home list). A startup's verdict path decides who it meets: a declared member (PORTFOLIO SUPPORT) meets programmes, funders and clusters, not accelerators (D65); an investor is shown the early pipeline and told in words when none is at due diligence (D63). No total score for a startup in the page or the API (A34); the API's internal ordering values are listed in the JSON API row below. Organisations only; the dataset's person table is never read (D28 to D30). Method, practices adopted and rejected: [docs/MATCHING.md](docs/MATCHING.md) | `radar/matchmaker.py`, `radar/matchmaker_orgs.py`, `radar/matchtext.py`, `radar/home_orgs.py`, `radar/routes/match.py`, `matching:` in `config/thesis.yaml`, `tests/test_matchmaker.py` |
| Aava | A spoken analyst of one company page, as six questions with one first-person answer each, and a one-question feed reader | The text is built by code from the rows the page shows (company, signals, memo, who comes next, the decision table); a missing fact is spoken as missing, and it says what a new record would change, never that evidence would lower a verdict (D49). Each segment carries a fingerprint of its text, so a recording is played only when it was rendered from exactly that text, and otherwise the browser's own voice speaks. Recordings for Viva Jets, Arctic Fry and the home "what is new" answer are made once at build time (ElevenLabs, voice Rachel) and committed, so the demo plays files with no network call and no key; because the fingerprint is exact, a change of wording silently retires a clip (the 15:04 UTC restart left 3 of the 16 matching; the company clips were re-rendered at 17:34 UTC and 12 of the 16 match at 17:40 UTC, the 4 feed clips do not). For a declared member the answers name the member rule (D65). Behind `?demo=1` | `radar/aava.py`, `radar/aava_voice.py`, `radar/routes/aava.py`, `radar/static/aava.js`, `radar/static/aava/audio/` |
| Sector taxonomy | Eleven sub-sectors of "Blue economy" plus "Not yet classified", derived from evidence: each link in `company_sector` has a basis (industry code, own text, corroborated name, declared research, procurement notice) and the public page it rests on | The owner asked for a sector filter, and CLAUDE.md says nothing about a company without a source link, so a sub-sector is never a label we chose: it is a link with a record behind it. The taxonomy is data in the thesis file's `taxonomy:` block and `radar/sectors.py` holds no sector word; the backfill is idempotent (`python3 -m radar.sectors backfill --db <store> --thesis <id>`, about 1 s) and additive (D45): no feed, memo, matching, readiness or decision rule reads it | `radar/sectors.py`, `radar/schema/062_sector.sql`, `taxonomy:` in `config/thesis.yaml`, `tests/test_sectors.py` |
| Aava reasoning mode (live behind the demo flag since 17:37 UTC) | Aava on Claude Sonnet 5.5 through the Messages API, as a streamed conversation in the Ask Aava bar and a company page's "Ask a follow-up" | A model that is asked to write company names can write one that does not exist, so the model reasons only through six read-only tools over code the site already runs (a seventh, `suggest_followups`, is out of the schema since D62; the follow-up buttons come from a closing line that code strips and caps) and the check after generation is code, not a request in the prompt: a link to a company stays only if a tool returned it in the same turn, an external link only if its address is in a tool result, a company-shaped name no tool returned is left unlinked and listed as unverified, and a Sources line is built from the addresses the tools cited. **Limit:** the code checks names, links and addresses, not that a figure or date matches the record it restates. Gated by the demo flag and limited to 8 turns per minute per client address and 400 per day (all visitors together); adaptive thinking at effort low, at most 3 steps and a hard ceiling of 4 model calls, only the final turn's text shown (D62); every failure falls back to the deterministic `radar/ask.py` answer; without a key, or with the file `data/AAVA_LLM_OFF` present (read at each request, no restart), the pages are served exactly as before. **On since 17:37 UTC on 17 Oct, behind the demo flag** (D61, D62): the file is absent (parked as `data/AAVA_LLM_OFF.parked`) and `/api/aava/status` answers `available: true`; five selftests took 4.7 to 7.0 s and cost $0.015 to $0.026 a turn | `radar/aava_llm.py`, `radar/aava_tools.py`, `radar/aava_entities.py`, `radar/routes/aava_chat.py`, `radar/static/aava_chat.js`, `config/aava_llm.yaml`, `config/aava_prompt.md`, `tests/test_aava_llm.py`, `tests/test_aava_chat.py` |
| Ask Aava bar (live, merge 5cd3293) | The home hero: a text and voice bar, answered by a deterministic intent router at `GET /api/ask?q=` | Intents are company, filter, feed, match, search and help, chosen by rules over the question's words; every word the rules react to is in the thesis file's `ask:` block, none in code. It calls the same functions as the pages and the Aava scripts, so there is no model and no network call; a filter answer is applied in place on the home page (D32). An example question is a chip only when its answer is not empty in that sector's store (D40). Voice input is the browser's Web Speech API, only with the demo flag. The header tabs move into a Menu and the footer. With the reasoning mode on it tries that first and falls back to this router | `radar/ask.py`, `radar/routes/ask.py`, `radar/static/askbar.js`, `ask:` in `config/thesis.yaml` |
| The stitcher | Finds dated events on the public web | An LLM is good at finding pages and bad at quoting and dating them faithfully. So the LLM only proposes; code fetches each page itself and keeps an event only when the page names the company and prints the date, then fetches it again and checks the quote, the name next to it and the event words. The Internet Archive's first capture of the URL is stored as `public_since`, the earliest day anyone could have read it, and that is the date the backtest uses. Its events are counted apart from the four backtest groups | `radar/adapters/stitcher.py`, `radar/schema/040_stitch_log.sql`, [METHOD.md](METHOD.md) |
| Web pages | FastAPI routes render Jinja2 templates; htmx swaps the feed rows when a filter is picked | Server-rendered honesty: what the page says is what the database returned, and every source link is in the HTML. No client build step and no JavaScript framework. htmx, the fonts and the country flags (11 flag-icons 7.2.3 SVGs, MIT) are vendored or self-hosted, so the pages themselves make no third-party request (the browser's own speech recognition, behind the demo flag, may use its vendor's service) | `app.py`, `radar/routes/*.py`, `radar/templates/`, `radar/static/` |
| Route discovery | `app.py` includes every module in `radar/routes/` that exposes `router` | Same reason as adapters; the catch-all `zz_notfound.py` sorts last | `app.py` |
| JSON API | Company search, company (with the Ocean Impact Assessment), feed, backtest and matchmaking (`/api/match/company/{key}`, `/api/match/org/{id}`, `/api/match/orgs`) as JSON | The same read side, for a partner's own tools; read-only, no auth, the thesis comes only from `?thesis=`. The match API has no total score, only an ordinal `rank`, a `weight` on each reason and the reasons with their links; `/api/company/{key}` also returns the declared research dataset's own match `score` and its readiness numbers (`oi_score`, `br_score`, `ir_score`, `oir_score`) | `radar/routes/api.py`, `radar/routes/match.py`, `tests/test_api.py`, `tests/test_matchmaker.py` |
| Refresh | Re-reads the fast live sources from the `/data` page | Works on a copy and swaps it in only after `quick_check`, so pages never see a half-written store; one run at a time with a cooldown; switched off unless `REFRESH_ENABLED=1` | `radar/refresh.py`, `radar/routes/data.py` |
| Datasette | Raw tables, read-only | Lets the team browse and export without the app. Tables that hold people are denied. It is not routed to a public URL | `deploy/datasette/` |
| Combined database | `python3 -m radar.combined --thesis <id>` copies the declared ecosystem file and appends the radar's `radar_*` tables and the view `v_entity_public_record` | One file answers "what public record does the radar hold for each dataset entity". The dataset's tables are copied unchanged and checked by digest, the store is only read, and the file is for the team only because it carries the dataset's `person` table | `radar/combined.py`, `data/combined/<thesis id>_combined.sqlite` (gitignored), `tests/test_combined.py` |

## Architecture decisions

**Transferability is a file, not a fork.** Every rule that decides what counts as the sector is read from the thesis file through
`radar/thesis.py`; no other module opens YAML. The proof runs live: `/?thesis=health_tech_turku` and `/?thesis=baltic_blue` serve a
different store and a different list from the same code, and `tests/test_thesis_swap.py` checks that a swap changes the rows and the
counts. Sector words still in code, named so nobody has to find them: `radar/frameworks.py` labels the "Ocean Impact Readiness (Ocean
Impact Navigator)" dimension because the partners' brief names that framework; `radar/adapters/eu_grants.py` keeps its programme list
(`BLUE_PROGRAMMES`: EMFAF, BlueInvest, Cluster 6) in code; the stitcher's thesis-evidence prompt describes the themes in blue-economy
words, and its list of capitalised words that are not personal names includes sea and ocean words.

**Companies only, enforced in four places.** At write: the ecosystem adapter does not import the dataset's people fields or free-text
summaries, and the wide intake does not store legal names shaped like a private person's name. At read: the feed hides personal-name
holding companies that have no signal beyond a register entry, and `/data` leaves out person-shaped names. In the stitcher: our queries are
built only from register facts and never use a personal name, the prompt forbids quoting a sentence that names a private person, person-shaped names are
redacted to `[name]` in stored quotes and, since commit 431df23, in the LLM's own logged queries, and LinkedIn, Facebook, Instagram,
X, Crunchbase, Dealroom, PitchBook, Tracxn, CB Insights and Nordic9 are refused in the prompt and dropped by code.
In Datasette: the `person` table and every table or view that holds a person's name, an email address or a LinkedIn link is denied. In Aava's reasoning mode (live behind the demo flag): the tools return companies and organisations only, and a company-shaped name that no tool returned is left unlinked and listed as unverified.

**Empty is empty.** A missing value stays NULL in the store and is drawn as a hatched chip ("not in public records", "no public
evidence"). A readiness level appears only when a record of its evidence class exists. A year-only date (Business Finland, some stitcher
events) is stored as 1 January with a `signal_meta` precision row, and the page labels it "year only".

**A gap is information, not a score.** The sponsor's guidance (A'Pelago, 17 Oct) is that missing information is not necessarily a reason to assign a low score, and that naming the gap, separating facts from assumptions and saying what to investigate next is itself venture intelligence. The architecture carries that in four places. A level with no record is "unknown" or "no public record" and never matches a decision-table cell that needs a band, so a missing level cannot produce REJECT / LOW FIT (A10, A12). The ocean-impact rungs 1 and 2 carry no band and read "not yet evidenced" (D27). Every ocean-impact level states a confidence with its reason and the record that would raise it. And an assumption is printed as one: "impact implied by the sector" whenever the memo's fallback applies (A13), and a declared-research reading of low confidence is "a lead and sets no rung" (A24).

**A ranking explains itself in words (A34).** Matchmaking lists the reasons that hold, each as a chip and a sentence with the record behind it, and lists what did not hold with its note; there is no total score for a startup on the page or in the API (the API's internal ordering values are listed in the JSON API row above). The weights in `matching: weights` only order the list. They are a stated hypothesis (D29): there is no ground truth for who should have met whom, so `docs/MATCHING.md` says so and PILOT.md asks the partners to rate 20 pairs.

**Deterministic where it speaks, and a model only behind a checked gate.** Aava's recorded answers and, without the demo flag, the Ask Aava bar's answers are built by code from the rows the pages show, with no model and no network call at run time. The recordings are made once at build time and played only when their text fingerprint matches the text on the page (`radar/aava.py` `text_sha`), which is also why a change of wording retires a clip until it is rendered again. The reasoning mode (D61) is the one place a model can speak, and it is built so that it cannot change a record: read-only tools only, no SQL from the model, names and links checked by code after generation, the demo flag, rate and daily limits, a graceful fallback to the deterministic answer on any failure, and a kill-switch file (`data/AAVA_LLM_OFF`) that turns it off without a restart. It is on behind the demo flag on the live site since 17:37 UTC (the public pages still serve the deterministic answers). What the code cannot check, and the documents say so, is that a figure or date inside a sentence matches the record it restates.

**One impact truth (D46).** The memo, the criteria box, the company page, Aava and the API read the impact band from one engine, the Ocean Impact ladder: a ladder band of Medium or High is the impact band, and a level with no band (rungs 1 to 2) or no level stays unknown, so the fallback applies; the Navigator-style category is context only. After the ladder was wired in, evidence could lower a verdict (a company with level 5 read WATCHLIST while sixteen declared members with no impact evidence read ACCELERATOR through the implied band; D65 later made those members read PORTFOLIO SUPPORT), so D53 lets "impact Medium on record" reach the fallback like the implied band: more evidence never lowers a verdict. A declared cohort or portfolio member reads High thesis fit by rule (D47), so most of the ACCELERATOR rows are the partners' own companies; EVAL.md says so.

**In the backtest, live, declared and stitched never mix.** The backtest counts live public records in one group and declared research events in a
separate group; stitcher events are counted on their own line and never move a company between groups.

## Data flow: where a number on the company page comes from

`GET /c/3166759-6` goes to `radar/routes/company.py`, which opens the store for the current thesis. `store.company` reads the company row
and its signals; `fit` gives the thesis-fit reasons, `frameworks.assess` the readiness levels with their rules, `matching` who comes next
and the next step, `lifeline` the dated line, and the template calls `memo.for_template` for the decision. The Jinja2 template prints
each value beside the `source_url` of the row it came from, and counts are computed from the same rows. For example, "First sales,
2020-10-05" is one `first_sales` signal written by `tax_registers.py`, with the PRH/YTJ link stored next to it.

## What keeps it honest

- One writer (`emit.py`) and one event shape: every signal has a public `source_url`, an event date and a confidence word from the
  printed rule.
- The feed rule, the backtest rule, the readiness rules and the decision table are printed on the pages (`/method`, `/backtest`, the
  company page), so a judge can check a row by hand.
- The stitcher keeps an LLM's proposal only after two code checks against the page it cites, and logs every drop with its reason.
- Partner organisations and capital sources are never shown as discovered startups (71 names on 17 Oct, listed on `/method`).
- Tests: `python3 -m pytest -q` (880 passed, 1 failed, 5 skipped on 17 Oct at 15:19 to 15:26 UTC, main 1b6c857, one latency test left out, before the j3 merges and not re-run in full since; the one failure is an intermittent timing test of the audio player) and CI on every push (`.github/workflows/ci.yml`). The deployed site:
  `/root/hack/bin/smoke.py https://jx.hankintaviikko.fi` loads 15 pages with no error (PASS 15/15 on 17 Oct at 15:19 UTC and at 17:49 UTC on build ac49cd8).
- Anything a model writes is checked by code for names and links before it is shown, and the model can be switched off without a restart (D61).
- Every number in the judged documents has a row in [docs/NUMBERS.md](docs/NUMBERS.md) with the page or query it was read from.

## What breaks first at scale

Request-time computation. Every page computes the feed rule and the intake tier from the whole store on each request; nothing is
precomputed except the caches below. Measured over the public URL on 17 Oct (15:18 UTC on build 1b6c857, 10 requests each, host load average about 1.8; re-measured at 17:50 UTC on build ac49cd8 with the same order of result), with 17,192 companies and 47,691 dated records on `/data` (they read 17,193 and 47,693 when the timings were taken, before 3 person-shaped names were hidden):
`/api/feed` answers in 0.17 to 0.27 s, `/api/backtest` in 0.30 to 0.70 s, and the home page in 0.63 to 1.13 s (median 0.78 s; an in-place filter click, `/home/list`, takes 0.08 to 0.17 s); at 17:50 UTC the same calls took 0.14 to 0.27 s, 0.27 to 0.60 s, 0.49 to 1.38 s (median 0.67 s) and 0.09 to 0.14 s, and an investor's counterpart view, `/api/match/org/redstone-blue`, 1.05 to 1.38 s. The wide intake alone put 16,384 companies into the live store (`/data`). Adding the Nordic registers
multiplies the store again. The fix is to compute the feed, the tiers and the backtest once per refresh into tables and serve those.

Cached exceptions. The home list (`radar/home_list.py`): it builds a fund memo, an ocean-impact assessment and the criteria for every row (about 0.1 s each, per its docstring), so it is kept in memory per thesis and per store file, and **every thesis in `config/` is warmed in one background thread when the app starts** (D26); a request that arrives while its list is still being built waits at most 3 seconds and then gets the plain feed with the line "The grouped view of this sector is still being prepared". Before that rule, `/?thesis=baltic_blue` took 70 s on the first load after a restart (D26); measured after a warm start, it answers in 0.45 to 0.87 s (10 requests, 15:18 UTC); right after the 13:16 UTC restart its first two requests took 3.6 s and 2.8 s (the 3 second wait plus the render) and the third 0.5 s. The matchmaking index (`radar/matchmaker.py`) builds once per store version, in about 2 seconds for the first match after a start (1.4 to 2.7 s in three runs on 17 Oct), and then a company's matches take milliseconds; the Top matching tab's ranking for one organisation is built the same way, once per organisation and store version in a background thread (about 1.5 s, A'Pelago's at start), and a request waits for it at most 3 seconds (D35); the counterpart view profiles the best 300 of a cheap first pass in full (an investor's view the best 1,000, because the early pipeline is a small share of them, D63) and says how many more passed and were not checked.

The second limit is freshness: the network adapters read at one request every 2 seconds, and the refresh button re-reads only the
register notices and recent registrations and is switched off on this deployment.

## What we would change with a week

- Extend the Norwegian and Danish register lookups (1 record each in the Finland and Nordics store; the Baltic store holds 1,290 Norwegian and 82 Estonian records) to full registers, add Sweden, and load the Estonian adapter into the Nordics store: 12 of the 19 cohort companies
  have no Finnish business ID, and 8 of those 12 are Danish, Swedish or Norwegian.
- Precompute the feed, the intake tiers and the backtest at refresh time, and run the existing copy, check and swap refresh on a
  schedule.
- Move the sector words still in code into the thesis file (the list is under "Transferability is a file").
- Replace the matchmaking weights, a stated hypothesis, with ones fitted to the partners' own ratings of 20 pairs (PILOT.md).
- Give the Ocean Impact ladder a measured top: a rung-9 source (an official or register outcome) is not connected today.
