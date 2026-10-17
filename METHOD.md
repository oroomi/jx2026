# Dated-event research method (the stitcher)

How `radar/adapters/stitcher.py` finds dated public events for one company. The rule throughout: an LLM proposes, plain code decides, and every decision is logged in `stitch_log` (`radar/schema/040_stitch_log.sql`).

## 1. Queries (search step)
They are built only from register facts already in the store. A personal name is never used.
- `"<legal name>"`, `"<business ID>"`, `"<FI VAT number>"`, `"<domain>"`, `site:<domain>`, `site:<domain> news OR press OR customers OR partners`
- `"<core name>" funding OR investment OR grant`, `"<core name>" pilot OR customer OR contract OR award`
- `"<core name>" EU project OR Horizon OR BlueInvest OR "Business Finland"`
- Finnish companies add `"<core name>" rahoitus OR asiakas OR pilotti OR palkinto OR kiihdyttämö OR sijoitus OR hanke`.
- **Other names of the company** (added 17 Oct for recall): every name the trade register holds for the business ID (PRH/YTJ open API: main, parallel, auxiliary and earlier names), and the name the declared cohort list uses. Each gets `"<name>"`, `"<name>" funding OR investment OR pilot OR customer OR award OR accelerator` and, for Finnish companies, the Finnish line. The prompt lists them as "Also known as". A name shaped like a private person's name is never used.
- When checking a page, a registered name names the company as strongly as the legal name (`registered_name`, high confidence with a day or month). A declared cohort name is `declared_name` (medium). A declared name that the list itself marks as an unconfirmed link (WAIing for Taikoa Oy) widens the search but never names the company on a page.
- The three companies with 0 proposals on 16 Oct trade under other names: Arctic Fry Oy is WESI Solutions (auxiliary name), Sub Marine Store Oy also holds Suomen Varavirta (auxiliary name), Taikoa Oy is behind WAIing (declared, unconfirmed). Each went from 8 to 13 queries.

The core name is the folded name without the legal form (`openalex.core_name`). Both our queries and the queries the LLM reports it ran are logged.

