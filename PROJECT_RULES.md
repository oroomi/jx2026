# Project rules: assumptions, decisions, taxonomy, formats

The project's one register of rules. Follow it in every session. Sections:

- **A, assumptions:** standing rules applied the same way to every record.
- **D, decisions:** dated decisions, each with the time (UTC), the rule, the reason and the records affected.
- **T, taxonomy:** signal types, sources, confidence levels, verdicts, group tags.
- **F, formats:** dates, IDs, countries, amounts.
- **Q, open questions.**
- **K, known inconsistencies.**

This file folds in ASSUMPTIONS.md (bf4547c, merged to main as e0568b2) and keeps its numbering. A1 to A27 and D1 to D20
are the same rules under the same ids. New items extend the numbering and nothing is renumbered.

How the register is used:

- An open case is asked in a batch (`QUESTIONS_B<n>.md`). Live pages keep the current rule until the case is answered (A31).
- An answer becomes the next D number.
- Every change-log entry cites an A or D id (A32).
- `python3 -m radar.consistency` checks the stores against this file before delivery.
- `python3 -m radar.rules_pdf` renders this file as the "Assumptions & Decisions" chapter, `docs/method/assumptions_and_decisions.pdf`.

This file is re-issued after every question batch.

Sources and dates: the thesis files, the code, EVAL.md, README.md, MODULES.md, METHOD.md, ARCHITECTURE.md, tasks/cloud/*.md
and `git log`. Times are UTC commit times. Counts are the ones the repo states; where none is written, the entry says so.
`thesis.yaml` is `config/thesis.yaml` (blue economy, Finland); `baltic` is `config/thesis_baltic_blue.yaml`; `health` is
`config/thesis_health_turku.yaml`. A rule with no thesis named is the same in all three.

## A. Project assumptions

**A1. One source of record for a company's facts.** For a Finnish company the PRH/YTJ register sets legal name, founding date, industry code and description, website, status and town. The declared list, Hilma and CORDIS may insert a company first, but `prh` re-reads every company that has a business ID and replaces those fields with the register's non-null values; a NULL never erases. Business Finland, tax registers, OpenAlex, the web archive and the ecosystem dataset only match companies that exist (the dataset inserts an unmatched company tagged `ecosystem`, outside the feed). The AI stitcher writes no company field, only checked signals (A17). The repo holds no ranking among Business Finland, Hilma, CORDIS and the declared lists; they do not compete, because only the register overwrites. Town comes only from the register address (visiting address, else postal; abroad stays NULL). For Norway the register supplies founded, code and status and the declared name stays.
*Example:* the declared list names Arctic Fry Oy; the register then gives founded 2020-10-23 and code 03220 (EVAL.md). *Where:* `radar/emit.py` `upsert_company`; `radar/adapters/prh.py` `_refresh`; `radar/build.py` PHASE; `radar/town.py`; `radar/nordic.py` `import_cohort`.

**A2. What a "startup" is (wide intake).** A company enters intake when its PRH company form is 16 (limited company) or 14 (cooperative), never a sole trader or partnership; its industry code starts with 03, 26, 27, 28, 29, 30, 582, 62, 63, 71 or 72, or is a code under `industry_codes`; and it has `min_signals: 1` startup signal of type first_sales, first_hire, eu_project, eu_grant, research_output, bf_funding, startup_notice, equity_event or public_funding, never the register entry. It enters on that signal's date. Intake says nothing about sector fit: the row reads "Thesis fit: no public evidence yet" until evidence appears. `health` uses prefixes 21, 26, 32, 62, 63, 72 and has neither 582 nor 03.
*Example:* Sireness Oy (72100) entered on 2025-09-29, rank 20 of 103 new 2025 companies in family 72 (EVAL.md). *Where:* `intake:` in each thesis file; `radar/intake.py`; `/method#intake`.

**A3. Listed companies are left out.** A legal name with Oyj or Abp among its last two words is left out of the feed and the intake tier; the footer and `/method#left-out` print how many.
*Example:* "Solar Foods Oyj" is left out, "Oyjala Boats Oy" is not (`tests/test_round3.py`). *Where:* `radar/store.py` `LISTED_FORM_WORDS`, `is_listed_company`; `radar/intake.py`.

**A4. Human-health practice is not health technology (`health` only).** Companies whose industry code starts with 86 (clinics, physiotherapy, medical specialists) are left out of the feed and the intake tier; 86900 is off its code list. The blue files exclude no code prefix. Now 30 companies on `health`: 1 main, 29 weak (README.md).
*Example:* a clinic under code 86xxx never appears; code 32500 still does. *Where:* `feed_exclude_code_prefixes` in `health`; `store.excluded_code`; `/method#left-out`.

**A5. Strong versus weak feed row.** A row is strong (main list) only when the stored record shows at least one reason: the industry code is on the thesis list, a thesis word is in the registered line of business, a thesis word is in the source's own text (Hilma notice title, CORDIS title and objective, BlueInvest profile text; our own `detail` annotations are never read), or a thesis word in the legal name is corroborated by a record from a different source family (A6). Every other row is weak and stays in the closed Weak list. A name word alone never admits a company. On 17 Oct: 122 companies, 30 main, 92 weak (README.md).
*Example:* code 30110 (ship building) alone is strong; the word "marin" in Sub Marine Store Oy backed only by a PRH tax-register record is weak. *Where:* `store.explain`, `REASON_IDS`; `/method#precision`.

**A6. Corroboration comes from a different source family.** `prh`, `prh_notices`, `prh_intake`, `prh_recent` and `tax_registers` are one family, the PRH registry, so a PRH record never backs another PRH record. A CORDIS, Hilma or Business Finland record does.
*Example:* a name word plus a PRH notice is weak; the same word plus a CORDIS project is strong. *Where:* `store.SOURCE_FAMILIES`, `CORROBORATION_RULE`; `/method#corroboration`.

**A7. Consultancy and research codes are never enough alone.** A code in a `code_alone_weak` family is a hint only: the row stays weak unless the line of business, the source text or a corroborated name word also backs it. Families: 711, 712, 721 in `thesis.yaml` and `baltic`; 702, 721 in `health`. A dot is ignored (NACE 71.12 is 711). Ship building, water and aquaculture codes are unchanged.
*Example:* a company registered only under 71121 reads "Weak: industry code 711xx alone; a consultancy code needs a sector word". *Where:* `code_alone_weak` in each thesis file; `store.code_alone_family`, `explain`.

**A8. Word matching.** A thesis word matches a whole word, or the start of a longer word when the thesis word has 5 or more characters; text is case-folded; `keyword_stop_words` blocks known false friends even as prefixes.
*Example:* `aalto` would prefix-match a surname, so `aaltonen` and `aaltola` are on the stop list. *Where:* `radar/fit.py` `MATCH_RULE`, `MIN_PREFIX`; `name_keywords`, `keyword_stop_words`; `/method`.

**A9. Confidence levels.** High: the source names the company or its business ID directly and states the date. Medium: matched by exact legal name or website domain, date stated by the source. Low: matched by name keyword or industry code only; shown, never counted in rankings. Register discovery never exceeds medium for a name word and is low for a code alone; the stitcher is high only when the business ID or legal name and a day or month are on the page. Declared research counts in the backtest only at medium or high.
*Example:* a PRH refresh of a known company is high; a new registration found by the code 39000 is low. *Where:* `radar/emit.py` docstring; `store.CONFIDENCE_RULES`; `radar/adapters/prh.py`; `/method` Confidence rule.

**A10. Readiness levels come only from the sponsors' frameworks, and unknown is never Low.** Technology = Aalto TRL 1-9, business = KTH BRL 1-9, investment = Investment Readiness 1-9 read from the ten Investment Potential dimensions, impact = the Ocean Impact Navigator category. Each level is a printed evidence-class rule over public records; no record in a class means no level, shown as "no public evidence". A BlueInvest profile's stated TRL wins over the rule TRL. We built no questionnaire scores.
*Example:* Arctic Fry Oy: business readiness 2 of 9 from the register entry; technology and investment "no public evidence". *Where:* `radar/frameworks.py` `BRL_MAP`, `TRL_MAP`, `IRL_MAP`, `page_levels`; `config/frameworks.yaml`; `/method#frameworks`.

**A11. Levels become Low / Medium / High through fixed bands.** TRL, BRL and IRL: 1-3 Low, 4-6 Medium, 7-9 High; no level is unknown. Impact: a Navigator category found by rule is Medium; the dataset's own impact score is declared research and never sets a band. Thesis fit: industry code or own text High; line of business or corroborated name word Medium; legal-name word only Low; no reason unknown. The memo reads the same levels question 02 prints.
*Example:* a company with a BlueInvest-stated TRL 4 is Medium technology. *Where:* `memo.bands` in each thesis file; `radar/memo.py`.

**A12. The decision table runs in passes; the first match wins.** Pass 1: the team's 10 rows, an exact match on impact, business, investment and thesis fit. Pass 2: the team's rules a to g. Pass 3 (A13). Otherwise WATCHLIST. A cell that needs a band never matches "unknown", so a missing level cannot produce REJECT / LOW FIT; that needs evidence of low fit and low impact. Pass 3 exists only in `thesis.yaml`; `baltic` and `health` stop at pass 2, and `health` sets impact to `any`.
*Example:* Arctic Fry Oy: impact Medium, business Low, investment unknown, fit Medium gives WATCHLIST. *Where:* `memo.decisions` in each thesis file; `radar/memo.py` `decide`; `/method#memo-rules`.

**A13. The fallback applies only when the fit is more than an industry code.** When fit is High and impact is unknown, impact is read as Medium, implied by the sector, and rules c1 (business Low or Medium, TRL 1-3: GRANT SUPPORT), c2 (business Low or Medium: ACCELERATOR), c3 (business and investment High: DUE DILIGENCE) apply. The gate `requires_any` needs one of: a declared cohort or portfolio member, a fit reason from the source's own text, the registered line of business, or a corroborated name word. A code-only company stays WATCHLIST ("fit rests on the industry code alone").
*Example:* Viva Jets Oy reads ACCELERATOR, "because: fallback c2, impact implied by sector". *Where:* `memo.decisions.fallback` in `thesis.yaml`; `memo.fallback`, `SUPPORT_KEYS`; `/method#memo-fallback`.

**A14. Declared cohort and portfolio members get at least Medium thesis fit.** They were selected into the programme. `declared_member_band: Medium` is in all three files; question 01 reads "declared cohort company", never "no public evidence yet".
*Example:* Arctic Fry Oy has no code, line of business or source text that shows fit, and still reads Medium. *Where:* `memo.bands.fit.declared_member_band`; `memo._fit`.

**A15. Countries per thesis.** `thesis.yaml`: FI, depth "registers+contracts+grants". `baltic`: FI, SE, EE, LV, LT, DK, NO, DE, PL; national depth only for FI, EE (register+grants) and NO (register); DK looks up by name or CVR number only; SE is a connector slot; LV, LT, DE, PL are "EU sources only". `health`: FI. EU-wide adapters (TED, CORDIS, EU grants, BlueInvest) run for every listed country; TED skips a country whose depth lists "contracts", so no award is counted twice, and adds only micro and small winners as new companies.
*Example:* TuniSea (NO) is dated by the Norwegian register lookup; a Latvian company is reached only by EU sources. *Where:* `countries`, `country_depth`, `ted_cpv`; `radar/thesis.py`; `/method#countries`.

**A16. Companies only: person-shaped legal names are hidden.** A name of 2 or 3 capitalised words followed only by company suffixes, with at least one of Holding, Invest, Capital, Consulting, Tmi, Ky, is treated as a private person's. The feed hides it unless the company has a non-register signal (the footer counts them); the API listings, `/data`, the wide intake and the TED adapter leave it out. Words in `non_person_words` or the thesis keywords make it a business. No private individual is named anywhere; the ecosystem dataset's people fields are not imported.
*Example:* "Given Family Holding Oy" is hidden; "Blue Bay Oy" is not. *Where:* `radar/fit.py` `looks_like_person`; `non_person_words`; `radar/routes/api.py`; `radar/adapters/prh_intake.py`.

**A17. AI text is only a code-checked summary of linked sources.** The stitcher's LLM proposes; code keeps an event only if the fetched page names the company and prints the date, then re-fetches and confirms the quote, the name near it and the event words. Its events never move a company between backtest groups (A22). The AI brief (`radar/briefs.py`) is written in batch, and code drops any sentence whose URL, date, number or capitalised name is not in the company's export, or that uses praise a cited title does not hold; a brief with fewer than 2 slots left is dropped. The memo and every level use no LLM.
*Example:* batch of 17 Oct: 168 events passed check 1, 128 passed check 2, 29 emitted (EVAL.md). *Where:* METHOD.md sections 2 to 4; `radar/adapters/stitcher.py`; `radar/briefs.py` `verify_sentence`.

**A18. Date precision is labelled.** An event date is the day it happened, never the fetch date. A year-only source (Business Finland) is stored as 1 January with a `signal_meta` row `year` and printed "2026 (year only)"; a month-only date is stored as the last day of the month and labelled. A year-only record is never a feed entry signal and counts in the backtest as 1 January.
*Example:* Sub Marine Store Oy's Business Finland record reads "2026 (year only)". *Where:* `store.is_year_only`, `_date_fields`; `radar/schema/` `signal_meta`; `/method` Sources.

**A19. Amounts are EUR from the source, with no conversion.** `amount_eur` is filled only when the source states an amount in euros. TED is kept only when its currency field is EUR and the notice has one winner; CORDIS stores the EC contribution; Business Finland stores the export's total in euros. The repo has no exchange-rate code.
*Example:* a TED notice priced in SEK stores no amount. *Where:* `radar/schema/001_core.sql` `amount_eur`; `radar/adapters/ted.py`, `cordis.py`, `businessfinland.py`.

**A20. Refresh is narrow, guarded and switched off by default.** The `/data` Refresh button re-reads only the `refresh_adapters` (`prh_notices`, `prh_recent`; `baltic` defines none). It works on a copy, swaps it in with `os.replace` only after `PRAGMA quick_check` is ok, runs one at a time (lock stale after 1,800 s), waits a 600 s cooldown, and answers 403 unless the environment sets `REFRESH_ENABLED=1`.
*Example:* a failed step deletes the copy and the live store is untouched. *Where:* `refresh_adapters` in the thesis files; `radar/refresh.py`; MODULES.md.

**A21. The feed shows a company on its first counted signal in the window.** Window 90 days; one row per company; counted types are the dated public records a scout could have seen (22 types in `thesis.yaml`). Never counted: board_change (routine), capital_loss, sales_ended, employer_ended (negative), website_first_seen (a site existing is not traction). `baltic` counts only 7 types.
*Example:* a first_hire in the employer register counts; a board change does not. *Where:* `geography.feed_window_days`, `feed_signal_types`; `store._feed`.

**A22. The backtest counts a signal only if the feed rule would have shown the company.** Reference date 2026-01-01 (the programme start month, declared by the team, not an entry date); a register entry counts only if the company was at most 5 years old (`stage_max_company_age_years`). Four groups that always add up to 19: found earlier by live public records, found earlier only by declared research, found later, no public signal. Declared research and stitcher events are counted apart and never mixed into the live count. Result on 17 Oct: 0, 12, 6, 1.
*Example:* Arctic Fry Oy's 2020 first sales is on its page but is not counted (code 03220 is not on the list). *Where:* `radar/earliness.py` `rule_lines`; `/backtest`; EVAL.md.

**A23. Partner organisations are never shown as discoveries.** Any legal name starting A'Pelago, APelago, Redstone or Turku Science Park, and every name on `investors.csv` and `programmes_grants.csv` (71 names on 17 Oct), is left out of the feed, the radar and the intake.
*Example:* Redstone-named entities never appear as startups. *Where:* `store.PARTNER_PREFIXES`, `is_partner_org`; `/method#partners`.

**A24. Declared research is labelled and never sets a level.** Events from the ecosystem dataset carry "declared research (date)" and the dataset's own confidence; low-confidence rows are leads. Its free-text summaries and people fields are not imported. It adds evidence beside a readiness level and never changes one.
*Example:* the 12 cohort companies found "only by declared research" are a separate backtest group. *Where:* `radar/adapters/ecosystem.py`; `/method#ecosystem`; `frameworks.page_levels`.

**A25. Empty is empty.** A missing value stays NULL and is drawn as a hatched chip ("not in public records", "no public evidence"); no level, date or number appears without a record and a public source link behind it.
*Example:* Taikoa Oy has no counted signal and its backtest lane stays blank. *Where:* CLAUDE.md; `radar/emit.py`; ARCHITECTURE.md "Empty is empty".

**A26. Public contracts: a young company's first win, or any win for a declared company.** A Hilma award signals a discovery company only if its CPV division is in `hilma_cpv_divisions` or its title holds a `hilma_keywords` word, and the company was at most 5 years old at the award; a cohort or portfolio company counts on any win. Rows whose notice has no verified public page are skipped.
*Example:* a company registered 3 years before its first in-category award counts; one registered 8 years before does not. *Where:* `radar/adapters/hilma.py`; `hilma_*` keys; `geography.stage_max_company_age_years`.

**A27. Fetch etiquette and honesty lines.** Network adapters send 1 request per 2 seconds (OpenAlex 1 per second), cache raw responses under `data/cache/<name>/` and use the project User-Agent. Nothing is scraped behind a login; LinkedIn, Dealroom, Crunchbase, PitchBook and Tracxn are shown only as "connector slot, not connected" and the stitcher refuses them.
*Example:* Sweden's Bolagsverket has no free API and is a connector slot. *Where:* CLAUDE.md code contract; `radar/adapters/_fetch.py`; `/method` Connector slots.

**A28. Field candidates are kept, not chosen.** Every value a source states for a company's name, founded date, industry code and description, town, website, register status or country is kept in `field_candidates` with its source, link, date read and basis, beside the value live pages show (A1). Two candidates agree under one rule per field: names by the folded name key (diacritics, case, legal-form words and punctuation removed); founded dates at the coarser of the two precisions; industry codes by digits only (NACE 10.890 is 10890); websites by host without `www.`; towns with diacritics and a bracketed note folded away; descriptions only within one language; status words mapped to active, ended, bankrupt or unknown. A company field with two or more groups of agreeing values is a conflict and goes to the next question batch.
*Example:* the ecosystem dataset's founding year 2018 agrees with PRH's 2018-10-11 for Awake.AI Oy; "Piikkio (Kaarina)" and "Piikkiö" name one post office. *Where:* `radar/candidates.py` `norm`, `same`, `clusters`; `radar/schema/060_field_candidates.sql`; `python3 -m radar.candidates build` (on a store copy).

**A29. Country codes are ISO 3166-1 alpha-2.** Every stored country is a two-letter upper-case ISO 3166-1 alpha-2 code. A country name in a list is mapped through one table, and a name missing from it gives no code, never a guess. An empty country in the ecosystem dataset is read as Finland, as the dataset's own scope is Finland.
*Example:* BlueInvest's "Finland" is stored as FI; "United States" as US. *Where:* `radar/formats.py` `ISO_COUNTRIES`, `country_ok`; `radar/adapters/ecosystem.py` `COUNTRIES`.

**A30. A company key is its Business ID when it has one.** A Finnish company's key is its Business ID, written NNNNNNN-C with a valid check digit. A company without one gets `<country>-<slug>` from the declared list, `name:<slug>` from a source that names it without an ID, or, when found in the Norwegian or Danish register's live window, the register's prefix and its organisation number (`radar/nordic.py` `import_rows`). A key never changes once written, so a later Business ID for a `name:` company is a duplicate to merge (QUESTIONS_B1.md, B1-12), not a rename.
*Example:* Arctic Fry Oy is `3166759-6`; TuniSea is `no-tunisea`; Hailia Nordic Oy is `name:hailia-nordic`. *Where:* `radar/formats.py` `business_id_ok`; `radar/adapters/declared.py` `slug`; `radar/adapters/ecosystem.py`; `radar/nordic.py`.

**A31. An open question never changes a live value.** When no assumption decides a case (sources disagree with no rule covering it, a value contradicts an assumption, an outlier, dates out of order, a company that is both startup and investor, a possible duplicate, a link that redirects to another company, an unexpected calculation, a new rule needed), it is asked in a numbered batch (`QUESTIONS_B<n>.md`: issue ID, affected records, problem, options A/B/C with sources, recommendation and why, other records affected). The competing values are marked `PENDING_DECISION` with the issue id in `field_candidates` only; live pages keep A1. An answer becomes the next D number, applied to every matching record including those already processed, with the count changed. One issue type is never decided two ways.
*Example:* B1-06 asks whether Redkik Oy is the Finnish subsidiary or the US group; until then the page shows FI and Joensuu. *Where:* `radar/candidates.py` `OPEN_ISSUES`, `mark`; `radar/stop_and_ask.py`; `QUESTIONS_B1.md`.

**A32. Every rule-driven change is logged with its rule.** A tool that changes records under a rule appends an entry to `provenance` citing the A or D id, with the records affected; a dated decision is recorded with its commit and the counts the repo states. An entry citing an id that is not in this file fails the consistency check.
*Example:* each `radar.candidates build` run logs an A1 entry with its row and conflict counts. *Where:* `radar/provenance.py`; `radar/schema/061_provenance.sql`.

**A33. Nothing is delivered until the consistency check passes.** Before a ZIP, a deploy or a store swap, `python3 -m radar.consistency` runs read-only over each store and all eight checks print PASS: no PENDING_DECISION on an applied value; every signal's confidence is what its adapter's rule gives; every signal type and source has a label; every date is ISO 8601 with a precision; every Business ID has a valid check digit; every country code is ISO 3166-1 alpha-2; every amount is EUR; every provenance entry cites an id in this file. A FAIL is fixed or asked, never waived.
*Example:* the blue and health snapshot copies pass 8 of 8 (17 Oct). *Where:* `radar/consistency.py`; `tests/test_consistency.py`.

**A34. A ranking explains itself in words.** Any ranking the product shows (matchmaking today) lists the reasons that hold, each as a short chip and a sentence with the record behind it, and lists what did not hold with its note; it never shows a single number as the headline, and its API has no score field. A reason that cannot be said in words with a source is not a reason. Numbers in a reason are dates, TRL or age windows, counts with their total ("2 of 20 declared companies") or codes, never a bare figure.
*Example:* "Same sector: ship design and propulsion. The startup shows it through its industry code 30120 (building of pleasure and sporting boats) and its own text naming 'hull'; Business Finland through dataset capability tag C2." *Where:* `radar/matchmaker.py`; `tests/test_matchmaker.py` (no score key, no bare numbers). *Why:* the data partner's rule for any ranking, 17 Oct ("Climate focus, Seed stage, Baltic region, Ticket size match" good, "AI score = 92" bad).

## D. Decisions

**D1. 2026-10-16 20:23Z (eb1c749, implemented 98c4e1e 21:16Z). Levels use the sponsors' frameworks.** *Rule:* TRL 1-9 (Aalto), BRL 1-9 (KTH, not 1-5), the Navigator category, and ten investment dimensions; afaa4fb (23:25Z) declined the team's own 0-20 rubrics (TASKS.md amendments; the first is headed 20:50Z, git time is used here). *Why:* the official written brief names them. *Affected:* every company's readiness lines; no count stated. `readiness.business.scale` in the thesis files still says "1-5 commercial readiness"; the page prints BRL 1-9.

**D2. 2026-10-16 21:34Z (11970db). Feed precision.** *Rule:* own-text reasons read only the source's stored text, keywords match whole words or 5+ character prefixes with a stop list, name-only matches are weak, person-shaped holding names are hidden. *Why:* VERIFY_night2 D-N1 (f92d137): CORDIS rows entered the main list because our own annotation was read as project text, 11 rows. *Affected:* blue main 39 to 31, weak 55 to 62 (1 hidden); health main 37 to 34, weak 23 to 26 (commit message). API listings hid person-shaped names from 22:58Z (baad087).

**D3. 2026-10-16 22:16Z (64c39bb). The backtest uses the feed's own rule.** *Rule:* A (A22). *Why:* judge review item 1: "5 of 19" were counted by register-entry date alone and their codes (46900, 70200, 47279, 62100, 72100) are not on the list (`tasks/cloud/backtest_fix.md`). *Affected:* snapshot earlier 5, later 1, none 13 became live 0, declared 0, later 1, none 18; with local tax-register and ecosystem runs 1, 12, 5, 1 (0ef14d2).

**D4. 2026-10-16 22:46Z (0ef14d2). Counted and refused signal types.** *Rule:* counted startup_notice, equity_event, research_output, website_milestone, eu_grant (plus first_sales, first_hire); refused board_change, capital_loss, sales_ended, employer_ended, website_first_seen, each with a written reason on `/backtest`. *Why:* a counted type must be a dated record a scout could have seen (EARLINESS_AUDIT.md section 2). *Affected:* no group moved; the cohort's only new-type rows were 4 startup_notice and 15 board_change on companies the rule does not admit.

**D5. 2026-10-16 22:58Z (baad087). 72190 removed from the thesis codes; 72100 not added.** *Rule:* `industry_codes` in `thesis.yaml` and `baltic` carry neither. *Why:* PRH returned 0 companies under 72190 and 30 under 72100 for registrations 2026-07-18 to 2026-10-16 (an upper bound), and the audit's likely explanation is that PRH re-registered main business lines on 2026-01-01 under a new code set (EARLINESS_AUDIT.md sections 4, 5; the audit proposed keeping 72190, baad087 dropped it). Adding 72100 was proposed in 0ef14d2 and "NOT applied": it would move Sireness Oy to found earlier (live 0/0/1/18 to 1/0/1/17) at up to about 30 low-confidence feed rows per 90 days. The repo records no separate judge ruling; no commit adds 72100. *Affected:* Sireness Oy (3568392-1); it is reached instead by wide intake (A2). `baltic` `nace_codes` (Norway, Denmark registers only) keep NACE 72.19 and 72.10.

**D6. 2026-10-16 22:58Z and 23:14Z (baad087, 5a114ac). TOL 2025 marine codes.** *Rule:* 03211 and 03111 replaced by 03210 (marine aquaculture) and 03110 (marine fishing) in the Finnish lists; the Baltic file also keeps 03211 and 03111 as "Estonian EMTAK code". *Why:* the commit names 03210 and 03110 the TOL 2025 codes, and the audit ties the change to PRH's 2026-01-01 re-coding; the Estonian register has its own codes (its basic-data file carries none today, `estonia_register.py`). *Affected:* 12 earliness and backtest tests that used 03211 (fixtures moved to 03210); no company count stated.

**D7. 2026-10-16 23:15Z (f78f668). Wide intake.** *Rule:* A2, shown as a third feed tier "New startups, no thesis evidence yet" under Main and Weak. *Why:* the feed let in only companies that already sounded blue; Sireness (72100) never qualified (`tasks/cloud/jx28_wide_intake.md`). *Affected (store copy, 93798f5):* 50,480 companies examined, 19,027 passed the form and code test, 15,584 new, 41,220 signals; 2 of 19 cohort companies entered before cohort entry; of the other 17, 11 have no business ID and 6 have a code outside the families (46900, 03220, 47279, 58290, 70200).

**D8. 2026-10-16 23:19Z, 23:22Z, 23:33Z (17f5cee, 341ea51, fd4c16b). Stitcher limits.** *Rule:* programme_entry, award and funding_round are emittable (the chief's decision); every other kept type stays in `stitch_log`; a second code pass re-fetches each page; stitcher events never enter the four backtest groups. *Why:* an LLM may propose but code decides (A17). *Affected (batch of 17 Oct 00:18Z):* 54 companies, 175 proposed, 168 kept, 128 confirmed (refuted: 25 type not in quote, 12 company not near quote, 3 year not near quote), 29 emitted, 99 logged only; 1 of 19 cohort companies archived before the reference (VesselChain). EVAL.md also reports 27 stitcher signals in the live store; the two figures are not reconciled in the repo.

**D9. 2026-10-16 23:28Z to 23:35Z (0b3c241, a2b8eb6). The team's decision table.** *Rule:* A12 and A11, with unknown never Low. *Why:* the team's decision-rules doc (TASKS.md amendment 23:40Z): every company ends in exactly one of seven outcomes. *Affected:* every company page; investment readiness by dimension count could reach 4 of 10 at most from today's sources (a2b8eb6), so it was mostly Low or unknown until D16 changed the band.

**D10. 2026-10-16 23:35Z (a2b8eb6). Declared members get at least Medium fit.** *Rule:* A14. *Why:* the commit calls it a deviation from the chief's mapping; they were selected into the programme. *Affected:* the 19 cohort and 9 portfolio companies (28); question 01 shows the line from 02:41Z (ce502ed).

**D11. 2026-10-17 01:18Z (0cbe141). Intake families 582 and 03 added, labelled in-sample.** *Rule:* `code_prefixes` gain 582 (software publishing) and 03 (fishing and aquaculture) in `thesis.yaml` and `baltic`, not `health`; the `tuning_note` is printed on `/method` and `/backtest`. *Why:* the backtest showed the net missed Kilocode (58290) and Arctic Fry (03220), so their result is measured on the companies used to tune the net. *Affected:* intake before cohort entry went from 2 of 19 (store copy) to 4 of 19 on the live store (Sireness 1 of 104, Arctic Fry 3 of 16, Kilocode 3 of 8, Emission-Eye 132 of 1,176 by rank and pool size, EVAL.md; the earlier "median rank 3 of 60" was withdrawn, D25); 16,385 `prh_intake` signals live (README.md).

**D12. 2026-10-17 02:30Z (ada70c5). Corroboration must come from a different source family.** *Rule:* A6. *Why:* judge round 3: Sub Marine Store's only hit was "marin" plus a PRH tax-register record from the same registry. *Affected:* backtest live headline 1 of 19 to 0 of 19 (0, 12, 6, 1). Feed 123 companies (70 main, 53 weak) to 122 (36 main, 86 weak); the two counts were measured before and after the rule together with the data swap (6ac05bc, README.md), so the change is not the rule alone.

**D13. 2026-10-17 02:31Z (8944ff2). Listed companies left out.** *Rule:* A3. *Why:* judge review round 2 item 9: a listed company is not an early signal. *Affected:* the live count is printed in the feed footer and `/method#left-out`; the repo states no fixed number.

**D14. 2026-10-17 02:31Z (8944ff2). Human-health practice (TOL 86) left out of `health`.** *Rule:* A4. *Why:* clinics matched on "medical" in the line of business; care delivery is not health technology (judge review 2 item 9, as the thesis comment cites it). *Affected:* `health` feed now 30 companies, 1 main, 29 weak; the health swap test moved to code 32500 (d7df036).

**D15. 2026-10-17 02:31Z (8a88193). Norway imported into the Baltic thesis only.** *Rule:* Norwegian live-window rows enter a thesis only when NO is one of its countries; cohort matches enter every thesis. *Why:* the commit gives none; the adapter docstring ties the live window to NO being an active country of the thesis (A15). *Affected:* 1,289 limited companies fetched for 17 Oct 2025 to 17 Oct 2026 (948 by NACE prefix, low; 341 by name word, medium); TuniSea found as TUNISEA AS (936277241), one exact name match (efd042d). Denmark: 1 of 6 cohort lookups answered before the daily limit (c66e1aa).

**D16. 2026-10-17 02:38Z (7413623). Bands read the page levels, and the fallback is added.** *Rule:* the memo's bands read exactly the levels question 02 prints (TRL, BRL, IRL, Navigator category), replacing the count of investment dimensions; pass 3 adds c1 to c3 (A13). *Why:* the memo must never say a level the page does not show (`radar/memo.py`); with fit High and impact unknown no table row can match, so every such company fell to WATCHLIST, and the fallback reads impact as implied by the sector and prints that it did (`thesis.yaml` comment). *Affected:* on the live copy 911 companies would read ACCELERATOR before the gate (D18).

**D17. 2026-10-16 23:04Z, 2026-10-17 00:19Z, 02:42Z (9da6080, 431df23, faf5a9b). Person names redacted in stitcher output.** *Rule:* stored quotes, then the LLM's own logged queries, then everything the company page prints from the stitcher go through the redactor: two or more consecutive capitalised name-shaped words that are not in the legal name or the thesis business words become `[name redacted]`. *Why:* a batch answer held a query with a private person's surname (431df23); over-redaction is the accepted cost. *Affected:* the stitcher block on every company page; no count of redacted strings is stated.

**D18. 2026-10-17 03:09Z and 04:35Z (79ac042, 0c19d90). The fallback gate.** *Rule:* A13. First gate (declared member, own text, corroborated name word): 911 to 3 ACCELERATOR on the live copy. Then the registered line of business also counted as more than a code: 245 ACCELERATOR on the live store. *Why:* a High fit that is only a coarse industry code must not carry a recommendation. *Affected:* 911 to 3 to 245 ACCELERATOR (the commit messages call the first a "live copy", the second the "live store"); code-only companies stay WATCHLIST.

**D19. 2026-10-17 02:00Z and 02:44Z (7667e78, 1754936). Demo examples: Viva Jets and Arctic Fry replace Kelluu.** *Rule:* the judged documents, the search placeholder, MODULES.md and the demo path use Viva Jets Oy (2962040-6, portfolio) and Arctic Fry Oy (3166759-6, cohort). *Why:* no commit message says why Kelluu left; DEMO_SCRIPT.md gives each company's role: Arctic Fry is the honest miss (first sales in 2020 not counted), Viva Jets has code 30120 on the list, share issues and Business Finland funding with links. *Affected:* README, DEMO_SCRIPT, MODULES, three templates and `tests/test_ease.py`; Kelluu stays on `/radar` and in the stitcher counts.

**D20. 2026-10-17 06:15Z (011e7ed). Consultancy codes alone demoted to weak.** *Rule:* A7. *Why:* such a code "is a hint that the company could be in the sector, never evidence on its own" (`code_alone_weak` comment). *Affected:* live-store copy, main 36 to 30 and weak 86 to 92; six companies moved: eSuunta, SU Engineering, Valavia, JSL Konsultointi, MittaTopi, ICEYE.

**Notes added in this register to D1 to D20** (the entries above are as ASSUMPTIONS.md has them):

- D1: the thesis label `readiness.business.scale` reads BRL 1-9 since 69b8e3e (2026-10-17 08:26Z, main), so the mismatch the entry notes is closed.
- D2: the reason for hiding person-shaped names is VERIFY_night2.md D-N7 ("a reviewer may read it as a named individual"); D-N1 is the reason for the CORDIS own-text part. The rule's marker words are explained in 11970db: a plain two-word name with a company suffix cannot be told from a business name.
- D12: JUDGE_REVIEW2.md item 2 counted 33 of 57 main rows resting on a same-registry corroboration; ARCHITECTURE.md read "40 of the 70 main-list companies carry the corroborated-name reason" (7667e78) and "0 of the 36" after (6ac05bc).
- D15: the reason is written at the import in `radar/adapters/brreg.py`: live-window rows belong to a thesis that covers Norway; cohort matches are imported for every thesis.

**D21. 2026-10-17 08:31Z (d4409fc, Dayo via the chief). Governance work is additive.** *Rule:* field candidates, provenance, the stop-and-ask list and the consistency check live in new tables (`field_candidates`, `provenance`) and new files; no existing table, column, template, stylesheet or feed, memo, matching, readiness or intake rule changes; open questions mark candidate rows only (A31). *Why:* "it must not affect what is being built" (Dayo, relayed by the chief for task jx40). *Affected:* no live record changed. On the blue snapshot copy, 5,357 candidate rows were written and 57 marked PENDING_DECISION; the health snapshot copy got 3,185 rows, 11 of them pending.

**D22. 2026-10-17 10:50Z (7ef08c0). Water, waste and remediation codes read Medium thesis fit.** *Rule:* A7, `memo.bands.fit.medium_codes` in `config/thesis.yaml`: industry codes 36, 37 and 39 are municipal utility codes, a sector match and not a High fit on the code alone; the company's own text still lifts a code match to High. *Why:* judge dry-run 2: four utilities read ACCELERATOR on a sewerage or water code alone. *Affected:* those four companies drop from ACCELERATOR to WATCHLIST. The Aava feed reader applies the same rule (`aava.code_only_skip`, `memo.code_only_fit`, families read from the thesis file): it does not name a feed row whose fit rests on a code in these families alone, and the feed list and its counts are unchanged.

**D23. 2026-10-17 11:40Z (fix/judge2). A company's own name is never redacted.** *Rule:* A16, D17. The person-name redactor (`radar.fit.redact_person_names`, and the stitcher's write-time `redact_people`) leaves alone the company's own name and its former names (`field_candidates`), the legal-form words (Oy, Oyj, Ab, osk, Ltd, GmbH ...), the possessive ("Kelluu's"), every cohort, portfolio, ecosystem and feed company in the store, and the investor, buyer and programme lists the thesis declares (`radar.names.known_names`). A register-intake name that could be a private person's (one word, or two or three plain name words) is kept only with its legal-form word beside it, so "Pekka Virtanen said" still hides a person when a "Pekka Virtanen Oy" is in the register. Text in brackets and lower-case fragments of a declared name are not names. *Why:* the Viva Jets page printed "[name redacted]., founded in Oulu in 2018" for "Snowsus Ltd." (the company's former name, and "Ltd" was not a legal-form word). *Affected:* on the live copy, 54 stitcher blocks: stored `[name]` markers 262 and `[name redacted]` 1, in 208 texts (stitch_log 199, signals 9, briefs 0); one is a wrongly hidden company name (Suomen Vesistökunnostus Oy, in an LLM query) and `python3 -m radar.repair_redaction` restores it; at render time 147 markers become 136 (Snowsus Ltd., Kelluu Canada Ltd., Suomen Vesistökunnostus). The other 262 stored markers hide organisations and events that are not in the store (Wave Boat Poland, Uber Freight, Venture Kick ...; 11 of the texts have no saved original to check); over-redaction stays the accepted cost. 

**D24. 2026-10-17 10:50Z (7ef08c0). No raw token on a company page.** *Rule:* A25. The register type code ("type 6_80"), the stemmed keyword ("keyword 'marin'"), capability codes (C3, C10) and the category name printed as an impact level are fixed where they are made, not hidden at print time. *Why:* judge dry-run 2. *Affected:* tax-register details, the category keyword, the capability labels and the Ocean impact key statistic on every company page.

**D25. 2026-10-17 11:45Z (fix/judge2). The backtest states a rank beside its own pool, never a median.** *Rule:* A22. `/backtest` prints each early company's rank and intake size as one pair ("Sireness Oy 1 of 104, Arctic Fry Oy 3 of 16, Kilocode Oy 3 of 8 and Emission-Eye Oy 132 of 1,176"); `intake.summary` no longer computes a median rank or a median pool size. *Why:* "median rank 3 of 60" paired a median rank with a median pool size, two numbers that belong to no one company. *Affected:* the `/backtest` intake headline, EVAL.md, D11.

**D26. 2026-10-17 11:50Z (fix/judge2). Every sector's home list is warm, and no request waits more than 3 seconds for it.** *Rule:* `radar.home_list.warm_all` builds the grouped home list of every `config/thesis*.yaml`, the default first, in one background thread at start; a list that is not cached is built once in the background and a request waits for it at most 3 seconds, then gets the plain feed with the line "The grouped view of this sector is still being prepared". *Why:* `/?thesis=baltic_blue` took 70 s on the first load after a restart. `store.is_partner_org` also folds the declared names once per file version instead of once per call (66,689 calls in a baltic_blue build; identical answers on all 17,270 names checked): the build takes 7 s on the live copy, 14 s before that change on the same machine. *Affected:* the first load of every sector after a restart or a store refresh.

**D27. 2026-10-17 12:05Z (3de21f9, renumbered from D22 at merge; amended at the gate: rungs 1-2 carry no band and read "not yet evidenced", per the A'Pelago note that missing information is not a low score; Dayo via the chief). Ocean Impact Readiness is evidence readiness, nine rungs, applied by code.** *Rule:* the Ocean Impact Assessment (`radar/ocean_impact.py`, attached as `memo["ocean_impact"]`, `/api/company/<key>` and the combined file's `radar_ocean_impact`) gives an impact area in words and a level of 9 from the ladder in `impact_readiness.levels` of the thesis files: 1 to 2 sector implied only (industry-code family, registered line of business, a legal-name word backed by a second source family, all from the trade register); 3 to 4 the source's own text names the area (A5's own-text sources: Hilma title, CORDIS text, BlueInvest profile); 5 to 6 a second independent source family names it (A6) and a blue programme or portfolio page (`programme_hosts`) lists the company; 7 to 8 declared research holds an impact assessment (an Ocean Impact Readiness reading with evidence text) or a quantified outcome with a stated method (reading at or above `measured_min_score`); 9 a measured outcome from an official or register source. The highest passing rung wins; a company with no record naming an area has no level, never a guessed one. Confidence is high when two or more independent source families agree, medium for one family that is more than the sector implied, low otherwise. Bands: 1 to 2 Low, 3 to 7 Medium, 8 to 9 High (High needs a measured outcome on record, so an assessment alone stays Medium). Scalability is stated only from a register in more than one country, an EU-level programme record or the source's own text about markets, else "not assessed from public records". *Amends A24 for this ladder only:* declared research may set rungs 7 and 8, labelled as declared research, and only when the dataset's own confidence is medium or high (a low-confidence reading is listed as a lead and sets nothing); it still never sets a TRL, BRL or IRL level. *Why:* the data partner's review of the live site (ocean impact "may feel secondary", "don't make Ocean Impact Readiness just another score": show impact area, evidence, scalability, readiness x of 9 and confidence) and the owner's "make ocean impact a headline"; the Navigator is login-walled and defines KPIs, not levels (D1), so a ladder that says which record must be on file is the only level the records can carry. It measures how well the area is evidenced, not true impact (METHOD.md section 7). *Affected:* additive (D21): no decision-table band, verdict, feed, matching or other readiness level changes; the company page and the home rows show the assessment, and the verdict's explanation is five plain-word bullets from the memo's why lines. On a copy of the live store (17 Oct, the 58 home-list companies): level 1 for 25, level 2 for 1, level 5 for 3, no level for 29; confidence high for 3 and low for 55. No company reaches rung 6 or higher: of the 11 companies with a declared-research reading, 9 are low confidence and 2 (medium) have no named area, and a reading alone never names an area.

**D28. 2026-10-17 12:20Z (059bd6c, renumbered from D22 at merge). Matchmaking hard filters.** *Rule:* a counterpart is listed for a startup only if (1) its kind is one the startup's verdict path meets (`matching: path_kinds`: ACCELERATOR, GRANT SUPPORT and WATCHLIST meet accelerators, programmes and public funders or foundations; DUE DILIGENCE and INVEST meet investors; PARTNER INTRODUCTION meets clusters; REJECT / LOW FIT none) or is a pilot partner (`always_kinds`: corporates and ports, for every path); (2) the geography it declares, read into country codes through `matching: regions`, includes the startup's country (nothing declared, or text with no readable place, or an unknown startup country, filters nothing and is said); (3) it is open (a closed programme or a passed deadline is out), and no stated TRL window, age limit or stage window excludes the startup; and it holds at least one topic reason (sector, shared words, lookalike), or, when its declared text names no sector, a satisfied readiness window. A counterpart whose declared cohort or portfolio holds the startup is "already connected" and not listed. *Why:* the partner brief ("Hard filters: counterpart type fits the startup's verdict path ... geography the counterpart declares"); filter three repeats what `radar/matching.py` already does for programmes (a TRL outside the window, a company older than the limit, a closed call are left out), so the two blocks on the company page never contradict each other; WATCHLIST meets the support kinds because the owner's brief names no path for it and nothing is committed to a watchlisted startup. *Affected:* new code and files only; no existing record, table, feed, memo or "who comes next" rule changes (D21). On the live copy 15,511 startups are matchable; Viva Jets (ACCELERATOR) has 56 counterparts after the filters.

**D29. 2026-10-17 12:20Z (059bd6c, renumbered from D23 at merge). Matchmaking reasons, weights and thresholds.** *Rule:* six reasons with configured weights (`matching: weights`): sector or impact area 3, portfolio lookalike 3, shared words 2, readiness window 2, timing 1, geography 1. Rank = weight of the satisfied reasons, then their number, then the evidence behind sector and word reasons, then the nearest deadline, then name; a counterpart's declared members come first in its own view. Lookalike: at least 2 of the counterpart's declared companies in our store, and at least 15% of them, share the startup's industry group (first 3 digits of the code); age band and country are shown beside it. Shared words: at least 2 raw word stems (first 6 letters) in both texts, outside the keyword groups, not in the stop list, and in no more than 3% of the counterparts' texts or 1% of the startups' texts. Timing: a stated deadline within 90 days. A broad keyword group (software, hardware: `needs_structure`) counts only with an industry code or dataset tag behind it and is never enough alone. Org view: a cheap first pass over every company, then the best 300 profiled in full. *Why:* topic evidence outranks the conditions a place or a date can satisfy; one shared word or one of twenty portfolio companies is a coincidence, so the thresholds, found by reading junk matches on the live store (in-sample, no ground truth exists); the weights are a stated hypothesis for the partners to rate (docs/MATCHING.md section 5). *Affected:* new code and `config/thesis.yaml` `matching:` keys only.

**D30. 2026-10-17 12:20Z (059bd6c, renumbered from D24 at merge). Counterpart demand is declared plus revealed, and organisations only.** *Rule:* an organisation's demand profile is its declared text, stages, geography, ticket, window and deadline (`investors.csv`, `programmes_grants.csv`, `corporates_clients.csv`, the ecosystem dataset's accelerator, investor, public funder, cluster, corporate and port rows, the programme windows in the thesis file), and its revealed cohort or portfolio in our store (the declared cohort and portfolio file mapped by `matching: revealed_groups`, the dataset's portfolio and investor tables, and its dated rounds). A round's counterparty counts only when it names a listed organisation or a configured alias; any other name, in particular a person, is dropped and never stored. The dataset's `person` table and contact or note columns are never read; free text shown or read passes through the person-name redactor (D17). A programme reads lookalikes from the organisation that runs it but does not claim its cohort; a fund of a listed investor merges into it. An organisation with no declared text is shown as "demand is revealed from its portfolio only" or "no declared text". *Why:* companies and organisations only, never named private individuals (CLAUDE.md); the owner's brief ("what the companies or organisations or VCs or investors usually work with"). *Affected:* new code only; live count 191 organisations, 14 with a declared cohort or portfolio in the store (67 links).

**D31. 2026-10-17 (fix/feed_and_orgtext). An organisation's declared description never shows a redaction marker.** *Rule:* the person-name redactor runs first (D17, D23). Where a declared description is shown (`radar.matchmaker_orgs._focus`: the `/match` list and org view, `/api/match/orgs`, `/api/match/org/<id>`, and the counterpart rows of `/api/match/company/<key>` behind the company page's Next steps) every sentence or semicolon-separated clause that holds a marker is dropped whole (`radar.fit.drop_redacted_clauses`) before the line is cut to 150 characters; a full stop after "incl.", "e.g." and similar does not end a sentence. When nothing is left the organisation type (its kind label) is shown alone; an organisation that declared no text keeps "no declared text". In the write-time redactor an apostrophe inside a capitalised word is part of the word (`stitcher._CAP`), so "A'Pelago Industries" is one run and is never cut to "A'[name]". *Why:* the live page printed "Ranked 5th in the 2025 Startup [name redacted] (behind Shell, DNV, Maersk...", "founded by University of Turku, [name redacted], TUAS or Novia people" and "Sessions Feb-Apr 2027, [name redacted] 2027": the redactor also hides venue, place and organisation names, and a gap inside a sentence reads as broken. Dropping the clause keeps D17 (no private person's name is printed) at the cost of showing less. *Affected:* display only; matching reads the declared text, not this line. On a copy of the live store (17 Oct): markers on `/match` 16 to 0; 19 of the 191 descriptions change and 5 show the type only (A'Pelago, the Kymenlaakso and Southwest Finland wellbeing areas, the Ministry of the Interior, Skyborn Renewables). Stored text is not rewritten: 8 `stitch_log` quotes already hold "A'[name]" and stay as they are (no page in this change prints them).

**D32. 2026-10-17 (feat/filters_inplace). Filtering never leaves the home page: one state in the URL, and only the list section is swapped.** *Rule:* the home list's filter state is its URL query (verdict, impact, trl, brl, irl, fit, country, sector, age, source, deadline, member, group, for; the old `src` is read as `source` and an old `group=cc-FI` as the country filter), parsed once by `radar.home_filter.parse_state` and mirrored in the browser by `radar/static/filters.js`. Every control (rail option, group tab, country link, removable chip, Clear all, the Ask bar's filter answer, the terminal skin's keys 1 to 9) asks `GET /home/list` for the next state with htmx; the answer is the list section alone (`#hc-list`) plus the count line swapped out of band into `#hc-count`, a polite live region that never leaves the page, and the address bar is rewritten with `hx-replace-url` and the response's `HX-Replace-Url` header, never `hx-push-url`: no page loads and no history entry is added. The same URL loaded or refreshed renders the same section server-side, and with scripts off every control is still a link to that URL. Active filters show as removable chips above the list with "Clear all", the count reads "12 of 58 startups", and an empty result says "No startup matches these filters" with its chips. The facet list, the rail's headings and the group labels live in `config/home_filters.yaml` (the hook for a later taxonomy: a facet listed there whose values the rows carry in `facets[param]` is offered with no code change); the country name table moved there from `radar/home_list.py` and `radar/routes/feed.py`, and the Ask bar's country words read it too. The rail group that held the Ocean Impact Navigator category (parameter `sector`) is headed "Impact category", so "Sector" can mean the thesis (D33). *Why:* the owner's spec, "filtering must NEVER navigate away from the home page or trigger a full page reload": the group tabs and country links were plain `/?group=` links, the rail pushed a history entry per click and swapped the whole section, the Ask answer navigated to a URL, and the terminal skin's number keys set `location.href`. A replaced address instead of a pushed one keeps the back button for leaving the page. *Affected:* `/`, the new `/home/list`, `radar/home_filter.py`, `radar/templates/_home_list.html`, `_filter_rail.html`, `_home_count.html`, `feed.html`, `feed_rows.html` (its kind pills now replace the address too), `askbar.js`, `criteria.js` (the phone sheet only), `_skin_head.html`. No row, group, verdict, count or score of the list changes (the cached rows are the same ones). One side effect: the Ask bar now recognises every ISO 3166-1 country name from the config table (it recognised 13 before).

**D33. 2026-10-17 (feat/filters_inplace). The sector is a filter group, not a header block.** *Rule:* the `<details class="sector">` form in `base.html` (which reloaded the page with `?thesis=`) is removed from every page. Its job is the first group of the home list's filter, "Sector", whose options are the configured theses (`thesis.available()`, the `config/thesis*.yaml` files; each printed by its title without the trailing bracket, with the number of startups its list holds when that list is cached) and which takes one choice. The sector in view is also shown as a default chip, "Blue economy, Finland and Nordics" for the default thesis: a label with no cross, that "Clear all" leaves alone. Choosing another sector asks `GET /home/list?thesis=<id>`, swaps the list section in place for that thesis' list (store, groups, counts, rail), rewrites the address with `replaceState` and sets the `radar_thesis` cookie (so the other pages follow), and updates the Ask bar (its count line out of band, its `data-thesis` and example questions in `filters.js`). Each option's link carries only the filters and group the other sector's rows offer (`radar.home_filter.sector_options`: a value no row of that sector carries is dropped; a sector whose list is not cached yet carries none), and the investor of the Top matching tab is reset to that sector's default; the whole page for the same address renders the same. The full records under the list belong to the sector the page was loaded with: when another sector is in view they are hidden behind a link to open them for the sector in view. `/?thesis=<id>` keeps working for old links, and every other page keeps resolving its sector from `?thesis=`, then the cookie, then the default; a page with no list to filter (no store for the sector, a search result) shows the sectors as plain links. *Why:* the owner's spec: the sector block reloaded the whole page and is a filter in everything but name. *Affected:* `base.html` and its CSS (app, site, home_c, askbar), `radar/routes/method.py` (the `thesis_options` template global is gone), `/home/list`, `_filter_rail.html`, `feed.html`, `askbar.js`, `filters.js`; no row, count or score of any sector's list changes.

**D34. 2026-10-17 (feat/filters_inplace). The country filter is a multi-select over the countries in the list, named in words, with a flag.** *Rule:* A29 (a country is stored as ISO 3166-1 alpha-2, upper case; the filter's value `none` means the register states none). The Country group and the country links above the list are one filter: several countries are alternatives (OR), and the country filter together with every other filter must hold (AND); an option is offered only for a country some row of the current group carries (a country already selected stays, with 0, so it can be switched off); the number beside it is how many rows would show with it switched on and the other filters as selected. Names are printed from the table `countries:` in `config/home_filters.yaml` (all 249 ISO codes with their English names, Unicode CLDR), never from Python. A 16 px flag is printed beside the name in the group, the links and the chip, from `radar/static/vendor/flags/<code>.svg` (flag-icons 7.2.3, MIT, with its licence and a README beside the files) when the file exists, and the name alone when it does not; the eleven files held are the countries in the home lists of the three sectors today. *Why:* the owner's spec (multi-select, ISO codes kept, English names in config, flags if cheap); the names were two separate Python tables (`home_list.COUNTRY_NAMES`, `routes/feed.COUNTRY_NAMES`) that listed 13 and 6 countries. The table's keys are quoted because a bare `NO` is a YAML false and Norway read as "NO". *Affected:* the Country group, the country links and chips on the home list, `/search`'s "countries" sentence and the Ask bar's country words (both read the table). No row, group or count changes. The Spanish flag file is 91 KB (it draws the coat of arms), the others under 400 bytes.




## T. Taxonomy

### Signal types

Every signal type a page can print, with its label from `radar/labels.py` (the only label table) and where it becomes emittable. `radar/emit.py` rejects a type that is not on its list.

| Type | Label | Emittable via |
|---|---|---|
| `register_entry` | New register entry | `radar/emit.py` |
| `bf_funding` | Business Finland funding | `radar/emit.py` |
| `eu_project` | EU project | `radar/emit.py` |
| `blueinvest` | BlueInvest pipeline | `radar/emit.py` |
| `patent` | Patent filing | `radar/emit.py` |
| `public_contract` | Public contract | `radar/emit.py` |
| `job_ad` | Open job ad | `radar/emit.py` |
| `site_customer` | Customer on own site | `radar/emit.py` |
| `first_sales` | First sales | `radar/emit.py` |
| `first_hire` | First hire | `radar/emit.py` |
| `sales_ended` | Sales ended | `radar/emit.py` |
| `employer_ended` | Employer register ended | `radar/emit.py` |
| `research_output` | Research output | `radar/emit.py` |
| `website_first_seen` | Website first seen | `radar/emit.py` |
| `website_milestone` | Website milestone | `radar/emit.py` |
| `pilot_named` | First customer or pilot named | `radar/adapters/ecosystem.py` (added at import) |
| `certification` | Certification or type approval | `radar/adapters/ecosystem.py` (added at import) |
| `programme_entry` | Accelerator or programme entry | `radar/adapters/ecosystem.py` (added at import) |
| `exhibitor` | Exhibitor or demo | `radar/adapters/ecosystem.py` (added at import) |
| `award` | Award or pitch win | `radar/adapters/ecosystem.py` (added at import) |
| `funding_round` | Funding round | `radar/adapters/ecosystem.py` (added at import) |
| `product_launch` | Product launch | `radar/adapters/ecosystem.py` (added at import) |
| `public_funding` | Grant or public funding | `radar/adapters/ecosystem.py` (added at import) |
| `ecosystem_event` | Other dated event | `radar/adapters/ecosystem.py` (added at import) |
| `equity_event` | Share issue or capital increase | `radar/adapters/prh_notices.py` (added at import) |
| `board_change` | Board change | `radar/adapters/prh_notices.py` (added at import) |
| `capital_loss` | Loss of share capital | `radar/adapters/prh_notices.py` (added at import) |
| `startup_notice` | Start-up notification | `radar/adapters/prh_notices.py` (added at import) |

`eu_grant` has a label and is a counted type in the thesis files, but it is not on the emit list, so `radar/adapters/eu_grants.py` writes `eu_project` instead (its own comment says the add is one line in `radar/emit.py`, a contract file the chief owns).

### Sources and source families

| Adapter | Label on pages | Source family (A6) |
|---|---|---|
| `blueinvest` | BlueInvest pipeline | blueinvest |
| `brreg` | none in radar/labels.py (falls back to the plain id) | brreg |
| `businessfinland` | Business Finland export | businessfinland |
| `cordis` | CORDIS | cordis |
| `cvr` | none in radar/labels.py (falls back to the plain id) | cvr |
| `declared` | declared list | declared |
| `ecosystem` | declared research | ecosystem |
| `estonia_register` | Estonian e-Business Register | estonia_register |
| `eu_grants` | EU grants | eu_grants |
| `hilma` | Hilma notice | hilma |
| `openalex` | OpenAlex | openalex |
| `prh` | PRH/YTJ register | prh |
| `prh_intake` | PRH/YTJ register (wide intake) | prh |
| `prh_notices` | PRH registered notices | prh |
| `prh_recent` | PRH/YTJ register (recent registrations) | prh |
| `stitcher` | AI stitcher (checked by code) | stitcher |
| `tax_registers` | PRH/YTJ tax registers | prh |
| `ted` | TED contract awards | ted |
| `webarchive` | Internet Archive | webarchive |

`brreg` and `cvr` have no entry in `radar/labels.py`; pages fall back to the plain id. Proposed labels: "Norwegian register (Brønnøysund)" and "Danish CVR register".

### Confidence levels (A9)

| Level | Rule (`radar/emit.py`) |
|---|---|
| high | the source names the company or its business ID directly and states the date |
| medium | matched by an exact legal name or website domain, date stated by the source |
| low | matched by name keyword or industry code only; shown, never counted in rankings |

### Verdicts (A12, A13)

Seven outcomes, the team's decision table in `memo.decisions` of `config/thesis.yaml`: INVEST, DUE DILIGENCE, ACCELERATOR, GRANT SUPPORT, PARTNER INTRODUCTION, WATCHLIST, REJECT / LOW FIT. No match is WATCHLIST. Levels are banded Low / Medium / High / unknown (A11); unknown never matches a cell that needs a band.

### Group tags

| Tag | Meaning | Written by |
|---|---|---|
| `cohort` | one of the 19 Nordic Blue cohort companies | `radar/adapters/declared.py` |
| `portfolio` | one of the 9 Redstone portfolio companies | `radar/adapters/declared.py` |
| `feed` | found by a public source; may enter the early-signal feed | discovery adapters |
| `intake` | wide intake, startup-shaped with one startup signal (A2) | `radar/adapters/prh_intake.py` |
| `ecosystem` | inserted from the declared ecosystem dataset, outside the feed | `radar/adapters/ecosystem.py` |

`cohort` and `portfolio` are never downgraded to `feed` (`emit.upsert_company`).

### Field candidate statuses (A28, A31)

`applied` (the value in the companies table, what live pages show), `agrees`, `differs`, `not_comparable` (two languages), `store_empty` (the store holds no value), `PENDING_DECISION` (an open question names the row; never on an applied row).

## F. Formats

| What | Format | Where it is checked |
|---|---|---|
| Event and founding dates | ISO 8601 calendar date `YYYY-MM-DD`, the day the event happened, never the fetch date (A18) | `radar/emit.py`, `radar/formats.py` `date_ok` |
| Date precision | `day` unless `signal_meta.date_precision` says `year` (stored as 1 January, printed "2026 (year only)") or `month` (stored as the last day of the month, labelled); a field candidate carries `day`, `month` or `year` | `radar/schema/005_signal_meta.sql`, `field_candidates.precision` |
| Times | UTC, `YYYY-MM-DDTHH:MM:SSZ` (`fetched_at`, `built_at`, provenance `at`) | `radar/emit.py` `now_utc` |
| Business ID (Y-tunnus) | `NNNNNNN-C`; C is the check digit: weights 7, 9, 10, 5, 8, 4, 2; remainder 0 gives 0, remainder 1 is never issued, otherwise 11 minus the remainder | `radar/formats.py` `business_id_ok` |
| Country | ISO 3166-1 alpha-2, upper case (A29) | `radar/formats.py` `country_ok` |
| Amounts | `amount_eur`: euros as the source states them, no conversion and no exchange-rate code; NULL when the source states none (A19) | `radar/schema/001_core.sql` |
| Money and dates in Finnish copy | Finnish format (CLAUDE.md), no em dashes | page templates |
| Links | every signal and candidate carries an `http(s)` link a human can open; nothing behind a login (A27) | `radar/emit.py`, `field_candidates` CHECK |
| Rule ids | `A<n>` (assumption) and `D<n>` (decision) in this file; question ids `B<n>-NN` in `QUESTIONS_B<n>.md` | `radar/consistency.py`, `provenance` CHECK |

## Q. Open questions

Batch B1 (`QUESTIONS_B1.md`, 17 Oct): 15 issues. B1-01 to B1-11 come from the field candidate conflicts, and B1-12 to B1-15 from the stop-and-ask scans: duplicates, dates, amounts. Until they are answered, live pages keep A1. When answers land they become the next free D number (D22 to D24 are the matchmaking decisions of 17 Oct), and this file is re-issued.

## K. Known inconsistencies between documents and code (for the chief; nothing changed here)

- `config/thesis.yaml:26` (and the Baltic file) still says "TOL 2008 (NACE) codes" above a list that D6 moved to TOL 2025 codes.
- ARCHITECTURE.md (the "with a week" list) still proposes the source-family corroboration rule that D12 implemented.
- EVAL.md (health section) still says the health feed lists clinics matched on "medical"; D14 left TOL 86 out. It may refer to clinics coded outside 86; the repo does not say.
- D8: EVAL.md reports 27 stitcher signals in the live store and the batch reports 29 emitted; the repo does not reconcile the two.
- `eu_grant` is labelled and counted but not emittable (see T).

## H. History of this register

- 2026-10-17 08:19Z: ASSUMPTIONS.md, A1 to A27 and D1 to D20, drafted on the VPS (bf4547c); merged to main as e0568b2.
- 2026-10-17: folded into this file with the same ids (task jx40). Added A28 to A33, notes to D1, D2, D12 and D15, D21, the taxonomy, the formats and batch B1.
- 2026-10-17: D27 (Ocean Impact Readiness, renumbered from D22 at merge as evidence readiness; amends A24 for rungs 7 and 8).
- 2026-10-17: matchmaking (059bd6c): A34 and D28 to D30 (renumbered from D22 to D24 at merge); no earlier rule changed.
- 2026-10-17: D31 (organisation descriptions drop redacted clauses); a sentence added to D22 for the Aava feed reader.
- 2026-10-17: D32 (filters in place: one URL state, only the list section swaps; facets, group labels and country names in config/home_filters.yaml); no earlier rule changed.
- 2026-10-17: D33 (the sector is a filter group on the home list; the header block is removed); no earlier rule changed.
- 2026-10-17: D34 (country filter: multi-select over the countries in the list, names from config, vendored flags); no earlier rule changed.
