"""Business Finland adapter. Every workbook here is a TEST FIXTURE built inside the test (in tmp_path); the app never loads them."""
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from radar import db, emit
from radar.adapters import businessfinland as bf

REAL = Path(__file__).resolve().parent.parent / "data" / "declared" / "businessfinland.xlsx"


def build_fixture(path, headings, rows, pad=2):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["TEST FIXTURE, not Business Finland data"])
    for _ in range(pad - 1):
        ws.append([])
    ws.append(headings)
    for r in rows:
        ws.append(r)
    wb.save(path)


FI = ["Organisaatio", "Y-tunnus", "Päätöspäivä", "Myönnetty rahoitus", "Rahoitusmuoto", "Hanke"]
EN = ["Organisation", "Business ID", "Decision date", "Funding granted", "Funding type", "Project"]
ROWS = [
    ["Alfa Marine Oy", "1111111-1", datetime(2026, 5, 4), "1 234,50", "Innovaatiosetteli", "Hull sensor"],
    ["Beta Subsea Oy", None, "12.06.2026", 50000, "Tempo", "ROV"],
    ["Gamma Oy", "2222222-2", datetime(2026, 7, 1), 10, "Tempo", "New thing"],
    ["No Date Oy", "3333333-3", None, 100, "Tempo", "x"],
    ["Ghost Oy", None, datetime(2026, 7, 1), 5, "Tempo", "y"],
]
REAL_HEADS = ["Organisaatio", "Y-tunnus", "Myöntämisvuosi", "Avustus €", "Laina €", "EAKR-rahoitus €", "Tutkimusrahoitus €", "Yhteensä €"]


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1111111-1", name="Alfa Marine Oy", y_tunnus="1111111-1", source_url="https://example.org", group_tag="cohort")
    emit.upsert_company(c, company_key="name:beta", name="Beta Subsea", source_url="https://example.org", group_tag="portfolio")
    return c


def year_conn():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1111111-1", name="Fixture Oy", y_tunnus="1111111-1", source_url="https://example.org", group_tag="cohort")
    emit.upsert_company(c, company_key="name:nameonly", name="Namematch Fixture Oy", source_url="https://example.org", group_tag="portfolio")
    emit.upsert_company(c, company_key="2222222-2", name="Conflict Fixture Oy", y_tunnus="2222222-2", source_url="https://example.org", group_tag="cohort")
    emit.upsert_company(c, company_key="name:dup1", name="Twin Fixture Oy", source_url="https://example.org")
    emit.upsert_company(c, company_key="name:dup2", name="Twin Fixture Ab", source_url="https://example.org")
    return c


YROWS = [
    ["Fixture Oy", "1111111-1", 2020, 9536, 0, 0, 0, 9536],
    ["Fixture Oy", "1111111-1", 2020, 0, 5000, 0, 0, 5000],
    ["Fixture Oy", "1111111-1", 2021, 0, 0, 100, 200, 999],
    ["Namematch Fixture Oy", None, 2019, 700, 0, 0, 0, 700],
    ["Conflict Fixture Oy", "9999999-9", 2019, 1, 0, 0, 0, 1],
    ["Twin Fixture Oy", None, 2019, 1, 0, 0, 0, 1],
    ["Unmatched Org Oy", "8888888-8", 2019, 1, 0, 0, 0, 1],
]


@pytest.mark.parametrize("heads", [FI, EN])
def test_finnish_and_english_headings_day_path(tmp_path, conn, heads):
    p = tmp_path / "x.xlsx"
    build_fixture(p, heads, ROWS)
    r = bf.run(conn, {}, path=p)
    assert r["signals"] == 2 and r["skipped_no_date"] == 1 and r["unmatched"] == 2
    s = conn.execute("select * from signals where company_key='1111111-1'").fetchone()
    assert s["signal_type"] == "bf_funding" and s["date"] == "2026-05-04" and s["source_url"] == bf.DASHBOARD_URL
    assert s["amount_eur"] == 1234.5 and s["confidence"] == "high"
    assert s["detail"].startswith("Innovaatiosetteli: Hull sensor") and "manual" in s["detail"]
    m = conn.execute("select date_precision from signal_meta where signal_id=?", (s["id"],)).fetchone()
    assert m[0] == "day"


