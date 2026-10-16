# Pitch, 3 minutes (Sunday 14:00, then questions)

Presenter: Dayo. One live demo moment: a judge names one of their own Nordic Blue companies, we type it into the search box, the four answers appear with a public record under each, then the earliness chart.

Spoken lines are in quote blocks. Everything else is a stage direction and is not said. The superscript numbers point to the source list at the end. Three numbers are still open and are written `<N1>`, `<N2>`, `<N3>`: read them off the live pages on Sunday, never from memory.

## Before you go on (Sunday, by 13:30)

- Fill `<N1>`, `<N2>` from https://jx.hankintaviikko.fi/backtest and `<N3>` from the footer of https://jx.hankintaviikko.fi/ (sources 3, 7, 8).
- Laptop: start page full screen, brightness at 100 percent, on power. Second tab ready on /backtest.
- Open any company page and look at sections 03 and 04. If they still say "not yet scored", use line 4B below, not 4A.
- Fallback company if no judge answers within three seconds: Emission-Eye (Nordic Blue cohort, Finnish, register entry 2025-06-13, source 13).
- If the network fails, switch to the screen recording on the phone (DEMO_SCRIPT.md, table checklist). Never say "it normally works".

## 0:00 to 0:15. The problem, in the brief's own words

On screen: the start page, heading "New this quarter" (slide 1 is the live app).

> Your brief asks for two things: find promising startups as early as possible, and turn fragmented startup and ecosystem data into decision-ready venture intelligence.

## 0:15 to 0:30. What we built

> So we built Ocean Opportunity Radar. It reads the trade register, public contracts, Business Finland and EU project records, and answers your four questions¹ about a company, with a public record under every line.

## 0:30 to 2:00. The demo (90 seconds)

On screen: the start page list. Point at the first rows.

> This is the start page: <N3>³ companies that appeared in public records in the last 90 days² and fit the blue-economy rules. Each line says why and links to the record.

Turn to the judges.

> You know your companies best. Name one from Nordic Blue.

Type the name into "Find a startup" and press "Find this startup". On screen: the company page. At the top: Y-tunnus, Founded, Industry, each with a small source chip.

> Business ID, founding date, industry, each with a small chip.

Tap the chip under Founded. The trade register record opens in a new tab. Hold it for two seconds, then close it.

> That chip opens the trade register record itself. Every fact on this page comes from a record like that.

Scroll to "01 Who is most promising".

> Now your four questions, in your order. One, who is most promising: the public records that tie it to the sector.

Scroll to "02 How ready are they".

> Two, how ready are they, on the frameworks you named: the KTH Business Readiness Level, the Aalto TRL, Investment Readiness across your ten Investment Potential dimensions⁴, and the Ocean Impact Navigator. A level appears only when a record backs it, with its rule underneath. Otherwise it says "no public evidence". We never fill a gap.

Scroll to 03 and 04. Say 4A or 4B, never both.

4A, when 03 and 04 show answers:

> Three, who comes next: [read the first row and its reason]. Four, what should happen next: [read the sentence and its "because"]. Each with its link.

4B, when 03 and 04 still say "not yet scored":

> Three and four are not switched on in this build. They answer only when a rule and a record support the answer.

Only if the company is outside Finland and the page is mostly hatched:

> This one is not Finnish. Our register sources cover Finland only, so the page says "not in public records" instead of guessing.

Tap "Earliness test" in the top menu. On screen: "Earliness test: would we have found them first?", one lane per company, a vertical line at the reference date.

> And this is the test we ran on ourselves: your 19 Nordic Blue companies⁵, one lane each. The dot is the first public record we hold; the line is January 2026⁶, the programme start month as we declared it, since entry dates are not public. We would have flagged <N1>⁷ of 19 before that line. <N2>⁸ have no public signal, and they stay blank.

Point at one hatched lane. If `<N1>` is 0 on Sunday, replace the last two sentences with: "On our own rule, we would have flagged none of the 19 before that line. That is the honest result, and it is why we are asking for your pipeline."

## 2:00 to 2:25. How it is different

