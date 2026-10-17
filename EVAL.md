# Evaluation

Every rule and dated decision behind these numbers: [PROJECT_RULES.md](PROJECT_RULES.md) (assumptions, decisions, taxonomy, formats; it folds in ASSUMPTIONS.md with the same ids).

**Headline, measured on the live site: 1 of 19, and that one is in-sample.** Applying its own feed rule to live public records, the radar
would have shown 1 of the 19 Nordic Blue 2026 cohort companies before January 2026: Arctic Fry Oy, first sales 2020-10-05, counted because
industry code 03220 (freshwater aquaculture) is on the sector list. **It is on the list since 17 Oct** (D47: committed 13:38 UTC, live at the 15:04 UTC restart): our own
earliness audit and a judge's review had both named the missing code as the reason the company was missed, and we added it. So this one
hit is tuned, the way the intake's two added families are (below). **Before that change the figure was 0 of 19**, measured on 17 Oct with the
code before the deploy, and 0 of 19 is the number that was not tuned towards the cohort. With declared research added, 12 more companies have a
counted signal before that date (13 of 19 in all), 5 appear only after it, and 1 has none. The live `/backtest` page and `/api/backtest` read
"would have shown 1 before January 2026 using live public records" and do not print the in-sample label themselves; this document does.
**Rule change 1, 17 Oct (judge round 3):** a sector word in the legal name is now corroborated only by a record from a different
source family (PRH register entries, PRH notices and PRH tax registers are one registry). Sub Marine Store's hit was the word "marin"
plus a PRH tax-register record, so under that rule the live store showed **0 of 19** from live records (12 declared research
only, 6 later, 1 none). **Rule change 2, 17 Oct (D47):** code 03220 joined the list, which moved Arctic Fry from "later" to "earlier by live
public records": 1, 12, 5, 1. The tables below are measured after both changes. The memo also has a fallback: thesis fit High, with no impact
evidence or with impact Medium on record, reads impact as the fallback's implied level, so a High-fit company with an unknown or evidenced-Medium impact
reads ACCELERATOR (the decision table's High-fit rule; D18, D53), printed as "the High-fit rule, impact Medium on record".
Source: <https://jx.hankintaviikko.fi/api/backtest> and <https://jx.hankintaviikko.fi/backtest>, read on 17 Oct 2026 at about 15:17 UTC,
footer build 1b6c857. Every number below has a row in [docs/NUMBERS.md](docs/NUMBERS.md).

**What the low number means.** For the Finnish companies the data was there; the sector rule is what missed them. All 7 cohort
companies with a Finnish business ID have dated public records in our store from before January 2026 (register entry, first sales,
first hire, register notices), and the rule counted one of them, the one whose code we added. The other 6 are not registered
under an industry code on the sector list: they are registered as software (58290, 62100), retail (47279),
wholesale (46900), management consulting (70200) and research and development (72100). A filter on industry codes and name words cannot see a blue-economy startup that registered as a
software company. That is why the radar has a **wide intake** (take startup-shaped companies in first, then grade sector fit by
evidence) and an **AI stitcher** (find the dated events on public web pages that registers do not hold). Both are measured below
and neither is mixed into the headline.

## Question

Would the radar have shown the companies that Redstone Blue and A'Pelago chose, before they chose them?

## Held-out set

- **19 Nordic Blue 2026 cohort companies and 9 Redstone Blue portfolio companies**, 28 rows in
  `data/declared/cohort_portfolio_companies.csv`. The list was assembled from apelago.fi and redstone.vc/portfolio on 16 Oct 2026 and
  committed in the first hour of the event (see DISCLOSURE.md). It is the population the partners picked, not one we picked.
- **Reference date: 2026-01-01**, the programme start month, declared by the team. Per-company pipeline entry dates are not public.
  The code reads `data/declared/cohort_entry_dates.csv` when it exists and then uses each company's own date, labelled with its source;
  that file does not exist yet (PILOT.md asks the partners for it).
- **How blind it is.** The cohort list and the first thesis file were committed in the same minute, 16 minutes after the bell, and
  the thesis file's comments mention a cohort company, so the people who wrote the sector rules had seen the names. When we first
  measured it, none of the 7 Finnish cohort companies' industry codes was on the sector list, so that headline (0 of 19) was not tuned towards the
  cohort. Since 17 Oct one code, Arctic Fry's 03220, is on the list because we saw the miss, so the live-records count of 1 is in-sample. Two wide-intake code families were also added after the backtest and are labelled in-sample (below).
- **The 9 portfolio companies have no entry dates in public data**, so they get no earliness verdict. They are used for coverage
  (does the radar hold dated records for them) and for the stitcher's recall.

## Metric

Each cohort company falls in exactly one of four groups, and the four always add up to 19 (the full rule is printed on `/backtest`):

- **Found earlier by live public records**: a stored signal of a feed type, dated before the reference date, that passes the same
  sector test the feed uses (industry code on the list, a sector word in the registered line of business or the source's own text, or
  a sector word in the legal name backed by a second record). A register entry counts only if the company was at most 5 years old.
- **Found earlier only by declared research**: no such live signal, but a medium- or high-confidence event from the declared research
  dataset dated before the reference date.
- **Found later**: counted signals exist, none before the reference date.
- **No public signal**: nothing counted.

## Result

| Group | Cohort companies |
|---|---|
| Found earlier by live public records | 1 (Arctic Fry Oy, in-sample: its code 03220 was added on 17 Oct) |
| Found earlier only by declared research | 12 |
| Found later | 5 |
| No public signal | 1 |
| Total | 19 |

Per company, first counted signal as served by `/api/backtest` on 17 Oct, about 15:17 UTC:

| Company | Country | Business ID | Group | First counted signal |
|---|---|---|---|---|
| Arctic Fry Oy | FI | 3166759-6 | earlier, live public records (in-sample, code 03220 added 17 Oct) | 2020-10-05, first sales (VAT register, PRH/YTJ tax registers), 62 months before |
| NIDO Contech | ES | none | earlier, declared research only | 2023-10-31, first customer or pilot named |
| PEATZ | DK | none | earlier, declared research only | 2024 (year only), accelerator or programme entry |
| ReefCircular | DK | none | earlier, declared research only | 2024 (year only), award or pitch win |
| VesselChain | ES | none | earlier, declared research only | 2024-02-29, exhibitor or demo |
| Race for Oceans Technology | DK | none | earlier, declared research only | 2024-06-30, exhibitor or demo |
| MOR | SE | none | earlier, declared research only | 2024-10-31, exhibitor or demo |
| Kilocode Oy | FI | 1840910-3 | earlier, declared research only | 2024-11-04, other dated event |
| Sensemakers | DK | none | earlier, declared research only | 2024-12-23, grant or public funding |
| Sireness Oy | FI | 3568392-1 | earlier, declared research only | 2025-04-30, grant or public funding |
| Your Devocean | SE | none | earlier, declared research only | 2025-04-03, exhibitor or demo |
| TuniSea | NO | none | earlier, declared research only | 2025-09-28, other dated event |
| Finnish Sauna Shop Oy | FI | 3516783-9 | earlier, declared research only | 2025-10-16, product launch |
| Sub Marine Store Oy | FI | 3197621-7 | later | 2026 (year only), Business Finland funding |
| Edilm | FI | none | later | 2026-02-09, other dated event |
| Emission-Eye Oy | FI | 3543918-7 | later | 2026-02-09, other dated event |
| Just-measure | DK | none | later | 2026-02-09, other dated event |
| RedGet.io | BG | none | later | 2026-02-09, other dated event |
| Taikoa Oy | FI | 3380111-1 | no public signal | none |

### The Finnish-register subset

7 of the 19 cohort companies have a Finnish business ID; 12 do not (5 Danish, 2 Swedish, 2 Spanish, 1 Norwegian, 1 Bulgarian, and
Edilm, Finnish but with no business ID found). The register adapters cover Finland, so only these 7 can be found by live records.

| | Finnish subset (7) |
|---|---|
| Have a dated live public record before 2026-01-01 in the store | 7 of 7 |
| Industry code on the sector list | 1 of 7 (Arctic Fry, 03220, since 17 Oct) |
| Found earlier by live public records | 1 (Arctic Fry, in-sample) |
| Found earlier only by declared research | 3 (Kilocode, Sireness, Finnish Sauna Shop) |
| Found later | 2 (Sub Marine Store, Emission-Eye) |
| No public signal | 1 (Taikoa) |

### The portfolio (9)

`/radar` lists 6 of the 9 portfolio companies with at least one dated public record (Kelluu, Norolan Artisanlures, Viva Jets,
NanoHalen, Valkama Watercrafts, Redkik) and 3 with none (Klimate, Denmark; Tethys Robotics, Switzerland; Unique Docks, Finland, no
business ID found). 6 of the 9 have a Finnish business ID.

## Wide intake (in-sample for two families)

The intake takes in limited companies and cooperatives whose industry code starts with a listed family and that show at least one
startup signal beyond the register entry (first sales, first hire, EU project or grant, research output, Business Finland, start-up
notice, share issue, public funding). Nothing about intake says the company fits the sector.

**What we claim.** Had the intake been running through 2025, 4 of the 7 cohort companies with a Finnish business ID (Kilocode,
Sireness, Arctic Fry and Emission-Eye) would have been in it before January 2026, and the claim stops short of "found early":
Kilocode's intake date is a 2003 VAT registration, so it is not an early find; Kilocode and Arctic Fry are in only because we added
their code families after seeing them, so they are in-sample; Sireness enters on a declared-research record rather than a public one;
and Emission-Eye, on a public start-up notice, ranks 132 of 1,176 among the 2025 registrations in its code family.

Live, from `/api/backtest` (`intake`) and the wide intake table on `/backtest`, read 17 Oct 2026 at about 15:17 UTC. The headline there
reads "Entered wide intake before cohort entry: 4 of 19" (before = 4). The other 3 Finnish cohort companies are outside the intake
code families (Finnish Sauna Shop 47279, Sub Marine Store 46900, Taikoa 70200); the other 12 have no Finnish business ID, so they
are not checked against the Finnish register. Rank counts companies of the same registration year and code family that had entered
intake by 2026-01-01, strongest first by startup signals up to that date, then earliest intake date.

| Company | Intake date and the record that set it | Rank, same year and family | What limits the claim |
|---|---|---|---|
| Kilocode Oy (1840910-3) | 2003-08-01, first sales, VAT register (PRH/YTJ tax registers); registered 2003-07-11 | 3 of 8 (2003, family 58) | Not an early find: the date is 22 years before cohort entry. In-sample: family 582 was added after the backtest showed the net missed it. |
| Sireness Oy (3568392-1) | 2025-04-30, grant or public funding, a declared-research record (dataset confidence medium) | 1 of 104 (2025, family 72) | Rests on a declared record, not a public one; the date is five months before the company's own registration (2025-09-29). On public records alone its first startup signal is 2025-09-29 (first sales and first hire, tax registers), also before cohort entry. |
| Arctic Fry Oy (3166759-6) | 2020-10-05, first sales, VAT register (PRH/YTJ tax registers) | 3 of 16 (2020, family 03) | In-sample: family 03 was added after the backtest showed the net missed it, so the result is measured on a company used to tune the net. |
| Emission-Eye Oy (3543918-7) | 2025-07-02, start-up notification (PRH registered notices) | 132 of 1,176 (2025, family 62), about the top 11 percent | A public record, in a family that was not added afterwards. The page itself calls the rank generous to the cohort company: read it as an upper bound on how findable the company was. |

- **Not blind, even for the untuned families.** The first intake families (26 to 30, 62, 63, 71, 72) were chosen as general
  tech-startup families after the earliness audit had already listed the cohort's registered codes (62100 for Emission-Eye, 72100
  for Sireness; [EARLINESS_AUDIT.md](EARLINESS_AUDIT.md)); only 582 and 03 were added later and are labelled. So none of the four is a
  blind result, and 4 of 7 is a statement about what the net holds, not a forecast of what it will find next.
