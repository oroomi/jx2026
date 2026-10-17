# Evaluation

**Headline, measured on the live site: 0 of 19.** Applying its own feed rule to live public records, the radar would have shown
0 of the 19 Nordic Blue 2026 cohort companies before January 2026. With declared
research added, 12 of 19 have a counted public signal before that date, 6 appear only after it, and 1 has none.
**Rule change, 17 Oct (judge round 3):** a sector word in the legal name is now corroborated only by a record from a different
source family (PRH register entries, PRH notices and PRH tax registers are one registry). Sub Marine Store's hit was the word "marin"
plus a PRH tax-register record, so under the new rule the swapped live store shows **0 of 19** from live records (12 declared research
only, 6 later, 1 none), measured with the code on 17 Oct before deploy. The tables below are measured after the change. The memo also
gained a fallback: thesis fit High on more than an industry code, with no impact evidence, reads impact as Medium, implied by the sector (rule c2 gives ACCELERATOR,
c1 GRANT SUPPORT for TRL 1-3, c3 DUE DILIGENCE), printed as "because: fallback c2, impact implied by sector".
Source: <https://jx.hankintaviikko.fi/api/backtest> and <https://jx.hankintaviikko.fi/backtest>, read on 17 Oct 2026 at 03:24 UTC,
build c2174cd.

**What the low number means.** For the Finnish companies the data was there; the sector rule is what missed them. All 7 cohort
companies with a Finnish business ID have dated public records in our store from before January 2026 (register entry, first sales,
first hire, register notices), and the rule counted none of them. None of the 7 is registered
under an industry code on the sector list: they are registered as software (58290, 62100), retail (47279),
wholesale (46900), management consulting (70200), research and development (72100) and freshwater aquaculture (03220, next to the
listed 03210 marine aquaculture). A filter on industry codes and name words cannot see a blue-economy startup that registered as a
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
  the thesis file's comments mention a cohort company, so the people who wrote the sector rules had seen the names. None of the 7
  Finnish cohort companies' industry codes is on the sector list, so the headline was not tuned towards the cohort. Two wide-intake code families were added after the backtest and are labelled in-sample (below).
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
| Found earlier by live public records | 0 |
| Found earlier only by declared research | 12 |
| Found later | 6 |
| No public signal | 1 |
| Total | 19 |

Per company, first counted signal as served by `/api/backtest` on 17 Oct, 03:24 UTC:

