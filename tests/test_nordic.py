"""Norwegian and Danish registers. Responses are synthetic records in the exact shape brreg and cvrapi.dk return; names are fixtures."""
import json
from datetime import date

import pytest

from radar import db, emit, nordic, thesis
from radar.adapters import brreg, cvr

BALTIC = thesis.load("config/thesis_baltic_blue.yaml")
TODAY = date(2026, 10, 17)


def unit(orgnr, name, form="AS", registered="2026-03-02", founded="2026-02-20", code="03.211", desc="Havbruk", **kw):
    u = {"organisasjonsnummer": orgnr, "navn": name, "organisasjonsform": {"kode": form}, "registreringsdatoEnhetsregisteret": registered,
         "stiftelsesdato": founded, "naeringskode1": {"kode": code, "beskrivelse": desc}, "forretningsadresse": {"kommune": "OSLO"}, "konkurs": False}
    u.update(kw)
    return u


def page(*units, pages=1):
    return {"_embedded": {"enheter": list(units)}, "page": {"size": 100, "number": 0, "totalElements": len(units), "totalPages": pages}}


def store_with(tmp_path, *rows):
    conn = db.connect(tmp_path / "n.sqlite")
    for key, name, country, group in rows:
        emit.upsert_company(conn, company_key=key, name=name, country=country, group_tag=group, source_url="https://example.test/declared")
    conn.commit()
    return conn


# ---- config -----------------------------------------------------------------------------------------------------

def test_baltic_thesis_lists_norway_and_denmark_with_codes_and_keywords():
    assert "NO" in thesis.countries(BALTIC) and "DK" in thesis.countries(BALTIC)  # NO must survive YAML (unquoted NO is False)
    assert "SE" in thesis.country_depth(BALTIC) and "connector slot" in thesis.country_depth(BALTIC)["SE"]
    assert "Brønnøysund" in thesis.country_depth(BALTIC)["NO"]
    kw = BALTIC["name_keywords"]
    assert {"hav", "sjø", "akvakultur", "havn", "skip"} <= set(kw["no"]) and {"hav", "skib", "fiskeri"} <= set(kw["da"])
    codes = {c["code"] for c in BALTIC["nace_codes"]}
    assert {"03.11", "03.21", "30.11", "30.12", "50.10", "50.20", "52.22", "71.12", "72.19"} <= codes


# ---- the shared decision ----------------------------------------------------------------------------------------

def test_decide_found_ambiguous_not_found():
    a = {"id": "1", "name": "Fixture Sea AS"}
    b = {"id": "2", "name": "Fixture Sea Holding AS"}
    c = {"id": "3", "name": "FIXTURE SEA A/S"}
    assert nordic.decide("Fixture Sea", [a, b])["match"]["id"] == "1"
    r = nordic.decide("Fixture Sea", [a, c])
    assert r["status"] == "ambiguous" and r["match"] is None and [x["id"] for x in r["candidates"]] == ["1", "3"]
    r = nordic.decide("Fixture Sea", [b])
    assert r["status"] == "ambiguous" and r["candidates"] == [b]  # near, never chosen
    assert nordic.decide("Fixture Sea", [{"id": "9", "name": "Other Company AS"}])["status"] == "not_found"
    assert nordic.decide("Fixture Sea", [])["status"] == "not_found"


# ---- Norway -----------------------------------------------------------------------------------------------------

def test_normalise_a_brreg_unit():
    u = brreg.normalise(unit("999000001", "Fixture Sea AS", hjemmeside="fixturesea.example.test", underAvvikling=False))
    assert u["url"] == "https://data.brreg.no/enhetsregisteret/oppslag/enheter/999000001"
    assert u["registered"] == "2026-03-02" and u["founded"] == "2026-02-20" and u["code"] == "03.211" and u["website"] == "https://fixturesea.example.test"
    assert brreg.normalise(unit("999000002", "X AS", konkurs=True))["status"] == "bankrupt"
    assert brreg.normalise(unit("999000003", "X AS", underTvangsavviklingEllerTvangsopplosning=True))["status"] == "ended"
    assert brreg.normalise({"organisasjonsnummer": "1", "navn": "N"})["registered"] is None  # absent stays None


