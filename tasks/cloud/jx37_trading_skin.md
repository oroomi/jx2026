# jx37_trading_skin [cloud]: direction C, the Trading 212 feel on B's structure, phone first

Branch: `cloud/design_v2` (continue). Dayo's new direction, replacing the visual skin of B (keep B's structure: country list, then the dossier): make it feel like Trading 212, the retail investing app. At the demo a QR code goes on the screen and the audience opens the live site on their phones, so the phone view is the primary design and the laptop view derives from it.

## References
Trading 212's current iOS/Android app: pull its public App Store / Google Play screenshots and any public screenshots in reviews (Dayo's own cropped screenshots may follow; use them when they arrive). Note exactly: the home list row (logo, name, sparkline, price and change pill), the instrument page (big number, time-range chips under a chart, two big action buttons, "Key statistics" grid, "About", news list, analyst bars), the Discover/search tab, the bottom tab bar, the rounded cards, the single blue accent, the type scale and spacing.

## Heading map (ours on the right; every number stays ours and sourced)
- Portfolio value -> "On the radar": count of companies in this country's list, with a change badge "+N this quarter".
- Investments list row -> startup row: initials mark, name, town or sector tag, a mini sparkline of its dated signals, right side a verdict pill (coloured like a change pill: grey Watchlist, teal Accelerator / Partner, green Invest / Due diligence, red Reject) and "last signal 3 d ago".
- Discover / Search -> Search companies (name or Business ID) with the country tabs.
- Pies -> Lists: "Nordic Blue 19", "Redstone portfolio 9", "New this quarter", "No thesis evidence yet".
- Instrument page big number -> the verdict with its one-line reason; time-range chart -> the company's life-line (dated signals over time) with chips 1Y, 3Y, MAX; Buy / Sell buttons -> "Ask Aava" and "Print memo" (never money words).
- Key statistics grid -> the four readiness levels, founded, Business ID, first public record, last signal.
- About -> the six-row AI summary card ("What the public record says").
- News -> dated signals, newest first, each with its source link.
- Analysts -> the decision-table match, printed as "because: High / Medium / Low / High".
- Bottom tab bar on phone: Radar, Search, Lists, Backtest, Data.

## Rules that do not bend
Our neutral palette with one accent (tokens.css), no green/red except the verdict pill. No partner logos. Every number sourced; hatched "no public evidence yet" stays. Phone at 390 px first, under 2 s to first paint, no horizontal scroll; laptop at 1440 derives from it (list left, dossier right is fine). Works without JavaScript for the content (htmx and small scripts only for the chart and Aava). Aava's button must be a plain tap (mobile browsers need a user gesture for speech).

## Deliver
1. By 04:30 UTC: static prototypes c_home.html and c_company.html (Viva Jets) in docs/design_v2/, phone and laptop, both themes, screenshots read, one self-critique round. Push with a STATUS line; the chief serves them to Dayo.
2. PHASE2_PLAN.md updated for direction C (which templates and CSS, in what order, the bottom tab bar in base.html, the sparkline and life-line chart as small inline SVG rendered server-side where possible).
3. Still wait for "main merged, go" before touching app templates.
