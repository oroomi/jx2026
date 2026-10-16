# The 15 hardest judge questions, with honest answers

Two sentences per answer. Numbers marked "16 Oct" are from the live site on 16 Oct 2026, 22:27Z, build c13bf41, and can move by Sunday: re-read the page named in brackets before the pitch. The cohort numbers stay as `<N1>` and `<N2>` (from /backtest), as in PITCH_3MIN.md, because declared-research events are still being imported. Lines starting "Check Sunday" are notes for Dayo, not part of the answer.

## 1. Where does TRL 6 come from?

Never from us: our rules only give TRL 3, 4, 5 or 7, each from a record type printed under the level (patent filing, funded development project, BlueInvest listing, public contract). A TRL 6 appears only where the company's own BlueInvest pipeline profile states it, labelled "the BlueInvest profile states TRL 6" with a link to the profile (4 profiles in the 16 Oct snapshot), and the "TRL 6-8" next to the EIC Accelerator in our sector file is that grant's entry rule, not a level for any company.

## 2. You have no revenue data. How can you judge anything?

Right, we have no revenue: it sits in filed financial statements and paid databases, and our Financials dimension shows only public grants and contracts. Instead each company page carries a life-line of the traces a company leaves before its first statement (register entry, Business Finland and EU funding, registered share issues and board changes, and first sales and first hire from the tax registers), each dated and linked.

Check Sunday: on build c13bf41 the /method sources table says "PRH/YTJ tax registers: not loaded in this build", so the first-sales and first-hire rows read "no public evidence" on most pages. If they are still not loaded, say "once the tax-register rows are loaded" after "first hire".

## 3. How is this different from Dealroom?

Dealroom Signal is a 1 to 100 "about to raise" score built from Dealroom's own database, and its weights are not public (research/BENCHMARKS.md). We show official registers and public decisions with the record behind every line, measured our earliness on your own cohort instead of claiming it, and keep Dealroom as a connector slot, so a licence holder's data could sit next to ours rather than replace it.

## 4. Your own test says the radar would not have found our cohort early. So what is it for?

Correct: applying its own feed rule, the radar shows `<N1>` of your 19 before January 2026 on /backtest, because your cohort was invisible to public registers until after you picked them. What it does is show the companies that are visible now, each with a dated public record, and the pilot tests that forward on your pipeline instead of claiming it backwards.

Check Sunday: `<N1>` was 0 on 16 Oct. If it is above 0, replace "because your cohort was invisible to public registers until after you picked them" with "so `<N1>` of them were visible before you picked them, and the rest were not".

## 5. `<N2>` of your 19 have no public signal at all. Isn't the data too thin?

Of the 18 on 16 Oct, 10 are outside Finland with no dated record in our sources, 5 have records that our own sector rule rejects (four Finnish register entries, one EU project), 2 were registered before our five-year young-company cut, and 1 has no business ID we could find [/backtest and the company pages]. We keep the blanks on the chart because hiding them would make it prettier and the tool less trustworthy, and /backtest says plainly that a blank "says nothing about whether they were findable elsewhere".

Check Sunday: if `<N2>` is no longer 18, do not quote the breakdown; say "/backtest prints the reason beside each company" and open it.

## 6. What about Sweden?

Sweden is one of the eight countries in the Baltic Sea region selection, but there it gets EU-wide sources only, because we built national register depth just for Finland and Estonia, as /method prints. Both Swedish cohort companies, MOR and Your Devocean, show no public signal today, and a Swedish register would be one new adapter module that we have not built or tested.

Check Sunday: on build c13bf41 the /method sources table lists EU grants and TED as "not loaded in this build"; if asked which EU sources Sweden gets, name CORDIS and BlueInvest unless those two are loaded by then.

## 7. Is the AI inventing anything?

No language model writes anything on the live pages: every sentence is a template filled from a stored record, and the record's link sits beside it. AI coding tools wrote the code this weekend, which DISCLOSURE.md declares, and if an AI summary is ever added it may only restate sourced facts and must carry the same links.

Check Sunday: if Amir's website reader (TASKS.md row 25) is merged, add that it keeps a fact only when the quoted sentence is found on the fetched page. Note for the chief: DISCLOSURE.md lists "in-product LLM calls", but no model client was in radar/, app.py or requirements.txt on build 446e896.

## 8. How do you know the date is right?

We print the date the source itself states (the register's registration date, the CORDIS project start, the Hilma notice date, the registered notice's date) and link the record, so anyone can check it in one tap. Where a source gives only a year, as the Business Finland export does, the page says "year only" and the backtest counts it as 1 January; we never sharpen a date, and a register date is when the company was registered, not when anyone first heard of it.

## 9. Most of your feed is low-confidence code matches. Isn't it noise?

Partly, and we say so on screen: the 90-day window holds 1 high, 59 medium and 34 low-confidence companies, and "low" means "matched by name keyword or industry code only; shown, but never counted in rankings" [16 Oct, start page footer and /method]. Name-only matches sit in a closed "Weak matches" list (37 on 16 Oct), and /method prints that an industry code "is a hint, not proof of a blue-economy business".

## 10. Your sector rule rejected Emission-Eye, one of our own cohort. Isn't the filter wrong?

It is too coarse for some companies, and we print that: Emission-Eye is registered under industry code 62100, computer programming, which is not on the blue-economy code list, and the sector file itself notes that codes are coarse with Emission-Eye as its example. Adding 62100 would also admit every software firm registered in the window, so the better fix is source text that states the business (project texts, contract titles, the company's own site) and your entry dates as ground truth.

## 11. Which company should I call first on Monday?

Question 04 on each company page gives one next step from a decision table, with its "because" and a link, or says that no next step is supported by public records. We do not rank companies against each other: /radar orders by the count of dated public events, "No weighting, no score, no prediction", so the judgement stays yours.

Check Sunday: if section 04 still reads "not yet scored", answer instead: "Question 04 is not switched on in this build; when it is, it gives one step with its because and link, or says none is supported."

## 12. How precisely does it evaluate? What is your measured accuracy?

The one measured result is the earliness test on your cohort, `<N1>` of 19 shown before the reference date by the radar's own feed rule, with every row and its rule on /backtest. A held-out precision test of the feed is `<fill from EVAL.md on Sunday, or say: not completed this weekend>`, and we will not quote a number we have not measured.

## 13. Does it work outside the blue economy, or outside Finland?

Yes: everything that depends on the sector or the region lives in one file, and the header switch loads a health-technology Turku file or a Baltic Sea region file with eight countries on the same code. The limit is register depth: Finland and Estonia have their national registers wired, the other six countries get EU sources only, so each new country needs one new register adapter.

## 14. What did you build this weekend, and what did you bring?

All application code in the repository was written at the event, from the first commit, and `git log --reverse` shows it. We brought generic tooling (screenshot, smoke-test and deploy scripts), our server and domain, our own archive of public procurement notices built before the event, and public datasets, each declared with its source in DISCLOSURE.md.

## 15. Are you tracking founders or private people?

No: the radar's store and every page hold companies only, and a legal name shaped like a private person's name plus Holding, Invest, Capital, Consulting or Tmi is hidden unless the company has a record beyond its register entry (the start page footer prints how many). Registered board changes appear on our pages as a dated event type with a link, never with names, and the radar does not fetch LinkedIn or anything behind a login.

Check Sunday (for the chief, before the ZIP): the declared research file data/declared/ecosystem/blue_economy_fi.sqlite on main still has a `person` table with 87 named rows that no page reads. A judge who opens the repository can find them, which contradicts "companies only": drop that table or that file from the submission, or this answer must say it is there.
