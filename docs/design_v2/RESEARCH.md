# Research: how investor tools show a company list and one company (jx36, part 1)

Question: how do the tools investors and accelerators already use show (a) a list of companies and (b) one company in depth? And which of their habits help or hurt a fund partner aged 40 to 60?

Short answer: the industry default is a dense, configurable table plus a long tabbed profile full of scores. Partners at this age are better served by its quieter parts: a company header with 3 or 4 large facts, a dated timeline, a source on every number, plain-word badges, and "what changed since I last looked".

## Products

### 1. Dealroom (plus public ecosystem dashboards)
- **List screen:** You build a search by typing into a filter bar at the top, for example "HQ Location: Europe". Filters can be excluded and combined with AND/OR, and they default to OR. An advanced Filters panel covers industry, launch year and funding, and "Smart sector matching" adds semantic search. A search can be saved to alerts and named, and new matches arrive in a bell-icon Notification Center. Export lets you pick columns and download CSV or xlsx, and is Premium-only. The help article does not describe the results table's columns or sorting (**not verified**).
- **Company screen:** The public profile (dealroom.co/companies/dealroom-co) is a jump-menu page with these sections: Overview, Knowledge graph (news, research), Investors, Talent, Global footprint and Market sentiment. The header shows name, tagline, location, founding year and sector. Four KPI tiles show valuation, revenue, headcount and total equity funding, as ranges ("$25–50M", "<100"). Investors are grouped by the round they entered. Talent counts (founders, operators, "startup mafia") are gated. Footprint shows headcount share by country, and Market sentiment is an AI summary of X posts. Dealroom's founder guide describes "Dealroom Signal" as a "composite momentum score vs. sector average".
- **Ecosystem dashboards:** The Helsinki city page (dealroom.co/cities/helsinki) has a sidebar table of contents. It shows big stat tiles (972 funded startups), a funnel chart from Pre-Seed to Decacorn, a treemap of rounds over $15M, academia spinout counts and a peer-city ranking with a scatter chart. It lists no companies. Company-level data needs a demo or login. Business Helsinki's free Dealroom-powered "Startup Map" and similar city portals (Oulu, Turku, Espoo, Tampere) exist, but their list UI was **not verified** because the fetches were blocked.
- **Does well:** Ranges and big summary tiles give a fast sense of scale, and ecosystem pages tell a story with charts.
- **Bad for a 50-year-old partner:** Key numbers are greyed, gated or shown as ranges, and the filter-bar query syntax expects analyst habits.
- Links: https://dealroom.co/companies/dealroom-co/ · https://dealroom.co/knowledge/Navigate/navigate-founder-profile · https://knowledge.dealroom.co/knowledge/how-to-create-and-save-searches?hsLang=en · https://dealroom.co/cities/helsinki/ · https://dealroom.co/blog/from-supercell-to-slush-new-helsinki-database-catalogues-startup-ecosystem (search only)

### 2. PitchBook
- **List screen (search summary):** The search results page has a header with Share, a blue "Save / Save As New" button and "Quick Criteria" for editing a search without rerunning it. Results are split into tabs, and help pages define the columns per tab. A saved search is dynamic and a saved list is static, and you can set email alerts on either. "My Fields" adds custom columns for status, tags and notes. The full column list was **not verified**.
- **Company screen (search summary, Emory tutorial dated 2018–19):** The default Profile tab has a left "Contents" sidebar jumping to sections. Sections are General info and highlights (employees, hiring), Timeline, Financials, Consensus Estimates, Stock Performance (public companies only), Deal history and financing, Cap table, Valuations, Executives and Competitors. The Timeline plots employee count as a dotted line and capital raised per deal as vertical bars. A third-party review adds pre- and post-money valuations and AI-generated overviews. The current tab names were **not verified**.
- **Does well:** It is the deepest record of deals, valuations and cap tables. G2 summaries praise ease of use and support.
- **Bad for a 50-year-old partner:** It is very long, analyst-grade and expensive, and G2 reviewers flag gaps or stale data on niche companies, which is exactly where ocean startups sit.
- Links: https://pitchbook.com/help/search-results-page (403; search summary) · https://pitchbook.com/help/create-save-use-lists (search summary) · https://libraries.emory.edu/sites/default/files/migrated-documents/db-pages/pitchbook-viewing-company-profile.pdf (search summary) · https://g2.com/products/pitchbook (search summary)

