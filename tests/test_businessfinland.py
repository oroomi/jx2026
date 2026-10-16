"""Business Finland adapter. The xlsx files here are TEST FIXTURES built in this file; the app never loads them."""
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from radar import db, emit
from radar.adapters import businessfinland as bf

FIXTURE = Path(__file__).parent / "fixtures" / "bf_export_test_fixture.xlsx"


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


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1111111-1", name="Alfa Marine Oy", y_tunnus="1111111-1", source_url="https://example.org", group_tag="cohort")
    emit.upsert_company(c, company_key="name:beta", name="Beta Subsea", source_url="https://example.org", group_tag="portfolio")
    return c


@pytest.mark.parametrize("heads", [FI, EN])
def test_finnish_and_english_headings(tmp_path, conn, heads):
    p = tmp_path / "x.xlsx"
    build_fixture(p, heads, ROWS)
    r = bf.run(conn, {}, path=p)
    assert r["signals"] == 3 and r["skipped_no_date"] == 1 and r["unmatched"] == 1 and r["inserted_companies"] == 1
    s = conn.execute("select * from signals where company_key='1111111-1'").fetchone()
    assert s["signal_type"] == "bf_funding" and s["date"] == "2026-05-04" and s["source_url"] == bf.DASHBOARD_URL
    assert s["amount_eur"] == 1234.5 and s["confidence"] == "high"
    assert s["detail"].startswith("Innovaatiosetteli: Hull sensor") and "manual" in s["detail"]


def test_name_match_is_medium_and_numeric_amount(tmp_path, conn):
    p = tmp_path / "x.xlsx"
    build_fixture(p, FI, ROWS)
    bf.run(conn, {}, path=p)
    s = conn.execute("select * from signals where company_key='name:beta'").fetchone()
    assert s["confidence"] == "medium" and s["amount_eur"] == 50000.0 and s["date"] == "2026-06-12"
    g = conn.execute("select group_tag from companies where company_key='2222222-2'").fetchone()
    assert g["group_tag"] == "feed"
    assert conn.execute("select count(*) from companies where name='Ghost Oy'").fetchone()[0] == 0


def test_committed_fixture_file(conn):
    build_fixture(FIXTURE, EN, ROWS)
    assert bf.run(conn, {}, path=FIXTURE)["signals"] == 3


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
