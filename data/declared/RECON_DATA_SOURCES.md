# Ocean Opportunity Radar: public data source recon (fetched 2026-10-16 15:25-15:45Z)

Scope: the 28 companies in /root/hack/research/PARTNERS.md (19 Nordic Blue 2026 cohort + 9 Redstone Blue portfolio). Per-company results are in `companies.csv` (same folder). All fetches used 1 request per 2 s and UA `HankintaviikkoBot/1.0 (+https://hankintaviikko.fi)`. No logins, no LinkedIn/Dealroom/Crunchbase/Tracxn/PitchBook.

Verdict summary

| # | Source | Verdict | The one fact that matters |
|---|---|---|---|
| 1 | PRH/YTJ open API v3 | usable | 13 of 28 resolve to a Y-tunnus in one call each (1 only weakly); 13 are non-Finnish; 2 Finnish ones (Edilm, Unique Docks) have no register entry |
| 2 | Business Finland funding decisions | partial | Public, but only as a Qlik Sense dashboard (Excel export by hand); no bulk file or API, so no match check was possible |
| 3 | CORDIS + BlueInvest | usable (CORDIS), partial (BlueInvest) | CORDIS bulk CSV shows 2 of 28 with EU money (Kelluu EUR 301,500; NIDO Constructech EUR 202,125); BlueInvest pipeline lists RedGet.io and ReefCircular |
| 4 | EIC / BlueInvest calendar | partial | Only one official EIC date exists: 4 Nov 2026; 3 Feb 2027 is secondary-source and provisional; BlueInvest has no cut-offs, only rolling readiness assistance |
| 5 | Hilma awards (tenderhub) | usable for buyers, no for company match | 0 of 28 appear as winners; the 12-month buyer set for water, emissions and port categories is real and linkable |
| 6 | Company websites | partial | Only 7 of 28 sites name anyone (customers: Klimate, Tethys, Redkik, Kelluu, Your Devocean logos; partners only: Race for Oceans, ReefCircular); 21 name none |

---

## 1. PRH/YTJ open data API (v3)

