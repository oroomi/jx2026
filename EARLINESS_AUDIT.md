# Earliness audit (cloud/earliness_audit), Fri 16 Oct 2026, about 22:40 UTC

Question: why does the live `/backtest` say the radar would have flagged almost none of the 19 Nordic Blue 2026 cohort companies before January 2026, and which of the new dated record types are honest discovery signals?

## 0. How the numbers were produced

- **Live data (section 1).** I read the 19 company pages on https://jx.hankintaviikko.fi/c/{key} at about 22:35 UTC on 16 Oct 2026, rebuilt a local database from exactly what they show (facts, and every stored signal with type, date, confidence and source URL) and ran `radar.earliness.backtest` on it. With the thesis files as they were on main it reproduces the live page: **0 earlier, 0 declared, 1 later, 18 none**.
- **What the live store does not hold yet (section 6).** The live cohort pages hold no `first_sales`, `first_hire`, `equity_event`, `research_output`, `website_*` or ecosystem events. To see what the backtest reads once those adapters have run on the VPS, I ran the repo's own `tax_registers` and `ecosystem` adapters against the same 19 companies (public PRH data and the declared ecosystem dataset in the repo). OpenAlex and the web archive could not be run from this session (the egress proxy refused api.openalex.org and web.archive.org), so `research_output` and `website_*` are untested on real data. `eu_grant` is not yet a registered signal type in `radar/emit.py`, so it has no rows.
- Reference date is the default 2026-01-01 (the programme start month, declared by the team, not an entry date). No per-company entry dates exist.

## 1. Every stored signal of the 19 cohort companies on the live site

Rule used (`store.explain`, the same test the feed uses): the industry code is on the thesis list, or a thesis word is in the registered line of business, or in the source's own text, or a thesis word in the legal name is backed by a second independent source. A register entry also needs a registration no more than 5 years before the reference date.

**Pattern.** 12 of the 19 companies are not Finnish registrants in our data (DK, SE, NO, ES, BG, plus Edilm with no business ID). They have no business ID, so no register, tax-register or notice record can be joined, and their only possible live source is CORDIS (NIDO Contech: one EU project dated 2026-06-01, which the rule does not admit because the company has no industry code or description and no thesis word in its name). Of the 7 Finnish companies with a business ID, 4 are off the thesis code list (Emission-Eye 62100, Finnish Sauna Shop 47279, Taikoa 70200, Sireness 72100), 2 are older than the 5-year cut (Arctic Fry registered 2020, Kilocode 2003), and Sub Marine Store is admitted by name word plus a second source but only through a year-only Business Finland record dated 1 January 2026, which is on the reference day and so counts as later.

### Sub Marine Store Oy (3197621-7)

FI; business ID 3197621-7; founded 2021-03-15; industry 46900 Non-specialised wholesale trade. Group: **later** (0 months after (later or same, year only)).

Admitted by the thesis rule, but the first counted signal is dated on or after the reference date.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2021-03-15 | high | no | registered 2021-03-15, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3197621-7 |
| bf_funding | 2026-01-01 | high | yes | The legal name has 'marin' and a PRH/YTJ register record from 2021-03-15 supports it. | https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html |

### Arctic Fry Oy (3166759-6)

FI; business ID 3166759-6; founded 2020-10-23; industry 03220 Freshwater aquaculture. Group: **none**.

Why not found by the live rule: industry code 03220 is not on the thesis list; registered 2020-10-23, older than the 5-year cut.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2020-10-23 | high | no | registered 2020-10-23, older than the radar's 5-year cut, not counted | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3166759-6 |
| board_change | 2023-02-01 | high | no | board_change 2023-02-01: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2024-09-08 | high | no | board_change 2024-09-08: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2024-12-02 | high | no | board_change 2024-12-02: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2024-12-03 | high | no | board_change 2024-12-03: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2025-12-06 | high | no | board_change 2025-12-06: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2026-03-27 | high | no | board_change 2026-03-27: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2026-05-13 | high | no | board_change 2026-05-13: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2026-06-03 | high | no | board_change 2026-06-03: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |

### Edilm (fi-edilm)

FI; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined.

No stored signal.

### Emission-Eye Oy (3543918-7)

FI; business ID 3543918-7; founded 2025-06-13; industry 62100 Computer programming activities. Group: **none**.

