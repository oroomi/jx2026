"""Provenance (jx40): the change log of rule-driven transformations, each citing the PROJECT_RULES.md id behind it.

Two kinds of entry, in the `provenance` table (radar/schema/061_provenance.sql):
  decision  a dated decision already taken in the repo (D1 to D20 in PROJECT_RULES.md, carried over from ASSUMPTIONS.md),
            with the commit, and the records affected exactly as a commit message or a judged document states them.
            Where no count is written anywhere, `affected` says so; nothing is estimated.
  run       a tool that applied rules to a store appends one entry per run (radar/candidates.py build cites A1).

  python3 -m radar.provenance log                    # the seeded decisions, oldest first (no store needed)
  python3 -m radar.provenance log --rule D12
  RADAR_DB=/tmp/copy.sqlite python3 -m radar.provenance seed    # write the decisions into a store copy, then print its log
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

from radar import emit
from radar import thesis as thesis_mod

SCHEMA = Path(__file__).resolve().parent / "schema" / "061_provenance.sql"
RULE_ID = re.compile(r"^[AD]\d+$")

# The decisions already in the repo. Times are commit times (UTC) from git log; `affected` quotes the source named in
# `evidence`. Order follows PROJECT_RULES.md section D.
SEED = (
    dict(rule_id="D1", at="2026-10-16T20:23:00Z", commit_sha="eb1c749", scope="readiness, every company page",
         action="readiness levels use the sponsors' frameworks: Aalto TRL 1-9, KTH BRL 1-9, Ocean Impact Navigator category, ten investment dimensions",
         affected="every company's readiness lines; no count stated", evidence="TASKS.md amendment 20:50Z; 98c4e1e; afaa4fb"),
    dict(rule_id="D2", at="2026-10-16T21:34:00Z", commit_sha="11970db", scope="feed, both theses",
         action="feed precision: own-text reasons read only the source's stored text, whole-word or 5+ character prefix matching with a stop list, "
                "name-only matches weak, person-shaped holding names hidden",
         affected="blue main 39 to 31, weak 55 to 62 (1 hidden); health main 37 to 34, weak 23 to 26",
         evidence="commit 11970db message; reasons VERIFY_night2.md D-N1 (CORDIS annotation read as text, 11 rows) and D-N7 (person-shaped names)"),
    dict(rule_id="D3", at="2026-10-16T22:16:00Z", commit_sha="64c39bb", scope="backtest",
         action="the backtest counts a signal only if the feed rule would have shown the company",
         affected="snapshot earlier 5, later 1, none 13 became live 0, declared 0, later 1, none 18",
         evidence="tasks/cloud/backtest_fix.md; 0ef14d2 for the 1, 12, 5, 1 run with tax registers and ecosystem"),
    dict(rule_id="D4", at="2026-10-16T22:46:00Z", commit_sha="0ef14d2", scope="feed and backtest signal types",
         action="counted startup_notice, equity_event, research_output, website_milestone, eu_grant; refused board_change, capital_loss, "
                "sales_ended, employer_ended, website_first_seen",
         affected="no backtest group moved; the cohort's new-type rows were 4 startup_notice and 15 board_change",
         evidence="EARLINESS_AUDIT.md section 2; commit 0ef14d2"),
    dict(rule_id="D5", at="2026-10-16T22:58:00Z", commit_sha="baad087", scope="config/thesis.yaml and thesis_baltic_blue.yaml industry_codes",
         action="72190 removed from the thesis codes; 72100 not added",
         affected="PRH returned 0 companies under 72190 and 30 under 72100 for registrations 2026-07-18 to 2026-10-16 (an upper bound); "
                  "adding 72100 would move Sireness Oy 3568392-1 to found earlier (live 0/0/1/18 to 1/0/1/17); no count for the removal itself",
         evidence="EARLINESS_AUDIT.md sections 4 and 5; commit 0ef14d2 (proposal, not applied)"),
    dict(rule_id="D6", at="2026-10-16T22:58:00Z", commit_sha="baad087", scope="Finnish thesis code lists",
         action="TOL 2025 marine codes: 03211 and 03111 replaced by 03210 (marine aquaculture) and 03110 (marine fishing); the Baltic file "
                "keeps 03211 and 03111 as Estonian EMTAK codes",
         affected="12 earliness and backtest tests moved from 03211 to 03210; no company count stated",
         evidence="commits baad087, 5a114ac, 93798f5"),
    dict(rule_id="D7", at="2026-10-16T23:15:00Z", commit_sha="f78f668", scope="feed, third tier",
         action="wide intake: limited companies and cooperatives in the intake code families with one startup signal",
         affected="store copy: 50,480 companies examined, 19,027 passed the form and code test, 15,584 new, 41,220 signals; "
                  "2 of 19 cohort companies entered before cohort entry",
         evidence="commit 93798f5; tasks/cloud/jx28_wide_intake.md"),
    dict(rule_id="D8", at="2026-10-16T23:19:00Z", commit_sha="17f5cee", scope="AI stitcher",
         action="stitcher limits: programme_entry, award, funding_round emittable; other kept types stay in stitch_log; a second code pass "
                "re-fetches each page; stitcher events never enter the four backtest groups",
         affected="batch of 17 Oct 00:18Z: 54 companies, 175 proposed, 168 kept, 128 confirmed, 29 emitted, 99 logged only",
         evidence="EVAL.md; METHOD.md; commits 17f5cee, 341ea51, fd4c16b"),
    dict(rule_id="D9", at="2026-10-16T23:28:00Z", commit_sha="0b3c241", scope="memo, every company page",
         action="the team's decision table in passes, unknown never Low",
         affected="every company page; no count stated", evidence="TASKS.md amendment 23:40Z; commits 0b3c241, a2b8eb6"),
    dict(rule_id="D10", at="2026-10-16T23:35:00Z", commit_sha="a2b8eb6", scope="memo thesis fit",
         action="declared cohort and portfolio members get at least Medium thesis fit",
         affected="the 19 cohort and 9 portfolio companies (28)", evidence="commit a2b8eb6; ce502ed"),
    dict(rule_id="D11", at="2026-10-17T01:18:00Z", commit_sha="0cbe141", scope="intake code_prefixes, thesis.yaml and baltic",
         action="intake families 582 (software publishing) and 03 (fishing and aquaculture) added and labelled in-sample (tuning_note)",
         affected="intake before cohort entry 2 of 19 (store copy) to 4 of 19 on the live store (Kilocode, Sireness, Arctic Fry, "
                  "Emission-Eye; median rank 3 of 60); 16,385 prh_intake signals live",
         evidence="EVAL.md; README.md; config/thesis.yaml tuning_note"),
    dict(rule_id="D12", at="2026-10-17T02:30:00Z", commit_sha="ada70c5", scope="feed corroboration",
         action="a thesis word in the legal name is corroborated only by a record from a different source family; the PRH register, "
                "notices, intake, recent registrations and tax registers are one family",
         affected="feed 123 companies (70 main, 53 weak) to 122 (36 main, 86 weak), measured together with the data swap (6ac05bc); "
                  "backtest live headline 1 of 19 to 0 of 19; ARCHITECTURE.md: 40 of the 70 main-list companies carried the corroborated-name "
                  "reason before, 0 of the 36 after",
         evidence="README.md; EVAL.md; JUDGE_REVIEW2.md item 2 (33 of 57 main rows); commits ada70c5, 6ac05bc, 7667e78"),
    dict(rule_id="D13", at="2026-10-17T02:31:00Z", commit_sha="8944ff2", scope="feed and intake",
         action="listed companies (Oyj, Abp among the last two words of the legal name) left out",
         affected="the live count is printed in the feed footer and on /method#left-out; the repo states no fixed number",
         evidence="JUDGE_REVIEW2.md item 9; radar/store.py LISTED_FORM_WORDS"),
    dict(rule_id="D14", at="2026-10-17T02:31:00Z", commit_sha="8944ff2", scope="health thesis feed and intake",
         action="human-health practice (TOL 86) left out of the health thesis; 86900 off its code list",
         affected="health feed now 30 companies, 1 main, 29 weak (measured with the data swap and D12; no count for the exclusion alone)",
         evidence="README.md; config/thesis_health_turku.yaml feed_exclude_code_prefixes; d7df036"),
    dict(rule_id="D15", at="2026-10-17T02:31:00Z", commit_sha="8a88193", scope="Norwegian register adapter",
         action="Norwegian live-window rows enter a thesis only when NO is one of its countries (the Baltic thesis); cohort matches enter every thesis",
         affected="1,289 Norwegian limited companies fetched for 17 Oct 2025 to 17 Oct 2026 (948 by NACE prefix, low; 341 by name word, medium); "
                  "TuniSea found as TUNISEA AS 936277241",
         evidence="commits d673607, 8a88193, efd042d; radar/adapters/brreg.py comment at the import"),
    dict(rule_id="D16", at="2026-10-17T02:38:00Z", commit_sha="7413623", scope="memo, thesis.yaml",
         action="memo bands read the page levels; pass 3 fallback c1 GRANT SUPPORT, c2 ACCELERATOR, c3 DUE DILIGENCE for High fit with unknown impact",
         affected="on the live copy 911 companies would read ACCELERATOR before the gate (D18)", evidence="commits 7413623, 79ac042"),
    dict(rule_id="D17", at="2026-10-16T23:04:00Z", commit_sha="9da6080", scope="AI stitcher output",
         action="person names redacted in stitcher quotes, logged queries and the company page block",
         affected="the stitcher block on every company page; no count of redacted strings stated", evidence="commits 9da6080, 431df23, faf5a9b"),
    dict(rule_id="D18", at="2026-10-17T03:09:00Z", commit_sha="79ac042", scope="memo fallback gate",
         action="the fallback applies only when the High fit rests on more than an industry code (declared member, own text, "
                "corroborated name word; from 0c19d90 also the registered line of business)",
         affected="ACCELERATOR 911 to 3 on the live copy, then 245 on the live store", evidence="commits 79ac042, 0c19d90"),
    dict(rule_id="D19", at="2026-10-17T02:00:00Z", commit_sha="7667e78", scope="judged documents and demo path",
         action="demo examples Viva Jets Oy 2962040-6 and Arctic Fry Oy 3166759-6 replace Kelluu",
         affected="README, DEMO_SCRIPT, MODULES, three templates and tests/test_ease.py", evidence="commits 7667e78, 1754936; DEMO_SCRIPT.md"),
    dict(rule_id="D20", at="2026-10-17T06:15:00Z", commit_sha="011e7ed", scope="feed, code_alone_weak",
         action="a consultancy or research industry code alone (711, 712, 721; health 702, 721) is a weak match",
         affected="live-store copy main 36 to 30, weak 86 to 92; six companies moved", evidence="commit 011e7ed"),
)


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


def record(conn: sqlite3.Connection, *, rule_id: str, kind: str, action: str, at: str | None = None, scope: str | None = None,
           affected: str | None = None, commit_sha: str | None = None, evidence: str | None = None) -> bool:
    """Append one entry. Returns True when new (the same rule, kind, time and action are recorded once)."""
    if not RULE_ID.match(rule_id or ""):
        raise ValueError(f"rule_id must be A<n> or D<n>, got {rule_id!r}")
    apply_schema(conn)
    cur = conn.execute(
        """INSERT OR IGNORE INTO provenance (at, rule_id, kind, action, scope, affected, commit_sha, evidence, recorded_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (at or emit.now_utc(), rule_id, kind, action, scope, affected, commit_sha, evidence, emit.now_utc()))
    conn.commit()
    return cur.rowcount == 1


