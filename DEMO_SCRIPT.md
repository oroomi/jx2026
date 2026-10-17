# Demo script

Gavel expo voting is pairwise: "better or worse than the last table?" The first ten seconds decide it.
Partners pick their own track winner against their own criterion, so lead with the partners' words for partner judges.
Every number below was read from the live site or its JSON API on 17 Oct 2026 (17:38 to 17:50 UTC, footer build ac49cd8, live since 17:37 UTC, after the j3 round); each is listed with its source in [docs/NUMBERS.md](docs/NUMBERS.md). Say the number on screen if one has moved.

Two companies carry the demo, both real and both on the live site:
- **Viva Jets Oy**, business ID 2962040-6, Redstone Blue portfolio: <https://jx.hankintaviikko.fi/c/2962040-6>. Industry code 30120 (building of pleasure and sporting boats) is on the sector list. The memo reads **PORTFOLIO SUPPORT** (D65): "Already in Redstone Blue's portfolio, and the next support is a pilot with Eckerö Line Abp (Eckerö Group) and a grant from Interreg Central Baltic Programme 2021-2027". It no longer reads accelerator: a company a fund already holds is not sent to an accelerator. The Ocean Impact Assessment reads level 5 of 9, Medium, confidence high; TRL 4, BRL 6, IRL 4.
- **Arctic Fry Oy**, business ID 3166759-6, Nordic Blue 2026 cohort: <https://jx.hankintaviikko.fi/c/3166759-6>. Registered as freshwater aquaculture (03220), a code added to the sector list on 17 Oct (D47) after the earliness audit had named it as the reason the company was missed. It reads PORTFOLIO SUPPORT as a cohort company ("Already in A'Pelago's Nordic Blue 2026 cohort, and the next support is a pilot with Natural Resources Institute Finland (Luke) and a grant from Baltic Sea Action Plan (BSAP) Fund (NIB + NEFCO)"). Business readiness is 2 of 9, technology and investment readiness have no public record, and the page says so. It is also the one company the earliness test finds from live records (first sales on 2020-10-05), and that hit is in-sample.
- **Aava is hidden on the public site.** The demo URL carries `?demo=1` (the flag is remembered on that device; `?demo=0` turns it off). **Recorded voice (Rachel):** the company clips were re-rendered at 17:34 UTC, and 12 of the 16 committed clips match the page: all six questions for Viva Jets and all six for Arctic Fry. The home "what is new" answer (4 clips) was not re-rendered and is read by the browser's voice. Captions are always on, so either voice works on a quiet table.
- **Aava's reasoning mode is ON behind the demo flag** (since 17:37 UTC; `GET /api/aava/status` answers `available: true`, model `claude-sonnet-5-5`). With `?demo=1` a question typed or spoken in the Ask Aava bar opens the conversation panel and a model answers, through read-only tools over our own records: "looking at the radar", "reading the company record", then the answer, in about 5 to 7 seconds (one live turn for "Tell me about Viva Jets" took 6.2 s on 17 Oct) and about 2 cents a turn, spoken in Rachel through the run-time voice (capped at 8,000 characters a day, so roughly ten spoken answers; after that the browser's voice reads it). Adaptive thinking, effort low, at most 3 steps; 8 turns a minute per client address and 400 a day. **The limit is per address, so judges on the same venue wifi share the 8 a minute**; past it, or on any error, the bar shows a graceful sentence and then the deterministic answer, which plays the recorded clip. The kill switch is the file `data/AAVA_LLM_OFF`: it is absent now (parked as `data/AAVA_LLM_OFF.parked`), and moving it back switches the mode off with no restart.

