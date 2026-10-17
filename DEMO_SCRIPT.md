# Demo script

Gavel expo voting is pairwise: "better or worse than the last table?" The first ten seconds decide it.
Partners pick their own track winner against their own criterion, so lead with the partners' words for partner judges.

Two companies carry the demo, both real and both on the live site:
- **Viva Jets Oy**, business ID 2962040-6, Redstone Blue portfolio: <https://jx.hankintaviikko.fi/c/2962040-6>. Industry code
  30120 (building of pleasure and sporting boats) is on the sector list; share issues registered from 2022 to 2026 and Business
  Finland funding in 2019, 2021 and 2024 are on the page with their links. The memo reads ACCELERATOR ("fallback c2, impact implied
  by sector"). This is the one page with **Ask Aava** on a recorded voice.
- **Arctic Fry Oy**, business ID 3166759-6, Nordic Blue 2026 cohort: <https://jx.hankintaviikko.fi/c/3166759-6>. Its first live
  public record is from 2020 (first sales on 2020-10-05 in the VAT register), more than five years before the cohort, and the sector rule
  still did not count it, because it is registered as freshwater aquaculture (03220), a code the list does not hold. The memo reads
  WATCHLIST. **Arctic Fry has no recorded voice**: if Aava is tapped there, the browser's own voice reads it, so do not use Aava on this page.
- **Aava (voice briefing) is hidden on the public site.** The demo URL is `/c/2962040-6?demo=1` (the flag is remembered on that device;
  `?demo=0` turns it off). Only two things have a recorded voice: the Viva Jets page (40 clips) and the home feed reader (5 clips).
  Every other page falls back to the browser voice. Use Aava on Viva Jets only.

What the live pages look like now (17 Oct, build b7085d3), so the driver is never surprised:
- **Home `/` (editorial):** the headline "22 companies surfaced" with the caption "Count of companies whose first public record falls in
  the window", the status line "58 rows", three tabs (All startups 58, Top fits 31, New this quarter 22) and a list. A row shows the
  company's initials, name, registered line of business, a life-line of dated records and the memo's verdict. **A row has no source
  chip.** Click a row to open the company page; sources and "How sure" lines sit on the company page and in the folded section "All
  public records in the window, weak matches and the rules", which holds the 122-company feed list (30 strong, 92 weak) and the
  search box ("Find a startup"; press `/` to open it).
- **Company page:** the verdict and its reason at the top, key statistics, the four questions (01 to 04) with every rule printed, the
  memo, the life-line and every dated record with its link. The "Ask Aava" button sits bottom right when the demo flag is on.
- **Earliness test `/backtest`:** the four groups (0, 12, 6, 1), the lane chart, the wide intake table and the stitcher line.

---

## 90-second script (drive and narrate)

Start with `/` loaded, the demo flag already set (see "Before going live"), sound on.

| Time | Driver does | Narrator says |
|---|---|---|
| 0-8 s | Home `/` already loaded: the headline, the three tabs, the list. Do not click yet. | The opener sentence. "22 companies whose first public record falls in the last 90 days; these are the ones your pipeline has not seen yet." |
| 8-20 s | Click the **Viva Jets Oy** row (Accelerator). The company page opens. | "Every row is a company, its registered line of business, the life-line of dated public records and the fund memo's verdict. Viva Jets is a Redstone portfolio company: Accelerator, because thesis fit is High (its industry code is on the sector list) and the page prints the rule. Every level prints its rule and its link." |
| 20-45 s | Tap **Ask Aava**, then **What's missing?** Let it play in full (about 24 s, captions on). Say nothing while it speaks. | After it ends: "Aava reads only the records on this page. No AI model at runtime, no network call, and it says what is missing as plainly as what is there." |
| 45-62 s | Open <https://jx.hankintaviikko.fi/c/3166759-6> (type the URL, or go back to the home page, press `/`, type `Arctic Fry` and press Enter). **Do not tap Aava here.** | "Arctic Fry, a Nordic Blue company. The memo says Watchlist and names the missing evidence. Its first public trace is first sales in October 2020; every level prints its rule." |
| 62-85 s | `/backtest`: point at the headline, then at Taikoa's blank lane | "Applying our own rule to live records, we would have shown 0 of your 19 before January 2026, the programme start we declared as the reference. Declared research adds 12. Blanks stay blank. All 7 Finnish ones had records in our store before January; the rule counted none, because they are registered as software, retail, wholesale, consulting, R&D and freshwater aquaculture." |
| 85-90 s | Stay on `/backtest` | Takeaway line. |

The 62-85 s numbers come from the live `/backtest`. If the moment needs data we do not have,
change the moment, not the data. The wide intake line (below) is not in the 90-second version; say it when asked or in the longer versions.

---

## The wide intake line (say it exactly this strong, no stronger)

Live `/api/backtest` (17 Oct 2026, 09:36 UTC): "Entered wide intake before cohort entry: 4 of 19", all four among the 7 cohort companies
with a Finnish business ID. The four: Kilocode (intake date 2003-08-01, a VAT registration; rank 3 of 8; code family added after seeing
it), Sireness (2025-04-30 on a declared-research record; rank 1 of 104), Arctic Fry (2020-10-05, family added after seeing it; rank 3 of 16)
and Emission-Eye (2025-07-02, a public start-up notice; rank 132 of 1,176). Detail: EVAL.md, "Wide intake".

**Pitch line:** "If this had been running last year it would have had 4 of your 7 Finnish startups in its intake before you took them (Kilocode,
Sireness, Arctic Fry and Emission-Eye), but we claim less than that: Kilocode's intake date is a 2003 VAT registration, so it is not an
early find; Kilocode and Arctic Fry are in only because we added their code families after seeing them, so they are in-sample; Sireness
enters on a declared-research record rather than a public one; and Emission-Eye, on a public start-up notice, ranks 132 of 1,176
among the 2025 registrations in its code family."

