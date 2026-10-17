# Modules: data, matching, API, web

The radar is four modules in one repository. They meet at one place: a SQLite store per thesis
(`data/radar_<thesis id>.sqlite`). Data writes it, matching reads it, the API and the web pages show what matching returns.
No file moves between modules: each folder below already exists, and this page is the map.

```
  public sources                                   declared research (data/declared/, read only)
  PRH/YTJ, tax registers, Hilma, TED, Business      cohort_portfolio_companies.csv, investors.csv,
  Finland export, CORDIS, EU grants, BlueInvest,    programmes_grants.csv, corporates_clients.csv,
  OpenAlex, Internet Archive, Estonia register      ecosystem/blue_economy_fi.sqlite
            |                                                   |
            v                                                   v
  (a) DATA   radar/adapters/<name>.py  --- only through radar/emit.py --->  data/radar_<thesis>.sqlite
             run by radar/build.py, schema radar/schema/*.sql               (one store per thesis file)
                                                                                    |
                                                    radar/store.py (the read side: feed, company, search)
                                                                                    |
            +-----------------------------------------------------------------------+
            v
  (c) MATCHING  radar/fit.py         does a company belong in the feed, and why
                radar/frameworks.py  readiness levels (TRL, BRL, investment, ocean impact) from evidence classes
                radar/earliness.py   would the radar have found the cohort before it entered (backtest)
                radar/matching.py    who comes next (investors, funding, partners) and what should happen next
            |
            +----------------------+-------------------------+--------------------------------+
            v                      v                         v                                v
  (d) WEB pages            (b) API JSON               database browser                 thesis switch
  radar/routes/*.py        radar/routes/api.py        Datasette, deploy/datasette/     config/thesis*.yaml
  radar/templates, static  /api/...                   raw tables, read-only            (no sector word in code)
```

## (a) DATA: sources into one store per thesis

| | |
|---|---|
| Folders | `radar/adapters/` (one file per source), `radar/build.py`, `radar/emit.py` (the only writer), `radar/db.py`, `radar/schema/*.sql`, `data/declared/` |
| Inputs | public sources over the network (cached under `data/cache/<adapter>/`, 1 request per 2 s); declared lists in `data/declared/`, including the ecosystem dataset `data/declared/ecosystem/blue_economy_fi.sqlite` |
| Outputs | `data/radar_<thesis id>.sqlite`: `companies`, `signals` (company, signal_type, event date, source_url, confidence), `signal_meta`, `signal_text`, `blueinvest_profiles`, `company_traction`, and the declared ecosystem tables `eco_entity`, `eco_match`, `eco_readiness`, `eco_meta` |
| Adapters | `declared`, `prh`, `prh_notices`, `tax_registers`, `hilma`, `ted`, `businessfinland`, `cordis`, `eu_grants`, `blueinvest`, `openalex`, `webarchive`, `estonia_register`, `ecosystem` |
| Owner | farm build tasks (`task/*`) and cloud sessions (`cloud/*`), one adapter each; the chief owns the contract files (`emit.py`, `db.py`, `001_core.sql`, `config/thesis*.yaml`) |

Rules that hold for every row: the event date is the date the event happened, every signal has a `source_url` a human can
open, confidence follows the rule printed in `radar/emit.py`, and missing stays NULL.

## (b) API: read-only JSON over the same stores

| | |
|---|---|
| Folder | `radar/routes/api.py` (picked up by `app.py` like every route module) |
| Inputs | the thesis store through `radar/store.py`, plus `radar/frameworks.py`, `radar/earliness.py`, `radar/matching.py` |
| Outputs | JSON only: GET, no auth, no CORS, no writes; errors are JSON too (400 unknown thesis or type, 404 unknown key or endpoint, 503 no store). The thesis comes only from `?thesis=` (an id from `config/thesis*.yaml`), never a cookie |
| Owner | task jx27 (cloud builder, branch `cloud/modules`) |

Each endpoint with one example (`BASE=http://127.0.0.1:8130` on the server, or the public URL once the chief deploys):

```
curl -s "$BASE/api"                                         # endpoint list and thesis ids
curl -s "$BASE/api/companies?q=viva"                        # search by name, key or Y-tunnus (no q: all, by name, limit/offset)
curl -s "$BASE/api/company/2962040-6"                       # facts, signals with sources, readiness levels, who comes next, next step
curl -s "$BASE/api/feed?thesis=redstone_apelago_blue&window=30"   # feed rows with strength, reasons and the why line
curl -s "$BASE/api/backtest?thesis=redstone_apelago_blue"   # earliness backtest per cohort company
```

On the 16 Oct snapshot (`RADAR_DATA_DIR=data/snapshot`, measured locally): `/api/company/2962040-6` 8 ms,
`/api/backtest` 8 ms, `/api/companies?q=oy` 14 ms, `/api/feed` 270 to 330 ms. `tests/test_api.py` holds each under 500 ms.

## (c) MATCHING: rules that turn rows into answers

