# Blue-economy "who comes next" seed dataset (built 2026-10-16, 15:45Z to 16:15Z)

All four CSVs sit in this folder. Every row has a `source_url`; every CSV also has a trailing `note` column (startups also have `found_via`) for the caveats that matter. Empty cell means "not on the source page", never "guessed".

## Row counts

| File | Rows | Target |
|---|---|---|
| investors.csv | 43 (32 funds, angel network, corporate VC; 11 public funders) | 40-80 |
| corporates_clients.csv | 56 | 40-60 |
| programmes_grants.csv | 29 | n/a |
| startups_universe.csv | 47 (none duplicate the 28 in companies.csv; checked by name) | 40-100 |

## How it was fetched

HankintaviikkoBot/1.0 UA, robots.txt checked per host, at most 1 request per 2 s per host (hosts were fetched in parallel, so total throughput was higher than 0.5 req/s but no host saw more than that). Public pages only. No LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn, no logins. Search-engine queries were used only to discover URLs; rows cite the primary page, except where noted below.

Sources actually read: paaomasijoittajat.fi member directory; each investor's own site (Redstone, Voima, Maki, Icebreaker, Lifeline, Butterfly, Superhero, Wave, NordicNinja, Vendep, Greencode, Grid.vc, Kvanted, Momentum, Katapult, Nordic Foodtech VC, Monttu, Inventure, Innovestor, NSI, Kiilto, Metsa Spring, Trill, NIF, Karma, Gorilla); Tesi (approach, funds, companies pages); FiBAN; Business Finland (funding pages, Sprint, YIC, Tempo, 2026 news); EIC page plus the EC topic JSON; EC BlueInvest and EIF BlueInvest Fund pages; NEFCO; Nordic Innovation; Finnvera; Central Baltic; apelago.fi (cohort 2024, 2025, 2026, 2027 programmes, NOCA, partners, Mission Ocean hub, Initiative); Business Turku pages; BlueInvest project pipeline (Finland filter: 19 profiles plus 19 detail pages); PRH/YTJ open API (name and businessId lookups, 57 calls); the CORDIS Horizon Europe and H2020 bulk CSVs already downloaded by the earlier recon (Finnish SMEs in marine/water projects); our local Hilma archive (awards_deep.sqlite, read-only) for buyer evidence and young winning companies; about 45 corporate and authority homepages.

## Findings you should act on

1. Tempo is dead. Business Finland's own page says the service is closed and a 2026 news item says it "will not be reopened"; the Young Innovative Company (NIY) calls "will most likely remain closed". The replacement is the Sprint Grant (max EUR 100,000, 75 percent of costs, continuous call from 1 Sep 2026). Any next-step rule that says "apply for Tempo" must use Sprint instead. Monttu Ventures' site still recommends Tempo: outdated.
2. ilmastorahasto.fi is a consumer-loan comparison site, not the Finnish Climate Fund (Ilmastorahasto Oy, state-owned). I could not find or read the fund's real site, so its investors.csv row is a flagged placeholder.
3. sofokusventures.com now serves a Chinese streaming spam page (domain hijacked); excluded. springvest.com is a Taiwanese firm with the same name; excluded. cloudberry.vc is a semiconductor VC (not blue); excluded. OpenOcean and Nexit are data/digital software VCs despite the name; excluded.
4. YTJ shows a bankruptcy situation (KONK) for FimusKraft Oy (A'Pelago 2025 cohort; kept in startups with a warning) and for Aquaminerals Finland Oy (listed in Tesi's portfolio page; not added to startups).
5. EIC Accelerator cut-off 4 Nov 2026 is confirmed again from the EC topic JSON (deadlineDates 1793750400000). The EIC page says TRL 6-8; the topic text read earlier says TRL 5 completed: show the window as "TRL 6-8 (5 completed)".
6. Redstone Blue's ticket (EUR 200k to 2.0m, pre-seed to Series A) is now confirmed on Redstone's own page. One press source quoted USD 230k-2.3m; ignore it.
7. A'Pelago 2027: four programmes. Helsinki Blue Economy Studio deadline is 30 Nov 2026 (confirmed). Northern Blue and NOCA say applications are open but give no deadline; Lab2Impact is "TBA". Initiative 2027 is 18-19 Aug 2027 (Turku). Kongsberg Maritime is buying Steerprop (headline on Meriteollisuus, 7 Sep 2026).

## What is thin

