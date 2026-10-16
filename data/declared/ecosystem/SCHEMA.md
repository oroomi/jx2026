# Finnish Blue Economy dataset — record schema and capability taxonomy

Scope: entities registered or headquartered in Finland (incl. Åland), plus non-Finnish
investors/funders that demonstrably invest in Finnish blue-economy companies.
"Blue economy" = everything that earns from or protects seas, lakes and water:
maritime/shipping/shipbuilding, ports and logistics, aquaculture and fisheries,
marine biotech and blue bioeconomy, water tech and pollution control, ocean data and
sensing, offshore/marine renewable energy, Arctic/ice tech, coastal tourism and boating,
marine safety/defence tech.

## One JSON record per entity (write an array to raw/<slice>.json)

```json
{
  "name": "Awake.AI Oy",
  "entity_type": "startup | scaleup | sme | corporate | investor_vc | investor_angel | investor_corporate | public_funder | accelerator_incubator | research_org | cluster_network | shipowner_operator | port",
  "business_id": "FI Y-tunnus if found, else null",
  "city": "Turku",
  "region": "Varsinais-Suomi",
  "founded": 2018,
  "website": "https://...",
  "linkedin_url": "https://www.linkedin.com/company/...",
  "github_url": "https://github.com/... or null",
  "other_urls": ["crunchbase/dealroom/press..."],
  "size_employees": "1-10 | 11-50 | 51-200 | 201-500 | 501-1000 | 1000+",
  "size_employees_exact": 35,
  "revenue_eur": "latest known turnover, number or null",
  "revenue_year": 2025,
  "funding_total_eur": 12000000,
  "last_round": {"type": "seed | series_a | grant | ...", "amount_eur": 0, "date": "YYYY-MM", "investors": ["..."]},
  "stage": "idea | pre_seed | seed | series_a | series_b_plus | growth | established | public",
  "segments": ["maritime_software", "shipbuilding", "aquaculture", "...free text ok"],
  "capabilities": ["C1", "C4"],
  "description": "2-4 sentences: what they do, for whom, what is distinctive.",
  "working_on_now": "latest product/project/news 2025-2026 with date",
  "keywords": ["port call", "AIS", "ETA prediction", "digital twin"],
  "needs": {
    "funding": "e.g. raising Series A 2026, or null",
    "talent": ["roles they are hiring or publicly short of"],
    "pilots_customers": "what customers/pilots they seek",
    "partners": "tech/distribution partners they seek",
    "other": null
  },
  "recruitment_signals": [{"role": "ML engineer", "url": "...", "date": "2026-09", "language_req": "EN|FI"}],
  "key_people": [{"name": "...", "role": "CEO", "linkedin": "..."}],
  "investor_profile": {
    "thesis": "only for investors: what they fund",
    "stages": ["pre_seed", "seed"],
    "ticket_eur": "200k-2M",
    "geography": "Finland | Nordics | Baltic | EU | global",
    "blue_portfolio": ["company names"],
    "fund_size_eur": 25000000,
    "how_to_apply": "url / process / contact"
  },
  "sources": ["every URL used"],
  "confidence": "high | medium | low",
  "data_gaps": "what could not be found, what is ambiguous or contradictory",
  "last_verified": "2026-10-16"
}
```

Use `null` for unknowns. NEVER invent numbers; a null with a note in data_gaps is
worth more than a guess. Mark contradictions between sources in data_gaps.

## Capability taxonomy (tag every company with 1-3 codes; investors with the codes they fund)

| Code | Capability | Examples |
|---|---|---|
| C1 | Maritime autonomy, navigation & situational awareness software | autonomous/remote vessels, bridge AI, AIS analytics, remote pilotage |
| C2 | Vessel design, shipbuilding & propulsion engineering | naval architecture, yards, propulsion, hull, Arctic/ice design |
| C3 | Maritime decarbonisation & energy | alternative fuels, electrification, batteries, efficiency, wind-assist, emissions compliance |
| C4 | Ocean & water sensing, data and monitoring | sensors, buoys, drones, satellites, digital twins, hydrography, weather/ice |
| C5 | Aquaculture, fisheries & blue bioeconomy | fish farming, RAS, feed, algae, marine biotech, novel proteins, side-streams |
| C6 | Water treatment, circularity & pollution control | nutrient removal, microplastics, ballast/wastewater, oil spill, Baltic eutrophication |
| C7 | Port, logistics & supply-chain digitalisation | port call optimisation, cargo handling, terminal automation, freight visibility |
| C8 | Offshore & marine renewable energy | offshore wind (fixed/floating), wave, ocean-to-grid, marine construction for energy |
| C9 | Marine safety, security, Arctic & defence tech | icebreaking, search & rescue, surveillance, underwater defence, cyber for ships |
| C10 | Coastal tourism, boating & marine services | boat building, marinas, cruise services, archipelago logistics, leisure |

## Segment keys for investors' "needs" (what they look for)
stage fit, ticket size, geography, sector thesis, TRL / product maturity, team
(technical + commercial), traction (revenue, pilots, LOIs), IP/defensibility,
impact/ESG metrics, co-investor requirement, EU-grant leverage.
