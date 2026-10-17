# Phase 4: three skins on the approved layout

Switch with `?skin=terminal|editorial|product` on "/" and on any company page (`/c/{key}`). The choice is remembered in localStorage. It replaces the earlier `?accent=` switch. Without a choice the page uses **product**.
The layout, every number, every link and every test are unchanged. A skin is CSS (`radar/static/skins.css`) plus a few skin-only hooks in `feed.html` and `company.html` that the other skins hide. The skin script and behaviours are in `radar/templates/_skin_head.html`, and the fonts are vendored (IBM Plex Mono added, SIL OFL).

## terminal
- **What it is:** a Bloomberg Terminal reinterpreted by Linear and Raycast. IBM Plex Mono with tabular numerals, hairline rules, dense 56 px rows, square marks, and one amber phosphor accent (#FFB000). A thin LIVE status line runs under the headline (store date, rows, window). Verdicts are bracketed text, `[ACCELERATOR]`. Keyboard hints on laptops: `/` search, `1`-`n` groups, `j`/`k` rows, Enter to open.
- **Signature:** the sparkline becomes a 12-month tape. Each dated public record is a tick on a hairline, and the latest tick is tall and amber.
- **Borrowed from:** Bloomberg (density, amber on black, bracketed status), Linear (hairlines, restraint, keyboard first), Raycast (kbd hints, command feel).

## editorial
- **What it is:** FT Visual Vocabulary, The Pudding and Bloomberg Businessweek on warm near-black paper (#15130F). Newsreader display at 48 and 32, Plex for numbers, ruled lines instead of cards, and a source line under the headline number. Verdicts are small-caps labels with a thin coloured rule. Rows drop the mark and set the name in the serif.
- **Signature:** the company page opens with the memo verdict as a headline sentence ("Viva Jets Oy reads *accelerator*: no measured impact on record.") with its one evidence link under it. The home number counts up once from 0 in 560 ms. This is off under reduced motion, and the real number is in the HTML.
- **Borrowed from:** FT (source line under every number, ruled sections, salmon accent on dark), The Pudding (one big number with a sentence beside it), Businessweek (serif headline voice, small-caps labels).

## product
- **What it is:** Stripe, Mercury, Robinhood and Trading 212. Layered dark surfaces with 1 px borders and a soft inner glow, 12 px radii, rounded pills, and gradient only as light at the top of the page. Hover lift and press states at 150 ms. Skeleton shimmer rows clear in sequence on load, and are off under reduced motion.
- **Signature:** the round company mark carries a thin ring filled to the share of the six public-record checks covered, the same six the company page counts. The verdict uses a seven-hue scale, one hue per verdict, used nowhere else: Invest green, Due diligence lime, Accelerator amber, Partner introduction pink, Grant support violet, Watchlist grey, Reject red.
- **Borrowed from:** Stripe (layering, glow, gradient as light), Mercury (calm neutral surfaces, white primary button), Robinhood and Trading 212 (rounded rows, the signal-and-pill row pattern, colour as status only).

## Ranking
1. **editorial:** the most distinctive at a hackathon and the most on-brand for an evidence product. The verdict-as-headline-sentence with its evidence link is the clearest "judgement plus receipt" moment, and partners aged 40 to 60 read serif headlines and ruled pages easily.
2. **product:** the most polished and familiar, and the check ring explains coverage at a glance. Most at risk of looking like every fintech app.
3. **terminal:** the strongest character and the best density for power users, but mono at phone size costs readability for the QR-code audience.

## References
Linear, Raycast, Stripe, Mercury, The Pudding and the FT Visual Vocabulary were reachable by HTTP from the build container. The headless browser here rejects the environment's TLS proxy certificate, though, so reference screenshots could not be captured into `docs/design_v2/refs/`. That needs a browser that trusts the proxy, or screenshots from Dayo. Bloomberg's terminal page returned 403.

## Lifeline (folded into editorial only)
The concept session's lifeline is in **editorial** only, because it suits that skin's calm, ruled pages best. On a company page it is a full-width strip under the header: every dated public record is a dot on one time axis from the first record to today, with year ticks only and the latest record larger in the accent. A dashed cohort-entry marker is drawn when `data/declared/cohort_entry_dates.csv` has the company (that file is absent today, so none shows). Home rows in editorial draw the same dots in place of the sparkline, so the mark is one identity across both pages. There is no motion, no axes beyond year ticks, and no chart chips. Terminal keeps its tape and product keeps its sparkline.
