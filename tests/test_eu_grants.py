"""eu_grants adapter on a 20-record synthetic fixture (Fixture names only; the real file was not reachable)."""
import json

import pytest

from radar import db, emit
from radar.adapters import eu_grants as eg

THESIS = {"name_keywords": {"en": ["ocean", "marine"]}}


def grant(i, org, country="FI", prog="EMFAF", start="2025-03-01", vat=None, title="Fixture project", acr=None, amount=1000):
    return {"identifier": f"FIX{i:03d}", "acronym": acr or f"FX{i}", "title": title, "programme": prog, "callIdentifier": "FIXCALL",
            "startDate": start, "participants": [{"legalName": org, "country": country, "vatNumber": vat, "euContribution": amount}]}


def records():
    r = [grant(1, "Fixture Known Oy", vat="FI11111111"),                       # VAT maps to a held Y-tunnus: high
         grant(2, "Fixture Named Oy"),                                         # exact folded name: medium
         grant(3, "Fixture Ocean Oy", vat="FI22222220", title="Marine pilot"),  # discovery in a blue programme
         grant(4, "Fixture Ocean Plain Oy", vat="FI33333330", prog="LIFE"),    # keyword but not a blue programme: skipped
         grant(5, "Fixture Dull Oy", vat="FI44444440"),                        # blue programme, no keyword: skipped
         grant(6, "Fixture Known Oy", vat="FI11111111", start="2024"),         # year-only date
         grant(7, "Fixture Known Oy", vat="FI11111111", start="", acr="NODATE"),  # no date: skipped
         grant(8, "Fixture Swedish AB", country="SE"),                         # country filter
         grant(9, "Fixture Dup Oy", vat="FI55555550", acr="DUPACR")]           # already in CORDIS
    r += [grant(10 + i, f"Fixture Other {i} GmbH", country="DE") for i in range(11)]
    assert len(r) == 20
    return r


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    for key, name in (("1111111-1", "Fixture Known Oy"), ("5555555-0", "Fixture Dup Oy")):
        emit.upsert_company(c, company_key=key, name=name, source_url="https://example.org/x", y_tunnus=key, country="FI")
    emit.upsert_company(c, company_key="name:named", name="Fixture Named Oy", source_url="https://example.org/y", country="FI")
    emit.emit_signal(c, company_key="5555555-0", signal_type="eu_project", date="2025-03-01", source_url="https://cordis.europa.eu/project/id/777",
                     confidence="medium", adapter="cordis", detail="DUPACR: Fixture project (Horizon Europe)")
    c.commit()
    return c


@pytest.fixture
def result(conn, tmp_path):
    p = tmp_path / "grantsTenders_fixture.json"
    p.write_text(json.dumps({"grants": records()}))
    return eg.run(conn, THESIS, path=p), conn


def test_counts_and_country_filter(result):
    c, conn = result
    assert c["grants"] == 20 and c["finnish_beneficiaries"] == 8   # Swedish and German rows are not counted
    sigs = conn.execute("SELECT * FROM signals WHERE adapter='eu_grants'").fetchall()
    assert {s["company_key"] for s in sigs} == {"1111111-1", "name:named", "2222222-0"}
    assert c["signals"] == 4 and c["signals_by_programme"] == {"EMFAF": 4}


def test_confidence_and_source(result):
    _, conn = result
    s = {r["company_key"]: r for r in conn.execute("SELECT * FROM signals WHERE adapter='eu_grants' AND date='2025-03-01'")}
    assert s["1111111-1"]["confidence"] == "high" and s["name:named"]["confidence"] == "medium"
    assert s["1111111-1"]["source_url"] == f"{eg.FILE_URL}#FIX001" and "FIX001" in s["1111111-1"]["detail"]
    assert s["1111111-1"]["amount_eur"] == 1000


def test_year_only_precision(result):
    _, conn = result
    row = conn.execute("SELECT s.date, m.date_precision FROM signals s JOIN signal_meta m ON m.signal_id=s.id "
                       "WHERE s.company_key='1111111-1' AND s.date='2024-01-01'").fetchone()
    assert row is not None and row["date_precision"] == "year"
    assert conn.execute("SELECT count(*) FROM signals WHERE detail LIKE '%NODATE%'").fetchone()[0] == 0


def test_discovery_needs_blue_programme_and_keyword(result):
    c, conn = result
    assert c["discovery_companies"] == 1 and c["skipped_unmatched"] == 2
    assert conn.execute("SELECT group_tag, country FROM companies WHERE company_key='2222222-0'").fetchone()[:] == ("feed", "FI")
    assert conn.execute("SELECT count(*) FROM companies WHERE company_key IN ('3333333-0','4444444-0')").fetchone()[0] == 0


def test_dedupe_against_cordis(result):
    c, conn = result
    assert c["deduped_against_cordis"] == 1
    assert conn.execute("SELECT count(*) FROM signals WHERE company_key='5555555-0'").fetchone()[0] == 1
    assert "FIX009" in conn.execute("SELECT detail FROM signals WHERE company_key='5555555-0'").fetchone()[0]


def test_idempotent(result, tmp_path):
    c, conn = result
    p = tmp_path / "grantsTenders_fixture.json"
    assert eg.run(conn, THESIS, path=p)["signals"] == 0


def test_blocked_download_returns_cleanly(conn, monkeypatch):
    monkeypatch.setattr(eg, "download", lambda: {"path": None, "blocked": "HTTP 403", "error": None})
    c = eg.run(conn, THESIS)
    assert c["blocked"] == "HTTP 403" and c["signals"] == 0


def test_catalogue_without_beneficiaries_is_blocked_not_invented(conn, tmp_path):
    f = tmp_path / "catalogue_fixture.json"
    f.write_text(json.dumps({"fundingData": {"GrantTenderObj": [
        {"type": 1, "identifier": "FIXTURE-2026-TOPIC", "title": "Fixture topic", "callIdentifier": "FIXTURE-2026",
         "frameworkProgramme": {"abbreviation": "EMFAF"}, "publicationDateLong": 1611792000000}]}}))
    c = eg.run(conn, {"keywords": []}, path=f)
    assert c["grants"] == 1 and c["signals"] == 0 and "catalogue" in c["blocked"]
