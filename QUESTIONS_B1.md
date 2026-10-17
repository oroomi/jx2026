# Questions, batch 1 (B1)

For: Dayo and the dataset owner. From: cloud builder, task jx40, 17 Oct 2026.

Each issue below is a case no assumption in PROJECT_RULES.md decides. Until an answer lands, live pages keep today's rule
(A1: the PRH register is the one source of record; every other source only matches an existing company or inserts a new
one), and the competing values sit in the `field_candidates` table with status `PENDING_DECISION` and the issue id. Nothing
on a live page changes. An answer becomes a numbered decision (D21, D22, ...) in PROJECT_RULES.md, applied to every
matching record, with the count of records changed.

Where the numbers come from (each is reproducible):

- **Snapshot**: `data/snapshot/radar_redstone_apelago_blue.sqlite` (16 Oct, 743 companies, 1,423 signals), copied, then
  `RADAR_DB=<copy> python3 -m radar.candidates build`. That run read 5,357 candidate rows for 741 companies. It used the
  PRH records cached in this checkout (139 API responses) and every declared file. The Hilma awards file is not on this
  machine. On the live store the chief's run reads more PRH records and the Hilma profiles, so its counts will be higher.
- **Health snapshot**: the same run on `radar_health_tech_turku.sqlite`. It read 3,185 rows and found 11 PENDING rows
  under B1-01 and B1-02.
- **Live**: `python3 -m radar.stop_and_ask --api https://jx.hankintaviikko.fi`. On 17 Oct about 08:25 UTC it read all
  17,193 company rows of the live blue store through the public read-only API, 500 per request with 2 s between requests.
- **Scan**: `python3 -m radar.stop_and_ask --db <snapshot copy>` runs the signal checks: dates, amounts, duplicates.

Counts, snapshot blue:

| Field | Company fields with 2 or more sources | Conflicts | PENDING_DECISION rows |
|---|---|---|---|
| name | 156 | 24 | 44 |
| founded | 52 | 1 | 2 |
| industry_code | 42 | 0 | 0 |
| industry_desc | 42 | 0 | 0 |
| town | 21 | 4 | 4 |
| website | 39 | 5 | 6 |
| register_status | 49 | 0 | 0 |
| country | 51 | 1 | 1 |

---

## B1-01. The Business Finland export names a company by an earlier or other name

- **Issue ID:** B1-01
- **Affected records:** 10 companies, 12 candidate rows (snapshot blue). Examples:
  - 0498749-8, Tapio Palvelut Oy: the export says Metsäkustannus Oy.
  - 2157464-4, Loihde Advisory Oy: the export says Talent Base Oy.
  - 2962040-6, Viva Jets Oy (the demo company): the export says SNOWSUS OY.
  - 2590096-1, Varian Medical Systems Finland Oy: the export says Adelmann Healthcare Solutions Oy and Noona Healthcare Oy.
- **Problem:** The Business Finland export joins on the Business ID (Y-tunnus). The organisation name in the export is
  the one at the time of the grant. The register gives today's legal name. No assumption says whether an older name may
  be shown, or whether a different name under the same ID means the grant belongs to the company at all.
- **Options:**
  - **A.** Keep the register's current legal name everywhere. Keep the export's name only as a candidate, and print it
    beside the funding row as "granted as <name>". Sources: PRH/YTJ API v3, `names` type 1; `data/declared/businessfinland.xlsx`, column Organisaatio.
  - **B.** Keep the register's name, and never show the export's name.
  - **C.** Treat a name mismatch as "matched by ID only" and lower the funding signal from high to medium confidence (A9).
- **Recommendation:** A. The Business ID is the key the export itself uses, and A9 makes an ID match high confidence. The
  earlier name is a fact a reader can check in the export, so showing it with "granted as" is honest and changes no level.
- **Other records affected:** on the health snapshot, 9 companies (10 rows), 3 of them not in the blue store. On the
  live store, every company with a Business Finland row may have such a row. The chief's run on a store copy gives the count.

