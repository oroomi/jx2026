# Ocean Opportunity Radar: decision-ready venture intelligence for the European Tech Renaissance (Redstone x A'Pelago)

Every rule and dated decision behind these numbers: [PROJECT_RULES.md](PROJECT_RULES.md) (assumptions, decisions, taxonomy, formats; it folds in ASSUMPTIONS.md with the same ids). Every number in the judged documents, with the page or query it was read from: [docs/NUMBERS.md](docs/NUMBERS.md).

Ocean Opportunity Radar finds young blue-economy companies in public records before they reach a fund's or an accelerator's
pipeline, and answers the partners' four questions about each one with a source link under every fact.
Built at JunctionX Turku 2026 for the Redstone x A'Pelago challenge by team Old Hackers.

**Live:** <https://jx.hankintaviikko.fi>

![The home page: the Ask Aava bar with its example questions, the filter rail on the left ("What the judges score"), the tabs, and on each row the criteria box with impact, TRL, BRL, IRL, thesis fit and verdict](docs/hero_home.png)

*Screenshot committed at 13:20 UTC on 17 Oct (e46a899). Since 17:37 UTC the live rows also print their first reason in words under the name, the verdicts read Watchlist, Portfolio support and Partner introduction, and the list is sorted by a stated rule (D65, D70); the numbers in the text below are the live ones.*

## 30 seconds

**The problem, in the partners' words.** "Find promising startups as early as possible" and turn "fragmented startup and
ecosystem data into decision-ready venture intelligence".

**Who it is for.** The investment team at Redstone Blue (pre-seed and seed) and the programme team at A'Pelago, who screen
applicants for the Nordic Blue accelerator.

**What it does.** It reads Finnish and EU public records (trade register, tax registers, register notices, public contracts,
EU projects, Business Finland funding), keeps one dated event per record with its link, and puts every company through the
partners' four questions: 01 Who is most promising, 02 How ready are they, 03 Who comes next, 04 What should happen next. Five features carry it, named the way the judges score:

| Feature | Judge criterion | What it is, and where to see it |
|---|---|---|
| **Ocean Impact Assessment** on every blue company page | Creativity, precision | The impact area in words, the records that name it (each with a link), scalability from records only, an evidence-readiness ladder of 9 rungs and a confidence with its reason. A sector-implied rung reads "not yet evidenced", never Low. <https://jx.hankintaviikko.fi/c/2962040-6> |
| **Criteria box on every row and 14 filters, all working in place** | Usability, precision | Each home row shows impact, TRL, BRL, IRL, thesis fit and verdict as the company page states them. The rail filters on all of them and on sector and sub-sector, country (with its flag), impact category, registered age, source, programme deadline and declared member. Filtering never leaves the home page: one URL holds the state, active filters show as removable chips with "Clear all", an empty result says so, and every view is still a shareable link, for example `/?verdict=PORTFOLIO+SUPPORT`. <https://jx.hankintaviikko.fi/> |
| **Matchmaking**, `/match` | Actionability | Who is the next step for a startup, and which startups fit an investor, programme, funder or pilot partner: filter first, then rank, declared plus revealed demand, keywords from both sides, every reason in words with its record, no score. The home page's "Top matching startups for A'Pelago" tab (with a picker for any investor or accelerator) prints the same ranking, its first 25, and an investor is shown the early pipeline under the line "No startup on the radar is at due diligence yet; these are the closest" (D63). <https://jx.hankintaviikko.fi/match> |
| **Aava**, a six-question conversation, and the Ask Aava bar on the home page | Visual appeal, usability | The analyst speaks the page: "what do you think", "what is the official score", "how sure are you", "who should we meet", "what is the next move", "what would change your mind". Answers are built by code from the page's own records. A recorded voice (Rachel, ElevenLabs) plays only while its text matches the page (12 of 16 committed clips do at 17:40 UTC on 17 Oct: all six questions for Viva Jets and all six for Arctic Fry; see "Aava" below), the browser voice otherwise. Behind `?demo=1`, where the Ask Aava bar and a company page's follow-up box also answer through a reasoning mode on Claude Sonnet 5.5 (**on** since 17:37 UTC on 17 Oct; read-only tools, names and links checked by code). |
| **The earliness test, a checked AI stitcher and one thesis file per sector** | Scalability, technical execution with data and AI | Applying our own feed rule to live records, would we have shown the 19 Nordic Blue companies before they entered? The AI only proposes, plain code decides, and a sector swap is one YAML file. <https://jx.hankintaviikko.fi/backtest> |

