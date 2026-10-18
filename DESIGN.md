# Design (decided before the first screen; source: docs/DESIGN_DIRECTIONS_RECON.md, direction 1 "Receipts")

## Three references
1. https://ourworldindata.org : a source line under every figure. We take the footer-per-claim habit.
2. https://www.perplexity.ai : numbered citation chips that open the source. We take the chip and the drawer.
3. https://stripe.com/docs : hairline rules, tabular numerals, quiet density. We take the rhythm.
Supporting component (from direction 2, no extra cost): the readiness ladder for section 02, one definition per level (NASA TRL wording for 1 to 9). Supporting view (direction 3): the 19-row radar table, rows visible without scrolling, tap opens the company page.

## Direction (one)
Evidence first: an evidence chip under every number (source, date fetched, link), a printed rule next to every level or score, and a hatched chip "not in public records" where there is nothing. A fund associate on a phone in a dark expo hall must be able to check any claim in one tap.

## Tokens
Colours follow the pitch deck's "Electric Ocean" palette (D92, 18 Oct; it replaced the first dark-teal and warm-paper sets) and live only as CSS custom properties: editorial dark in skins.css, editorial light in site.css, the skinless base in app.css. Dark (default): page #021B44, surface #023E8A, hairline #2E6BB8, text #F6FDFF (16.4:1), muted #CDEBFF (13.6:1), accent #00E5D4 (10.6:1, hover #00C2FF), primary buttons #00E5D4 with #021B44 text. Light: page #F6FDFF, surface #FBFEFF, hairline #9FD9F2, text #0A1F3D (16.0:1), muted #33507A (7.9:1), accent #005FCC (5.8:1, hover #023E8A), primary buttons ink. The dark theme is the default, light comes through the "Light or dark" toggle, stored in localStorage inside try/catch. One accent only; the verdict colours are the one exception and each holds 4.5:1 on its surface. Missing data uses a diagonal hatch of the hairline colour, never a lighter version of a real value. A few line icons (radar/templates/_icons.html) sit beside words, never alone.

## Rules
- Type: Newsreader (headings and the 22 px answer sentences) + IBM Plex Sans (body, chips, tabular figures via `font-variant-numeric: tabular-nums`). Self-hosted woff2 in radar/static/fonts (fetched from the @fontsource packages at build time, licence SIL OFL, declared in DISCLOSURE.md); `font-display: swap`; no Google Fonts request at runtime, hall wifi must not break type. This overrides the system-font default at the founder's request.
- Layout: 390 px first. Single column, 16 px gutters, 8 px scale, body 16 px minimum, tap targets 44 px. At 1440 px: left rail 240 px with four anchors, centre column 720 px, right drawer 360 px showing the filing for the fact in focus.
- Every number carries a chip. Every score or level shows its rule in one line under it. A level with no evidence reads "no public evidence" and renders as the hatched state.
- Real data on every screen. Empty state says "no signals yet for <x>" or "not in public records". No lorem, no placeholder avatars, no emoji, sentence case, no exclamation marks, no em dashes.
- Connector slots (LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn) are drawn as a plain disabled row labelled "connector slot, not connected", never as data.
- Motion: none except loading indicators. No animated counters. No gradient hero. No four identical cards in a row: the four questions are four numbered sections in the partner's words with different content shapes.
- Colour is never the only signal: arrows or words accompany any up, down or dark state.

## Screens
| Screen | Route | Purpose | Reference used |
|---|---|---|---|
| Early-signal feed | / | Companies that surfaced in the last 90 days, newest first; row = company, signal, date, chip | Perplexity chips, Stripe rhythm |
| Company page | /c/{key} | The four questions with sourced facts and levels; sticky bottom bar "Radar of 19" on mobile | Our World in Data footers, readiness ladder |
| Cohort radar | /radar | 19 cohort + 9 portfolio, earliness backtest chart, rows open the company page | Direction 3 table |
| Method | /method | Rules printed in full: confidence, readiness, matching, next step; declared datasets | Stripe docs |

## Review loop
Every task ends with shot.py desktop + mobile, and the builder reads both PNGs against these rules and the slop list in CLAUDE.md. Dayo confirms the direction once (STATUS.md, Dayo action 2); until then it is final by default.
