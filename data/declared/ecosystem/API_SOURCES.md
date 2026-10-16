# API and data sources for the Finnish blue-economy dataset

Status legend: TESTED = called successfully from this server on 2026-10-16; KNOWN = documented public
interface, not exercised today; PAID = needs a purchased key; LOGIN = free account required.

## A. Free, no key

| Source | What it gives | Endpoint / how | Status |
|---|---|---|---|
| PRH open data (Finnish Trade Register, YTJ) | Business ID, legal name history, registration date, trade-register status (1 active, 4 ended), end date, main business line, addresses | `GET https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=<name>` or `?businessId=1234567-8`. JSON. Docs: https://avoindata.prh.fi/en/ytj/swagger | TESTED |
| Fintraffic Digitraffic Marine | Port calls (ETA/ATA/ATD, berths), AIS vessel locations and metadata, sea-state, winter navigation, VTS data | Base `https://meri.digitraffic.fi/api/`. Examples: `port-call/v1/port-calls?from=2026-10-15T00:00:00Z`, `ais/v1/locations`, `ais/v1/vessels`. Send headers `Accept-Encoding: gzip` and `Digitraffic-User: <your-app-name>` (406 without them). Docs: https://www.digitraffic.fi/en/marine-traffic/ | TESTED |
| EU Funding & Tenders portal, grants data | Every Horizon/LIFE/EMFAF grant with beneficiaries, country, amounts | `https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json` (83 MB download). Beneficiary-level CSVs also at https://data.europa.eu (search "CORDIS projects" / "Horizon Europe participants") | TESTED (download) |
| FMI open data | Weather, sea level, wave, ice charts (for context and as baselines in impact calculations) | WFS: `https://opendata.fmi.fi/wfs?service=WFS&version=2.0.0&request=GetCapabilities`; stored queries listed there. Docs: https://en.ilmatieteenlaitos.fi/open-data | TESTED (capabilities) |
| avoindata.fi (Finnish open-data catalogue) | Index of government datasets incl. Business Finland, Traficom, Statistics Finland | CKAN API: `https://www.avoindata.fi/data/api/3/action/package_search?q=<term>` (use www. host; the bare host redirects). Web: https://www.avoindata.fi/data/en_GB/dataset/?q=business+finland | TESTED (web) |
| GitHub REST | Public repos and orgs (weak signal for this sector) | `https://api.github.com/search/users?q=location:Finland+maritime+type:org`; unauthenticated 10 searches/min, 60 calls/h; with `gh auth` 5,000/h | TESTED earlier today |
| EMSA THETIS-MRV | Per-ship annual CO2, fuel, distance, time at sea, CO2 per nm, for all ships >5,000 GT calling EU ports since 2018 | Portal: https://mrv.emsa.europa.eu/#public/emission-report → "Export" gives one XLSX per reporting year. No documented REST API; guessed `/api/public/...` paths return 404. Automate with a headless browser or download yearly files by hand (7 files) | TESTED (portal only) |
| SYKE open environmental data (Hertta / rajapinnat.ymparisto.fi) | Water quality, marine monitoring stations, emissions-to-water register (YLVA/VAHTI) for permit holders incl. fish farms | REST/OData: `https://rajapinnat.ymparisto.fi/api/` (services: Hertta water quality, VESLA, YLVA emissions). Docs: https://www.syke.fi/en/environmental-data/open-information | KNOWN |
| HELCOM map and data service | Baltic nutrient loads (PLC), pressures, protected areas | WMS/WFS and downloads: https://maps.helcom.fi/website/mapservice/ ; data portal https://metadata.helcom.fi | KNOWN |
| Fingrid open data | Finnish grid CO2 emission factor (real time and historic), production by type — turns MWh into CO2 avoided | `https://data.fingrid.fi/api/datasets/<id>/data` with header `x-api-key` (free key after registering at https://data.fingrid.fi) | LOGIN (free) |
| Statistics Finland PxWeb | Enterprise statistics, maritime transport, aquaculture production | `https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/` JSON-stat; docs https://stat.fi/en/statistical-data/interfaces | KNOWN |
| Traficom open data | Vessel register, boat register counts, maritime statistics | https://www.traficom.fi/en/statistics-and-publications/open-data and https://tieto.traficom.fi | KNOWN |
| Espacenet OPS (EPO patents) | Patents by applicant, families, legal status | `https://ops.epo.org/3.2/rest-services/published-data/search?q=pa%3D%22norsepower%22` with OAuth2 client credentials (free registration at https://developers.epo.org) | LOGIN (free) |
| Google Patents | Same, via web or BigQuery public dataset `patents-public-data` | Web: https://patents.google.com/?assignee=<name>; BigQuery needs a Google Cloud project | TESTED (web) |
| CORDIS | EU-funded project descriptions, deliverables, participants | Bulk CSV/JSON at https://data.europa.eu/data/datasets?query=cordis ; project pages https://cordis.europa.eu/project/id/<id> | KNOWN |
| keep.eu (Interreg projects) | Interreg Baltic Sea / Central Baltic project partners and budgets | Web search https://keep.eu/projects/ ; no stable public API (the /api/projects path returned 404) | KNOWN |
| NEFCO / BSAP Fund | Project list and final reports (BSAP-2020-103 Sofi, BSAP-2022-140 Nemo) | Web only: https://www.nefco.int/?s=BSAP | TESTED (web) |
| Ocean Impact Navigator (1000 Ocean Startups) | 34 ocean-impact KPIs, 6 impact areas, technical appendix | Web/PDF only, no API: https://www.1000oceanstartups.org/navigator | TESTED (web) |
| KTH Business Readiness Level, Aalto TRL | Level definitions | PDFs/pages: https://kthinnovationreadinesslevel.com/ ; https://www.aalto.fi/en/services/technology-readiness-level-trl | TESTED |
| Business Finland data bank (tietopankki) | Funded projects and amounts per company | https://tietopankki.businessfinland.fi (returned HTTP 502 at test time; retry). Funding decisions are also published as yearly lists on businessfinland.fi | KNOWN (down at test) |

## B. Paid or account-gated startup databases

| Source | What it gives | How to connect | Status |
|---|---|---|---|
| Dealroom | Funding rounds, investors, team, valuations; Finnish ecosystem view | REST `https://api.dealroom.co/api/v2/companies` with HTTP Basic auth (app id as username); key is sold per seat/plan. Web and API return 403 without it. Docs: https://api.dealroom.co/docs | PAID |
| Crunchbase | Companies, rounds, investors, people | `https://api.crunchbase.com/api/v4/entities/organizations/<permalink>?user_key=<key>`; Basic plan key is paid. A Crunchbase connector exists in this Claude workspace and would work once authorised in the connector settings | PAID / connector |
| Tracxn | Startup profiles, sector maps | Web subscription; API on enterprise plans | PAID |
| PitchBook | Rounds, valuations, investors | Enterprise licence; API only for enterprise customers | PAID |
| LinkedIn | Headcount, people, posts | No public API. Options: search-engine snippets (what we used), LinkedIn Marketing/Sales API (partner-only), third-party resolvers such as Proxycurl (paid per call). The Apollo and Lusha connectors in this workspace also need authorisation and a paid plan | PAID |
| BlueInvest Community | Project pipeline of EU blue-economy SMEs, investor report, matchmaking | Free member login at https://blueinvest-community.converve.io/ ; no API. Once you register I can read it through the browser | LOGIN (free) |
| Asiakastieto / Vainu / Finder | Finnish financial statements, headcount, credit data | Asiakastieto REST API and Vainu API are paid per company/report; Finder web pages are free to read one at a time (https://www.finder.fi/search?what=<name>) | PAID (web free) |
| PRH Virre | Filed financial statements as PDFs | https://virre.prh.fi, pay per document (a few euros) | PAID per doc |

## C. Minimal working examples

```bash
# PRH: status of a company (1 = active, 4 = ended)
curl -s "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=Clewat" | python3 -c "import json,sys; [print(c['businessId']['value'], c['names'][0]['name'], c.get('tradeRegisterStatus'), c.get('endDate')) for c in json.load(sys.stdin)['companies']]"
```

```bash
# Digitraffic: port calls since a timestamp (headers are mandatory)
curl -s --compressed -H "Accept-Encoding: gzip" -H "Digitraffic-User: mishakin-blue" "https://meri.digitraffic.fi/api/port-call/v1/port-calls?from=2026-10-15T00:00:00Z" | head -c 600
```

```bash
# EU grants reference data (83 MB)
curl -s -o grantsTenders.json "https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData/grantsTenders.json"
```

```bash
# Fingrid emission factor (after getting a free key at data.fingrid.fi)
curl -s -H "x-api-key: $FINGRID_KEY" "https://data.fingrid.fi/api/datasets/266/data?startTime=2026-01-01T00:00:00Z&endTime=2026-01-02T00:00:00Z"
```

```bash
# Espacenet OPS: get a token, then search by applicant
TOKEN=$(curl -s -u "$OPS_KEY:$OPS_SECRET" -d "grant_type=client_credentials" https://ops.epo.org/3.2/auth/accesstoken | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" "https://ops.epo.org/3.2/rest-services/published-data/search?q=pa%3D%22norsepower%22"
```

## D. Which gap each source fills

| Missing metric | Source |
|---|---|
| Legal status, business ID, end date | PRH open data |
| Revenue, equity ratio, headcount | Finder web (free, manual), Asiakastieto/Vainu (paid), PRH Virre (paid per doc) |
| Grant and public-funding history | EU grants JSON, CORDIS, Business Finland data bank, keep.eu, NEFCO |
| Patents | Espacenet OPS, Google Patents |
| Private rounds, investors | Dealroom, Crunchbase (paid); press via web search (free) |
| Measured fuel/CO2 impact for ship tech | THETIS-MRV before/after per ship |
| Port waiting-time impact | Digitraffic port calls and AIS |
| CO2 avoided for offshore wind | Fingrid emission factor × metered MWh |
| Nutrient discharge of fish farms | SYKE YLVA emissions register, AVI permit decisions, HELCOM PLC |
| Impact KPI vocabulary | Ocean Impact Navigator (34 KPIs) |
| Business readiness levels | KTH BRL 1-9; TRL per Aalto/EU definitions |
| Team names and roles | PRH (board/CEO in trade-register extract, paid), Finder pages (free), LinkedIn snippets |
| Current ask | No database; company form, pitch events, Dealroom "raising" flag |
