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
