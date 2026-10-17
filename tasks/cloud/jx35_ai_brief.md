# jx35_ai_brief [cloud]: the AI box, a cited summary of each startup's public record

Branch: `cloud/ai_brief`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first.

## Why
Dayo wants an AI box under each startup that sheds light on it. CLAUDE.md allows LLM text only as a summary of sourced facts, carrying the same links. So the AI writes, code checks, and nothing reaches the page unchecked. It runs as a batch, so there is no live API key and no new cost.

## Build
1. `radar/briefs.py`
   - `export(conn, thesis, keys) -> list[dict]`: for each company, the facts the page already shows (name, Business ID, founded, industry, every signal with type, date, source_url and title, the four levels with rule and evidence URL, fit reasons, the memo verdict if radar/memo.py exists, and the who-comes-next names). Pure Python, no LLM.
   - CLI: `python3 -m radar.briefs export --keys FILE --out DIR` writes one JSON per company; `python3 -m radar.briefs import --dir DIR` loads the briefs into a new table (new schema file radar/schema/NNN_briefs.sql).
2. Brief format (JSON per company): 4 to 6 sentences in plain English for a fund partner aged 40 to 60. Cover what the company does, what stage the public record shows, what is notable, what is missing, and what that means for the fund. Each sentence carries `cites: [source_url, ...]`, taken ONLY from that company's export.
3. Verify, in code, before import: every cited URL is in the export; every number and date in a sentence appears in the export; no person's name (radar/fit.py looks_like_person on capitalised word pairs, plus a list of the export's person-free names); no words like "strong team" or "market leader" unless a cited title contains them. A failing sentence is dropped, and a brief left with fewer than 2 sentences is dropped. Log every drop with its reason.
4. Generation: you write the briefs in your own session from the exported JSON. The chief exports from the LIVE store on the VPS and commits the JSON under data/fetched/briefs/in/ on this branch. Until that lands, develop on exports you make from data/snapshot. Commit your outputs under data/fetched/briefs/out/ (text only).
5. Template `radar/templates/company_brief.html`: the box headed "What the public record says", each sentence followed by small numbered source links, and a footer reading "AI summary of the linked public records, checked by code; written <date>". With no brief, show "No summary yet". Do NOT include it in company.html yourself; cloud/design_v2 places it. Give it plain semantic classes (brief, brief-sentence, brief-cite, brief-foot).

## Done
Tests on data/snapshot: export is person-free; verify drops a sentence with a foreign URL, a sentence with an unknown number, and a person-shaped name; import round-trips; the template renders both states. Push the code first: by Sat 02:00 UTC with a STATUS line saying "ready for live export". RESULT: briefs kept / dropped by reason for the live batch, two sample briefs (Kelluu plus one feed company), pytest count. Feature freeze Sat 18:30 UTC.
