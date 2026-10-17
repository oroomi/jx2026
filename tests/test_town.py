"""Company home town: read from the PRH address block, no network. Fixtures are trimmed copies of real API responses."""
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from radar import backfill_town, db, emit, town
from radar.adapters import declared, prh

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 16)
THESIS = {"industry_codes": [{"code": "30110"}], "name_keywords": {"fi": ["meri"], "en": ["marine"]}}


def _addr(kind, cities, date_="2020-01-01", **extra):
    return {"type": kind, "registrationDate": date_, "postOffices": [{"city": c, "languageCode": lc} for lc, c in cities.items()], **extra}


def test_clean_city_title_cases_and_drops_mail_recipients():
    assert town.clean_city("TURKU") == "Turku"
    assert town.clean_city("  ÄÄNEKOSKI ") == "Äänekoski"
    assert town.clean_city("YLI-II") == "Yli-Ii"
    assert town.clean_city("KAUHAJOKI AS") == "Kauhajoki" and town.clean_city("HOLLOLA KK") == "Hollola"
    assert town.clean_city("KOSKI TL") == "Koski Tl"  # a real municipality name, not a service point
    for junk in ("VARMA", "Osoite Tuntematon", "YRITYSLOKERO", "", None):
        assert town.clean_city(junk) is None


def test_of_prefers_finnish_name_and_visiting_address():
    c = {"addresses": [_addr(2, {"2": "ÅBO", "1": "TURKU"}), _addr(1, {"1": "MIKKELI", "2": "S:T MICHEL"})]}
    assert town.of(c) == ("Mikkeli", "visiting")
    assert town.of({"addresses": [_addr(2, {"2": "HELSINGFORS", "1": "HELSINKI"})]}) == ("Helsinki", "postal")
    assert town.of({"addresses": [_addr(2, {"2": "JAKOBSTAD"})]}) == ("Jakobstad", "postal")  # no Finnish name: the one given


def test_of_uses_current_and_latest_address_and_never_guesses():
    old = _addr(1, {"1": "OULU"}, "2019-01-01", endDate="2024-01-01")
    assert town.of({"addresses": [old]}) == (None, None)  # ended
    new_a, new_b = _addr(1, {"1": "ESPOO"}, "2021-01-01"), _addr(1, {"1": "VANTAA"}, "2023-01-01")
    assert town.of({"addresses": [new_a, new_b, old]})[0] == "Vantaa"
    abroad = {"type": 1, "registrationDate": "2025-01-01", "postOffices": [], "country": "SE", "freeAddressLine": "Solbergaleden 6 81340 Torsäker"}
    assert town.of({"addresses": [abroad]}) == (None, None)  # free text is not parsed
    assert town.of({"addresses": [abroad, _addr(2, {"1": "TAMPERE"})]}) == ("Tampere", "postal")  # falls back to the next address
    assert town.of({"addresses": [_addr(1, {"1": "VARMA"}), _addr(2, {"1": "LAHTI"})]}) == ("Lahti", "postal")
    assert town.of({}) == (None, None)


def test_source_url_keeps_the_stored_prh_link_else_ytj_page():
    stored = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3543918-7"
    assert town.source_url("3543918-7", stored) == stored
    assert town.source_url("3543918-7", "https://example.org/x") == "https://tietopalvelu.ytj.fi/yritys/3543918-7"
    assert town.source_url("3543918-7", None) == "https://tietopalvelu.ytj.fi/yritys/3543918-7"


def test_schema_050_is_idempotent_and_upgrades_an_old_store(tmp_path):
    p = tmp_path / "old.sqlite"
    old = sqlite3.connect(p)
    old.executescript((db.SCHEMA_DIR / "001_core.sql").read_text(encoding="utf-8"))  # a store from before 050
    old.execute("INSERT INTO companies (company_key,name,source_url,fetched_at) VALUES ('k','K Oy','https://x.org','2026-10-01T00:00:00Z')")
    old.commit()
    old.close()
    for _ in range(3):  # every start re-applies every schema file
        c = db.connect(p)
        cols = [r[1] for r in c.execute("PRAGMA table_info(companies)")]
        assert cols.count("town") == 1 and cols.count("town_source_url") == 1
        c.close()
    c = db.connect(p)
    assert c.execute("SELECT name, town, town_source_url FROM companies").fetchone()[:] == ("K Oy", None, None)


