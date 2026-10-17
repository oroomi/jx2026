# Demo script

Gavel expo voting is pairwise: "better or worse than the last table?" The first ten seconds decide it.
Partners pick their own track winner against their own criterion, so lead with the partners' words for partner judges.
Every number below was read from the live site or its JSON API on 17 Oct 2026 (15:13 to 15:40 UTC, footer build 1b6c857, after the 15:04 UTC restart); each is listed with its source in [docs/NUMBERS.md](docs/NUMBERS.md). Say the number on screen if one has moved.

Two companies carry the demo, both real and both on the live site:
- **Viva Jets Oy**, business ID 2962040-6, Redstone Blue portfolio: <https://jx.hankintaviikko.fi/c/2962040-6>. Industry code 30120 (building of pleasure and sporting boats) is on the sector list. The memo reads ACCELERATOR, "ocean impact medium on record" (the decision table's High-fit rule). The Ocean Impact Assessment reads level 5 of 9, Medium, confidence high.
- **Arctic Fry Oy**, business ID 3166759-6, Nordic Blue 2026 cohort: <https://jx.hankintaviikko.fi/c/3166759-6>. Registered as freshwater aquaculture (03220), a code that was added to the sector list on 17 Oct (D47) after the earliness audit had named it as the reason the company was missed. The memo now reads ACCELERATOR on the same rule (ocean impact medium on record, level 5 of 9): business readiness is 2 of 9, technology and investment readiness have no public record, and the page says so. It is also the one company the earliness test now finds from live records (first sales on 2020-10-05 in the VAT register), and that hit is in-sample.
- **Aava is hidden on the public site.** The demo URL carries `?demo=1` (the flag is remembered on that device; `?demo=0` turns it off). **Which answers play the recorded voice (Rachel) today:** a clip plays only while its text matches the page, and the merges that went live at 15:04 UTC changed the wording, so only 3 of the 16 committed clips match: Viva Jets questions 1, 4 and 5. Viva Jets questions 2, 3 and 6, all six for Arctic Fry and the home "what is new" answer are read by the browser's own voice until the clips are rendered again. Captions are always on, so either voice works on a quiet table, and the script below says which is which.
- **Aava's reasoning mode is switched off.** `GET /api/aava/status` answers `available: false` and the file `data/AAVA_LLM_OFF` is present. Everything below is the deterministic Aava and bar. If the chief has switched it on before the ZIP, the bar and the "Ask a follow-up" box also answer through a model (see "Hard questions", 7).

