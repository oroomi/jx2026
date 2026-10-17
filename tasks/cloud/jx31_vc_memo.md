# jx31_vc_memo [cloud]: answer "so what?" for the fund, not the startup

Branch: `cloud/vc_memo`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first.

## Why
A new teammate's review: the levels (Ocean Impact, BRL, TRL, investment readiness) explain a startup but do not tell an investor what to do. The challenge owners are Redstone Blue (a fund) and A'Pelago (an accelerator), so every recommendation is addressed to THEM, never to the startup. Today radar/matching.py NEXT_RULES speaks to the startup ("apply to that programme", "raise"). Fix that and add a short memo at the top of the company page.

## Build
1. `radar/memo.py` (rules only, no LLM, so it runs live with no API key): from the company's existing readiness levels, fit reasons, who_comes_next and next_step, produce:
   - Verdict for the fund, one of: "Meet now", "Introduce", "Watch", "Check in", "Not enough evidence yet". Each with its rule printed.
   - Strength: the highest level or strongest fit reason, with its evidence link.
   - Biggest gap: a diagnosis from the gap between levels, e.g. TRL 7 with BRL 4 and investment level 3 -> "Technology is ahead of business validation." The gap table lives in config (thesis yaml `memo:` section), not in code.
   - Why now: the nearest dated reason (programme deadline, recent contract, recent hire or first sales) with its date and link, or "no dated reason yet".
   - Next actions for you (at most 3): e.g. "Introduce to <programme> before <deadline>", "Ask about their <buyer> contract", "Revisit when a first paying customer appears; the radar flags it". Every action names its source row.
   Missing evidence is shown as missing (hatched chip). Nothing without a link.
2. Rewrite NEXT_RULES in radar/matching.py so each rule is an action for the fund or accelerator ("Introduce them to ...", "Ask about ...", "Meet now: ...", "Check in ...", "Watch: ..."). Keep rule numbers and logic; update tests.
3. Q03 correctness (judge review 2 item 4 and the modules review): print the match reason on every row, hide rows with no reason, apply the TRL window to every funding row (not only programmes_grants.csv rows), and make the stage check two-way (a series A company is not offered a pre-seed studio).
4. Template `radar/templates/company_memo.html`, included at the top of company.html above question 01 (one include line; company.html is also being edited by cloud/stitcher, cloud/wide_intake and cloud/visual_polish, so change nothing else there). Use existing CSS classes; the visual session polishes. Add a print stylesheet rule so the memo plus the four answers print as one clean page ("Print memo" link).
5. The memo appears in /api/company/{key} only if radar/routes/api.py needs no edit; otherwise leave the API alone and say so.

## Rules
Companies only. No sector word in code. Tests on data/snapshot: memo for Kelluu (2902007-2), for a company with almost no evidence, and for the health thesis (no blue wording). Don't touch adapters, store.py feed logic, api.py, or the chief's docs; propose doc lines in RESULT.

RESULT: the memo verdict and biggest gap for Kelluu and two other companies, the new NEXT_RULES text, pytest count. First slice (items 1, 2, 4) by Sat 09:00 UTC; feature freeze Sat 18:30 UTC.

## AMENDMENT 23:45Z (team docs; see TASKS.md amendments 23:30Z and 23:40Z, which win where they differ from the text above)
- Verdict = exactly one of the team's 7 categories: INVEST | DUE DILIGENCE | ACCELERATOR | GRANT SUPPORT | PARTNER INTRODUCTION | WATCHLIST | REJECT / LOW FIT. This replaces "Meet now / Introduce / Watch / Check in / Not enough evidence yet".
- Decision table = the team's 10-row table (Ocean impact, Business readiness, Investment readiness, Thesis fit -> decision + action), stored as data in the thesis yaml (`decisions:`), first match wins, unmatched -> WATCHLIST. Print the matched row on the page ("because: High / Medium / Low / High").
- Low/Medium/High comes from OUR sponsor-framework levels (Ocean Impact Navigator, KTH BRL, Aalto TRL, 10 investment dimensions) through a mapping in config. Do NOT build the team's 0-20 questionnaires. A level with no public evidence is "unknown", never "Low": a row that needs it does not match, so the company lands in WATCHLIST with "more public evidence needed: <which level>". REJECT / LOW FIT only when thesis fit and ocean impact are Low on evidence; label it "Low fit on public evidence". A company from the wide-intake tier with no thesis evidence is WATCHLIST, not REJECT.
- Layout: Recommendation, then Why (+ bullets, each linked to evidence), Risks (- bullets: evidence gaps and weak levels, e.g. "no public revenue evidence"), Recommended actions for the fund or accelerator (1 to 3, filled from the who-comes-next lists with real names, e.g. PARTNER INTRODUCTION names the partner rows). Never "strong team" or "moderate competition" unless a linked source says so.
- The health thesis gets the same table with its own wording in thesis_health_turku.yaml (no ocean words).