def fake_search(by_query):
    def f(adapter, url, **kw):
        p = kw["params"]
        key = p.get("navn") or p.get("naeringskode")
        return (by_query.get(key, page()), False)
    return f


def test_cohort_lookup_found_ambiguous_and_sole_proprietors_never_candidates(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("no-fixture-sea", "Fixture Sea", "NO", "cohort"), ("no-twin", "Fixture Twin", "NO", "cohort"),
                      ("no-solo", "Fixture Solo", "NO", "cohort"), ("no-none", "Fixture Nothing", "NO", "cohort"),
                      ("dk-other", "Fixture Dane", "DK", "cohort"))
    monkeypatch.setattr(brreg, "cached_get", fake_search({
        "Fixture Sea": page(unit("999000001", "FIXTURE SEA AS")),
        "Fixture Twin": page(unit("999000002", "Fixture Twin AS"), unit("999000003", "Fixture Twin A.S.", form="ASA")),
        "Fixture Solo": page(unit("999000004", "Fixture Solo", form="ENK")),
    }))
    stats = {"requests": 0}
    by = {t["company_key"]: brreg.lookup(t["name"], stats) for t in nordic.targets(conn, "NO")}
    assert set(by) == {"no-fixture-sea", "no-twin", "no-solo", "no-none"}  # the Danish company is not a Norwegian target
    assert by["no-fixture-sea"]["status"] == "found" and by["no-fixture-sea"]["match"]["id"] == "999000001"
    assert by["no-twin"]["status"] == "ambiguous" and len(by["no-twin"]["candidates"]) == 2
    assert by["no-solo"]["status"] == "not_found"  # sole proprietorship: not a company
    assert by["no-none"]["status"] == "not_found"


def test_live_window_filters_and_reasons(monkeypatch):
    rows = [unit("999100001", "Fixture Havn Teknologi AS", code="62.010", desc="Programmering"),                      # keyword hav(n)
            unit("999100002", "Fixture Plain AS", code="03.211", desc="Havbruk"),                                      # code only
            unit("999100003", "Fixture Sole", form="ENK", code="03.211"),                                              # not a company
            unit("999100004", "FIXTURE AS TVANGSAVVIKLINGSBO", code="03.211"),                                         # estate of a dissolved firm
            unit("999100005", "Fixture Broke AS", code="03.211", konkurs=True),
            unit("999100006", "Fixture Elsewhere AS", code="47.110", desc="Detaljhandel"),                             # neither code nor word
            unit("999100007", "Anna Maria Virtanen Holding AS", code="03.211"),                                        # person-shaped
            unit("999100001", "Fixture Havn Teknologi AS", code="62.010", desc="Programmering")]                       # duplicate across queries
    monkeypatch.setattr(brreg, "cached_get", lambda adapter, url, **kw: (page(*rows) if kw["params"].get("naeringskode") == "03.21" else page(), False))
    out = brreg.live_window(BALTIC, TODAY, {"requests": 0})
    by = {r["id"]: r for r in out}
    assert set(by) == {"999100001", "999100002"}
    assert by["999100001"]["confidence"] == "medium" and "'hav" in by["999100001"]["reason"]
    assert by["999100002"]["confidence"] == "low" and "NACE code 03.211" in by["999100002"]["reason"]


