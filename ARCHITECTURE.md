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
            radar/earliness.py  the backtest: first counted public signal against the cohort reference date
            radar/intake.py     wide intake: startup-shaped companies first, sector fit graded by evidence
            radar/matching.py   who comes next (investors, funding, partners) and what should happen next
            radar/memo.py       the fund memo: one decision from the team's decision table
            radar/lifeline.py   every dated record on one line from founding to today
            |
            +-----------------------------------+-------------------------------------+
            v                                   v                                     v
 WEB        FastAPI + Jinja2 + htmx    JSON API radar/routes/api.py          DATASETTE deploy/datasette/
            radar/routes/*.py, all     GET only, no auth, errors as JSON     raw tables read-only on 127.0.0.1:8170,
            included by app.py         /api, /api/companies, /api/company,   person tables denied, not deployed
            radar/templates, static    /api/feed, /api/backtest              to a public URL

 config/thesis*.yaml, read only through radar/thesis.py, drives every layer above:
 sector words, industry codes, intake families, feed signal types, countries, matching lists, backtest population, memo table
```

## Components and why we chose them

| Component | What it does | Why this choice | Files |
|---|---|---|---|
| Thesis file | Holds everything sector-specific: sector label, industry codes, name keywords and stop words, feed signal types, Hilma and TED categories, countries, matching lists, backtest population, the memo's bands and decision table, the intake families, which sources the refresh re-reads | The partners judge scalability and transferability. A new sector, region or fund is a new YAML file, not a code change. Three files ship: blue economy Finland, blue economy Baltic Sea, health tech Turku | `config/thesis.yaml`, `config/thesis_baltic_blue.yaml`, `config/thesis_health_turku.yaml`, `radar/thesis.py` |
| Adapters | One module per source, each exposing `NAME` and `run(conn, thesis)` plus its own CLI | Discovered by module, so a farm task, a cloud session and Amir each add one file and never edit a shared list. Phases make the declared companies exist before enrichers try to match them. A failing adapter is reported and the others still run | `radar/adapters/*.py`, `radar/build.py`, `radar/adapters/_fetch.py` |
| `emit.py` | The only code that writes companies and signals | One event shape means the feed, the company page, the backtest and the API read one table. The confidence rule lives in one place. The stored date is the event date, never the fetch date, and a missing value stays NULL | `radar/emit.py`, `radar/schema/001_core.sql` |
| SQLite per thesis | One database file per thesis file | A sector swap is one environment variable (`RADAR_THESIS`) or one `?thesis=` parameter, and the two stores never mix. A file can be copied, checked with `PRAGMA quick_check` and swapped with `os.replace`, which is how the refresh works. No database server to run; a judge can open the file | `radar/db.py`, `radar/thesis.py` (`db_path`), `radar/schema/*.sql` |
| Numbered schema files | A new table goes in a new numbered file | Parallel branches add tables without touching each other's files | `radar/schema/005` to `040` |
| Read side and rules | Pure functions over a connection and the thesis | No web code inside, so each one imports and tests alone, and the pages and the API cannot disagree | `radar/store.py`, `fit.py`, `frameworks.py`, `earliness.py`, `intake.py`, `matching.py`, `memo.py`, `lifeline.py` |
| Fund memo | One decision per company from the team's decision table | The table is data in the thesis file, so the partners can change it without code. Rules only, no LLM, so it runs with no API key. A level with no public evidence is "unknown", never Low | `radar/memo.py`, `memo:` in `config/thesis.yaml` |
| The stitcher | Finds dated events on the public web | An LLM is good at finding pages and bad at quoting and dating them faithfully. So the LLM only proposes; code fetches each page itself and keeps an event only when the page names the company and prints the date, then fetches it again and checks the quote, the name next to it and the event words. The Internet Archive's first capture of the URL is stored as `public_since`, the earliest day anyone could have read it, and that is the date the backtest uses. Its events are counted apart from the four backtest groups | `radar/adapters/stitcher.py`, `radar/schema/040_stitch_log.sql`, [METHOD.md](METHOD.md) |
| Web pages | FastAPI routes render Jinja2 templates; htmx swaps the feed rows when a filter is picked | Server-rendered honesty: what the page says is what the database returned, and every source link is in the HTML. No client build step and no JavaScript framework. htmx is vendored and the fonts are self-hosted, so a page makes no third-party request | `app.py`, `radar/routes/*.py`, `radar/templates/`, `radar/static/` |
| Route discovery | `app.py` includes every module in `radar/routes/` that exposes `router` | Same reason as adapters; the catch-all `zz_notfound.py` sorts last | `app.py` |
| JSON API | Company search, company, feed and backtest as JSON | The same read side, for a partner's own tools; read-only, no auth, the thesis comes only from `?thesis=` | `radar/routes/api.py`, `tests/test_api.py` |
| Refresh | Re-reads the fast live sources from the `/data` page | Works on a copy and swaps it in only after `quick_check`, so pages never see a half-written store; one run at a time with a cooldown; switched off unless `REFRESH_ENABLED=1` | `radar/refresh.py`, `radar/routes/data.py` |
| Datasette | Raw tables, read-only | Lets the team browse and export without the app. Tables that hold people are denied. It is not routed to a public URL | `deploy/datasette/` |

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
In Datasette: the `person` table and every table or view that holds a person's name, an email address or a LinkedIn link is denied.

**Empty is empty.** A missing value stays NULL in the store and is drawn as a hatched chip ("not in public records", "no public
evidence"). A readiness level appears only when a record of its evidence class exists. A year-only date (Business Finland, some stitcher
events) is stored as 1 January with a `signal_meta` precision row, and the page labels it "year only".

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
- Tests: `python3 -m pytest -q` (397 passed on 17 Oct, 29 s) and CI on every push (`.github/workflows/ci.yml`). The deployed site:
  `/root/hack/bin/smoke.py https://jx.hankintaviikko.fi` loads 13 pages with no error (PASS 13/13 on 17 Oct).

## What breaks first at scale

Request-time computation. Every page computes the feed rule and the intake tier from the whole store on each request; nothing is
precomputed. Today `/api/feed` answers in 0.34 to 0.39 s over the public URL with 17,195 companies in the store. The wide intake run on a store copy added 15,584 companies and 41,220 signals, and before it was
rewritten into one pass the intake tier took 10 s per request on 4,600 intake companies (now under 1 s). Adding the Nordic registers
multiplies the store again. The fix is to compute the feed, the tiers and the backtest once per refresh into tables and serve those.

The second limit is freshness: the network adapters read at one request every 2 seconds, and the refresh button re-reads only the
register notices and recent registrations and is switched off on this deployment.

## What we would change with a week

- Add the Swedish, Norwegian and Danish registers and load the Estonian adapter into the live store: 12 of the 19 cohort companies
  have no Finnish business ID, and 8 of those 12 are Danish, Swedish or Norwegian.
- Precompute the feed, the intake tiers and the backtest at refresh time, and run the existing copy, check and swap refresh on a
  schedule.
- Count a keyword in a legal name as corroborated only when the second record comes from a different source family (0 of the 36
  main-list companies carry the corroborated-name reason today), and move the sector words still in
  code into the thesis file.
