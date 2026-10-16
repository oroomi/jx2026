# Creative early-signal sources: what we tested, what we use, what we refuse (16 Oct 2026, 20:40-23:45Z)

The partners said their benchmark data is proprietary and that the job is to find startups EARLY, with traction before financial statements exist. This file is the research behind the radar's sources. Every source below was tested from this server tonight unless marked otherwise. "Signal" means an event with company, type, date and a URL a judge can open.

## 1. The find of the night: the trade register's notice feed (PRH, free, no key)

`https://avoindata.prh.fi/opendata-registerednotices-api/v3/?noticeRegistrationDateStart=YYYY-MM-DD&noticeRegistrationDateEnd=YYYY-MM-DD&entryCode=CODE` returns every registered notice in Finland in a date window, 50 per page, with the company's founding date, industry code and the notice's entry codes. Code list: `/description?code=EC&lang=EN` (tab-separated). Tested 16 Oct: ANTIP (decision to issue shares) 480 notices nationally in 1 Sep to 16 Oct 2026, KOROI (capital increase) 513, OANKO (new shares and increase of share capital), OANTI/ANTIK (new shares), OPTIO (option rights), HAL (board of directors), OPOMEN (loss of share capital, negative), typeOfRegistration U (start-up notification). Young companies appear within days: Danvantar Biophotonics Oy (founded 2022) share issue registered 13 Oct 2026; Steady Energy Oyj book-entry registration 9 Sep 2026.

Why this matters: an equity round in a Finnish limited company must be registered here, usually within weeks of closing, long before the first financial statement is filed and before any press. Filter by industry code and founding date (under 5 years) and you have a national feed of "young company just took money or granted options" that Dealroom learns about from press releases later, if at all. Nobody at the table will have seen this used. Adapter: jx21_prh_notices.

## 2. Used tonight (already adapters)
- PRH/YTJ company register: new registrations by industry code and line-of-business text (jx12 precision rule).
- Hilma and city decision archives: first public contract won (our own archive, nobody else has the city layer).
- Business Finland funding export: year-only grant events, 42 signals (jx11).
- CORDIS: Horizon Europe and H2020 participations, 82 eu_project signals (jx13).
- BlueInvest public pipeline (jx14, running).

## 3. Tested tonight, usable Saturday
- EU Funding and Tenders reference data `grantsTenders.json` (83 MB, every Horizon, LIFE, EMFAF grant with beneficiaries and country): one adapter covers the fisheries and maritime fund EMFAF that CORDIS does not. Adapter: jx22_eu_grants.
- Espacenet via EPO OPS: adapter and tests built in a cloud session (branch cloud/espacenet); needs a free developer key, Dayo registers.
- Fintraffic Digitraffic marine AIS `/api/ais/v1/vessels` (953 vessels, names, IMO, MMSI; headers `Digitraffic-User` and gzip required): useful to show a startup's named test vessel at sea, only if the vessel name is known from another record. Demo garnish, not a discovery source.
- The Finnish blue-economy dataset built on this server 16 Oct (/root/blue_economy, 197 entities: 79 companies, 73 capital sources, 47 buyers; 2,931 scored startup-to-investor pairs with reasons; readiness table with TRL, BRL, IRL and ocean-impact evidence for 73 companies; 32 job signals). This is the matching layer for screen two question 03 and the evidence base for question 02. Import as declared data with its sources: jx23_ecosystem_join.

## 4. Tested, weak or blocked, and why (shown as empty, never faked)
- Traficom vessel register CSV (2,271 rows): has first registration date, build year, owner TYPE and municipality, but no owner name or business ID. Cannot be joined to a company. Not used.
- Työmarkkinatori job-ad API: real and free but needs a registration tied to a business ID and fixed IPs; not for this weekend. Hiring signals stay as the 32 rows the dataset already holds.
- Theseus (thesis repository, companies commission student theses years before revenue): behind a bot wall (HTTP 403 with a challenge page). Would be a creative Finnish-only source; not reachable headless tonight.
- Research.fi: no public API found; export of decision lists is forbidden by its Act. Not used.
- Environmental and water permits (fish-farm permits = aquatech traction): the permit authority moved to a new national agency on 1 Jan 2026; its decision search presented an expired certificate; not used tonight.
- Ocean Impact Navigator: login-walled WEF-hosted app, no API; cited by name.
- keep.eu (Interreg partners): web export only, no API. Manual export possible Saturday if a cohort company is in an Interreg project.
- Dealroom, Crunchbase, PitchBook, Tracxn, LinkedIn: paid or licence-gated; shown as connector slots. If the partners hold a licence they can export for the weekend, the export goes in data/declared with its provenance.

## 5. What global VCs actually use (for /method, so the judge sees we know the field)
Signal-based sourcing vendors (Harmonic, Specter, Crustdata; Dealroom and Crunchbase signals) build on hiring boards, social profiles, web traffic, app downloads, GitHub, domain registrations, press and funding announcements; they refresh daily on priority companies, and practitioners report thin and stale coverage below Series A. Our difference, said plainly: official registers and public decisions, dated and linkable, and the earliness is measured by backtest on the partner's own cohort rather than claimed.

## 6. Do we need a database?
We have two and the product is their join. The radar store (SQLite, signals per company with source URLs: 639 register, 295 contracts, 42 Business Finland, 82 EU projects, more tonight) answers "who surfaced and when". The ecosystem store (/root/blue_economy, entities, capital sources, buyers, scored matches, readiness evidence) answers "fit and who next". jx23 copies the second into the first as declared data so the live app reads one file. After the weekend, the same SQLite grows nightly from the adapters; a server database is not needed until there are users.