### 3. Crunchbase Pro
- **List screen (search summary):** Advanced Search gives a configurable results table. You add columns through the 3-dot menu or a column-header arrow, sort any column and export to Excel (1k rows per export, 2k per month on Pro, and at most 1,000 results viewable). Saved searches can email you new matches. Lists ("My Follows" and custom lists) can be used as Include or Exclude filters, up to 5 lists. Heat and Growth score filters exist, but searches using them cannot be exported.
- **Company screen:** Crunchbase's redesign blog describes an "About" block (description, HQ, funding status, Crunchbase Rank) and "Highlights" (total funding, acquisitions). "Recent News & Activity" sits on the main page. Header tabs hold technology, estimated revenue range, people and "Signals & News". A Save button puts the company into a list. Help pages (search summary) put Heat Score (0–100, market interest) and Growth Score at the top of the profile. A "Predictions & Insights" tab sits in the left sidebar, where Pro users see a limited preview and Business users see probabilities.
- **Does well:** The first fold is clean (description, HQ, total funding, rank) and news sits next to the facts.
- **Bad for a 50-year-old partner:** The opaque AI scores (Heat, Growth, Rank, Predictions) aren't explained on the page, and paywalled teasers sit beside real data.
- Links: https://about.crunchbase.com/blog/new-crunchbase-profile-design · https://support.crunchbase.com/hc/en-us/articles/39902159873043/ (403; search summary) · https://support.crunchbase.com/hc/en-us/articles/115010583327 (search summary)

### 4. CB Insights
- **List screen:** Advanced Search lets you add Mosaic as a column. "Collections" are saved company sets that can be sorted by Mosaic to find high-growth or struggling firms. The general column set was **not verified**.
- **Company screen:** The public profile (cbinsights.com/company/dealroom/financials) has a header with logo, name, "Unclaimed" tag and website. Tabs are Overview & Products, Financials, People, and Alternatives & Competitors. Summary stats show Total Raised and Investors Count. The funding table has columns Date, Round, Amount, Investors, Valuation, Revenue and **Sources**. An investor table shows First/Last Funding, Rounds, Board Seats, Type and Location. A "Compare to competitors" section shows six cards, each with logo, description, founded year and HQ. Paid users also see Mosaic, a 0–1000 score built from four parts (Momentum, Money, Market, Management), plus Commercial Maturity and Exit Probability.
- **Does well:** Every funding row has a Sources column, and competitors sit on the profile itself.
- **Bad for a 50-year-old partner:** A 0–1000 composite score with sub-scores is hard to reason about or defend in an IC meeting, and many cells read "Subscribe to see more".
- Links: https://www.cbinsights.com/company/dealroom/financials · https://www.cbinsights.com/mosaic-health

### 5. Tracxn
- **List screen (search summary):** "Feeds" are curated lists of startups by sector, 1,800+ in total. Sector browsing goes Home > Sectors in a taxonomy tree of 3,000+ sectors. "Deal-sourcing boards" such as "Wide Scan" surface newly added companies within a mandate, with 15+ filters including sector, stage, geography, total funding and founded year. Capterra reviewers praise the filters. Columns were **not verified**.
- **Company screen (search summary):** The Okta listing says profiles cover basics, key metrics (total funding, employees), markets (industry, sector), key people and a competitive landscape where competitors are ranked by "Tracxn Score". The score method is undisclosed (**not verified**).
- **Does well:** The analyst-curated sector taxonomy is a good way to browse a thematic space like "ocean".
- **Bad for a 50-year-old partner:** The taxonomy is deep and tree-like, the score is unexplained, and reviewers call it pricey with weak sector reports.
- Links: https://tracxn.com (403) · https://www.okta.com/en-ca/integrations/tracxn/ (search summary) · https://www.capterra.com.sg/software/204090/tracxn (search summary) · https://www.trustradius.com/products/tracxn/reviews (search summary)

