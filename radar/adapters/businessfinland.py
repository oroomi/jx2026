"""Business Finland funding from the hand-made Qlik Excel export -> bf_funding signals.

The export has no per-row link, so every signal points at the dashboard page and says so in detail.
The real export carries the grant YEAR, not a decision date: those signals are dated YYYY-01-01 and marked
date_precision 'year' in signal_meta (radar/schema/005_signal_meta.sql). Rows are aggregated to one signal per
(company, year). Only companies already in the database are matched (Y-tunnus first, then a unique folded name);
the other organisations in the export are never inserted. Runs in build phase 2 (enrichers).
Dayo saves the export as data/declared/businessfinland.xlsx. Headings are matched against SYNONYMS.
"""
from __future__ import annotations

import logging
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

from radar import emit

NAME = "businessfinland"
PHASE = 2
ROOT = Path(__file__).resolve().parent.parent.parent
EXPORT_PATH = ROOT / "data" / "declared" / "businessfinland.xlsx"
DASHBOARD_URL = "https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html"

# Add the real Qlik headings here. Compared after lowercasing, stripping diacritics and punctuation.
SYNONYMS = {
    "name": ["organisaatio", "organisation", "organization", "asiakas", "customer", "yritys", "company", "nimi", "name", "yrityksen nimi", "saaja", "recipient"],
    "y_tunnus": ["y-tunnus", "ytunnus", "y tunnus", "business id", "businessid", "business identity code", "company id", "yritys- ja yhteisotunnus", "y-tunnus / business id"],
    "date": ["paatospaiva", "paatospvm", "paatoksen paivamaara", "paatosaika", "decision date", "date of decision", "granted date", "myonnetty", "myontopaiva", "paivamaara", "date", "paatosvuosi"],
    "year": ["myontamisvuosi", "vuosi", "year"],
    "amount_grant": ["avustus"],
    "amount_loan": ["laina"],
    "amount_eakr": ["eakr-rahoitus", "eakr"],
    "amount_research": ["tutkimusrahoitus"],
    "amount": ["yhteensa", "total", "total eur", "myonnetty rahoitus", "myonnetty rahoitus eur", "myonnetty rahoitus ", "rahoitus", "rahoitus eur", "funding granted", "granted funding", "funding amount", "funding eur", "amount", "amount eur", "summa", "myonnetty summa"],
    "funding_type": ["rahoitusmuoto", "rahoituslaji", "tukimuoto", "funding type", "type of funding", "funding form", "instrument", "palvelu"],
    "project": ["hanke", "hankkeen nimi", "projekti", "projektin nimi", "project", "project title", "project name", "title"],
}
AMOUNT_COLUMNS = (("amount_grant", "grant"), ("amount_loan", "loan"),
                  ("amount_eakr", "EAKR regional funding"), ("amount_research", "research funding"))
_log = logging.getLogger(NAME)
_SUFFIX = re.compile(r"\b(oy|oyj|ab|abp|ltd|as|a/s|aps|gmbh|inc|ky|tmi|osakeyhtio)\b\.?")


def _fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9/ -]+", " ", s).replace("  ", " ").strip()


_SYN_FOLDED = {k: {_fold(v) for v in vs} for k, vs in SYNONYMS.items()}


def norm_name(s) -> str:
    s = _fold(s).replace("-", " ").replace("/", " ")
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", s)).strip()


def norm_ytunnus(v) -> str | None:
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) == 8:
        return f"{d[:7]}-{d[7]}"
    if len(d) == 7:  # leading zero lost by Excel numeric cell
        d = "0" + d
        return f"{d[:7]}-{d[7]}"
    return None


