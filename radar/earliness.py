"""Earliness backtest: would the radar have found the cohort companies before the programme started?

Pure functions over a sqlite3.Connection and the thesis (read through radar.thesis). Nothing here writes data.
CLI: python3 -m radar.earliness [--thesis path]"""
from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path

from radar import labels
from radar import blueinvest, intake as intake_mod, store, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
# The cohort programme started in January 2026. This is the team's declaration, not a published entry date.
DEFAULT_REFERENCE_DATE = "2026-01-01"
ENTRY_DATES_CSV = ROOT / "data" / "declared" / "cohort_entry_dates.csv"  # columns: company, entry_date, source (absent tonight)
DAYS_PER_MONTH = 30.44
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _age_cut_years(th: dict) -> int:
    return int((th.get("geography") or {}).get("stage_max_company_age_years") or 5)


def reference(th: dict) -> tuple[str, str]:
    """(ISO date, where it comes from)."""
    val = (th.get("backtest") or {}).get("reference_date")
    if val:
        return str(val), "thesis key backtest.reference_date"
    return DEFAULT_REFERENCE_DATE, "default: the programme start month, declared by the team (not an entry date)"


def reference_label(ref: str) -> str:
    d = date.fromisoformat(ref)
    return f"{_MONTHS[d.month - 1]} {d.year}"


def rule_lines(th: dict) -> list[str]:
    ref, _ = reference(th)
    cut = _age_cut_years(th)
    types = ", ".join(labels.signal_label(t).lower() for t in th.get("feed_signal_types") or [])
    return [
        f"Population: companies in the declared cohort group. The number comes from the database.",
        f"Reference date: {ref} ({reference_label(ref)}, the programme start month, declared by the team). Individual pipeline entry dates are not public; "
        "a per-company entry date from the declared cohort entry dates list replaces the reference for that company and is labelled with its source.",
        f"A live public signal is a stored signal of the company whose type is one of the thesis feed signal types ({types}), with its stored date, "
        "and it counts only if the radar's own feed rule would have shown that company: the same test the feed uses (radar/store.py explain), "
        "applied to the company's registered facts and to the signals dated no later than that signal. That means the industry code is on the thesis list, "
        "or a thesis word is in the registered line of business, or a thesis word is in the source's own text, or a thesis word in the legal name is backed by a record from a different source family (PRH register entries, notices and tax registers are one family). "
        "A signal that fails the test is listed in muted text as outside the thesis rule and is not counted.",
        f"A register entry also counts only if the company was registered no more than {cut} years before the reference date: the radar flags new registrations, "
        f"so the registration of an older company is not a discovery signal.",
        "Declared research events (a signal whose detail says declared research, or a pilot, first hire, certification, programme entry, exhibitor, award, funding round or product launch) "
        "count only with medium or high confidence and form a separate group, never mixed into the live count.",
        "Year-only dates (Business Finland funding) count as 1 January of that year and are labelled year only.",
        f"First counted signal = the earliest counted signal date. Months = days between that date and the reference date, divided by {DAYS_PER_MONTH}, rounded down, shown as N months before or N months after.",
        "Found earlier by live public records = a live counted signal strictly before the reference date. Found earlier only by declared research = no such live signal, but a counted declared research event strictly before it. "
        "Found later = counted signals exist but none is before the reference date (a year-only date in the reference year is later or same). No public signal = no counted signal at all, shown blank. "
        "The four groups always add up to the cohort size.",
        "Undated profile evidence (a BlueInvest profile with a TRL and no listing date) is shown as a note and never moves a company between groups.",
        "AI stitcher events (proposed by an LLM, checked by code) never count in the four groups. They are counted on a separate line, only when the event "
        "passed both code checks, is of a type the radar emits, and the Internet Archive captured its page before the company's reference date (public since, not the event date).",
        "Confidence is printed beside the signal that set the first date. A low confidence keyword match is shown but is never proof.",
    ]


def rule_text(th: dict) -> str:
    return "\n".join(rule_lines(th))


def _minus_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 February
        return d.replace(year=d.year - years, day=28)


def _entry_dates(path) -> dict[str, tuple[str, str]]:
    """casefolded company name or key -> (entry_date, source). Empty when the file is absent."""
    p = Path(path)
    if not p.is_file():
        return {}
    out = {}
    with p.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            who, d = (r.get("company") or "").strip(), (r.get("entry_date") or "").strip()
            if who and d:
                try:
                    date.fromisoformat(d)
                except ValueError:
                    continue
                out[who.casefold()] = (d, (r.get("source") or "").strip())
    return out


def _months(a: date, b: date) -> int:
    """Whole months between two dates (30.44 days each), rounded down, of the absolute distance."""
    return int(abs((a - b).days) / DAYS_PER_MONTH)


