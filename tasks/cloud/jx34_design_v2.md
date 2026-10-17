# jx34_design_v2 [cloud]: redesign the whole site, premium product UI + data-journalism editorial

Branch: `cloud/design_v2`. Protocol: tasks/cloud/PROTOCOL.md. Dayo's verdict on the current site and on the polish pass: "none of them look good". His direction: a combination of premium product UI and data-journalism editorial, with an AI box on each startup (built by cloud/ai_brief; you design its slot).

## References (study them before drawing anything; cite what you take from each in docs/design_v2/README.md)
1. Linear (linear.app): the product frame. Dark layered surfaces, 1 px hairline borders, crisp sans, restrained glow, fast 150 ms hover states, command-style search.
2. Stripe (stripe.com, Stripe Press): depth and type. Soft shadows, generous whitespace, gradients used only as light, never as decoration.
3. FT Visual Vocabulary and FT / Bloomberg graphics: every chart has a headline sentence, direct labels instead of legends, an annotation on the one point that matters, and a source line underneath.
4. The Pudding: restraint, one idea per screen, numbers set large with a sentence beside them.

## The direction ("Dossier")
- Frame: Linear-grade dark UI (light theme as well), a 12-column grid with a max width of about 1200 px, sticky header with the product name and a search field that looks like a command bar.
- Type: Newsreader for editorial headlines and the big answer sentences; one clean sans (IBM Plex Sans is already vendored) for UI; tabular figures everywhere numbers sit in columns. A strict type scale (for example 14 / 16 / 18 / 22 / 32 / 48).
- Colour: one sea-teal accent plus neutrals. Status colours only for the verdict pill. Hatched chips for "no public evidence" stay.
- Home ("front page"): one headline sentence with a big number (for example "123 blue-economy companies surfaced in the last 90 days"), then the feed as an editorial index. Each row shows the company, a one-line why, the signal and date, a verdict pill, and a small mark strip of its dated signals. Filters are quiet tabs.
- Company page ("dossier"): a header with name, Business ID, home town, founded and the verdict pill; the memo verdict as a 32 px headline sentence; a strip of four big numbers (the four levels, each with its framework name); then the AI BOX slot ("What the public record says", 4 to 6 cited sentences, labelled as an AI summary checked against the linked sources; for now render it from a placeholder-free empty state: "No summary yet"); then the company's life-line chart, then questions 01 to 04 as editorial sections with annotated evidence.
- Radar / backtest: one striking annotated chart, the life-lines of the 19 against cohort entry, headline sentence on top, source line below.
- Motion: subtle only (hover lift, fade-in on load, under 200 ms, respects prefers-reduced-motion). No 3D, no particles, no animated counters.

## Phase 1, start now: prototype, no app templates yet
Build docs/design_v2/home.html and docs/design_v2/company.html as self-contained static pages with REAL data from data/snapshot embedded as JSON (Kelluu, 2902007-2, for the dossier). Add docs/design_v2/tokens.css as the proposed design system. Screenshot both at 1440x900 and 390x844 with playwright, in dark and light, and READ every PNG against the four references. Run a self-critique round: list the 5 weakest things you see, fix them, and re-shoot. Push by Sat 02:30 UTC with a STATUS line. The chief serves the prototype to Dayo for approval.

## Phase 2, only after the chief messages "main merged, go": apply it to the real templates
Branch from the new main and apply the design to base.html, every page template and radar/static/*.css. Keep every fact, number, link and test intact. You will own all templates and CSS in phase 2; the chief holds other branches off them.

## Rules
Companies only. No fabricated data: every number on the prototype comes from the snapshot. No partner logos or partner colours. Slop list in CLAUDE.md applies. Fonts and libraries are vendored only (no CDN). Do not touch adapters, store.py, matching.py, memo.py, api.py or the chief's docs.
