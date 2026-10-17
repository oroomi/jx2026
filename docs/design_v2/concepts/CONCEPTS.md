# Concept boards

Two static boards, for diversity against the three skins being built on the real
templates. Each board shows the home page and the company page at 1440 and 390,
side by side. Open either file straight from disk; there is no build step and
nothing is fetched at runtime.

| File | Concept |
|---|---|
| `lifeline.html` | Concept 1, Lifeline |
| `dossier.html` | Concept 2, Dossier |
| `concepts.css` | shared board chrome and the vendored font faces |
| `concepts-data.js` | the real data both boards read |

## Concept 1, Lifeline

The dated public record is the identity: every company carries one horizontal
lifeline, first record to today, and the same mark does the work on the list and
on the company page, where it runs full width with year ticks and a cohort-entry
marker for cohort companies.

Borrows the calm chart treatment from **Apple Stocks** and **Robinhood** (a thin
line, one emphasised point, no gridlines shouting), and the frame, type scale and
quiet density from **Linear**.

One accent, a warm white, and a seven-step tonal scale for the verdict. The live
decision table has five rules today; the two outer steps carry the empty states so
nothing has to be invented to fill the scale.

## Concept 2, Dossier

The product as a printed investment dossier on screen: masthead, ruled lines, a
numbered table of contents (01 verdict, 02 evidence, 03 who to meet, 04 timeline),
and every figure set as a big number with one sentence beside it and its source
beneath.

Borrows the masthead and the numbered spine from **Bloomberg Businessweek**, the
source line under every figure from the **FT Visual Vocabulary**, and the
book-like measure and restraint from **Stripe Press**.

Dark warm paper with a single amber accent. The signature is the verdict set as
the page's headline sentence, in quotation marks, with its rule and evidence link
directly under it.

## Where the data comes from

Read live from `https://jx.hankintaviikko.fi/api` on 2026-10-17:
`/api/company/2962040-6` (Viva Jets Oy, portfolio, 26 records),
`/api/company/3166759-6` (Arctic Fry Oy, cohort, 12 records), `/api/feed`
(122 companies in the 90 days to 2026-10-17), and one `/api/company` call per
feed row so that each lifeline on the home list is that company's real record set.

Nothing on either board is invented. Where a value is missing it is drawn as the
hatched empty state, and those are real: Arctic Fry genuinely has no technology,
investment or ocean-impact level in the public record. Both companies genuinely
sit on rule 5, "watch". Source URLs are deduplicated into the `urls` table in
`concepts-data.js`; every link on both boards resolves to a real public record.

Fonts are the woff2 files already vendored at `radar/static/fonts`, referenced by
relative path from `concepts.css`. Nothing loads from a CDN, and there is no 3D,
no particles and no partner logo anywhere.

## Shots

`shots/` is empty. The cloud session that built these boards cannot commit binary
files, so the two PNGs were rendered and read during the self-critique rounds but
could not be pushed. Re-shoot with playwright at 1900 wide, full page, or ask Dayo
for the copies he already has.