| Company | Country | Business ID | Group | First counted signal |
|---|---|---|---|---|
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
| Arctic Fry Oy | FI | 3166759-6 | later | 2026-02-09, other dated event (the A'Pelago cohort announcement) |
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
| Industry code on the sector list | 0 of 7 |
| Found earlier by live public records | 0 |
| Found earlier only by declared research | 3 (Kilocode, Sireness, Finnish Sauna Shop) |
| Found later | 3 (Sub Marine Store, Arctic Fry, Emission-Eye) |
| No public signal | 1 (Taikoa) |

### The portfolio (9)

`/radar` lists 6 of the 9 portfolio companies with at least one dated public record (Kelluu, Norolan Artisanlures, Viva Jets,
NanoHalen, Valkama Watercrafts, Redkik) and 3 with none (Klimate, Denmark; Tethys Robotics, Switzerland; Unique Docks, Finland, no
business ID found). 6 of the 9 have a Finnish business ID.

## Wide intake (in-sample for two families)

The intake takes in limited companies and cooperatives whose industry code starts with a listed family and that show at least one
startup signal beyond the register entry (first sales, first hire, EU project or grant, research output, Business Finland, start-up
notice, share issue, public funding). Nothing about intake says the company fits the sector.

- **Run on a store copy** (commit 93798f5, before families 582 and 03 existed): 50,480 companies examined, 19,027 passed the form and
  code test, 2 of 19 cohort companies entered intake before cohort entry: Sireness Oy (first startup signal 2025-09-29, rank 20 of 103
  new 2025 companies in family 72) and Emission-Eye Oy (first sales 2025-08-01, rank 715 of 1,176 in family 62).
- **The honesty note.** The families 582 (software publishing) and 03 (fishing and aquaculture) were added after that backtest showed
  the net missed two cohort companies, Kilocode (58290) and Arctic Fry (03220). Any result for those two is measured on the companies
  used to tune the net, and `/method` and `/backtest` print that sentence.
- **Live today**: the intake rows are in the live store (16,385 from `prh_intake`), so `/backtest` reads
  "Entered wide intake before cohort entry: 4 of 19": 4 of the 7 Finnish cohort startups entered intake before the cohort entry
  (Kilocode, Sireness, Arctic Fry, Emission-Eye; median rank 3 of 60).

## AI stitcher

Batch run of 17 Oct 2026, 00:18 UTC, recorded in [METHOD.md](METHOD.md) and in the commit message of `origin/cloud/stitcher`. The
LLM answers are committed in `data/fetched/stitcher/proposals/` (54 files), so the code checks can be replayed without LLM time.

- **54 companies**: the 28 cohort and portfolio companies and the 26 Main-feed companies of the snapshot.
- **168 events passed the first check** (the page names the company and prints the date; 5 dropped as company not on page,
  2 fetch failures). **128 passed the second check** (fresh fetch; refuted: 25 type not in quote, 12 company not near quote,
  3 year not near quote). **29 emitted**; 99 confirmed events stay in `stitch_log` only because their type is not one the radar emits
  (incorporation 30, partnership 10, 40 other labels).
- **41 of 54 companies** have at least one confirmed event: cohort 17 of 19 (62 events), portfolio 8 of 9 (50), Main feed 16 of 26
  (16, nearly all register-directory incorporation lines).
- **Earliness, counted apart**: 1 of 19 cohort companies has an emittable confirmed event whose page the Internet Archive captured
  before 2026-01-01: VesselChain, a pilot with BMT, public since 2022-10-03. Counting unmapped labels would give 4; the rule forbids it.
- **Recall on the three companies with no proposals in the first run**: Sub Marine Store 0 to 3 proposed (2 confirmed), Taikoa 0 to 2
  (1 confirmed), Arctic Fry 0 to 2 (0 confirmed: both Nordic Blue entries were refuted because the quotes do not state the programme
  next to the company's name).
- **Intake thesis-evidence pass** on the top 100 wide-intake companies: 1 yes (Meriva Oy), 30 no, 69 unclear (nothing public describes
  the company's activity). Counted from the 100 committed records on `origin/cloud/stitcher` (commit 634f83c), which is not merged into
  main yet.
- **Live today**: the batch has been replayed into the live store (27 stitcher signals); `/backtest` reads "3 of 19 ... (19 of 19 have a
  stitcher run)". The live store holds 6 stitcher signals for Kelluu.
- **Limits of this run**: the cloud session could not reach web.archive.org's CDX index, so `public_since` came from the Wayback
  availability API; the web-search budget ran out mid-batch, so 21 companies were first researched by direct page fetches and the 13
  Main-feed ones among them got no second pass with search.

## Software checks

- `python3 -m pytest -q`: 397 passed in 29 s on 17 Oct, on main at 4080686.
- `/root/hack/bin/smoke.py https://jx.hankintaviikko.fi`: PASS 13/13 pages (the home page with and without the trailing slash,
  radar, backtest, method, data and seven feed filters), no console errors.
- Fresh clone, offline: `pip install -r requirements.txt`, `python3 -m radar.build --adapters declared,businessfinland,ecosystem`
  (3 s, 147 signals), then nine pages answered 200 from `uvicorn` on a spare port.

## Failure examples (real ones)

| Company | Expected | Got | Why |
|---|---|---|---|
| Arctic Fry Oy (3166759-6) | found before 2026: first sales 2020-10-05 and registration 2020-10-23 are in the store | later (2026-02-09, declared) | code 03220 freshwater aquaculture is not on the list (03210 marine is), "aqua" matches whole words only, and the registration is older than the 5-year cut |
| Emission-Eye Oy (3543918-7) | found before 2026: registered 2025-06-13, start-up notice 2025-07-02, first sales 2025-08-01 | later | code 62100 computer programming is not on the list and the name has no sector word |
| Taikoa Oy (3380111-1) | found: registered 2023-07-28, first sales the same day | no public signal | code 70200 management consulting; the company trades as WAIing, a link the declared list itself marks unconfirmed |
| Sub Marine Store Oy (3197621-7) | a hit for a sector reason | later (2026, year-only Business Finland record): the word "marin" in the name is backed only by a register record from the same PRH/YTJ family, which no longer counts | the code is 46900 non-specialised wholesale; the corroborating record is not an independent source |
| 12 non-Finnish companies | some live record | at most a CORDIS project (NIDO Contech, 2026-06-01) | no register adapter for Denmark, Sweden, Norway, Spain or Bulgaria |

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
- The health-tech thesis is a swap demo, not an evaluated thesis: its feed still lists clinics matched on "medical" in the line of
  business.
- No partner has yet scored the memos or the next steps; usefulness to Redstone Blue and A'Pelago is untested (PILOT.md, weeks 5 to 8).
