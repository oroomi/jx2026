# Database browser (Datasette, read-only)

Everything the radar knows is in three SQLite files. This serves them read-only on 127.0.0.1:8170 so anyone on the team can
browse tables, follow `source_url` links and export CSV or JSON without touching the app. The chief decides whether it is
ever exposed publicly; nothing here routes it to a public URL.

| Database (Datasette name) | File | Written by |
|---|---|---|
| `radar_redstone_apelago_blue` | `data/radar_redstone_apelago_blue.sqlite` | `python3 -m radar.build` (default thesis) |
| `radar_health_tech_turku` | `data/radar_health_tech_turku.sqlite` | `python3 -m radar.build --thesis config/thesis_health_turku.yaml` |
| `blue_economy_fi` | `data/declared/ecosystem/blue_economy_fi.sqlite` | declared research dataset (read only, never rebuilt here) |

## Start (from the repo root)

```
pip install "datasette>=0.65,<1.0"
datasette serve \
  --immutable data/radar_redstone_apelago_blue.sqlite \
  --immutable data/radar_health_tech_turku.sqlite \
  --immutable data/declared/ecosystem/blue_economy_fi.sqlite \
  --metadata deploy/datasette/metadata.yml \
  --host 127.0.0.1 --port 8170 \
  --setting allow_download off --setting default_allow_sql off --setting allow_csv_stream off
```

In a cloud session without the live stores, replace `data/radar_*.sqlite` with `data/snapshot/radar_*.sqlite`.
Stop it with `fuser -k 8170/tcp` or by the PID you started. `--immutable` opens each file read-only and caches its row
counts: after `python3 -m radar.build` rewrites a store, restart Datasette to see the new rows.

## What is switched off

- Arbitrary SQL: `allow_sql: false` in metadata.yml plus `--setting default_allow_sql off`. Table filters that need SQL
  (`?_where=`) are refused too. The canned queries in metadata.yml still run: they are fixed SQL.
- Downloading a whole database file (`--setting allow_download off`), so the denied tables cannot leave as a file.
- Streaming every row as CSV (`--setting allow_csv_stream off`). Per-page CSV and JSON stay on.

## What is hidden (companies-only rule)

The two radar stores are served as they are: a scan of every text column found none of the 87 names in the dataset's
`person` table, no email address and no LinkedIn profile link. Their `companies` table holds legal names exactly as the
registers print them; in the 16 Oct snapshot 2 of 743 names are shaped like a private person's name (a personal holding or
consulting company). The feed hides those (rule in radar/fit.py `looks_like_person`); the browser shows the register row
as is. Decide this before any public exposure.

In `blue_economy_fi`, these tables and views are denied (403, not listed) because at least one column holds a person's name,
an email address or a LinkedIn link:

| Table or view | Why |
|---|---|
| `person` | 87 named individuals: name, role, LinkedIn link |
| `entity` | `linkedin_url`; `raw_json` (key people, 10 rows with an email, 9 LinkedIn profiles); `description`, `working_on_now`, `data_gaps` name people; `inv_how_to_apply` has 8 emails |
| `readiness` | `team` (names, 25 LinkedIn profiles), `board` (names), `sources` (19 LinkedIn profiles) |
| `cohort_member` | `description` names founders |
| `event` | `summary` and `counterparty` name individuals (angel investors, a trustee) |
| `entity_investor` | `investor_name` includes private angel investors |
| `impact` | `sources` includes a LinkedIn profile; free-text claims |
| `source` | `url` includes 9 LinkedIn profiles and 51 other LinkedIn pages |
| `github_repo` | `owner` and `url` can be a personal account |
| `prh`, `public_funding`, `enrich_log` | `raw_json`, `beneficiary_name` (a sole trader is a person) and free text; empty today, denied before they fill |
| `v_startups`, `v_investors`, `v_demand` | `SELECT e.*` of `entity` |

Their company columns are served through canned queries that select named columns only and drop LinkedIn links:
`organisations`, `cohort_roster`, `dated_events` (no summary, no counterparty), `readiness_levels` (no team, board or
evidence text), `impact_scores`, `public_sources` (LinkedIn removed) and `matches_for_company` (parameter `company`).
Served as tables: `match`, `capability`, `entity_capability`, `entity_keyword`, `entity_segment`, `investor_portfolio`,
`job_signal`, `mrv_ship`, `vendor_ship`, `impact_calc`, `v_capability_counts`.

## Checked on 16 Oct 2026 (cloud session, snapshot stores, Datasette 0.65.5)

| Request | Status |
|---|---|
| `/radar_redstone_apelago_blue/companies?_size=3` | 200 |
| `/blue_economy_fi/match?_size=2` | 200 |
| `/blue_economy_fi/matches_for_company?company=Kelluu` | 200 |
| `/blue_economy_fi/person`, `/blue_economy_fi/entity`, `/blue_economy_fi/v_startups` | 403 |
| `/blue_economy_fi?sql=select+name+from+person` | 403 |
| `/blue_economy_fi.db` (download) | 403 |

None of the 87 `person` names, no LinkedIn link and no email address appears in any served table or query output.
`tests/test_api.py` keeps the deny list and the canned-query columns honest.
