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
| Country flags: flag-icons 7.2.3 (MIT, Copyright (c) 2013 Panayiotis Lipiridis; https://github.com/lipis/flag-icons), 11 SVG files from its `flags/4x3/` set (bg, ch, de, dk, ee, es, fi, lv, no, pl, se), vendored in `radar/static/vendor/flags/` beside the licence text and a README | Self-hosted images, 16 x 12 px, shown beside the country names in the home list's Country filter (D34); the pages make no request to a flag CDN. Added 17 Oct |
| Python libraries | FastAPI, Uvicorn, Jinja2, httpx, PyYAML, openpyxl, and the Anthropic Python SDK (`anthropic`, used only by Aava's reasoning mode, which is live behind the demo flag) (open source) |

## Datasets declared with licences
Declared datasets are copied unchanged into `data/declared/` with their `source_url` columns intact. They were assembled from public pages on 16 Oct 2026, 15:25 to 16:15 UTC, inside the event window (it opened at 15:00 UTC, which is 18:00 in Helsinki), by a recon run outside this repo; the fetch method and every caveat are in `data/declared/RECON_DATA_SOURCES.md` and `data/declared/RECON_ECOSYSTEM_README.md`.

| Dataset | Rows / date range | URL | Licence | Snapshot date |
|---|---|---|---|---|
| data/declared/cohort_portfolio_companies.csv (19 Nordic Blue 2026 cohort + 9 Redstone Blue portfolio, with register, CORDIS, BlueInvest and website findings per company) | 28 rows | per-row columns ytj_source, customers_url, cordis_url, blueinvest_url; cohort list from apelago.fi, portfolio from redstone.vc/portfolio | public pages; PRH data CC BY 4.0 | 2026-10-16 |
| data/declared/investors.csv | 43 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| data/declared/corporates_clients.csv | 56 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| data/declared/programmes_grants.csv | 29 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| data/declared/startups_universe.csv | 47 rows | per-row source_url | public pages, facts only | 2026-10-16 |
| PRH/YTJ open data API v3 (fetched live by radar/adapters/prh.py) | live | https://avoindata.prh.fi/opendata-ytj-api/v3 | CC BY 4.0, attribution to PRH, no PRH logos | fetch date stored per row |
| Hilma public procurement awards, read-only from /opt/portfolio/tenderhub/data/awards_deep.sqlite (our own archive of public notices, built before the event, 43,502 awards 2018-09-07 to 2026-10-16, counted on 17 Oct) | rows used are copied into signals | https://www.hankintailmoitukset.fi | public notices | 2026-10-16 |
| CORDIS Horizon Europe and H2020 bulk CSV (fetched by radar/adapters/cordis.py) | live | https://cordis.europa.eu/data/ | EU open data, CC BY 4.0 | fetch date stored |
| EU Funding and Tenders reference data grantsTenders.json (fetched by radar/adapters/eu_grants.py into data/cache/eu/, never committed) | live, when reachable | https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json | EU open data | fetch date stored |
| TED (Tenders Electronic Daily) contract award notices, public search API (fetched by radar/adapters/ted.py into data/cache/ted/, never committed) | live; award notices since 2025-01-01 for the thesis CPV prefixes and countries, no key | https://api.ted.europa.eu/v3/notices/search | EU open data, re-use of TED notices under the Commission's reuse policy | fetch date stored per signal |
| Estonian e-Business Register open data, Basic data CSV (fetched by radar/adapters/estonia_register.py into data/cache/estonia_register/, never committed) | live, refreshed daily by the register | https://avaandmed.ariregister.rik.ee/en/downloading-open-data | CC BY 4.0, attribution to the Estonian Centre of Registers and Information Systems (RIK) | file date stored in the cache |
| Business Finland funding decisions, manual Excel export from the public dashboard (data/declared/businessfinland.xlsx, when present) | export | https://tietopankki.businessfinland.fi | public dashboard export | export date in data/declared/README.md |
| EIC Accelerator call date and BlueInvest pages | 1 official date | EC topic JSON, blueinvest-community.converve.io | public | 2026-10-16 |
| PRH/YTJ registeredEntries: VAT liability, prepayment and employer register dates (radar/adapters/tax_registers.py, same API as above, cached) | live | https://avoindata.prh.fi/opendata-ytj-api/v3 and https://tietopalvelu.ytj.fi | CC BY 4.0, attribution to PRH | fetch date stored per row |
| OpenAlex works by affiliation string (radar/adapters/openalex.py, cohort, portfolio and ecosystem companies only) | live | https://api.openalex.org/works | CC0 | fetch date stored per row |
| Internet Archive Wayback CDX captures of company websites (radar/adapters/webarchive.py) | live | https://web.archive.org/cdx/search/cdx | public archive index, links to captures only | fetch date stored per row |

Not connected, shown only as "connector slot": LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn. Nothing was scraped or bought from them. A few facts in the declared research (`data/declared/ecosystem/blue_economy_fi.sqlite`, table `source`) cite 19 public pages of Tracxn (8), PitchBook (6), Dealroom (3) and Crunchbase (2) as their source.

## Frameworks cited
Named by the official Redstone x A'Pelago brief; levels on the company page are our own evidence-class rules over public records, printed on /method.
| Framework | Use | Source | Access |
|---|---|---|---|
| Ocean Impact Navigator | The framework the brief names for ocean impact; we use its impact areas in words (per A'Pelago themes). It publishes no levels, so the nine rungs of our Ocean Impact Assessment are our own evidence ladder, not a Navigator level (D27) | https://www.1000oceanstartups.org/navigator | login-walled; cited by name and link |
| KTH Innovation Readiness Level, BRL 1-9 | Business Readiness Level labels and evidence-class mapping | https://kthinnovationreadinesslevel.com/wp-content/uploads/sites/9/2018/10/Business-readiness-Level.pdf | public PDF, text saved in data/declared/frameworks/ |
| Aalto University TRL 1-9 | Technology Readiness Level labels and evidence-class mapping | https://www.aalto.fi/en/services/technology-readiness-level-trl | public page, text saved in data/declared/frameworks/ |
| Investment Potential dimensions (ten) | Market, Product, Team, Business Model, Competition, Marketing & Distribution, Financials, Tech, Deal Dynamics, Impact | official brief | five have no source here and show "not in public records" |
| PRH registered notices API v3 | Dated equity events, board changes, capital losses and start-up notices | https://avoindata.prh.fi/opendata-registerednotices-api/v3/ | CC BY 4.0, no key; fetched by radar/adapters/prh_notices.py, cached in data/cache/prh_notices/ |

## Partner guidance received during the event (no data, rules only)

| From | Date | What it said | Where it shaped the product |
|---|---|---|---|
| A'Pelago | 17 Oct 2026 | "missing information is not necessarily a reason to exclude a company or assign it a low score. Identifying information gaps, distinguishing facts from assumptions, and determining what to investigate next can itself be valuable venture intelligence." | Rungs 1 and 2 of the Ocean Impact ladder read "not yet evidenced", never Low (D27); the sentence is quoted once in README.md and once in DEMO_SCRIPT.md |
| The data partner's review of the live site | 17 Oct 2026 | A ranking must explain itself in words ("Climate focus, Seed stage, Baltic region, Ticket size match" good, "AI score = 92" bad); ocean impact may feel secondary and should not become "just another score": show impact area, evidence, scalability, readiness x of 9 and confidence | A34 (matchmaking shows reasons with records and no score) and D27 (the Ocean Impact Assessment) |

## Matchmaking method: sources read (ideas only, no code, text or data copied)

Read on 17 Oct 2026 for `radar/matchmaker.py`; what we took is in [docs/MATCHING.md](docs/MATCHING.md). Each row is a public web page; nothing from them is stored in the repo.

| Source | URL | What we took | Licence or access |
|---|---|---|---|
| Google, Recommendation systems overview | https://developers.google.com/machine-learning/recommendation/overview/types | candidate generation, then scoring, then constraints: filter then rank | public documentation, read only |
| Metal, Recommended process (investor identification) | https://docs.metal.so/content/high-resolution-identification/recommended-process.md | elimination criteria before ranking; past investments in similar companies as a starting point | public documentation, read only |
| b2match, Event networking | https://www.b2match.com/news/give-your-attendees-the-networking-they-actually-want | mutual interest first; each match labelled with why it exists | vendor page, read only |
| Reciprocal recommender systems: analysis of state-of-art literature | https://arxiv.org/abs/2007.16120 | both sides' preferences must be taken into account | arXiv abstract, read only |
| Xu, Zhang, Lv, Mariani, Recommending investors for new startups | https://arxiv.org/abs/1912.02962 | investors' domain preference is revealed by past deals and helps for startups with no investors yet | arXiv abstract, read only |
| InEvent, AI matchmaking | https://inevent.com/products/ai/matchmaking.php | configurable weights and cut-offs; matchmaking "cannot be a black box" | vendor page, read only |
| Converve, B2B matchmaking software | https://www.converve.com/event-platform/b2b-event-matchmaking/ | rules the organiser can read, not an AI black box | vendor page, read only |
| Tintarev and Masthoff, Explaining recommendations | https://abdn.elsevierpure.com/en/publications/explaining-recommendations-design-and-evaluation/ | explanations give seven distinct benefits | publisher abstract, read only |
| freeCodeCamp, Cold start problem in recommender systems | https://www.freecodecamp.org/news/cold-start-problem-in-recommender-systems/ | content features carry a match when there is no history | public article, read only |
| Stanford NLP group, Introduction to Information Retrieval, inverse document frequency | https://nlp.stanford.edu/IR-book/html/htmledition/inverse-document-frequency-1.html | rare terms weigh more than common ones | public book chapter, read only |

The matchmaking reads only data already declared above (the declared lists and the ecosystem dataset, organisations only), our store, and `config/thesis.yaml`; it adds no dataset and calls no external service or paid API.

## Third-party services
| Service | Purpose | Account pre-existed? |
|---|---|---|
| ElevenLabs | text-to-speech. (1) The Aava narration, rendered once at build time into MP3 files (voice Rachel, model `eleven_multilingual_v2`, Starter plan): 16 clips, 4,449 characters, 12 for Viva Jets Oy and Arctic Fry Oy (1,833 and 2,065 characters, re-rendered on 17 Oct at 17:34 UTC for the portfolio-support wording) and 4 for the home page's "what is new" answer (551 characters, not re-rendered); the recorded clips need no call and no key at run time, and 12 of the 16 match the live text at 17:40 UTC (the 4 feed clips play the browser voice until re-rendered). (2) `POST /api/aava/tts` streams a live voice at run time (Jessica, model `eleven_v3`, picked on 17 Oct at 20:30 UTC; the recorded clips above are Rachel) for the reasoning Aava's spoken answers when `ELEVENLABS_API_KEY` is set in the service environment (it is: `/api/aava/status` reports `tts: true`); it needs the demo-flag header and is capped at 8,000 characters per day, and the page calls it only when the reasoning mode is available, which it is since 17:37 UTC on 17 Oct (a model answer in the bar is therefore spoken through this call, not from a recording) | yes, the owner's existing account, opened before the event |
| Anthropic Claude (Claude Code + API) | Pair programmer and in-product LLM calls (the stitcher's proposals and the batch-written company summaries; code checks both) | yes |
| Anthropic API, Aava's reasoning mode (`radar/aava_llm.py`, D61) | Claude Sonnet 5.5 via the Messages API, read-only tools over this site's own records, company names code-checked after generation, deterministic fallback, demo-flag gated, rate-limited; prepaid promotional credit. Built and merged on 17 Oct and **live since 17:37 UTC on 17 Oct, behind a client header that the page sends only with the demo flag (`?demo=1`)**: `GET /api/aava/status` answers `available: true`, the kill-switch file `data/AAVA_LLM_OFF` is absent (parked as `data/AAVA_LLM_OFF.parked`), and the server refuses the chat without the header `X-Aava-Demo: 1`. That is a switch, not a lock, because anyone can send the header; what limits use is 8 turns a minute per client address and 400 turns a day, all visitors together. Per model turn at most 4 calls go to the Anthropic API (3 steps and one forced answer, D62); five measured turns took 4.7 to 7.0 s and cost $0.015 to $0.026 each, paid from the same prepaid credit. The model receives the visitor's question, the visitor's current view (the page's filters) and the site's own records through read-only tools (no SQL, no writes, no network); code checks the names and links in its answer, not every figure. The key reaches the app only through the service's environment, never the repository | yes, the same Anthropic row as above |
| Cloudflare tunnel + VPS jx.hankintaviikko.fi | Public URL for the demo | yes |
| GitHub (oroomi/jx2026) | Source hosting | account yes, repo created at the bell |
| Claude Code cloud session (claude.ai) | Second builder | yes |
| Browser SpeechSynthesis API (the visitor's own device voices; Aava, radar/static/aava.js, and the Ask Aava bar's spoken answers) | Reads the page's records aloud when no recording matches the text; no audio or text is sent to any service by us | built into the browser |
| Browser Web Speech API, speech recognition (`SpeechRecognition` or `webkitSpeechRecognition`; the Ask Aava bar's voice input, live since 17 Oct 12:54 UTC, behind `?demo=1`; `radar/static/askbar.js`) | Turns the visitor's spoken question into text in the browser (language en-US). Some browsers do this on their vendor's speech service; this site receives only the text of the question, and the overlay prints that sentence. We call no speech service, keep no audio and add no library | built into the browser |
| Browser microphone (`getUserMedia`) and Web Audio API (the same voice overlay) | The microphone level moves the orb animation. Nothing is recorded, stored or sent by us; the visitor is asked for permission by the browser | built into the browser |

Narration audio pre-rendered with ElevenLabs text-to-speech from the page's own segment text; no runtime calls, no key in the app (build-time tool `radar/aava_voice.py`, voice id `21m00Tcm4TlvDq8ikWAM` (Rachel), MP3 files in `radar/static/aava/audio/<company key>/`, one manifest per page keyed by a fingerprint of the text). The browser voice stays as the fallback. The home page's "what is new" answer (4 clips, 551 characters, `radar/static/aava/audio/feed/`) was re-rendered in Rachel's voice on 17 Oct (commit de11098) when the feed reader changed; the five earlier clips in another voice were removed. **Staleness:** a clip plays only while the fingerprint of its text equals the fingerprint of the text on the page, and the merges that went live at the 15:04 UTC restart changed the answers' wording (verdicts, impact wording, KalanPojat Oy in the feed), so at 15:40 UTC the clips for Viva Jets questions 1, 4 and 5 match (3 of 6), none of Arctic Fry's 6 and none of the feed's 4. The browser voice reads the rest. To render again: `python3 -m radar.aava_voice render --keys 2962040-6,3166759-6 --feed` with `ELEVENLABS_API_KEY` set.

## Not used
No code from any earlier project. No private or scraped personal data. No named private individuals.

## Chief notes after the night-two verification (16 Oct 2026, 21:30Z)
- data/declared/businessfinland.xlsx (2.4 MB) is tracked on main on purpose, against the earlier "keep it untracked" rule: it is the public Business Finland funding export as downloaded by the team on 16 Oct, and a judge must be able to rebuild the bf_funding signals from the repo alone. It is declared data, not fetched data.
- BlueInvest public pipeline profiles stored: 21 in total, 18 with country Finland (earlier notes said 19 Finnish; the stored count is the truth).
- Feed precision defect D-N1 (own-text reasons from our own annotations, short keywords hitting common words) was fixed by task jx20b and is merged (PROJECT_RULES.md, D2).

## Feed precision (jx20b)

Built during the event: whole-word keyword matching (`radar/fit.py`), a stop list and a non-person word list in the thesis files, the `signal_text` table (`radar/schema/011_signal_text.sql`) that keeps the CORDIS project title, objective and keywords apart from our own `detail` annotation, and a rule that hides legal names shaped like a private person plus Holding, Invest, Capital, Consulting or Tmi when the company has no signal beyond a register entry. No new external data or library.

## Declared ecosystem dataset (jx23)

`data/declared/ecosystem/blue_economy_fi.sqlite` (with SCHEMA.md and API_SOURCES.md) is a research dataset built on this server on 16 Oct 2026, during the event, with a source URL per record: 215 entities (95 companies, 120 capital sources and buyers), 2,931 scored company-to-target pairs each with a reason string, readiness evidence for 73 companies, dated events and job ads. It is declared data, read-only; `radar/adapters/ecosystem.py` imports it (tables in `radar/schema/006_ecosystem.sql`). Its own confidence words are shown as given and low-confidence rows are leads, not facts. Not imported: the dataset's free-text summaries and key-people fields (they name private individuals), links to personal profiles, and rows without a date (they stay evidence text, never signals). The dataset never sets a readiness level; it is printed beside the register rule's level.

## Filters in place, sector taxonomy and country flags (feat/filters_inplace, feat/taxonomy; D32 to D35, D45)

Built during the event, on 17 Oct. No new external data and no new service: the sub-sector links in `company_sector` are derived by `radar/sectors.py` from records already in the store (industry code, the registered line of business, a checked stitcher quote, a corroborated name word, the declared ecosystem research, a procurement notice title), each with the public page it rests on (1,059 links on 979 of 17,195 companies in the store; `/data` shows 17,192, as 3 person-shaped names are hidden there). The taxonomy, 11 sub-sectors under "Blue economy" and "Not yet classified", was approved by the owner and sits in `config/thesis.yaml`; it is not taken from any outside classification. The country names are the English names of the Unicode CLDR table for the 249 ISO 3166-1 codes, kept in `config/home_filters.yaml`; the flags are the vendored flag-icons files listed above.

## Aava's reasoning mode (feat/aava_ai, D61, D62)

Built during the event, merged on 17 Oct, **live behind the demo flag since 17:37 UTC on 17 Oct** (the Anthropic row in the service table above is live: it is a call from the public site, for requests that carry the demo header, which the page sends when `?demo=1` is on). It adds the Anthropic SDK (`anthropic`, `requirements.txt`) and, per model turn, up to four outbound calls (three steps, plus one forced answer if the model still asks for a data tool in the last step, D62) to the Anthropic Messages API (Claude Sonnet 5.5, `claude-sonnet-5-5`, adaptive thinking at effort low), and, for spoken answers, `POST /api/aava/tts` to ElevenLabs (see the service rows above). Everything the model may know comes through read-only tools over code the site already runs (`radar/aava_tools.py`; six in the schema); it adds no dataset. After generation, code checks the company names, links and addresses in the answer (`radar/aava_entities.py`): a link to a company stays only if a tool returned that company in the same turn, an external link only if its address is in a tool result, a company-shaped name no tool returned is left unlinked and listed as unverified, and every answer ends with a Sources line built from the addresses the tools cited. **What is not checked:** that a figure or date inside a sentence equals the record it restates; the prompt (`config/aava_prompt.md`), the tools' plain-word results and the Sources line are the guard. Gating: the demo header (`X-Aava-Demo: 1`, sent by the page when `?demo=1` is on; a switch, not a lock), 500 characters of input, 12 messages of history, 8 turns per minute per client address and 400 turns per day in memory; any failure ends in a graceful message and then the deterministic answer. The kill switch is the file `data/AAVA_LLM_OFF`, read at each request without a restart; it is absent on the live site, and moving it back (it is parked as `data/AAVA_LLM_OFF.parked`) switches the mode off. Measured: five real turns took 4.7 to 7.0 s and cost $0.015 to $0.026 (EVAL.md, "Aava's reasoning mode"); answer quality across a question set is not scored.
