# Assessment benchmarks used by accelerators and early-stage investors

Researched 16 Oct 2026 for the Ocean Opportunity Radar (JunctionX Turku 2026), branch `cloud/benchmarks`. Research only: no application code, no data, no other doc touched.

## Evidence basis (read this first)

None of the primary pages could be opened from the build sandbox: the network policy refused every host (DNS failure for the fetch tool, tunnel refusal for curl). Everything below comes from web-search result text about the cited pages, so:

- A fact marked **not retrieved** was not in what I could see. It is a gap, not a "no".
- Numbers about a vendor's own coverage or accuracy (millions of companies, "6 to 12 months earlier") are the vendor's claims. I found no independent check of any of them.
- Weights and formulas of the proprietary scores (Dealroom Signal, Crunchbase, Specter, Harmonic) are not public in anything I saw.
- Where sources disagree, the disagreement is stated, not resolved. The list to verify on the primary page before quoting to judges is at the end.

## Summary

"No financials" means: can an early company with no financial statements be assessed at all? A "Yes" is not the same as "from public records": most of these need the company's own input.

| Benchmark | What it is | Who uses it | Startup with no financial statements? | Input comes from |
|---|---|---|---|---|
| Village Capital VIRAL | 9 levels x 8 categories, self-assessed | Village Capital, Maine Technology Institute, NRV (a fund) | Partly: early milestones yes, upper levels use sales and revenue facts | The founder |
| KTH Innovation Readiness Level | 9 levels x 6 dimensions, licensed | Universities and innovation agencies | Yes by design (not stated outright) | The team, with an assessor |
| EIC Accelerator readiness use | TRL 6 to 8 plus market and business readiness, inside a funding application | European Innovation Council and its evaluators | Partly: pre-revenue can apply, must show forecasts and resources | The applicant's dossier |
| Dealroom Signal | 1 to 100 "about to raise" score | VCs, corporates, government enablers, founders | Probably, not stated | Dealroom's own database |
| Crunchbase Growth, Heat, Rank | 0 to 100 scores | Crunchbase subscribers | Mostly no: no score without a financing event or a strong prediction | Crunchbase's own database |
| Specter | Signal feeds on talent, interest, company, strategic events | Investment firms | Yes, built for stealth | Vendor's undisclosed sources |
| Harmonic | Discovery engine with saved-search signals | VC firms, business development teams | Yes, built for pre-funding | Vendor's sources |
| Ocean Impact Navigator | Open impact KPI framework for ocean startups | 1000 Ocean Startups members, Katapult Ocean, others | Yes: impact, not finance | The company's reported KPIs |
| 1000 Ocean Startups | Coalition with qualitative entry criteria | 32 member organisations | Not a scoring tool | Member programmes |

## Village Capital VIRAL