**Missing information is a finding, not a low score.** The sponsor's guidance (A'Pelago, 17 Oct): "missing information is not necessarily a reason to exclude a company or assign it a low score. Identifying information gaps, distinguishing facts from assumptions, and determining what to investigate next can itself be valuable venture intelligence." The product does exactly that, and says so on the page:

- **Not yet evidenced.** Ocean impact rungs 1 and 2 (the sector is implied by an industry code or a line of business, and no record names the area) carry no band: 27 of the 59 companies on the home list read "Not yet evidenced", and the filter rail counts them as their own group. Technology, business and investment levels with no record read "no public record", and the decision table cannot turn a missing level into REJECT / LOW FIT (A10, A12).
- **What is missing.** The company page prints a "What's missing" line (for Arctic Fry: "Gaps on the record: business readiness is Low on the stored evidence; no public evidence for investment readiness; no public market evidence (public buyers in the category); no public financials evidence (grants and contracts)"), the decision table says "more public evidence needed" where it leaves a company on the watchlist, and Aava's sixth answer begins "What I am missing".
- **How sure.** Every ocean-impact level carries a confidence (high, medium, low) with the reason ("2 independent source families agree: PRH/YTJ register, Redstone Blue page"); every feed record carries a "How sure" line.
- **Facts versus assumptions.** "Impact implied by the sector" is printed whenever the memo's fallback reads impact as Medium; declared research is labelled as such and a low-confidence reading is "a lead and sets no rung"; the AI summary is a sentence-by-sentence extract of linked records, checked by code.
- **What would change my mind, and the record that would raise it.** Every ocean-impact level prints "To raise it" with the one record that would lift the rung (for Viva Jets at level 5: "Rung 6 needs a record from a source family other than the register whose own text names the area: a notice title, EU project text or investor-pipeline profile holding an area word"); Aava's sixth answer says what is missing and what would change the verdict, and never that evidence would lower one (for Viva Jets, a declared portfolio member: "What I am missing: no public buyer on record yet; market evidence on file: customer on own site. The verdict rests on the declared member list, not on the bands, so only a change to that list would change it", D49, D65).

