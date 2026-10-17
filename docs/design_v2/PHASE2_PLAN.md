# Phase 2, company page only (approved C layout, chart removed)

Applies the moment the chief says "main merged, go". Another agent is editing these files on main now, so nothing here is touched before then. Prototype to match: `c_company.html` (Viva Jets).

## Shared components (merged from cloud/design_c_components 493cb0a; use these, not my prototype versions)
`radar/templates/_c_components.html` and `radar/static/c_components.css`, tested in `tests/test_c_components.py`:
- `verdict_pill(verdict, reason)`: grey Watchlist, teal Partner introduction or Accelerator, green Invest or Due diligence, red Reject. The memo's decision arrives in capitals ("WATCHLIST"), so the page passes it title-cased (`rec.decision|capitalize`) and puts `rec.note` in `reason`.
- `key_stats(rows, title)`: rows of `{label, value, source_url}`. Block 5 builds its 8 rows: Technology, Business, Investment, Ocean impact ("4 / 9" strings from the frameworks level, empty means hatched), Founded, Business ID, First public record, Last signal. The Investment "N of 10 dimensions" line goes into the label ("Investment (2 of 10 dimensions)"), so the macro stays unchanged.
- `sparkline(signals, ...)`: home rows only (on hold for Dayo's screenshot).
- `lifeline(...)`: not used on the company page. Dayo removed the chart; block 3 is the one-line public record.
- `_tabbar.html` `tabbar(current)`: included once in `base.html` (`current` = radar, search, lists, backtest or data per route).
My prototype CSS (`docs/design_v2/c.css`) only adds what the macros do not cover: the instrument header, the big verdict word, the public-record line, the capsule buttons, the About card, News and Analysts. Those rules go to `radar/static/company.css`, not a second component sheet.

## Page order (top to bottom), mapped to today's files
| # | Block | Built from | File |
|---|---|---|---|
| 1 | Back link, initials mark, grey caps "Business ID · group", name | `c`, `register` | `company.html` (replaces `co-head`; the `<h1>` stays first) |
| 2 | Verdict as the big word, plus the memo's one-line reason | `memo_for(...)` (`company_memo.html` gives the decision and note) | `company.html` header plus a slimmed `company_memo.html` |
| 3 | One quiet line: "Public record: first <date> · N dated signals · latest <date>", each date an anchor to its row in News | `signals` (min and max date, count) | `company.html` |
| 4 | Two capsule buttons: "Ask Aava" (the `_aava.html` partial from jx25, its own button and sheet, a plain tap for the speech gesture) and "Print memo" (`window.print()` plus a print stylesheet that hides navigation) | `_aava.html`, `aava.js` | one `{% include "_aava.html" %}` line plus a print button |
| 5 | Key statistics grid: 4 readiness levels (frameworks level; Investment adds "N of 10 dimensions"), founded, Business ID, first public record, last signal, each with its source chip | `readiness`, `register`, `signals` | `company.html` |
| 6 | About = "What the public record says": the jx35 brief when one exists (`company_brief.html`, placed here by me, not edited), otherwise the six rule-written rows (what it does, thesis fit, readiness, who to meet, what the fund should do, what's missing) with numbered sources and hatched "no public evidence yet" | `company_brief.html`; **new** `radar/card.py` + **new** `radar/routes/card.py` (template global, no edit to `company.py`) + **new** `company_card.html` | include lines |
| 7 | News: dated signals, newest first, each with source; row ids `sig-<id>` for the anchors in 3 | `signals` | `company.html` (keeps `id="signals"`, heading "Public records found" kept for tests) |
| 8 | Analysts: the decision-table bands as four bars, "because: ...", table source | memo `because_labels` | slimmed `company_memo.html` (why, risks and actions move into Evidence) |
| 9 | Evidence (folded `<details>`): 01 to 04 sections with their ids `q1` to `q4` unchanged, the memo's why, risks and actions, the stitcher block (`company_stitch.html`, included unchanged), connector slots, "Sources on this page" | existing markup, unchanged inside | `company.html` |

Laptop at 960 px and up: blocks 1 to 5 on the left (about 520 px), 6 to 8 on the right, Evidence full width under both. Phone: one column in the order above, bottom tab bar from `base.html`.

## Test constraints read from tests/ (must stay true)
- `<h1>` comes before "Connections across records", which comes before `id="q1"` (`test_first_traction.py`). Connections move into block 1's grey line or stay just under the `<h1>`.
- `id="lifeline"` comes before `id="q1"` (`test_first_traction.py:257`). The chart is removed per Dayo, so block 3 (the public-record line) carries `id="lifeline"`. The test keeps passing, and the anchor still means "the company's timeline".
- The `q1` to `q4` contents are asserted by slice (`test_company.py`, `test_judge_fixes.py`, `test_visual_polish.py`). Their inner markup is moved into Evidence, not rewritten.
- "Sources on this page" and every source URL stay in the page.

## Files, in order (one commit each, `pytest -q` green, phone and laptop screenshots read)
0. Already done: `cloud/design_c_components` merged into this branch (b0b3b63), tests green (407 passed).
1. `radar/static/company.css` (the company-only rules from `docs/design_v2/c.css`; components come from `c_components.css`) and `base.html` (`{% include "_tabbar.html" %}` plus `c_components.css` linked once): 30 min
2. **new** `radar/card.py`, `radar/routes/card.py`, `radar/templates/company_card.html`, `tests/test_card.py`: 50 min
3. `radar/templates/company.html` (blocks 1 to 9) and `company_memo.html` (split into the verdict and Analysts partials, with why, risks and actions under Evidence): 70 min
4. Include lines for `company_brief.html` (jx35) and `_aava.html` (jx25) if they exist on main at that moment; otherwise the card and a disabled "Ask Aava" with "not connected yet": 15 min
5. Print stylesheet (`@media print` in `c.css`: hide navigation, buttons and folds; open Evidence): 15 min

About 3 hours. The home page waits for Dayo's screenshot.

---

# Phase 2 plan

**Current direction: C (jx37), the Trading 212 feel on B's structure, phone first.** The C plan below replaces the B plan's skin steps. B's structural decisions ("/" is the country list of feed main-tier rows, the six-row card, evidence folded under it) still hold.

## Direction C: files and order
| # | Files | What changes | About |
|---|---|---|---|
| C1 | `radar/static/app.css` (+ **new** `radar/static/c.css`, from `docs/design_v2/c.css`) | Tokens plus the C skin: 16 px cards, segmented tabs, big numbers, verdict pills coloured like change pills (grey Watchlist, teal Partner or Accelerator, green Invest or Due diligence, red Reject; the only status colours), 52 px action buttons, the bottom tab bar | 40 min |
| C2 | `radar/templates/base.html` | Bottom tab bar on phone (Radar `/`, Search `/company-search`, Lists `/radar`, Backtest `/backtest`, Data `/data`), a top tab bar at 960 px and up. Keeps `#theme-toggle` and the `theme` localStorage key. The health thesis becomes a quiet "Sector" switch. `/method` and `/how` stay linked from the footer | 30 min |
| C3 | *(superseded: the sparkline and life-line now come from `_c_components.html`)* | Server-side inline SVG: `sparkline(dates, today)` (cumulative dated signals over 12 months, about 72x24) and `lifeline(signals, today, years)` (the step chart). Rendered without JavaScript. The 1Y, 3Y and MAX chips are plain links (`?range=1y`) that htmx swaps in place | 50 min |
| C4 | **new** `radar/card.py` + **new** `radar/routes/card.py` + **new** `radar/templates/company_card.html` | The six-row card as in the B plan (template global, no edit to `company.py`, `memo.py` or `matching.py`). On the C page it is the "About" section | 50 min |
| C5 | `radar/templates/company.html`, `company.css`, `company_memo.html`, `memo.css` | The instrument page: initials mark, name, Business ID and group; the verdict as the big word with its one-line reason; the life-line SVG with chips; "Ask Aava" (a plain button, so the browser gets the user gesture speech needs) and "Print memo" (`window.print()` plus a print stylesheet); Key statistics grid (4 readiness levels, founded, Business ID, first public record, last signal, each sourced); About (the card); News (dated signals, newest first, sourced); Analysts (the decision-table bands as bars, "because: ..."). The existing 01 to 04 sections, stitcher block and sources fold under "Evidence" with their ids kept for tests | 70 min |
| C6 | `radar/templates/feed.html`, `feed_rows.html`, `feed.css` | "/" as the C home: segmented country tabs (Finland, Baltic; they switch `?thesis=`), "On the radar" count with a "+N this quarter" badge, search, rows (initials, name, one-liner, sparkline, verdict pill, "New" plus "N d ago"), weak matches and "no thesis evidence yet" as two closed disclosures. On laptop the Lists cards sit on the right | 60 min |
| C7 | Every other template | Tokens only, no structure change. Then screenshots of every route at 390x844 and 1440x900 in both themes, one critique round, and a first-paint check under 2 s on a phone profile | 45 min |

About 6 hours in total. C1 to C6 are the demo path for the QR code (phone, then laptop).

---

# Earlier plan for B (structure still applies)

Starts on the chief's "main merged, go". Branch `cloud/design_v2_apply` from the new main. Prototype to match: `b_home.html` and `b_company.html` (Viva Jets).
Ground rule: every fact, number, link and test stays intact. Tests that pin page markup (about 400 `in r.text` assertions) are read before each file is touched, and any wording they check is kept. They live in `test_company.py`, `test_feed.py`, `test_visual_polish.py`, `test_judge_fixes.py`, `test_first_traction.py`, `test_frameworks.py`, `test_stitcher.py`, `test_app.py`, `test_intake.py` and `test_thesis_swap.py`.

## Order (each step is one commit with screenshots and `pytest -q` green)
| # | Files | What changes | About |
|---|---|---|---|
| 1 | `radar/static/app.css` | Bring in the tokens from `docs/design_v2/tokens.css`: type scale, colours both themes, chip, pill, hatch, tabs, focus, motion. Keep existing class names as aliases so pages don't break between steps | 30 min |
| 2 | `radar/templates/base.html` | Header becomes brand plus search plus theme button (keeps `#theme-toggle` and the `theme` localStorage key used by theme.js). Main nav and the sector or region switch stay, quieter. Footer unchanged | 20 min |
| 3 | **new** `radar/card.py` + **new** `radar/routes/card.py` + **new** `radar/templates/company_card.html` + **new** `radar/static/card.css` | The six-row card built only from what the page already has (company, readiness from radar/frameworks, `who_comes_next`, `next_step`, memo verdict, why and risks), with numbered sources. Registered as a template global the way `routes/memo.py` registers `memo_for`, so `company.py`, `memo.py` and `matching.py` are not edited. Empty row shows hatched "no public evidence yet". Unit tests in **new** `tests/test_card.py`: every row has a source or the empty state, and there is no number without a source | 60 min |
| 4 | `radar/templates/company.html`, `radar/static/company.css`, `company_memo.html`, `memo.css` | Header strip (memo verdict pill, founded, Business ID, last signal, each with its source) and the card on top. The current sections 01 to 04, life-line, public records, memo details, stitcher block and sources move under "Evidence behind the card" as `<details>`, with public records open. Section ids (`q1` to `q4`, `signals`, `lifeline`) are kept for links and tests | 60 min |
| 5 | `radar/templates/feed.html`, `feed_rows.html`, `radar/static/feed.css`, `base.html` (tab bar only) | "/" becomes the country list, with no new route. Country tabs switch the thesis store exactly as `?thesis=` does today (Finland = `redstone_apelago_blue`, Baltic = `baltic_blue`). The rows ARE the feed's main-tier rows (companies the radar found, newest public signal first), each with its verdict pill and the card's one-liner. A small "New this quarter" label sits on rows inside the window; it is not a page of its own. Weak matches and "New startups, no thesis evidence yet" (the intake tier) stay as two closed disclosures under the list, as today. The health thesis is a sector, not a country: it moves to a quiet "Sector" switch in the header. The quiet Sort control stays (newest signal by default). The verdict pill and one-liner per row come from a **new** template global in **new** `radar/startup_list.py` (memo verdict plus the card's "what it does" sentence), so `feed.py` stays untouched | 60 min |
| 6 | `radar.html`, `backtest.html`, `method.html`, `data.html`, `how.html`, `company_search.html`, `company_404.html`, `error.html`, and `radar.css`, `backtest.css`, `data.css`, `matching.css`, `stitch.css`, `chip.css` | Restyle with the tokens only: no structure change, no copy change | 45 min |
| 7 | Screenshots of every route at 1440x900 and 390x844 in both themes, one self-critique round, README cloud section | Final pass | 30 min |

About 5 hours in total. Steps 1 to 5 are the demo path (home, then company); step 6 can be cut if the freeze comes first.

## Not in my files (owners)
- **Town:** the PRH address is not stored. One field in `radar/adapters/prh.py` plus a column in a new `radar/schema/NNN_*.sql`. Owned by the adapter, not me. Until then the list shows "not stored yet".
- **AI sentences in the card:** jx35 (cloud/ai_brief) can replace the rule-written answers row by row. `card.py` takes an optional per-row override with its own sources, so no template change is needed.
- **Investment readiness:** shown from radar/frameworks (level), with the memo's dimension count as a grey second line, per the chief.

## Decided by the chief (17 Oct)
- "/" is the country list. No new route. `/radar`, `/backtest`, `/method`, `/how`, `/data` and `/api` keep their routing unchanged.
- The list rows are the feed's main tier, not cohort plus portfolio. The prototype's "portfolio and cohort first" order is dropped in phase 2: the default is newest signal first. Cohort and portfolio companies stay reachable from `/radar` and search.
- Country tabs = thesis stores (Finland, Baltic). The health thesis = the "Sector" switch in the header.
