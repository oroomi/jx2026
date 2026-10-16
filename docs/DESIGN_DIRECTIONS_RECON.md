# Design directions: Redstone x A'Pelago company page (JunctionX Turku, 16 Oct 2026)

Product: one-screen company page answering the four partner questions with sourced facts and readiness levels, plus a radar of 19 startups. Judged on a judge's phone, first 20 seconds, dark expo hall. All text contrast checked (WCAG ratio in brackets). Pick one by number.

---

## 1. Receipts (evidence first)

**References**
- https://ourworldindata.org : source line under every figure. Borrow the footer-per-claim habit.
- https://www.perplexity.ai : numbered citation chips; tap opens the source. Borrow chip and drawer.
- https://stripe.com/docs : hairline rules, tabular numerals. Borrow the quiet density.

**System.** Newsreader (headings, answer sentences) + IBM Plex Sans (body, chips, tabular figures).
Dark: bg #0B0F14, surface #121820, text #E8EDF2 (16.3), muted #9AA7B4 (7.8), accent #4FD1B5 (10.2).
Light: bg #F6F4EF, text #14181D (16.2), muted #5A6470 (5.5), accent #0B6B5C (5.8).

**390 px.** Name, one-line thesis fit. Four numbered sections in the partner's words, each opening with a 22 px serif answer, then fact rows with chips. Sticky bottom bar: "Radar of 19".
**1440 px.** Left rail 240 px, four anchors. Centre 720 px. Right 360 px drawer showing the filing for the fact in focus.

**Signature:** an evidence chip under every number (source, date fetched, link). Missing data gets a hatched chip "not in public records".

**Must not:** gradient hero, emoji icons, placeholder charts, lorem, a score without its printed rule, animated counters.

---

## 2. Ladder (readiness first)

**References**
- https://www.nasa.gov/directorates/somd/space-communications-navigation-program/technology-readiness-levels/ : canonical 1 to 9 TRL. Borrow one definition per level.
- https://linear.app : dense rows, status glyphs. Borrow density and glyphs.
- https://www.datawrapper.de : direct-labelled charts, no legends. Borrow direct labelling.

**System.** Schibsted Grotesk + Geist Mono (levels, dates).
Dark: bg #0C1014, rail-off #2A333D, text #EDEFF2 (16.6), muted #A3AEB9 (8.5), accent amber #F2B134 (10.1).
Light: bg #FAF8F3, text #15181C (16.8), muted #5B6068 (6.0), accent #8A5A00 (5.6).

**390 px.** Name, one-sentence thesis fit, then four stacked rails (Technology 1-9, Business 1-5, Investment 1-9, Ocean impact 1-5) filled to level, step named in words. Tap a rail: rule and evidence open under it. Questions 03 and 04 follow.
**1440 px.** Left 320 px company column. Centre: rails as one nine-column table. Right: who comes next, next step.

**Signature:** the readiness ladder; "no public evidence" renders as an empty hatched rail, never a guess.

**Must not:** rainbow level colours, gauges, emoji, a level without linked facts, four identical cards.

---

## 3. Tape (radar first)

**References**
- https://www.koyfin.com : sortable watchlist with inline sparklines. Borrow the row anatomy.
- https://finviz.com : screener density, every row visible at once. Borrow the no-scroll 19-row table.
- https://linear.app : keyboard-free list, detail opens in a side sheet. Borrow list-to-sheet.

**System.** Barlow Semi Condensed + Fragment Mono (figures).
Dark: bg #07090C, row #0E1217, text #E6EAEE (16.5), muted #98A3AE (7.8), up #3DDC97 (11.3), dark-signal #FF8A7A (8.7).
Light: bg #F3F5F7, text #11161B (16.6), muted #566170 (5.8), up #0A7A4B (4.9), dark-signal #B2361F (5.6).

**390 px.** Header: "19 companies, ranked by dated public events, last 12 months" with the rule printed under it. Rows: rank, name, 96 px sparkline, count, four level ticks. Tap opens the company page as a full sheet.
**1440 px.** Table left 880 px, all 19 rows visible. Company page pinned right 480 px, updates on row hover.

**Signature:** a momentum sparkline whose ticks are individual filings; tap a tick, see its source.

**Must not:** green/red as the only signal (add arrow glyphs), fake ticker motion, invented trend lines, gradient fills, emoji.

---

## Recommendation

Pick 1 (Receipts). The biggest loss in the brief is one unverifiable fact about a real startup in front of its investor, and an evidence chip under every number shows the answer to that on the phone within seconds. The ladder from 2 drops in as the component for section 02 at no extra design cost, and the radar from 3 stays the second screen.

## Build notes
- DESIGN.md and the hack-design skill say system fonts and no motion; this file overrides the font rule at the founder's request. Self-host via @fontsource (as in the 3D recipe) so hall wifi cannot break type.
- Dark default, light via prefers-color-scheme plus a toggle; body 16 px minimum, tap targets 44 px.
- Two typefaces per direction, one accent, 8 px scale, 16 px gutters.
