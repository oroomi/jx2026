# Slides (8 at most, for the 3-minute pitch)

Slide 1 is the live app, not a title card. Slides 2 and 3 are the live app too; their screenshots are the fallback only if the network fails. Slides 4 to 8 are static and show while Dayo speaks the last minute of PITCH_3MIN.md. Numbers written `<N1>`, `<N2>`, `<N3>` come from the live pages on Sunday (sources in PITCH_3MIN.md).

## Visual notes (all slides, from DESIGN.md "Receipts")

- Dark default: background #0B0F14, surface #121820, text #E8EDF2, muted #9AA7B4, hairline rules #232C37. One accent only, teal #4FD1B5, used for chips and the one number on a slide.
- Titles in Newsreader. Body, chips and figures in IBM Plex Sans with tabular numerals. Sentence case, left aligned, no centred paragraphs.
- Every number on a slide carries an evidence chip under it: source name, date fetched, and the page it came from.
- Missing data is the hatched chip "not in public records" (diagonal hatch in the muted colour), never a lighter version of a real value.
- Not allowed: gradients, emoji, animated counters, exclamation marks, placeholder avatars, four identical cards in a row, any partner logo or letterhead.

## 1. New this quarter

LIVE: https://jx.hankintaviikko.fi start page, full screen, heading "New this quarter" and the first rows with their "Why" lines and source chips.

Speaker note: say the problem sentence and the "what we built" sentence over the live page; do not click yet.

## 2. Your four questions, one of your companies

LIVE: the company page of the name a judge gives (fallback Emission-Eye, /c/3543918-7).
Sections 01 to 04 in the partner's order, a chip under every fact.
Fallback screenshot: the same page captured Sunday morning, not an older build.

Speaker note: tap one chip so the trade register record opens, point at the life-line, then walk 01, 02, 03, 04 in order.

## 3. Your cohort was invisible to public registers until after you picked them

LIVE: https://jx.hankintaviikko.fi/backtest, the lane chart of the 19 Nordic Blue companies, most lanes hatched.
On its own feed rule the radar shows `<N1>` of 19 before January 2026; `<N2>` have no public signal.
This radar shows the companies that are visible now, each with a dated public record.

Speaker note: point at one hatched lane; if `<N1>` is above 0 on Sunday, retitle "`<N1>` of 19 were visible before you picked them".

## 4. Every line is a public record

Trade register, public contracts, Business Finland funding, EU projects.
Each line: what was found, the date the source states, a link that opens the record.
Visual: one real feed row with its chip, enlarged; no diagram.

Speaker note: "dated, linkable, the same for anyone who opens it".

## 5. Earliness measured on your cohort, not claimed

Vendors state their own lead time; we found no independent check (research/BENCHMARKS.md).
We tested ourselves on your 19 with the feed's own rule and printed the result, blanks included.
Visual: a crop of the /backtest chart around the reference line, with its rule line underneath.

Speaker note: "I am a maritime engineer; I trust a measurement more than a claim."

## 6. What it does not do

No score we cannot source: five of the ten Investment Potential dimensions read "not in public records".
LinkedIn, Dealroom, Crunchbase, PitchBook, Tracxn: connector slot, not connected.
Companies only, never private people.

Speaker note: name the four frameworks once more: KTH BRL, Aalto TRL, Ocean Impact Navigator, Investment Potential dimensions.

## 7. Same code, another sector or region

Everything sector- or region-specific lives in one file (config/thesis*.yaml).
The header switch loads the Baltic Sea region (8 countries) or health technology in Turku on the same code.
Register depth so far: Finland and Estonia; the other six countries read EU sources only.

Speaker note: only if time allows; otherwise leave it on screen during the ask.

## 8. Run it on your pipeline for a month

Note the date each company reaches you; we show what the public record held on that day.
https://jx.hankintaviikko.fi, with a QR code to the same address.

Speaker note: end on "Right now `<N3>` companies are visible, each with a dated record. Scan the code and try your own company."