What the live pages look like now, so the driver is never surprised:
- **Home `/`:** the hero is the **Ask Aava bar**: the title, one line saying every answer is built from the public records on file, the input with a send button, five example questions as chips ("What is new on the radar?", "Tell me about Viva Jets", "Who should A'Pelago meet?", "Aquaculture startups with TRL at least 4", "Show high thesis fit companies in Finland"), and one muted line, "23 companies first seen in the last 90 days, 59 on the list. Press Ctrl K to ask." The header tabs are in the **Menu** (top right) and in the footer. Under the bar three tabs (All startups 59, **Top matching startups for A'Pelago** 25, New this quarter 23), the country links, a sort line ("Sorted by verdict, strongest first (Invest to Watchlist), then by evidence") and on desktop the filter rail on the left: **Sector** first (the three sectors, and under the blue one the sub-sectors: Shipbuilding and boats 14, Water and pollution 10, Ship repair and maritime services 8, Aquaculture and fisheries 4, Ocean data and monitoring 4, Coastal tourism and boating 3, Ports and marine construction 2, Maritime software and tech 1, Shipping and logistics 1, Not yet classified 17), then "What the judges score" (Verdict: Partner introduction 1, Portfolio support 28, Watchlist 30; Ocean impact; Technology, Business and Investment readiness; Thesis fit High 29, Medium 30) and "Narrow down" (Country, Impact category, Registered, Source records, Programme deadline, Declared company). Each row has the company name, its first reason in words, its line of business, its ocean impact area, a life-line and the **criteria box** (Impact, TRL, BRL, IRL, Fit, Verdict). The first rows are Suomen Vesistökunnostus Oy (the one PARTNER INTRODUCTION), then Viva Jets Oy, Valkama Watercrafts Oy and Arctic Fry Oy. On a phone the rail is a bottom sheet. Filters work in place: the list changes, the address bar changes, the page does not reload.
- **Company page:** the verdict and its reason at the top, "Read against the sector thesis Blue economy, Finland and Nordics", the **Ocean Impact Assessment**, key statistics, an AI summary of the linked records, Who to meet, Next steps (matchmaking), the news life-line, the four questions (01 to 04) with every rule printed. The "Ask Aava" button sits bottom right when the demo flag is on; it opens six questions.
- **Match `/match`:** pick a counterpart (191) or a startup; reason chips and one sentence per reason with its record; no score. A counterpart's own companies are listed apart on the tab "Already connected".
- **Earliness test `/backtest`:** the four groups (1, 12, 5, 1), a tuning note directly under the headline, the lane chart, the wide intake table and the stitcher line.

---

## The 3-minute path (drive and narrate; sound on, demo flag set)

Start with `/?demo=1` loaded and nothing filtered (see "Before going live" and "Reset").

| Time | Driver does | Narrator says |
|---|---|---|
| 0:00-0:30 | **Home with the Ask Aava bar.** Type "Tell me about Viva Jets" and press Enter. For about 6 s the panel says "Aava is thinking" and "reading the company record", then the answer appears (verdict Portfolio Support, thesis fit High, ocean impact Medium 5 of 9, ranks 2nd of 59) with a link to the Viva Jets page, and is spoken in Rachel. Do not open it yet. If the model is slow or fails, the deterministic card appears instead and plays the recorded clip (about 28 s: "Based on what the radar holds on Viva Jets Oy, I think it needs portfolio support, not an entry decision..."); cut it short if the hall is loud. | The opener sentence in the partners' words: "We find promising blue-economy startups in public records before they reach your pipeline, and answer your four questions with a link under every fact." Then: "You can ask the radar in plain words. The answer is written from the records, with the links, and code checks the names and links before you see them." |
| 0:30-1:10 | Open **Viva Jets Oy** from the answer's link. Read the headline: **Portfolio support**, "Already in Redstone Blue's portfolio, and the next support is a pilot with Eckerö Line Abp and a grant from Interreg Central Baltic Programme". Point at "Read against the sector thesis". Scroll to the **Ocean Impact Assessment**: impact area, the evidence records with their links, scalability "not assessed from public records", **level 5 of 9, Medium**, **confidence high** with its reason, and **To raise it**. | "Redstone already holds this company, so the radar does not tell you to put it in an accelerator; it says what the next support is. This is the ocean impact, as you asked: the area in words, the records behind it, how ready the evidence is on a ladder of nine, and how sure we are. It measures how well the impact is evidenced, not how much impact there is." |
| 1:10-1:25 | Tap **Ask Aava**, then question 4, **Who should we meet, and what do we say?** (about 19 s, recorded voice, captions on). Say nothing while it speaks. If time is short, question 6 instead (about 15 s: "What I am missing: no public buyer on record yet ... only a change to that list would change it"). | After it ends: "Aava speaks only from the records on this page, and says what it is missing as plainly as what it has." |
| 1:25-2:00 | **A'Pelago's match page.** Menu, Match (A'Pelago is the default): <https://jx.hankintaviikko.fi/match?org=apelago>. Point at "Declared cohort or portfolio: 23 companies, 20 in our records", "Best fits 25", open the first fit and its **Why this match** (sector, stage window, geography, each with its record). Then press the tab **Already connected** (20). | "A top match is a match for someone. This is A'Pelago's list: filter first, then rank, every reason in words with its record, and no score, because a number cannot be argued with. Its own cohort is listed apart as already connected, never ranked. The home page's second tab prints these same 25." |
| 2:00-2:30 | **Redstone Blue's match page:** choose Redstone Blue in the counterpart list, or <https://jx.hankintaviikko.fi/match?org=redstone-blue>. Point at "Best fits 22, Already connected 9", at the line "No startup on the radar is at due diligence yet; these are the closest, in the order below", and at Arctic Fry, Emission-Eye, Sireness and Sub Marine Store, each marked portfolio support. | "For an investor the radar shows the early pipeline. None is at due diligence yet, and the page says so instead of showing nothing. Fifteen of Redstone's 22 best fits are A'Pelago cohort companies: accelerator to fund. That is the handover your two organisations are here to make." |
| 2:30-3:00 | `/backtest`: point at the headline, at the tuning note directly under it, then at the wide intake table. | Takeaway: "We publish our own miss rate. Applying our own rule to live records, we would have shown 1 of your 19 before January 2026, and that one is tuned: we added Arctic Fry's code after seeing it. Before that it was 0. Declared research finds 12 more. All 7 Finnish ones were already in our store; the miss is the sector rule, and the radar shows you exactly where." Then the closing line below. |

If time runs over, cut question 4 or 6 and the tuning note read-out. If a number on `/backtest` has moved, say the number on screen. The wide intake line (below) is not in the 3 minutes; say it when asked. A 25-second extra, if the hall allows: in the home rail press the sub-sector **Ocean data and monitoring** (4 of 59), then the country **Finland** (3 of 59), point at the chips and the address bar, and press **Clear all** (59 again).

**Lines to avoid.**
- **Do not switch the sector to Health technology, Turku region.** It holds one company (KE Pharma Oy); it is a swap demo, not an evaluated thesis. Keep the Baltic file out of the live path too, unless asked.
- **Do not press the example chip "Show high thesis fit companies in Finland" on a table without the model.** The deterministic router answers "46 of 59 companies on the list match: in Finland. I did not use: high, thesis, fit", that is, it applies Finland only; the filter that means it is Thesis fit High with Finland, 16 of 59.
- **Do not say "accelerator candidate" for any company on the list.** No row on the home list reads ACCELERATOR since D65 and D66 (the Match page still labels some register companies outside the list with the accelerator path), and the former chip "Show accelerator candidates in Finland" now answers 0 of 59.

## Reset (between visitors, 10 seconds)

Type `/?demo=1` in the address bar and press Enter. That opens the default sector (blue economy, Finland and Nordics), resets the sector cookie so the Menu pages follow it, keeps the demo flag, and loads the home page with no filters (the filters live in the URL, so an address with no query has none). Press Esc to close an open Aava answer or panel. Then check the muted line under the bar and the three tabs, 59 / 25 / 23 (see "Before going live", step 6). Do this after every visitor, after any visit that chose another sector, and at the start of every shift.

## If the first laptop stalls (the backup-laptop line)

Say, without apology: "Let me carry on on the second screen. It is the same live address, so we are exactly where we were." Take the second laptop, which already has the same pages open in the demo order with the demo flag set (Before going live, step 5), and continue from the step you were on. The pages in order are `/?demo=1`, `/c/2962040-6?demo=1`, `/match?org=apelago`, `/match?org=redstone-blue`, `/backtest`. Do not restart the story, and never say "it normally works". If the whole site is down on both laptops, switch to the saved 60-second recording (Table checklist).

---

## The pitch lines

**Opener (partners' words).** "We find promising blue-economy startups in public records before they reach your pipeline, and answer your four questions with a link under every fact." No team introduction, no market size, never "Hi, we are team X and we built...".

**The missing-information line (say it at the Ocean Impact Assessment, or when asked how we score).** "A'Pelago's own guidance, 17 October: 'missing information is not necessarily a reason to exclude a company or assign it a low score. Identifying information gaps, distinguishing facts from assumptions, and determining what to investigate next can itself be valuable venture intelligence.' We built that in. Where the evidence is only the sector implied, the page says 'not yet evidenced', not Low; 27 of the 59 companies on the home list read that way. Every level says how sure we are and why, and which single record would raise it. Aava has a question for exactly this: what would change your mind?"

**One line per judge criterion** (use the one the judge asks about):
- *Creativity:* "Ocean impact is not another score. It is an area in words, the records that name it, and a ladder of how well it is evidenced."
- *Usability and precision:* "Every row carries the six criteria you score, fourteen filters narrow the list in place, and every view is a link. Every level prints its rule and its source."
- *Actionability:* "For each startup, who it should meet next and why, in words, with a deadline when there is one: 54 counterparts pass the filters for Viva Jets. For each investor or programme, the startups that fit it, its own cohort listed apart."
- *Scalability:* "A new sector is one YAML file. The health-tech swap and the Baltic file run from the same code; nothing sector-specific is in Python."
- *Technical execution with data and AI:* "17,193 companies and 47,693 dated records, each with a link. The AI only proposes: it finds dated events on web pages, and plain code keeps one only after fetching the page twice. The memo, the levels and the matching use no model at all, and the recorded Aava answers are built by code from the records. Behind the demo flag a reasoning mode on Claude Sonnet 5.5 answers typed questions through read-only tools over our own records; code checks every name and link in its answer before you see it, and the answer falls back to the deterministic one on any failure."
- *Visual appeal:* "One editorial design, light and dark, one accent colour, phone and laptop; Aava speaks the page, in a recorded voice (all twelve company clips match the text today) and in the same voice for the model's answers."

**First ten seconds (the hook, all versions share it).** 0-4 s: the opener. 4-10 s: the first visible action on the live URL (the bar or the Viva Jets row). The judge sees a company page with a verdict and links before they hear any architecture.

**Closing line (peak-end).** The last thing said is ONE real number and the ask. The ask is "scan this and try it on your phone", never "vote for us". "From live records, 0 of your 19 before we tuned one code and 1 after, and all 7 Finnish ones were already in our store: the miss is the sector rule, and the radar shows you exactly where. Scan this and try it yourself."
Opener languages: English first. For Madeleine, a Finnish opener with its English gloss: "Löydämme lupaavat sinisen talouden startupit julkisista rekistereistä ennen kuin ne tulevat teidän tietoonne, ja jokaisen rivin takana on linkki lähteeseen." (We find promising blue-economy startups in public registers before you hear of them, and there is a link to the source behind every line.) Ask the judge's preference, do not assume.

---

## The earliness line (say it exactly this strong, no stronger)

Live `/api/backtest` (17 Oct 2026, 17:38 UTC): "would have shown 1 before January 2026 using live public records. Declared research alone finds 12 earlier; 5 are found only after; 1 have no counted signal." The 1 is Arctic Fry Oy, counted because industry code 03220 (freshwater aquaculture) joined the sector list on 17 Oct, after our own audit had named that code as the reason we missed it (D47). It is in-sample.

**Line:** "Before we added that one code, 0 of your 19 from live records; now 1, and it is the one we tuned. We tell you so because the number is only worth quoting if it is honest. The other 6 Finnish ones are registered as software, retail, wholesale, consulting and research, and the sector list does not hold those codes."

Do not say "we find 1 in 19 early". Say it was tuned, in the same breath. The `/backtest` headline reads "1 before January 2026"; since 17:24 UTC (D74) a tuning note sits directly under it ("The families 582 (software publishing) and 03 (fishing and aquaculture) were added after the backtest showed the net missed two cohort companies, so results for those two are measured on the companies used to tune the net"). It names the intake families, and Arctic Fry's code 03220 is in family 03, so point at the note and say the Arctic Fry sentence above in your own words.

## The wide intake line (say it exactly this strong, no stronger)

Live `/api/backtest` (17 Oct 2026, 17:38 UTC): "Entered wide intake before cohort entry: 4 of 19", all four among the 7 cohort companies
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
| 10-50 s | Core flow: one sub-sector click and one country click (the list changes in place), Viva Jets and its Ocean Impact Assessment (level, confidence, "to raise it"), Aava question 4 if the hall is quiet enough, then A'Pelago's match page (the Top matching tab prints the same 25), then `/backtest`; one drives, one narrates; point at the page, never the terminal |
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
Answer: yes, behind the demo flag, since 17:37 UTC on 17 Oct, and nowhere else. Without `?demo=1` the pages, the memo, the matching and the bar's answers are built from records by code (a deterministic router); the voice is a recording made at build time (ElevenLabs) where the text still matches, or the browser's own voice. With the flag, a typed or spoken question goes to Aava on Claude Sonnet 5.5 through the Messages API, with read-only tools over this site's own records (no SQL, no writes, no network), adaptive thinking at low effort and at most 3 steps. Measured: five real selftests took 4.7 to 7.0 s and cost $0.015 to $0.026 a turn. Code checks every company name and link in the answer against what the tools returned and prints a Sources line; it falls back to the deterministic answer on any failure; it is rate-limited (8 turns a minute per address, 400 a day). Say the limit if asked: code checks names, links and addresses, not that every figure in a sentence matches the record it restates. Elsewhere the only AI in the data path is the stitcher, whose proposals plain code checks twice, and the company summaries, whose every sentence code verifies.

**8. Why aren't LinkedIn, Dealroom and Crunchbase connected?**
Answer: they sit behind a login or a paid account, and we do not scrape behind a login (A27). They are drawn as connector slots, "not connected", and PILOT.md names the way in: your own deal notes as a private source.

**9. Arctic Fry is your one live hit. Did you tune the rule to it?**
Answer: yes, one code. Arctic Fry is registered as freshwater aquaculture, 03220, and our list held the marine code 03210 only; we added 03220 on 17 October, after our own earliness audit and a judge's review had both named it (D47). So 1 of 19 is in-sample, the 0 of 19 before it was not, and the page for Arctic Fry shows the rule that counted it.

---

**10. Why does Viva Jets read "portfolio support" and not "accelerator"?**
Answer: because Redstone already holds it (D65). A declared cohort or portfolio company gets the verdict PORTFOLIO SUPPORT whatever its bands, and the sentence names the relationship and the next support: a pilot partner and a grant. A judge's dry-run read "Kelluu reads accelerator" with a 15 million euro round on file; the partners' own companies were being told to enter an accelerator, and that was wrong.

**11. So 28 of your 59 are just the companies we gave you?**
Answer: yes, and the page says so. The 28 declared members read PORTFOLIO SUPPORT by rule, which is not an independent finding. The radar's own finds are the other 31: WATCHLIST 30 and PARTNER INTRODUCTION 1, and none is at due diligence yet; the investor view says that in words and shows the closest. A thesis fit that rests on the industry code alone is capped at Medium (D66), which is why two register companies fell from accelerator to watchlist.

---

## Before going live (every time, in this order)

1. **Open every page once after any restart or deploy**, in the order of the demo, and wait for each to finish: `/?demo=1`, `/?verdict=PORTFOLIO+SUPPORT`, `/c/2962040-6?demo=1`, `/c/3166759-6?demo=1`, the home page's Top matching tab, `/match?org=apelago`, `/match?org=redstone-blue`, `/match?company=2962040-6`, `/backtest`, `/radar`. Every sector's home list is built in the background at start (D26) and a request waits at most 3 seconds for it; if a page shows "The grouped view of this sector is still being prepared", wait ten seconds and reload. The Top matching tab builds its ranking once per organisation in a background thread (about 1.5 s, A'Pelago's at start) and waits at most 3 seconds. The first matchmaking page after a restart builds its index from the store in about 2 seconds (1.4 to 2.7 s measured); after that a company's matches take milliseconds.
2. **Present from a laptop**, not a phone: the demo path uses the filter rail, the wide tables on `/backtest` and sound. The phone is for the judge's own trial after the QR scan.
3. **Sound on, and tested.** Laptop volume up, open `/c/2962040-6?demo=1`, tap Ask Aava, then question 4 (Who should we meet): you should hear the recorded voice (Rachel), not a robotic browser voice. All six of Viva Jets' questions and all six of Arctic Fry's play Rachel today; only the home "what is new" answer is read by the browser voice. If you hear the browser voice on a company question, a clip did not load: hard reload. Captions are always on, so a dead speaker costs nothing; keep going.
4. **Set the demo flag once** on the presenting laptop (`?demo=1`; it is remembered on that device). With the flag on, Ask Aava appears on every company page and on the home page, and the Ask Aava bar's microphone button appears. Allow the microphone in the browser once and say one question aloud to test it (Chrome or Edge; speech recognition is done by the browser); the bar works by typing if the hall is too loud. `GET /api/aava/status` should answer `available: true` (the reasoning mode is on); if it says false, the file `data/AAVA_LLM_OFF` is back in place or the key is missing, and the bar answers by the deterministic router only (the script still works; the first beat then plays the recorded clip). Type one question in the bar before the doors open so the model's first call is warm, and expect 5 to 7 seconds.
5. **A second laptop with the same pages open as backup**: same URL, same demo flag, the same tabs open in the demo order, battery full, on power. If the first laptop stalls, use the backup-laptop line above and continue from the step you were on.
6. **Check the home page reads as expected:** the muted line under the bar reads "23 companies first seen in the last 90 days, 59 on the list" (the number moves as records arrive; say the number on screen), the tabs read 59 / 25 / 23, the rail's Verdict group reads Partner introduction 1, Portfolio support 28 and Watchlist 30, and the filter chips are empty. If the headline is 0 or the list is empty, the store did not load: tell the chief and switch to the fallback recording (Table checklist).
7. **The example chips: all have an answer, one is weak.** A chip is shown only when its answer is not empty (D40). "Aquaculture startups with TRL at least 4" answers "1 of 59 companies on the list match: in the aquatech sector, TRL at least 4 (bands 4 to 6 and 7 to 9)" and applies the filter in place. "What is new on the radar?" is read by the browser's voice, because the feed's recorded clips no longer match its text. "Show high thesis fit companies in Finland" is the weak one (see "Lines to avoid"). With the model on, every chip is answered by the model instead.
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
- 60-second screen recording of the demo path saved on the phone as the fallback, made from the 17:37 UTC build (ac49cd8) or later (an older recording shows ACCELERATOR verdicts, 28 on the Top matching tab, or 58 startups and a "Top fits" tab).
- Typed fallback ready for any voice input in case the hall is too loud.
- Judge pass (hack-verify): QR card printed and standing next to the laptop, brightness 100 percent, laptop on power, handout on the table, narrator on the aisle side.
- Never say "it normally works": switch to the fallback recording instead.
- Run "Before going live" above at the start of every shift, not only once, and the Reset step between visitors.