def _signals(conn, key: str) -> list[dict]:
    rows = [dict(r) for r in conn.execute(
        "SELECT id AS signal_id, signal_type, date, source_url, confidence, adapter, detail FROM signals WHERE company_key=? ORDER BY date, id", (key,))]
    store.with_precision(conn, rows)
    return rows


def _other(s: dict, counted: bool, reason: str | None) -> dict:
    return {"date": s["date"], "date_label": s["date_label"], "year_only": s["date_precision"] == "year", "type": s["signal_type"],
            "label": labels.signal_label(s["signal_type"]), "source_url": s["source_url"],
            "confidence": s["confidence"], "source_label": store.evidence(s)["label"], "adapter": s["adapter"], "counted": counted, "reason": reason}


_CONF = {"high": 0, "medium": 1, "low": 2}
# Why a stored type is listed but never counted. Shown on /backtest beside the dated signal, so a judge sees the reason.
NOT_COUNTED = {
    "board_change": "routine filing, not evidence of traction or discovery",
    "capital_loss": "a negative record (loss of share capital), shown but never counted as a find",
    "sales_ended": "a negative record, shown but never counted as a find",
    "employer_ended": "a negative record, shown but never counted as a find",
    "website_first_seen": "a website existing is not traction, and the archive date is only an upper bound",
}
STITCHER = "stitcher"  # AI stitcher events never count in the four groups; archived_before() counts them apart
STITCHER_NOT_COUNTED = "found by the AI stitcher: never in the live count, counted apart by the date its page was first archived"
RESEARCH_TYPES = ("pilot_named", "first_hire", "certification", "programme_entry", "exhibitor", "award", "funding_round", "product_launch")
GROUP_ORDER = ("earlier", "declared", "later", "none")


def is_research(s: dict) -> bool:
    """Declared research = anything the ecosystem adapter imported, or a research-type signal whose detail says so. A live register
    signal that shares a type name (tax_registers first_hire) stays live."""
    if s.get("adapter") == "ecosystem" or "declared research" in (s.get("detail") or "").casefold():
        return True
    return s["signal_type"] in RESEARCH_TYPES and s.get("adapter") != "tax_registers"


def headline(res: dict) -> str:
    """The verdict sentence, built only from the computed counts."""
    return (f"Of {res['total']} cohort companies, the radar, applying its own feed rule, would have shown {res['earlier']} before {res['reference_label']} "
            f"using live public records. Declared research alone finds {res['declared']} earlier; {res['later']} are found only after; "
            f"{res['none']} have no public signal.")


