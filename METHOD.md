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

## 5. Earliness: counted apart
Stitcher signals never count in the backtest's four groups (live public records, declared research, later, none). `/backtest` lists them under the company as "found by the AI stitcher: never in the live count", and prints one separate line. That line counts cohort companies whose latest stitcher run has an event that passed both code checks and whose page the Internet Archive captured strictly before the company's reference date. The archive date (`public_since`) counts, never the event date. `radar.adapters.stitcher.archived_before`, called from `radar/earliness.py`, returned as `stitcher` in the backtest result.
