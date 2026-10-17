# jx30_visual_polish [cloud]: clear, on-brand, easy for a 50-year-old fund partner

Branch: `cloud/visual_polish`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first.

## Why
Judge review 2 scored visual appeal 3. The criterion reads "clear and on-brand". The partners asked for ease of use for 40 to 60 year old operators: search, assess, match, in plain words, nothing to learn first. DESIGN.md direction 1 "Receipts" stays (dark default, one teal accent, Newsreader + IBM Plex Sans, hatched chips for missing data). Polish it; do not invent a new direction.

## See before you touch
Install playwright + chromium in your session and screenshot a local uvicorn over data/snapshot at 1440x900 and 390x844 for: /, /c/2902007-2, /radar, /backtest, /how, /method, and the health thesis home (/?thesis=health_tech_turku). Read every PNG. Commit the before set under docs/shots/before/ and the after set under docs/shots/after/ (PNG, small). If playwright cannot run, say so in a STATUS line and push; the chief screenshots on the VPS.

## What to fix, in this order
1. First screen, phone and laptop: within one screen a fund partner sees what this is (one sentence), a search box, and the first company row. Zero-signal filter pills go behind one closed "More filters" disclosure (judge item 6).
2. Readability for 40 to 60: body text at least 17 px, line height 1.5, contrast AA or better in both themes, tap targets at least 44 px, no text under 14 px except tabular footnotes. Plain words over our jargon on every label a judge sees first (keep the precise term in a tooltip or the /how page).
3. Company page as the hero: the four partner questions read as four clearly separated answers, each with its one-line answer first in Newsreader 22 px, then the evidence. Evidence links look clickable. Hatched "not in public records" chips stay distinct from real values.
4. Cohort radar and backtest: the chart reads at a glance on a phone (labels not overlapping, legend in words), the headline sentence above the chart.
5. Consistency: one spacing scale, one radius, one accent; headings, chips and tables look the same on every page. Header with the product name "Ocean Opportunity Radar" and "for Redstone Blue x A'Pelago, JunctionX Turku 2026" as plain text. Never the partners' logos or colours as if they made it.
6. Slop list in CLAUDE.md: no purple gradients, emoji headings, four identical cards, centered paragraphs, "Welcome to", placeholder avatars, animated counters.

## Files
You own radar/static/*.css, radar/static/theme.js, radar/templates/base.html, home.html, how.html, method.html, radar.html, backtest.html. feed.html, feed_rows.html, company.html and _chip.html are being changed by cloud/wide_intake and cloud/stitcher tonight: in those, change classes and wrapper elements only, no moved or rewritten blocks, so merges stay clean. Never change data, wording of facts, or numbers. Never touch radar/adapters, radar/store.py, radar/routes/api.py or the chief's docs.

## Done
pytest green on data/snapshot (add a test that the home page puts the first feed row before any zero-count pill and that body font-size is at least 17 px), before/after shots committed, and RESULT: one sentence naming the three biggest visible changes with the after-shot paths. Push a first slice (items 1 and 2) by Sat 08:00 UTC; feature freeze Sat 18:30 UTC.
