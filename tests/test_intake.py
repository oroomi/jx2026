"""Wide intake: rule, adapter, third feed tier, Q01 chip and the backtest precision line. All companies are synthetic ("Fixture ...")."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from radar import db, earliness, emit, intake, store, thesis, thesis as thesis_mod
from radar.adapters import prh, prh_intake

TH = thesis.load(thesis.resolve(None))
CFG = thesis.intake(TH)
TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def add(conn, key, name, *, code="62100", form="16", founded=None, group="intake", desc="Computer programming activities", profile=True):
    emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key if key[0].isdigit() else None, country="FI", founded=founded,
                        industry_code=code, industry_desc=desc, group_tag=group, source_url=f"https://example.test/prh/{key}")
    if founded:
        emit.emit_signal(conn, company_key=key, signal_type="register_entry", date=founded, source_url=f"https://example.test/prh/{key}",
                         confidence="high", adapter="prh_intake", detail="Registered.")
    if profile:
        conn.execute("INSERT OR REPLACE INTO intake_profile VALUES (?,?,?,?,?)", (key, form, "form", founded, "2026-10-16T00:00:00Z"))


def sig(conn, key, kind, day, detail="Fixture signal."):
    emit.emit_signal(conn, company_key=key, signal_type=kind, date=day, source_url=f"https://example.test/{kind}/{key}", confidence="high",
                     adapter="tax_registers", detail=detail)


# ---- thesis section ---------------------------------------------------------------------------------------------

def test_every_thesis_file_has_a_valid_intake_section():
    for tid, path in thesis.available().items():
        cfg = thesis.intake(thesis.load(path))
        assert cfg and cfg["min_signals"] >= 1 and "16" in cfg["company_forms"] and cfg["code_prefixes"], tid
        assert "register_entry" not in cfg["startup_signals"]


def test_invalid_intake_section_is_refused(tmp_path):
    p = tmp_path / "t.yaml"
    base = (open(thesis.default_path(), encoding="utf-8").read().split("\nintake:")[0])
    p.write_text(base + "\nintake:\n  company_forms: []\n  code_prefixes: ['62']\n  startup_signals: [first_sales]\n", encoding="utf-8")
    with pytest.raises(thesis.ThesisError):
        thesis.load(p)
    p.write_text(base + "\nintake:\n  company_forms: [{code: '16'}]\n  code_prefixes: ['62']\n  startup_signals: [first_sales]\n  min_signals: 0\n", encoding="utf-8")
    with pytest.raises(thesis.ThesisError):
        thesis.load(p)


def test_health_thesis_has_no_blue_words_in_its_intake():
    h = thesis.load(thesis.available()["health_tech_turku"])
    assert "30" not in thesis.intake(h)["code_prefixes"] and "26" in thesis.intake(h)["code_prefixes"]


# ---- the rule ---------------------------------------------------------------------------------------------------

def test_eligibility_form_and_code():
    assert intake.eligible("16", "62100", CFG) == (True, None)
    assert intake.eligible("14", "72100", CFG)[0]
    assert intake.eligible("16", "30110", CFG)[0] and intake.eligible("16", "39000", CFG)[0]  # a thesis code outside the prefixes
    assert "not a limited company" in intake.eligible("26", "62100", CFG)[1]
    assert "outside the intake code families" in intake.eligible("16", "46900", CFG)[1]
    assert intake.eligible(None, "62100", CFG)[1] == "legal form not in public records"
    assert intake.eligible("16", None, CFG)[1] == "industry code not in public records"


def test_entry_date_is_the_min_signals_th_startup_signal_and_never_the_register_entry():
    s = [{"signal_type": "register_entry", "date": "2020-01-01", "id": 1}, {"signal_type": "first_hire", "date": "2020-06-01", "id": 3},
         {"signal_type": "first_sales", "date": "2020-03-01", "id": 2}, {"signal_type": "board_change", "date": "2020-02-01", "id": 4}]
    assert intake.entered(s, CFG)[0] == "2020-03-01"
    assert intake.entered(s, {**CFG, "min_signals": 2})[0] == "2020-06-01"
    assert intake.entered(s, CFG, until="2020-02-15")[0] is None
    assert intake.entered(s[:1], CFG)[0] is None


# ---- the adapter ------------------------------------------------------------------------------------------------

def record(bid, name, founded, *, code="62100", form="16", entries=()):
    return {"businessId": {"value": bid, "registrationDate": founded}, "names": [{"name": name, "type": "1", "version": 1}],
            "mainBusinessLine": {"type": code, "descriptions": [{"languageCode": "3", "description": "Computer programming activities"}]},
            "companyForms": [{"type": form, "registrationDate": founded, "descriptions": [{"languageCode": "3", "description": "form"}]}],
            "registeredEntries": [{"register": r, "type": t, "registrationDate": d} for r, t, d in entries],
            "companySituations": []}


def test_accept_filters_form_code_name_and_window():
    th = TH
    ok = record("9000101-1", "Fixture Intake Oy", ago(30))
    assert prh_intake.accept(ok, CFG, th, ago(365), ago(0))["form"] == "16"
    assert prh_intake.accept(record("9000102-1", "Fixture Sole", ago(30), form="26"), CFG, th, ago(365), ago(0)) is None
    assert prh_intake.accept(record("9000103-1", "Fixture Shop Oy", ago(30), code="47910"), CFG, th, ago(365), ago(0)) is None
    assert prh_intake.accept(record("9000104-1", "Fixture Old Oy", "2015-01-01"), CFG, th, ago(365), ago(0)) is None  # name change, not new
    assert prh_intake.accept(record("9000105-1", "Anna Maria Virtanen Holding Oy", ago(30)), CFG, th, ago(365), ago(0)) is None


def test_queries_cover_prefixes_and_uncovered_thesis_codes_only():
    qs = [q["mainBusinessLine"] for q in prh_intake.queries(CFG)]
    assert "62" in qs and "39000" in qs and "30110" not in qs  # 30110 is covered by prefix 30


def test_run_stores_intake_companies_apart_from_the_feed(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "i.sqlite")
    add(conn, "9000200-1", "Fixture Cohort Oy", code="62100", founded="2018-05-01", group="cohort", profile=False)
    conn.commit()
    new = record("9000201-1", "Fixture New Oy", ago(40), entries=[("6", "80", ago(35)), ("7", "1", ago(10))])
    old = record("9000202-1", "Fixture Year Oy", "2018-07-01", entries=[("6", "80", "2018-08-01")])
    cohort = record("9000200-1", "Fixture Cohort Oy", "2018-05-01", entries=[("5", "1", "2018-06-01")])
    monkeypatch.setattr(prh, "fetch", lambda params, client=None: ({"companies": [cohort]}, False))

    def fake(adapter, url, **kw):
        p = kw["params"]
        if p["mainBusinessLine"] == "62" and p["page"] == 1:
            return ({"companies": [new, old], "totalResults": 2}, False)
        return ({"companies": [], "totalResults": 0}, False)
    monkeypatch.setattr(prh_intake, "cached_get", fake)
    res = prh_intake.run(conn, TH, today=TODAY)
    assert res["inserted"] == 2 and res["blocked"] == 0 and res["declared"] == 1
    assert conn.execute("SELECT group_tag FROM companies WHERE company_key='9000201-1'").fetchone()[0] == "intake"
    assert conn.execute("SELECT group_tag FROM companies WHERE company_key='9000200-1'").fetchone()[0] == "cohort"
    kinds = {(r["company_key"], r["signal_type"]) for r in conn.execute("SELECT * FROM signals")}
    assert ("9000201-1", "first_sales") in kinds and ("9000201-1", "first_hire") in kinds and ("9000200-1", "first_sales") in kinds
    assert conn.execute("SELECT form_code FROM intake_profile WHERE company_key='9000201-1'").fetchone()[0] == "16"
    assert store.feed(conn, TH) == []  # Main and Weak never read the intake group
    assert prh_intake.run(conn, TH, today=TODAY)["inserted"] == 0  # idempotent


def test_run_stops_cleanly_when_the_source_is_blocked(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "b.sqlite")

    def boom(*a, **k):
        raise prh_intake.Blocked("offline")
    monkeypatch.setattr(prh_intake, "cached_get", boom)
    res = prh_intake.run(conn, TH, today=TODAY)
    assert res["blocked"] == 1 and res["inserted"] == 0


def test_run_without_an_intake_section_is_skipped(tmp_path):
    th = {k: v for k, v in TH.items() if k != "intake"}
    assert prh_intake.run(db.connect(tmp_path / "s.sqlite"), th) == {"skipped": "thesis has no intake section"}


# ---- the third tier ---------------------------------------------------------------------------------------------

@pytest.fixture()
def tier_db(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite")
    add(conn, "9000301-1", "Fixture Alpha Oy", founded=ago(60))
    sig(conn, "9000301-1", "first_sales", ago(20))
    sig(conn, "9000301-1", "first_hire", ago(10))
    add(conn, "9000302-1", "Fixture Beta Oy", founded=ago(60))
    sig(conn, "9000302-1", "first_sales", ago(5))
    add(conn, "9000303-1", "Fixture Quiet Oy", founded=ago(60))                       # no startup signal: not in intake
    add(conn, "9000304-1", "Fixture Shipyard Oy", code="30110", founded=ago(60), desc="Building of ships and floating structures")
    sig(conn, "9000304-1", "first_sales", ago(15))                                    # thesis code: has evidence, left to Main
    add(conn, "9000305-1", "Fixture Old Oy", founded="2019-01-01")
    sig(conn, "9000305-1", "first_sales", ago(400))                                   # entered intake outside the window
    add(conn, "9000306-1", "Anna Maria Virtanen Holding Oy", founded=ago(60))
    sig(conn, "9000306-1", "first_sales", ago(12))                                    # person-shaped legal name
    add(conn, "9000307-1", "Fixture Trader", form="26", founded=ago(60))
    sig(conn, "9000307-1", "first_sales", ago(12))                                    # sole trader
    conn.commit()
    return conn


def test_tier_rows_are_ranked_by_startup_signals_and_say_why(tier_db):
    rows = intake.tier(tier_db, TH, today=TODAY)
    assert [r["name"] for r in rows] == ["Fixture Alpha Oy", "Fixture Beta Oy"]
    a = rows[0]
    assert a["n"] == 2 and a["signal"]["signal_type"] == "first_sales" and a["date"] == ago(20)
    assert "First sales" in a["why"] and "1 more startup signal." in a["why"]
    assert a["signal"]["source_url"].startswith("https://example.test/first_sales")


def test_tier_leaves_out_main_weak_evidence_person_names_and_sole_traders(tier_db):
    names = {r["name"] for r in intake.tier(tier_db, TH, today=TODAY, exclude={"9000302-1"})}
    assert names == {"Fixture Alpha Oy"}
    assert intake.tier(tier_db, {k: v for k, v in TH.items() if k != "intake"}, today=TODAY) == []


def test_feed_page_shows_a_closed_third_tier_and_keeps_main_and_weak(tier_db, tmp_path, monkeypatch):
    emit.upsert_company(tier_db, company_key="9000310-1", name="Fixture Marine Oy", y_tunnus="9000310-1", industry_code="30110",
                        industry_desc="Building of ships", group_tag="feed", source_url="https://example.test/prh/310")
    emit.emit_signal(tier_db, company_key="9000310-1", signal_type="register_entry", date=ago(3), source_url="https://example.test/prh/310",
                     confidence="medium", adapter="prh", detail="Registered.")
    tier_db.commit()
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "t.sqlite"))
    import app
    c = TestClient(app.app)
    html = c.get("/").text
    i, j = html.index("Fixture Marine Oy"), html.index("New startups, no thesis evidence yet")
    assert i < j  # Main first, the third tier below it
    tier_html = html[j:html.index('class="chiprule"')]
    assert "Fixture Alpha Oy" in tier_html and "Fixture Marine Oy" not in tier_html
    assert 'id="intake-tier"' in html and "open" not in html[html.index('<details class="weak intake"'):j].split(">")[0]
    assert "Thesis fit: no public evidence yet" in tier_html
    assert c.get("/feed/rows?type=first_sales").text.count("New startups, no thesis evidence yet") == 0  # unfiltered feed only


def test_health_thesis_feed_renders_with_no_blue_wording(tier_db, tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import shutil
    shutil.copy(tmp_path / "t.sqlite", tmp_path / "radar_health_tech_turku.sqlite")
    import app
    html = TestClient(app.app).get("/?thesis=health_tech_turku").text
    assert "health-tech" in html and "blue" not in html.split("<main")[1].lower().replace("blueinvest", "")


# ---- Q01 chip ---------------------------------------------------------------------------------------------------

def test_company_page_chip_and_startup_signals_when_there_is_no_evidence(tier_db, tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "t.sqlite"))
    import app
    c = TestClient(app.app)
    html = c.get("/c/9000301-1").text
    q1 = html[html.index('id="q1"'):html.index('id="q2"')]
    assert "Thesis fit: no public evidence yet" in q1 and "2 startup signals brought it in" in q1
    assert "First sales" in q1 and "https://example.test/first_sales/9000301-1" in q1
    assert "it fits this sector" not in q1
    ship = c.get("/c/9000304-1").text
    q1s = ship[ship.index('id="q1"'):ship.index('id="q2"')]
    assert "Thesis fit: no public evidence yet" not in q1s and "reason" in q1s  # the existing reasons show as before


def test_company_page_for_a_company_outside_intake_names_the_reason(tier_db, tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "t.sqlite"))
    import app
    html = TestClient(app.app).get("/c/9000307-1").text
    assert "Thesis fit: no public evidence yet" in html and "not a limited company or cooperative" in html


# ---- backtest ---------------------------------------------------------------------------------------------------

@pytest.fixture()
def bt_db(tmp_path):
    conn = db.connect(tmp_path / "bt.sqlite")
    add(conn, "9000401-1", "Fixture Cohort A Oy", founded="2018-03-01", group="cohort", code="30110")
    sig(conn, "9000401-1", "first_sales", "2018-03-09")
    add(conn, "9000402-1", "Fixture Cohort B Oy", founded="2025-06-01", group="cohort", code="62100")
    sig(conn, "9000402-1", "first_sales", "2026-03-01")                                 # intake after cohort entry
    add(conn, "9000403-1", "Fixture Cohort C Oy", founded="2021-06-01", group="cohort", code="46900", desc="Wholesale")
    sig(conn, "9000403-1", "first_sales", "2021-07-01")                                 # code family outside intake
    emit.upsert_company(conn, company_key="no-fixture-d", name="Fixture Cohort D", group_tag="cohort", country="NO", source_url="https://example.test/d")
    for i, n in enumerate((3, 1, 0, 2)):                                                # same year and family 30 pool
        k = f"900041{i}-1"
        add(conn, k, f"Fixture Peer {i} Oy", founded=f"2018-0{4 + i}-01", code="30120")
        for j in range(n):
            sig(conn, k, ("first_sales", "first_hire", "eu_project")[j], f"2018-1{j}-01")
    add(conn, "9000419-1", "Fixture Peer Late Oy", founded="2018-09-01", code="30120")
    sig(conn, "9000419-1", "first_sales", "2026-05-01")                                  # entered after the reference: not in the pool
    conn.commit()
    return conn


def test_cohort_row_rank_and_intake_size(bt_db):
    th = {**TH, "backtest": {"cohort_group": "cohort", "reference_date": "2026-01-01"}}
    res = earliness.backtest(bt_db, th)
    rows = {r["company_key"]: r["intake"] for r in res["rows"]}
    a = rows["9000401-1"]
    assert a["state"] == "entered" and a["before_entry"] and a["intake_date"] == "2018-03-09"
    assert (a["year"], a["family"], a["size"]) == ("2018", "30", 4)    # cohort A and the three peers with a startup signal; the late peer is out
    assert a["rank"] == 3 and a["n_signals"] == 1                       # peers with 3 and 2 signals rank ahead; the tie at 1 signal goes to the earlier intake date
    b = rows["9000402-1"]
    assert b["state"] == "entered" and not b["before_entry"]
    assert rows["9000403-1"]["state"] == "ineligible" and "outside the intake code families" in rows["9000403-1"]["reason"]
    assert rows["no-fixture-d"]["state"] == "not_in_register"


def test_summary_headline_and_medians(bt_db):
    th = {**TH, "backtest": {"cohort_group": "cohort", "reference_date": "2026-01-01"}}
    s = earliness.backtest(bt_db, th)["intake"]
    assert s["total"] == 4 and s["entered"] == 2 and s["before"] == 1 and s["with_rank"] == 1
    assert s["ranks"] == [{"name": s["ranks"][0]["name"], "rank": 3, "size": 4}] and "median" not in s["headline"]
    assert "before cohort entry: 1 of 4" in s["headline"] and f"{s['ranks'][0]['name']} 3 of 4." in s["headline"]
    assert "never counted as found early without its rank" in s["headline"]
    assert intake.summary([])["ranks"] == [] and "No rank can be shown yet" in intake.headline(intake.summary([]))
    four = [{"state": "entered", "before_entry": True, "rank": r, "size": z} for r, z in ((132, 1176), (3, 8), (1, 104), (3, 16))]
    assert "1 of 104, 3 of 16, 3 of 8 and 132 of 1,176." in intake.headline(intake.summary(four))  # one rank beside its own pool, never two medians


def test_never_early_without_rank_when_no_pool_is_stored(tmp_path):
    conn = db.connect(tmp_path / "np.sqlite")
    add(conn, "9000501-1", "Fixture Solo Oy", founded=None, group="cohort", code="62100")
    conn.execute("UPDATE companies SET founded='2020-02-01' WHERE company_key='9000501-1'")
    sig(conn, "9000501-1", "first_sales", "2020-03-01")
    conn.execute("DELETE FROM companies WHERE 0")
    conn.commit()
    row = intake.cohort_row(conn, TH, {"company_key": "9000501-1", "name": "x", "founded": "2020-02-01", "industry_code": "62100"}, "2026-01-01", None)
    assert row["state"] == "entered" and row["rank"] == 1 and row["size"] == 1
    s = intake.summary([{**row, "rank": None}])
    assert s["with_rank"] == 0 and s["before"] == 1 and "No rank can be shown yet" in intake.headline(s)


def test_backtest_page_prints_rank_and_size_beside_every_early_company(bt_db, tmp_path, monkeypatch):
    bt_db.close()
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "bt.sqlite"))
    import app
    html = TestClient(app.app).get("/backtest").text
    sec = html[html.index('id="intake"'):html.index('aria-labelledby="rule-h"')]
    assert "Entered wide intake before cohort entry: 1 of 4" in sec
    assert "rank 3 of 4 new 2018 companies in code family 30" in sec
    assert "not in intake" in sec and "outside the intake code families" in sec and "Finnish register" in sec
    assert "no thesis evidence yet" in sec


# ---- code families added after the backtest (582, 03): printed where the rule is explained, blue sector files only ------

def test_added_families_are_in_the_blue_files_and_the_note_says_they_were_tuned():
    for tid in ("redstone_apelago_blue", "baltic_blue"):
        cfg = thesis.intake(thesis.load(thesis.available()[tid]))
        assert "582" in cfg["code_prefixes"] and "03" in cfg["code_prefixes"], tid
        assert "measured on the companies used to tune the net" in cfg["tuning_note"], tid
    assert intake.eligible("16", "58290", CFG)[0] and intake.eligible("16", "03220", CFG)[0]
    assert not intake.eligible("16", "58110", CFG)[0]  # book publishing stays out: only 582 was added
    h = thesis.load(thesis.available()["health_tech_turku"])
    assert intake.tuning_note(h) is None and "582" not in thesis.intake(h)["code_prefixes"]


def test_method_and_backtest_print_the_tuning_note_and_health_does_not(tier_db, tmp_path, monkeypatch):
    import shutil
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    shutil.copy(tmp_path / "t.sqlite", tmp_path / "radar_redstone_apelago_blue.sqlite")
    shutil.copy(tmp_path / "t.sqlite", tmp_path / "radar_health_tech_turku.sqlite")
    import app
    c = TestClient(app.app)
    note = "The families 582 (software publishing) and 03 (fishing and aquaculture) were added after the backtest"
    m = c.get("/method?thesis=redstone_apelago_blue").text
    assert 'id="intake"' in m and note in m and "starts with 03, 26," in m
    hm = c.get("/method?thesis=health_tech_turku").text
    assert note not in hm and "fishing" not in hm.lower() and 'id="intake"' in hm


def test_backtest_carries_the_tuning_note_for_blue_only(bt_db):
    th = {**TH, "backtest": {"cohort_group": "cohort", "reference_date": "2026-01-01"}}
    assert "used to tune the net" in earliness.backtest(bt_db, th)["intake"]["note"]
    h = thesis.load(thesis.available()["health_tech_turku"])
    assert earliness.backtest(bt_db, {**h, "backtest": th["backtest"]})["intake"]["note"] is None
