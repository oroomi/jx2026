"""PRH/YTJ adapter and declared loader. Offline: tests/fixtures/prh_*.json are trimmed copies of real API responses."""
import json
from datetime import date
from pathlib import Path

import pytest

from radar import db
from radar.adapters import declared, prh

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 16)
THESIS = {"industry_codes": [{"code": "30110"}], "name_keywords": {"fi": ["meri"], "en": ["marine"]}}


def _load(name):
    return json.loads((FIX / f"prh_{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def offline(monkeypatch):
    def fake(params, client=None):
        if params.get("businessId") == "3543918-7":
            return _load("emission_eye"), False
        if params.get("businessId") == "3327328-3":
            return _load("agile_composites"), False
        if params.get("name") == "meri":
            return _load("discovery_meri"), False
        return {"totalResults": 0, "companies": []}, False
    monkeypatch.setattr(prh, "fetch", fake)


def test_declared_loads_28():
    c = db.connect(":memory:")
    r = declared.run(c)
    assert r["companies"] == 28 and r["signals"] == 0
    assert c.execute("select count(*) from signals").fetchone()[0] == 0
    assert c.execute("select group_tag, count(*) from companies group by 1 order by 1").fetchall()[0][1] == 19
    ee = c.execute("select * from companies where company_key='3543918-7'").fetchone()
    assert ee["founded"] == "2025-06-13" and ee["source_url"].startswith("https://")
    for name in ("Edilm", "Unique Docks"):
        row = c.execute("select * from companies where name=?", (name,)).fetchone()
        assert row["y_tunnus"] is None and row["founded"] is None and row["source_url"].startswith("http")
    assert c.execute("select company_key from companies where name='TuniSea'").fetchone()[0] == "no-tunisea"


def test_prh_refresh_emission_eye(offline):
    c = db.connect(":memory:")
    declared.run(c)
    res = prh.run(c, THESIS, today=TODAY)
    ee = c.execute("select * from companies where company_key='3543918-7'").fetchone()
    assert ee["founded"] == "2025-06-13" and ee["register_status"] == "active" and ee["industry_code"] == "62100"
    assert ee["industry_desc"] == "Computer programming activities"
    sigs = c.execute("select * from signals where company_key='3543918-7'").fetchall()
    assert len(sigs) == 1 and sigs[0]["signal_type"] == "register_entry" and sigs[0]["confidence"] == "high"
    assert sigs[0]["date"] == "2025-06-13" and sigs[0]["source_url"].startswith("https://avoindata.prh.fi/")
    # Edilm and Unique Docks: no Y-tunnus, no signal
    assert c.execute("select count(*) from signals s join companies k using(company_key) where k.name in ('Edilm','Unique Docks')").fetchone()[0] == 0
    assert res["discovered"] == 3


def test_bankrupt_company_has_status_and_no_signal(offline):
    c = db.connect(":memory:")
    from radar import emit
    emit.upsert_company(c, company_key="3327328-3", name="Agile Composites Oy", y_tunnus="3327328-3", source_url="https://example.org", group_tag="portfolio")
    prh.run(c, {"industry_codes": [], "name_keywords": {}}, today=TODAY)
    assert c.execute("select register_status from companies where company_key='3327328-3'").fetchone()[0] == "bankrupt"
    assert c.execute("select count(*) from signals where company_key='3327328-3'").fetchone()[0] == 0


def test_status_ignores_top_level_status():
    comp = _load("agile_composites")["companies"][0]
    assert comp["status"] == "2"
    assert prh.derive_status(comp) == "bankrupt"
    assert prh.derive_status({"companySituations": [], "registeredEntries": [{"type": "1", "endDate": "2024-01-01"}]}) == "ended"
    assert prh.derive_status({}) == "unknown"


def test_discovery_confidence_and_filters(offline):
    c = db.connect(":memory:")
    prh.run(c, THESIS, today=TODAY)
    rows = {r["name"]: r for r in c.execute("select k.name, s.confidence, k.group_tag from companies k join signals s using(company_key) where k.group_tag='feed'")}
    assert set(rows) == {"Saariston Meritie Oy", "MeriTekno Oy", "Meridian Consulting Oy"}
    assert all(r["confidence"] == "medium" for r in rows.values())  # never high for discovery
    # registered before the window (Meribom 2025-06-25) and a housing company are dropped
    assert c.execute("select count(*) from companies where name like 'Meribom%' or name like 'Fastighets%'").fetchone()[0] == 0


def test_code_only_match_is_low():
    comp = {"businessId": {"value": "1234567-1", "registrationDate": "2026-01-02"}, "names": [{"name": "Plain Oy", "type": "1"}],
            "mainBusinessLine": {"type": "30110", "descriptions": []}, "companySituations": [],
            "registeredEntries": [{"type": "1"}], "companyForms": []}
    c = db.connect(":memory:")
    stats = {"discovered": 0, "signals": 0, "samples": []}
    prh._consider(c, comp, {"30110"}, ["meri"], "2025-10-16", stats)
    assert c.execute("select confidence from signals").fetchone()[0] == "low"


def test_keyword_is_word_start_only():
    assert prh._words_start_with("MeriTekno Oy", ["meri"]) == ["meri"]
    assert prh._words_start_with("Ameriikan Oy", ["meri"]) == []