def test_run_writes_json_imports_dated_cohort_and_live_rows(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("no-fixture-sea", "Fixture Sea", "NO", "cohort"))
    monkeypatch.setattr(brreg, "cached_get", lambda adapter, url, **kw: (
        page(unit("999000001", "Fixture Sea AS")) if kw["params"].get("navn") == "Fixture Sea"
        else page(unit("999100002", "Fixture Plain AS", code="03.211", registered="2026-05-05")) if kw["params"].get("naeringskode") == "03.21" else page(), False))
    path = tmp_path / "brreg.json"
    res = brreg.run(conn, BALTIC, today=TODAY, path=path)
    assert res["found"] == 1 and res["blocked"] == 0 and res["source"] == "register"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["live_window_run"] and [r["id"] for r in data["rows"]] == ["999100002"] and data["cohort"][0]["status"] == "found"
    s = conn.execute("SELECT * FROM signals WHERE company_key='no-fixture-sea'").fetchone()
    assert s["date"] == "2026-03-02" and s["confidence"] == "medium" and s["adapter"] == "brreg"
    assert s["source_url"] == "https://data.brreg.no/enhetsregisteret/oppslag/enheter/999000001" and "exact legal name" in s["detail"]
    c = conn.execute("SELECT * FROM companies WHERE company_key='no-fixture-sea'").fetchone()
    assert c["group_tag"] == "cohort" and c["name"] == "Fixture Sea" and c["founded"] == "2026-02-20" and c["country"] == "NO"
    live = conn.execute("SELECT * FROM companies WHERE company_key='no-999100002'").fetchone()
    assert live["group_tag"] == "feed"
    assert conn.execute("SELECT confidence FROM signals WHERE company_key='no-999100002'").fetchone()[0] == "low"


def test_run_without_no_in_the_countries_does_the_cohort_lookup_only(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("no-fixture-sea", "Fixture Sea", "NO", "cohort"))
    th = {**BALTIC, "countries": ["FI"], "geography": {**BALTIC["geography"], "countries": ["FI"]}}
    monkeypatch.setattr(brreg, "cached_get", lambda adapter, url, **kw: (page(unit("999000001", "Fixture Sea AS")), False))
    res = brreg.run(conn, th, today=TODAY, path=tmp_path / "b.json")
    assert res["found"] == 1 and json.loads((tmp_path / "b.json").read_text())["live_window_run"] is False


def test_unreachable_register_imports_the_committed_json(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("no-fixture-sea", "Fixture Sea", "NO", "cohort"))
    monkeypatch.setattr(brreg, "cached_get", lambda adapter, url, **kw: (page(unit("999000001", "Fixture Sea AS")), False))
    path = tmp_path / "brreg.json"
    brreg.run(conn, BALTIC, today=TODAY, path=path)
    conn2 = db.connect(tmp_path / "second.sqlite")
    emit.upsert_company(conn2, company_key="no-fixture-sea", name="Fixture Sea", country="NO", group_tag="cohort", source_url="https://example.test/d")

    def down(*a, **k):
        raise brreg.Blocked("offline")
    monkeypatch.setattr(brreg, "cached_get", down)
    res = brreg.run(conn2, BALTIC, today=TODAY, path=path)
    assert res["blocked"] == 1 and res["source"] == "committed JSON" and res["found"] == 1 and res["signals"] == 2  # the cohort match and the same unit as a live-window row (code 03.211)
    assert brreg.run(conn2, BALTIC, today=TODAY, path=tmp_path / "missing.json")["source"] == "none"
    assert brreg.run(conn2, BALTIC, today=TODAY, path=path, offline=True)["signals"] == 0  # idempotent


# ---- Denmark ----------------------------------------------------------------------------------------------------

def cvr_answer(vat, name, start="14/03 - 2023", desc="Anpartsselskab", code=80, **kw):
    d = {"vat": vat, "name": name, "startdate": start, "companydesc": desc, "companycode": code, "industrycode": 721100,
         "industrydesc": "Forskning", "city": "Aarhus"}
    d.update(kw)
    return d