def parse_amount(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v).replace(" ", "").replace(" ", ""))
    if not re.search(r"\d", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(v) -> str | None:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
        if not m:
            return None
        d, mo, y = map(int, m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def map_headings(cells) -> dict[str, int]:
    """Column index per field for one row of cells (only the fields found)."""
    found: dict[str, int] = {}
    for i, c in enumerate(cells):
        f = _fold(c)
        if not f:
            continue
        for field, syns in _SYN_FOLDED.items():
            if field not in found and f in syns:
                found[field] = i
    return found


def _usable(m: dict[str, int]) -> bool:
    return "name" in m and ("date" in m or "year" in m)


def find_header(rows: list[tuple]) -> tuple[int, dict[str, int]]:
    """Scan the first 15 rows; raise with the headings seen if none maps."""
    for idx, row in enumerate(rows[:15]):
        m = map_headings(row)
        if _usable(m):
            return idx, m
    seen = [[str(c) for c in r if c not in (None, "")] for r in rows[:15]]
    raise ValueError(
        "Business Finland export: cannot map the heading row (need an organisation column and a decision date or grant year column). "
        f"Headings seen in the first rows: {seen}. Known synonyms are in SYNONYMS in radar/adapters/businessfinland.py"
    )


def parse_year(v) -> int | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        y = int(v) if float(v) == int(v) else None
    else:
        m = re.fullmatch(r"\s*(\d{4})(?:\.0)?\s*", str(v))
        y = int(m.group(1)) if m else None
    return y if y is not None and 1900 <= y <= 2100 else None


def _eur(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _read_rows(p: Path):
    """Yield (row_tuple) once through the first sheet, streaming."""
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    try:
        for r in wb.worksheets[0].iter_rows(values_only=True):
            yield tuple(r)
    finally:
        wb.close()


def run(conn, thesis=None, path: Path | str | None = None) -> dict:
    p = Path(path) if path else EXPORT_PATH
    if not p.exists():
        _log.warning("no export file: save the Business Finland Qlik Excel export as %s", p)
        return {"skipped": "no export file", "companies": 0, "signals": 0}
    it = _read_rows(p)
    head_rows: list[tuple] = []
    cols = None
    for row in it:
        head_rows.append(row)
        m = map_headings(row)
        if _usable(m):
            cols = m
            break
        if len(head_rows) >= 15:
            break
    if cols is None:
        find_header(head_rows)  # raises with the headings seen

    # lookups built once; no per-row query
    by_y: dict[str, str] = {}
    comp_y: dict[str, str | None] = {}
    by_name: dict[str, set] = {}
    for r in conn.execute("SELECT company_key,name,y_tunnus FROM companies"):
        comp_y[r["company_key"]] = r["y_tunnus"]
        if r["y_tunnus"]:
            by_y[r["y_tunnus"]] = r["company_key"]
        by_name.setdefault(norm_name(r["name"]), set()).add(r["company_key"])

    out = {"companies": 0, "signals": 0, "skipped": 0, "rows_read": 0, "skipped_no_date": 0, "skipped_no_name": 0,
           "unmatched": 0, "matched_ytunnus": 0, "matched_name": 0, "name_conflict": 0, "ambiguous_name": 0,
           "total_mismatch": 0, "year_min": None, "year_max": None}
    groups: dict[tuple, dict] = {}
    name_cache: dict[str, str] = {}

    def cell(row, field):
        i = cols.get(field)
        return row[i] if i is not None and i < len(row) else None

    for row in it:
        if not any(c not in (None, "") for c in row):
            continue
        out["rows_read"] += 1
        name = str(cell(row, "name") or "").strip()
        if not name:
            out["skipped"] += 1
            out["skipped_no_name"] += 1
            continue
        d = parse_date(cell(row, "date")) if "date" in cols else None
        precision = "day"
        if d is None:
            yr = parse_year(cell(row, "year")) if "year" in cols else None
            if yr is None:
                out["skipped"] += 1
                out["skipped_no_date"] += 1
                continue
            d, precision = f"{yr}-01-01", "year"
        parts = {lab: parse_amount(cell(row, f)) or 0.0 for f, lab in AMOUNT_COLUMNS if f in cols}
        total = parse_amount(cell(row, "amount"))
        if parts and total is not None and abs(total - sum(parts.values())) > 0.5:
            out["total_mismatch"] += 1
        y = norm_ytunnus(cell(row, "y_tunnus"))
        if y and y in by_y:
            key, conf = by_y[y], "high"
            out["matched_ytunnus"] += 1
        else:
            nn = name_cache.get(name)
            if nn is None:
                nn = name_cache[name] = norm_name(name)
            cands = by_name.get(nn, ()) if nn else ()
            if len(cands) == 1:
                key = next(iter(cands))
                if comp_y.get(key) and y and comp_y[key] != y:
                    out["name_conflict"] += 1
                    continue
                conf = "medium"
                out["matched_name"] += 1
            elif len(cands) > 1:
                out["ambiguous_name"] += 1
                continue
            else:
                out["unmatched"] += 1
                continue
        yr_n = int(d[:4])
        out["year_min"] = yr_n if out["year_min"] is None else min(out["year_min"], yr_n)
        out["year_max"] = yr_n if out["year_max"] is None else max(out["year_max"], yr_n)
        g = groups.setdefault((key, d), {"precision": precision, "conf": conf, "rows": 0, "total": None,
                                         "parts": {lab: 0.0 for _, lab in AMOUNT_COLUMNS}, "first": row})
        g["rows"] += 1
        if conf == "medium":
            g["conf"] = "medium"  # cautious: one name-matched row makes the aggregate medium
        if total is not None:
            g["total"] = (g["total"] or 0.0) + total
        for lab, v in parts.items():
            g["parts"][lab] += v

    for (key, d), g in groups.items():
        nonzero = [(lab, v) for lab, v in g["parts"].items() if v]
        ftypes = " + ".join(lab for lab, _ in nonzero) or None
        if g["precision"] == "year":
            amounts = ", ".join(f"{lab} EUR {_eur(v)}" for lab, v in nonzero) or "funding type and split not stated"
            detail = (f"Business Finland funding granted in {d[:4]} (year only; the export has no decision date): {amounts}. "
                      f"Row from the manual dashboard export, no per-row link.")
            if g["rows"] > 1:
                detail += f" Sum of {g['rows']} export rows for this year."
        else:
            ftype = str(cell(g["first"], "funding_type") or "").strip()
            proj = str(cell(g["first"], "project") or "").strip()
            what = ": ".join(x for x in (ftype, proj) if x) or "funding decision"
            detail = f"{what} (Business Finland funding decision, row from the manual dashboard export; the export has no per-row link)"
        g["detail"], g["ftypes"] = detail, ftypes
        emit.emit_signal(conn, company_key=key, signal_type="bf_funding", date=d, source_url=DASHBOARD_URL, confidence=g["conf"],
                         adapter=NAME, detail=detail, amount_eur=g["total"])
    ids = {(r["company_key"], r["date"]): r["id"] for r in conn.execute(
        "SELECT id, company_key, date FROM signals WHERE adapter = ? AND source_url = ?", (NAME, DASHBOARD_URL))}
    conn.executemany(
        "INSERT OR REPLACE INTO signal_meta (signal_id, date_precision, funding_types, rows_aggregated) VALUES (?,?,?,?)",
        [(ids[k], g["precision"], g["ftypes"], g["rows"]) for k, g in groups.items() if k in ids])
    out["signals"] = len(groups)
    out["companies"] = len({k for k, _ in groups})
    conn.commit()
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from radar import db
    try:
        from radar import thesis as _t
        th = _t.load()
    except ImportError:
        th = {}
    conn = db.connect()
    try:
        res = run(conn, th)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(res.get("skipped") and f"skipped: {res['skipped']}; save the export as {EXPORT_PATH}" or "", res)