- **The honesty note.** The families 582 (software publishing) and 03 (fishing and aquaculture) were added after the first backtest
  showed the net missed two cohort companies, Kilocode (58290) and Arctic Fry (03220). `/method` and `/backtest` print that sentence.
- **First run, on a store copy** (commit 93798f5, before families 582 and 03 existed): 616 requests, 50,480 companies examined,
  19,027 passed the form and code test, 2 of 19 cohort companies entered intake before cohort entry (Sireness and Emission-Eye, both
  still in the live result). The live store holds records that copy did not (a declared-research grant for Sireness, a start-up
  notification for Emission-Eye), so their dates and ranks moved: that run gave Sireness 2025-09-29, rank 20 of 103, and
  Emission-Eye 2025-08-01, rank 715 of 1,176. The live figures above replace them.
- **Live store**: the intake rows are in the live store (16,385 from `prh_intake`, `/data`, 17 Oct about 15:17 UTC).

## AI stitcher

The cloud batch of 17 Oct 2026, 00:18 UTC, is recorded in [METHOD.md](METHOD.md) and in the commit message of `origin/cloud/stitcher`
(54 companies on the snapshot store). Its LLM answers are committed in `data/fetched/stitcher/proposals/` (54 files), so the code checks can be
replayed without LLM time. The replay on the live store (run `2026-10-17T01:42:07Z`, read from the live store's `stitch_log`) is what the live pages
show, and its figures differ from the batch's (METHOD.md has the batch's own: 168 kept, 128 confirmed, 29 emitted):