- Fish farmers' association, Port of Oulu, Rauma Marine Constructions own site, Alandia, Viking Line, ABB Marine, Väylävirasto, Border Guard sites: unreachable (DNS, certificate, 403 or timeout) so those corporate rows lean on other pages. The Finnish Fish Farmers' Association row was dropped for lack of any readable source.
- Maria 01 and Kiuas: maria01.com does not resolve from the VPS; kiuas.com is JavaScript-only. Their programme rows are placeholders; the Maria 01 source is a search-result page we could not fetch (HTTP 403). No marine track found.
- Business Finland funding decisions (Qlik dashboard), Slush lists, Meriteollisuus member list (a PDF we did not parse), VTT spinouts, Åbo Akademi/University of Turku spinouts: no public list found or readable. The university-spinout slice of startups_universe is effectively empty; the only route is Lab2Impact and NSI.
- Blue Economy Center Turku has no published member list.
- Investor tickets: only 11 of 43 rows have a ticket from the investor's own page. Several investors (Voima, Maki, Lifeline, Butterfly, Katapult, Momentum) state no cheque size. Pale Blue Dot returned 429 and ETF Partners 403, so those two rows have no thesis.
- Mission Ocean (Horizon Europe) call deadlines and the Finnish EMFAF programme calls were not located: two named gaps in programmes_grants.csv. Interreg Central Baltic has no open call visible (5th call closed 30 Sep 2025). BlueInvest event dates (12 Nov, Malta 25-27 Nov) are carried over from DATA_SOURCES.md, not re-verified.
- Startups: 47 rows, but only 15 are under five years old. Several (APL Systems, Norsepower, Luode, Mapita) are mature firms kept because they appear in BlueInvest or CORDIS; `founded` is the YTJ registration date, so filter on it. Name-only YTJ matches (Ocean Eye, Lumra, Ruoco, Lentola) are flagged in `note`. Six rows (all A'Pelago alumni) have no Y-tunnus because the name search found nothing (Aila, Fish Farm 4.0, SubDrone, Alga.e, Coral Rescue, OW-Ferment); their country is unconfirmed.
- Hilma notice links use the tenderhub template; a bot GET to one returned 404, so open them in a browser before showing as evidence. The buyer facts themselves come straight from the archive.
- Corporates `what_they_buy_or_pilot` is evidence-based for authorities, ports and utilities (Hilma awards, last 12 months) but for shipping majors it is only what their homepage says; none of the corporates publishes a startup-pilot programme except Kemira, Meyer Turku (supplier route) and Väylävirasto (one innovation-partnership notice, EF-58323, EUR 650k). This is the real supply-side gap.

## Ten investor/funder to startup pairs visible now

Fit is judged from public fields only (stage, ticket, thesis, TRL, age); no investor has confirmed interest.

1. Redstone Blue and Krosswise Marine Oy (registered 2024-08-22): Redstone names "digitalized port operations"; Krosswise just won the D/S POLO port-activity software framework from Fintraffic's maritime traffic management (Jun 2026). First public contract plus pre-seed age.
2. Redstone Blue and Meric Wave Computanics Oy (2024-07-24, Tampere): hydrogen for reliable ice operation (EU H4PERION, EUR 202,125, from Jun 2026) fits "low-emission vessel solutions"; first EU signal, not yet in any cohort list.
3. Redstone Blue and Nexamass Oy (2024-07-09, Espoo): marine biomass platform, TRL 6, in both A'Pelago cohorts 2024 and 2025 and in BlueInvest; fits "blue biotech and water innovation".
4. Voima Ventures and Mittausguru Oy (2022, Kempele): Voima lists "sensing and diagnostics" and science-based deep tech; Mittausguru makes measurement instruments and won EUR 1.0M of continuous water-quality measurement from Tampere (Dec 2025).
5. Katapult Ocean and Ocean Eye: Katapult's ocean thesis names ocean data; Ocean Eye (citizen-science ocean data, TRL 9, scaling to the Baltic) is in BlueInvest and the A'Pelago 2025 cohort.
6. Nordic Foodtech VC and Hailia Nordic Oy (2020, Karkkila): deep tech for food, Nordics; Hailia upcycles seafood filleting sidestreams, TRL 9.
7. Momentum Partners and Nemo Seafarms Oy (2021): Momentum states a focus on ocean industries and seed entry; Nemo is moving its Filter Farm (seaweed/mussel nutrient capture) to pilot.
8. NordicNinja VC and Norsepower Oy Ltd: Series A, EUR 2-8M, decarbonization; Norsepower rotor sails are TRL 9 with a CORDIS record (RotorDEMO, EUR 1.58M). Later-stage match.
9. EIC Accelerator (cut-off 4 Nov 2026, TRL 6-8) and Awake.AI Oy (2018, Turku): TRL 8 smart-port platform, already an EU participant (SEAMLESS, EUR 248,550). Closest "apply before this date" case in the file.
10. Business Finland Sprint Grant (max EUR 100,000) and SEATOM Technologies Oy (2024-09-24, TRL 4): first R&D grant step for a two-year-old company; the same rule fits Lumra Oy (registered 2026-02-26, TRL 6).

## Build notes

Scripts and cached pages live in the session scratchpad, not in the repo. Nothing was committed; no application code written; no secrets, crontab, decisions.json or approved.sha256 touched.