## B1-02. A trading, auxiliary or declared brand name differs from the legal name

- **Issue ID:** B1-02
- **Affected records:** 11 companies, 24 candidate rows (snapshot blue). Examples:
  - 3166759-6, Arctic Fry Oy: the declared list, the register's auxiliary name and the ecosystem dataset all say WESI Solutions.
  - 2962040-6, Viva Jets Oy: the declared list and the register's auxiliary name say Viva Electric Jets.
  - 3380111-1, Taikoa Oy: the declared list says WAIing.
  - 1840910-3, Kilocode Oy: the register lists four auxiliary names, among them Saaristo.online.
- **Problem:** Pages print the legal name (A1). The programme and the partners know these companies by their brand. No
  assumption says which name is the title, or whether auxiliary names count as the same company when matching sources.
- **Options:**
  - **A.** Title = legal name. Add "also known as" with the declared name and the register's current auxiliary names.
    Sources: PRH `names` type 1 and type 3; `data/declared/cohort_portfolio_companies.csv`, column `company`.
  - **B.** Title = the declared name for cohort and portfolio companies, with the legal name under it. Legal name everywhere else.
  - **C.** Legal name only, as today.
- **Recommendation:** A. The legal name is the one every register and the Business ID agree on. The brand helps a
  partner recognise the company and is itself sourced: a register auxiliary name or the team's declared list.
- **Other records affected:** 1 company on the health snapshot. Every company with a register auxiliary name. The live
  count needs the chief's run over the full PRH cache.

## B1-03. A bracketed note or a tagline inside a name in a list

- **Issue ID:** B1-03
- **Affected records:** 7 companies, 7 candidate rows (snapshot blue). Examples:
  - Viva Jets Oy (Viva Electric Jets) and Kilocode Oy (Saaristo.online), both from the ecosystem dataset.
  - Mittausguru Oy (Enmeon) and Isola Corvus Oy (Velarca), from the startup universe list.
  - ReefCircular - Turning shell waste into sea life, from the BlueInvest pipeline.
- **Problem:** The lists put a second name or a tagline into the name field. Under the comparison rule (A28) these read
  as different names from the register's. No rule says to drop the note.
- **Options:**
  - **A.** New rule: when comparing names, drop a bracketed part and anything after " - ". Keep the bracketed name as a
    B1-02 candidate. Source: the list rows themselves.
  - **B.** Compare as written. The rows stay as conflicts.
  - **C.** Ask the list owners to clean the files.
- **Recommendation:** A. Each example names the same company. Folding the note away turns all 7 rows into agreeing
  rows, and the second name is not lost.
- **Other records affected:** every ecosystem, universe or BlueInvest name with brackets: 7 on the snapshot.

## B1-04. A company with no register record: the CORDIS legal name differs from the declared name

- **Issue ID:** B1-04
- **Affected records:** 1 company, 1 row. es-nido-contech: declared NIDO Contech, CORDIS NIDO CONSTRUCTECH SL (the
  CORDIS match itself is flagged medium confidence, similarity 0.83).
- **Problem:** For a company abroad with no national register in our sources, A1 has no source of record. The declared
  name stays in the store.
- **Options:**
  - **A.** Keep the declared name. Store the CORDIS legal name as a candidate. Source: CORDIS project 101292324.
  - **B.** Use the CORDIS legal name as the legal name.
  - **C.** Look the company up in the Spanish register (a connector slot today) before deciding.
- **Recommendation:** A. The CORDIS match is itself only probable, so it should not overwrite.
- **Other records affected:** 0 more on the snapshot; on the live store, every non-Finnish company matched by name in CORDIS.

## B1-05. Town: the register's post office is a village or postal district; another source names the municipality