def seed(conn: sqlite3.Connection) -> int:
    return sum(record(conn, kind="decision", **d) for d in SEED)


def entries(conn: sqlite3.Connection | None = None, rule: str | None = None) -> list[dict]:
    """The log, oldest first: from the store when it has the table, else the built-in decisions."""
    rows: list[dict]
    if conn is not None and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provenance'").fetchone():
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM provenance ORDER BY at, id")]
    else:
        rows = sorted(({"kind": "decision", **d} for d in SEED), key=lambda d: d["at"])
    return [r for r in rows if not rule or r["rule_id"] == rule]


def render(rows: list[dict]) -> str:
    out = []
    for r in rows:
        out.append(f"{r['at']}  {r['rule_id']:<4} {r['kind']:<8} {r['action']}")
        for label, key in (("scope", "scope"), ("affected", "affected"), ("commit", "commit_sha"), ("evidence", "evidence")):
            if r.get(key):
                out.append(f"{'':28}{label}: {r[key]}")
    out.append(f"{len(rows)} entries")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.provenance", description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["log", "seed"])
    ap.add_argument("--db", type=Path, help="store copy (default RADAR_DB, else the thesis store); log reads it when it has the table")
    ap.add_argument("--rule", help="only this A or D id")
    ap.add_argument("--allow-live", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    path = a.db or thesis_mod.db_path(thesis_mod.load())
    conn = None
    if Path(path).is_file():
        if a.cmd == "seed":
            from radar.candidates import _guard
            _guard(Path(path), a.allow_live)
            conn = sqlite3.connect(str(path))
            n = seed(conn)
            print(f"seeded {n} new decision entries into {path}")
        else:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    elif a.cmd == "seed":
        print(f"no store at {path}", file=sys.stderr)
        return 2
    print(render(entries(conn, a.rule)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