Why not found by the live rule: industry code 62100 is not on the thesis list.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2025-06-13 | high | no | registered 2025-06-13, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3543918-7 |
| startup_notice | 2025-07-02 | high | no | startup_notice 2025-07-02, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3543918-7 |
| board_change | 2025-07-02 | high | no | board_change 2025-07-02: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3543918-7 |
| board_change | 2025-09-24 | high | no | board_change 2025-09-24: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3543918-7 |

### Finnish Sauna Shop Oy (3516783-9)

FI; business ID 3516783-9; founded 2025-03-08; industry 47279 Retail sale of other food n.e.c.. Group: **none**.

Why not found by the live rule: industry code 47279 is not on the thesis list.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2025-03-08 | high | no | registered 2025-03-08, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3516783-9 |
| startup_notice | 2025-03-14 | high | no | startup_notice 2025-03-14, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3516783-9 |
| board_change | 2025-03-14 | high | no | board_change 2025-03-14: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3516783-9 |

### Just-measure (dk-just-measure)

DK; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country DK: the register adapters cover Finland only.

No stored signal.

### Kilocode Oy (1840910-3)

FI; business ID 1840910-3; founded 2003-07-11; industry 58290 Other software publishing. Group: **none**.

Why not found by the live rule: industry code 58290 is not on the thesis list; registered 2003-07-11, older than the 5-year cut.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2003-07-11 | high | no | registered 2003-07-11, older than the radar's 5-year cut, not counted | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=1840910-3 |
| board_change | 2022-01-21 | high | no | board_change 2022-01-21: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/1840910-3 |

### MOR (se-mor)

SE; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country SE: the register adapters cover Finland only.

No stored signal.

### NIDO Contech (es-nido-contech)

ES; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country ES: the register adapters cover Finland only.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| eu_project | 2026-06-01 | medium | no | eu project 2026-06-01, outside the thesis rule | https://cordis.europa.eu/project/id/101292324 |

### PEATZ (dk-peatz)

DK; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country DK: the register adapters cover Finland only.

No stored signal.

### Race for Oceans Technology (dk-race-for-oceans-technology)

DK; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country DK: the register adapters cover Finland only.

No stored signal.

### RedGet.io (bg-redget-io)

BG; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country BG: the register adapters cover Finland only.

No stored signal.

### ReefCircular (dk-reefcircular)

DK; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country DK: the register adapters cover Finland only.

No stored signal.

### Sensemakers (dk-sensemakers)

DK; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country DK: the register adapters cover Finland only.

No stored signal.

### Sireness Oy (3568392-1)

FI; business ID 3568392-1; founded 2025-09-29; industry 72100 Research and experimental development on natural sciences and engineering. Group: **none**.

Why not found by the live rule: industry code 72100 is not on the thesis list.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2025-09-29 | high | no | registered 2025-09-29, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3568392-1 |
| startup_notice | 2025-10-08 | high | no | startup_notice 2025-10-08, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3568392-1 |
| board_change | 2025-10-08 | high | no | board_change 2025-10-08: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3568392-1 |

### Taikoa Oy (3380111-1)

FI; business ID 3380111-1; founded 2023-07-28; industry 70200 Business and other management consultancy activities. Group: **none**.

Why not found by the live rule: industry code 70200 is not on the thesis list.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2023-07-28 | high | no | registered 2023-07-28, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3380111-1 |
| startup_notice | 2023-08-10 | high | no | startup_notice 2023-08-10, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3380111-1 |
| board_change | 2023-08-10 | high | no | board_change 2023-08-10: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3380111-1 |
| board_change | 2025-11-20 | high | no | board_change 2025-11-20: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3380111-1 |
| bf_funding | 2026-01-01 | high | no | business finland funding 2026 (year only), outside the thesis rule | https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html |

### TuniSea (no-tunisea)

NO; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country NO: the register adapters cover Finland only.

No stored signal.

### VesselChain (es-vesselchain)

ES; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country ES: the register adapters cover Finland only.

No stored signal.

### Your Devocean (se-your-devocean)

SE; business ID none; founded not in public records; industry not in public records. Group: **none**.

Why not found by the live rule: no Finnish business ID, so no register, tax-register or notice record can be joined; country SE: the register adapters cover Finland only.

No stored signal.


## 2. Which new types are honest discovery signals

Test: a dated public record that a scout could have opened on that date, that says something about the company becoming real or traction, and whose date is the event date (not the fetch date). Negative records are shown but never counted as finds. Nothing dated after the reference can make a company "found earlier" (the backtest already files such companies under "later"; a test now pins this).

