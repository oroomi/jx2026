# Pilot plan: Redstone Blue x A'Pelago, eight weeks

**Goal.** By week 8 the radar reads public records for the Nordic and Baltic countries every week, its memo reflects your own
decisions, and a second backtest on your 2026 intake shows whether it finds companies before you do. Then you decide go or no-go.

**Starting point (17 Oct 2026).** Live at <https://jx.hankintaviikko.fi>, with register depth for Finland only. 7 of the 19 Nordic
Blue 2026 cohort companies have a Finnish business ID. From live records the radar would have shown 1 of 19 before January 2026, and that one is tuned
(Arctic Fry's industry code was added to the sector list on 17 Oct after we saw the miss; before that it was 0 of 19), yet all 7 Finnish ones have public records dated before then in today's store. The gap is
coverage (12 of the 19 are outside the Finnish register) and the sector rule (6 of the 7 Finnish ones are registered under codes the
sector list does not hold), as measured in [EVAL.md](EVAL.md).
Our strict rule caught 1 of 19 before they joined. The wide intake, which takes startup-shaped companies in before any sector test, would have held 4 of 19, 2 of them only after we tuned it on the misses. The four are Kilocode,
Sireness, Arctic Fry and Emission-Eye, and the claim is smaller than that sounds: Kilocode's intake date is a 2003 VAT registration,
so it is not an early find; Kilocode and Arctic Fry are in only because we added their code families after seeing them (in-sample);
Sireness enters on a declared-research record rather than a public one; and Emission-Eye, on a public start-up notice, ranks 132 of
1,176 among the 2025 registrations in its code family. The other 3 Finnish ones are registered outside the intake's code families.
Since then two things were added that nobody but you can check. The home list shows each company's criteria (impact, TRL, BRL, IRL, fit, verdict) with an Ocean Impact Assessment whose nine rungs are our own evidence ladder, because the Ocean Impact Navigator publishes areas and no levels; of the 59 companies on the home list, 3 reach a rung, 27 read "not yet evidenced" and 29 read "no public record". And `/match` ranks 191 counterparts against the startups with reasons in words and no total score; its weights are a hypothesis with no ground truth, and 17 of the 19 cohort companies and all 9 portfolio companies have at least one counterpart that passes its filters. Two things changed on the evening of 17 Oct after a judge's dry-run: the 28 cohort and portfolio companies on the home list read PORTFOLIO SUPPORT by rule (the radar does not tell you to put your own companies into an accelerator, and it says what the next pilot partner and grant would be), and an investor's view shows the early pipeline in words, "No startup on the radar is at due diligence yet; these are the closest". The other 31 rows on the home list are the radar's own finds, all WATCHLIST.

## What you get in 8 weeks

| Weeks | What we do | What you see at the end |
|---|---|---|
| 1-2 | **Nordic and Baltic registers.** The Norwegian (`brreg.py`) and Danish (`cvr.py`) adapters already exist, and so does the Estonian one (`estonia_register.py`). Today the Finland and Nordics store holds 1 Norwegian and 1 Danish record, because its sector file runs Finland only; the Baltic store, which runs Norway, holds 1,290 Norwegian and 82 Estonian records. The pilot adds: the Norwegian live window and the Estonian register in the Nordics store, a way past the Danish cohort lookups (the free CVR API has no search by date or industry code, and the open index needs credentials), and Sweden (Bolagsverket), which has no free API and is a connector slot today. Each starts with a check of the register's open-data terms; a register that needs an agreement is named as a dependency, not worked around. | Register facts and dated records for the 5 Danish, 2 Swedish and 1 Norwegian cohort companies: 8 of the 12 cohort companies outside the Finnish register. The other 4 (2 Spanish, 1 Bulgarian, and Edilm, which has no business ID we could find) stay open and are named on the page. |
| 3-4 | **Weekly refresh and re-checks.** The refresh runs weekly on the existing copy, check and swap path. Companies that the stitcher's thesis-evidence pass marked "unclear" (69 of the top 100 wide-intake companies on 17 Oct) are checked again as their websites appear. The stitcher batch is replayed on the live store with Internet Archive dates from the CDX index. | A dated "new since last week" list each week. Companies move from unclear to yes or no, each with the quoted page. |
| 5-6 | **Your deal notes as a private source**, in a connector slot: kept apart from public records, never on a public page and never in the repository. **The memo tuned with your decisions**: the decision table is data in the thesis file, so it changes without code. **The ocean-impact ladder and the matching weights tuned with your ratings**: both are data in the thesis file. | Memos that match your calls where the evidence supports them, and say why where they do not, printed for the 20 companies you judged. The nine rungs confirmed or replaced by your own definition, and the matching weights compared with your ratings of 20 matched pairs. |
| 7-8 | **Second backtest** on your full 2026 intake (applicants and deals, not only the published cohort) with your real entry dates. The code already replaces the reference date per company from `data/declared/cohort_entry_dates.csv` and labels the source. **Go/no-go meeting.** | Per company: first public signal against your entry date, blanks kept. A go or no-go against the criteria agreed in week 1. |

## What we need from you

- **Entry dates.** When each of the 19 cohort and 9 portfolio companies, and the rest of your 2026 intake, first entered your
  pipeline. You choose the event (application, first meeting, term sheet) and we label it. This turns "before January 2026" into
  "before you".
- **Your verdicts on 20 companies** that we pick from the feed and the radar's own finds (the 28 declared members read PORTFOLIO SUPPORT by rule, so they are not a test of the memo), in week 5: would you have met them, and why.
- **Your ratings of 20 matched pairs** (a startup and a counterpart `/match` lists for it), in week 5: useful, not useful, and why. This is the first ground truth the matching has.
- **Your view of the ocean-impact rungs**: which record you would require for each of the nine, so the ladder is yours and not ours.
- **One owner** on your side for 1 hour a week, and a 30-minute review at the end of weeks 2, 4, 6 and 8.
- **Optional, weeks 5-6:** an export of your deal notes, in any format.
- **Go/no-go criteria, agreed in week 1.** Our proposal: the share of your 2026 intake that live public records show before your
  entry date, against today's 1 of 19 (0 of 19 before the one tuned code), and how often the memo agrees with your verdict on the 20.

## What stays public-only

- The feed, the company pages, the backtest's live count and the API read public records only. Your verdicts and deal notes are
  shown only to your team, in their own labelled slot, the way LinkedIn and Dealroom appear as connector slots today.
- Your entry dates drive the second backtest. Whether that backtest is published or runs on a private copy is your call.
- Companies only. No private individuals, no scraping behind logins: the same rules as today. A missing record stays "not yet evidenced" or "no public record" in every phase; no phase turns a gap into a low score.

## First meeting

30 minutes. One ask: the entry dates for the 19 cohort and 9 portfolio companies.
