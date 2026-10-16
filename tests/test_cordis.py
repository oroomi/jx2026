import io
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from cordis_fixture import make_zip, org, proj  # noqa: E402

from radar import db, emit  # noqa: E402
from radar.adapters import cordis  # noqa: E402

THESIS = {"name_keywords": {"en": ["ocean", "marine"]}}


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1111111-1", name="Fixture Declared Oy", source_url="https://example.org/a",
                        y_tunnus="1111111-1", country="FI", group_tag="portfolio")
    emit.upsert_company(c, company_key="es-fixture-nido", name="Fixture Nido SL", source_url="https://example.org/b",
                        country="ES", group_tag="cohort")
    emit.upsert_company(c, company_key="dk-fixture-exact", name="Fixture Exact ApS", source_url="https://example.org/c",
                        country="DK", group_tag="cohort")
    emit.upsert_company(c, company_key="dk-fixture-none", name="Fixture Nothing ApS", source_url="https://example.org/d",
                        country="DK", group_tag="cohort")
    emit.upsert_company(c, company_key="2222222-2", name="Register Name Oy", source_url="https://register.example/2",
                        y_tunnus="2222222-2", country="FI", group_tag="feed")
    c.commit()
    return c


@pytest.fixture(autouse=True)
def declared_csv(tmp_path, monkeypatch):
    p = tmp_path / "declared.csv"
    p.write_text("company,group,country,y_tunnus,cordis_url\n"
                 "Fixture Nido,cohort,ES,,https://cordis.europa.eu/project/id/900\n"
                 "Fixture Exact,cohort,DK,,\n"
                 "Fixture Nothing,cohort,DK,,\n")
    monkeypatch.setattr(cordis, "DECLARED_CSV", p)


def zips(tmp_path, orgs, projects):
    return {"horizon-europe": make_zip(tmp_path / "he.zip", orgs, projects)}


def sigs(conn, key=None):
    q = "SELECT * FROM signals WHERE adapter='cordis'" + (" AND company_key=?" if key else "")
    return conn.execute(q, (key,) if key else ()).fetchall()


def test_vat_match_high(conn, tmp_path):
    z = zips(tmp_path, [org("1", "Fixture Declared Oy", vat="FI11111111", amount="5000")], [proj("1", start="2024-09-01")])
    c = cordis.run(conn, THESIS, zips=z)
    s = sigs(conn, "1111111-1")
    assert len(s) == 1 and s[0]["confidence"] == "high" and s[0]["date"] == "2024-09-01"
    assert s[0]["amount_eur"] == 5000 and s[0]["source_url"] == "https://cordis.europa.eu/project/id/1"
    assert "VAT" in s[0]["detail"] and "Horizon Europe" in s[0]["detail"]
    assert c["declared_matched"]["vat"] == 1


def test_recon_link_medium_with_ratio(conn, tmp_path):
    z = zips(tmp_path, [org("900", "FIXTURE NIDO CONSTRUCT SL", country="ES"), org("900", "Other Partner GmbH", country="DE")],
             [proj("900")])
    cordis.run(conn, THESIS, zips=z)
    s = sigs(conn, "es-fixture-nido")
    assert len(s) == 1 and s[0]["confidence"] == "medium"
    assert "recon link" in s[0]["detail"] and "treat as probable, not certain" in s[0]["detail"] and "similarity 0." in s[0]["detail"]


def test_recon_link_below_ratio_gives_nothing(conn, tmp_path):
    z = zips(tmp_path, [org("900", "Zzzz Qqqq", country="ES")], [proj("900")])
    cordis.run(conn, THESIS, zips=z)
    assert sigs(conn, "es-fixture-nido") == []


def test_exact_name_medium_and_no_match_nothing(conn, tmp_path):
    z = zips(tmp_path, [org("2", "Fixture Exact ApS", country="DK")], [proj("2")])
    c = cordis.run(conn, THESIS, zips=z)
    s = sigs(conn, "dk-fixture-exact")
    assert len(s) == 1 and s[0]["confidence"] == "medium" and c["declared_matched"]["exact_name"] == 1
    assert sigs(conn, "dk-fixture-none") == []


