# Design v2 "Dossier": phase 1 prototype

Two self-contained static pages and a proposed design system, built for review before any app template is touched.

| File | What it is |
|---|---|
| `home.html` | Front page: headline number, weekly arrivals chart, the feed as an editorial index |
| `company.html` | Dossier for Viva Jets Oy (2962040-6, portfolio, electric watercraft): verdict, four levels, AI box slot, life-line chart, questions 01 to 04 |
| `tokens.css` | Design system: type scale, colour tokens (dark default, light), chips, pills, tabs, chart conventions, motion |
| `src/*.src.html` | Page sources; `__DATA__` is replaced with JSON at build time |
| `build.py` | Embeds real data: calls the app's own `/api/feed` and `/api/company/{key}` through FastAPI's TestClient against `data/snapshot` |
| `shoot.py` | Playwright screenshots at 1440x900 and 390x844, dark and light, full page plus fold, into `shots/` |

Rebuild and re-shoot: `python3 docs/design_v2/build.py && python3 docs/design_v2/shoot.py`.
Open the pages straight from disk. Fonts load from `radar/static/fonts`, so nothing is fetched from a CDN.

## What each reference contributed
1. **Linear (product frame).** Dark layered surfaces (`--bg`, `--bg-raised`, `--surface`) separated by 1 px hairlines rather than shadows. A sticky translucent header with a command-bar search (`/` focuses it). Quiet tabs with a 2 px accent underline. 150 ms hover states.
2. **Stripe (depth and type).** Soft two-layer shadows on raised cards, generous whitespace, and gradient used only as light: the faint teal glow in the corner of the AI box, nowhere else.
3. **FT Visual Vocabulary, FT and Bloomberg graphics.** Every chart opens with a headline sentence that states the finding ("20 of the 26 arrived before the end of August", "EUR 3.19 million of public funding on record across 6 decisions since 2018"). Labels sit directly on the marks, with no legends. One annotation marks the point that matters (the peak week, the largest decision). A source line runs underneath.
4. **The Pudding (restraint).** One idea per screen: a very large number with its sentence set beside it. Section numbers 01 to 04 are set large in the accent colour, the question in serif, and the rule in small muted type.

## Type and colour
- Newsreader for headlines, answer sentences and big numbers. IBM Plex Sans for UI, using tabular figures wherever numbers sit in columns. Scale: 12 / 14 / 16 / 18 / 22 / 32 / 48 / 72.
- One accent (sea teal: `#4FD1B5` dark, `#0B6B5C` light) plus neutrals. Status colours appear only in the verdict pill.
- Missing data is always the hatched chip or row ("not in public records", "No public evidence"), never a placeholder that looks real.

## Data honesty notes
- Every number on both pages comes from the snapshot through the app's API. Nothing is typed by hand.
- **The verdict pill is the next-step rule from the decision table** (1 Apply now, 2 Contact buyer, 3 Raise, 4 Check in, 5 Thin evidence). On the snapshot every feed company resolves to rule 5 (grey) and Viva Jets to rule 4 (check in). When the memo verdict from jx31 lands, the pill can switch to it with no layout change.
- Home town is not in the stored record, so it shows the hatched "not in public records" chip.
- The AI box shows its empty state ("No summary yet"). cloud/ai_brief fills the same slot: 4 to 6 cited sentences, labelled as an AI summary checked against the linked sources.

## Self-critique round (5 weakest things after the first shots, all fixed and re-shot)
1. **The home hero headline ran five lines** at 72 px and pushed the index below the fold. Fix: the number now sits beside a 48 px sentence (stacked on phones), and the hero is shorter.
2. **The chart annotation was clipped** at the right edge ("0 with a ..."). Fix: it's right-aligned to the left of the leader line, on two lines.
3. **The index rows were tall and monotone**: the pill, chip and strip were stacked, with 26 identical pills down the right. Fix: one-line rows on desktop with the reason clamped to one line, the pill in its own quiet column, and a caption explaining the strip and the pill.
4. **The dossier life-line chart was unreadable at 390 px**, and the registration label collided with the 2018 bar. Fix: phones get a horizontal bar per decision with in-row labels. On desktop the registration label sits below the axis, and the day-dated EU bar no longer touches the 2025 bar.
5. **The level cards wrapped framework names badly** ("Aalto TRL) 1-/9"). Fix: short framework names pinned to the card foot, with the full name kept in the link title.

## Known gaps for phase 2
- The cohort radar or backtest chart is designed in the task text but not prototyped here; phase 2 builds it on the same chart conventions.
- The search field and nav items for Cohort radar and Method are visual only in the prototype.
