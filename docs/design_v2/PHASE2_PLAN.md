# Phase 2 plan: apply B with the summary card to the real templates

Starts on the chief's "main merged, go". Branch `cloud/design_v2_apply` from the new main. Prototype to match: `b_home.html` and `b_company.html` (Viva Jets).
Ground rule: every fact, number, link and test stays intact. Tests that pin page markup (about 400 `in r.text` assertions) are read before each file is touched, and any wording they check is kept. They live in `test_company.py`, `test_feed.py`, `test_visual_polish.py`, `test_judge_fixes.py`, `test_first_traction.py`, `test_frameworks.py`, `test_stitcher.py`, `test_app.py`, `test_intake.py` and `test_thesis_swap.py`.

## Order (each step is one commit with screenshots and `pytest -q` green)
| # | Files | What changes | About |
|---|---|---|---|
| 1 | `radar/static/app.css` | Bring in the tokens from `docs/design_v2/tokens.css`: type scale, colours both themes, chip, pill, hatch, tabs, focus, motion. Keep existing class names as aliases so pages don't break between steps | 30 min |
| 2 | `radar/templates/base.html` | Header becomes brand plus search plus theme button (keeps `#theme-toggle` and the `theme` localStorage key used by theme.js). Main nav and the sector or region switch stay, quieter. Footer unchanged | 20 min |
| 3 | **new** `radar/card.py` + **new** `radar/routes/card.py` + **new** `radar/templates/company_card.html` + **new** `radar/static/card.css` | The six-row card built only from what the page already has (company, readiness from radar/frameworks, `who_comes_next`, `next_step`, memo verdict, why and risks), with numbered sources. Registered as a template global the way `routes/memo.py` registers `memo_for`, so `company.py`, `memo.py` and `matching.py` are not edited. Empty row shows hatched "no public evidence yet". Unit tests in **new** `tests/test_card.py`: every row has a source or the empty state, and there is no number without a source | 60 min |
| 4 | `radar/templates/company.html`, `radar/static/company.css`, `company_memo.html`, `memo.css` | Header strip (memo verdict pill, founded, Business ID, last signal, each with its source) and the card on top. The current sections 01 to 04, life-line, public records, memo details, stitcher block and sources move under "Evidence behind the card" as `<details>`, with public records open. Section ids (`q1` to `q4`, `signals`, `lifeline`) are kept for links and tests | 60 min |
| 5 | `radar/templates/feed.html`, `feed_rows.html`, `radar/static/feed.css` | Home becomes country tabs, then the plain list (name, card "what it does" sentence, town, newest signal and date, verdict pill) with the quiet Sort control. The list rows come from a **new** template global `startup_list` in **new** `radar/startup_list.py` (cohort plus portfolio plus feed rows with a stated reason). The existing feed rows, weak list and intake tier stay below as "New finds" so `/feed/rows` and its tests keep working | 60 min |
| 6 | `radar.html`, `backtest.html`, `method.html`, `data.html`, `how.html`, `company_search.html`, `company_404.html`, `error.html`, and `radar.css`, `backtest.css`, `data.css`, `matching.css`, `stitch.css`, `chip.css` | Restyle with the tokens only: no structure change, no copy change | 45 min |
| 7 | Screenshots of every route at 1440x900 and 390x844 in both themes, one self-critique round, README cloud section | Final pass | 30 min |

About 5 hours in total. Steps 1 to 5 are the demo path (home, then company); step 6 can be cut if the freeze comes first.

## Not in my files (owners)
- **Town:** the PRH address is not stored. One field in `radar/adapters/prh.py` plus a column in a new `radar/schema/NNN_*.sql`. Owned by the adapter, not me. Until then the list shows "not stored yet".
- **AI sentences in the card:** jx35 (cloud/ai_brief) can replace the rule-written answers row by row. `card.py` takes an optional per-row override with its own sources, so no template change is needed.
- **Investment readiness:** shown from radar/frameworks (level), with the memo's dimension count as a grey second line, per the chief.

## QUESTION
Should "/" become the country list (step 5), with the 90-day feed moved under it as "New finds"? Or should the country list live on a new route such as `/startups`, with "/" unchanged? The first matches Dayo's brief. The second touches fewer tests.