- **Issue ID:** B1-05
- **Affected records:** 3 companies, 3 rows (snapshot blue):
  - 2902007-2, Kelluu Oy: Reijola (register and declared) vs Joensuu (ecosystem dataset).
  - 2982240-3, Norolan Artisanlures Oy: Norola vs Mikkeli.
  - dk-just-measure: Aarhus N (CVR) vs Aarhus (ecosystem dataset).
- **Problem:** A1 takes the town from the register's post office name (`radar/town.py`). Some post offices are villages
  inside a municipality. A partner filtering by Joensuu misses Kelluu.
- **Options:**
  - **A.** Keep the post office as the town, and add the municipality beside it from a municipality code table. That
    needs one more declared table, Statistics Finland's postcode-to-municipality file.
  - **B.** Keep the post office only, as today.
  - **C.** Take the municipality from the ecosystem dataset where it has one.
- **Recommendation:** A, after the freeze. The register is the source of record, and a public code table maps a postcode
  to its municipality with no judgement involved. C would mix a declared list into a register field.
- **Other records affected:** on the live store, every company whose post office is not a municipality name. The count
  needs the postcode table.

## B1-06. The ecosystem dataset describes a parent company abroad

- **Issue ID:** B1-06
- **Affected records:** 1 company, 2 rows. 3154837-8, Redkik Oy: register town Joensuu and country FI. The ecosystem
  dataset says Oxford and US. The declared list notes "parent Redkik, Inc. (US)".
- **Problem:** Is the company the Finnish subsidiary (register) or the group (dataset)? A1 keeps FI and Joensuu.
- **Options:**
  - **A.** Keep the Finnish entity's facts. Record the parent's country as a candidate only. Source: PRH 3154837-8.
  - **B.** Show both, as "Finnish subsidiary of a US company".
  - **C.** Use the group's country.
- **Recommendation:** A. Every signal we hold is keyed to the Finnish Business ID.
- **Other records affected:** 0 more on the snapshot.

## B1-07. Website: the register's website differs from another source's site

- **Issue ID:** B1-07
- **Affected records:** 4 companies, 5 rows:
  - 2639822-1, ICEYE Oy: iceye.fi (store) vs iceye.com (ecosystem).
  - 3380111-1, Taikoa Oy: taikoa.com (register) vs waiing.com (declared brand).
  - 1840910-3, Kilocode Oy: kilocode.net vs a saaristo.online portal.
  - fi-edilm: edilm.uk vs atlan.fi/edilm.
- **Problem:** A1 keeps the register's field. The other sites may be the product's own site, which is the one a partner opens.
- **Options:**
  - **A.** Keep the register's website as the link. List the other sites as "other sites" with their source.
  - **B.** Prefer the declared site for cohort and portfolio companies.
  - **C.** Register only, as today.
- **Recommendation:** A. It keeps one source of record and loses nothing.
- **Other records affected:** 31 website hosts are each shared by 2 to 10 companies in the live store (75 companies).
  That is a separate stop-and-ask item, B1-12.

## B1-08. A login-walled page given as a company website

- **Issue ID:** B1-08
- **Affected records:**
  - dk-peatz: the ecosystem dataset gives a LinkedIn company page. This row is PENDING. The store keeps peatz.eu.
  - In the live store, 2 companies hold such a page as their website: 3386016-2 (a LinkedIn company page) and 3350221-8
    (a Facebook page), both from the register's website field.
- **Problem:** A27 says LinkedIn and similar sites are connector slots only, and nothing behind a login is used. The
  live store already shows two such values, because the register states them.
- **Options:**
  - **A.** Never use a login-walled URL as a website or a source link. Show "website: not in public records" with a note
    "the register lists a social media page". Source: PRH website field.
  - **B.** Show it, because the register states it.
  - **C.** Drop the candidate row only, and leave the store as it is.
- **Recommendation:** A. It applies A27 the same way to every source, the register included.
- **Other records affected:** 2 on the live store, 1 candidate row on the snapshot.