def backtest(conn: sqlite3.Connection, th: dict, *, entry_dates_path=ENTRY_DATES_CSV) -> dict:
    ref_iso, ref_source = reference(th)
    cut = _age_cut_years(th)
    types = set(th.get("feed_signal_types") or [])
    group = (th.get("backtest") or {}).get("cohort_group") or "cohort"
    entries = _entry_dates(entry_dates_path)
    cohort = conn.execute("SELECT company_key, name, y_tunnus, country, industry_code, industry_desc, founded FROM companies WHERE group_tag=? ORDER BY name", (group,)).fetchall()
    rows = []
    for c in cohort:
        key = c["company_key"]
        eff_iso, eff_source = ref_iso, ref_source
        hit = entries.get(c["name"].casefold()) or entries.get(key.casefold())
        if hit:
            eff_iso = hit[0]
            eff_source = f"data/declared/cohort_entry_dates.csv: {hit[1] or 'no source stated'}"
        eff = date.fromisoformat(eff_iso)
        cutoff = _minus_years(eff, cut)
        sigs = _signals(conn, key)
        for s in sigs:
            s["id"], s["company_key"] = s["signal_id"], key
        texts = store.source_texts(conn, sigs)
        company = {"name": c["name"], "industry_code": c["industry_code"], "industry_desc": c["industry_desc"]}
        counted, others = [], []
        for s in sigs:
            d = f"{s['date'][:4]}-01-01" if s["date_precision"] == "year" else s["date"]
            label = labels.signal_label(s["signal_type"])
            if s.get("adapter") == STITCHER:
                others.append(_other(s, False, STITCHER_NOT_COUNTED))
                continue
            if is_research(s):
                if s["confidence"] in ("medium", "high"):
                    o = _other(s, True, None)
                    o.update(counted_date=d, research=True, rule="declared research event with " + s["confidence"] + " confidence")
                    counted.append(o)
                else:
                    others.append(_other(s, False, f"declared research with {s['confidence']} confidence, not counted"))
            elif s["signal_type"] not in types:
                others.append(_other(s, False, f"{label.lower()} {s['date_label']}: {NOT_COUNTED.get(s['signal_type'], 'not a counted signal type in this thesis')}"))
            elif s["signal_type"] == "register_entry" and date.fromisoformat(d) < cutoff:
                others.append(_other(s, False, f"registered {s['date']}, older than the radar's {cut}-year cut, not counted"))
            else:
                earlier_sigs = [o for o in sigs if o["id"] != s["id"] and o["date"] <= s["date"]]
                ex = store.explain({**company, **s}, earlier_sigs, th, texts)
                if ex["strength"] == "strong":
                    o = _other(s, True, None)
                    o.update(counted_date=d, research=False, rule=ex["why"].removeprefix("Why: "))
                    counted.append(o)
                else:
                    what = f"registered {s['date']}" if s["signal_type"] == "register_entry" else f"{label.lower()} {s['date_label']}"
                    others.append(_other(s, False, f"{what}, outside the thesis rule"))
        counted.sort(key=lambda o: (o["counted_date"], _CONF.get(o["confidence"], 3), o["type"]))
        live = [o for o in counted if not o["research"]]
        research = [o for o in counted if o["research"]]
        fd_of = lambda o: date.fromisoformat(o["counted_date"])  # noqa: E731
        if live and fd_of(live[0]) < eff:
            grp, first = "earlier", live[0]
        elif research and fd_of(research[0]) < eff:
            grp, first = "declared", research[0]
        elif counted:
            grp, first = "later", counted[0]
        else:
            grp, first = "none", None
        months, timing = None, None
        rest = [o for o in counted if o is not first]
        if first:
            n = _months(eff, fd_of(first))
            if fd_of(first) < eff:
                months, timing = n, f"{n} months before"
            else:
                months = -n
                timing = f"{n} months after" + (" (later or same, year only)" if first["year_only"] and fd_of(first).year == eff.year else "")
            first = dict(first, date=first["counted_date"])
        others = rest + others
        others.sort(key=lambda o: o["date"])
        notes = []
        prof = blueinvest.profile_for(conn, key)
        if prof and not prof.get("listed_date"):
            trl = prof.get("trl")
            notes.append({"text": "listed in the BlueInvest pipeline, " + (f"TRL {trl}" if trl is not None else "no TRL stated") + ", no date stated, not counted",
                          "source_url": prof.get("url")})
        live_dates = sorted(o["counted_date"] for o in live)
        wide = intake_mod.cohort_row(conn, th, c, eff_iso, live_dates[0] if live_dates else None)
        rows.append({"company_key": key, "name": c["name"], "country": c["country"], "first_signal": first, "months": months, "timing": timing, "intake": wide,
                     "group": grp, "others": others, "notes": notes, "reference_date": eff_iso, "reference_source": eff_source,
                     "reference_from_csv": bool(hit)})
    rows.sort(key=lambda r: (r["months"] is None, -(r["months"] or 0), r["name"].casefold()))
    tot = {g: sum(1 for r in rows if r["group"] == g) for g in GROUP_ORDER}
    res = {"rows": rows, "earlier": tot["earlier"], "declared": tot["declared"], "later": tot["later"], "none": tot["none"], "total": len(rows),
           "reference_date": ref_iso, "reference_source": ref_source, "reference_label": reference_label(ref_iso), "age_cut_years": cut}
    res["headline"] = headline(res)
    from radar.adapters import stitcher
    res["stitcher"] = stitcher.archived_before(conn, [(r["company_key"], r["reference_date"]) for r in rows])
    names = {r["company_key"]: r["name"] for r in rows}
    for r in res["stitcher"]["rows"]:
        r["name"] = names.get(r["company_key"], r["company_key"])
    if intake_mod.settings(th) is not None:
        s = intake_mod.summary([r["intake"] for r in rows], [r["name"] for r in rows])
        res["intake"] = {**s, "headline": intake_mod.headline(s), "rule": intake_mod.rule_text(th), "note": intake_mod.tuning_note(th)}
    else:
        res["intake"] = None
    return res


def not_connected(conn, th: dict) -> list[str]:
    """Feed signal types with no stored signal at all in this database, named from the data (not a typed list)."""
    out = []
    for t in th.get("feed_signal_types") or []:
        n = conn.execute("SELECT COUNT(*) FROM signals WHERE signal_type=?", (t,)).fetchone()[0]
        if n == 0:
            out.append(t)
    return out


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m radar.earliness")
    ap.add_argument("--thesis", default=None)
    a = ap.parse_args(argv)
    th = thesis_mod.load(a.thesis)
    conn = store.open_db(thesis=th)
    if conn is None:
        print(store.empty_state_text(th))
        return 0
    try:
        res = backtest(conn, th)
    finally:
        conn.close()
    print(f"reference {res['reference_date']} ({res['reference_source']})")
    for r in res["rows"]:
        f = r["first_signal"]
        print(f"{r['name']:34} {r['group']:8} {r['timing'] or 'no public signal':24} "
              + (f"{f['date']} {f['type']} ({f['confidence']}) {f['source_url']}" if f else ""))
    print(f"earlier {res['earlier']}, declared {res['declared']}, later {res['later']}, none {res['none']}, total {res['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
