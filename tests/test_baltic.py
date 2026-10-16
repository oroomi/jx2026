import importlib.util
from pathlib import Path

import pytest

from radar import db, emit, thesis as thesis_mod
from radar.adapters import cordis, ted

ROOT = Path(__file__).resolve().parent.parent


def _fx(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / "fixtures" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tedfx = _fx("ted_fixture")
BALTIC = {"countries": ["FI", "EE", "LV", "SE"], "country_depth": {"FI": "registers+contracts+grants", "EE": "register+grants"},
          "geography": {}, "ted_cpv": [{"prefix": "45241"}, {"prefix": "34510"}]}


# ---- thesis ----------------------------------------------------------------------------------------------------

def test_thesis_without_countries_defaults_to_finland():
    th = {"geography": {"feed_window_days": 90}}
    assert thesis_mod.countries(th) == ["FI"]
    assert thesis_mod.country_depth(th) == {"FI": "EU sources only"}


def test_thesis_geography_countries_is_the_fallback():
    assert thesis_mod.countries({"geography": {"countries": ["ee", "LV", "EE"]}}) == ["EE", "LV"]


def test_default_thesis_is_finland_only_baltic_thesis_lists_eight():
    assert thesis_mod.countries(thesis_mod.load("config/thesis.yaml")) == ["FI"]
    b = thesis_mod.load("config/thesis_baltic_blue.yaml")
    assert thesis_mod.countries(b) == ["FI", "SE", "EE", "LV", "LT", "DK", "DE", "PL"]
    depth = thesis_mod.country_depth(b)
    assert depth["FI"] == "registers+contracts+grants" and depth["EE"] == "register+grants" and depth["LV"] == "EU sources only"
    assert "baltic_blue" in thesis_mod.available()


def test_bad_countries_are_rejected(tmp_path):
    f = tmp_path / "thesis_bad.yaml"
    f.write_text("id: x\ntitle: x\ngeography: {feed_window_days: 5}\nindustry_codes: []\nfeed_signal_types: []\nname_keywords: [a]\ncountries: [Finland]\n")
    with pytest.raises(thesis_mod.ThesisError):
        thesis_mod.load(f)


# ---- country filter in the EU adapters -------------------------------------------------------------------------

def test_vat_key_per_country():
    assert cordis.vat_key("FI12345678", "FI") == "1234567-8"
    assert cordis.vat_key("EE 100 123 456", "EE") == "ee-vat-100123456"
    assert cordis.vat_key("LV40003000000", "EE") is None   # VAT of another country never keys this one
    assert cordis.vat_key(None, "EE") is None


def test_cordis_discovery_follows_thesis_countries(tmp_path):
    import io
    import zipfile
    org = ("projectID;name;country;activityType;SME;vatNumber;role;ecContribution\n"
           "9001;Fixture Aqua Oy;FI;PRC;true;FI12345678;participant;1000\n"
           "9001;Fixture Aqua OU;EE;PRC;true;EE100123456;participant;2000\n"
           "9001;Fixture Aqua AB;SE;PRC;true;SE556677889901;participant;3000\n")
    proj = ("id;acronym;title;startDate;endDate;frameworkProgramme;fundingScheme;objective;keywords\n"
            "9001;FIX;Aquaculture fixture;2026-01-15;2027-01-15;HORIZON;RIA;ocean farming;aqua\n")
    zp = tmp_path / "fx.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("organization.csv", org)
        z.writestr("project.csv", proj)
    th = {**thesis_mod.load("config/thesis.yaml")}
    for countries, expect in ((["FI"], {"FI"}), (["FI", "EE"], {"FI", "EE"})):
        conn = db.connect(":memory:")
        cordis.run(conn, {**th, "countries": countries}, zips={"horizon-europe": zp})
        got = {r["country"] for r in conn.execute("SELECT country FROM companies")}
        assert got == expect, (countries, got)


# ---- TED ---------------------------------------------------------------------------------------------------------

def test_ted_query_has_cpv_prefixes_and_iso3_countries():
    q = ted.build_query(BALTIC, ["EE", "LV"], "2026-01-01")
    assert "winner-country IN (EST LVA)" in q and "publication-date>=20260101" in q
    assert "classification-cpv=45241*" in q and "classification-cpv=34510*" in q
    assert ted.build_query({"countries": ["EE"]}, ["EE"]) is None          # no ted_cpv in the thesis: nothing to ask
    assert ted.build_query(BALTIC, []) is None


def test_ted_skips_countries_with_a_national_contract_archive():
    use, skip = ted.active_countries(BALTIC)
    assert skip == ["FI"] and use == ["EE", "LV", "SE"]


def test_ted_parse_notice():
    p = ted.parse_notice(tedfx.HITS[0])
    assert p["pub"] == "1-2026" and p["date"] == "2026-02-03" and p["amount"] == 125000.5
    assert p["winners"] == [{"name": "Fixture Sadam OU", "cc3": "EST", "size": "small"}]
    two = ted.parse_notice(tedfx.HITS[1])
    assert len(two["winners"]) == 2 and two["amount"] is None            # value kept only for a single winner
    amb = ted.parse_notice(tedfx.HITS[3])                                  # names and countries cannot be paired
    assert amb["winners"] == [] and amb["skipped"] == 2


class _Client:
    def __init__(self, hits):
        self.hits, self.calls = hits, 0

    def post(self, url, json=None):
        self.calls += 1
        return type("R", (), {"status_code": 200, "json": lambda s: {"notices": self.hits}, "raise_for_status": lambda s: None})()


def test_ted_run_emits_winner_signals_by_country(tmp_path):
    conn = db.connect(":memory:")
    res = ted.run(conn, BALTIC, client=_Client(tedfx.HITS), cache=tmp_path)
    assert res["blocked"] == "" and res["by_country"] == {"EE": 1, "LV": 2}
    assert res["skipped_large"] == 1 and res["skipped_countries"] == "FI"
    rows = conn.execute("SELECT c.name, c.country, s.* FROM signals s JOIN companies c USING (company_key) ORDER BY s.id").fetchall()
    assert [r["name"] for r in rows] == ["Fixture Sadam OU", "Fixture Laivas SIA", "Fixture Two SIA"]
    assert rows[0]["country"] == "EE" and rows[0]["signal_type"] == "public_contract" and rows[0]["adapter"] == "ted"
    assert rows[0]["source_url"] == "https://ted.europa.eu/en/notice/-/detail/1-2026" and rows[0]["date"] == "2026-02-03"
    assert rows[0]["amount_eur"] == 125000.5 and rows[1]["amount_eur"] is None
    assert not conn.execute("SELECT 1 FROM companies WHERE name LIKE '%Large%' OR name LIKE '%Suomi%'").fetchone()
    again = ted.run(conn, BALTIC, client=_Client(tedfx.HITS), cache=tmp_path)   # second run reads the cache and adds nothing
    assert again["signals"] == 0 and again["requests"] == 0


def test_ted_skips_sole_traders_named_like_a_person(tmp_path):
    conn = db.connect(":memory:")
    res = ted.run(conn, {**BALTIC, "countries": ["EE", "LV", "SE", "PL"]}, client=_Client(tedfx.HITS), cache=tmp_path)
    assert res["skipped_person"] == 1 and "PL" not in res["by_country"]
    assert ted.looks_like_company("Fixture Laivas SIA", BALTIC) and not ted.looks_like_company("Fixture Person", BALTIC)


def test_ted_stops_on_429(tmp_path):
    class Blocked:
        def post(self, url, json=None):
            return type("R", (), {"status_code": 429})()
    conn = db.connect(":memory:")
    res = ted.run(conn, BALTIC, client=Blocked(), cache=tmp_path)
    assert "429" in res["blocked"] and res["signals"] == 0


# ---- Estonia ---------------------------------------------------------------------------------------------------------

from datetime import date, timedelta  # noqa: E402

from radar.adapters import estonia_register as ee  # noqa: E402

eefx = _fx("estonia_fixture")
EE_THESIS = {"countries": ["FI", "EE"], "industry_codes": [{"code": "03211"}],
             "name_keywords": {"et": ["mere", "laev"], "en": ["marine"]}}


def _ee_file(tmp_path, delimiter_rows=None):
    f = tmp_path / "ee.csv"
    f.write_text("\n".join(delimiter_rows or eefx.rows(lambda n: (date.today() - timedelta(days=n)).isoformat())), encoding="utf-8")
    return f


def test_estonia_parse_date_both_formats():
    assert ee.parse_date("2026-03-04T00:00:00") == "2026-03-04" and ee.parse_date("04.03.2026") == "2026-03-04"
    assert ee.parse_date("") is None and ee.parse_date("March 2026") is None


def test_estonia_fixture_rows(tmp_path):
    conn = db.connect(":memory:")
    res = ee.run(conn, EE_THESIS, path=_ee_file(tmp_path))
    assert res["blocked"] == "" and res["bad_header"] == "" and res["signals"] == 3
    rows = {r["name"]: r for r in conn.execute("SELECT c.name, c.country, c.industry_code, s.* FROM signals s JOIN companies c USING (company_key)")}
    assert set(rows) == {"Fixture Mere OÜ", "Fixture Kood OÜ", "Fixture Laev AS"}
    assert rows["Fixture Mere OÜ"]["confidence"] == "medium" and rows["Fixture Kood OÜ"]["confidence"] == "low"
    assert all(r["country"] == "EE" and r["signal_type"] == "register_entry" for r in rows.values())
    assert rows["Fixture Mere OÜ"]["source_url"] == "https://ariregister.rik.ee/est/company/90000001"
    assert rows["Fixture Kood OÜ"]["source_url"] == "https://ariregister.rik.ee/eng/company/90000002"  # no link in the row: built from the code
    assert rows["Fixture Laev AS"]["industry_code"] is None            # not stated stays NULL
    assert ee.run(conn, EE_THESIS, path=_ee_file(tmp_path))["signals"] == 0   # idempotent


def test_estonia_inactive_without_the_country(tmp_path):
    conn = db.connect(":memory:")
    res = ee.run(conn, {**EE_THESIS, "countries": ["FI"]}, path=_ee_file(tmp_path))
    assert res["signals"] == 0 and "not an active country" in res["note"]


def test_estonia_bad_header_is_reported_not_guessed(tmp_path):
    conn = db.connect(":memory:")
    res = ee.run(conn, EE_THESIS, path=_ee_file(tmp_path, ["a;b;c", "1;2;3"]))
    assert res["bad_header"] and res["signals"] == 0


def test_estonia_blocked_on_429(tmp_path, monkeypatch):
    class C:
        def get(self, url):
            return type("R", (), {"status_code": 429})()
    monkeypatch.setattr(ee, "download", lambda *a, **k: (_ for _ in ()).throw(ee.Blocked("HTTP 429")))
    res = ee.run(db.connect(":memory:"), EE_THESIS)
    assert "429" in res["blocked"]