## B1-09. Founded: no register record, and two declared lists disagree

- **Issue ID:** B1-09
- **Affected records:** 1 company, 2 rows. name:hailia-nordic, Hailia Nordic Oy: the ecosystem dataset says 2021, the
  startup universe list says 2020-08-20. The store has no founding date and no Business ID.
- **Problem:** No source of record. The two lists disagree even at year precision.
- **Options:**
  - **A.** Leave founded empty until a register record is found. Keep both as candidates.
  - **B.** Use the universe list's day date.
  - **C.** Look up the Business ID in PRH by name and let A1 decide. That is a network step.
- **Recommendation:** C, then A as the fallback. The company's name has the form of a Finnish limited company, so a
  register record is likely to exist.
- **Other records affected:** every name: key company with a founding date in a list. 17 company fields on the snapshot
  have candidates but an empty store value (status `store_empty`).

## B1-10. Industry: another code set or source differs from the register (no case on the snapshot)

- **Issue ID:** B1-10
- **Affected records:** none on the snapshot. 42 companies had 2 or more sources for the industry code, and every one agreed.
- **Problem:** The chief reports that PRH now returns TOL 2025 codes while the store may hold TOL 2008 codes in places.
  The likely carriers are the Hilma company profiles (`tolCode`) and older cached records. The thesis comment
  `config/thesis.yaml:26` still says "TOL 2008 (NACE) codes" above a list that D6 moved to TOL 2025.
- **Options:**
  - **A.** The register's current code wins (A1), and an older-set code stays a candidate with its code set named.
  - **B.** Convert old codes with Statistics Finland's TOL 2008 to TOL 2025 key.
  - **C.** Keep whichever code the store has.
- **Recommendation:** A. It needs no conversion table and is what A1 already says. The chief's run on the live store
  will show whether any case exists. The thesis comment fix belongs to the chief (config is a contract file).
- **Other records affected:** to be counted by the live-store run.

## B1-11. Register status: a list's status differs from the register (no case on the snapshot)

- **Issue ID:** B1-11
- **Affected records:** none on the snapshot. 49 companies had 2 or more status sources, and all agreed.
- **Problem:** The ecosystem dataset uses `dormant_unverified`, `defunct` and `acquired_or_renamed`. The register says
  active, ended or bankrupt (A1). A dormant mark has no register equivalent.
- **Options:**
  - **A.** The register's status wins. A dataset status is shown only as declared research (A24).
  - **B.** Show "possibly dormant" when the dataset says so.
  - **C.** Ignore the dataset's status.
- **Recommendation:** A, the same as A1 and A24.
- **Other records affected:** none known.

---

## Stop-and-ask items found by the scans (not field candidates)

These change no candidate row, but each one is a rule we do not have yet.

### B1-12. Possible duplicates

- **Affected records (live, 17,193 companies):**
  - 6 companies stored twice, once under a Business ID and once under a name: key. Examples: AWAKE.AI Oy 2945733-8 and
    name:awake-ai (from BlueInvest); Clewat Oy 2896110-2 and name:clewat; Manna Insect Oy 2952102-9 and name:manna-insect.
  - 15 legal names held by two Business IDs, for example Alfame Group Oy, Brinter Oy and Verge Motorcycles Oy.
  - 31 website hosts shared by 2 to 10 companies (75 companies). Examples: nordvire.com on 10 IDs, polarnode.fi on 6,
    and elomatic.com on Elomatic Oy and Elomatic Solutions Oy.
- **Problem:** A name: key is made when a source has no Business ID (A1, emit). When the register later gives the ID,
  the name: row stays, so one company shows twice. Two IDs with one name are usually an old company and a new one. A
  shared website is often a group with several companies.
- **Options:**
  - **A.** Merge a name: key into the Business ID key when the folded names are equal and the ID's record is active.
    Keep two Business IDs apart, and show "same name as <ID>". Treat a shared website as a group hint only.
  - **B.** Merge on a name match alone, Business IDs included.
  - **C.** Leave all as is.