> How is this different? Every line is a public record, dated and linkable. And earliness is measured on your own cohort, not claimed: signal vendors say they find companies months earlier, and we found no independent check⁹. I am a maritime engineer; I trust a measurement more than a claim.

## 2:25 to 2:45. What it does not do

> What it does not do: no score we cannot source. Five of your ten dimensions have no public source, so they always say "not in public records"¹⁰. LinkedIn, Dealroom, Crunchbase, PitchBook and Tracxn are connector slots, not connected. And it covers companies, never private people.

## 2:45 to 3:00. The ask

> Our ask: run it on your pipeline for a month¹¹. Note the date each company reaches you; at the end we show you, company by company, whether the radar saw it first. The sector lives in one file¹², so another sector is one file away. <N1> of 19, on your own cohort. Scan the code and try your own company.

## Sources for every number in the script

| # | Number as spoken | Value today (16 Oct, build 446e896) | Source | Changes by Sunday? |
|---|---|---|---|---|
| 1 | four questions | 4 | CLAUDE.md "What this product is"; live company page sections 01 to 04, e.g. https://jx.hankintaviikko.fi/c/2902007-2 | no |
| 2 | 90 days | 90 | /method "Feed window: 90 days"; config/thesis.yaml `feed_window_days: 90`; start page "Window: 2026-07-18 to 2026-10-16 (90 days)" | no |
| 3 | `<N3>` companies in the main list | 26 | start page footer "93 companies: 26 main matches and 67 weak matches, 94 signals in the window 2026-07-18 to 2026-10-16"; /method "Now: 26 companies in the main list" | yes: read "main matches" in the footer of https://jx.hankintaviikko.fi/ on Sunday; it moves with every data refresh and precision fix |
| 4 | ten Investment Potential dimensions | 10 | TASKS.md amendment 16.10 20:50Z; /method, Frameworks | no |
| 5 | 19 Nordic Blue companies | 19 | /backtest "All 19 companies"; data/declared/cohort_portfolio_companies.csv (19 rows in group cohort) | no |
| 6 | January 2026 | 2026-01-01 | /backtest "Reference date: 2026-01-01 (January 2026, the programme start month, declared by the team). Individual pipeline entry dates are not public" | only if data/declared/cohort_entry_dates.csv arrives; then rewrite that sentence |
| 7 | `<N1>` of 19 flagged before the line | 5 | /backtest headline "We would have flagged 5 of 19 before January 2026; 1 only after; 13 have no public signal at all." | yes, likely: JUDGE_REVIEW.md (branch cloud/judge_review), finding 1, shows the five are counted on register date alone and none of their industry codes is on the thesis list; if the backtest adopts the feed's thesis rule the number can fall, possibly to 0 (use the replacement line above) |
| 8 | `<N2>` with no public signal | 13 | same /backtest headline | yes: same page, same fix |
| 9 | "months earlier" (vendors, no number spoken) | none spoken | research/BENCHMARKS.md (branch cloud/benchmarks): Harmonic's own claim "6 to 12 months before they appear elsewhere", Specter's months-ahead stamp, and "I found no independent check of any of them" | no |
| 10 | five of the ten dimensions | 5 | /method "Five of them have no source in this radar and always show 'not in public records'"; radar/frameworks.py `DIM_SOURCES` (Product, Team, Business Model, Competition, Marketing & Distribution have none) | only if that code changes |
| 11 | a month | 1 month | the ask set in tasks/cloud/pitch.md; not a measured number. PILOT.md (8 weeks) is still a template: the chief aligns the two | if PILOT.md is filled |
| 12 | one file | 1 | /method "Everything sector-specific lives in one sector file"; config/thesis.yaml; header sector switch (health technology, Turku region) | no |
| 13 | Emission-Eye, register entry 2025-06-13 (stage note, not spoken unless typed) | 2025-06-13 | https://jx.hankintaviikko.fi/c/3543918-7 "Founded 2025-06-13", chip to PRH/YTJ | no |

Spoken length: 438 words on the main path (line 4A, without the non-Finnish line and without the row read aloud from section 03), about 3 minutes at a calm pace including the typing.