| Type | Decision | Written reason |
|---|---|---|
| `startup_notice` | **Counted** | The trade-register start-up notification is the public act of a new business starting, with an exact day. A scout could see it in the open notice feed that day. It is a discovery signal of the same kind as a register entry, and still has to pass the thesis rule. |
| `equity_event` | **Counted** | A registered share issue, capital increase or option programme is a dated, official record that money or equity moved. A scout could open it that day. It is validation more than discovery (investors found the company first), but for a fund it is the earliest public sign of a round. None of the 19 cohort companies has one in the current store. |
| `first_sales` | **Counted** (already listed) | Tax Administration VAT-liability or prepayment register entry, exact date, public in the open data. A company that is VAT-liable is invoicing. |
| `first_hire` (tax register) | **Counted** (already listed) | Employer register entry, exact date: the day the company could first pay a salary. The declared-research `first_hire` from the ecosystem dataset stays in the declared group. |
| `research_output` | **Counted** | An OpenAlex work that names the company in an author affiliation has a publication date that anyone could have found that day and shows technical activity before revenue. Matching is by whole-word company name in the raw affiliation string, so it is medium confidence and still has to pass the thesis rule. Untested on real data here (API blocked). |
| `website_milestone` | **Counted** | The first archived capture of a customers, careers or pricing page proves the page existed on or before that date, so the archive date can only make a company look later, never earlier than it was. A scout could open the archived capture. Untested on real data here (archive blocked). |
| `eu_grant` | **Counted** | Same nature as `eu_project`: a dated public award from the EU funding database, with a project or grant link. Not yet a registered type in `radar/emit.py`, so the entry in the thesis list is inert until the chief adds it. |
| `board_change` | **Refused** | A board of directors change is routine administration. Arctic Fry has 8 of them, Emission-Eye 2, and they say nothing about traction or about a company being new. Counting them would reward paperwork. Shown on `/backtest` with its date and this reason. |
| `capital_loss` | **Refused** | Negative record (loss of share capital). Shown, never counted as a find. |
| `sales_ended`, `employer_ended` | **Refused** | Negative records. Shown, never counted as a find. |
| `website_first_seen` | **Refused** | A website existing is not traction, and the first 200 capture is only an upper bound on when it appeared. Never counted alone (per the task); I also refuse it in combination, because the milestone type already carries the useful part. |
| Declared-research types (`pilot_named`, `certification`, `programme_entry`, `exhibitor`, `award`, `funding_round`, `product_launch`, `public_funding`) | **Unchanged** | They stay in the list and in the separate declared group, exactly as before. |

Changed files: `config/thesis.yaml` and `config/thesis_health_turku.yaml` (`feed_signal_types` gains `startup_notice`, `equity_event`, `research_output`, `website_milestone`, `eu_grant`, with a comment naming the refused types), and `radar/earliness.py` (a refused signal now prints its date and its reason on `/backtest`, for example "board change 2025-09-24: routine filing, not evidence of traction or discovery", instead of "type board_change is not a feed signal type in this thesis"). Note that `feed_signal_types` is shared with the feed, so the feed now also counts these types as entry signals for a company.

## 3. Four group counts before and after step 2

| Data | Thesis lists | Earlier (live) | Earlier (declared research only) | Later | None |
|---|---|---|---|---|---|
| Live store as it is now | before (main) | 0 | 0 | 1 | 18 |
| Live store as it is now | after step 2 | 0 | 0 | 1 | 18 |
| Live store plus local `tax_registers` and `ecosystem` runs | before | 1 | 12 | 5 | 1 |
| Live store plus local `tax_registers` and `ecosystem` runs | after step 2 | 1 | 12 | 5 | 1 |

Step 2 changes no group count today, and that is the honest result: the only new-type records the 19 companies hold are 4 `startup_notice` and 15 `board_change` rows, the four start-up notices belong to companies that the thesis rule does not admit (Emission-Eye, Finnish Sauna Shop, Taikoa, Sireness), and `first_sales` and `first_hire` were already counted. The counted types matter for companies the rule admits; the rule, not the type list, is what holds the number at zero.

## 4. Proposed thesis change (NOT applied)

Add one industry code to `industry_codes` in `config/thesis.yaml`:

```
  - {code: "72100", note: "Research and experimental development on natural sciences and engineering"}
```