What the live pages look like now, so the driver is never surprised:
- **Home `/`:** the hero is the **Ask Aava bar**: the title, one line saying every answer is built from the public records on file, the input with a send button, five example questions as chips ("What is new on the radar?", "Tell me about Viva Jets", "Who should A'Pelago meet?", "Show accelerator candidates in Finland", "Aquaculture startups with a TRL above 4"), and one muted line, "23 companies first seen in the last 90 days, 59 on the list. Press Ctrl K to ask." The header tabs are in the **Menu** (top right) and in the footer. Under the bar three tabs (All startups 59, **Top matching startups for A'Pelago** 28, New this quarter 23), the country links, and on desktop the filter rail on the left: **Sector** first (the three sectors, and under the blue one the sub-sectors: Shipbuilding and boats 14, Water and pollution 10, Ship repair and maritime services 8, Aquaculture and fisheries 4, Ocean data and monitoring 4, Coastal tourism and boating 3, Ports and marine construction 2, Maritime software and tech 1, Shipping and logistics 1, Not yet classified 17), then "What the judges score" (Verdict, Ocean impact, Technology readiness, Business readiness, Investment readiness, Thesis fit) and "Narrow down" (Country, Impact category, Registered, Source records, Programme deadline, Declared company). Each row has the company name, its line of business, its ocean impact area, a life-line and the **criteria box** (Impact, TRL, BRL, IRL, Fit, Verdict). On a phone the rail is a bottom sheet. Filters work in place: the list changes, the address bar changes, the page does not reload.
- **Company page:** the verdict and its reason at the top, the **Ocean Impact Assessment**, key statistics, an AI summary of the linked records, Who to meet, Next steps (matchmaking), the news life-line, the four questions (01 to 04) with every rule printed. The "Ask Aava" button sits bottom right when the demo flag is on; it opens six questions.
- **Match `/match`:** pick a counterpart (191) or a startup; reason chips and one sentence per reason with its record; no score. A counterpart's own companies are listed apart as "Already connected".
- **Earliness test `/backtest`:** the four groups (1, 12, 5, 1), the lane chart, the wide intake table and the stitcher line.

---

## The 3-minute path (drive and narrate; sound on, demo flag set)

Start with `/?demo=1` loaded and nothing filtered (see "Before going live" and "Reset").

| Time | Driver does | Narrator says |
|---|---|---|
| 0:00-0:20 | **Home with the Ask Aava bar.** Type "Tell me about Viva Jets" and press Enter. The answer card appears with Aava's first answer (recorded voice, about 28 s; cut it short if the hall is loud) and "Open the full memo". Do not open it yet. | The opener sentence in the partners' words: "We find promising blue-economy startups in public records before they reach your pipeline, and answer your four questions with a link under every fact." Then: "You can ask the radar in plain words. It answers from the records, with no AI model behind the bar." |
| 0:20-0:45 | **Two clicks, filtering in place.** In the rail's first group, Sector, press the sub-sector **Ocean data and monitoring**: the list narrows to 4 of 59. Press the country **Finland** (its flag beside the name): 3 of 59, the Bulgarian company drops out. Point at the chips and at the address bar, then press **Clear all** (59 again). Point at one row's criteria box. | "The sector is a filter now, with the sub-sectors under it, each one traced to a record. Click a country and the list changes where you stand: no page load, and the address bar holds the view, so this is a link you can send. Every row shows what you score: impact, TRL, BRL, IRL, thesis fit and verdict, as the company page states them." |
| 0:45-1:10 | Click the **Viva Jets Oy** row (or "Open the full memo"). Read the headline ("reads accelerator: ocean impact medium on record"), then scroll to the **Ocean Impact Assessment**: impact area, the evidence records with their links, scalability "not assessed from public records", **level 5 of 9, Medium**, **confidence high** with its reason, and **To raise it**. | "This is the ocean impact, as you asked: the area in words, the records behind it, how ready the evidence is on a ladder of nine, and how sure we are. It measures how well the impact is evidenced, not how much impact there is. Level 5: the register and Redstone's own portfolio page agree. To raise it: a record from another source family whose own text names the area." |
| 1:10-1:40 | Tap **Ask Aava**, then question 4, **Who should we meet, and what do we say?** (about 21 s, recorded voice, captions on). Say nothing while it speaks. Then question 6, **What would change your mind?** (about 15 s, the browser's voice today). | After it ends: "Aava speaks only from the records on this page: every sentence is built by code from a sourced record, and it says what it is missing as plainly as what it has. It never says a new record would lower a verdict. The voice is a recording, or the browser's own voice where the text changed." |
| 1:40-2:05 | Open <https://jx.hankintaviikko.fi/c/3166759-6?demo=1> (type it, or use the bar: "Tell me about Arctic Fry"). Tap question 6 (about 20 s, the browser's voice). | "Arctic Fry, a Nordic Blue company: accelerator on the same rule. Business readiness 2 of 9, technology and investment readiness have no public record. Not a low score: a gap, and Aava says which record would move it." |
| 2:05-2:40 | Back on the home page press the tab **Top matching startups for A'Pelago** (28 of 59): point at one row's two reasons in words, and at the "Matched for" picker. Then open **Match** from the Menu: <https://jx.hankintaviikko.fi/match>, A'Pelago is the default. Point at "Already connected" (20), then at one startup's reason chips and the sentence under them. | "A top match is a match for someone. This is A'Pelago's list, and the same ranking is on the match page: filter first, then rank. Every reason in words with its record. No score, because a number cannot be argued with. Its own cohort is listed apart, as already connected. From a startup the same view gives Viva Jets 56 counterparts that pass the filters." |
| 2:40-3:00 | `/backtest`: point at the headline, then at the wide intake table. | Takeaway: "Applying our own rule to live records, we would have shown 1 of your 19 before January 2026, and that one is tuned: we added Arctic Fry's code after seeing it. Before that it was 0. Declared research finds 12 more. All 7 Finnish ones were already in our store; the miss is the sector rule, and the radar shows you exactly where." Then the closing line below. |

If time runs over, cut question 6 on Arctic Fry. If a number on `/backtest` has moved, say the number on screen. The wide intake line (below) is not in the 3 minutes; say it when asked.

**If the clips are re-rendered before the ZIP** (command in README, "Aava"), Viva Jets questions 3 (about 32 s) and 6 (about 14 s) and Arctic Fry question 6 play the recorded voice too; read the durations from the `manifest.json` beside the clips and use "How sure are you?" at 1:10 if there is time. Until then use the questions above.

## Reset (between visitors, 10 seconds)

Type `/?demo=1` in the address bar and press Enter. That opens the default sector (blue economy, Finland and Nordics), resets the sector cookie so the Menu pages follow it, keeps the demo flag, and loads the home page with no filters (the filters live in the URL, so an address with no query has none). Then check the muted line under the bar and the three tabs (see "Before going live", step 6). Do this after any visit that chose another sector, and at the start of every shift.

## If the first laptop stalls (the backup-laptop line)

Say, without apology: "Let me carry on on the second screen. It is the same live address, so we are exactly where we were." Take the second laptop, which already has the same pages open in the demo order with the demo flag set (Before going live, step 5), and continue from the step you were on. Do not restart the story, and never say "it normally works".

---

## The pitch lines

**Opener (partners' words).** "We find promising blue-economy startups in public records before they reach your pipeline, and answer your four questions with a link under every fact." No team introduction, no market size, never "Hi, we are team X and we built...".

**The missing-information line (say it at the Ocean Impact Assessment, or when asked how we score).** "A'Pelago's own guidance, 17 October: 'missing information is not necessarily a reason to exclude a company or assign it a low score. Identifying information gaps, distinguishing facts from assumptions, and determining what to investigate next can itself be valuable venture intelligence.' We built that in. Where the evidence is only the sector implied, the page says 'not yet evidenced', not Low; 27 of the 59 companies on the home list read that way. Every level says how sure we are and why, and which single record would raise it. Aava has a question for exactly this: what would change your mind?"

**One line per judge criterion** (use the one the judge asks about):
- *Creativity:* "Ocean impact is not another score. It is an area in words, the records that name it, and a ladder of how well it is evidenced."
- *Usability and precision:* "Every row carries the six criteria you score, fourteen filters narrow the list in place, and every view is a link. Every level prints its rule and its source."
- *Actionability:* "For each startup, who it should meet next and why, in words, with a deadline when there is one: 56 counterparts pass the filters for Viva Jets. For each investor or programme, the startups that fit it, its own cohort listed apart."
- *Scalability:* "A new sector is one YAML file. The health-tech swap and the Baltic file run from the same code; nothing sector-specific is in Python."
- *Technical execution with data and AI:* "17,193 companies and 47,693 dated records, each with a link. The AI only proposes: it finds dated events on web pages, and plain code keeps one only after fetching the page twice. The memo, the levels and the matching use no model at all, and Aava's answers are built by code from the records; a reasoning mode exists and is switched off."
- *Visual appeal:* "One editorial design, light and dark, one accent colour, phone and laptop; Aava speaks the page, in a recorded voice where a recording matches the text."

**First ten seconds (the hook, all versions share it).** 0-4 s: the opener. 4-10 s: the first visible action on the live URL (the bar or the Viva Jets row). The judge sees a company page with a verdict and links before they hear any architecture.

**Closing line (peak-end).** The last thing said is ONE real number and the ask. The ask is "scan this and try it on your phone", never "vote for us". "From live records, 0 of your 19 before we tuned one code and 1 after, and all 7 Finnish ones were already in our store: the miss is the sector rule, and the radar shows you exactly where. Scan this and try it yourself."
Opener languages: English first. For Madeleine, a Finnish opener with its English gloss: "Löydämme lupaavat sinisen talouden startupit julkisista rekistereistä ennen kuin ne tulevat teidän tietoonne, ja jokaisen rivin takana on linkki lähteeseen." (We find promising blue-economy startups in public registers before you hear of them, and there is a link to the source behind every line.) Ask the judge's preference, do not assume.

---

## The earliness line (say it exactly this strong, no stronger)

Live `/api/backtest` (17 Oct 2026, 15:17 UTC): "would have shown 1 before January 2026 using live public records. Declared research alone finds 12 earlier; 5 are found only after; 1 has no public signal." The 1 is Arctic Fry Oy, counted because industry code 03220 (freshwater aquaculture) joined the sector list on 17 Oct, after our own audit had named that code as the reason we missed it (D47). It is in-sample.

**Line:** "Before we added that one code, 0 of your 19 from live records; now 1, and it is the one we tuned. We tell you so because the number is only worth quoting if it is honest. The other 6 Finnish ones are registered as software, retail, wholesale, consulting and research, and the sector list does not hold those codes."

Do not say "we find 1 in 19 early". Say it was tuned, in the same breath. The `/backtest` headline reads "1 before January 2026" and does not print the in-sample label itself; the label is in EVAL.md and here, so say it.

## The wide intake line (say it exactly this strong, no stronger)

Live `/api/backtest` (17 Oct 2026, 15:17 UTC): "Entered wide intake before cohort entry: 4 of 19", all four among the 7 cohort companies
with a Finnish business ID. The four: Kilocode (intake date 2003-08-01, a VAT registration; rank 3 of 8; code family added after seeing
it), Sireness (2025-04-30 on a declared-research record; rank 1 of 104), Arctic Fry (2020-10-05, family added after seeing it; rank 3 of 16)
and Emission-Eye (2025-07-02, a public start-up notice; rank 132 of 1,176). Detail: EVAL.md, "Wide intake".

**Pitch line:** "If this had been running last year it would have had 4 of your 7 Finnish startups in its intake before you took them (Kilocode,
Sireness, Arctic Fry and Emission-Eye), but we claim less than that: Kilocode's intake date is a 2003 VAT registration, so it is not an
early find; Kilocode and Arctic Fry are in only because we added their code families after seeing them, so they are in-sample; Sireness
enters on a declared-research record rather than a public one; and Emission-Eye, on a public start-up notice, ranks 132 of 1,176
among the 2025 registrations in its code family."

Do not say "found early" or "4 of 7 found". The page prints each rank beside its own pool and no median. If a number has moved since this was written, say the number on screen and keep the four qualifications.

---

## 60-second table version (Gavel expo, crowded hall)

| Time | Beat |
|---|---|
| 0-4 s | One-sentence opener (partners' words) |
| 4-10 s | First visible action on the live URL: type "Tell me about Viva Jets" in the bar (or click the Viva Jets Oy row) |
| 10-50 s | Core flow: one sub-sector click and one country click (the list changes in place), Viva Jets and its Ocean Impact Assessment (level, confidence, "to raise it"), Aava question 4 if the hall is quiet enough, then the "Top matching startups for A'Pelago" tab, then `/backtest`; one drives, one narrates; point at the page, never the terminal |
| 50-60 s | The closing line |

---

## Hard questions with answer slots

**1. Who exactly is it for?**
Answer: the accelerator lead (A'Pelago screens many applications for a small cohort; the exact numbers are theirs to state, we do not claim them) and the VC associate (Redstone Blue, pre-seed and seed). Monday decision: which five do I call this week, and about what.

**2. What was built this weekend versus pre-existing?**
Answer: see DISCLOSURE.md. Short version: "All application code in this repository was written between 16 Oct 18:00 and 18 Oct 10:00 (Helsinki) with AI coding tools. We brought our own build tooling, checklists, and the public datasets listed there, and we used the third-party services listed there." No hedging.

**3. What breaks first at scale?**
Answer: request-time computation. Every page computes the feed rule from the whole store on each request; with wide intake and the Nordic registers the store grows many times over, so the feed and the backtest must be computed once per refresh instead. The home list and the matchmaking index are already cached and warmed at start. ARCHITECTURE.md names it. Name it before they do.

**4. Did the wide intake find your startups early?**
Answer: the pitch line above, word for word. If pressed on the other 3: "Finnish Sauna Shop, Sub Marine Store and Taikoa are registered as retail, wholesale and consulting, outside the intake's code families, and 12 of the 19 are outside the Finnish register. Your real entry dates would replace our January 2026 reference; that is the one ask in PILOT.md."

**5. Is the ocean impact level a real impact score?**
Answer: no, and the page says so. It is evidence readiness: how well an impact area is evidenced in public records, on nine rungs that each name the record that must be on file. The Ocean Impact Navigator publishes areas and KPIs but no levels, so the ladder is ours and is open for you to change (PILOT.md, weeks 5 and 6).

**6. Where is the score in the matching?**
Answer: there is none, by rule (A34). Every counterpart shows the reasons that hold, each with its record, and the ones that did not hold with a note. The weights only order the list, and they are a stated hypothesis: there is no ground truth for who should have met whom, so a partner rating of 20 pairs is the first real check (PILOT.md).

**7. Is there an AI model behind Aava and the Ask Aava bar?**
Answer: not on the live site today. The text is built from records by code and the bar's answers come from a deterministic router. The voice is a recording made at build time (ElevenLabs) where the text still matches, or the browser's own voice. We did build a reasoning mode: Aava on Claude Sonnet 5.5 through the Messages API, with seven read-only tools over this site's own records, company names and links code-checked after generation, a deterministic fallback, gated by the demo flag and rate-limited. It is switched off until its live test passes. Say the limit if asked: code checks names and links, not that every figure in a sentence matches the record it restates. Elsewhere the only AI in the data path is the stitcher, whose proposals plain code checks twice, and the company summaries, whose every sentence code verifies.

**8. Why aren't LinkedIn, Dealroom and Crunchbase connected?**
Answer: they sit behind a login or a paid account, and we do not scrape behind a login (A27). They are drawn as connector slots, "not connected", and PILOT.md names the way in: your own deal notes as a private source.

**9. Arctic Fry is your one live hit. Did you tune the rule to it?**
Answer: yes, one code. Arctic Fry is registered as freshwater aquaculture, 03220, and our list held the marine code 03210 only; we added 03220 on 17 October, after our own earliness audit and a judge's review had both named it (D47). So 1 of 19 is in-sample, the 0 of 19 before it was not, and the page for Arctic Fry shows the rule that counted it.

---

## Before going live (every time, in this order)

1. **Open every page once after any restart or deploy**, in the order of the demo, and wait for each to finish: `/?demo=1`, `/?verdict=ACCELERATOR`, `/c/2962040-6?demo=1`, `/c/3166759-6?demo=1`, the home page's Top matching tab, `/match`, `/match?company=2962040-6`, `/backtest`, `/radar`. Every sector's home list is built in the background at start (D26) and a request waits at most 3 seconds for it; if a page shows "The grouped view of this sector is still being prepared", wait ten seconds and reload. The Top matching tab builds its ranking once per organisation in a background thread (about 1.5 s, A'Pelago's at start) and waits at most 3 seconds. The first matchmaking page after a restart builds its index from the store in about 2 seconds (1.4 to 2.7 s measured); after that a company's matches take milliseconds.
2. **Present from a laptop**, not a phone: the demo path uses the filter rail, the wide tables on `/backtest` and sound. The phone is for the judge's own trial after the QR scan.
3. **Sound on, and tested.** Laptop volume up, open `/c/2962040-6?demo=1`, tap Ask Aava, then question 4 (Who should we meet): you should hear the recorded voice (Rachel), not a robotic browser voice. Questions 2, 3 and 6 and all of Arctic Fry's are read by the browser voice today, and that is expected until the clips are re-rendered. If you hear the browser voice on Viva Jets question 1, 4 or 5, a clip did not load: hard reload. Captions are always on, so a dead speaker costs nothing; keep going.
4. **Set the demo flag once** on the presenting laptop (`?demo=1`; it is remembered on that device). With the flag on, Ask Aava appears on every company page and on the home page, and the Ask Aava bar's microphone button appears. Allow the microphone in the browser once and say one question aloud to test it (Chrome or Edge; speech recognition is done by the browser); the bar works by typing if the hall is too loud. `GET /api/aava/status` should answer `available: false`; if it says true, the chief has switched the reasoning mode on and the bar will converse through the model first, which is slower and not part of this script.
5. **A second laptop with the same pages open as backup**: same URL, same demo flag, the same tabs open in the demo order, battery full, on power. If the first laptop stalls, use the backup-laptop line above and continue from the step you were on.
6. **Check the home page reads as expected:** the muted line under the bar reads "23 companies first seen in the last 90 days, 59 on the list" (the number moves as records arrive; say the number on screen), the tabs read 59 / 28 / 23, the rail's Verdict group reads Accelerator 21 and the filter chips are empty. If the headline is 0 or the list is empty, the store did not load: tell the chief and switch to the fallback recording (Table checklist).
7. **The example chips are all safe.** A chip is shown only when its answer is not empty (D40). "Show accelerator candidates in Finland" answers "15 of 59 companies on the list match: accelerator candidates, in Finland." and applies the filter in place. "What is new on the radar?" answers in the browser's voice today, because the recorded clips were rendered before KalanPojat Oy entered the answer.
8. **Keep the Baltic thesis out of the live path** unless asked ("a third thesis file widens the same code to the Baltic countries; it is not part of the demo"). Choosing it in the Sector group swaps the list in place and sets the sector cookie, so use the Reset step afterwards. It is warm after a restart (0.45 to 0.87 s over 10 requests on 17 Oct), so it will not stall if a judge asks to see it.

---

## Mid-demo restart line

If a judge arrives while the demo is running, stop immediately:
"Let me start from the top. We find promising blue-economy startups in public records before they reach your pipeline, and answer
your four questions with a link under every fact."
Jump straight to the first visible action. Never finish the flow you were in.

---

## Table checklist

- Laptop on the live URL, phone on the live URL, QR card, one-page PILOT printed x10.
- A second laptop with the same pages open as the backup (Before going live, step 5).
- One person at the table at all times during the expo window. Rotate every 30-40 minutes.
- Battery, charger, hotspot. Demo must work on 4G if venue wifi dies.
- 60-second screen recording of the demo path saved on the phone as the fallback, made from the 15:04 UTC build (1b6c857) or later (an older recording shows 58 startups and a "Top fits" tab).
- Typed fallback ready for any voice input in case the hall is too loud.
- Judge pass (hack-verify): QR card printed and standing next to the laptop, brightness 100 percent, laptop on power, handout on the table, narrator on the aisle side.
- Never say "it normally works": switch to the fallback recording instead.
- Run "Before going live" above at the start of every shift, not only once, and the Reset step between visitors.
