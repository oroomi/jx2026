# Direction mockups (jx33)

Three directions for the hero visual, as static mockups. Dayo picks one, and only then do
we build it. The sonar build was stopped before any three.js or app code was written, so
nothing under `radar/` is touched by this branch.

Open any file straight from disk in a browser. Each one is self-contained: no build step,
no network request, no vendored library. Rendered at 1440x900 and 390x844, dark and light.

| File | Direction |
|---|---|
| `map.html` | Where the cohort sits, and where the radar can see |
| `lifelines.html` | Every public signal of the 19, against cohort entry |
| `sonar.html` | The original radar idea, drawn flat, for comparison |

## 1. Map

**References**

1. MarineTraffic live vessel map, <https://www.marinetraffic.com/>. Every dot is a real
   vessel and clicking one opens its record. We take the habit that nothing is on the map
   that is not a real thing you can open.
2. Datawrapper symbol maps, <https://www.datawrapper.de/maps/>. A plain legend and a source
   line under the figure. We take the legend sentence and the source line.

**What a fund partner learns in 5 seconds.** Our coverage is a Finland map, not a Baltic
one: 7 of the 19 have a Finnish business ID and the other 12 cannot be joined to any
register we hold.

## 2. Life-lines

**References**

1. FT Visual Vocabulary, the change-over-time family,
   <https://ft-interactive.github.io/visual-vocabulary/>. The one-row-per-subject dated
   mark chart. We take the row rhythm and the single reference line.
2. Our World in Data, <https://ourworldindata.org/>. A source under every figure. Each mark
   here has a filing behind it, so the chart has to carry that.

**What a fund partner learns in 5 seconds.** Almost every row is empty, so on the records
we hold the radar would not have seen this cohort coming.

## 3. Sonar

**References**

1. Flightradar24, <https://www.flightradar24.com/>. A radar people already know how to
   read, where distance and position mean something literal.
2. Florence Nightingale's polar area diagram,
   <https://en.wikipedia.org/wiki/Pie_chart#Polar_area_diagram>. The canonical case for
   encoding a quantity as distance from a centre, and the argument for a printed scale.

**What a fund partner learns in 5 seconds.** The ring outside the centre is empty, so
nothing in this cohort was found early.

## Where the numbers come from

- Companies and signals: `data/snapshot/radar_redstone_apelago_blue.sqlite`, group
  `cohort`. 19 companies, 10 stored signals between them, 8 companies holding at least one.
- Registered towns: `ytj_address` and `hq_note` in
  `data/declared/cohort_portfolio_companies.csv`. 16 of 19 have a town. Edilm, MOR and
  TuniSea do not, and are named rather than placed.
- Reference date 2026-01-01 and the month rule: `radar/earliness.py`. It is the programme
  start month declared by the team, not a published entry date, and no per-company entry
  dates exist.
- Group per company: `EARLINESS_AUDIT.md` section 1, with the four counts from section 3.
  Live store as it stands: 0 earlier, 0 declared, 1 later, 18 none.
- Kelluu Oy's who-comes-next rows: the customer, CORDIS, investor and programme evidence
  already held in the cohort file, `config/thesis_baltic_blue.yaml` and
  `data/declared/programmes_grants.csv`. Every row carries its source link.

## What these mockups do not do

- **No PNGs.** This session cannot commit binary files, so the mockups are HTML and the
  screenshots are taken on the VPS.
- **The thesis fit test is not re-implemented.** `store.explain` decides whether a signal is
  counted, and these files do not reproduce it. Group membership is read from the audit
  rather than recomputed, so the figures match `/backtest` instead of guessing at it.
- **Two different counts appear, and both are right.** 11 companies have no stored record
  at all; 18 have no record the rule counts. Each view says which one it is showing.
- **The snapshot holds fewer signal types than the live store.** It carries no
  `board_change` rows, so a company's mark count here can be lower than on its live page.
- **No coastline on the map.** None is held in the data, so the plane is a plain latitude
  and longitude grid under a one-point perspective rather than an invented shoreline.
- **Fonts are not vendored.** DESIGN.md calls for self-hosted Newsreader and IBM Plex Sans;
  woff2 files are binary, so these mockups fall back to a serif and a sans stack.