Do not say "found early", "4 of 7 found" or the page's "median rank 3 of 60" (it mixes pools of 8, 16, 104 and 1,176 companies).
If a number on `/backtest` has moved since this was written, say the number on screen and keep the four qualifications.

---

## First ten seconds (the hook, all versions share it)

**0-4 s:** the opener, in the partners' words: "We find promising blue-economy startups in public records before they reach your
pipeline, and answer your four questions with a link under every fact." No team introduction, no market size. Never open with
"Hi, we are team X and we built...".

**4-10 s:** the demo moment starts immediately: the home list is on screen and the driver clicks the Viva Jets Oy row. The judge sees
a company page with a memo, a verdict and links before they hear any architecture.

---

## 60-second table version (Gavel expo, crowded hall)

| Time | Beat |
|---|---|
| 0-4 s | One-sentence opener (partners' words) |
| 4-10 s | First visible action on the live URL: click the Viva Jets Oy row on the home list |
| 10-50 s | Core flow: Viva Jets memo (Aava "What's missing?" if the hall is quiet enough), Arctic Fry and question 02 with its printed rule, then `/backtest`; one drives, one narrates; point at the page, never the terminal |
| 50-60 s | Takeaway line: one sentence the judge can repeat at the next table |

Opener (partners' words): "We find promising blue-economy startups as early as possible for accelerator and fund teams, so that you see the companies your pipeline has not seen yet, with the public record behind every line."
Takeaway line: "Ocean Opportunity Radar finds blue-economy startups from public records before they reach your pipeline, and answers your four questions with a link under every fact."
Closing number: "0 of your 19 cohort companies were visible to our rule in live public records before January 2026, our declared reference for the Nordic Blue start, and 12 of 19 with declared research; 1 had nothing public. Scan this and try it on your own company."

---

## 2-minute table version + 1 minute questions

| Time | Beat |
|---|---|
| 0:00-0:10 | One-sentence opener and first visible action |
| 0:10-1:15 | Core flow on the live URL, one drives one narrates: the home list, Viva Jets Oy (portfolio: code 30120 on the sector list, share issues and Business Finland years with links, Ask Aava "What's missing?"), then Arctic Fry Oy (cohort, the memo and the four questions; no Aava here) |
| 1:15-1:35 | One edge case shown honestly: Arctic Fry's first sales in 2020 is on the page but not counted by the backtest, because freshwater aquaculture is not on the code list; we added the fishing and aquaculture family to wide intake after seeing that, and the page says so. The pitch line above, if the judge asks about the wide intake |
| 1:35-1:50 | Why it works: one sector file drives everything, and an AI stitcher may only propose events that plain code then checks twice against the page; never the terminal or editor |
| 1:50-2:00 | Takeaway line |
| 2:00-3:00 | Questions: see hard questions below |

---

## 3-minute stage version (finals, if reached)

| Time | Beat |
|---|---|
| 0:00-0:20 | Hook and one-sentence opener |
| 0:20-0:40 | The problem in the partners' words: "find promising startups as early as possible" in "fragmented startup and ecosystem data"; no solution yet |
| 0:40-2:10 | Live demo on the deployed URL: home, Viva Jets Oy with Ask Aava, Arctic Fry Oy, `/backtest`; one honest miss (Arctic Fry's 2020 record not counted) and the wide intake table with the pitch line. Optional last beat, only if time is left: the sector swap `/?thesis=health_tech_turku` ("1 company surfaced"; 30 in the folded list, 1 strong and 29 weak; a swap demo, not an evaluated thesis) |
| 2:10-2:40 | Tech and real-world impact: 0 of 19 from live records, all 7 Finnish cohort companies already in our store, and the stitcher's 168 first-check events cut to 128 by the second check (EVAL.md) |
| 2:40-3:00 | Close and takeaway line |

Confirm stage length with organisers Sunday morning before the ceremony.

---

## Before going live (every time, in this order)

1. **Open every page once after any restart or deploy**, in the order of the demo, and wait for each to finish: `/`,
   `/c/2962040-6?demo=1`, `/c/3166759-6`, `/radar`, `/backtest` (and `/?thesis=health_tech_turku` only if you will show it). The
   default thesis is warmed when the app starts; any other thesis builds its home list on its first request. The first load of
   `/?thesis=baltic_blue` can take 30 seconds (independent dry run, 17 Oct; once warm it took 1.8 s when we measured at 09:58 UTC),
   which is the reason to keep it out of the live path.
2. **Present from a laptop**, not a phone: the demo path uses the `/` shortcut, the wide tables on `/backtest` and sound. The
   phone is for the judge's own trial after the QR scan.
3. **Keep the Baltic thesis out of the live path.** Do not choose it in the sector selector, do not type its URL, do not mention
   it unless asked ("a third thesis file widens the same code to the Baltic countries; it is not part of the demo").
4. **Sound on, and tested.** Laptop volume up, open `/c/2962040-6?demo=1`, tap Ask Aava, then What's missing?: you should hear
   the recorded voice (Lily), not a robotic browser voice. If you hear the browser voice on Viva Jets, a clip did not load: hard
   reload. Captions are always on, so a dead speaker costs nothing; keep going.
5. **Set the demo flag once** on the presenting laptop (`?demo=1`; it is remembered on that device). With the flag on, the Ask Aava
   button also appears on pages with no recording (Arctic Fry, `/radar`): do not tap it there.
6. **Check the home page reads as expected:** headline "22 companies surfaced" (the number moves as records arrive; say the number on
   screen), tabs 58 / 31 / 22, status line "LIVE". If the headline is 0 or the list is empty, the store did not load: tell the chief and switch to the fallback recording
   (Table checklist).

---

## Mid-demo restart line

If a judge arrives while the demo is running, stop immediately:
"Let me start from the top. We find promising blue-economy startups in public records before they reach your pipeline, and answer
your four questions with a link under every fact."
Jump straight to the first visible action. Never finish the flow you were in.

---

## Four hard questions with answer slots

**1. Who exactly is it for?**
Answer: the accelerator lead (A'Pelago screens many applications for a small cohort; the exact numbers are theirs to state, we do not claim them) and the VC associate (Redstone Blue, pre-seed and seed). Monday decision: which five do I call this week, and about what.

**2. What was built this weekend versus pre-existing?**
Answer: see DISCLOSURE.md. Short version: "All application code in this repository was written between 16 Oct 18:00 and 18 Oct 10:00 (Helsinki) with AI coding tools. We brought our own build tooling, checklists, and the public datasets listed below, and we used the third-party services listed below." No hedging.

**3. What breaks first at scale?**
Answer: request-time computation. Every page computes the feed rule from the whole store on each request; with wide intake and the Nordic registers the store grows many times over, so the feed and the backtest must be computed once per refresh instead. ARCHITECTURE.md names it. Name it before they do.

**4. Did the wide intake find your startups early?**
Answer: the pitch line above, word for word. If pressed on the other 3: "Finnish Sauna Shop, Sub Marine Store and Taikoa are registered as retail, wholesale and consulting, outside the intake's code families, and 12 of the 19 are outside the Finnish register. Your real entry dates would replace our January 2026 reference; that is the one ask in PILOT.md."

---

## Closing line (peak-end, JUDGE_LEVERS A6)

The last thing said is ONE real number (from EVAL.md) and the ask. The ask is "scan this and try it on your phone". It is never "vote for us".
Closing line: "0 of 19 from live records today, and all 7 Finnish ones were already in our store: the miss is the sector rule, and the radar shows you exactly where. Scan this and try it yourself."
Opener languages: English first. For Madeleine, a Finnish opener with its English gloss: "Löydämme lupaavat sinisen talouden startupit julkisista rekistereistä ennen kuin ne tulevat teidän tietoonne, ja jokaisen rivin takana on linkki lähteeseen." (We find promising blue-economy startups in public registers before you hear of them, and there is a link to the source behind every line.) Ask the judge's preference, do not assume.
Short version (45 s, crowded hall or late rotation): opener, one action, closing line.

---

## Table checklist

- Laptop on the live URL, phone on the live URL, QR card, one-page PILOT printed x10.
- One person at the table at all times during the expo window. Rotate every 30-40 minutes.
- Battery, charger, hotspot. Demo must work on 4G if venue wifi dies.
- 60-second screen recording of the demo path saved on the phone as the fallback.
- Typed fallback ready for any voice input in case the hall is too loud.
- Judge pass (hack-verify): QR card printed and standing next to the laptop, brightness 100 percent, laptop on power, handout on the table, narrator on the aisle side.
- Never say "it normally works": switch to the fallback recording instead.
- Run "Before going live" above at the start of every shift, not only once.
