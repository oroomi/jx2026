# VERIFY night 1 (jx10_verify)

- Time: Fri 16 Oct 2026 17:41 UTC (date -u), 20:41 Helsinki
- Live URL: https://jx.hankintaviikko.fi (STALE, see D1)
- main short sha: 070c2d9 (`git rev-parse --short main`). The live footer prints `build 12e0dd2` (jx01 skeleton).
- Method: the live service does not serve main, so content checks ran against main HEAD on the spare port 8159
  (`RADAR_DATA_DIR=/tmp/jx10_data python3 -m uvicorn app:app --port 8159`, data = copies of the two live
  data/radar_*.sqlite files). The server was stopped by PID afterwards. Live was re-checked at 17:41 UTC and still printed build 12e0dd2.
- Evidence screenshots: /root/hack/shots/verify_night1_{home,rich,sparse,method,health,tall}/ (desktop.png, mobile.png, text.txt),
  /root/hack/shots/verify_night1_bottom_c_2961350-5.png, verify_night1_bottom_c_no-tunisea.png, verify_night1_hilma_src*/.

## Per-task table

Scope check: `git log --no-merges --name-only --format= task/<n> --not 11b6280 <earlier task branches>` (own commits only, because
`git diff --name-only 11b6280..task/<n>` also lists merged predecessors), compared with "You own" in /root/hack/done/*_<n>_rc0.md.
No task touched radar/emit.py, radar/db.py, radar/schema/001_core.sql, config/thesis*.yaml or data/declared/
(`git diff --name-only 11b6280..main | grep -E 'emit.py|db.py|001_core|config/thesis|data/declared'` prints nothing).

| Task | Verdict | One line of evidence |
|---|---|---|
| jx01_skeleton | PASS | 3 commits, own files all in the list (app.py, thesis.py, build.py, home/method routes, templates, static, tests/test_app.py). |
| jx02_prh | PASS | 1 commit, files = declared.py, prh.py, tests/fixtures/prh_*.json, tests/test_prh.py. 6 of 6 sampled PRH records match the DB on business id, name and registration date (check 4). |
| jx03_hilma | PARTIAL | Scope clean. Buyer, title, amount match the notice for 2 of 2 sampled notices, but the winner is not visible in the rendered notice text, and "Founded" and "Industry" for Hilma-only companies are labelled with the Hilma notice as source (D4). |
| jx04_businessfinland | PASS | Scope clean. `/method` prints "awaiting export (data/declared/businessfinland.xlsx not present)". Running pytest rewrites the tracked xlsx fixture (see D8). |
| jx05_store | PARTIAL | Own files in the list, but the first commit 8a93889 added `data/radar.sqlite-journal` (removed again in 8424d78) and .gitignore does not cover `*.sqlite-journal` (D7). |
| jx06_feed | PASS | Scope clean (feed.py, feed templates, feed.css, home.py allowed edit). My SQL recount equals the page (check 5). |
| jx07_company | PARTIAL | Scope clean, four questions in order, honest empty lines. The fixed bottom bar covers the page footer at 390 px (D5). |
| jx08_thesis | PARTIAL | Edits outside its list: radar/static/app.css, radar/templates/feed_rows.html, tests/conftest.py. The swap works but the health feed has 0 rows (D3). |
| jx09_deploy | FAIL | Branch holds only the merge commit 070c2d9. The live service is still build 12e0dd2 with an empty feed (D1). Task was still in /root/hack/running at verification time. |

Totals: 4 PASS, 1 FAIL, 4 PARTIAL.

## Refutation attempts (command, outcome)

1. Scope per task (above). Outcome: no contract-file touches; three out-of-list edits by jx08, one stray journal file by jx05.
2. `python3 -m pytest -q` in this worktree: 98 passed in 2.27 s. Pytest dirties the tracked `tests/fixtures/bf_export_test_fixture.xlsx` (restored with git checkout). Assertions read: store (window_boundary, declared_excluded_by_default, tie_broken_by_confidence), feed (rows_and_order, footer_n_equals_rows), company (four_sections_in_order by index positions, unknown_key_404_escaped), thesis swap (swap_changes_rows_and_counts, cookie_keeps_choice, junk_falls_back_to_default). Each asserts what its name claims. Caveat: all of them run on synthetic fixtures; none runs on the real DB, which is how D2 and D3 slipped through.
3. `/root/hack/bin/smoke.py https://jx.hankintaviikko.fi/`: PASS 2/2, but only because the stale skeleton answers 200 on `/` and `/method`. Live `/` shows "no signals yet", live `/c/2902007-2` returns 404.
4. shot.py on `/`, `/c/2961350-5` (TPI Control, rich: Hilma plus register, 2 signals), `/c/no-tunisea` (sparse), `/method`, `/?thesis=health_tech_turku`, `/c/0208222-2` and read every PNG. 390 px assertion with playwright: scrollWidth = 390 on all 6 pages. Hosts requested: only localhost:8159. Console errors: none on 200 pages. No placeholder data seen. Contrast fine in dark theme. The 390 px header (brand, nav, thesis switcher, Switch, Theme) uses about 290 px of the first 844 px screen before the headline (D6).
5. Provenance, feed rows: first 5 feed rows (3661735-2, 3661594-7, 3661355-4, 3661460-2, 3661120-9): each found by `select ... from signals join companies where company_key=?` with source_url `https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=<id>` and the date shown on the page. Company-page facts for 2961350-5 (founded 2018-12-21, Hilma contract 2024-01-07 EUR 1,800,000, status active): found in the DB with source_url. All traced.
6. Source fetches, UA from CLAUDE.md, 2 s apart: 6 PRH URLs, all 200 (3455694-7, 3631645-3, 3245141-2, 3578590-1, 3306594-3, 3327970-6). 4 Hilma URLs (procedure 28618, 22434, 16583, 714): 404 from urllib without an Accept header, 200 with `Accept: text/html` or curl; the HTML is a 9688-byte SPA shell for any id, so only a browser render proves content. 10 of 10 reachable.
7. Primary-source diff, PRH: business id, name, and `businessId.registrationDate` equal the DB `founded` for all 6 companies (e.g. 3455694-7 Ruokomestarit - Premium Finnish Reed Oy 2024-06-06, 3631645-3 Seara Consulting Oy 2026-06-09). No mismatch. Note: the company-level `registrationDate` in the API is later (2024-07-11 for the first); the DB correctly uses the business-id date.
8. Primary-source diff, Hilma, rendered in browser (shot.py): procedure 812 notice 3856: buyer HUS Kiinteistöt Oy, title "931268 HUSK Nesteverkoston huoltojen hankinta", 1 800 000 EUR; matches the TPI Control signal. Procedure 714 notice 3658: buyer Riihimäen Kotikulma Oy, title "Ulkoalueiden hoidon ja korjaustöiden hankinta", estimated value 1 200 000 EUR (framework maximum 1 400 000 EUR); matches signal for 3259372-8. Not verified: that TPI Control and 3259372-8 are the winners (no winner text in the rendered page).
9. Rule truth: own SQL (group_tag='feed', feed_signal_types, window 2026-07-18..2026-10-16 from feed_window_days 90, min date per company): 82 companies. Page: footer "82 companies, 82 signals", pill All 82, rows 60 + 22 low = 82, register_entry pill 81 and 81 distinct links. Equal. PASS.
10. Inputs move outputs: default feed 82 rows vs health feed 0 rows (differ, but see D3); company pages 2961350-5 vs 3661735-2 vs no-tunisea differ in every fact. Marine leakage in health: none (feed empty; `select count(*) ... name like marine/ocean/subsea` in the health DB = 0).
11. Honesty audit: three sparse pages (no-tunisea, dk-reefcircular, dk-sensemakers): grep for lorem, TODO, example, N/A, TRL/IRL digits, level digits: no hits. Readiness shows "no public evidence" and Business shows "no public evidence" or "not scored yet"; Y-tunnus "not in public records". `git grep -i -E 'mock|lorem' -- radar tests config` finds nothing (only docs mention the word). Fixtures live under tests/fixtures and are named as such. Declared CSV headers contain no person-name columns; no named individuals seen in templates or adapters (spot check, `grep -i 'contact|founder|ceo'` finds only the CSV column `innovation_contact_page`).
12. Input bounds: `/c/%00` 404, `/c/<script>alert(1)</script>` 404, 5000-digit key 404, `/search?q=` 10 000 chars 200, `/search?q=<script>alert(1)</script>` 200 and echoed as `&lt;script&gt;`, `/?type=../../etc/passwd` 200 (full feed), `/?thesis=../../etc/passwd` 200 and default thesis, `/?thesis=` 5000 chars 200 default, `/feed/rows?type=nope` 200 (ignored, all rows), `/feed/rows?type=%00` 200, `/search?q=' OR 1=1--` 200. No 500, no traceback (uvicorn log checked), no unescaped echo. PASS.
13. Hygiene: `git grep -n -P '\x{2014}' -- . ':!data/declared'` empty. Secrets patterns (sk-, BEGIN ... PRIVATE KEY, AKIA) empty. `grep -rnE 'https?://' radar/templates radar/static/*.css` empty (source links are rendered from DB; fonts load from /static/fonts via @font-face; htmx at /static/vendor/htmx.min.js with zero http(s) strings inside). `git ls-files | grep -E '\.env|\.sqlite'` empty. PASS (D7 is history only).
14. First ten seconds, live URL (curl plus shot): the page shows the heading "Early-signal feed" and "no signals yet. Run `python3 -m radar.build`" with a hatched "not in public records" chip. Nothing real appears. FAIL on live. On main (8159) the feed is populated at once.
15. Takeaway from main's UI alone: "It lists recently registered or contract-winning Finnish companies that match a blue-economy keyword thesis, each row with a link to the public record, for a screening team (the words 'your pipeline' imply an accelerator or fund)." It needs light inference about the audience: PARTIAL on main, FAIL on live.
16. DEMO_SCRIPT.md: see section below.
17. Tallest state at 390 px: the page with the most signals (2) is 2961350-5 (3784 px tall). Scrolled to bottom: fixed `.co-bar` ("Radar of 19, opens Saturday") sits at top 792, height 52, over the page footer (footer top 791, bottom 844), so "build 070c2d9 / Public records only. Companies only." is hidden (D5). Content above is not hidden (last section ends above the bar). The bar carries a teaser, not the headline answer; the first answer (section 01) is not pinned.

## DEMO_SCRIPT.md check

| Claim | Live product (stale 12e0dd2) | main on 8159 |
|---|---|---|
| Feed `/` loaded with companies from the last 90 days | FAIL: empty | OK, 82 rows |
| Tap top row, chip opens register record | FAIL | OK: PRH/YTJ link on every row |
| Type one of THEIR cohort companies, four-question page appears | FAIL: `/c/...` 404 | OK: `/search?q=TuniSea` 302 to `/c/no-tunisea`; four sections in order |
| `/radar` earliness chart | not built | not built: Saturday gap |
| Swap thesis to health-tech Turku | switcher absent | switch works, but the health feed shows 0 rows (D3) |
| "A'Pelago screens 160 applications for 21 places" | not on screen | not on screen; `grep -n '160 ' README.md DISCLOSURE.md TASKS.md EVAL.md PILOT.md` found no source in the repo: unsourced number in the script (D9) |
| Opener "companies your pipeline has not seen yet" | not on screen | OK: it is the H1 |
| Closing line `<N> of 19`, `<number> <unit>` | placeholders | placeholders (Saturday) |

## Defects

| # | Sev | Defect and exact reproduction | Fix owner |
|---|---|---|---|
| D1 | high | Live URL serves the jx01 skeleton. `curl -s https://jx.hankintaviikko.fi/ \| grep -o 'build [0-9a-f]\{7\}'` prints `build 12e0dd2`, page says "no signals yet", `curl -o /dev/null -w '%{http_code}' https://jx.hankintaviikko.fi/c/2902007-2` prints 404, `/?thesis=health_tech_turku` shows no switcher. Main is 070c2d9. smoke.py still prints PASS, so it cannot catch this. | jx09_deploy (deploy.sh run plus build of data/radar_*.sqlite on the VPS); smoke.py could also assert a non-empty feed (/root/hack/bin/smoke.py) |
| D2 | medium | Keyword matching puts non-marine firms at the top of the feed with "medium" confidence: `curl -s localhost:8159/ \| sed -n '/<ol class="feed"/,/<\/li>/p'` shows Meridian Vector Oy (NACE 58290 software publishing, matched on 'meri'), Grey Seal Ventures Oy (matched on 'sea'), Meridies Group Oy. 59 of 82 rows are medium and 22 low; a first-time viewer sees unrelated companies first. | radar/adapters/prh.py (keyword rule) and config/thesis.yaml (planner), radar/store.py ordering |
| D3 | medium | Thesis swap demo is empty: `/?thesis=health_tech_turku` shows "0 companies" and "no signals yet" because all 217 signals in data/radar_health_tech_turku.sqlite are public_contract dated 2023-11-24 to 2026-07-05, outside the 90-day window. The DEMO_SCRIPT 80-90 s beat has nothing to show; tests only use synthetic data. | radar/adapters/hilma.py and thesis_health_turku.yaml (window or signal types), tests/test_thesis_swap.py needs one real-DB assertion |
| D4 | medium | Provenance mislabel: `/c/0172386-8?thesis=health_tech_turku` shows Founded 2026-02-16 and Industry 87301 with a chip "www.hankintailmoitukset.fi", but those values come from the awards archive company profile (`registered`, `tolCode` at radar/adapters/hilma.py:130) and are not on the notice page. A human opening the chip cannot find them. Also the Industry chip date is the fetch date. | radar/adapters/hilma.py (source of the profile facts) and radar/templates/company.html |
| D5 | medium | At 390 px the fixed bar `.co-bar` ("Radar of 19, opens Saturday") covers the page footer on every company page: playwright at 390x844, scrolled to bottom, footer 791..844 vs bar 792..844; screenshot /root/hack/shots/verify_night1_bottom_c_2961350-5.png. The bar also advertises a screen that does not exist yet. | radar/static/company.css (bottom padding or bar offset), radar/templates/company.html |
| D6 | low | Mobile header takes about 290 px of the first screen (brand, nav, thesis select, Switch, Theme) before the headline: /root/hack/shots/verify_night1_home/mobile.png. | radar/templates/base.html, radar/static/app.css |
| D7 | low | `.gitignore` has `data/radar*.sqlite` but not `data/*.sqlite-journal`; jx05 committed `data/radar.sqlite-journal` once (`git log --all --oneline -- data/radar.sqlite-journal`). Not tracked in main now. | .gitignore (chief) |
| D8 | low | Running pytest rewrites the tracked `tests/fixtures/bf_export_test_fixture.xlsx` (git status shows it modified after `python3 -m pytest -q`), so five task commits include a binary diff of it. | tests/test_businessfinland.py (write the xlsx to tmp_path) |
| D9 | low | DEMO_SCRIPT.md states "A'Pelago screens 160 applications for 21 places" with no source in the repo or product. | DEMO_SCRIPT.md (chief): add a source or drop it |
| D10 | low | jx08 edited files outside its list (radar/static/app.css, radar/templates/feed_rows.html, tests/conftest.py). The edits are small and sensible but break the "You own" rule. | process note for the chief |

## Gaps scheduled for Saturday (not failures)

Cohort radar `/radar` and earliness backtest (TASKS rows 13-25: "Radar of 19" teaser, backtest chart), readiness levels with printed rules ("not scored yet, rule table lands Saturday"), matching in section 03 ("matching rules land Saturday"), next-step table in section 04, agentic stitcher, Business Finland data (awaiting export), EU projects / BlueInvest / patents / job ads signals (pills show "no signals"), closing-line number from EVAL.md, DEMO_SCRIPT placeholders.

## Verdict

FAIL for night one as deployed: main passes 98 tests and its feed, provenance and injection checks hold, but the live URL still serves the empty skeleton (D1), and the health-thesis demo is empty on real data (D3).