### 6. Specter (tryspecter.com)
- **List screen:** The "Companies / Database" table shows "55M+ companies" with Export, Clear Search and Save Search buttons and "Sort by Rank". Filters are removable chips ("Growth Stage is Pre-seed/Seed") added with "+ Add Filter", using operators such as is, ≥, AND and OR. Columns are Company (logo, name, tagline), Growth Stage, HQ Location, Employee Count, 3m Web Visits and 3m Total Funding. Each metric carries an inline growth % (for example, 9 employees, +80%). The left sidebar holds Companies, People, Investors, Transactions, Talent Signals, Interest Signals, Searches and Lists. Saved searches show a count of new results since the last run, and lists show owner and private or team visibility.
- **Company screen:** The header lists stage, founded, HQ, headcount, total raised and business model. Sections cover team breakdown by function with 90-day hires, and time-series charts for headcount, web visits, app downloads and social followers with year-on-year change. The page also has modelled revenue and valuation (flagged when disclosed), funding and investors, news with a significance score, people, and LinkedIn connection paths. "Company Highlights" adds badges such as Headcount Surge, Web Traffic Surge, Top Tier Investors and No Recent Funding.
- **Does well:** Plain-language highlight badges and "N new since last run" counts make changes visible.
- **Bad for a 50-year-old partner:** It is tuned for digital SaaS signals (web visits, app downloads) that say little about hardware or ocean ventures, and the screens are dense with micro-percentages.
- Links: https://tryspecter.com · https://tryspecter.com/company-signals · https://insights.tryspecter.com/new-feature-company-highlights/

### 7. Harmonic (harmonic.ai)
- **List screen:** Company, people and investor searches use "granular filters", and Scout takes natural-language queries. Searches can be saved, and Scouts rerun weekly or monthly with alerts. Lists live in a "Workspace". The help centre covers "Customize list view", which uses an Edit Columns button with drag-and-drop ordering and an "Apply To" option that pushes one column order to all searches and lists. It also has a configurable relevance scoring model (search summary) and CSV import and export.
- **Company screen:** The API example fields are name, description, headcount, funding total, rounds (type, amount, investors, lead flag), highlights, tags, domain, web traffic, 30-day web traffic change and 90-day engineering headcount change. The visual layout was **not verified**. Network Mapping (who on your team knows the company) is a documented feature.
- **Does well:** One column layout everywhere means the table looks the same each time, and network mapping finds a warm intro.
- **Bad for a 50-year-old partner:** It assumes heavy self-serve searching and tuning, and its momentum metrics are percentage deltas without context.
- Links: https://harmonic.ai · https://support.harmonic.ai/en/collections/3238663-getting-started · https://support.harmonic.ai/en/articles/8827822-customize-list-view (search summary)

### 8. Affinity (affinity.co)
- **List screen:** Lists are typed as Organization, People or Opportunity lists. Columns are spreadsheet-style attributes, for example Status, Owner, Last contact, Location, Firm Type, Sector Focus and Preferred Deal Stage, and custom columns are allowed. You filter by column values and save a filtered view with "Duplicate this view". **Board view** shows a kanban by pipeline stage, and the help guide says teams often use it in weekly meetings. Reminders fire after N days without contact.
- **Company screen:** The marketing page shows a Connections panel with team relationship strength (a 0–100 tooltip score built from real interactions). It also shows an activity timeline of meetings, emails and reminders, a monthly feed, AI notetaker summaries and enriched fields from 40+ sources (PitchBook, Preqin, Grata, with Crunchbase and Dealroom logos). The exact section order was **not verified**.
- **Does well:** "Who do we know here, and when did we last talk" is the question partners actually ask, and kanban maps onto the Monday meeting.
- **Bad for a 50-year-old partner:** It is CRM-heavy and only as good as the data entry, and the relationship score is opaque.
- Links: https://www.affinity.co/product · https://support.affinity.co/learn/industry-guides/best-practices-affinity-for-venture-capital

### 9. Nordic 9 (nordic9.com)
- **List screen:** The homepage shows "graded deal cards", each with a **letter grade (A+ to C)**, company name, one-line description, amount and round type, date, country, sector tags, investors and a link to the source news article. Data menus are "All investment deals" and "M&A and Secondary". Tools such as Startup radar, Stealth founders and New funds have country, stage, year and fund-size dropdowns. Watchlists and alerts exist (Dealroom listing, search summary). The deal-table columns were **not verified**.
- **Company screen:** Profiles exist under /companies/, but their contents were **not verified**.
- **Does well:** A letter grade plus a link to the source article on each card is quick to scan and easy to trust.
- **Bad for a 50-year-old partner:** The grading method isn't explained on the cards, and coverage is Nordic and deal-centric rather than company-centric.
- Links: https://nordic9.com · https://app.dealroom.co/companies/nordic9 (403; search summary)

