"""Sector taxonomy (radar/sectors.py, D42): the mapping on fixture companies, multi-membership, the gates, the declared and notice bases, the
idempotent backfill and its command line, the home rows, the company API and the combined file's table. Fixtures only (an empty store per test)."""
import sqlite3
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from radar import db, emit, home_list, sectors, thesis

ROOT = Path(__file__).resolve().parent.parent
PRH = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId="
BLUE = "redstone_apelago_blue"


def _company(conn, key, name, code, desc, group="feed", country="FI"):
    emit.upsert_company(conn, company_key=key, name=name, source_url=PRH + key, y_tunnus=key, country=country, founded="2020-01-01",
                        industry_code=code, industry_desc=desc, group_tag=group)
    emit.emit_signal(conn, company_key=key, signal_type="register_entry", date="2020-01-01", source_url=PRH + key, confidence="high", adapter="prh")


def _project(conn, key, text):
    url = f"https://cordis.europa.eu/project/id/{key}"
    emit.emit_signal(conn, company_key=key, signal_type="eu_project", date="2024-01-01", source_url=url, confidence="high", adapter="cordis",
                     detail="EU project participation")
    sid = conn.execute("SELECT id FROM signals WHERE source_url=? AND company_key=?", (url, key)).fetchone()[0]
    conn.execute("INSERT INTO signal_text (signal_id, field, text) VALUES (?,?,?)", (sid, "objective", text))
    return url


def _notice(conn, key, title):
    url = f"https://www.hankintailmoitukset.fi/fi/notice/{key}"
    emit.emit_signal(conn, company_key=key, signal_type="public_contract", date="2025-05-18", source_url=url, confidence="high", adapter="hilma",
                     detail=f"Fixture buyer: {title} (EUR 1,000)")
    return url


def _bf(conn, key):
    emit.emit_signal(conn, company_key=key, signal_type="bf_funding", date="2024-03-01", source_url="https://www.businessfinland.fi/fixture", confidence="medium",
                     adapter="businessfinland", detail="Business Finland funding granted in 2024")


@pytest.fixture()
def th():
    return thesis.load(thesis.available()[BLUE])


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "store.sqlite")
    yield c
    c.close()


def links(conn, th, key=None):
    res = sectors.compute(conn, th)
    return [(l["company_key"], l["sector"], l["basis"]) for l in res["links"] if key in (None, l["company_key"])]


def sub_slugs(conn, th, key):
    return {s for _, s, _ in links(conn, th, key)}


# ---- 1. the mapping ----------------------------------------------------------------------------------------------------------------
def test_a_boat_builder_lands_in_shipbuilding_by_code(conn, th):
    _company(conn, "9400001-1", "Fixture Boats Oy", "30120", "Building of pleasure and sporting boats")
    assert links(conn, th, "9400001-1") == [("9400001-1", "shipbuilding_boats", "code")]
    ln = sectors.compute(conn, th)["links"][0]
    assert ln["source_url"] == PRH + "9400001-1" and "30120" in ln["source_label"] and ln["source_label"].startswith("PRH/YTJ register")


def test_software_is_maritime_only_with_a_maritime_word(conn, th):
    _company(conn, "9400002-1", "Fixture Apps Oy", "62010", "Computer programming activities")
    assert sub_slugs(conn, th, "9400002-1") == set()                       # the code alone classifies nothing
    _company(conn, "9400003-1", "Fixture Ship Software Oy", "62010", "Computer programming activities")
    _project(conn, "9400003-1", "Route optimisation software for vessels in the Baltic Sea")
    assert links(conn, th, "9400003-1") == [("9400003-1", "maritime_software", "own_text")]
    _company(conn, "9400004-1", "Fixture Grid Oy", "62010", "Computer programming activities")
    _project(conn, "9400004-1", "Software for electricity grid balancing")  # own text without a maritime word
    assert sub_slugs(conn, th, "9400004-1") == set()
    _company(conn, "9400005-1", "Fixture Vessel Software Oy", "58290", "Other software publishing")  # name word, no second source family yet
    assert sub_slugs(conn, th, "9400005-1") == set()
    _bf(conn, "9400005-1")                                                   # a Business Finland record backs the name word (A6)
    assert links(conn, th, "9400005-1") == [("9400005-1", "maritime_software", "name_corroborated")]


