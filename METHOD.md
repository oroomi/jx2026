# Dated-event research method (the stitcher)

How `radar/adapters/stitcher.py` finds dated public events for one company. The rule throughout: an LLM proposes, plain code decides, and every decision is logged in `stitch_log` (`radar/schema/040_stitch_log.sql`).

## 1. Queries (search step)
They are built only from register facts already in the store. A personal name is never used.
- `"<legal name>"`, `"<business ID>"`, `"<domain>"`, `site:<domain> news OR press OR customers OR partners`
- `"<core name>" funding OR investment OR grant`, `"<core name>" pilot OR customer OR contract OR award`
- `"<core name>" EU project OR Horizon OR BlueInvest OR "Business Finland"`
- Finnish companies add `"<core name>" rahoitus OR asiakas OR pilotti OR palkinto`.

The core name is the folded name without the legal form (`openalex.core_name`). Both our queries and the queries the LLM reports it ran are logged.

## 2. Sources trusted (read step)
`claude -p --model sonnet` with WebSearch and WebFetch gets the prompt from `build_prompt()`. Print it with `--print-prompt`. The rules it must follow:
- Every event carries the exact URL it opened, and that page must name the company and print the date.
- Preferred sources are the company's own site, press releases, EU sources (CORDIS, BlueInvest), Business Finland, patent offices and news.
- Refused, and also dropped by code: LinkedIn, Facebook, Instagram, X, Crunchbase, Dealroom, PitchBook, Tracxn, CB Insights, Nordic9.
- The quote is at most 20 verbatim words and names the company. A sentence that names a private person is never used. Code also redacts person-shaped names to `[name]`.
- The signal type must be one of the existing types in `radar/emit.py`. Anything else is `unmapped` plus a suggested label, which is reported and never added.

The answer is cached under `data/cache/stitcher/llm/` by prompt hash. A saved answer can be replayed with `--proposals DIR`.

## 3. Dating (verify step, no LLM)
- The code fetches each URL itself: 1 request per 2 s, cached under `data/cache/stitcher/pages/`, PDFs read with pdftotext.
- **Kept only if** the page names the company and prints the date or its year. Naming means, strongest first: business ID or FI VAT number, then the legal name, then the core name as whole words, then the website domain.
- Dates are matched in ISO, Finnish `d.m.yyyy`, `d/m/yyyy`, and month names in English, Finnish, Swedish, Danish, German and Spanish, including Finnish inflections.
- The stored precision is what the page supports and never more than proposed. A day the page does not print becomes month or year, and the log says so.
- Stored dates: a month-only date is the last day of the month, as `ecosystem.py` does. A year-only date is 1 January with a `signal_meta` row of `year`.
- Confidence follows the rule in `emit.py`. It is high when the business ID or legal name and a day or month are on the page. Otherwise it is medium.
- **public_since** is the Internet Archive's first 200 capture of that exact URL, from CDX. It is the earliest day anyone could have read the event, and it is the honest number for earliness.
- Drop reasons are `source_not_allowed`, `date_in_future`, `fetch_failed: …`, `company_not_on_page`, `date_not_on_page` and `name_and_date_not_on_page`.

## 4. Emit
Writes go only through `radar.emit.emit_signal` with adapter `stitcher`. The verbatim quote goes into `signal_text` only when it appears word for word on the page and nothing was redacted. `build.py` does not run the stitcher because the module has no `run()`.

## Run (VPS, 16 Oct 23:06Z, live thesis store, Sonnet answers replayed from files)
`RESULT run 2026-10-16T23:06:54Z: 6 companies, 15 proposed, 14 kept, 1 dropped (date_not_on_page), 2 emitted, 12 not emitted (types not in SIGNAL_TYPES: programme_entry 2, award, funding_round, partnership, incorporation, crowdfunding_campaign, facility_expansion, first_international_client, research_collaboration, network_membership, supplier_selection), 8 kept events dated before the 2026-01-01 reference, 3 of them also archived before it, across 3 companies.`

Three companies got no proposals at all: Sub Marine Store, Taikoa and Arctic Fry.