### 10. Vainu (vainu.com)
- **List screen:** "Reach" lets you describe a target, then filter on 550+ fields (revenue band, industry, software used, e.g. "Runs NetSuite"). It shows result counts such as "214 companies, 1,940 contacts". Lists update themselves. Columns and sorting were **not verified**.
- **Company screen:** Identity fields are name, business ID, city, head office and parent. Financials (revenue trend, balance sheet, EBIT and EBITDA) come from official filings. Other data covers vehicles, real estate, software, hiring keywords and contacts. "Discover" signals answer "why and when to reach out" and **cite the exact source line**, for example an annual-report sentence with its page number. Data Sync pushes to CRM and shows change events.
- **Does well:** Signals carry a verbatim citation from registry and filing data, which is the strongest source story of any tool here.
- **Bad for a 50-year-old partner:** It is built for sales prospecting, not venture, so it has no funding rounds or cap tables in focus. G2 rates its data availability and accuracy lower than its ease of use.
- Links: https://www.vainu.com · https://www.g2.com/compare/growbots-vs-vainu (search summary)

### 11. 1000 Ocean Startups / Ocean Impact Navigator
- **List screen:** The homepage cites 850+ solutions across "6 Impact Areas", with "View Start-ups" and "Browse catalog items" links. The link goes to a **login**, so the public card and filter layout was **not verified**.
- **Company screen:** Not verified. The Ocean Impact Navigator (launched at the UN Ocean Conference 2022, with SYSTEMIQ) is an open-source **impact KPI framework**, a harmonised set of ocean-health metrics per impact area, rather than a database UI. An assessor certification scheme was announced in 2026 (event listing, unverified).
- **Does well:** Shared ocean-impact vocabulary (impact areas, standard KPIs) that blue-economy funds already reference.
- **Bad for a 50-year-old partner:** The catalogue is behind a login, and impact KPIs aren't connected to funding or traction data.
- Links: https://www.1000oceanstartups.org · https://www3.weforum.org/docs/WEF_The_Ocean_Impact_Navigator_2023.pdf (search summary) · https://tnfd.global/knowledge-bank/the-ocean-impact-navigator/ (search summary)

### 12. Katapult Ocean (katapult.vc/ocean)
- **List screen:** The fetched pages (katapult.vc/ocean, /ocean/portfolio) show only aggregate statistics: 90 ocean investments since 2018, 195 across Katapult, and "200+" companies. Ecosystem cards each carry a number label ("01 / 04"), category, title, blurb and a "Visit →" link. No individual company grid appeared in the fetched content, which may be rendered by JavaScript (**not verified**).
- **Company screen:** Not observed. Company news appears as blog posts.
- **Does well:** Big-number impact stats and a calm, editorial card layout.
- **Bad for a 50-year-old partner:** There are no filters, metrics or comparable fields, so it is marketing rather than a tool.
- Links: https://katapult.vc/ocean/ · https://katapult.vc/ocean/portfolio

### 13. EU BlueInvest (platform and community)
- **List screen:** The "Project pipeline" is a curated, vetted showcase of 560+ investable blue-economy products and technologies (2025 UN progress report). The community has about 1,800 members, including 300 investors, and has run more than 4,300 matchmaking meetings. It is hosted on blueinvest-community.converve.io, a login-only event and matchmaking platform with role-based registration (investor, company, stakeholder). The BlueInvest team checks each profile within 24 hours. The list UI was **not verified**.
- **Company screen (inferred from registration):** Registration asks for organisation data, the participating person, and "value proposition and objectives". The profile is therefore self-declared pitch content geared toward booking meetings. The rendered layout was **not verified**.
- **Does well:** A human-vetted, blue-only pipeline linked to meeting booking.
- **Bad for a 50-year-old partner:** Profiles are self-reported with no traction or funding verification, and the platform feels like an event-matchmaking tool.
- Links: https://blueinvest-community.converve.io/registration.html (search summary) · https://sdgs.un.org/partnership-progress/developing-bluelnvest-platform-tue-05062025-1734 (search summary) · https://cinea.ec.europa.eu/featured-projects/blueinvest-platform-accelerating-european-blue-economy_en (search summary)