**The measured result.** Applying its own feed rule to live public records, the radar would have shown **1 of the 19** cohort
companies before January 2026, and that one is tuned: Arctic Fry Oy counts only since 17 Oct, when freshwater aquaculture (industry
code 03220) was added to the sector list (D47) after the earliness audit had named that missing code as the reason the company was
missed. Before that change the live-records figure was **0 of 19**, the one we did not tune towards the cohort. Declared research
finds 12 more before January 2026 (13 of 19 with a counted signal in all), 5 appear only after it and 1 has none. The reason the number
is low is the finding: of the 7 cohort companies with a Finnish business ID, only Arctic Fry is registered under a code on the sector list,
and only since that addition; the other six are registered as software, retail, wholesale, consulting and R&D. Method and every
caveat: [EVAL.md](EVAL.md). Since the 17:37 UTC deploy the `/backtest` page prints a tuning note directly under its headline (D74): the intake families 582 and 03 were added after the backtest showed the net missed two cohort companies, so results for those two are measured on the companies used to tune the net (Arctic Fry's code 03220 sits in family 03).
The wide intake (it takes startup-shaped companies in before any sector test) held 4 of those 7 before January 2026 (Kilocode,
Sireness, Arctic Fry and Emission-Eye), and we claim less than that: Kilocode's intake date is a 2003 VAT registration, Kilocode and
Arctic Fry are there only because we added their code families after seeing them (in-sample, labelled on `/backtest`), Sireness
enters on a declared-research record rather than a public one, and Emission-Eye ranks 132 of 1,176 among the 2025 registrations in its
code family. Dates and ranks: [EVAL.md](EVAL.md), "Wide intake".

## The demo path (3 minutes, on the live site)

Full script with the lines to say, the reset step and the backup-laptop line: [DEMO_SCRIPT.md](DEMO_SCRIPT.md). The numbers below are the ones on the pages and in the JSON API on 17 Oct 2026 (17:38 to 17:50 UTC, build ac49cd8, live since 17:37 UTC) and move as the store is refreshed; each is read from the page or query named in [docs/NUMBERS.md](docs/NUMBERS.md).

1. **Home with the Ask Aava bar** <https://jx.hankintaviikko.fi/?demo=1> (the demo link also resets the sector to the default). Type "Tell me about Viva Jets" (or press its example chip). With the demo flag the reasoning mode answers in about 6 s (verdict Portfolio support, rank 2nd of 59, a link to the company, a Sources line) and the answer is spoken in Rachel through the run-time voice; if the model is off or fails, the deterministic card appears and plays the recorded clip (about 28 s): "Based on what the radar holds on Viva Jets Oy, I think it needs portfolio support, not an entry decision: already in Redstone Blue's portfolio, and the next support is a pilot with Eckerö Line Abp (Eckerö Group) and a grant from Interreg Central Baltic Programme 2021-2027." Under the bar a muted line reads "23 companies first seen in the last 90 days, 59 on the list"; the list carries 59 startups (the 31 found with a stated reason plus the 28 declared cohort and portfolio companies, 19 + 9); tabs All startups 59, Top matching startups for A'Pelago 25, New this quarter 23. Each row shows its first reason in words, and a sort line above the list says how the order is made.
2. **Viva Jets Oy as portfolio support**, <https://jx.hankintaviikko.fi/c/2962040-6> (`?demo=1` for Aava). It reads PORTFOLIO SUPPORT, not an accelerator place (D65): "Already in Redstone Blue's portfolio, and the next support is a pilot with Eckerö Line Abp (Eckerö Group) and a grant from Interreg Central Baltic Programme 2021-2027". Directly under it: "Read against the sector thesis Blue economy, Finland and Nordics". The Ocean Impact Assessment says: impact area sustainable maritime and port technology, found through industry code 30120; evidence records with links; level 5 of 9, Medium; confidence high because two source families agree; to raise it, a record from another source family whose own text names the area. All six of Aava's questions play the recorded voice.
3. **A'Pelago's match page**, <https://jx.hankintaviikko.fi/match?org=apelago>: "Declared cohort or portfolio 23 companies, 20 in our records", Best fits 25, and a second tab **Already connected** (20, never ranked). Each fit opens **Why this match**: the reasons in words, each with its record, and no score. The same 25 are the home page's Top matching tab.
4. **Redstone Blue's match page**, <https://jx.hankintaviikko.fi/match?org=redstone-blue>: Best fits 22, Already connected 9, and the line "No startup on the radar is at due diligence yet; these are the closest, in the order below." 15 of the 22 are A'Pelago Nordic Blue cohort companies (Arctic Fry, Emission-Eye, Sireness, Sub Marine Store, RedGet.io, VesselChain and others), read as portfolio support: an accelerator's graduates are the fund's early pipeline.
5. **Earliness test**, <https://jx.hankintaviikko.fi/backtest>: 1, 12, 5, 1 of 19 (the 1 is in-sample, and the tuning note says so under the headline), and the wide intake table with each rank beside its own pool. Close on it: we publish our own miss rate.

Optional if there is time (about 25 s): in the home rail press the sub-sector "Ocean data and monitoring" (4 of 59) and the country Finland (3 of 59); the list changes in place and "Clear all" returns to 59. Arctic Fry Oy, <https://jx.hankintaviikko.fi/c/3166759-6>, reads PORTFOLIO SUPPORT as a cohort company with the honest gap printed (business readiness 2 of 9, technology and investment readiness "no public record") and is the one live hit of the earliness test, a tuned one.

## What each screen does

1. **The home page** (`/`): the **Ask Aava bar** (below), then one list of companies, each row showing the name, the registered line of business, the ocean impact area, a life-line of dated public records, the **criteria box** (impact, TRL, BRL, IRL, thesis fit, verdict, each "x of 9", a band or "no public record", with the source records in its tooltip) and the memo's verdict, with the memo's first reason in words under the name (D70). A sort line above the list says how it is ordered: by verdict, strongest first (Invest, Due diligence, Accelerator, Partner introduction, Grant support, Portfolio support, Watchlist), and inside a verdict by evidence (declared cohort or portfolio member, then the Ocean Impact level, its confidence, business readiness, number of dated records, newest record; D48). On the live home list that is WATCHLIST 30, PORTFOLIO SUPPORT 28 and PARTNER INTRODUCTION 1, and no startup reads ACCELERATOR: a declared cohort or portfolio member reads PORTFOLIO SUPPORT whatever its bands (D65), and a thesis fit that rests on the industry code alone is capped at Medium (D66), which moved Härksalmi Oy and Kustservice i Finland Ab Oy to WATCHLIST. The 28 PORTFOLIO SUPPORT rows are the partners' own companies, so that verdict says "already yours; here is the next support", not an independent finding. Tabs: All startups, **Top matching startups for {investor or accelerator}** (default A'Pelago, the matchmaker's first 25 as the Match page prints them, each row with its reasons in words; a picker lists 73 investors and accelerators; D35, D63), New this quarter; country links; a **filter rail** with 14 filters in three groups: **Sector** (the three thesis files, and under the blue one 11 sub-sectors plus "Not yet classified", each link traced to a record; D33, D45), **What the judges score** (verdict, ocean impact, TRL, BRL, IRL, thesis fit) and **Narrow down** (country, impact category, registered age, source records, programme deadline, declared company). Filters work in place (D32): one URL holds the state, every control asks `GET /home/list` and only the list section is swapped, the address bar is rewritten without a history entry, active filters show as removable chips with "Clear all", and an empty result says "No startup matches these filters"; with scripts off every control is still a link. Choices inside one filter are alternatives, different filters all have to hold, and the number beside an option is how many startups would remain. Countries are a multi-select named in words with a flag (11 vendored flag-icons 7.2.3 SVGs, MIT; D34). The folded section "All public records in the window, weak matches and the rules" lists the 122 companies (31 main, 91 weak) with each record, why it fits the sector, how sure we are and the link.
2. **The company page** (`/c/{company key}`, the business ID for a Finnish company): the verdict and its reason in one sentence, the sector thesis it is read against (D71), the **Ocean Impact Assessment**, key statistics, an AI summary of the linked records (checked by code), **Who to meet** and **Next steps** (the matchmaking block; one top-three who-to-meet list that the memo's actions and Aava's meeting answer both read, D67), six public-record checks counted by one function, so the page and the home list agree (D68), the news life-line, and the four questions in the partners' order with every level's rule and evidence printed.
3. **Match** (`/match`): a counterpart list (191 organisations: 57 investors, 16 accelerators, 11 grant or loan programmes, 32 public funders and foundations, 60 corporate or public buyers, 10 ports, 5 clusters) and a startup search; an organisation's companies it already has are listed apart on their own tab ("Already connected", never ranked; D38). Method, practices adopted and rejected, and limits: [docs/MATCHING.md](docs/MATCHING.md).
4. **The Nordic Blue 19** (`/radar`) and the **earliness test** (`/backtest`): the 19 cohort companies and the 9 Redstone portfolio companies, and the test of whether the radar would have shown the cohort before it entered the programme.
5. **Menu** (top right, and the footer): the pages that used to be the header's tab row (New this quarter, The Nordic Blue 19, Match, Earliness test, Rules, Data). "New this quarter" opens the home page's tab of that name (`/?group=new`); `/how` answers a redirect to `/method` and the old 60-second guide is gone (D73). **Rules** (`/method`), **Data** (`/data`: 17,193 companies and 47,693 dated records, each with its link) and the read-only JSON API at <https://jx.hankintaviikko.fi/api> (company search, company with the Ocean Impact Assessment, feed, backtest, `/api/match/company/{key}`, `/api/match/org/{id}`, `/api/match/orgs`).

**Ocean Impact Assessment (rule D27).** Evidence readiness from public records, not a measure of true impact: the Ocean Impact Navigator publishes impact areas and KPIs but no levels, so the nine rungs are ours and each names the record that must be on file. 1 to 2 the sector is implied (industry-code family, registered line of business, a legal-name word backed by a second source family); 3 to 4 the source's own text names the area; 5 to 6 a second independent source family names it and a blue programme or portfolio page lists the company; 7 to 8 declared research holds an impact assessment or a quantified outcome with a stated method; 9 a measured outcome from an official or register source, which no connected source holds. Bands: levels 1 to 2 carry no band ("not yet evidenced"), 3 to 7 Medium, 8 to 9 High. **One impact truth (D46):** the criteria box, the verdict, the company page and the API all take the impact band from this ladder, and the Navigator-style category the frameworks rule finds is context only. On the 59 home rows: 3 companies reach a level (all 5 of 9, confidence high), 27 read "not yet evidenced" (25 at rung 1, 2 at rung 2), and the other 29 have no rung and read "No public record". The filter rail counts the same split: Medium 3, Not yet evidenced 27, No public record 29. No company reaches rung 6 or higher today. Ladder in full on `/method#ocean-impact`; method note in [METHOD.md](METHOD.md), section 7.

![The Ocean Impact Assessment on the company page of Viva Jets Oy, a Redstone Blue portfolio company: impact area, evidence records with links, scalability (not assessed from public records), level 5 of 9 with the nine-rung bar, confidence high with its reason, and the record that would raise it](docs/hero_ocean.png)

*Screenshot committed at 13:20 UTC on 17 Oct (e46a899). The assessment is unchanged; the verdict line above it now reads Portfolio support for this company (D65), and "Read against the sector thesis" is printed under the verdict (D71).*

**Matchmaking (rules D28 to D30, A34).** For a startup: the investors, programmes, funders and pilot partners that fit its verdict path, the geography they declare and the readiness window they state (hard filters), with the same sector or impact area, shared words, lookalikes in the counterpart's declared cohort or portfolio and a deadline inside 90 days as reason chips. For a counterpart: the startups that fit it, ranked, with the companies it already has (its declared cohort or portfolio) listed apart as "Already connected" (D38). Demand is **declared** (its own text, stages, geography, window) plus **revealed** (the companies it has chosen: 14 of the 191 organisations have declared companies in our records, 67 links); keywords are read on **both sides** (the counterpart's declared words and the startup's own text, through keyword groups from the thesis file and raw shared word stems); there is **no score** anywhere, and the API has no score field. The verdict path decides who a startup meets: a declared cohort or portfolio member (PORTFOLIO SUPPORT) meets programmes, funders and clusters, never accelerators (D65), and every startup also meets corporates and ports as pilot partners; an investor is shown the early pipeline, with due diligence and invest first when any exist (D63).

**Aava (deterministic answers, recorded voice).** Six questions per company page, each with one first-person answer built only from the rows the page shows; a fact the records lack is spoken as missing. For a declared cohort or portfolio member the answers name the member rule (D65) and say that only a change to the declared list would change the verdict. The answers for Viva Jets Oy and Arctic Fry Oy, and the home page's one "what is new" answer, were pre-rendered at build time in the ElevenLabs voice Rachel (16 clips, 4,449 characters: 12 for the two companies, 1,833 for Viva Jets and 2,065 for Arctic Fry, and 4 for the feed answer, 551; model `eleven_multilingual_v2`, in `radar/static/aava/audio/`). A clip plays from a file, with no network call and no key at runtime, only while its text fingerprint equals the text on the page; otherwise the browser's own voice reads it. **The company clips were re-rendered for the portfolio-support wording (commit ac49cd8, 17:34 UTC), and at 17:40 UTC 12 of the 16 match the live text**: all six questions for Viva Jets and all six for Arctic Fry play Rachel. The feed's 4 clips were not re-rendered and no longer match, so "What is new on the radar?" is read by the browser's voice. Aava is hidden on the public site: `?demo=1` turns it on for that device (remembered), `?demo=0` turns it off. To render again: `ELEVENLABS_API_KEY=... python3 -m radar.aava_voice render --keys 2962040-6,3166759-6 --feed`.

**Aava's reasoning mode (live behind `?demo=1` since 17:37 UTC on 17 Oct; D61, D62).** With the demo flag on, the Ask Aava bar and a company page's "Ask a follow-up" open a conversation with Aava on Claude Sonnet 5.5 through the Messages API (`radar/aava_llm.py`, `POST /api/aava/chat`, streamed; the prompt is `config/aava_prompt.md`, every setting `config/aava_llm.yaml`). Settings (D62): adaptive thinking at effort low, at most 3 steps (a hard ceiling of 4 model calls), only the final turn's text is shown (an interim note written beside a tool call is held back), and the answer is three short paragraphs. The model reasons only through read-only tools over code the site already runs (`radar/aava_tools.py`: search the cached home rows by sub-sector and the rail's other facets, get one startup's memo and records, explain a match, list organisations, read the visitor's current view, apply filters in the browser); the follow-up buttons come from a closing "Follow-ups:" line that code strips and caps at three; it sends no SQL, writes nothing and reaches no network. After generation code checks the names and links (`radar/aava_entities.py`): a company link stays only if a tool returned that company in the same turn, an external link only if its address is in a tool result, a company-shaped name no tool returned is left unlinked and listed as unverified, and every answer ends with a Sources line built from the addresses the tools cited. **Limit:** code checks names, links and addresses, not that a sentence's figure or date matches the tool result it restates. The chat takes 500 characters of input and 12 messages of history and is limited to 8 turns per minute per client address and 400 turns per day; on any failure (no key, limit, timeout, API error, refusal) the visitor gets a graceful sentence and then the deterministic answer of `radar/ask.py`. **Measured:** five real selftests on the live store took 4.7 to 7.0 s and cost $0.015 to $0.026 a turn ([EVAL.md](EVAL.md), "Aava's reasoning mode"). **Kill switch:** the file `data/AAVA_LLM_OFF`, read at each request with no restart; it is absent on the live site (parked as `data/AAVA_LLM_OFF.parked`), `GET /api/aava/status` answers `available: true` at 17:38 UTC, and moving the file back switches the mode off, after which the bar answers by the deterministic router only. Without `?demo=1` a visitor never reaches the model.

