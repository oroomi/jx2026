"""Business Finland funding decisions from the hand-made Qlik Excel export -> bf_funding signals.

The export has no per-row link, so every signal points at the dashboard page and says so in detail.
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
ROOT = Path(__file__).resolve().parent.parent.parent
EXPORT_PATH = ROOT / "data" / "declared" / "businessfinland.xlsx"
DASHBOARD_URL = "https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html"

# Add the real Qlik headings here. Compared after lowercasing, stripping diacritics and punctuation.
SYNONYMS = {
    "name": ["organisaatio", "organisation", "organization", "asiakas", "customer", "yritys", "company", "nimi", "name", "yrityksen nimi", "saaja", "recipient"],
    "y_tunnus": ["y-tunnus", "ytunnus", "y tunnus", "business id", "businessid", "business identity code", "company id", "yritys- ja yhteisotunnus", "y-tunnus / business id"],
    "date": ["paatospaiva", "paatospvm", "paatoksen paivamaara", "paatosaika", "decision date", "date of decision", "granted date", "myonnetty", "myontopaiva", "paivamaara", "date", "paatosvuosi"],
    "amount": ["myonnetty rahoitus", "myonnetty rahoitus eur", "myonnetty rahoitus ", "rahoitus", "rahoitus eur", "funding granted", "granted funding", "funding amount", "funding eur", "amount", "amount eur", "summa", "myonnetty summa"],
    "funding_type": ["rahoitusmuoto", "rahoituslaji", "tukimuoto", "funding type", "type of funding", "funding form", "instrument", "palvelu"],
    "project": ["hanke", "hankkeen nimi", "projekti", "projektin nimi", "project", "project title", "project name", "title"],
}
_REQUIRED = ("name", "date")
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


def find_header(rows: list[tuple]) -> tuple[int, dict[str, int]]:
    """Scan the first 15 rows; raise with the headings seen if none maps."""
    for idx, row in enumerate(rows[:15]):
        m = map_headings(row)
        if all(r in m for r in _REQUIRED):
            return idx, m
    seen = [[str(c) for c in r if c not in (None, "")] for r in rows[:15]]
    raise ValueError(
        "Business Finland export: cannot map the heading row (need at least an organisation and a decision date column). "
        f"Headings seen in the first rows: {seen}. Known synonyms are in SYNONYMS in radar/adapters/businessfinland.py"
    )



def run(conn, thesis=None, path: Path | str | None = None) -> dict:
    p = Path(path) if path else EXPORT_PATH
    if not p.exists():
        _log.warning("no export file: save the Business Finland Qlik Excel export as %s", p)
        return {"skipped": "no export file", "companies": 0, "signals": 0}
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    try:
        rows = [tuple(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()
    hi, cols = find_header(rows)

    by_y = {r["y_tunnus"]: r["company_key"] for r in conn.execute("SELECT company_key,y_tunnus FROM companies WHERE y_tunnus IS NOT NULL")}
    by_name: dict[str, str] = {}
    for r in conn.execute("SELECT company_key,name FROM companies"):
        by_name.setdefault(norm_name(r["name"]), r["company_key"])
    out = {"companies": 0, "signals": 0, "skipped": 0, "skipped_no_date": 0, "skipped_no_name": 0,
           "unmatched": 0, "matched_ytunnus": 0, "matched_name": 0, "inserted_companies": 0}
    touched: set[str] = set()

    def cell(row, field):
        i = cols.get(field)
        return row[i] if i is not None and i < len(row) else None

    for row in rows[hi + 1:]:
        if not any(c not in (None, "") for c in row):
            continue
        name = str(cell(row, "name") or "").strip()
        if not name:
            out["skipped"] += 1
            out["skipped_no_name"] += 1
            continue
        d = parse_date(cell(row, "date"))
        if d is None:
            out["skipped"] += 1
            out["skipped_no_date"] += 1
            continue
        y = norm_ytunnus(cell(row, "y_tunnus"))
        key, conf = None, "medium"
        if y and y in by_y:
            key, conf = by_y[y], "high"
            out["matched_ytunnus"] += 1
        elif norm_name(name) in by_name:
            key = by_name[norm_name(name)]
            out["matched_name"] += 1
        elif y:
            # unmatched with a Y-tunnus: in the feed; the keyword only says whether the name hints at the thesis
            emit.upsert_company(conn, company_key=y, name=name, y_tunnus=y, country="FI", group_tag="feed", source_url=DASHBOARD_URL)
            key = by_y[y] = y
            by_name.setdefault(norm_name(name), y)
            out["inserted_companies"] += 1
        else:
            out["unmatched"] += 1
            continue
        ftype = str(cell(row, "funding_type") or "").strip()
        proj = str(cell(row, "project") or "").strip()
        what = ": ".join(x for x in (ftype, proj) if x) or "funding decision"
        detail = f"{what} (Business Finland funding decision, row from the manual dashboard export; the export has no per-row link)"
        emit.emit_signal(conn, company_key=key, signal_type="bf_funding", date=d, source_url=DASHBOARD_URL, confidence=conf,
                         adapter=NAME, detail=detail, amount_eur=parse_amount(cell(row, "amount")))
        out["signals"] += 1
        touched.add(key)
    out["companies"] = len(touched)

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