def test_a_water_utility_lands_in_water_and_pollution(conn, th):
    _company(conn, "9400006-1", "Fixture Water Utility Oy", "36000", "Water collection, treatment and supply")
    assert links(conn, th, "9400006-1") == [("9400006-1", "water_pollution", "code")]


def test_membership_in_several_sub_sectors(conn, th):
    _company(conn, "9400007-1", "Fixture Ferry Oy", "50100", "Sea and coastal passenger water transport")
    assert sub_slugs(conn, th, "9400007-1") == {"shipping_logistics", "coastal_tourism_boating"}        # 50 and 5010
    _company(conn, "9400008-1", "Fixture Yard Oy", "30110", "Building of ships and floating structures")
    _project(conn, "9400008-1", "A floating offshore wind foundation built in a shipyard")
    assert sub_slugs(conn, th, "9400008-1") == {"shipbuilding_boats", "offshore_ocean_energy"}


def test_floating_structures_in_a_code_name_is_not_ocean_energy(conn, th):
    _company(conn, "9400009-1", "Fixture Hulls Oy", "30110", "Building of civilian ships and floating structures")
    assert sub_slugs(conn, th, "9400009-1") == {"shipbuilding_boats"}


def test_ship_repair_is_3315_not_all_of_331(conn, th):
    _company(conn, "9400010-1", "Fixture Docks Oy", "33150", "Repair and maintenance of ships and boats")
    _company(conn, "9400011-1", "Fixture Machines Oy", "33129", "Repair and maintenance of other special-purpose machinery")
    assert sub_slugs(conn, th, "9400010-1") == {"ship_repair_services"}
    assert sub_slugs(conn, th, "9400011-1") == set()


def test_the_gated_codes_need_their_word(conn, th):
    _company(conn, "9400012-1", "Fixture Forwarding Oy", "52290", "Other transportation support activities")
    _company(conn, "9400013-1", "Fixture Harbour Forwarding Oy", "52290", "Other transportation support activities")
    _project(conn, "9400013-1", "Cargo forwarding for coastal shipping and vessels")
    assert sub_slugs(conn, th, "9400012-1") == set()
    assert links(conn, th, "9400013-1") == [("9400013-1", "shipping_logistics", "own_text")]
    _company(conn, "9400014-1", "Fixture Lab Oy", "72100", "Research and experimental development on natural sciences and engineering")
    _company(conn, "9400015-1", "Fixture Algae Lab Oy", "72100", "Research and experimental development on natural sciences and engineering")
    _project(conn, "9400015-1", "Cultivating macroalgae for protein")
    assert sub_slugs(conn, th, "9400014-1") == set()
    assert "marine_biotech" in sub_slugs(conn, th, "9400015-1")
    _company(conn, "9400016-1", "Fixture Fun Oy", "93290", "Amusement and recreation activities n.e.c.")
    _company(conn, "9400017-1", "Fixture Marina Fun Oy", "93290", "Amusement and recreation activities n.e.c.")
    _project(conn, "9400017-1", "Marina services and boat rental for visitors")
    assert sub_slugs(conn, th, "9400016-1") == set()
    assert links(conn, th, "9400017-1") == [("9400017-1", "coastal_tourism_boating", "own_text")]


def test_a_name_word_alone_classifies_nothing(conn, th):
    _company(conn, "9400018-1", "Offshore Wind Fixture Oy", "70220", "Business and other management consultancy activities")
    assert sub_slugs(conn, th, "9400018-1") == set()                         # A5: the name word needs a record from another source family
    _bf(conn, "9400018-1")
    assert links(conn, th, "9400018-1") == [("9400018-1", "offshore_ocean_energy", "name_corroborated")]


def test_a_procurement_notice_is_a_notice_link(conn, th):
    _company(conn, "9400019-1", "Fixture Civil Oy", "42110", "Construction of roads and motorways")
    url = _notice(conn, "9400019-1", "Satamalaiturin korjaus ja ruoppaus")
    got = [l for l in sectors.compute(conn, th)["links"] if l["company_key"] == "9400019-1"]
    assert [(l["sector"], l["basis"], l["source_url"]) for l in got] == [("ports_marine_construction", "notice", url)]
    assert "2025-05-18" in got[0]["source_label"]


