# jx38_nordic_registers [cloud]: Norway and Denmark company registers, so the 12 non-Finnish cohort companies become visible

Branch: `cloud/nordic_registers`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first.

## Why
12 of the 19 Nordic Blue cohort companies have no Finnish business ID, so no Finnish register can see them and the backtest cannot judge them. The brief scores scalability and transferability; the Estonia adapter already proves the pattern. Add the two open Nordic registers that need no key:
- Norway: Brønnøysundregistrene Enhetsregisteret open API (https://data.brreg.no/enhetsregisteret/api/, JSON, no key, documented rate limits; search by name, filter by registration date (registreringsdatoEnhetsregisteret) and NACE code (naeringskode)).
- Denmark: CVR via the open Virk "cvr-permanent" Elasticsearch endpoint needs credentials, so use the public JSON search (https://cvrapi.dk, no key for low volume, honour its terms) or mark Denmark BLOCKED with the reason if the terms forbid it. Sweden (Bolagsverket) has no free API: write that down as a connector slot.

## Build
1. Adapters radar/adapters/brreg.py and radar/adapters/cvr.py following CLAUDE.md's adapter contract (NAME, run(conn, thesis), CLI, cache under data/cache/<name>/, 1 request per 2 s, our User-Agent). Signals through radar/emit.py only: register_entry with the registration date and the register's own public URL (brreg has https://data.brreg.no/enhetsregisteret/oppslag/enheter/<orgnr>; cvr has https://datacvr.virk.dk/enhed/virksomhed/<cvr>). Companies only; skip sole proprietorships (ENK in Norway, enkeltmandsvirksomhed in Denmark).
2. Country config: extend config/thesis_baltic_blue.yaml `countries` and `country_depth` with NO and DK, the NACE codes equivalent to the thesis industry_codes (NACE Rev. 2 four-digit: 03.11, 03.21, 30.11, 30.12, 50.x, 52.22, 71.12, 72.19), and the thesis keywords in Norwegian and Danish (hav, sjø, marin, maritim, fiskeri, akvakultur, havn, skip, offshore; Danish: hav, marin, maritim, fiskeri, akvakultur, havn, skib).
3. Cohort lookup: for each of the 12 non-Finnish cohort companies in data/declared (the cohort CSV and the ecosystem dataset give their names and countries), search the registers by name, record the match with the register URL and registration date, and emit it so the backtest can date them. Report per company: found / not found / ambiguous (never guess a match; an ambiguous name is "not found" with the candidates listed in the RESULT).
4. Run both adapters in your session (full network) for the live window (last 365 days) under the thesis codes and keywords, and commit the fetched rows as JSON under data/fetched/nordic/ (text only, no caches) so the chief can import without network. Tests on data/snapshot with recorded fixtures.

## Deliver
STATUS lines per PROTOCOL.md; a first push with the brreg adapter and the cohort lookup by 03:30 UTC. RESULT: companies found per register for the live window, cohort companies dated (N of 12, with names), BLOCKED items with reasons, pytest count. Do not touch templates, store.py, matching.py, memo.py, api.py or the chief's docs.