- **44 companies read** (18 cohort, 8 portfolio, 18 main-feed), **175 events proposed**, **146 passed the first check** (the page names
  the company and prints the date; 29 dropped: 19 name and date not on the page, 5 company not on the page, 5 page not fetched, HTTP 429 or 403).
  **105 passed the second check** (fresh fetch; 41 refuted: 24 type not in quote, 10 company not near quote, 4 page not re-fetched on HTTP 429,
  3 year not near quote). **25 emitted**, 4 were duplicates of signals already stored (25 + 4 = 29, the number the batch reports as emitted), and 76
  confirmed events stay in `stitch_log` only because their type is not one the radar emits (incorporation 12, partnership 10, product launch 4, grant 4, and other labels).
- **27 stitcher signals in the live store** (25 from this replay, 2 from the first run of 16 Oct, 23:06 UTC), on 13 companies (`/data`). The 27 are the 25 of this replay plus 2; the earlier "27 against 29" gap in this document is the 4 duplicates.
- **25 of the 44 companies** have at least one confirmed event: cohort 13 of 18 (53 events), portfolio 7 of 8 (47 events), main feed 5 of 18 (5 events).
- **Earliness, counted apart**: `/backtest` reads "3 of 19 cohort companies have an event found by the AI stitcher and checked by code whose page the
  Internet Archive captured before the company's reference date (19 of 19 have a stitcher run)": VesselChain (customer on own site, page public since 2022-10-03),
  Race for Oceans Technology (programme entry, public since 2025-12-12) and Edilm (programme entry, public since 2025-09-09). Events with an unmapped label are never counted.