def test_set_town_never_erases():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1234567-8", name="A Oy", y_tunnus="1234567-8", source_url="https://avoindata.prh.fi/x")
    assert town.set_town(c, "1234567-8", "Turku", "https://avoindata.prh.fi/x") is True
    assert town.set_town(c, "1234567-8", "Turku", "https://avoindata.prh.fi/x") is False  # unchanged
    assert town.set_town(c, "1234567-8", None, "https://avoindata.prh.fi/x") is False
    assert c.execute("SELECT town FROM companies").fetchone()[0] == "Turku"
    emit.upsert_company(c, company_key="1234567-8", name="A Oy", y_tunnus="1234567-8", source_url="https://avoindata.prh.fi/y")
    assert c.execute("SELECT town FROM companies").fetchone()[0] == "Turku"  # a later upsert keeps it


@pytest.fixture
def offline(monkeypatch):
    def load(name):
        return json.loads((FIX / f"prh_{name}.json").read_text(encoding="utf-8"))

    def fake(params, client=None):
        if params.get("businessId") == "3543918-7":
            return load("emission_eye"), False
        if params.get("businessId") == "3327328-3":
            return load("agile_composites"), False
        if params.get("name") == "meri":
            return load("discovery_meri"), False
        return {"totalResults": 0, "companies": []}, False
    monkeypatch.setattr(prh, "fetch", fake)


def test_prh_adapter_stores_town_at_refresh_and_discovery(offline):
    c = db.connect(":memory:")
    declared.run(c)
    res = prh.run(c, THESIS, today=TODAY)
    ee = c.execute("SELECT town, town_source_url FROM companies WHERE company_key='3543918-7'").fetchone()
    assert ee[0] == "Espoo" and ee[1] == "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=3543918-7"
    found = c.execute("SELECT name, town FROM companies WHERE group_tag='feed' AND y_tunnus IS NOT NULL").fetchall()
    assert res["discovered"] == 3 and len(found) == 3 and all(t for _, t in found)
    assert c.execute("SELECT count(*) FROM companies WHERE name IN ('Edilm','Unique Docks') AND town IS NOT NULL").fetchone()[0] == 0  # no y-tunnus, no town


def _cache_file(d, name, companies):
    (d / f"{name}.json").write_text(json.dumps({"totalResults": len(companies), "companies": companies}), encoding="utf-8")


def _rec(bid, addresses, modified="2026-01-01T00:00:00"):
    return {"businessId": {"value": bid}, "lastModified": modified, "addresses": addresses}


def test_backfill_maps_cache_to_store_and_reports(tmp_path, monkeypatch, capsys):
    cache_a, cache_b = tmp_path / "prh", tmp_path / "prh_intake"
    cache_a.mkdir(), cache_b.mkdir()
    _cache_file(cache_a, "a", [_rec("1111111-1", [_addr(1, {"1": "TURKU"})]), _rec("2222222-2", [_addr(2, {"1": "TURKU"})]),
                               _rec("3333333-3", [{"type": 2, "postOffices": [], "country": "SE", "freeAddressLine": "x"}])])
    _cache_file(cache_b, "b", [_rec("1111111-1", [_addr(1, {"1": "ESPOO"})], "2025-01-01T00:00:00"),  # older copy of the same business id
                               _rec("4444444-4", [_addr(1, {"1": "OULU"})])])
    store = tmp_path / "store.sqlite"
    monkeypatch.setattr(db, "DB_PATH", store)
    c = db.connect(store)
    for bid in ("1111111-1", "2222222-2", "3333333-3", "5555555-5"):
        emit.upsert_company(c, company_key=bid, name=f"N {bid}", y_tunnus=bid, source_url=f"https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId={bid}")
    emit.upsert_company(c, company_key="name:no-id", name="No Id", source_url="https://example.org/no-id")
    c.commit()
    c.close()

    assert backfill_town.main(["--cache-dir", str(cache_a), "--cache-dir", str(cache_b)]) == 0
    out = capsys.readouterr().out
    assert "companies updated: 2" in out and "companies with no cached address: 2" in out and "distinct towns: 1" in out and "Turku: 2" in out
    rows = dict(sqlite3.connect(store).execute("SELECT company_key, town FROM companies").fetchall())
    assert rows == {"1111111-1": "Turku", "2222222-2": "Turku", "3333333-3": None, "5555555-5": None, "name:no-id": None}  # newest record wins
    assert backfill_town.main(["--cache-dir", str(cache_a), "--cache-dir", str(cache_b)]) == 0  # second run changes nothing
    assert "(0 changed)" in capsys.readouterr().out
    assert backfill_town.main(["--cache-dir", str(tmp_path / "empty")]) == 2
