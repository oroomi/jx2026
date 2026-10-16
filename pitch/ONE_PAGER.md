# One-page handout (text), worked example: Kelluu Oy

Notes for whoever prints it: this is the text for one printed page per company. The header is the plain text line below, never A'Pelago's or Redstone's letterhead or logo. Every value comes from the snapshot store `data/snapshot/radar_redstone_apelago_blue.sqlite` (rows fetched 2026-10-16), and matches https://jx.hankintaviikko.fi/c/2902007-2 on build 446e896. Sections 03 and 04 are empty in that snapshot and are printed as empty. Regenerate from the live page on Sunday morning before printing.

---

Prepared for A'Pelago

## Kelluu Oy

Y-tunnus 2902007-2 · registered 2018-03-09 · industry 30310 Manufacture of civilian air and spacecraft and related machinery · register status active · website kelluu.com
Source: PRH/YTJ register, https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=2902007-2 (read 2026-10-16)

Why it is on the radar: it is on the declared Redstone Blue portfolio list (data/declared/cohort_portfolio_companies.csv, from redstone.vc/portfolio). Its industry code 30310 is not on the blue-economy thesis list, so the feed's code filter alone would not have found it.

Connections across records: received a Business Finland funding decision in 2018 (year only), and 4 more of the same type (Business Finland); registered in the trade register in March 2018 (PRH); joined an EU project (project start) in September 2024 (CORDIS).

### 01 Who is most promising

7 public records tie it to the sector. No score and no ranking.

| Date | Record | Amount | Source |
|---|---|---|---|
| 2026 (year only) | Business Finland funding, grant | EUR 501 369 | Business Finland export (no per-row link) |
| 2025 (year only) | Business Finland funding, grant | EUR 749 000 | Business Finland export (no per-row link) |
| 2024-09-01 | EU project SingleTree (Horizon Europe), role participant, matched by VAT number FI29020072 | EC contribution EUR 301 500 | https://cordis.europa.eu/project/id/101157488 |
| 2022 (year only) | Business Finland funding, grant | EUR 884 740 | Business Finland export (no per-row link) |
| 2019 (year only) | Business Finland funding, loan | EUR 707 200 | Business Finland export (no per-row link) |
| 2018-03-09 | Trade register entry | | PRH/YTJ register |
| 2018 (year only) | Business Finland funding, grant | EUR 50 000 | Business Finland export (no per-row link) |

Business Finland rows come from the public dashboard export of 2026-10-16 (https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html); the export gives a year, not a decision date.

### 02 How ready are they

A level appears only when a public record backs it. The rule that fired is printed beside it.

| Framework | Level from public records | Rule that fired | Evidence |
|---|---|---|---|
| Business Readiness Level (KTH BRL) 1-9 | 4 of 9 | first grant: Business Finland funding decision or EU project participation | 6 records (5 Business Finland, 1 CORDIS) |
| Technology Readiness Level (Aalto TRL) 1-9 | 4 of 9 | Business Finland or EU project funding: a funded development project | 6 records (5 Business Finland, 1 CORDIS) |
| Investment Readiness 1-9, read from the ten Investment Potential dimensions | 4 of 9 | two or more funding records | 6 records (5 Business Finland, 1 CORDIS) |
| Ocean Impact Readiness (Ocean Impact Navigator) | no public evidence | Navigator category: not in public records | 0 records |

The ten Investment Potential dimensions: Financials 5 records (Business Finland), Tech 6 records (5 Business Finland, 1 CORDIS). Market, Product, Team, Business Model, Competition, Marketing & Distribution, Deal Dynamics and Impact: not in public records.

Levels are evidence-class rules over public records, not an assessment of the company. Rules in full: https://jx.hankintaviikko.fi/method

### 03 Who comes next

Not in this snapshot: "not yet scored: matching rules land Saturday". On Sunday, copy the first three rows of section 03 from the live page, each with its reason and link, or leave this line as it is.

### 04 What should happen next

Not in this snapshot: "not yet scored: next-step rules land Saturday". On Sunday, copy the one sentence of section 04 from the live page with its "because" and link, or leave this line as it is.

Not connected, no data shown: LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn (connector slots).

---

generated from public records on 16 Oct 2026 by Ocean Opportunity Radar, team Old Hackers

---

## Template for any other company

Replace each `<...>` from the company's live page /c/{company_key}. Leave a field as "not in public records" when the page says so; never type a value the page does not show.

```
Prepared for A'Pelago

<legal name>
Y-tunnus <id or "not in public records"> · registered <date> · industry <code and text> · register status <status> · website <domain>
Source: <register link> (read <date>)

Connections across records: <the sentence from the page, with its sources>

01 Who is most promising
<N> public records tie it to the sector. No score and no ranking.
<one line per record: date, record, amount, source>

02 How ready are they
KTH BRL 1-9: <level or "no public evidence">, rule: <rule>, evidence: <count and sources>
Aalto TRL 1-9: <level or "no public evidence">, rule: <rule>, evidence: <count and sources>
Investment Readiness 1-9 (ten Investment Potential dimensions): <level or "no public evidence">, rule: <rule>, evidence: <count>
Ocean Impact Navigator: <category or "no public evidence">
Dimensions with evidence: <names and counts>. Not in public records: <names>.

03 Who comes next
<first three rows of section 03 with reason and link, or the page's own empty text>

04 What should happen next
<the sentence, "because", link, or "no next step supported by public records">

generated from public records on <date> by Ocean Opportunity Radar, team Old Hackers
```