- **What:** Venture Investment-Readiness and Awareness Levels. Nine levels, eight categories: Team, Problem & Vision, Value Prop, Product, Market, Business Model, Scale, Exit. The founder circles the highest level completed in each category; the lowest circle sets the overall level; then picks 1 to 3 milestones to level up.
- **Who uses it:** Village Capital created it. The Maine Technology Institute uses it as a self-assessment before funding decisions and for a baseline and follow-on assessment of funded companies (an online version, Abaca, exists for Maine enterprises). NRV, a Richmond, Virginia fund, runs an initial VIRAL diagnosis on companies that approach it. Investors use it to say at which level they invest.
- **Inputs:** The founder's own judgement against level descriptors. Descriptors seen: level 6 "sales beyond initial target customers"; level 7 "majority of first sales in target market are inbound"; level 8 "multiple renewals with low sales effort"; level 9 "minimum 2x revenue growth for multiple years". Levels 1 to 5: **not retrieved**.
- **No financial statements?** Partly. The method is milestone-based self-assessment, not statement-based, so an early company can place itself. The upper levels need sales and revenue facts that only the company has. It cannot be run from public records.
- **Sources:** [VIRAL trifold (MTI)](https://www.mainetechnology.org/wp-content/uploads/VIRAL-Trifold-1.pdf), [MTI levels overview](https://www.mainetechnology.org/wp-content/uploads/MTI-VIRAL-Levels-Overview-1.pdf), [MTI explainer](https://www.mainetechnology.org/updates/whats-a-viral-assessment-and-why-is-it-important-to-mti/), [Unreasonable Group](https://unreasonablegroup.com/articles/vc-advice-entrepreneurs-hate-fundraising/)

## KTH Innovation Readiness Level (IRL)

- **What:** A model from KTH Innovation at KTH Royal Institute of Technology, Sweden, inspired by NASA's TRL. Nine levels per dimension, six dimensions. DTU says each dimension has level definitions plus the milestones and activities needed to reach the next level. Dimension names, from secondary sources: Funding, Customer, Technology, Business Model, Intellectual Property Rights, Team. Two sources count differently (five at IFW Dresden, eight in an adaptation at Halmstad University's LEAP for Life); I treat those as adaptations.
- **Who uses it:** DTU holds a licence from KTH Innovation. Other users named in the results: McGill (Innovsanté), the Academy of Sciences Malaysia, the Czech Academy of Sciences transfer office, and Dresden institutions. One secondary source also lists Imperial College, Vinnova and Aalto University; I could not confirm that on a primary page.
- **Inputs:** An innovation case described against each dimension. The results describe a scored model applied to a case; **no interview method or evidence list retrieved**.
- **No financial statements?** Yes by design, though no source says it outright. Funding is one dimension scored as a level, not from statements. It still needs the team's own answers; public records can fill only parts (Technology from patents and EU projects, Funding from grants).
- **Licence note:** The model is trademarked and licensed ("KTH Innovation Readiness Level™"). Do not copy its wording into the product.
- **Sources:** [DTU page](https://www.inside.dtu.dk/en/research/commercialisation-and-patenting/patents-and-software/kth-innovation-readiness-level), [KTH IRL site](https://wpmu-bis.sys.kth.se/irl/), [Academy of Sciences Malaysia](https://www.akademisains.gov.my/asm-irl/), [Czech Academy transfer office](https://transfer.cas.cz/portal/en/news?id=105)

## EIC Accelerator (how the EU funder uses readiness)

- **What:** Not a scoring index. A funding application where readiness decides eligibility. The EIC says the grant component finances TRL 6 to 8; the equity component can finance above TRL 8. Entry level is reported inconsistently: older material says TRL 5 and above, a 2026 summary says TRL 6, the EIB listing says 6 to 8. A national agency states that strong importance is given to market readiness and business readiness (Market and Business Readiness Level scales are in the EIC FAQ, **not retrieved**).
- **Who uses it:** The European Innovation Council and its evaluators. National agencies (Business Finland, the Israel Innovation Authority) publish applicant guidance.
- **Inputs:** Short application: a form (about 12 pages on the EIC page; one source says 5, check the current call), a pitch deck of up to 10 slides, a video of up to 3 minutes. A practitioner guide says basic financials appear at this stage. Full proposal: business plan, financial information, letters of intent, freedom-to-operate analysis, implementation plan.
- **No financial statements?** Partly. A pre-revenue startup can apply, but must show access to the resources to commercialise and scale (EIC wording as summarised), so forecasts are expected. It is an applicant-submitted dossier, not something assessable from outside.
- **In this repo:** `config/thesis.yaml` already carries the 4 Nov 2026 cut-off with a TRL window.
- **Sources:** [EIC tips for applicants](https://eic.ec.europa.eu/tips-applicants-eic-accelerator_en), [EIC Accelerator page](https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en), [EIB advisory](https://advisory.eib.org/future-finance-programme/eic-accelerator), [Business Finland guide (Aug 2023)](https://www.businessfinland.fi/4a2b51/globalassets/eic-accelerator_09082023.pdf)

## Dealroom Signal

- **What:** A 1 to 100 score meant to find companies about to raise, not to rate quality. Dealroom's knowledge base lists four inputs: completeness (profile fullness and fit to the user's segments), founding team (past performance, experience, serial founder, education), growth rate (headcount expansion; the launch post also mentions product growth), and timing (expected time to next round, from proprietary stage benchmarks). The launch post lists three inputs and omits timing. The knowledge-base text, as summarised, describes the score as the average of the four. Weights and formulas are not public. Pattern for funded companies: the score resets after funding and peaks about a year later.
- **Who uses it:** Per Dealroom's own materials, VCs, corporates, government enablers and founders. A separate Dealroom People Signal Score rates a founder's likelihood of building a venture-backed company; that is a person score and a different product.
- **Inputs:** Dealroom's own database: profile, team and headcount data.
- **No financial statements?** Probably, since no input named is a financial statement. No source says so explicitly, and the post-funding reset suggests funding events do matter.
- **Sources:** [Dealroom knowledge base](https://knowledge.dealroom.co/knowledge/dealroom-signal-1), [launch post](https://dealroom.co/blog/introducing-dealroom-signal), [founder guide](https://dealroom.co/blog/for-founders-how-to-improve-your-dealroom-signal)

## Crunchbase (Growth Score, Heat Score, CB Rank, Trend Score)

- **What:** Heat Score, 0 to 100: market interest from Crunchbase profile activity and recent media coverage, AI-generated, not editable. Growth Score, 0 to 100: blends historical data and predictions. Inputs listed: funding, headcount, operations, market share, financial, customer growth, M&A activity, investor history, and Crunchbase Predictions. Time decay and self-relative scaling; above 90 is strong recent growth, about 50 neutral. CB Rank and Trend Score: Crunchbase says proprietary algorithms; **no inputs or weights retrieved**.
- **Who uses it:** Crunchbase subscribers. Prediction data is a Crunchbase Business feature.
- **Eligibility rule (the important part):** A Growth Score is generated only for a company that is not a government-designated entity and has either a financing event of any kind or a high-conviction growth prediction (probability above 66 or below 33). Otherwise there is no score.
- **No financial statements?** Mostly no. A company with no financing event and no strong prediction gets no score at all, so the benchmark is silent exactly where early signals matter.
- **Sources:** [What is a Growth Score](https://support.crunchbase.com/hc/en-us/articles/39902124712211), [Technical overview](https://support.crunchbase.com/hc/en-us/articles/53295907409555), [What is a Heat Score](https://support.crunchbase.com/hc/en-us/articles/39902159873043/), [Interpreting Growth Scores](https://support.crunchbase.com/hc/en-us/articles/46180336353043-Interpreting-Growth-Scores-FAQ), [Crunchbase Rank](https://about.crunchbase.com/crunchbase-rank)

## Specter

- **What:** Signal feeds for investors. Talent signals: 1,000+ a day (vendor claim) from new stealth founders, spinouts, fresh YC founders and applicants; types New Company, New Role, Promotion, Searching, tagged Live, Stealth or Out of Stealth; no signal older than five days; each stamped with how many months it led the public announcement. Interest signals: which investors engage which companies, said to land weeks before a round is public. Company signals: revenue, news, talent and interest feeds. Strategic signals: the online and social behaviour of investors and corporate insiders, used to predict rounds and acquisitions. Vendor scale claims: 55M+ companies, 550M+ people, 330K+ investors, 1M+ transactions.
- **Who uses it:** Investment professionals; the vendor says "trusted by 300+ investment firms" and publishes a BeeNext case study.
- **Inputs:** **Underlying data sources not named; the stealth-detection method is not described** in anything retrieved.
- **No financial statements?** Yes, that is the product. The cost is an opaque method that tracks individuals' behaviour.
- **Sources:** [Platform](https://tryspecter.com/platform), [talent signals](https://www.tryspecter.com/signals/talent), [interest signals](https://www.tryspecter.com/signals/interest), [API](https://api.tryspecter.com/), [BeeNext case](https://insights.tryspecter.com/beenext-running-on-signal-not-serendipity/)

## Harmonic

- **What:** A startup discovery engine with saved searches that fire on matches. Vendor says it sources from legal filings and dozens of public sources, plus data from venture firms and accelerators and portfolio updates from investors. Signals named by third parties: stealth emergence, hiring spikes, founder movement, team growth, stealth domain activity, investor overlaps, portfolio alumni launching ventures. Vendor claims: 35M+ companies, 195M+ people, and getting venture-backable companies in front of investors 6 to 12 months before they appear elsewhere. Access via web console, Chrome extension, REST and GraphQL API; pricing custom.
- **Who uses it:** VC firms, business development teams, SaaS companies.
- **No financial statements?** Yes, early detection before funding is the pitch. **I found no independent evidence of its accuracy.**
- **Sources:** [How Harmonic serves VCs](https://harmonic.ai/blog/how-harmonic-serves-venture-capital-firms), [launch post](https://harmonic.ai/blog/introducing-harmonic-a-better-way-to-discover-and-invest-in-startups), [vs PitchBook](https://harmonic.ai/blog/harmonic-vs-pitchbook), [third-party review](https://techbullion.com/top-7-deal-sourcing-platforms-for-venture-capital-in-2025/)

## Ocean Impact Navigator (OIN)

- **What:** An open-source impact KPI framework for ocean startups and their investors, launched at the 2022 UN Ocean Conference by the 1000 Ocean Startups coalition with SYSTEMIQ, to harmonise impact measurement and reporting. A Technical Appendix proposes the KPIs and was labelled work in progress in 2022; an online tool was planned (current status **not confirmed**). The Ocean Impact Organisation adopted the six Ocean Impact Areas defined in OIN; **the six names and the KPI list were not retrieved**. GIIN's IRIS+ has a Marine Resource Conservation and Management theme with indicators aligned to OIN.
- **Who uses it:** 1000 Ocean Startups members; Katapult Ocean's 2024 impact report describes it as a structured framework to define, assess and communicate impact potential; the Ocean Impact Organisation; the Sasakawa Peace Foundation presents it for evaluating ocean opportunities. No independent evaluation of its effect found.
- **Inputs:** Impact KPIs reported by the company.
- **No financial statements?** Yes, because it measures impact, not finance. It is a reporting taxonomy, not a maturity score, and public records alone cannot fill it.
- **Sources:** [WEF report 2023](https://www3.weforum.org/docs/WEF_The_Ocean_Impact_Navigator_2023.pdf), [launch material (AquaDocs)](https://aquadocs.org/handle/1834/42789), [IRIS+ and OIN](https://iris.thegiin.org/document/iris-and-the-ocean-impact-navigator/), [Katapult Ocean 2024](https://katapult.vc/ocean/2024-impact-report-progress-challenges-and-the-path-to-a-thriving-blue-economy), [Ocean Impact Organisation](https://www.ocean-impact.org/pitchfest-2023), [Sasakawa Peace Foundation](https://www.spf.org/opri/en/event/20260914.html)

## 1000 Ocean Startups

- **What:** A coalition hosted by the World Economic Forum, not a scoring tool. Goal: scale at least 1,000 transformative startups by the end of the UN Ocean Decade to restore ocean health and meet SDG 14. WEF: 32 member organisations (VC funds, incubators, accelerators, innovation platforms) that have supported at least 330 ocean startups.
- **Criteria:** The only entry criteria found come from a third-party aggregator and are **unconfirmed**: an ocean-related solution, SDG 14 alignment, potential for scalability and impact. A Dealroom landscape "1000OS startups (Ocean, Blue Economy)" exists, and a 2025 conference paper analysed the database of 1000OS-backed startups.
- **No financial statements?** Not applicable: qualitative criteria, no score.
- **Sources:** [WEF ocean innovation](https://www.weforum.org/friends-of-ocean-action/ocean-innovation/), [IAU HESD entry](https://www.iau-hesd.net/action/1000-ocean-start-ups-coalition), [allbusiness.africa (third-party)](https://allbusiness.africa/investors/1000-ocean-startups), [Dealroom landscape](https://dealroom.co/charts/landscape-54611-1000os-startups-ocean-blue-economy.html), [OOS2025 paper](https://meetingorganizer.copernicus.org/OOS2025/OOS2025-1558.html)

## Also relevant: EU BlueInvest

The European Commission programme (launched 2019) gives selected blue-economy startups an investment readiness assessment and a business coach for three months; 202 businesses received readiness assistance in the first edition (EU Blue Economy Observatory, Oct 2023). A BlueInvest grant call expects TRL 6 to 8. This repo already reads BlueInvest profiles as readiness evidence. Dates and thresholds here are 2019 to 2023 material; check the current calls. Sources: [BlueInvest](https://oceans-and-fisheries.ec.europa.eu/ocean/blue-economy/blueinvest_en), [coaching programme notice](https://blue-economy-observatory.ec.europa.eu/news/blueinvest-coaching-programme-high-potential-eu-start-ups-and-smes-2023-10-26_en)

## What we do differently

1. **Public records only, every level traceable.** VIRAL, KTH IRL and OIN need the company's own answers. The commercial scores use inputs and weights they do not publish. Our readiness levels come only from dated public sources (register, patents, contracts, funding decisions, EU projects, BlueInvest), each with a link, and the rule is printed beside the level.
2. **No financial statements needed, and no score of zero for silence.** Crunchbase gives no Growth Score without a financing event or a strong prediction. We show a hatched "no public evidence" instead, so absence is visible and never looks like a low score.
3. **Companies, not people.** Specter, Harmonic and Dealroom's People Signal score founders and track individuals. We emit signals about companies only.
4. **Earliness is measured, not claimed.** Vendors self-report lead time (Harmonic "6 to 12 months", Specter stamps months-ahead on each signal) and I found no independent check. We backtest first public signal date against the cohort entry date for the 19 Nordic Blue companies, blanks kept as blanks.
5. **One config swaps the sector.** OIN and the EIC and BlueInvest rules are blue-economy specific. Our sector, themes and readiness sources live in `config/thesis.yaml`; the health-tech thesis runs on the same code.
6. **Explainable next step.** The benchmarks stop at a score or a label. We end in one sentence from a decision table, with the "because" and a link.

### Where we are weaker (say it before a judge does)

- Thin coverage: for the cohort, public records are sparse (13 of 28 resolve in the register per STATUS.md), so many rows will show "no public evidence".
- No founder or team signal, which Dealroom Signal weights heavily and VIRAL and KTH IRL score directly. We have no commercial-traction input (no sales, renewals, customers beyond the website customer lists).
- Ocean impact rests on BlueInvest and CORDIS text only; OIN's KPIs need company-reported data we do not have.
- The patent source is blocked until an EPO OPS key is reachable from the build environment.

## Proposed for the chief (docs are chief-only)

- **Name collision:** `config/thesis.yaml` calls the investment scale "IRL 1-9". KTH's IRL is "Innovation Readiness Level", licensed. Label ours "investment readiness" on screen and in docs so no judge conflates them.
- ARCHITECTURE.md or EVAL.md: cite VIRAL (investment readiness, milestone levels) and KTH IRL (multi-dimension 1 to 9, TRL-inspired) as the closest ancestors of our readiness ladder, and OIN as the closest relative of the ocean impact line, without copying their level wording.
- Before quoting any figure above to judges, check it on the primary page. Verify first: Dealroom Signal input count (four vs three), EIC entry TRL (5 vs 6), KTH IRL dimension names, VIRAL levels 1 to 5, OIN's six impact areas, whether the OIN online tool is live.
