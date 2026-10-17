# A versus B (jx36, part 3)

| | **A "Industry pattern"** (`a_home.html`, `a_company.html`) | **B "Dayo's"** (`b_home.html`, `b_company.html`) |
|---|---|---|
| What you see first | A filter rail (country, source group, verdict) beside a sortable 6-column table | Country tabs, then the startup list straight away |
| Company page | Header with tags, 4 KPI tiles, AI box, timeline, key-facts sidebar, section tabs | One scrolling column: AI box first, then verdict, company, public record, readiness, why and risks, who comes next, next step. Source in grey beside every line |
| Example data | 54 companies (19 cohort, 9 portfolio, 26 feed finds), Arctic Fry Oy first; Viva Jets Oy page | Same data and order; same Viva Jets Oy page |

## On the judges' criteria (1 = weak, 5 = strong)

| Criterion | A | B | Why |
|---|---|---|---|
| Clear in 5 seconds | 2 | **5** | A opens on a filter panel and a 6-column table. B opens on "Finland 41", then names with a one-line description, a dated signal and a verdict |
| On-brand (evidence first, honest gaps) | 3 | **5** | A's tiles put sources in small print, and its tabs hide the rest. B prints a source beside every datum, and gaps say "not in public records" in place |
| Usable by a 40 to 60 partner | 3 | **5** | RESEARCH.md patterns 1, 2 and 6 (dense table, filters as the way in, tabs) are the ones that hurt this reader, and A uses all three. B uses the helpful ones: a plain list, a header, sources, a dated record |
| Actionable | 3 | **4** | B shows the verdict on every row and keeps "who comes next" and "next step" on the company page. A puts next steps in the sidebar and tabs |
| Scalable to other countries and sectors | 4 | **4** | Both are driven by the data and the thesis file. B's country tabs grow with the data (7 today). A's filters scale to many facets better |
| Visual appeal | 4 | 4 | A looks like a familiar SaaS product. B is calm and editorial, but long on the company page |
| Phone (390 px) | 2 | **5** | A's table scrolls sideways inside its frame, with the verdict off screen. B stacks each row with its verdict visible |
| **Build cost before the Sat 18:30 UTC freeze** | About 4 to 5 h: new table and filter templates plus tab state, and the tests for feed rows change | **About 2 to 3 h**: one list template (country tabs, then rows) and one long company template that reuse the current routes and API fields. No new data is needed |

## Recommendation: B
B is simpler to read, closer to the evidence-first brand, kinder to the 40 to 60 reader, and cheaper to build before the freeze. Two things from A are worth keeping in B, and both are cheap:
1. The sticky country tabs could carry one quiet "Sort" control later. Not by default.
2. A short header strip on the company page (founded, Business ID, last signal) above the AI box, so the first screen answers "what, where, how recent".

## Known gaps in both, for Dayo's decision
- **Town is not stored.** The PRH register holds the address, but the radar does not save it, so every row shows "not stored yet". Saving it is a one-field adapter change in prh.py (adapter owner, not this task).
- **The AI box is empty** ("No summary yet") until jx35 lands. The snapshot has no checked stitcher rows, and the stitcher's raw proposals were deliberately not shown.
- **Verdicts are almost all Watchlist** (53 of 54; 1 Partner introduction), because most companies lack ocean-impact evidence. The pill is honest grey. B makes that visible at once, which is a finding in itself.
- Investment readiness shows the frameworks level (4 for Viva Jets), with the memo's "N of 10 investment dimensions have public evidence" as a grey second line, per the chief's answer. The memo band still says Low until the memo.py fix on main lands; rebuilding picks it up.

Dayo decides.