def test_the_emissions_area_counts_through_its_emission_words_only(conn, th):
    _company(conn, "9400020-1", "Fixture Monitor Oy", "71200", "Technical testing and analysis")
    _project(conn, "9400020-1", "Monitoring ship emissions from the air")
    _company(conn, "9400021-1", "Fixture Cells Oy", "27200", "Manufacture of batteries and accumulators")
    _project(conn, "9400021-1", "A battery for electrification of buildings")
    assert "ocean_data_monitoring" in sub_slugs(conn, th, "9400020-1")
    assert "ocean_data_monitoring" not in sub_slugs(conn, th, "9400021-1")


def test_declared_capability_and_declared_list_category(conn, th, tmp_path):
    eco = tmp_path / "eco.sqlite"
    e = sqlite3.connect(eco)
    e.executescript("CREATE TABLE capability (code TEXT PRIMARY KEY, label TEXT NOT NULL);"
                    "CREATE TABLE entity_capability (entity_id TEXT, code TEXT, PRIMARY KEY(entity_id, code));"
                    "INSERT INTO capability VALUES ('C4', 'Ocean and water sensing, data and monitoring');"
                    "INSERT INTO entity_capability VALUES ('BE9001', 'C4'), ('BE9001', 'C9');")
    e.commit()
    e.close()
    lst = tmp_path / "universe.csv"
    lst.write_text("name,y_tunnus_if_found,category,source_url\nFixture List Oy,9400023-1,aquatech,https://example.test/list\n", encoding="utf-8")
    t = dict(th)
    t["taxonomy"] = {**th["taxonomy"], "declared": {"ecosystem_db": str(eco), "lists": [
        {"file": str(lst), "id_column": "y_tunnus_if_found", "category_column": "category", "url_column": "source_url", "label": "Fixture list"}]}}
    _company(conn, "9400022-1", "Fixture Sensing Oy", "70220", "Business and other management consultancy activities")
    conn.execute("CREATE TABLE IF NOT EXISTS eco_entity (entity_id TEXT PRIMARY KEY, name TEXT, entity_type TEXT, side TEXT, business_id TEXT, country TEXT, city TEXT, "
                 "website TEXT, status TEXT, stage TEXT, confidence TEXT, company_key TEXT, source_url TEXT)")
    conn.execute("INSERT INTO eco_entity (entity_id, name, side, company_key, source_url) VALUES ('BE9001', 'Fixture Sensing Oy', 'supply', '9400022-1', 'https://example.test/sensing')")
    _company(conn, "9400023-1", "Fixture List Oy", "70220", "Business and other management consultancy activities")
    got = {(l["company_key"], l["sector"], l["basis"]): l for l in sectors.compute(conn, t)["links"]}
    assert set(got) == {("9400022-1", "ocean_data_monitoring", "declared"), ("9400023-1", "aquaculture_fisheries", "declared")}   # C9 maps to no sub-sector
    assert got[("9400022-1", "ocean_data_monitoring", "declared")]["source_url"] == "https://example.test/sensing"
    assert "C4" in got[("9400022-1", "ocean_data_monitoring", "declared")]["source_label"]
    assert got[("9400023-1", "aquaculture_fisheries", "declared")]["source_url"] == "https://example.test/list"


def test_a_company_in_another_register_is_not_backed_by_its_own_register(conn, th):
    emit.upsert_company(conn, company_key="no-936277241", name="Offshore Fixture AS", source_url="https://data.brreg.no/enhetsregisteret/api/enheter/936277241",
                        country="NO", industry_code="70.220", industry_desc="Bedriftsradgivning", group_tag="feed")
    emit.emit_signal(conn, company_key="no-936277241", signal_type="register_entry", date="2026-01-01", source_url="https://data.brreg.no/x", confidence="high", adapter="brreg")
    assert sub_slugs(conn, th, "no-936277241") == set()


# ---- 2. every link carries its basis and a source -----------------------------------------------------------------------------------
def test_every_link_has_a_basis_a_public_link_and_words(conn, th):
    _company(conn, "9400030-1", "Fixture Catch Oy", "03210", "Marine aquaculture")
    _project(conn, "9400030-1", "Seaweed and mussel farming")
    for ln in sectors.compute(conn, th)["links"]:
        assert ln["basis"] in sectors.KINDS and ln["source_url"].startswith("http") and len(ln["source_label"]) > 10