def test_cvr_parse_and_normalise():
    assert cvr.parse_start("14/03 - 2023") == "2023-03-14" and cvr.parse_start("1/1 - 2020") == "2020-01-01"
    assert cvr.parse_start("2023-03-14") is None and cvr.parse_start("31/02 - 2023") is None and cvr.parse_start(None) is None
    u = cvr.normalise(cvr_answer(43880399, "Fixture Dane ApS"))
    assert u["id"] == "43880399" and u["registered"] == "2023-03-14" and u["url"] == "https://datacvr.virk.dk/enhed/virksomhed/43880399"
    assert cvr.normalise(cvr_answer(1, "Solo", desc="Enkeltmandsvirksomhed", code=10)) == {}
    assert cvr.normalise(cvr_answer(2, "Gone ApS", enddate="01/01 - 2025"))["status"] == "ended"


def test_declared_cvr_numbers_come_from_the_declared_list():
    n = cvr.declared_numbers()
    assert n["peatz"] == "43880322" and n["just-measure"] == "39525844" and "sensemakers" not in n and n["reefcircular"] == "44601478"


def test_quota_exceeded_is_blocked_and_never_circumvented(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("dk-a", "Fixture Dane", "DK", "cohort"), ("dk-b", "Fixture Second", "DK", "cohort"))
    calls = []

    def quota(params, client=None):
        calls.append(params)
        raise cvr.Blocked("cvrapi.dk answered QUOTA_EXCEEDED")
    monkeypatch.setattr(cvr, "fetch", quota)
    path = tmp_path / "cvr.json"
    res = cvr.run(conn, BALTIC, path=path)
    assert res["blocked"] == 1 and res["found"] == 0 and len(calls) == 1  # one refused call, then the run stops
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [c["status"] for c in data["cohort"]] == ["blocked", "blocked"] and "QUOTA_EXCEEDED" in data["cohort"][0]["blocked"]
    assert "no search by registration date" in data["live_window_blocked"] and data["rows"] == []
    assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0


def test_cvr_lookup_by_number_then_name_and_a_quota_day_keeps_earlier_answers(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("dk-peatz", "PEATZ", "DK", "cohort"), ("dk-name", "Fixture Named", "DK", "cohort"), ("dk-odd", "Fixture Odd", "DK", "cohort"))
    seen = []

    def fake(params, client=None):
        seen.append(params)
        if params.get("vat") == "43880322":
            return cvr_answer(43880322, "PEATZ ApS")
        if params.get("name") == "Fixture Named":
            return cvr_answer(55500001, "Fixture Named ApS")
        return cvr_answer(55500002, "Totally Different ApS")
    monkeypatch.setattr(cvr, "fetch", fake)
    path = tmp_path / "cvr.json"
    res = cvr.run(conn, BALTIC, path=path)
    assert res["found"] == 2 and res["ambiguous"] == 0 and res["not_found"] == 1 and res["signals"] == 2
    assert {"vat": "43880322"} in seen and {"name": "Fixture Named"} in seen
    s = conn.execute("SELECT * FROM signals WHERE company_key='dk-peatz'").fetchone()
    assert s["date"] == "2023-03-14" and "start date as stated" in s["detail"] and s["source_url"].endswith("/43880322")

    def quota(params, client=None):
        raise cvr.Blocked("cvrapi.dk answered QUOTA_EXCEEDED")
    monkeypatch.setattr(cvr, "fetch", quota)
    conn2 = db.connect(tmp_path / "n2.sqlite")
    emit.upsert_company(conn2, company_key="dk-peatz", name="PEATZ", country="DK", group_tag="cohort", source_url="https://example.test/d")
    res2 = cvr.run(conn2, BALTIC, path=path)  # the daily limit is hit, but the earlier answer in the JSON is still imported
    assert res2["blocked"] == 1 and res2["found"] == 1 and res2["signals"] == 1


def test_declared_number_naming_another_company_is_ambiguous_not_chosen(tmp_path, monkeypatch):
    conn = store_with(tmp_path, ("dk-peatz", "PEATZ", "DK", "cohort"))
    monkeypatch.setattr(cvr, "fetch", lambda params, client=None: cvr_answer(43880322, "Something Else ApS"))
    res = cvr.run(conn, BALTIC, path=tmp_path / "c.json")
    assert res["ambiguous"] == 1 and res["found"] == 0 and conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0
