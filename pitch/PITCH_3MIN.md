# Pitch, 3 minutes (Sunday 14:00, then questions)

Presenter: Dayo. One live demo moment: a judge names one of their own Nordic Blue companies, we type it into the search box, the four answers appear with a public record under each, then the earliness chart.

The pitch does not claim that we would have found the cohort first. Our own test says the cohort was invisible to public registers until after it was picked; the radar's job is the companies that are visible now, each with a dated public record.

Spoken lines are in quote blocks. Everything else is a stage direction and is not said. The superscript numbers point to the source list at the end. Four numbers are still open and are written `<N1>`, `<N2>`, `<N3>`, `<N4>`: read them off the live pages on Sunday, never from memory.

## Before you go on (Sunday, by 13:30)

- Fill `<N1>`, `<N2>` from https://jx.hankintaviikko.fi/backtest and `<N3>` from the footer of https://jx.hankintaviikko.fi/ (sources 3, 7, 8). Declared-research events are being imported, so the /backtest numbers can still move.
- Fill `<N4>` from the tax-register row of the Sources table on https://jx.hankintaviikko.fi/method (source 14); the chief sets the final count at deploy.
- If `<N1>` is above 0 on Sunday, the "invisible" sentence in the earliness part is no longer true: use the replacement line given there.
- Laptop: start page full screen, brightness at 100 percent, on power. Second tab ready on /backtest. Selection in the header: "Blue economy, Finland and Nordics".
- Open any company page and look at sections 03 and 04. If they still say "not yet scored", use line 4B below, not 4A.
- Fallback company if no judge answers within three seconds: Emission-Eye (Nordic Blue cohort, Finnish, register entry 2025-06-13, source 13).
- If the network fails, switch to the screen recording on the phone (DEMO_SCRIPT.md, table checklist). Never say "it normally works".

## 0:00 to 0:15. The problem, in the brief's own words

On screen: the start page, heading "New this quarter" (slide 1 is the live app).

> Your brief asks for two things: find promising startups as early as possible, and turn fragmented startup and ecosystem data into decision-ready venture intelligence.

## 0:15 to 0:30. What we built

> So we built Ocean Opportunity Radar. It reads public registers, contracts, grants and EU projects, and answers your four questions¹ about a company, with a public record under every line.

## 0:30 to 2:00. The demo (90 seconds)

On screen: the start page list. Point at the first rows.

> This is the start page: <N3>³ companies that appeared in public records in the last 90 days² and fit the blue-economy rules. Each line says why, with a link.

Turn to the judges.

> Name one of your Nordic Blue companies.

Type the name into "Find a startup" and press "Find this startup". On screen: the company page. At the top: Y-tunnus, Founded, Industry, each with a small source chip.

> Business ID, founding date, industry, each with a chip.

Tap the chip under Founded. The trade register record opens in a new tab. Hold it for two seconds, then close it.

> That chip opens the trade register record itself. Every fact here comes from a record like that.

Point at the "Life-line" block under the register facts: Formation, First money, First team, Validation. If this company's first-sales or first-hire row is hatched, point at the row anyway: the sentence explains what a date there would mean.

> Below, its life-line. First sales is the day it first registered for VAT; first hire, the day it first registered as an employer: exact dates from the national tax registers, <N4>¹⁴ of them in the radar.

Scroll to "01 Who is most promising".

> Now your four questions, in your order. One, who is most promising: the public records that tie it to the sector.

Scroll to "02 How ready are they".

> Two, how ready are they, on your frameworks: KTH Business Readiness Level, Aalto TRL, Investment Readiness across your ten Investment Potential dimensions⁴, and the Ocean Impact Navigator. A level appears only when a record backs it, with its rule underneath. Otherwise it says "no public evidence". We never fill a gap.

Scroll to 03 and 04. Say 4A or 4B, never both.

4A, when 03 and 04 show answers:

> Three, who comes next: [read the first row and its reason]. Four, what should happen next: [read the sentence and its "because"]. Each with its link.

4B, when 03 and 04 still say "not yet scored":

> Three and four are not switched on in this build. They answer only when a rule and a record support the answer.

Only if the company is outside Finland and the page is mostly hatched:

> This one is not Finnish. Our register depth is Finland and Estonia, so the page says "not in public records" instead of guessing.

Tap "Earliness test" in the top menu. On screen: "Earliness test: would we have found them first?", one lane per company, a vertical line at the reference date, most lanes hatched.

> This is the test we ran on ourselves: your 19 Nordic Blue companies⁵ against January 2026⁶, the programme start month as we declared it. On its own feed rule, the radar would have shown <N1>⁷ of them before that line; <N2>⁸ have no public signal. Your cohort was invisible to public registers until after you picked them. This radar shows the companies that are visible now, each with a dated public record.

Point at one hatched lane. If `<N1>` is above 0 on Sunday, replace "Your cohort was invisible to public registers until after you picked them." with "<N1> of them were visible in public registers before you picked them."

## 2:00 to 2:25. How it is different

> How is this different? Every line is a public record, dated and linkable. And we measured ourselves on your cohort instead of claiming earliness: vendors say they find companies months earlier; we found no independent check⁹. I am a maritime engineer; I trust a measurement over a claim, even an unflattering one.

## 2:25 to 2:45. What it does not do