# ---- 3. the backfill ---------------------------------------------------------------------------------------------------------------
def _snapshot(conn):
    return sorted(tuple(r) for r in conn.execute("SELECT cs.company_key, s.slug, cs.basis, cs.source_url, cs.source_label, cs.assigned_at FROM company_sector cs "
                                                 "JOIN sector s ON s.id = cs.sector_id"))


def test_backfill_is_idempotent_and_keeps_assigned_at(conn, th):
    _company(conn, "9400040-1", "Fixture Boats Oy", "30120", "Building of pleasure and sporting boats")
    _company(conn, "9400041-1", "Fixture Water Oy", "36000", "Water collection, treatment and supply")
    _company(conn, "9400042-1", "Fixture Nothing Oy", "47190", "Other retail sale in non-specialised stores")
    s1 = sectors.assign(conn, th)
    conn.execute("UPDATE company_sector SET assigned_at = '2026-01-01T00:00:00Z'")   # a link that still holds keeps the time it was first assigned
    first = _snapshot(conn)
    s2 = sectors.assign(conn, th)
    assert _snapshot(conn) == first and s1 == s2 and len(first) == 2
    assert s1["sub_sectors_per_company"] == {"0": 1, "1": 2, "2+": 0} and s1["per_sector"]["shipbuilding_boats"] == 1
    top = conn.execute("SELECT id FROM sector WHERE slug = 'blue_economy' AND parent_id IS NULL").fetchone()[0]
    assert conn.execute("SELECT COUNT(*) FROM sector WHERE parent_id = ?", (top,)).fetchone()[0] == 12      # eleven sub-sectors and "Not yet classified"
    assert conn.execute("SELECT COUNT(*) FROM company_sector WHERE company_key = '9400042-1'").fetchone()[0] == 0


def test_backfill_follows_the_records_and_drops_a_link_that_no_longer_holds(conn, th):
    _company(conn, "9400043-1", "Fixture Boats Oy", "30120", "Building of pleasure and sporting boats")
    sectors.assign(conn, th)
    conn.execute("UPDATE companies SET industry_code = '47190' WHERE company_key = '9400043-1'")
    sectors.assign(conn, th)
    assert _snapshot(conn) == []