The official name is the one PRH prints beside the code on Sireness Oy (`/c/3568392-1`). The list today carries `72190` ("R&D in natural sciences and engineering"); PRH returned 0 companies with main business line 72190 and 30 with 72100 among registrations from 2026-07-18 to 2026-10-16 (YTJ API, `mainBusinessLine` plus registration dates; the date filter can also match later changes, so 30 is an upper bound). Keep 72190 so nothing is removed.

| Backtest | Earlier | Declared | Later | None |
|---|---|---|---|---|
| Live store, without the change | 0 | 0 | 1 | 18 |
| Live store, with 72100 | **1** (Sireness Oy, register entry 2025-09-29, 3 months before) | 0 | 1 | 17 |
| With local tax and ecosystem runs, without | 1 | 12 | 5 | 1 |
| With local tax and ecosystem runs, with 72100 | 2 (Sub Marine Store Oy 57 months, Sireness Oy 3 months) | 11 | 5 | 1 |

Cost, stated plainly: the code is coarse, so the feed would gain up to about 30 low-confidence "industry code" rows per 90 days. They would sit under "How sure: low, matched on industry code only", and the main list is sorted by confidence. For comparison, `62100` (Emission-Eye's code, "Computer programming activities") had 469 registrations in the same window, so it must NOT be added; Emission-Eye can only be found by evidence other than its code. `03220` (Arctic Fry, "Freshwater aquaculture") had 1 registration in the window and would not help the cohort because Arctic Fry is older than the 5-year cut. I did not apply the change because it is a judgement about noise for the chief and the partners, and because Sireness' fit to the blue economy is not stated in any record I read.

## 5. Findings the chief should know

1. **Five "later" companies are later only because of the cohort announcement itself.** With the ecosystem adapter run, Arctic Fry, Edilm, Emission-Eye, Just-measure and RedGet.io each get a high-confidence `ecosystem_event` dated 2026-02-09, source https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/, detail "accelerator_or_programme_entry". That is the cohort entry announcement. It is circular as evidence of earliness (it is the event the backtest is measured against). Proposed, not applied: ignore programme-entry events of the cohort being tested when forming the "first counted signal".
2. **Sub Marine Store's 57 months is a same-day record.** Its `first_sales` is dated 2021-03-15, the same day as its register entry. It is an exact record, but it shows the company was VAT-liable on registration, not that anyone saw traction 57 months ahead.
3. **PRH re-registered main business lines on 2026-01-01 under a new code set** (Emission-Eye's record shows `typeCodeSet: TOIMI4` and `registrationDate: 2026-01-01`). Codes on the thesis list were written against the older set. This is the likely reason `72190` returns no new registrations. Worth checking the whole `industry_codes` list against current PRH codes (not done here).
4. **Cohort members without a Finnish business ID are blank by construction.** 12 of 19 have no way to receive a register, tax or notice record. Only declared research (ecosystem dataset) reaches them, which is why the declared group is where most of the cohort shows up in section 6.

## 6. What the backtest reads once tax-register and ecosystem data are loaded (computed here, not yet live)

Same 19 companies, live facts plus the local `tax_registers` run (11 signals for 7 Finnish companies) and the `ecosystem` run (declared research with sources). Groups: **1 earlier, 12 declared, 5 later, 1 none**. This is a preview from public data, not what the site shows today.

### Sub Marine Store Oy (3197621-7)

FI; business ID 3197621-7; founded 2021-03-15; industry 46900 Non-specialised wholesale trade. Group: **earlier** (57 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2021-03-15 | high | yes | The legal name has 'marin' and a PRH/YTJ tax registers record from 2021-03-15 supports it. | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3197621-7 |
| first_sales | 2021-03-15 | high | yes | The legal name has 'marin' and a PRH/YTJ register record from 2021-03-15 supports it. | https://tietopalvelu.ytj.fi/yritys/3197621-7 |
| ecosystem_event | 2023-01-01 | low | no | declared research with low confidence, not counted | https://www.substore.fi/pages/about |
| bf_funding | 2026-01-01 | high | yes | The legal name has 'marin' and a PRH/YTJ register record from 2021-03-15 supports it. | https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### NIDO Contech (es-nido-contech)

ES; business ID none; founded not in public records; industry not in public records. Group: **declared** (26 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| pilot_named | 2023-10-31 | medium | yes | declared research event with medium confidence | https://www.df.cl/capital/cultura/la-startup-de-una-chilena-que-busca-crear-una-casa-completamente |
| award | 2024-11-13 | medium | yes | declared research event with medium confidence | https://sitiospublicos.bancochile.cl/nuestro-banco/es/sala-de-prensa/detalle/emprendedora-bioclimatica |
| award | 2025-01-01 | low | no | declared research with low confidence, not counted | https://ecosistemastartup.com/?p=80135 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| ecosystem_event | 2026-05-11 | low | no | declared research with low confidence, not counted | https://ecosistemastartup.com/?p=80227 |
| eu_project | 2026-06-01 | medium | no | eu project 2026-06-01, outside the thesis rule | https://cordis.europa.eu/project/id/101292324 |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/774063 |
| award | 2026-08-25 | high | yes | declared research event with high confidence | https://www.apelago.fi/press-release-apelago-initiative-2026-brought-together-350-blue-economy-leaders-in-turku/ |
| award | 2026-08-31 | medium | yes | declared research event with medium confidence | https://www.descubre.vc/noticia/la-startup-con-ra-ces-chilenas-nido-contech-triunfa-en-el-a-pelago-pitch-challenge-en-finlandia-2026-08-25 |

### PEATZ (dk-peatz)

DK; business ID none; founded not in public records; industry not in public records. Group: **declared** (24 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| award | 2022-01-01 | low | no | declared research with low confidence, not counted | https://philab.esa.int/wp-content/uploads/sites/3/2024/12/Pitch-Deck_PEATZ_final.pdf |
| programme_entry | 2024-01-01 | medium | yes | declared research event with medium confidence | https://philab.esa.int/wp-content/uploads/sites/3/2024/12/Pitch-Deck_PEATZ_final.pdf |
| public_funding | 2024-11-30 | medium | yes | declared research event with medium confidence | https://philab.esa.int/wp-content/uploads/sites/3/2024/12/Pitch-Deck_PEATZ_final.pdf |
| pilot_named | 2024-11-30 | low | no | declared research with low confidence, not counted | https://philab.esa.int/wp-content/uploads/sites/3/2024/12/Pitch-Deck_PEATZ_final.pdf |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### ReefCircular (dk-reefcircular)

DK; business ID none; founded not in public records; industry not in public records. Group: **declared** (24 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| award | 2024-01-01 | high | yes | declared research event with high confidence | https://www.danishdesignaward.com/projects/reeftile |
| funding_round | 2024-02-15 | high | yes | declared research event with high confidence | https://www.mynewsdesk.com/dk/roest-kommunikation/pressreleases/paa-kanten-af-udvisning-til-fremadstormende-startup-kathryn-larsen-har-faaet-investeringer-for-over-1-million-kroner-i-nyt-projekt-der-skal-hjaelpe-havmiljoeet-3304218 |
| pilot_named | 2024-06-14 | high | yes | declared research event with high confidence | https://www.sn.dk/art5625859/halsnaes/nyhed/havn-faar-kunstige-rev/ |
| public_funding | 2025-02-03 | high | yes | declared research event with high confidence | https://via.ritzau.dk/pressemeddelelse/14246473/reefcircular-sikrer-forste-store-internationale-projekt-der-skal-forbedre-biodiversiteten-i-havet-ud-for-skotlands-kyst |
| pilot_named | 2025-02-04 | high | yes | declared research event with high confidence | https://kemifokus.dk/reefcircular-skal-forbedre-biodiversiteten-i-havet-ud-for-skotlands-kyst |
| ecosystem_event | 2025-03-22 | medium | yes | declared research event with medium confidence | https://www.reefcircular.com/projects-reefcircular |
| award | 2025-08-25 | medium | yes | declared research event with medium confidence | https://midspar.dk/klimaboost/reefcircular-har-potentiale-til-at-blive-havets-bedste-ven/ |
| award | 2025-10-10 | medium | yes | declared research event with medium confidence | https://nordicwomenintechawards.com/winners-2025/ |
| ecosystem_event | 2025-11-20 | high | yes | declared research event with high confidence | https://www.cleancluster.dk/en/case/reefcircular-lands-international-dream-partner-new-collaboration-with-wsp-stems-directly-from-clean-funded-pilot/ |
| public_funding | 2025-11-20 | high | yes | declared research event with high confidence | https://www.cleancluster.dk/en/case/reefcircular-lands-international-dream-partner-new-collaboration-with-wsp-stems-directly-from-clean-funded-pilot/ |
| ecosystem_event | 2026-01-01 | medium | yes | declared research event with medium confidence | https://www.reefcircular.com/projects-reefcircular |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| award | 2026-06-30 | high | yes | declared research event with high confidence | https://invest4nature.eu/2026/06/16/strong-showing-from-nature-based-enterprises-at-eu-green-week/ |
| ecosystem_event | 2026-07-31 | medium | yes | declared research event with medium confidence | https://www.reefcircular.com/projects-reefcircular |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/772623 |

### VesselChain (es-vesselchain)

ES; business ID none; founded not in public records; industry not in public records. Group: **declared** (22 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| exhibitor | 2024-02-29 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/891 |
| exhibitor | 2024-06-05 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/913 |
| exhibitor | 2024-06-12 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/913 |
| exhibitor | 2024-07-31 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/917 |
| award | 2024-11-25 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/946 |
| public_funding | 2025-02-24 | low | no | declared research with low confidence, not counted | https://www.jelurida.com/es/node/962 |
| product_launch | 2025-05-26 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/987 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| ecosystem_event | 2026-04-21 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/1066 |
| exhibitor | 2026-04-30 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/1066 |
| exhibitor | 2026-08-20 | medium | yes | declared research event with medium confidence | https://www.jelurida.com/es/node/1081 |
| exhibitor | 2026-09-16 | low | no | declared research with low confidence, not counted | https://www.jelurida.com/es/node/1084 |

### Race for Oceans Technology (dk-race-for-oceans-technology)

DK; business ID none; founded not in public records; industry not in public records. Group: **declared** (18 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| exhibitor | 2024-06-30 | medium | yes | declared research event with medium confidence | https://gotoams.nl/2024 |
| exhibitor | 2024-10-31 | medium | yes | declared research event with medium confidence | https://event.ing.dk/dts2024/speaker/1361961/signe-simonsen |
| public_funding | 2026-01-01 | low | no | declared research with low confidence, not counted | https://www.raceforoceanstechnology.com/about |
| first_hire | 2026-01-01 | low | no | declared research with low confidence, not counted | https://www.raceforoceanstechnology.com/about |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### MOR (se-mor)

SE; business ID none; founded not in public records; industry not in public records. Group: **declared** (14 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| exhibitor | 2024-10-31 | medium | yes | declared research event with medium confidence | https://garvemor.se/pages/about-us |
| exhibitor | 2025-01-01 | low | no | declared research with low confidence, not counted | https://garvemor.se/pages/about-us |
| exhibitor | 2025-11-08 | medium | yes | declared research event with medium confidence | https://garvemor.se/blogs/nyheter/mor-at-the-slow-fashion-gala-in-stockholm |
| programme_entry | 2026-01-01 | low | no | declared research with low confidence, not counted | https://garvemor.se/pages/about-us |
| pilot_named | 2026-01-01 | low | no | declared research with low confidence, not counted | https://garvemor.se/pages/about-us |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| ecosystem_event | 2026-03-19 | medium | yes | declared research event with medium confidence | https://garvemor.se/blogs/nyheter/mor-s-visit-to-toolspace-and-plans-for-scaling-fish-skin-production |
| exhibitor | 2026-04-29 | medium | yes | declared research event with medium confidence | https://garvemor.se/blogs/nyheter/webinar-india-eu-free-trade-agreement-mor-as-an-example-of-circular-economy-business |
| exhibitor | 2026-09-29 | medium | yes | declared research event with medium confidence | https://garvemor.se/blogs/nyheter |

### Kilocode Oy (1840910-3)

FI; business ID 1840910-3; founded 2003-07-11; industry 58290 Other software publishing. Group: **declared** (13 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2003-07-11 | high | no | registered 2003-07-11, older than the radar's 5-year cut, not counted | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=1840910-3 |
| first_sales | 2003-08-01 | high | no | first sales 2003-08-01, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/1840910-3 |
| board_change | 2022-01-21 | high | no | board_change 2022-01-21: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/1840910-3 |
| ecosystem_event | 2024-11-04 | medium | yes | declared research event with medium confidence | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?name=Kilocode |
| first_hire | 2025-01-03 | high | no | first hire 2025-01-03, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/1840910-3 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/780532 |

### Sensemakers (dk-sensemakers)

DK; business ID none; founded not in public records; industry not in public records. Group: **declared** (12 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| public_funding | 2024-12-23 | medium | yes | declared research event with medium confidence | https://business.esa.int/projects/autonomous-offshore-usv |
| product_launch | 2025-03-03 | medium | yes | declared research event with medium confidence | https://www.doi.dk/en/ptx/artikel/bornholmsk-startup-vil-overvaage-havmiljoeet-med-ny-teknologi |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| exhibitor | 2026-04-21 | high | yes | declared research event with high confidence | https://dasya.itu.dk/posts/watathon/ |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/798000 |

### Sireness Oy (3568392-1)

FI; business ID 3568392-1; founded 2025-09-29; industry 72100 Research and experimental development on natural sciences and engineering. Group: **declared** (8 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| public_funding | 2025-04-30 | medium | yes | declared research event with medium confidence | https://www.alandsbanken.fi/news/alandsbankenin_itameriprojekti_jakaa_550_000_euroa_itameren_tilaa/pdf |
| register_entry | 2025-09-29 | high | no | registered 2025-09-29, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3568392-1 |
| first_sales | 2025-09-29 | high | no | first sales 2025-09-29, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3568392-1 |
| first_hire | 2025-09-29 | high | no | first hire 2025-09-29, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3568392-1 |
| startup_notice | 2025-10-08 | high | no | startup_notice 2025-10-08, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3568392-1 |
| board_change | 2025-10-08 | high | no | board_change 2025-10-08: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3568392-1 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### Your Devocean (se-your-devocean)

SE; business ID none; founded not in public records; industry not in public records. Group: **declared** (8 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| exhibitor | 2025-04-03 | high | yes | declared research event with high confidence | https://www.wedonthavetime.org/events/move-the-money-investor-matchmaking-5 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/791072 |

### TuniSea (no-tunisea)

NO; business ID none; founded not in public records; industry not in public records. Group: **declared** (3 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| ecosystem_event | 2025-09-28 | medium | yes | declared research event with medium confidence | https://tunisea.no/ |
| product_launch | 2025-12-08 | medium | yes | declared research event with medium confidence | https://tunisea.no/ |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| ecosystem_event | 2026-02-24 | low | no | declared research with low confidence, not counted | https://data.brreg.no/enhetsregisteret/api/enheter/936277241 |
| first_hire | 2026-07-10 | low | no | declared research with low confidence, not counted | https://data.brreg.no/enhetsregisteret/api/enheter/936277241 |

### Finnish Sauna Shop Oy (3516783-9)

FI; business ID 3516783-9; founded 2025-03-08; industry 47279 Retail sale of other food n.e.c.. Group: **declared** (2 months before).

Admitted by the thesis rule.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2025-03-08 | high | no | registered 2025-03-08, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3516783-9 |
| first_sales | 2025-03-08 | high | no | first sales 2025-03-08, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3516783-9 |
| first_hire | 2025-03-08 | high | no | first hire 2025-03-08, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3516783-9 |
| startup_notice | 2025-03-14 | high | no | startup_notice 2025-03-14, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3516783-9 |
| board_change | 2025-03-14 | high | no | board_change 2025-03-14: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3516783-9 |
| exhibitor | 2025-06-04 | low | no | declared research with low confidence, not counted | https://www.b2match.com/e/wsf2025matchmaking/participations/533281 |
| product_launch | 2025-10-16 | high | yes | declared research event with high confidence | https://www.messukeskus.com/?p=59796 |
| pilot_named | 2025-10-28 | medium | yes | declared research event with medium confidence | https://saunafromfinland.com/?p=20093 |
| product_launch | 2025-10-31 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/wsf2025matchmaking/participations/533281 |
| product_launch | 2025-11-13 | high | yes | declared research event with high confidence | https://www.sauna-ing.com/fi/blogs/uutisia/origin-by-ocean-from-ocean-challenge-to-skincare-innovation |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### Arctic Fry Oy (3166759-6)

FI; business ID 3166759-6; founded 2020-10-23; industry 03220 Freshwater aquaculture. Group: **later** (1 months after).

Admitted by the thesis rule, but the first counted signal is dated on or after the reference date.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| first_sales | 2020-10-05 | high | no | first sales 2020-10-05, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3166759-6 |
| register_entry | 2020-10-23 | high | no | registered 2020-10-23, older than the radar's 5-year cut, not counted | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3166759-6 |
| board_change | 2023-02-01 | high | no | board_change 2023-02-01: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2024-09-08 | high | no | board_change 2024-09-08: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2024-12-02 | high | no | board_change 2024-12-02: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2024-12-03 | high | no | board_change 2024-12-03: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| first_hire | 2025-04-01 | high | no | first hire 2025-04-01, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3166759-6 |
| board_change | 2025-12-06 | high | no | board_change 2025-12-06: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| board_change | 2026-03-27 | high | no | board_change 2026-03-27: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2026-05-13 | high | no | board_change 2026-05-13: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |
| board_change | 2026-06-03 | high | no | board_change 2026-06-03: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3166759-6 |

### Edilm (fi-edilm)

FI; business ID none; founded not in public records; industry not in public records. Group: **later** (1 months after).

Admitted by the thesis rule, but the first counted signal is dated on or after the reference date.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| programme_entry | 2024-01-01 | low | no | declared research with low confidence, not counted | https://www.eitfood.eu/community/startups/edilm |
| programme_entry | 2025-06-30 | low | no | declared research with low confidence, not counted | https://www.eitfood.eu/community/startups/edilm |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### Emission-Eye Oy (3543918-7)

FI; business ID 3543918-7; founded 2025-06-13; industry 62100 Computer programming activities. Group: **later** (1 months after).

Admitted by the thesis rule, but the first counted signal is dated on or after the reference date.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2025-06-13 | high | no | registered 2025-06-13, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3543918-7 |
| startup_notice | 2025-07-02 | high | no | startup_notice 2025-07-02, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3543918-7 |
| board_change | 2025-07-02 | high | no | board_change 2025-07-02: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3543918-7 |
| first_sales | 2025-08-01 | high | no | first sales 2025-08-01, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3543918-7 |
| board_change | 2025-09-24 | high | no | board_change 2025-09-24: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3543918-7 |
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| exhibitor | 2026-05-31 | medium | yes | declared research event with medium confidence | https://startupcenter.aalto.fi/we-are-going-to-latitude-59-in-tallinn |
| patent | 2026-05-31 | low | no | declared research with low confidence, not counted | https://startupcenter.aalto.fi/we-are-going-to-latitude-59-in-tallinn |
| ecosystem_event | 2026-07-19 | low | no | declared research with low confidence, not counted | https://www.b2match.com/e/apelago-initiative-matchmaking/opportunities/UGFydGljaXBhdGlvbk9wcG9ydHVuaXR5OjI0ODMzMA== |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/769881 |

### Just-measure (dk-just-measure)

DK; business ID none; founded not in public records; industry not in public records. Group: **later** (1 months after).

Admitted by the thesis rule, but the first counted signal is dated on or after the reference date.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |
| product_launch | 2026-07-15 | medium | yes | declared research event with medium confidence | https://just-measure.com/case-studies |
| ecosystem_event | 2026-07-15 | medium | yes | declared research event with medium confidence | https://just-measure.com/case-studies/jmar-in-action |
| exhibitor | 2026-08-19 | medium | yes | declared research event with medium confidence | https://www.b2match.com/e/apelago-initiative-matchmaking/participations/789199 |

### RedGet.io (bg-redget-io)

BG; business ID none; founded not in public records; industry not in public records. Group: **later** (1 months after).

Admitted by the thesis rule, but the first counted signal is dated on or after the reference date.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| ecosystem_event | 2026-02-09 | high | yes | declared research event with high confidence | https://www.apelago.fi/nordic-blue-2026-meet-our-next-batch/ |

### Taikoa Oy (3380111-1)

FI; business ID 3380111-1; founded 2023-07-28; industry 70200 Business and other management consultancy activities. Group: **none**.

Why not found by the live rule: industry code 70200 is not on the thesis list.

| Type | Date | Confidence | Counted | Why / rule | Source |
|---|---|---|---|---|---|
| register_entry | 2023-07-28 | high | no | registered 2023-07-28, outside the thesis rule | https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3380111-1 |
| first_sales | 2023-07-28 | high | no | first sales 2023-07-28, outside the thesis rule | https://tietopalvelu.ytj.fi/yritys/3380111-1 |
| startup_notice | 2023-08-10 | high | no | startup_notice 2023-08-10, outside the thesis rule | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3380111-1 |
| board_change | 2023-08-10 | high | no | board_change 2023-08-10: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3380111-1 |
| board_change | 2025-11-20 | high | no | board_change 2025-11-20: routine filing, not evidence of traction or discovery | https://avoindata.prh.fi/opendata-registerednotices-api/v3/3380111-1 |
| bf_funding | 2026-01-01 | high | no | business finland funding 2026 (year only), outside the thesis rule | https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html |

