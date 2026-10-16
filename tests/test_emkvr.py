"""emkvr adapter on a 20-row synthetic fixture shaped like the Kaju JSON (Fixture names only)."""
import json

import pytest

from radar import db, emit
from radar.adapters import emkvr

THESIS = {"name_keywords": {"en": ["fish", "aquaculture"]}}
DEFS = [{"id": 3, "kunnat": [{"id": 1, "nimi": {"FI": "TURKU"}}], "hanketilanteet": [{"id": 505, "nimi": {"FI": "Käynnissä"}}, {"id": 506, "nimi": {"FI": "Hylätty"}}],
         "toimintalinjat": [{"id": 10, "nimi": {"FI": "Priority"}, "toimenpiteet": [{"id": 11, "nimi": {"FI": "Fixture measure"}}]}]}]
C = emkvr.COLUMNS[3]


def row(i, name, start="2025-01-09T22:00:00.000Z", project="Fixture operation", descr="", granted=1000, status=505):
    v = {C["name"]: name, C["number"]: 900000 + i, C["project"]: project, C["descr"]: descr, C["granted"]: granted, C["eu"]: 400, C["total"]: 2000}
    if start is not None:
        v[C["start"]] = start
    return {"id": i, "arvot": v, "viitteet": {"HANKETILANNE": status, "KUNTA": 1, "TOIMENPIDE": 11}}


ROWS = [row(1, "Fixture Known Oy"),                                              # matched by folded name
        row(2, "Fixture Known Oy", start="2024"),                                # year-only precision
        row(3, "Fixture Known Oy", start=None),                                  # no date: skipped
        row(4, "Fixture Fish Farm Oy", project="Fish farm pilot"),               # discovery (keyword)
        row(5, "Fixture Plain Oy", project="Office chairs"),                     # no keyword: skipped
        row(6, "Fixture Twin Oy"),                                               # ambiguous name in the store
        row(7, "Fixture Rejected Oy", status=506),                               # rejected
        row(8, "Lapin ELY-keskus", project="Fish programme"),                    # public
        row(9, "Fixture Fishers ry", project="Fish programme"),                  # association
        row(10, "Fixture Kala Ky", project="Fish programme"),                    # partnership
        row(11, "Fixture Person", project="Fish programme"),                     # other (private person form)
        row(12, "Fixture Cooperative osuuskunta", project="Fish programme")]     # cooperative
ROWS += [row(13 + i, f"Fixture Filler {i} Oy", project="Chairs") for i in range(8)]


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1111111-1", name="Fixture Known Oy", source_url="https://example.org/x", y_tunnus="1111111-1", country="FI")
    emit.upsert_company(c, company_key="2222222-2", name="Fixture Twin Oy", source_url="https://example.org/y", country="FI")
    emit.upsert_company(c, company_key="3333333-3", name="Fixture Twin Ab", source_url="https://example.org/z", country="FI")
    c.commit()
    return c


@pytest.fixture
def result(conn, tmp_path):
    (tmp_path / "ohjelmat.json").write_text(json.dumps(DEFS))
    (tmp_path / "rows_3.json").write_text(json.dumps(ROWS))
    files = {"ohjelmat": tmp_path / "ohjelmat.json", "rows_3": tmp_path / "rows_3.json"}
    return emkvr.run(conn, THESIS, files=files), conn, files


def test_beneficiary_types():
    assert [emkvr.beneficiary_type(n) for n in ("A Oy", "Lapin ELY-keskus", "Kalat ry", "B Ky", "C osuuskunta", "Jane Doe")] == \
        ["company", "public", "association", "sole_or_partnership", "cooperative", "other"]


def test_day_is_helsinki_calendar_day():
    assert emkvr.parse_day("2025-01-09T22:00:00.000Z") == ("2025-01-10", "day")
    assert emkvr.parse_day("2024") == ("2024-01-01", "year")
    assert emkvr.parse_day(None) == (None, None)


def test_match_and_signal(result):
    c, conn, _ = result
    s = conn.execute("SELECT * FROM signals WHERE company_key='1111111-1' AND date='2025-01-10'").fetchone()
    assert s["signal_type"] == "eu_grant" and s["confidence"] == "medium" and s["amount_eur"] == 1000
    assert s["source_url"] == "https://kaju.mmm.fi/kaju2020/?ok=3&_26=900001" and "900001" in s["detail"] and "TURKU" in s["detail"]
    assert c["rows_parsed"] == 20 and c["matched_companies"] == 1


def test_year_only_and_no_date(result):
    c, conn, _ = result
    r = conn.execute("SELECT m.date_precision FROM signals s JOIN signal_meta m ON m.signal_id=s.id WHERE s.date='2024-01-01'").fetchone()
    assert r["date_precision"] == "year" and c["skipped_no_date"] == 1


def test_discovery_and_skip_rules(result):
    c, conn, _ = result
    assert c["discovery_companies"] == 1 and c["skipped_no_keyword"] >= 1 and c["skipped_ambiguous"] == 1
    d = conn.execute("SELECT * FROM companies WHERE name='Fixture Fish Farm Oy'").fetchone()
    assert d["group_tag"] == "feed" and conn.execute("SELECT confidence FROM signals WHERE company_key=?", (d["company_key"],)).fetchone()[0] == "low"
    assert c["skipped_status"] == 1
    assert c["beneficiaries_by_type"]["public"] == 1 and c["beneficiaries_by_type"]["association"] == 1
    for n in ("Lapin ELY-keskus", "Fixture Fishers ry", "Fixture Kala Ky", "Fixture Person"):
        assert conn.execute("SELECT count(*) FROM companies WHERE name=?", (n,)).fetchone()[0] == 0


def test_idempotent(result, conn):
    _, conn, files = result
    assert emkvr.run(conn, THESIS, files=files)["signals"] == 0


def test_blocked_download_is_clean(conn, monkeypatch):
    monkeypatch.setattr(emkvr, "download", lambda: {"paths": {}, "blocked": "HTTP 403", "errors": [], "bytes": 0})
    c = emkvr.run(conn, THESIS)
    assert c["blocked"] == "HTTP 403" and c["signals"] == 0