**Ask Aava bar (live since 12:54 UTC on 17 Oct, merge 5cd3293).** The home hero is a bar: "Ask Aava. About any company on this radar. Every answer is built from the public records on file, and its source is one tap away." Type a question (Enter asks; Ctrl or Cmd K focuses the bar from anywhere on the home page) or press one of the five example questions ("What is new on the radar?", "Tell me about Viva Jets", "Who should A'Pelago meet?", "Aquaculture startups with TRL at least 4", "Show high thesis fit companies in Finland"); an example is shown only when its answer is not empty in that sector's store (D40), and a question with no answer says so (so "Show accelerator candidates in Finland" is no longer a chip: no startup on the list reads ACCELERATOR, and it now answers 0 of 59). A **deterministic intent router** at `GET /api/ask?q=` (`radar/ask.py`) answers from the same records and Aava scripts, with no model and no network call: a company by name or business ID (Aava's first answer and "Open the full memo"), "who should X meet" for a company (Aava's fourth answer) or for an organisation (the match view), filter phrases such as "Aquaculture startups with TRL at least 4" (1 of 59, with the filter rail's URL, applied in place on the home page; "at least 4" selects the bands 4 to 6 and 7 to 9, D72), "top startups" and similar questions (the Top matching ranking for A'Pelago, or for the investor or accelerator named; D63), what is new, an organisation name, otherwise the search page; every word it reacts to is in the `ask:` block of the thesis file. The "22 companies surfaced" headline became one small muted count line under the bar, and the header tabs moved into a Menu and the footer. With `?demo=1` a microphone button opens a voice overlay: the browser's Web Speech API turns the spoken question into text (en-US; some browsers do that on their vendor's speech service, and the overlay says so), the answer is written and spoken, in the recorded voice when a recording matches the answer's text (today the company answers for Viva Jets and Arctic Fry) and in the browser's voice otherwise. With `?demo=1` the reasoning mode is on, so the bar's typed and spoken questions go to it first and fall back to this router; without the demo flag they go to the router only.

**Words on screen (D36 to D41).** No dataset rating, rule id, capability id or list-maker's working note is printed on a page: the declared research's own ratings read "the declared ecosystem research rates the fit", a capability is said as its sector group, a decision rule is said in its own words, and a quote or search query that holds a redaction marker is dropped, not shown with a gap. A sector chosen earlier never turns a company link into a 404 (the page is found in the other sector's store), and `/?demo=1` resets the sector to the default. Numbers that read as one measure name their measures: the main list is 31 companies found by the rule, the home list is those plus the 28 declared cohort and portfolio companies (31 + 28 = 59). The home page's muted line counts a second measure, "23 companies first seen in the last 90 days": companies whose first dated public record of any kind falls in the window. The 31 and the 23 are of two different sets, and `/method` says which (D72).

## Run it in 3 commands

From the repository root, with Python 3.12:

```bash
pip install -r requirements.txt
python3 -m radar.build
python3 -m uvicorn app:app --port 8130     # open http://127.0.0.1:8130
```

`python3 -m radar.build` runs every adapter in `radar/adapters/` and writes `data/radar_redstone_apelago_blue.sqlite`. The network
adapters read public APIs at one request every 2 seconds and cache what they read under `data/cache/`, so the first full build is
slow. Two quicker ways, both run on 17 Oct:

- Offline, in under 10 seconds (5.2 s on a warm run and 8.7 s on the first, 17 Oct): `python3 -m radar.build --adapters declared,businessfinland,ecosystem` loads the 28 declared
  companies, the Business Finland export and the declared ecosystem dataset (147 signals), and every page renders.
- The committed snapshot of 16 Oct, about 21:40 UTC: `RADAR_DATA_DIR=data/snapshot python3 -m uvicorn app:app --port 8130`. Its
  numbers are older than the live site's.

Second thesis: `python3 -m radar.build --thesis config/thesis_health_turku.yaml`. Tests: `python3 -m pytest -q` (880 passed, 1 failed and 5 skipped on 17 Oct at 15:19 to 15:26 UTC, main 1b6c857, before the j3 merges and not re-run in full since, with one latency test left out; the one failure is an intermittent timing test of the audio player, `tests/test_aava_voice.py::test_player_plays_the_feed_answer_clip_by_clip`, which passed on 4 of 6 solo reruns).

Sub-sectors (D45): the home page's Sub-sector filter reads the tables `sector` and `company_sector`, which `python3 -m radar.sectors backfill --db data/radar_redstone_apelago_blue.sqlite --thesis redstone_apelago_blue` writes (idempotent, about 1 s on the live store; `--dry-run` prints the counts). The build does not run it, so a store built as above has no Sub-sector group until it is run (the group hides itself), and the committed 16 Oct snapshot predates it. On the live store (17 Oct) it holds 1,059 links on 979 of 17,195 companies, each with its basis (industry code 898, declared research 94, own text 57, notice 8, corroborated name 2) and the public page it rests on; the other 16,216 companies read "Not yet classified".

Combined database (team only): `python3 -m radar.combined --thesis redstone_apelago_blue` writes `data/combined/redstone_apelago_blue_combined.sqlite`, the declared ecosystem file unchanged plus the radar's public-record tables (`radar_*`) and the view `v_entity_public_record`; it carries the dataset's `person` table, so it is not for publication.

## Sources

| Source | What it gives | Adapter |
|---|---|---|
| PRH/YTJ open data API v3 (Finnish trade register) | company facts and the register entry date | `prh.py` |
| PRH/YTJ registered entries (tax registers) | first sales (VAT or prepayment register) and first hire (employer register) dates | `tax_registers.py` |
| PRH registered notices API v3 | share issues, board changes, start-up notices, capital losses, each dated | `prh_notices.py` |
| PRH/YTJ wide intake | startup-shaped limited companies and cooperatives, taken in before any sector test | `prh_intake.py` (in the live store: 16,385 signals) |
| Hilma public procurement awards | a young company's first public contract in the sector's categories | `hilma.py` |
| CORDIS (Horizon Europe and H2020) | EU project participation, start date and EU contribution | `cordis.py` |
| Business Finland funding export | funding decisions, year only (the dashboard export has no decision date) | `businessfinland.py` |
| BlueInvest project pipeline | public profiles with TRL; a dated signal only when a page states a listing date | `blueinvest.py` |
| OpenAlex | research output whose author affiliation names the company | `openalex.py` |
| Norwegian (Brønnøysund) and Danish (CVR) registers | register facts for cohort companies abroad | `brreg.py`, `cvr.py` (1 record each in the live store) |
| Internet Archive (Wayback CDX) | first archived capture of a company's site and milestone pages | `webarchive.py` (not in the live store yet) |
| TED contract award notices | EU-wide public contracts won | `ted.py` (not in the live store yet) |
| EU Funding and Tenders reference data | EU grants to Finnish beneficiaries | `eu_grants.py` (not in the live store yet) |
| Estonian e-Business Register | register entries of Estonian companies | `estonia_register.py` (not in the live store yet) |
| Declared lists in `data/declared/` | the 28 cohort and portfolio companies, investors, programmes, buyers, and the ecosystem dataset | `declared.py`, `ecosystem.py` |
| AI stitcher | dated events on public web pages, proposed by an LLM and kept only when plain code confirms them twice | `stitcher.py` (run by hand, not by the build) |

### The sponsor's suggested sources, mapped

The sponsor (A'Pelago, 17 Oct) suggested these families. What we read, how much of it is in the live store (`/data`, 17 Oct), and what we do not read:

| Suggested family | What we read | In the live store | Not read |
|---|---|---|---|
| Company websites | The AI stitcher reads company sites, press pages and partner pages found by search (its preferred sources), and the Internet Archive's first capture dates the page; the register's website field is kept | stitcher: 27 signals on 13 companies; the Internet Archive adapter is built and not loaded | No crawler of our own, no site-wide scraping |
| Registries and annual reports | PRH/YTJ register, tax registers (first sales, first hire), registered notices (share issues, board changes), the wide intake; Norwegian and Danish register lookups | PRH register 759, tax registers 27,790, notices 1,806, wide intake 16,385, Norway 1, Denmark 1 | **Annual reports and filed financial statements are not read**; the company page says "no public financials evidence (grants and contracts)". Sweden (Bolagsverket) is a connector slot; the Estonian adapter is built and not loaded |
| News | The stitcher may use news pages it finds for a named company, and every event it keeps carries a quote and a link | inside the 27 stitcher signals | No news feed or media-monitoring source |
| Research publications | OpenAlex works whose author affiliation names the company (cohort, portfolio and ecosystem companies only) | 75 records on 12 companies | No patent-office source (Espacenet) is connected |
| EU BlueInvest | The public project pipeline | 21 profiles stored, 18 of them Finnish; no dated signal, because the pages carry no listing date (the TRL is used on the page) | The E-Pitching session on the company pages comes from the declared programme list, not from the pipeline |
| Business Finland | The funding export | 342 records on 97 companies, year only | The export has no decision date |
| EU funding databases | CORDIS (Horizon Europe, H2020) | 82 records on 70 companies | The EU Funding and Tenders reference data and TED are built and not loaded |
| LinkedIn, Dealroom, Crunchbase | **Connector slots, not connected** (with PitchBook and Tracxn); the pages draw each as a hatched slot, and nothing from them is stored | none | LinkedIn sits behind a login and the other two behind an account or a paid licence, and we do not scrape behind a login (A27); the stitcher refuses all five and code drops them |

Licences, snapshot dates and the full list are in [DISCLOSURE.md](DISCLOSURE.md).

## Honesty lines

- **No scraping behind logins.** LinkedIn, Dealroom, Crunchbase, PitchBook and Tracxn appear only as connector slots marked
  "not connected". Nothing from them is in the repository or on the pages.
- **Companies only, by rule.** Legal names shaped like a private person's name are hidden, the stitcher builds its own queries from
  register facts only and redacts person-shaped names in the quotes it stores, but never a company's own name, former names or legal-form
  words (D23), and the ecosystem dataset's people fields are not imported.
- **"No public evidence" is never a placeholder.** Empty is shown as empty with a hatched chip such as "not in public records".
  No level, date or number appears without the record behind it, and no register type code or stemmed keyword is printed on a company page (D24).
- **A gap is not a low score.** "Not yet evidenced" and "no public record" are their own states; a missing level never decides REJECT / LOW FIT.
- **Declared research is labelled.** Events from the declared ecosystem dataset carry "declared research" and form their own group
  in the backtest. Stitcher events are counted apart and never added to the live count.
- **A ranking explains itself in words (A34).** Matchmaking shows reasons with records, never a single number.
- **No model behind the pages, the memo, the matching or the recorded Aava answers.** Text is built from records by code; the AI in the data path is the stitcher, whose output plain code checks twice, and the batch-written company brief, whose every sentence code verifies. The one other place a model speaks is Aava's reasoning mode (Claude Sonnet 5.5, read-only tools over this site's own records, names and links code-checked after generation, deterministic fallback): it is **on** since 17:37 UTC on 17 Oct, only behind `?demo=1`, and code does not check that a figure in its sentence matches the record it restates.

## Architecture

```
public sources --> radar/adapters/*.py --> radar/emit.py --> data/radar_{thesis id}.sqlite
                                                                  |
  store.py, fit.py, frameworks.py, earliness.py, matching.py, memo.py, ocean_impact.py, matchmaker.py, sectors.py, aava.py
                                                                  |
          FastAPI + Jinja2 + htmx pages, JSON API at /api, Datasette (local only)
                                                                  |
          behind ?demo=1, on: aava_llm.py + aava_tools.py (Claude Sonnet 5.5, read-only tools) --> deterministic ask.py on any failure
```

The sector rules (industry codes, keywords, intake families, the memo's decision table, the impact areas and ladder, the matchmaking weights, the backtest population) sit in one thesis
file in `config/`, so a sector swap is one environment variable or one `?thesis=` parameter; the few sector words still in code are
named in ARCHITECTURE.md. Adapters and page routes are discovered by module, so parallel branches never edit a shared list. Full detail:
[ARCHITECTURE.md](ARCHITECTURE.md); the module map with commands to run each piece: [MODULES.md](MODULES.md).

## Documents

- [ARCHITECTURE.md](ARCHITECTURE.md): diagram, components and why each was chosen, what breaks first.
- [MODULES.md](MODULES.md): the four modules (data, API, matching, web) and how to run each alone.
- [EVAL.md](EVAL.md): the held-out set, the measured result and real failures.
- [METHOD.md](METHOD.md): how the AI stitcher searches, reads, dates and double-checks an event; the ocean impact ladder.
- [DISCLOSURE.md](DISCLOSURE.md): what we built this weekend and what we brought.
- [PILOT.md](PILOT.md): eight weeks with Redstone Blue and A'Pelago.
- [docs/MATCHING.md](docs/MATCHING.md): matchmaking, the practices adopted and rejected, the method and its limits.
- [docs/NUMBERS.md](docs/NUMBERS.md): every number in these documents, where it was read and when.
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md): the 3-minute path, the pitch lines and the before-going-live checklist.

## Team

Team Old Hackers. Dayo: demo, partner desks and the judged documents. Amir (GitHub amirhnourian): the agentic stitcher with
citations and the explainable match rules. AI coding sessions (Claude Code on our server and in the cloud) wrote code on branches
that we reviewed and merged; see [DISCLOSURE.md](DISCLOSURE.md).