def test_the_command_line_backfill_and_dry_run(tmp_path, capsys, th):
    path = tmp_path / "radar_redstone_apelago_blue.sqlite"
    c = db.connect(path)
    _company(c, "9400050-1", "Fixture Boats Oy", "30120", "Building of pleasure and sporting boats")
    _company(c, "9400051-1", "Fixture Water Oy", "36000", "Water collection, treatment and supply")
    c.commit()
    c.close()
    assert sectors.main(["backfill", "--db", str(path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "Shipbuilding and boats" in out and "companies with 0 sub-sectors" in out
    c = sqlite3.connect(path)
    assert c.execute("SELECT COUNT(*) FROM company_sector").fetchone()[0] == 0 and c.execute("SELECT COUNT(*) FROM sector").fetchone()[0] == 0
    c.close()
    assert sectors.main(["backfill", "--db", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Water and pollution" in out and "dry run" not in out
    c = sqlite3.connect(path)
    assert c.execute("SELECT COUNT(*) FROM company_sector").fetchone()[0] == 2
    c.close()
    assert sectors.main(["backfill", "--db", str(tmp_path / "missing.sqlite")]) == 2


def test_the_backfill_creates_the_tables_in_a_store_that_has_not_got_them(tmp_path, th):
    path = tmp_path / "old.sqlite"
    c = sqlite3.connect(path)
    c.executescript((ROOT / "radar/schema/001_core.sql").read_text(encoding="utf-8"))
    c.execute("INSERT INTO companies (company_key, name, source_url, fetched_at, industry_code, industry_desc) VALUES ('9400060-1', 'Old Boats Oy', ?, '2026-10-01T00:00:00Z', '30110', 'Building of ships')", (PRH + "9400060-1",))
    c.commit()
    assert sectors.main(["backfill", "--db", str(path), "--thesis", BLUE]) == 0
    assert c.execute("SELECT COUNT(*) FROM company_sector").fetchone()[0] == 1


# ---- 4. exposure: home rows, API, combined file -------------------------------------------------------------------------------------
def test_home_rows_carry_subsectors_and_a_facet(conn, th):
    _company(conn, "9400070-1", "Fixture Boats Oy", "30120", "Building of pleasure and sporting boats", group="cohort")
    _company(conn, "9400071-1", "Fixture Nothing Oy", "47190", "Other retail sale in non-specialised stores", group="cohort")
    before = {r["company_key"]: r for r in home_list.build(conn, th)["rows"]}
    assert all(r["subsectors"] == [] and r["facets"]["subsector"] == [] for r in before.values())   # not backfilled: nothing is claimed
    sectors.assign(conn, th)
    rows = {r["company_key"]: r for r in home_list.build(conn, th)["rows"]}
    boats, other = rows["9400070-1"], rows["9400071-1"]
    assert [(s["slug"], s["label"], s["basis"]) for s in boats["subsectors"]] == [("shipbuilding_boats", "Shipbuilding and boats", ["code"])]
    assert boats["facets"]["subsector"] == ["shipbuilding_boats"]
    assert [s["slug"] for s in other["subsectors"]] == ["not_classified"] and other["subsectors"][0]["label"] == "Not yet classified"
    assert other["facets"]["subsector"] == ["not_classified"]


def test_a_thesis_without_a_taxonomy_has_no_subsectors(tmp_path):
    health = thesis.load(thesis.available()["health_tech_turku"])
    assert sectors.model(health) is None and health["taxonomy"] == []
    c = db.connect(tmp_path / "h.sqlite")
    _company(c, "9400080-1", "Fixture Lab Oy", "32500", "Manufacture of medical and dental instruments and supplies", group="cohort")
    assert sectors.assign(c, health)["taxonomy"] is False
    assert sectors.company_subsectors(c, health, "9400080-1") == []
    assert all(r["subsectors"] == [] for r in home_list.build(c, health)["rows"])
    c.close()


def test_the_company_api_lists_subsectors_with_basis_and_source(tmp_path, monkeypatch, th):
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    c = db.connect(thesis.db_path(th))
    _company(c, "9400090-1", "Fixture Ferry Oy", "50100", "Sea and coastal passenger water transport")
    _company(c, "9400091-1", "Fixture Nothing Oy", "47190", "Other retail sale in non-specialised stores")
    c.commit()
    import app
    client = TestClient(app.app)
    assert client.get("/api/company/9400090-1").json()["subsectors"] == []                  # not backfilled
    sectors.assign(c, th)
    c.commit()
    c.close()
    got = client.get("/api/company/9400090-1").json()["subsectors"]
    assert {s["slug"] for s in got} == {"shipping_logistics", "coastal_tourism_boating"}
    ferry = next(s for s in got if s["slug"] == "coastal_tourism_boating")
    assert ferry["label"] == "Coastal tourism and boating" and ferry["parent"] == {"slug": "blue_economy", "label": "Blue economy"}
    assert ferry["evidence"][0]["basis"] == "code" and ferry["evidence"][0]["source_url"] == PRH + "9400090-1"
    none = client.get("/api/company/9400091-1").json()["subsectors"]
    assert [s["slug"] for s in none] == ["not_classified"] and none[0]["evidence"] == []


# ---- 5. the configuration ----------------------------------------------------------------------------------------------------------
def test_the_blue_and_baltic_files_carry_the_same_taxonomy():
    blue = yaml.safe_load((ROOT / "config/thesis.yaml").read_text(encoding="utf-8"))
    baltic = yaml.safe_load((ROOT / "config/thesis_baltic_blue.yaml").read_text(encoding="utf-8"))
    assert blue["taxonomy"]["sectors"] == baltic["taxonomy"]["sectors"]
    assert {k: v for k, v in blue["taxonomy"].items() if k not in ("keyword_groups",)} == {k: v for k, v in baltic["taxonomy"].items() if k not in ("keyword_groups",)}
    # the Baltic file has no matchmaking block, so it keeps the groups the sub-sectors name; they must stay word for word the thesis' own
    thesis_groups = {g["id"]: g for g in blue["matching"]["keyword_groups"]}
    assert baltic["taxonomy"]["keyword_groups"] and all(g == thesis_groups[g["id"]] for g in baltic["taxonomy"]["keyword_groups"])
    assert [s["slug"] for s in blue["taxonomy"]["sectors"]] == [
        "shipbuilding_boats", "ship_repair_services", "shipping_logistics", "ports_marine_construction", "offshore_ocean_energy", "maritime_software",
        "ocean_data_monitoring", "aquaculture_fisheries", "marine_biotech", "water_pollution", "coastal_tourism_boating"]


def test_every_taxonomy_in_the_repo_loads_and_the_health_one_is_empty():
    for tid, path in thesis.available().items():
        t = thesis.load(path)
        assert (sectors.model(t) is None) == (tid == "health_tech_turku")


def test_a_taxonomy_that_names_a_missing_group_is_refused(tmp_path):
    d = yaml.safe_load((ROOT / "config/thesis.yaml").read_text(encoding="utf-8"))
    d["taxonomy"]["sectors"][0]["keyword_groups"] = ["no_such_group"]
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    with pytest.raises(thesis.ThesisError, match="no_such_group"):
        thesis.load(p)
    d = yaml.safe_load((ROOT / "config/thesis.yaml").read_text(encoding="utf-8"))
    d["taxonomy"]["sectors"][1]["evidence"] = ["magic"]
    p.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    with pytest.raises(thesis.ThesisError, match="evidence"):
        thesis.load(p)


def test_no_sector_word_lives_in_the_module():
    src = (ROOT / "radar/sectors.py").read_text(encoding="utf-8").casefold()
    for word in ("aquacultur", "seaweed", "harbour", "offshore", "hydrogen", "satama", "kalankasvat", "icebreaker"):
        assert word not in src, word


# ---- 6. the filter: sub-sectors inside the Sector group, in place --------------------------------------------------------------------
SNAP = ROOT / "data" / "snapshot"
needs_snapshot = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """The committed snapshot, copied, and backfilled: the sub-sector tables are filled in the copy only."""
    import shutil
    d = tmp_path_factory.mktemp("snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, d / f.name)
    mp = pytest.MonkeyPatch()
    mp.setenv("RADAR_DATA_DIR", str(d))
    mp.delenv("RADAR_DB", raising=False)
    mp.delenv("RADAR_THESIS", raising=False)
    mp.setenv("RADAR_NO_WARM", "1")
    th = thesis.load()
    c = db.connect(thesis.db_path(th))
    summary = sectors.assign(c, th)
    c.commit()
    c.close()
    try:
        yield {"th": th, "H": home_list.for_template(th, wait=None), "summary": summary, "dir": d}
    finally:
        mp.undo()


@pytest.fixture()
def page(world, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(world["dir"]))
    monkeypatch.setenv("RADAR_NO_WARM", "1")
    import app
    return TestClient(app.app)


@needs_snapshot
def test_snapshot_rows_carry_subsectors_and_the_facet(world):
    rows = world["H"]["rows"]
    known = {s["slug"] for s in world["th"]["taxonomy"]["sectors"]} | {"not_classified"}
    assert rows and all(r["subsectors"] and {x["slug"] for x in r["subsectors"]} <= known for r in rows)
    assert all(r["facets"]["subsector"] == [x["slug"] for x in r["subsectors"]] for r in rows)
    assert all(len(r["subsectors"]) == 1 for r in rows if r["subsectors"][0]["slug"] == "not_classified")


@needs_snapshot
def test_the_filter_returns_the_expected_subset(world):
    from radar import home_filter
    rows = world["H"]["rows"]
    count = {}
    for r in rows:
        for s in r["facets"]["subsector"]:
            count[s] = count.get(s, 0) + 1
    two = [s for s, _ in sorted(count.items(), key=lambda x: -x[1]) if s != "not_classified"][:2]
    assert len(two) == 2
    one = home_filter.apply(rows, {"subsector": [two[0]]})
    assert {r["company_key"] for r in one} == {r["company_key"] for r in rows if two[0] in r["facets"]["subsector"]} and len(one) == count[two[0]]
    both = home_filter.apply(rows, {"subsector": two})                                             # OR within the facet
    assert {r["company_key"] for r in both} == {r["company_key"] for r in rows if set(two) & set(r["facets"]["subsector"])}
    country = next(r["facets"]["country"][0] for r in one)
    narrowed = home_filter.apply(rows, {"subsector": two, "country": [country]})                  # AND across facets
    assert {r["company_key"] for r in narrowed} == {r["company_key"] for r in both if country in r["facets"]["country"]}
    assert home_filter.apply(rows, {"subsector": ["no_such_sub_sector"]}) == []


@needs_snapshot
def test_the_rail_lists_the_subsectors_inside_the_sector_group_with_counts(world):
    from radar import home_filter
    rows = world["H"]["rows"]
    sel = {"subsector": [next(s for s in rows[0]["facets"]["subsector"])]}
    R = home_filter.rail(rows, sel, {}, [{"value": "redstone_apelago_blue", "label": "Blue economy", "on": True, "count": len(rows), "href": "/", "hx": "/home/list", "id": "f-thesis-x"},
                                          {"value": "other", "label": "Other", "on": False, "count": None, "href": "/", "hx": "/home/list", "id": "f-thesis-y"}])
    assert [f["param"] for f in R["facets"]][0] == "thesis" and "subsector" not in [f["param"] for f in R["facets"]]   # nested, not a group of its own
    host = R["facets"][0]
    (n,) = host["nested"]
    assert n["param"] == "subsector" and n["sector"] == "Blue economy" and host["active"] == 1
    on = [o for o in n["options"] if o["on"]]
    assert [o["value"] for o in on] == sel["subsector"] and on[0]["label"] and on[0]["count"] > 0
    assert all(o["label"] and not o["label"].islower() for o in n["options"])
    for o in n["options"]:                                           # a count is how many rows would show if the option were on (the others as selected)
        sel2 = {"subsector": [o["value"]]}
        assert o["count"] == len(home_filter.apply(rows, sel2))
    assert n["options"][-1]["value"] == "not_classified" or all(o["value"] != "not_classified" for o in n["options"])


@needs_snapshot
def test_the_page_swaps_in_place_and_the_address_stays_canonical(world, page):
    rows = world["H"]["rows"]
    slug = rows[0]["facets"]["subsector"][0]
    full = page.get(f"/?subsector={slug}")
    assert full.status_code == 200 and 'class="hr-sub"' in full.text and f'id="f-subsector-{slug.replace("_", "-")}"' in full.text
    part = page.get(f"/home/list?subsector={slug}")
    assert part.status_code == 200 and part.headers["HX-Replace-Url"] == f"/?subsector={slug}" and part.headers["Cache-Control"] == "no-store"
    want = [r["company_key"] for r in rows if slug in r["facets"]["subsector"]]
    import re
    got = re.findall(r'class="hc-row" href="/c/([^"]+)"', part.text)
    assert sorted(got) == sorted(want)
    assert 'aria-checked="true"' in part.text and "Sub-sector: " in part.text                      # the chip names the sub-sector in words
    chip = re.search(r'id="chip-subsector-[^"]+" href="([^"]+)"', part.text)
    assert chip and "subsector=" not in chip.group(1)                                              # removing the chip drops the sub-sector from the URL
    assert "data-params" in part.text and "subsector" in re.search(r'data-params="([^"]+)"', part.text).group(1).split(",")


@needs_snapshot
def test_a_selection_in_the_url_is_read_back_and_unknown_values_match_nothing(world, page):
    t = page.get("/home/list?subsector=no_such_sub_sector").text
    assert "No startup matches these filters" in t
    two = [s for r in world["H"]["rows"] for s in r["facets"]["subsector"]][:2]
    part = page.get("/home/list?" + "&".join(f"subsector={s}" for s in dict.fromkeys(two)))
    assert part.status_code == 200 and part.headers["HX-Replace-Url"].startswith("/?subsector=")


@needs_snapshot
def test_a_sector_without_a_taxonomy_or_a_store_not_backfilled_offers_no_subsector(world, page, tmp_path, monkeypatch):
    from radar import home_filter
    assert "hr-sub" not in page.get("/home/list?thesis=health_tech_turku").text                    # health: empty taxonomy
    plain = tmp_path / "plain"
    plain.mkdir()
    import shutil
    shutil.copy(SNAP / "radar_redstone_apelago_blue.sqlite", plain / "radar_redstone_apelago_blue.sqlite")
    monkeypatch.setenv("RADAR_DATA_DIR", str(plain))
    H = home_list.build(db.connect(plain / "radar_redstone_apelago_blue.sqlite"), world["th"])
    assert all(r["subsectors"] == [] and r["facets"]["subsector"] == [] for r in H["rows"])
    R = home_filter.rail(H["rows"], {}, {})
    assert "subsector" not in [f["param"] for f in R["facets"]]                                    # no value in any row: the facet hides