> What it does not do: no score we cannot source. Five of your ten dimensions have no public source, so they say "not in public records"¹⁰. LinkedIn, Dealroom, Crunchbase, PitchBook and Tracxn are connector slots, not connected. And it covers companies, never private people.

## 2:45 to 3:00. The ask

> Our ask: run it on your pipeline for a month¹¹. Note the date each company reaches you; we show what the public record held that day. Sector and region live in one file; the Baltic switch loads eight countries¹². Right now <N3> are visible. Scan the code and try your own company.

## Sources for every number in the script

Values today are from the live site on 16 Oct 2026, 22:27Z, build c13bf41.

| # | Number as spoken | Value today | Source | Changes by Sunday? |
|---|---|---|---|---|
| 1 | four questions | 4 | CLAUDE.md "What this product is"; live company page sections 01 to 04, e.g. https://jx.hankintaviikko.fi/c/2902007-2 | no |
| 2 | 90 days | 90 | /method "Feed window: 90 days"; config/thesis.yaml `feed_window_days: 90`; start page "Window: 2026-07-18 to 2026-10-16 (90 days)" | no |
| 3 | `<N3>` companies in the main list (said twice) | 57 | start page footer "94 companies: 57 main matches and 37 weak matches, 95 signals in the window 2026-07-18 to 2026-10-16" | yes: read "main matches" in the footer of https://jx.hankintaviikko.fi/ on Sunday, with the Finland and Nordics selection; it moved from 26 to 57 on 16 Oct as register notices landed |
| 4 | ten Investment Potential dimensions | 10 | TASKS.md amendment 16.10 20:50Z; /method, Frameworks | no |
| 5 | 19 Nordic Blue companies | 19 | /backtest "Of 19 cohort companies"; data/declared/cohort_portfolio_companies.csv (19 rows in group cohort) | no |
| 6 | January 2026 | 2026-01-01 | /backtest "Reference date: 2026-01-01 (January 2026, the programme start month, declared by the team). Individual pipeline entry dates are not public" | only if data/declared/cohort_entry_dates.csv arrives; then rewrite that sentence |
| 7 | `<N1>` shown before the line by the radar's own feed rule | 0 | /backtest headline "Of 19 cohort companies, the radar, applying its own feed rule, would have shown 0 before January 2026 using live public records. Declared research alone finds 0 earlier; 1 are found only after; 18 have no public signal." Use the "live public records" number, not the declared-research one | yes, possibly: declared-research events are being imported tonight (chief, 22:40Z); read the headline on https://jx.hankintaviikko.fi/backtest |
| 8 | `<N2>` with no public signal | 18 | same /backtest headline | yes, possibly: same page, same import |
| 9 | "months earlier" (vendors, no number spoken) | none spoken | research/BENCHMARKS.md (branch cloud/benchmarks): Harmonic's own claim "6 to 12 months before they appear elsewhere", Specter's months-ahead stamp, and "I found no independent check of any of them" | no |
| 10 | five of the ten dimensions | 5 | /method "Five of them have no source in this radar and always show 'not in public records'"; radar/frameworks.py `DIM_SOURCES` (Product, Team, Business Model, Competition, Marketing & Distribution have none) | only if that code changes |
| 11 | a month | 1 month | the ask set in tasks/cloud/pitch.md; not a measured number. PILOT.md (8 weeks) is still a template: the chief aligns the two | if PILOT.md is filled |
| 12 | one file; eight countries | 1; 8 | /method "lives in one sector file"; https://jx.hankintaviikko.fi/method?thesis=baltic_blue "Countries: FI, SE, EE, LV, LT, DK, DE, PL" and "National register depth exists only where we built it: Finland (PRH, Hilma) and Estonia (e-Business Register)"; config/thesis_baltic_blue.yaml on main | no |
| 13 | Emission-Eye, register entry 2025-06-13 (stage note, not spoken unless typed) | 2025-06-13 | https://jx.hankintaviikko.fi/c/3543918-7 "Founded 2025-06-13", chip to PRH/YTJ | no |
| 14 | `<N4>` tax-register dates in the radar | not on the live site yet | /method Sources table, tax-register row ("PRH/YTJ tax registers"; on c13bf41 it read "not loaded in this build"). Chief, 22:45Z: the adapter ran on a copy of the store with 1,068 first-traction signals across 717 companies (first sales and first hire with exact dates, plus sales ended and employer ended as negatives); it goes live with the 03/04 merge and the final number is set at deploy | yes: read the /method row on Sunday and quote that number, not the 22:45Z one |

The sentence "Your cohort was invisible to public registers until after you picked them; this radar shows the companies that are visible now, each with a dated public record" is the chief's wording (message of 16 Oct, 22:40Z). It holds only while `<N1>` is 0.

The life-line rows mean, in plain words: first sales is the day a company first registered for VAT, first hire is the day it first registered as an employer, both exact dates from the national tax registers (PRH/YTJ open data; research/CREATIVE_SIGNALS.md section 7). "Sales ended" and "employer ended" are the same registers closing, shown as negatives. The registers say a company is selling or paying someone, never how much. Wording and loading per the chief's message of 16 Oct, 22:45Z.

Spoken length: 459 words on the main path (line 4A, without the non-Finnish line and without the row read aloud from section 03), about 3 minutes at a calm pace including the typing.