- **Recommendation:** A. A Business ID is a legal identity and two IDs are two companies. A name: key is a placeholder
  that a register record should replace. Merging is an import step for the chief, after the freeze.
- **Other records affected:** the 6, 15 and 31 groups listed. All 6 name: rows are feed companies.

### B1-13. An EU project dated by a start date that has not happened yet

- **Affected records:** 6 eu_project signals (snapshot) dated 2026-11-01 to 2027-03-01. Examples: Spatineo Oy and
  Pegasor Oy, both 2026-11-01.
- **Problem:** A18 says an event date is the day it happened. A future project start has not happened; the grant
  agreement has.
- **Options:**
  - **A.** Date the signal by the grant signature date (`ecSignatureDate` in the CORDIS project file) when the record
    states it. Otherwise use the start date, labelled "planned start".
  - **B.** Keep the start date, and hide future-dated signals from the feed until the date passes.
  - **C.** Keep as is.
- **Recommendation:** A. The signature is the dated public event a scout could have seen.
- **Other records affected:** 6 on the snapshot. Any CORDIS row with a future start in the live store.

### B1-14. One framework contract total stored on each winner

- **Affected records:** 35 Hilma notices stored with the same amount on 2 or more companies (89 companies, snapshot).
  Example: notice 8427/17818, EUR 20,000,000 on each of 2 winners.
- **Problem:** A19 stores the amount the source states. For a framework with several winners, Hilma states the
  framework total, so each winner reads as if it won all of it. The sum over companies overstates by the number of winners.
- **Options:**
  - **A.** Keep the amount, and label it "framework total, N winners" when one notice has more than one winner in the store.
  - **B.** Divide by the number of winners. This is a computed figure no source states.
  - **C.** Drop the amount for multi-winner notices.
- **Recommendation:** A. It stays a figure the source states (A19), and the label prevents the misreading.
- **Other records affected:** 7 of the 28 Hilma amounts over 10 times the median (EUR 1,000,000) are such shared notices.

### B1-15. Amounts far from the rest, and zero amounts

- **Affected records (snapshot):**
  - 64 amounts over 10 times their type's median: 34 Business Finland rows (17 companies, the largest EUR 77.8 million to
    a listed company), 28 Hilma and 2 CORDIS.
  - 3 Business Finland rows have amount 0. Example: Addcomposites Oy, 2024: "funding type and split not stated".
- **Problem:** A large amount may be real, a framework total (B1-14) or a units error. An amount of 0 reads as "EUR 0
  granted", but the export row only states no split.
- **Options:**
  - **A.** Keep large amounts as stated (A19), with no flag. Store NULL instead of 0 when the export's total is 0, so a
    page prints "amount not stated".
  - **B.** Flag amounts over 10 times the median on the page.
  - **C.** Keep as is.
- **Recommendation:** A. A large amount is a figure the source states. The largest are Business Finland yearly totals
  per company, as the adapter adds up the export's columns. A 0 that means "not stated" breaks A25 (empty is empty).
- **Other records affected:** 3 zero rows on the snapshot. The live count is in the chief's run.

### Checked, nothing to ask

- **Business IDs:** every Business ID in the live store (17,193 rows) has a valid check digit.
- **Country codes:** every country code is ISO 3166-1 alpha-2.
- **Dates:** no founding date is after today.
- **Companies that are also investors:**
  - The live store is not checked: the API has no investor list.
  - On the snapshot, no company in the store is also on `investors.csv` or on the capital side of the ecosystem dataset.
- **Event dates before registration:** no dated event is before its company's registration date (snapshot, compared at
  the event's precision).
- **Hilma and CORDIS amounts:** every stored amount equals the one EUR figure its own row states (snapshot).
- **Not run:** links that redirect to another company. That needs one fetch per link, and this batch makes no new fetches.