- **Recall on the three companies with no proposals in the first run** (Sub Marine Store, Taikoa, Arctic Fry): the replay proposed 3, 2 and 2 events for them and confirmed none.
- **Intake thesis-evidence pass** on the top 100 wide-intake companies: 1 yes (Meriva Oy), 30 no, 69 unclear (nothing public describes
  the company's activity). Counted from the 100 committed records in `data/fetched/stitcher/intake_fit/` (commit 634f83c, merged into main as 74fe976).
- **Limits of this run**: the replay's page fetches hit rate limits (9 of the drops and refutations are HTTP 429 or 403), so a second replay could confirm more; the batch's own
  limits (no access to the Internet Archive CDX index from the cloud session, web-search budget) are in METHOD.md.

## Ocean Impact Assessment (D27, D46)

What is measured, and what is not. The assessment is **evidence readiness from public records, not impact**: it says how well an impact area is evidenced, in
nine rungs that each name the record that must be on file (`radar/ocean_impact.py`; ladder in `impact_readiness:` of the thesis file; `/method#ocean-impact`). There is
no ground truth for it: the Ocean Impact Navigator publishes areas and KPIs but no levels and is login-walled. So what we can report is coverage and honesty, not accuracy.

- **On the 59 home-list companies** (store copy of 17 Oct, 15:13 UTC, the same rows the page counts): 3 reach a level, all rung 5, Medium, confidence high (Viva Jets Oy, Valkama Watercrafts Oy,
  Arctic Fry Oy); 27 are sector implied only (25 at rung 1, 2 at rung 2) and read "Not yet evidenced" with no band; 29 have no record that names an impact area and so no rung, and read "No public record". Since D46 the
  Navigator-style category that the frameworks rule finds (Kelluu Oy from an OpenAlex keyword, NIDO Contech from a CORDIS keyword) is context only and no longer shows as an impact band in the criteria box, so the two
  cells that read "Medium" by category before now read "No public record". The filter rail counts the same split (Medium 3, Not yet evidenced 27, No public record 29). None reads Low.
- **On the 28 declared cohort and portfolio companies**: the same 3 get a level and 25 get none. Most of the cohort is registered as software, retail or consulting, or sits outside
  Finland, so no record we hold names one of the five areas for it; the page says "No rung applies: no record on file names an impact area for this company" rather than guess.
- **No company reaches rung 6 or higher.** Rung 6 needs a second source family and a programme listing together, rungs 7 and 8 a declared-research impact reading at medium or high dataset
  confidence, and rung 9 an official or register outcome that no connected source holds. A low-confidence declared reading is shown as a lead and sets no rung (D27, A24).
- **What the one impact truth did to the verdicts (D46, D47, D53).** Every surface now takes the impact band from the ladder, and a declared cohort or portfolio member reads High thesis fit by rule. On the home list the verdicts moved from
  WATCHLIST 54, ACCELERATOR 3, PARTNER INTRODUCTION 1 (58 rows) to **ACCELERATOR 21, WATCHLIST 36, GRANT SUPPORT 1, PARTNER INTRODUCTION 1** (59 rows), and thesis fit from High 23 and Medium 35 to High 50 and Medium 9.
  Read it with this limit: 19 of the 21 ACCELERATOR rows are declared members the partners had already chosen (the other 2 are Härksalmi Oy and Kustservice i Finland Ab Oy), so the verdict now partly says "the partners picked it".
  It is a rule applied consistently, not a finding about those companies, and no partner has yet rated any verdict (PILOT.md).
- **The ladder is ours.** The partners' own definition would replace it; PILOT.md asks for that in weeks 5 and 6.

## Matchmaking

No ground truth exists for who should have met whom ([docs/MATCHING.md](docs/MATCHING.md), section 5), so nothing here is an accuracy figure. Measured on the live store copy of 17 Oct (15:13 UTC):

- **Counterparts:** 191 organisations (57 investors, 16 accelerators, 11 grant or loan programmes, 32 public funders and foundations, 60 corporate or public buyers, 10 ports, 5 clusters);
  14 have declared companies in our records (67 links; A'Pelago 20 of its 23).
- **Coverage:** of 15,511 matchable startups, 17 of the 19 cohort companies and all 9 portfolio companies have at least one counterpart that passes the filters with a topic reason. Viva Jets Oy has 56
  (Business Finland, Meyer Turku Oy and A'Pelago first), Arctic Fry Oy 33.
- **Speed:** the first match after a start builds the index in 1.4 to 2.7 s (three runs, 17 Oct 15:28 UTC), then a company's matches take 4 to 15 ms; a counterpart's view takes 0.6 to 1.1 s.
- **On the home page:** the tab "Top matching startups for A'Pelago" shows 28 of the 59 home rows (the matchmaker's ranking for A'Pelago intersected with the home list; D35); its picker holds 73 investors and accelerators. A'Pelago's own view lists its 20 declared companies in our records apart as "Already connected" (D38), ranks the other startups (300 checked in full pass the filters, 657 more passed the first pass and were not checked in full) and shows the top 25.
- **In-sample, and a hypothesis:** the keyword thresholds were set by reading junk matches on the live store; the weights (sector 3, lookalike 3, shared words 2, readiness 2, timing 1, geography 1) are a stated hypothesis that
  only order the list. A partner rating of 20 pairs is the first real check (PILOT.md).
- **No score:** the API returns the reasons with their links and an ordinal `rank`, never a number that could be read as a score (A34).

## Judge dry-run fixes (D22 to D26, D31 to D41, D45 to D53), as they read on the live site

| Fix | Rule | What the live site shows now (17 Oct, 15:13 to 15:40 UTC) |
|---|---|---|
| Water, sewerage and remediation codes read Medium thesis fit | D22 | All 8 home-list companies registered under codes 36, 37 or 39 read thesis fit Medium and WATCHLIST; none reads ACCELERATOR |
| A company's own name is never redacted, and `radar.repair_redaction` restores names that were hidden | D23 | The Viva Jets page prints "Snowsus Ltd., founded in Oulu in 2018", its company's former name, where it used to print "[name redacted].," |
| No raw token on a company page or in a matching sentence: a register type code, a stemmed keyword, a capability id, a dataset rating, a rule id | D24, D36 | 0 instances of "dataset match N of 100", "capability tag", "fallback c2" or "711xx" on `/`, the two demo company pages, `/match`, `/method`, `/data` and the match API; the dataset's own readiness readings are still printed beside the rule levels in question 02, labelled declared research with their scale (A24) |
| The backtest states each rank beside its own pool and no median | D25 | "Sireness Oy 1 of 104, Arctic Fry Oy 3 of 16, Kilocode Oy 3 of 8 and Emission-Eye Oy 132 of 1,176" |
| Every sector's home list is warm at start, and a request waits at most 3 seconds for it (then the page renders without it) | D26 | `/?thesis=baltic_blue` answered in 0.45 to 0.87 s over 10 requests (15:18 UTC, median 0.54 s); after the 13:16 UTC restart its first two requests took 3.6 s and 2.8 s while the list warmed (the wait is capped at 3 s, then the page renders what it has); it took 70 s on the first load before D26 |
| An organisation's description never shows a redaction marker | D31, D36 | `/match`, `/match?company=2962040-6`, the match API and both demo company pages hold 0 redaction markers ("[name]" or "[name redacted]"): since D36 a stitcher quote or search query that holds one is dropped, not shown with a gap (before: 5 on Viva Jets Oy, 1 on Arctic Fry Oy) |
| Filtering never leaves the home page | D32 | `/home/list?verdict=ACCELERATOR` answers "21 of 59 startups"; `verdict=INVEST` answers "0 of 59 startups" with "No startup matches these filters"; the response carries `HX-Replace-Url`, so the address bar is rewritten without a history entry; Sub-sector Ocean data and monitoring then Country Finland read 4 then 3 of 59 |
| The sector is a filter group, not a header block | D33 | The rail's first group lists the three sectors (59, 152 and 1 startups) and, under the blue one, its sub-sectors; the sector cookie follows the choice |
| Country multi-select with flags | D34 | Seven countries on the blue list (Finland 46, Denmark 6, Spain 2, Sweden 2, Bulgaria 1, Norway 1, Switzerland 1); 11 flag SVGs (flag-icons 7.2.3, MIT) are vendored beside their licence; a country with no file prints its name alone |
| "Top fits" is a match for someone | D35 | The tab reads "Top matching startups for A'Pelago", 28 of 59, with a picker of 73 investors and accelerators |
| Working notes and generic words are never reasons; an organisation's companies are listed apart | D37, D38 | A'Pelago's view: "Already connected 20", then 25 shown of the startups that fit |
| A sector chosen earlier never turns a link into a 404, and the demo link resets the sector | D39 | With the health sector in the cookie `/c/2962040-6` answers 200; `/?demo=1` sets the cookie back to the blue sector and shows "59 of 59" |
| Example questions have answers | D40 | The five chips each answer; "Show accelerator candidates in Finland" answers "15 of 59 companies on the list match" and replaced "Show investment-ready companies in Finland" (0 of 58) |
| Two numbers that read as one measure name their measures | D41 | `/method`: "31 new companies in the main list ... the list on the home page is these 31 plus the 28 declared cohort and portfolio companies" (59) |
| Sub-sectors, each link traced to a record | D45 | 1,059 links on 979 of 17,195 companies in the live store; on the 59 home rows shipbuilding and boats 14, water and pollution 10, ship repair and maritime services 8, aquaculture and fisheries 4, ocean data and monitoring 4, coastal tourism and boating 3, ports and marine construction 2, maritime software and tech 1, shipping and logistics 1, not yet classified 17 (a company can have several) |
| One impact truth; declared members read High fit; 03220 is a listed code; more evidence never lowers a verdict | D46, D47, D53 | Viva Jets, Valkama and Arctic Fry read ACCELERATOR with impact Medium on record; ACCELERATOR 3 to 21 (above); Arctic Fry counts in the earliness test (headline) |
| Inside a verdict the home list orders by evidence | D48 | First ten rows: Viva Jets Oy, Valkama Watercrafts Oy, Arctic Fry Oy, Kelluu Oy, VesselChain, Redkik Oy, Tethys Robotics, Sensemakers, Norolan Artisanlures Oy, NanoHalen Oy |
| Aava never says evidence would lower a verdict; a stale brief sentence is dropped; "to raise it" matches the families on file | D49, D50, D52 | Viva Jets question 6: "No single new record would lift the verdict by itself. It would move to due diligence if ocean impact rose to high and business readiness rose to high"; "To raise it: Rung 6 needs a record from a source family other than the register whose own text names the area" |

## Software checks

- `python3 -m pytest -q -p no:cacheprovider --deselect tests/test_api.py::test_each_endpoint_answers_under_500_ms`: 880 passed, 1 failed, 5 skipped, 1 deselected in 362 s, run on 17 Oct (15:19 to 15:26 UTC, on the merged tree with main 1b6c857).
  The one failure is `tests/test_aava_voice.py::test_player_plays_the_feed_answer_clip_by_clip`, a browser test of the audio player's timing: run alone it passed on 4 of 6 reruns and failed on 2, so it is intermittent, not a stable break.
  The deselected test asserts a latency (best of three under 0.5 s), which depends on host load, so it is left out of this run; the latencies below are measured on the public URL instead.
- `/root/hack/bin/smoke.py https://jx.hankintaviikko.fi --max 14`: PASS 15/15 pages on 17 Oct at 15:19 UTC (the home page with and without the trailing
  slash, radar, match, backtest, method, data and the home-list views: the tabs all, fit and new, and the country views FI, DK, ES and SE and BG), no console errors.
- Offline, from an empty data directory: `python3 -m radar.build --adapters declared,businessfinland,ecosystem` (5.2 s on a warm run and 8.7 s on the first, 17 Oct 15:19 UTC, 147 signals, 28 declared companies), then the pages answered from `uvicorn` on a spare port (28 rows on the home list, no Sub-sector group until `python3 -m radar.sectors backfill` is run on that store).
- Latency over the public URL, 10 requests each, 17 Oct 15:18 UTC (min to max): `/api/feed` 0.17 to 0.27 s, `/api/backtest` 0.30 to 0.70 s, `/api/company/2962040-6` 0.27 to 0.71 s,
  `/api/match/company/2962040-6` 0.05 to 0.12 s, `/api/match/org/apelago` 0.49 to 0.88 s, `/` 0.63 to 1.13 s (median 0.78 s), `/home/list` 0.08 to 0.17 s, `/api/ask?q=Tell me about Viva Jets` 0.26 to 0.62 s.

## Failure examples (real ones)

| Company | Expected | Got | Why |
|---|---|---|---|
| Arctic Fry Oy (3166759-6) | found before 2026: first sales 2020-10-05 and registration 2020-10-23 are in the store | later (2026-02-09, declared) until 17 Oct; since D47 earlier by live records (62 months before), in-sample | code 03220 freshwater aquaculture was not on the list (03210 marine is), "aqua" matches whole words only, and the registration is older than the 5-year cut. We added the code after seeing the miss, so the fix is tuned to this company, and the count of 1 says so |
| Emission-Eye Oy (3543918-7) | found before 2026: registered 2025-06-13, start-up notice 2025-07-02, first sales 2025-08-01 | later | code 62100 computer programming is not on the list and the name has no sector word |
| Taikoa Oy (3380111-1) | found: registered 2023-07-28, first sales the same day | no public signal | code 70200 management consulting; the company trades as WAIing, a link the declared list itself marks unconfirmed |
| Sub Marine Store Oy (3197621-7) | a hit for a sector reason | later (2026, year-only Business Finland record): the word "marin" in the name is backed only by a register record from the same PRH/YTJ family, which no longer counts | the code is 46900 non-specialised wholesale; the corroborating record is not an independent source |
| 12 companies without a Finnish business ID | some live record | 3 hold one: a CORDIS project (NIDO Contech, 2026-06-01), a Norwegian register entry (TuniSea, 2025-09-30) and a Danish one (Just-measure, 2018-04-20); none counts | Norway and Denmark are single look-ups of known companies, there is no register adapter for Sweden, Spain or Bulgaria |

## Rerun

```bash
curl -s https://jx.hankintaviikko.fi/api/backtest | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['headline'])"
python3 -m radar.earliness                      # the same backtest as text, on the local store
python3 -m radar.adapters.stitcher --batch data/fetched/stitcher/batch.txt --proposals data/fetched/stitcher/proposals
python3 -m pytest -q
```

## What this does not show

- n is small: 19 companies with an earliness verdict, one cohort, one reference date for all of them.
- The reference date is ours, not each company's real entry date, so "months before" is measured against January 2026.
- 12 of the 19 are outside the Finnish registers, so for them the test measures declared research, not the radar.
- The health-tech thesis is a swap demo, not an evaluated thesis, and a thin one. On 17 Oct its home page says "1 company first seen in the last 90 days, 1 on the list"
  (first public record inside the window: KE Pharma Oy) and the folded full-window list holds 30 companies,
  1 main match and 29 weak matches; several of the weak ones are not health companies (two "auto care" firms matched on the word "care").
- No partner has yet scored the memos, the next steps, the ocean-impact rungs or the matches; usefulness to Redstone Blue and A'Pelago is untested (PILOT.md, weeks 5 to 8).
- The Ocean Impact ladder and the matchmaking weights have no ground truth; the first is ours and the second is a hypothesis (above).
- **The 1 of 19 is tuned** (above): Arctic Fry's code was added after we saw the miss. The untuned live-records figure is 0 of 19. The live `/backtest` headline says 1 and does not print that label.
- **ACCELERATOR partly means "declared member".** 19 of the 21 ACCELERATOR rows on the home list are cohort or portfolio companies, because a declared member reads High thesis fit by rule (D47) and reaches the fallback when its impact is unknown (D53). The verdict is not an independent signal for them.
- Aava has a recorded voice for two companies (Viva Jets Oy and Arctic Fry Oy, 12 clips) and for the home "what is new" answer (4 clips) only, and the recordings are partly stale: a clip plays only while its text fingerprint matches, and the wording changed at the 15:04 UTC restart, so 3 of the 16 clips match the live text at 15:40 UTC (Viva Jets questions 1, 4 and 5); everywhere else the browser's voice reads it until the clips are rendered again.
- **Aava's reasoning mode is not evaluated.** It is built and switched off; no real-model turn has been measured for answer quality or latency, and code checks the names and links it writes, not that each figure matches the record it restates (D61). Nothing in this document's results depends on it.
- The Ask Aava bar (live) answers by deterministic rules and is not a measured feature; nothing in this document's results depends on it. An example question is shown only when it has an answer (D40).