### 14. Sifted (sifted.eu)
- **List screen:** sifted.eu returned 403, and no /companies pages were indexed. Sifted offers a deals tracker, investor rankings, market maps, the "Sifted 30" ranking and Sifted Pro "100+ Briefings" (search summary). The company-profile UI was **not verified**, and I could not confirm that Sifted has standalone company profiles at all.
- **Company screen:** Not verified. Company coverage appears as journalism, meaning articles and rankings.
- **Does well:** Editorial narrative ("why this matters") that partners already read.
- **Bad for a 50-year-old partner:** There is no structured, comparable company record (unverified).
- Links: https://sifted.eu/companies (403) · search results only

---

## Patterns: the 10 conventions these tools share, rated for a 40 to 60 partner

| # | Convention | Seen in | For a 40 to 60 partner |
|---|---|---|---|
| 1 | Dense, configurable results table (8+ columns, sortable, sticky header) | Specter, Crunchbase, Harmonic, PitchBook, Affinity | **Hurts as the default.** Many narrow columns of small numbers are slow to read. Keep it as an analyst view behind a 4 or 5 field row |
| 2 | Filter rail or filter bar with AND/OR | Dealroom, Specter, Crunchbase | **Hurts as the way in** (building queries is analyst work). Helps as one-click presets such as a country |
| 3 | Saved searches that alert on new matches ("N new since last run") | Specter, Dealroom, PitchBook, Crunchbase | **Helps.** "What changed since I last looked" is the partner's first question |
| 4 | Watchlists and a kanban board by pipeline stage | Affinity, Crunchbase, PitchBook, Nordic 9 | **Helps.** It mirrors the Monday pipeline meeting |
| 5 | Company header: name, place, founded, sector or stage, plus 3 to 4 large figures | Dealroom, Crunchbase, CB Insights, Specter | **Helps.** It answers what, where and how big above the fold |
| 6 | Profile split into tabs | CB Insights, Crunchbase, PitchBook | **Mostly hurts.** Partners don't open tabs. One scrolling page with section headings works better |
| 7 | Composite momentum score (Mosaic 0-1000, Heat, Tracxn Score, Nordic 9 A+ to C) | CB Insights, Crunchbase, Tracxn, Dealroom, Nordic 9 | **Hurts unexplained**, because a partner can't defend it to an IC. Helps only as a plain verdict with its 2 or 3 reasons one click away |
| 8 | Source beside each funding row, or a verbatim quote from the source | CB Insights (Sources column), Vainu (quoted annual-report line), Nordic 9 (news link) | **Helps strongly.** Experienced investors trust what they can check. Pair it with an "as of" date |
| 9 | Dated timeline of events, with one or two charts at most | PitchBook, Specter, Affinity | **Helps.** A dated story matches how partners reason. Six sparklines do not |
| 10 | Plain-word badges and an honest "unknown" (versus paywall ranges like "$XXM") | Specter ("Headcount Surge", "No Recent Funding") versus Dealroom and CB Insights placeholders | **Words help, placeholders hurt.** Show "not in public records" plainly |

Also seen, useful later: competitors on the profile (CB Insights, Tracxn), and a "who on our team knows them" panel (Affinity, Harmonic).

## What this means for Ocean Opportunity Radar
- **No tool covers ocean impact.** The blue-economy vocabulary lives in the Ocean Impact Navigator's impact areas and KPIs and in BlueInvest's vetted pipeline. The usual traction signals (web visits, app downloads) fit ocean hardware, aquaculture and biotech poorly. Our public-register, grant, EU-project and contract signals fill exactly that gap.
- **Do take** conventions 3, 4, 5, 8, 9 and 10: a simple list, a 3-to-4-fact header, sources everywhere, a dated record and honest gaps.
- **Do not take** conventions 1, 2, 6 and 7 as defaults: dense tables, query filters, tabs and opaque scores.
- Direction A (a_home.html, a_company.html) is built from the conventions as the industry ships them. Direction B (b_home.html, b_company.html) is Dayo's brief. It happens to follow the "helps" column above. See COMPARE.md.

## Method and limits
Desk research run on 17 Oct 2026 with web search and page fetches. Every product is behind a login, so no logged-in screen was seen directly. Descriptions come from vendor pages, help centres, public profiles and reviews. pitchbook.com, support.crunchbase.com, tracxn.com, app.dealroom.co, datacommons.dealroom.co and sifted.eu returned HTTP 403 from this environment. ecosystem.startupfinland.com did not resolve. Those entries rely on search-result summaries and are marked "(search summary)". Anything not confirmed is marked "not verified".
