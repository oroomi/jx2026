"""Earliness backtest: would the radar have found the cohort companies before the programme started?

Pure functions over a sqlite3.Connection and the thesis (read through radar.thesis). Nothing here writes data.
CLI: python3 -m radar.earliness [--thesis path]"""
from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path

from radar import blueinvest, store, thesis as thesis_mod

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
    types = ", ".join(th.get("feed_signal_types") or [])
    return [
        f"Population: companies in the cohort group (group_tag cohort). The number comes from the database.",
        f"Reference date: {ref} ({reference_label(ref)}, the programme start month, declared by the team). Individual pipeline entry dates are not public; "
        "a per-company entry date from data/declared/cohort_entry_dates.csv replaces the reference for that company and is labelled with its source.",
        f"A public signal is any stored signal of the company whose type is one of the thesis feed signal types ({types}), with its stored date.",
        f"A register entry counts only if the company was registered no more than {cut} years before the reference date: the radar flags new registrations, "
        f"so the registration of an older company is not a discovery signal. It is still listed, in muted text, as not counted.",
        "Year-only dates (Business Finland funding) count as 1 January of that year and are labelled year only.",
        f"First public signal = the earliest counted signal date. Months = days between that date and the reference date, divided by {DAYS_PER_MONTH}, rounded down, shown as N months before or N months after.",
        "Found earlier = first counted signal strictly before the reference date. Found later = first counted signal on or after the reference date "
        "(a year-only date in the reference year is later or same). No public signal = no counted signal at all, shown blank. The three groups always add up to the cohort size.",
        "Undated profile evidence (a BlueInvest profile with a TRL and no listing date) is shown as a note and never moves a company between groups.",
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
            "label": store.TYPE_LABELS.get(s["signal_type"], s["signal_type"]), "source_url": s["source_url"],
            "confidence": s["confidence"], "source_label": store.evidence(s)["label"], "adapter": s["adapter"], "counted": counted, "reason": reason}


_CONF = {"high": 0, "medium": 1, "low": 2}


def backtest(conn: sqlite3.Connection, th: dict, *, entry_dates_path=ENTRY_DATES_CSV) -> dict:
    ref_iso, ref_source = reference(th)
    cut = _age_cut_years(th)
    types = set(th.get("feed_signal_types") or [])
    group = (th.get("backtest") or {}).get("cohort_group") or "cohort"
    entries = _entry_dates(entry_dates_path)
    cohort = conn.execute("SELECT company_key, name, country FROM companies WHERE group_tag=? ORDER BY name", (group,)).fetchall()
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
        counted, others = [], []
        for s in _signals(conn, key):
            d = f"{s['date'][:4]}-01-01" if s["date_precision"] == "year" else s["date"]
            if s["signal_type"] not in types:
                others.append(_other(s, False, f"type {s['signal_type']} is not a feed signal type in this thesis"))
            elif s["signal_type"] == "register_entry" and date.fromisoformat(d) < cutoff:
                others.append(_other(s, False, f"registered {s['date']}, older than the radar's {cut}-year cut, not counted"))
            else:
                o = _other(s, True, None)
                o["counted_date"] = d
                counted.append(o)
        counted.sort(key=lambda o: (o["counted_date"], _CONF.get(o["confidence"], 3), o["type"]))
        first = counted[0] if counted else None
        months, grp, timing = None, "none", None
        if first:
            fd = date.fromisoformat(first["counted_date"])
            n = _months(eff, fd)
            if fd < eff:
                grp, months, timing = "earlier", n, f"{n} months before"
            else:
                grp, months = "later", -n
                timing = f"{n} months after" + (" (later or same, year only)" if first["year_only"] and fd.year == eff.year else "")
            first = dict(first, date=first["counted_date"])
        others = counted[1:] + others
        others.sort(key=lambda o: o["date"])
        notes = []
        prof = blueinvest.profile_for(conn, key)
        if prof and not prof.get("listed_date"):
            trl = prof.get("trl")
            notes.append({"text": "listed in the BlueInvest pipeline, " + (f"TRL {trl}" if trl is not None else "no TRL stated") + ", no date stated, not counted",
                          "source_url": prof.get("url")})
        rows.append({"company_key": key, "name": c["name"], "country": c["country"], "first_signal": first, "months": months, "timing": timing,
                     "group": grp, "others": others, "notes": notes, "reference_date": eff_iso, "reference_source": eff_source,
                     "reference_from_csv": bool(hit)})
    rows.sort(key=lambda r: (r["months"] is None, -(r["months"] or 0), r["name"].casefold()))
    tot = {g: sum(1 for r in rows if r["group"] == g) for g in ("earlier", "later", "none")}
    firsts = [r["first_signal"] for r in rows if r["first_signal"]]
    from_declared = sum(1 for f in firsts if f["adapter"] == "ecosystem")
    return {"rows": rows, "from_declared": from_declared, "from_live": len(firsts) - from_declared, "earlier": tot["earlier"], "later": tot["later"], "none": tot["none"], "total": len(rows),
            "reference_date": ref_iso, "reference_source": ref_source, "reference_label": reference_label(ref_iso), "age_cut_years": cut}


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
    print(f"earlier {res['earlier']}, later {res['later']}, none {res['none']}, total {res['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