def test_discovery_filter(conn, tmp_path):
    orgs = [
        org("10", "Fixture Marine Oy", vat="FI30000001"),                      # keyword in name
        org("11", "Fixture Title Oy", vat="FI30000002"),                       # keyword in title
        org("12", "Fixture Keywords Oy", vat="FI30000003"),                    # keyword in keywords
        org("13", "Fixture Objective Oy", vat="FI30000004"),                   # keyword in objective
        org("14", "Fixture Sweden Oy", vat="SE30000005", country="SE"),         # wrong country
        org("15", "Fixture NotSme Oy", vat="FI30000006", sme="false"),          # not SME
        org("16", "Fixture Uni Oy", vat="FI30000007", act="HES"),               # not private for profit
        org("17", "Fixture Old Oy", vat="FI30000008"),                          # starts before 2025
        org("18", "Fixture Nokw Oy", vat="FI30000009"),                         # no keyword
        org("19", "Fixture NoVat Oy", vat=""),                                  # keyword but no VAT
    ]
    projs = [proj("10"), proj("11", title="Ocean thing"), proj("12", keywords="marine, x"), proj("13", objective="about the ocean"),
             proj("14", title="Ocean"), proj("15", title="Ocean"), proj("16", title="Ocean"),
             proj("17", title="Ocean", start="2024-12-31"), proj("18"), proj("19", title="Ocean")]
    projs[0]["title"] = "Plain"
    c = cordis.run(conn, THESIS, zips=zips(tmp_path, orgs, projs))
    got = {r["company_key"]: r for r in sigs(conn)}
    assert set(got) == {"3000000-1", "3000000-2", "3000000-3", "3000000-4"}
    assert all(r["confidence"] == "low" for r in got.values())
    assert c["discovery_companies"] == 4 and c["skipped_no_vat"] == 1
    details = " ".join(r["detail"] for r in got.values())
    assert "organisation name: 'marine'" in details and "project title: 'ocean'" in details
    assert "project keywords: 'marine'" in details and "project objective: 'ocean'" in details
    new = conn.execute("SELECT group_tag,country,founded,source_url FROM companies WHERE company_key=?", (next(iter(got)),)).fetchone()
    assert new["group_tag"] == "feed" and new["country"] == "FI" and new["founded"] is None
    assert new["source_url"].startswith("https://cordis.europa.eu/project/id/")


def test_existing_company_not_upserted(conn, tmp_path):
    z = zips(tmp_path, [org("20", "Fixture CORDIS Name Oy", vat="FI22222222")], [proj("20", title="Marine")])
    cordis.run(conn, THESIS, zips=z)
    row = conn.execute("SELECT name,source_url FROM companies WHERE company_key='2222222-2'").fetchone()
    assert row["name"] == "Register Name Oy" and row["source_url"] == "https://register.example/2"
    assert len(sigs(conn, "2222222-2")) == 1


def test_blank_amount_is_null_and_idempotent(conn, tmp_path):
    z = zips(tmp_path, [org("30", "Fixture Marine Oy", vat="FI33333333", amount="")], [proj("30")])
    cordis.run(conn, THESIS, zips=z)
    assert sigs(conn)[0]["amount_eur"] is None and "not stated" in sigs(conn)[0]["detail"]
    n = len(sigs(conn))
    c2 = cordis.run(conn, THESIS, zips=z)
    assert len(sigs(conn)) == n and c2["signals"] == 0


def test_download_403_is_blocked_not_a_crash(conn, tmp_path):
    def opener(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b""))
    out = cordis.download(tmp_path / "cache", opener=opener, pause=0)
    assert out["blocked"] and "403" in out["blocked"] and out["paths"] == {}


def test_download_skips_valid_zip(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    for k in cordis.SOURCES:
        make_zip(cache / f"{k}.zip", [], [])

    def opener(req, timeout=0):
        raise AssertionError("must not download")
    out = cordis.download(cache, opener=opener, pause=0)
    assert len(out["paths"]) == 2 and out["bytes"] == 0
