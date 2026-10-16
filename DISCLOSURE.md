# What we built this weekend versus pre-existing

## One-line statement
"All application code in this repository was written between 16 Oct 18:00 and 18 Oct 10:00 (Helsinki) with AI coding
tools. We brought our own build tooling, checklists, and the public datasets listed below, and we used the
third-party services listed below."

## Application code written at the event
Every file in this repository except those listed below. The first commit ("bell") is the empty skeleton,
timestamped at the opening. `git log --reverse` is the proof.

## Tooling brought (not product code)
| Item | What it is |
|---|---|
| bin/shot.py | Screenshots a URL at desktop and mobile size, captures console errors |
| bin/smoke.py | Loads a page and its same-origin links, fails on errors |
| bin/deploy.sh | Writes a systemd unit for an app directory and restarts it |
| templates/ | This file and other judged-doc skeletons |
| Claude Code skills | hack-plan, hack-verify, hack-design, hack-docs, hack-demo |
| CI config | .github/workflows/ci.yml |
| config/thesis.yaml, config/thesis_health_turku.yaml | Sector filters written at the event from the partners' public wording |
| Fonts: Newsreader and IBM Plex Sans via @fontsource npm packages (SIL OFL 1.1), htmx (BSD 2-clause) | Self-hosted libraries, fetched at build time |
| Python libraries | FastAPI, Uvicorn, Jinja2, httpx, PyYAML, openpyxl (open source) |

## Datasets declared with licences
Declared datasets are copied unchanged into `data/declared/` with their `source_url` columns intact. They were assembled from public pages on 16 Oct 2026, 15:25 to 16:15 UTC (before the 16:00 UTC bell for the cohort file, up to 15 minutes after it for the ecosystem lists), by a recon run outside this repo; the fetch method and every caveat are in `data/declared/RECON_DATA_SOURCES.md` and `data/declared/RECON_ECOSYSTEM_README.md`.

| Dataset | Rows / date range | URL | Licence | Snapshot date |
|---|---|---|---|---|
| data/declared/cohort_portfolio_companies.csv (19 Nordic Blue 2026 cohort + 9 Redstone Blue portfolio, with register, CORDIS, BlueInvest and website findings per company) | 28 rows | per-row columns ytj_source, customers_url, cordis_url, blueinvest_url; cohort list from apelago.fi, portfolio from redstone.vc/portfolio | public pages; PRH data CC BY 4.0 | 2026-10-16 |
| data/declared/investors.csv | 43 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| data/declared/corporates_clients.csv | 56 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| data/declared/programmes_grants.csv | 29 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| data/declared/startups_universe.csv | 47 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| PRH/YTJ open data API v3 (fetched live by radar/adapters/prh.py) | live | https://avoindata.prh.fi/opendata-ytj-api/v3 | CC BY 4.0, attribution to PRH, no PRH logos | fetch date stored per row |
| Hilma public procurement awards, read-only from /opt/portfolio/tenderhub/data/awards_deep.sqlite (our own archive of public notices, built before the event, 43,495 awards 2018-09-07 to 2026-10-16) | rows used are copied into signals | https://www.hankintailmoitukset.fi | public notices | 2026-10-16 |
| CORDIS Horizon Europe and H2020 bulk CSV (fetched by radar/adapters/cordis.py) | live | https://cordis.europa.eu/data/ | EU open data, CC BY 4.0 | fetch date stored |
| Business Finland funding decisions, manual Excel export from the public dashboard (data/declared/businessfinland.xlsx, when present) | export | https://tietopankki.businessfinland.fi | public dashboard export | export date in data/declared/README.md |
| EIC Accelerator call date and BlueInvest pages | 1 official date | EC topic JSON, blueinvest-community.converve.io | public | 2026-10-16 |

Not connected, shown only as "connector slot": LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn. Nothing from them is in this repo.

## Frameworks cited
Named by the official Redstone x A'Pelago brief; levels on the company page are our own evidence-class rules over public records, printed on /method.
| Framework | Use | Source | Access |
|---|---|---|---|
| Ocean Impact Navigator | Ocean Impact Readiness: category only, no score | https://www.1000oceanstartups.org/navigator | login-walled; cited by name and link, categories per A'Pelago themes |
| KTH Innovation Readiness Level, BRL 1-9 | Business Readiness Level labels and evidence-class mapping | https://kthinnovationreadinesslevel.com/wp-content/uploads/sites/9/2018/10/Business-readiness-Level.pdf | public PDF, text saved in data/declared/frameworks/ |
| Aalto University TRL 1-9 | Technology Readiness Level labels and evidence-class mapping | https://www.aalto.fi/en/services/technology-readiness-level-trl | public page, text saved in data/declared/frameworks/ |
| Investment Potential dimensions (ten) | Market, Product, Team, Business Model, Competition, Marketing & Distribution, Financials, Tech, Deal Dynamics, Impact | official brief | five have no source here and show "not in public records" |
| PRH registered notices API v3 | Dated equity events, board changes, capital losses and start-up notices | https://avoindata.prh.fi/opendata-registerednotices-api/v3/ | CC BY 4.0, no key; fetched by radar/adapters/prh_notices.py, cached in data/cache/prh_notices/ |

## Third-party services
| Service | Purpose | Account pre-existed? |
|---|---|---|
| Anthropic Claude (Claude Code + API) | Pair programmer and in-product LLM calls | yes |
| Cloudflare tunnel + VPS jx.hankintaviikko.fi | Public URL for the demo | yes |
| GitHub (oroomi/jx2026) | Source hosting | account yes, repo created at the bell |
| Claude Code cloud session (claude.ai) | Second builder | yes |

## Not used
No code from any earlier project. No private or scraped personal data. No named private individuals.