## 2. Sources trusted (read step)
`claude -p --model sonnet` with WebSearch and WebFetch gets the prompt from `build_prompt()`. Print it with `--print-prompt`. The rules it must follow:
- Every event carries the exact URL it opened, and that page must name the company and print the date.
- Preferred sources are the company's own site, press releases, EU sources (CORDIS, BlueInvest), Business Finland, patent offices and news.
- Refused, and also dropped by code: LinkedIn, Facebook, Instagram, X, Crunchbase, Dealroom, PitchBook, Tracxn, CB Insights, Nordic9.
- The quote is at most 20 verbatim words and names the company. A sentence that names a private person is never used. Code also redacts person-shaped names to `[name]`.
- The signal type must be one of the emittable types: the existing types in `radar/emit.py` that a web page can show, plus `programme_entry`, `award` and `funding_round` (the chief's decision on 17 Oct: the thesis feed already counts them; registered in the stitcher the way `ecosystem.py` registers its types). Anything else is `unmapped` plus a suggested label: it stays in `stitch_log` as `not_emitted` and is never a signal. A saved answer that says `unmapped` with one of the three as its label is read as that type.

The answer is cached under `data/cache/stitcher/llm/` by prompt hash. A saved answer can be replayed with `--proposals DIR`.

## 3. Dating (verify step, no LLM)
- The code fetches each URL itself: 1 request per 2 s, cached under `data/cache/stitcher/pages/`, PDFs read with pdftotext.
- **Kept only if** the page names the company and prints the date or its year. Naming means, strongest first: business ID or FI VAT number, then the legal name, then the core name as whole words, then the website domain.
- Dates are matched in ISO, Finnish `d.m.yyyy`, `d/m/yyyy`, and month names in English, Finnish, Swedish, Danish, German and Spanish, including Finnish inflections.
- The stored precision is what the page supports and never more than proposed. A day the page does not print becomes month or year, and the log says so.
- Stored dates: a month-only date is the last day of the month, as `ecosystem.py` does. A year-only date is 1 January with a `signal_meta` row of `year`.
- Confidence follows the rule in `emit.py`. It is high when the business ID or legal name and a day or month are on the page. Otherwise it is medium.
- **public_since** is the Internet Archive's first 200 capture of that exact URL, from CDX. It is the earliest day anyone could have read the event, and it is the honest number for earliness. When CDX cannot be reached, the Wayback availability API is asked for the capture closest to 1 January 1996, which is the earliest. It is used only when that capture is a 200.
- Drop reasons are `source_not_allowed`, `date_in_future`, `fetch_failed: …`, `company_not_on_page`, `date_not_on_page` and `name_and_date_not_on_page`.

## 3b. Adversarial second pass (recheck step, no LLM)
Every kept event is checked again before anything is emitted. The code fetches the page fresh (no cache) and confirms all of these; the first failure drops the event, logged as `verify` / `refuted` with its reason:
- `quote_not_on_page`: the quote is on the re-fetched page word for word (case, accents and punctuation folded). A redacted quote must have each unredacted fragment there, in order.
- `company_not_near_quote`: the company is named in the quote, or within 200 characters of it (business ID, legal name, core name or domain). On the company's own site, the site naming the company is enough.
- `type_not_in_quote`: the quote states an event of the proposed type: it holds one of that type's words (`TYPE_WORDS` in the stitcher, English and Finnish, for example award, prize, won, palkinto for `award`; raised, round, seed, series, invest for `funding_round`; a grant is not a round).
- `nomination_not_award`: a finalist, nomination or shortlist place without a win word is not an award.
- `year_not_near_quote`: a year-only date must be printed within 300 characters of the quote, so a copyright line never dates an event.
- `no_quote`, `refetch_failed: …`.
Passed events are logged `verify` / `confirmed` with what matched. An `unmapped` event is checked for quote and company only and is never emitted. A past run can be rechecked alone with `--recheck-run RUN_ID`. That logs under the old run and emits or removes nothing.

## 4. Emit
Only confirmed events are emitted. Writes go only through `radar.emit.emit_signal` with adapter `stitcher`. The verbatim quote goes into `signal_text` only when it appears word for word on the page and nothing was redacted. `build.py` does not run the stitcher because the module has no `run()`.

## Run (VPS, 16 Oct 23:06Z, live thesis store, Sonnet answers replayed from files)
`RESULT run 2026-10-16T23:06:54Z: 6 companies, 15 proposed, 14 kept, 1 dropped (date_not_on_page), 2 emitted, 12 not emitted (types not in SIGNAL_TYPES: programme_entry 2, award, funding_round, partnership, incorporation, crowdfunding_campaign, facility_expansion, first_international_client, research_collaboration, network_membership, supplier_selection), 8 kept events dated before the 2026-01-01 reference, 3 of them also archived before it, across 3 companies.`

Three companies got no proposals at all: Sub Marine Store, Taikoa and Arctic Fry.

## Batch run (cloud session, 17 Oct 00:18Z, snapshot store copy, answers in data/fetched/stitcher/proposals/)
54 companies: the 28 declared cohort and portfolio companies and every Main-feed company of `data/snapshot` (26, fewer than the 30 asked). The list is in `data/fetched/stitcher/batch.txt`. The LLM step ran in this session's own agents with the `--print-prompt` prompts; the VPS replays the saved answers with `--proposals`, so it spends no LLM time.
`RESULT run 2026-10-17T00:18:33Z: 54 companies, 175 proposed, 168 kept by the first check (dropped: company_not_on_page 5, fetch_failed 2), 128 confirmed by the second check (refuted: type_not_in_quote 25, company_not_near_quote 12, year_not_near_quote 3), 29 emitted, 99 kept in stitch_log only (incorporation 30, partnership 10, and 40 other labels).`
Per group: cohort 19 companies, 62 confirmed events, 17 with at least one, 12 emitted; portfolio 9 companies, 50 confirmed, 8 with at least one, 17 emitted; Main feed 26 companies, 16 confirmed, nearly all register-directory incorporation lines, 0 emitted.
Earliness (section 5): 1 of 19 cohort companies has an emittable event whose page was archived before 1 January 2026: VesselChain, a pilot with BMT, public since 2022-10-03. With unmapped labels counted it would be 4; they are not, by rule. Against the same reference date, 3 of 9 portfolio companies would count (Kelluu, Redkik, Tethys Robotics).
Recall for the three with no proposals on 16 Oct: Sub Marine Store 0 to 3 proposed, 2 confirmed; Taikoa 0 to 2 proposed, 1 confirmed; Arctic Fry 0 to 2 proposed, 0 confirmed (both Nordic Blue entries were refuted: the quotes do not state the programme next to the company's name).

## 5. Earliness: counted apart
Stitcher signals never count in the backtest's four groups (live public records, declared research, later, none). `/backtest` lists them under the company as "found by the AI stitcher: never in the live count", and prints one separate line. That line counts cohort companies whose latest stitcher run has an event of an emittable type (an unmapped label such as an incorporation line never counts) that passed both code checks and whose page the Internet Archive captured strictly before the company's reference date. The archive date (`public_since`) counts, never the event date. `radar.adapters.stitcher.archived_before`, called from `radar/earliness.py`, returned as `stitcher` in the backtest result.

## 6. Intake thesis-evidence pass (`--intake-fit`, files only, emits nothing)
For the wide-intake list `tasks/cloud/intake_top100.tsv` (company_key TAB name; these companies are not in the store), the stitcher asks one question per company: is there public evidence that the company itself works in the thesis themes? Register facts come from PRH (website, line of business, other registered names). The LLM answers yes, no or unclear with a quote and a link, at most two searches, and never searches people. Code decides the label:
- **yes** only when the freshly fetched page names the company, holds the quote word for word, and the quote holds a thesis word that is not part of the company's own names. Thesis words come from configuration only: the thesis name keywords, its Hilma keywords and the impact-category words in `config/frameworks.yaml`.
- **no** only when the page names the company and holds the quote.
- Everything else is **unclear**, with the reason.
The checked record per company is `data/fetched/stitcher/intake_fit/<company_key>.json` (company_key, name, thesis_evidence, quote, source_url, public_since, archive_url, thesis_word, checked, llm_answer); the LLM's own answer is kept inside each record (`llm_answer`, with the quote and link when they passed the check), so the repo holds one copy per company. Re-check on the VPS with `python3 -m radar.adapters.stitcher --intake-fit tasks/cloud/intake_top100.tsv` (it reads the answer back from the record; `--proposals DIR` points it at raw answer files instead).

Run 17 Oct (cloud session): 1 yes, 30 no, 69 unclear. The LLM said yes 1, no 34, unclear 65. Code turned 4 of its "no" answers into unclear: three pages name only a brand or a parent group, not the Oy, and one quote was not on the re-fetched page. The yes is Meriva Oy (3652359-1): "Meriva Oy provides independent, expert, and practical-experience-based consulting services for aquaculture companies, investors, and authorities." (https://meriva.fi/services/). The page is not in the Internet Archive via the availability API, so public_since is empty; CDX on the VPS may differ. Most of the 100 were registered weeks ago and have no public description yet, so unclear is the honest majority.

## 7. Ocean Impact Readiness: evidence readiness, not true impact (D22)

The Ocean Impact Assessment on each company page (`radar/ocean_impact.py`, ladder and area table in `impact_readiness` of the thesis files) measures how well a company's ocean impact area is evidenced in public records. It does not measure how much impact the company has. The Ocean Impact Navigator publishes impact areas and KPIs but no levels, and the repo holds no sponsor definition of levels, so the nine rungs are ours and each names the record that must be on file: 1 to 2 the trade register's industry-code family, registered line of business or a corroborated name word point to an area (sector implied only); 3 to 4 the source's own text (a notice title, a project text, an investor-pipeline profile) holds an area word; 5 to 6 a second independent source family names the area and a blue programme or portfolio page lists the company; 7 to 8 declared research holds an impact assessment or a quantified outcome with a stated method, counted only at the dataset's own confidence medium or high; 9 a measured outcome from an official or register source, which no connected source holds yet. The highest rung that passes wins, a company with no record naming an area has no level, and confidence is high when two or more independent source families agree, medium for one family that is more than the sector implied, low otherwise.