| File | Answers | Entry point |
|---|---|---|
| `radar/fit.py` | thesis fit: does a company belong, with ordered reasons (industry code, name keyword, feed signals) | `fit(company, signals, thesis) -> [reason]`; the feed's one-line why is `store.explain` |
| `radar/frameworks.py` | readiness: TRL (Aalto), BRL (KTH), investment readiness over ten dimensions, ocean impact category; each level is a printed evidence-class rule, no evidence means no level | `assess(company, signals) -> levels`, `connections(signals)` |
| `radar/earliness.py` | the backtest: first counted public signal per cohort company against its entry date, blanks kept | `backtest(conn, thesis) -> rows and counts` |
| `radar/matching.py` | who comes next: investors, public funding, buyers, project partners and research institutes (plus the earlier funding and partners lists), ranked with the reason and a source link beside each; and what should happen next from a five-rule decision table | `who_comes_next(company_key, thesis, limit=5) -> {"investors", "funding", "partners", "public_funding", "buyers", "project_partners", "research_institutes"}` (`GROUPS`, `GROUP_RULES`, `RANK_RULE`), `next_step(company_key, thesis) -> {sentence, because, source_url, rule}` |

| | |
|---|---|
| Inputs | the thesis store (read only), the CSV lists the thesis names under `matching:` (`programmes`, `investors`, `corporates`), the ecosystem match rows imported into `eco_match` by the `ecosystem` adapter |
| Outputs | plain Python dicts; no web code in these files, so each imports and tests alone |
| Owner | `fit.py` farm jx07 and jx12, `frameworks.py` farm jx19, `earliness.py` farm jx15 and cloud backtest fix, `matching.py` farm jx23 (ecosystem join) |

## (d) WEB: the pages a judge sees

| | |
|---|---|
| Folders | `radar/routes/*.py` except `api.py` (`feed.py` `/`, `company.py` `/c/{key}`, `radar.py` `/radar`, `backtest.py` `/backtest`, `method.py` `/method`, `how.py` `/how`, `home.py` shared templates, `zz_notfound.py` last), `radar/templates/`, `radar/static/` (htmx vendored, fonts self-hosted) |
| Inputs | the same read side as the API: `radar/store.py` and the matching modules |
| Outputs | server-rendered HTML, both viewports |
| Owner | farm build tasks; the chief merges, deploys and screenshots |

`radar/refresh.py` + `radar/routes/data.py` + `radar/templates/data.html`: read-only database view and guarded refresh (copy, quick_check, os.replace; lock file, 10 min cooldown; steps from thesis key `refresh_adapters`). POST `/data/refresh` answers 403 unless the environment sets `REFRESH_ENABLED=1`.

## Everything in a database

| Store | File | Tables |
|---|---|---|
| Blue economy radar | `data/radar_redstone_apelago_blue.sqlite` | 16 Oct snapshot: 743 companies, 1,423 signals; on the server also the `eco_*` tables |
| Health tech Turku radar (thesis swap) | `data/radar_health_tech_turku.sqlite` | 16 Oct snapshot: 489 companies, 1,043 signals |
| Declared ecosystem dataset | `data/declared/ecosystem/blue_economy_fi.sqlite` | 215 entities, 2,931 scored matches, 73 readiness rows, 179 dated events |

Datasette serves all three read-only on 127.0.0.1:8170. People are not served: the `person` table (87 named individuals)
and every table or column that holds a person's name, an email or a LinkedIn link is denied; see `deploy/datasette/README.md`.

## Run each piece alone

```
# DATA: every adapter for the default thesis, one adapter, or the second thesis
python3 -m radar.build
python3 -m radar.build --adapters prh,hilma
python3 -m radar.adapters.cordis
python3 -m radar.build --thesis config/thesis_health_turku.yaml
python3 -m radar.store feed                       # the feed rule and counts as text
python3 -m radar.store company 2962040-6          # one company as text

# MATCHING: pure functions over a store
python3 -m radar.earliness                         # backtest as text
python3 -c "from radar import matching, thesis; import json; print(json.dumps(matching.who_comes_next('2962040-6', thesis.load()), indent=2, ensure_ascii=False))"
python3 -c "from radar import matching, thesis; print(matching.next_step('2962040-6', thesis.load()))"

# API and WEB: the same app (spare port for a local check; production is 8130)
python3 -m uvicorn app:app --host 127.0.0.1 --port 8164
curl -s http://127.0.0.1:8164/api/company/2962040-6

# Database browser: start command in deploy/datasette/README.md (port 8170)

# Without the live stores (a cloud session): prefix any command with RADAR_DATA_DIR=data/snapshot
RADAR_DATA_DIR=data/snapshot python3 -m uvicorn app:app --host 127.0.0.1 --port 8164

# Tests per module
python3 -m pytest -q tests/test_matching.py tests/test_fit.py tests/test_frameworks.py tests/test_earliness.py
python3 -m pytest -q tests/test_api.py
python3 -m pytest -q
```