- Endpoint: `GET https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=<text>` or `?businessId=<NNNNNNN-N>` (also filters for location, form, etc. per the swagger at https://avoindata.prh.fi/en/ytj/swagger-ui). Code lists: `GET /v3/description?lang=en&code=<CODESET>` (only `TLAHDE` verified to return data).
- Auth: none. Licence: CC BY 4.0, attribution required, no PRH logos (https://ytj.fi/en/index/opendata.html). Data refreshed daily.
- Rate limit: none documented; none observed (about 70 requests at 1 per 2 s, all 200, no rate-limit headers). Keep our 1 per 2 s.
- Name search is substring on any registered name, including auxiliary names (that is how `WESI Solutions` resolved to Arctic Fry Oy). Short or common names return noise (`MOR` returned 1,589 hits, `Valkama` 188): always confirm with the company's own website or VAT number before accepting a match.
- Fields we would use: `businessId.value`, `businessId.registrationDate`, `names[].name/type/endDate` (type 1 = legal name, 3 = auxiliary), `mainBusinessLine.type` (TOL 2008 code) and `.descriptions[]` (languageCode 1 fi, 2 sv, 3 en), `website.url`, `addresses[]`, `companyForms[]`, `registeredEntries[]` (type 1 registered, 55 prepayment register, 80 VAT liable; `endDate` means ended), `companySituations[]` (e.g. `KONK` = bankruptcy), `lastModified`.
- Caveat: top-level `status` was `2` for a company in bankruptcy (Agile Composites Oy), so do not read `status` as "healthy". Use `companySituations` and `registeredEntries.endDate`. `ytj_status` in the CSV is derived that way.
- Sample record (fetched 15:25Z, `?name=Emission-Eye`, trimmed):

```json
{"businessId":{"value":"3543918-7","registrationDate":"2025-06-13"},
 "names":[{"name":"Emission-Eye Oy","type":"1","registrationDate":"2025-07-02"}],
 "mainBusinessLine":{"type":"62100","descriptions":[{"languageCode":"3","description":"Computer programming activities"}]},
 "website":{"url":"https://emission-eye.io/"},
 "companySituations":[],
 "addresses":[{"street":"Linnatullinkatu","buildingNumber":"1","postCode":"02600","postOffices":[{"city":"ESPOO","languageCode":"1"}]}],
 "lastModified":"2026-09-10T12:55:23"}
```
- Result for the 28 (details in CSV): 13 Finnish-register matches. High confidence: Kilocode (1840910-3), Sub Marine Store (3197621-7), Sireness (3568392-1), WESI Solutions = Arctic Fry Oy (3166759-6), Emission-Eye (3543918-7), sauna/ing = Finnish Sauna Shop Oy (3516783-9, via the site's legal notice), Kelluu Oy (2902007-2), NanoHalen (3399187-5), Redkik Oy (3154837-8), Valkama Watercrafts Oy (3274823-2), Viva Jets Oy (2962040-6). Medium: Norolan = Norolan Artisanlures Oy (2982240-3). Low: WAIing, only a site hint to Taikoa Oy (3380111-1).
- Finnish but NOT in the register: Edilm (no company of that name; site footer says "Edilm Project"), Unique Docks (no company; the Savonlinna address belongs to Agile Composites Oy 3327328-3, which carries a bankruptcy situation, link to Unique Docks unconfirmed).
- Non-Finnish, skipped: TuniSea NO; Race for Oceans, ReefCircular, Sensemakers, PEATZ, Just-measure DK; MOR, Your Devocean SE; NIDO Contech ES (Chile link); VesselChain ES; RedGet.io BG; Klimate DK (Klimate ApS CVR 41057165); Tethys Robotics CH. Redkik is a Finnish Oy with a US parent (Redkik, Inc.).
- Demo risk: the sauna/ing, Edilm and WAIing identities are shaky. Show "not confirmed" rather than a guess.
- Verdict: **usable**.

## 2. Business Finland funding decisions

- Not on avoindata.fi. The CKAN organisation `business-finland` holds 1 dataset (Visit Finland tourist barometer), no funding data (`GET https://www.avoindata.fi/data/api/3/action/organization_list?all_fields=true&q=business`).
- Where it actually lives: Business Finland's own "funding information" page (https://www.businessfinland.fi/en/About-Us/Strategy-and-effectiveness/Results-and-impact/funding-information/) links Qlik Sense dashboards on `tietopankki.businessfinland.fi`:
  - Funding granted 2010-2026: https://tietopankki.businessfinland.fi/anonymous/extensions/fundingawarded/fundingawarded.html (Qlik app id 2814ac0a-f4a0-4f2d-96d5-d501340f8dc6)
  - Funding paid: .../fundingpaid/fundingpaid.html ; project level granted and paid 2016-2026: .../projectfunding/projectfunding.html
  - Public research and corporate projects: .../Public_research_and_corporate_projects/Public_research_and_corporate_projects.html
  - Finnish "Myönnetty rahoitus" with a "Customers" tab: .../MyonnettyRahoitus/MyonnettyRahoitus.html
- Auth: anonymous virtual proxy (no login); the pages are served 200. Format: HTML dashboard with Excel and PDF export buttons. Refreshed on the 15th of each month. Filters: organisation name, period, organisation type, size, sector, region.
- Machine access: I tried the Qlik Engine websocket (`wss://tietopankki.businessfinland.fi/anonymous/app/<id>`) with the anonymous session cookie and got HTTP 403 twice; I stopped there. A browser-driven export (headless Chrome clicking the Excel button) is the realistic path and is a few hours of work, not a Friday-night adapter.
- Columns: could not be read without the engine. The page text promises customer-level and project-level amounts.
- Do any of our 28 appear: **unknown**, not checked (no queryable data). Plausible hits to check by hand in the "Customers" tab: Kelluu Oy, Valkama Watercrafts Oy, Viva Jets Oy, NanoHalen Oy, Redkik Oy, Sub Marine Store Oy.
- Sample record: none obtainable (dashboard only). Evidence of access: `fundingawarded.html` returned 200 with title "Funding awarded".
- Verdict: **partial** (public, citable page link per company is possible, but no bulk or API path).

## 3. EU CORDIS and BlueInvest

CORDIS (usable)
- Bulk CSV, no auth, open: Horizon Europe `https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip` (37.5 MB, last-modified 2026-10-08) and Horizon 2020 `https://cordis.europa.eu/data/cordis-h2020projects-csv.zip` (55 MB). Files inside: `project.csv`, `organization.csv`, `euroSciVoc.csv`, `topics.csv`, `webLink.csv`, `policyPriorities.csv`; semicolon-delimited, UTF-8. Rate limit: none stated (static files; two downloads at 1 per 2 s). Plan: download once, load to sqlite, refresh weekly.
- Fields we would use: organization.csv `projectID, projectAcronym, vatNumber, name, shortName, SME, activityType, city, country, role, ecContribution, netEcContribution, totalCost, active`; project.csv `id, acronym, title, startDate, endDate, ecMaxContribution, topics, frameworkProgramme, fundingScheme, objective, keywords`. Match on `vatNumber` first (FI + 8 digits works for Finnish firms), name second.
- Hits among our 28 (name match on organization.csv; VAT match found only Kelluu):
  - Kelluu Airships: `KELLUU OY`, Horizon Europe project SingleTree 101157488 (CBE JU RIA, 2024-09-01 to 2028-08-31), EC contribution EUR 301,500. https://cordis.europa.eu/project/id/101157488
  - NIDO Contech: `NIDO CONSTRUCTECH SL`, Madrid, project SALINA 101292324 (macroalgae for food, cosmetics, construction; CBE JU IA, 2026-06-01 to 2030-05-31), EC contribution EUR 202,125. Name and subject match; treat as same entity "very likely". https://cordis.europa.eu/project/id/101292324
  - No hit: the other 26 (searched 38 name variants plus 15 VAT numbers, both programmes).
- Sample record (organization.csv): `projectID 101157488; projectAcronym SingleTree; name KELLUU OY; country FI; city Joensuu; activityType PRC; role participant; ecContribution 301500`.
- Note: EIC Accelerator awards (grant + equity) appear in the Horizon Europe file, so this also covers EIC, but only after signature.

BlueInvest (partial)
- Public "Project Pipeline" of 718 profiles, no login: https://blueinvest-community.converve.io/pipeline_front.html (36 pages of 20; page param `params[page]=N`; free-text param `params[q]=`; detail `?action=detail&params[show]=comp&params[other_id]=<id>`). Filters: TRL, sector, country, readiness/fundraising assistance beneficiary. No JSON or CSV export; HTML scrape only. Rate limit unknown; 70 requests at 1 per 2 s were fine. Entries are keyed by project title, so company names are only in detail pages.
- Hits: RedGet.io (BG, TRL 4, Coastal and environmental protection) https://blueinvest-community.converve.io/pipeline_front.html?action=detail&params%5Bevent_id%5D=1&params%5Bshow%5D=comp&params%5Bq%5D=&params%5Bother_id%5D=1505 and ReefCircular (DK, TRL 3) with other_id=490. The `q` search is fuzzy-token and misses companies listed under a project title, so absence for the other 26 is "not found by text search", not proof.
- Sample record fields: title, one-paragraph description, Project TRL, Main sector, company country, "About us", "Problem we are solving", "Financial needs".
- Parent page https://oceans-and-fisheries.ec.europa.eu/funding-and-investment/blueinvest_en names the pipeline but gives no direct link.
- Verdict: CORDIS **usable**; BlueInvest **partial**.

## 4. Call calendar (next 3 dates)

Today is 2026-10-16.

| # | Date | What | Source | Confidence |
|---|---|---|---|---|
| 1 | 2026-11-04 (17:00 Brussels) | EIC Accelerator 2026 call HORIZON-EIC-2026-ACCELERATOR-01 closes (topic JSON deadline 1793750400000 = 2026-11-04) | https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/horizon-eic-2026-accelerator-01.json and https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-EIC-2026-ACCELERATOR-01 ; also listed as the last 2026 full-application cut-off by https://www.hezelburcht.com/en/grants/eic-accelerator/ | official |
| 2 | 2027-02-03 | First 2027 EIC Accelerator full-application cut-off | https://www.deloitte.com/mt/en/services/tax/perspectives/gi3/eic-accelerator-2027-call.html (secondary; the official 2027 topic HORIZON-EIC-2027-ACCELERATOR-01 returns 404, "opening in November 2026" per the 2026 topic text) | provisional |
| 3 | not published | Next 2027 cut-off ("every two to three months" per the same source, so roughly April 2027) | same | unknown, do not show a date |

- Short proposals are continuous ("any time", GO valid for 12 months) per Hezelburcht and Deloitte; the 25 Sep 2026 date seen in a EUREKA Fast Track document is a special route and passed.
- BlueInvest has no cut-off: "Investment Readiness Assistance for SMEs" is open on a rolling basis (https://blueinvest-community.converve.io/investment_readiness_assistance.html; TRL 4 or higher, EU-headquartered). Dated events instead: BlueInvest E-Pitching Session on energy transition in aquaculture and fisheries, 2026-11-12, online; BlueInvest Thematic Workshop at Malta Maritime World, 2026-11-25 to 27 (https://blueinvest-community.converve.io/all_events.html). BlueInvest Day 2026 happened 2-3 March 2026 (call closed 15 Jan 2026); BlueInvest Africa pitcher call closed 13 Feb 2026. Nothing announced yet for BlueInvest Day 2027.
- EIC Accelerator eligibility reminder for the next-step rule: the topic text requires at least TRL 5 completed and an SME established in an EU member state or associated country (UK applicants can only receive grant-only); check Annex 2 of the EIC Work Programme 2026 before showing a Chile or non-associated entity as eligible.
- Verdict: **partial** (one hard date).

## 5. Hilma awards (tenderhub, read-only)

- DB: `/opt/portfolio/tenderhub/data/awards_deep.sqlite` (1.15 GB; the file of the same name in the tenderhub root is 0 bytes). Opened `mode=ro`. 43,495 awards, 2018-09-07 to 2026-10-16T03:05Z, 8,108 in the last 12 months. Tables used: `awards`, `award_winners`, `companies`.
- Company match: searched `companies.name/officialName`, `award_winners.rawName` and `awards.winners` (case-insensitive substring, 34 patterns) plus exact Y-tunnus lookups in `award_winners` for the 13 resolved Finnish IDs. Result: **0 of 28 appear as winners.** (False positives only: `Unidors Oy` for "nido", `Valkama` surnames, `Saaristo*` unrelated firms.) This is a real finding for the demo: none of these startups has won a public contract yet, so "first public contract" is a milestone they all still lack, and readiness evidence must come from other sources.
- Buyer list, last 12 months (published 2025-10-16 or later), keyword + CPV filter over titles (water quality, hydrography, emissions and air monitoring, ports and icebreaking, oil spill, aquaculture). The keyword pass is noisy; the 10 below were hand-picked from 127 candidates as the most relevant per buyer. Link template is the repo's own (`bin/export_archive_csv.py`: `.../procurement/{procedure_id}/notice/{noticeId}/overview`); I did not click-test the URLs.

| Buyer | Notice title | Winner | Value | Published | Link |
|---|---|---|---|---|---|
| Väylävirasto (Finnish Transport Infrastructure Agency) | Tornion meriväylän ja sataman geometrian parantaminen, vesistötarkkailut (water monitoring) | Eurofins Ahma Oy (0227583-3) | EUR 70,047 | 2026-09-09 | https://www.hankintailmoitukset.fi/fi/public/procurement/33698/notice/EF-56602/overview |
| Suomen ympäristökeskus (SYKE) | Research vessel Aranda crewing and operation | Arctia Meritaito Oy (2302565-7) | EUR 17,000,000 | 2026-05-01 | https://www.hankintailmoitukset.fi/fi/public/procurement/26749/notice/EF-47891/overview |
| Liikenne- ja viestintävirasto (Traficom) | Northern Savonia areal hydrographic survey 2026 | Arctia Meritaito Oy (2302565-7) | EUR 1,000,000 | 2026-06-12 | https://www.hankintailmoitukset.fi/fi/public/procurement/29012/notice/EF-51378/overview |
| Varsinais-Suomen hyvinvointialue (Southwest Finland wellbeing area) | C-class oil-spill response vessels | Alpo Pro Boats Oy (3101791-3) | EUR 750,000 | 2026-06-19 | https://www.hankintailmoitukset.fi/fi/public/procurement/25369/notice/EF-51967/overview |
| HaminaKotka Satama Oy | Icebreaking services | Finntugs Oy (0709036-0) | EUR 3,500,000 | 2026-02-06 | https://www.hankintailmoitukset.fi/fi/public/procurement/18434/notice/EF-39450/overview |
| Kajaanin kaupunki | Air-quality monitoring measurements 2026-2029 | Aeri Oy (3238148-5) | EUR 89,500 | 2026-06-26 | https://www.hankintailmoitukset.fi/fi/public/procurement/28053/notice/EF-52569/overview |
| Jyväskylän Seudun Puhdistamo Oy | Laboratory, water-sampling and discharge monitoring, Nenäinniemi and Korpilahti plants | KVVY Tutkimus Oy (2823750-1) | EUR 406,732 | 2026-01-29 | https://www.hankintailmoitukset.fi/fi/public/procurement/21711/notice/EF-39242/overview |
| Pohjanmaan vesi ja ympäristö ry | Load monitoring, Alhedan wastewater plant 2026-2028 | KVVY Tutkimus Oy (2823750-1) | EUR 108,044 | 2026-02-24 | https://www.hankintailmoitukset.fi/fi/public/procurement/22469/notice/EF-41823/overview |
| Luonnonvarakeskus (Luke) | Enonkoski aquaculture plant oxygenation system | Waterix Oy (2460261-2) | EUR 199,456 | 2026-08-05 | https://www.hankintailmoitukset.fi/fi/public/procurement/32587/notice/EF-54202/overview |
| Turun Satama Oy | Ferry Terminal Turku S2 quay works | Oteran Oy (2245597-0) | EUR 67,390,000 | 2026-09-19 | https://www.hankintailmoitukset.fi/fi/public/procurement/30447/notice/EF-57319/overview |

- Honest limits: these are awards (finished), not open tenders; most winners are incumbents (Arctia Meritaito, KVVY). Turku Satama's quay contract is construction, not a startup category. Use these as "buyers who purchase in your category", not as sales leads. Other category-adjacent buyers seen: Sisäministeriö (oil-spill materials, EF-35984), Vantaanjoen ja Helsingin seudun vesiensuojeluyhdistys (water sample analysis, EF-45221), Jakobstads Hamn (port icebreaking, EF-32630).
- Sample record (`awards` row): `EF-56602 | 2026-09-09T03:05:15Z | Väylävirasto | Tornion meriväylän ja sataman geometrian parantaminen, vesistötarkkailut | Eurofins Ahma Oy (0227583-3) | 70047.0 | cpv 71000000 | nuts FI | procedure_id 33698`.
- Fields we would use: `noticeId, published, buyer, title, winners, amountEur, cpv, procedure_id`, plus `buyer_profiles` (awards, suppliers, topCpvDiv) and `expiry` (contract end dates) for "who comes next".
- Verdict: **usable** for buyers (data fresh to today), **no** for company-winner matching (0 hits).

## 6. Company websites and customer disclosure

Full table in `companies.csv` (columns `website`, `customers_listed`, `customers_evidence`, `customers_url`). Summary:
- Name customers or partners on their own site: Klimate (Nykredit, Storebrand, CPH Airport; case studies at https://www.klimate.co/resources/case-studies), Tethys Robotics (Aramco Europe demo, SepcoTech, SeaRenergy; news posts), Redkik (testimonials: Translogistics, Canopy Specialty, Lockton), Kelluu (Terrafame, Koli National Park in news posts), Your Devocean (WSP, John Nurminen Foundation, Nemo Seafarms as logos, role unstated), Race for Oceans (partners, not customers, https://www.raceforoceanstechnology.com/about#partners), ReefCircular (partners; WSP via Clean Cluster case).
- Name none or only anonymous: TuniSea, Sensemakers, PEATZ, Just-measure (anonymous case studies), Edilm, Kilocode, WAIing (seeking pilots), Sub Marine Store, Sireness, WESI, Emission-Eye (seeking pilots and LOIs), sauna/ing, MOR, NIDO, VesselChain, RedGet.io, NanoHalen, Norolan, Valkama, Viva Electric Jets.
- Not confirmed: Unique Docks (uniquedocks.com shows a WordPress fatal error; ownership of that domain unconfirmed).
- Traps found: kilocode.com is an unrelated AI-coding product (use kilocode.net and saaristo.online); emissioneye.ai is a different Swiss methane firm and emissioneye.com is parked; wesi.io and vesselchain.xyz are for-sale pages; saaristo.online renders blank without JavaScript.
- Two product descriptions in PARTNERS.md are not visible on the sites (NanoHalen "arsenic", Norolan "lead-free"): do not print them as site facts.
- Verdict: **partial**. Because most sites are thin, the radar's "business readiness" level must lean on register age, VAT registration (registeredEntries type 80), CORDIS/BlueInvest records and Hilma, and show "no public evidence" for customers.

## Build implications (short)

1. Real and cheap Friday night: YTJ lookup by name then Y-tunnus (with a website-field cross-check), CORDIS bulk to sqlite, Hilma buyer table, EIC date. Each is one adapter with a source URL per fact.
2. Business Finland needs a browser-export adapter; schedule it as the Saturday stretch, or show it as a connector slot with the dashboard link per company.
3. The 28-company reality is thin: 13 register matches, 2 CORDIS records, 2 BlueInvest profiles, 0 Hilma wins. The demo will show many "no public evidence" rows. That is the honest product, but pick the demo company from the rich set: Kelluu (YTJ + CORDIS + site customers), or RedGet.io / ReefCircular (BlueInvest TRL) for the cohort side, and Emission-Eye (YTJ + site, no funding) as the "signal dark" example.