def test_name_match_is_medium(tmp_path, conn):
    p = tmp_path / "x.xlsx"
    build_fixture(p, FI, ROWS)
    bf.run(conn, {}, path=p)
    s = conn.execute("select * from signals where company_key='name:beta'").fetchone()
    assert s["confidence"] == "medium" and s["amount_eur"] == 50000.0 and s["date"] == "2026-06-12"


def test_real_heading_row_maps():
    m = bf.map_headings(REAL_HEADS)
    assert m == {"name": 0, "y_tunnus": 1, "year": 2, "amount_grant": 3, "amount_loan": 4, "amount_eakr": 5,
                 "amount_research": 6, "amount": 7}


def test_year_only_aggregation_types_and_matching(tmp_path):
    c = year_conn()
    p = tmp_path / "y.xlsx"
    build_fixture(p, REAL_HEADS, YROWS)
    r = bf.run(c, {}, path=p)
    assert r["rows_read"] == 7 and r["matched_ytunnus"] == 3 and r["matched_name"] == 1
    assert r["name_conflict"] == 1 and r["ambiguous_name"] == 1 and r["unmatched"] == 1 and r["total_mismatch"] == 1
    assert r["signals"] == 3 and r["companies"] == 2
    # no unmatched organisation was inserted
    assert c.execute("select count(*) from companies").fetchone()[0] == 5
    rows = {x["date"]: x for x in c.execute(
        "select s.*, m.date_precision, m.funding_types, m.rows_aggregated from signals s join signal_meta m on m.signal_id=s.id where company_key='1111111-1'")}
    a = rows["2020-01-01"]
    assert a["amount_eur"] == 14536 and a["date_precision"] == "year" and a["rows_aggregated"] == 2
    assert a["funding_types"] == "grant + loan" and a["confidence"] == "high"
    assert "granted in 2020 (year only; the export has no decision date)" in a["detail"] and "grant EUR 9 536" in a["detail"]
    b = rows["2021-01-01"]
    assert b["funding_types"] == "EAKR regional funding + research funding" and b["amount_eur"] == 999
    n = c.execute("select * from signals where company_key='name:nameonly'").fetchone()
    assert n["confidence"] == "medium" and n["date"] == "2019-01-01"
    assert c.execute("select count(*) from signals where company_key in ('2222222-2','name:dup1','name:dup2')").fetchone()[0] == 0


def test_idempotent_second_run(tmp_path):
    c = year_conn()
    p = tmp_path / "y.xlsx"
    build_fixture(p, REAL_HEADS, YROWS)
    bf.run(c, {}, path=p)
    bf.run(c, {}, path=p)
    assert c.execute("select count(*) from signals").fetchone()[0] == 3
    assert c.execute("select count(*) from signal_meta").fetchone()[0] == 3


def test_missing_year_and_date_columns_fail(tmp_path):
    p = tmp_path / "x.xlsx"
    build_fixture(p, ["Organisaatio", "Y-tunnus", "Yhteensä €"], [["a", "b", 1]])
    with pytest.raises(ValueError, match="Organisaatio"):
        bf.run(year_conn(), {}, path=p)


def test_absent_file_skips(conn, tmp_path):
    r = bf.run(conn, {}, path=tmp_path / "nope.xlsx")
    assert r == {"skipped": "no export file", "companies": 0, "signals": 0}


def test_unmappable_headings_fail_loudly(tmp_path, conn):
    p = tmp_path / "x.xlsx"
    build_fixture(p, ["Foo", "Bar"], [["a", "b"]])
    with pytest.raises(ValueError, match="Foo"):
        bf.run(conn, {}, path=p)


@pytest.mark.parametrize("raw,exp", [("1 234,50", 1234.5), ("1.234,50", 1234.5), ("12 000 €", 12000.0), (7, 7.0), ("n/a", None), (None, None)])
def test_amounts(raw, exp):
    assert bf.parse_amount(raw) == exp


@pytest.mark.skipif(not REAL.exists(), reason="real export not present")
def test_real_file_headings_and_row_count():
    c = db.connect(":memory:")
    r = bf.run(c, {}, path=REAL)
    assert r["rows_read"] == 59020  # 59 021 sheet rows including the heading row
    assert bf.map_headings(next(iter(bf._read_rows(REAL)))) == bf.map_headings(REAL_HEADS)
