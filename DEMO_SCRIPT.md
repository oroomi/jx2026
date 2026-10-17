# Demo script

Gavel expo voting is pairwise: "better or worse than the last table?" The first ten seconds decide it.
Partners pick their own track winner against their own criterion, so lead with the partners' words for partner judges.

Two companies carry the demo, both real and both on the live site:
- **Arctic Fry Oy**, business ID 3166759-6, Nordic Blue 2026 cohort: <https://jx.hankintaviikko.fi/c/3166759-6>. Its first live
  public record is from 2020 (first sales on 2020-10-05 in the VAT register), more than five years before the cohort, and the sector rule
  still did not count it, because it is registered as freshwater aquaculture (03220), a code the list does not hold.
- **Viva Jets Oy**, business ID 2962040-6, Redstone Blue portfolio: <https://jx.hankintaviikko.fi/c/2962040-6>. Industry code
  30120 (building of pleasure and sporting boats) is on the sector list; share issues registered from 2022 to 2026 and Business
  Finland funding in 2019, 2021 and 2024 are on the page with their links.
- **Aava (voice briefing) is hidden on the public site.** The demo URL is `/c/2962040-6?demo=1` (the flag is remembered on that device; `?demo=0` turns it off).

---

## 90-second script (drive and narrate)
| Time | Driver does | Narrator says |
|---|---|---|
| 0-10 s | Feed `/` already loaded: companies whose earliest public record falls in the last 90 days | The opener sentence. These are the companies your pipeline has not seen yet. |
| 10-30 s | Tap the source chip on the top row; the PRH/YTJ record opens | Every line is a public record with a link. "How sure" says how the company was matched. |
| 30-60 s | Type `Arctic Fry` in Find a startup; the company page opens | Your four questions, in your order. The memo says Watchlist and names the missing evidence. Its first public trace is first sales in October 2020; every level prints its rule. |
| 60-80 s | `/backtest`: point at the headline, then at Taikoa's blank lane | Applying our own rule to live records, we would have shown 1 of your 19 before January 2026, the programme start we declared as the reference. Declared research adds 12. Blanks stay blank. All 7 Finnish ones had records in our store before January; the rule counted one, because the others are registered as software, retail, consulting, R&D and freshwater aquaculture. |
| 80-90 s | Open `/?thesis=health_tech_turku` | Same code, different file: transferable. Takeaway line. |

The 60-80 s numbers come from the live `/backtest` <!-- recheck after data swap -->. If the moment needs data we do not have,
change the moment, not the data.

---

## First ten seconds (the hook, all versions share it)

**0-4 s:** the opener, in the partners' words: "We find promising blue-economy startups in public records before they reach your
pipeline, and answer your four questions with a link under every fact." No team introduction, no market size. Never open with
"Hi, we are team X and we built...".

**4-10 s:** the demo moment starts immediately: the feed is on screen and the driver taps the first source chip. The judge sees
something working before they hear any architecture.

---

## 60-second table version (Gavel expo, crowded hall)

| Time | Beat |
|---|---|
| 0-4 s | One-sentence opener (partners' words) |
| 4-10 s | First visible action on the live URL: tap the top row's source chip |
| 10-50 s | Core flow: type `Arctic Fry`, show the memo and question 02 with its printed rule, then `/backtest`; one drives, one narrates; point at source rows, never the terminal |
| 50-60 s | Takeaway line: one sentence the judge can repeat at the next table |

Opener (partners' words): "We find promising blue-economy startups as early as possible for accelerator and fund teams, so that you see the companies your pipeline has not seen yet, with the public record behind every line."
Takeaway line: "Ocean Opportunity Radar finds blue-economy startups from public records before they reach your pipeline, and answers your four questions with a link under every fact."
Closing number: "1 of your 19 cohort companies was visible to our rule in live public records before January 2026, our declared reference for the Nordic Blue start, and 13 of 19 with declared research; 1 had nothing public. Scan this and try it on your own company." <!-- recheck after data swap -->

---

## 2-minute table version + 1 minute questions

| Time | Beat |
|---|---|
| 0:00-0:10 | One-sentence opener and first visible action |
| 0:10-1:15 | Core flow on the live URL, one drives one narrates: the feed, Arctic Fry Oy (cohort, the memo and the four questions), then Viva Jets Oy (portfolio: code 30120 on the sector list, share issues and Business Finland years with links) |
| 1:15-1:35 | One edge case shown honestly: Arctic Fry's first sales in 2020 is on the page but not counted by the backtest, because freshwater aquaculture is not on the code list; we added the fishing and aquaculture family to wide intake after seeing that, and the page says so |
| 1:35-1:50 | Why it works: one sector file drives everything, and an AI stitcher may only propose events that plain code then checks twice against the page; never the terminal or editor |
| 1:50-2:00 | Takeaway line |
| 2:00-3:00 | Questions: see hard questions below |

---

## 3-minute stage version (finals, if reached)

| Time | Beat |
|---|---|
| 0:00-0:20 | Hook and one-sentence opener |
| 0:20-0:40 | The problem in the partners' words: "find promising startups as early as possible" in "fragmented startup and ecosystem data"; no solution yet |
| 0:40-2:10 | Live demo on the deployed URL: feed, Arctic Fry Oy, Viva Jets Oy, `/backtest`, the sector swap; one honest miss (Arctic Fry's 2020 record not counted) and the source row |
| 2:10-2:40 | Tech and real-world impact: 1 of 19 from live records, all 7 Finnish cohort companies already in our store, and the stitcher's 168 first-check events cut to 128 by the second check (EVAL.md) |
| 2:40-3:00 | Close and takeaway line |

Confirm stage length with organisers Sunday morning before the ceremony.

---

## Mid-demo restart line

If a judge arrives while the demo is running, stop immediately:
"Let me start from the top. We find promising blue-economy startups in public records before they reach your pipeline, and answer
your four questions with a link under every fact."
Jump straight to the first visible action. Never finish the flow you were in.

---

## Three hard questions with answer slots

**1. Who exactly is it for?**
Answer: the accelerator lead (A'Pelago screens many applications for a small cohort; the exact numbers are theirs to state, we do not claim them) and the VC associate (Redstone Blue, pre-seed and seed). Monday decision: which five do I call this week, and about what.

**2. What was built this weekend versus pre-existing?**
Answer: see DISCLOSURE.md. Short version: "All application code in this repository was written between 16 Oct 18:00 and 18 Oct 10:00 (Helsinki) with AI coding tools. We brought our own build tooling, checklists, and the public datasets listed below, and we used the third-party services listed below." No hedging.

**3. What breaks first at scale?**
Answer: request-time computation. Every page computes the feed rule from the whole store on each request; with wide intake and the Nordic registers the store grows many times over, so the feed and the backtest must be computed once per refresh instead. ARCHITECTURE.md names it. Name it before they do.

---

## Closing line (peak-end, JUDGE_LEVERS A6)

The last thing said is ONE real number (from EVAL.md) and the ask. The ask is "scan this and try it on your phone". It is never "vote for us".
Closing line: "1 of 19 from live records today, and all 7 Finnish ones were already in our store: the miss is the sector rule, and the radar shows you exactly where. Scan this and try it yourself." <!-- recheck after data swap -->
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
