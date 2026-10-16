# The 15 hardest judge questions, with honest answers

Two sentences per answer. Numbers marked "16 Oct" are from the live site on build 446e896 and can move by Sunday: re-read the page named in brackets before the pitch. Lines starting "Check Sunday" are notes for Dayo, not part of the answer.

## 1. Where does TRL 6 come from?

Never from us: our rules only give TRL 3, 4, 5 or 7, each from a record type printed under the level (patent filing, funded development project, BlueInvest listing, public contract). A TRL 6 appears only where the company's own BlueInvest pipeline profile states it, labelled "the BlueInvest profile states TRL 6" with a link to the profile (4 profiles in the 16 Oct snapshot), and the "TRL 6-8" next to the EIC Accelerator in our sector file is that grant's entry rule, not a level for any company.

## 2. You have no revenue data. How can you judge anything?

Right, we have no revenue: it sits in filed financial statements and paid databases, and our Financials dimension shows only public grants and contracts. Your brief asks to find startups as early as possible, which is before statements exist, so we read the traces a young company leaves first (register entry, grants, EU projects, first public contract), each dated and linked.

## 3. How is this different from Dealroom?

Dealroom Signal is a 1 to 100 "about to raise" score built from Dealroom's own database, and its weights are not public (research/BENCHMARKS.md). We show official registers and public decisions with the record behind every line, measure our earliness on your own cohort, and keep Dealroom as a connector slot, so a licence holder's data could sit next to ours rather than replace it.

## 4. 13 of your 19 have no signal at all. So what?

Ten of those 13 are outside Finland, where we have no register source, two are Finnish companies registered before our five-year young-company cut, and one has no business ID we could find in the Finnish register [16 Oct, /backtest and the company pages]. We show the blanks because hiding them would make the chart prettier and the tool less trustworthy, and the fix is more sources, starting with your own entry dates.

Check Sunday: if the backtest adopts the feed's thesis rule (JUDGE_REVIEW.md, finding 1), the counts change; re-read the headline and the "no public signal" rows.

## 5. What about Sweden?

Two of your 19 are Swedish (MOR and Your Devocean) and both show no public signal, because our register adapters read the Finnish register only: the sector file lists FI as the only register country. A Swedish register would be one new adapter module with its own source, and we have not built or tested it this weekend, so we do not claim it.

## 6. Is the AI inventing anything?

No language model writes anything on the live pages: every sentence is a template filled from a stored record, and the record's link sits beside it. AI coding tools wrote the code this weekend, which DISCLOSURE.md declares, and if an AI summary is ever added it may only restate sourced facts and must carry the same links.

Check Sunday: if Amir's website reader (TASKS.md row 25) is merged, add that it keeps a fact only when the quoted sentence is found on the fetched page. Note for the chief: DISCLOSURE.md lists "in-product LLM calls", but no model client is in radar/, app.py or requirements.txt on build 446e896.

## 7. How do you know the date is right?

We print the date the source itself states (the register's registration date, the CORDIS project start, the Hilma notice date) and link the record, so anyone can check it in one tap. Where a source gives only a year, as the Business Finland export does, the page says "year only" and the backtest counts it as 1 January; we never sharpen a date, and a register date is when the company was registered, not when anyone first heard of it.

## 8. Most of your feed is low-confidence code matches. Isn't it noise?

Partly, and we say so on screen: the window holds 1 high, 58 medium and 34 low-confidence companies, and "low" means "matched by name keyword or industry code only; shown, but never counted in rankings" [16 Oct, start page footer and /method]. Name-only matches sit in a closed "Weak matches" list (67 on 16 Oct), and /method prints that an industry code "is a hint, not proof of a blue business".

## 9. You chose the reference date yourselves. Isn't the backtest rigged in your favour?

The reference is January 2026, the programme start month, declared by us and printed on /backtest, because individual pipeline entry dates are not public. Give us real entry dates and each one replaces the reference for that company, labelled with its source (data/declared/cohort_entry_dates.csv): that is exactly the one-month pilot we are asking for.

## 10. A register entry only means a company exists. Why count it?

Fair, and /backtest says it in its limits: "A register entry shows that a company exists, not that anyone was interested in it", and it counts only for companies registered within five years of the reference date. That is why the company page adds the later traces (grants, EU projects, public contracts) and why a register entry alone gives at most BRL 2.

## 11. Which company should I call first on Monday?

Question 04 on each company page gives one next step from a decision table, with its "because" and a link, or says that no next step is supported by public records. We do not rank companies against each other: /radar orders by the count of dated public events, "No weighting, no score, no prediction", so the judgement stays yours.

Check Sunday: if section 04 still reads "not yet scored", answer instead: "Question 04 is not switched on in this build; when it is, it gives one step with its because and link, or says none is supported."

## 12. How precisely does it evaluate? What is your measured accuracy?

The one measured result is the earliness test on your cohort, `<N1>` of 19 before the reference date, with every row and its rule on /backtest. A held-out precision test of the feed is `<fill from EVAL.md on Sunday, or say: not completed this weekend>`, and we will not quote a number we have not measured.

## 13. Does it work outside the blue economy?

Yes: everything sector-specific lives in one file, and the sector switch in the header loads a health-technology Turku file on the same code, which gave a different list of 60 companies in its 90-day window [16 Oct, /?thesis=health_tech_turku]. A new sector in Finland is a new file, not new code; a new country needs a new register adapter.

Check Sunday: the health-tech page still showed the blue-economy subtitle on 16 Oct (JUDGE_REVIEW.md, finding 7); look before switching live.

## 14. What did you build this weekend, and what did you bring?

All application code in the repository was written at the event, from the first commit, and `git log --reverse` shows it. We brought generic tooling (screenshot, smoke-test and deploy scripts), our server and domain, our own archive of public procurement notices built before the event, and public datasets, each declared with its source in DISCLOSURE.md.

## 15. Are you tracking founders or private people?

No: the radar's store and every page hold companies only, and a legal name shaped like a private person's name plus Holding, Invest, Capital, Consulting or Tmi is hidden unless the company has a record beyond its register entry (1 hidden on 16 Oct, start page footer). The radar does not fetch LinkedIn or anything behind a login, and LinkedIn appears only as a connector slot, not connected.

Check Sunday (for the chief, before the ZIP): the declared research file data/declared/ecosystem/blue_economy_fi.sqlite on main still has a `person` table with 87 named rows that no page reads. A judge who opens the repository can find them, which contradicts "companies only": drop that table or that file from the submission, or this answer must say it is there.
