"""Ocean Impact Assessment (radar/ocean_impact.py, D22): the evidence-readiness ladder, the always-complete shape, no dataset slug in
the area, the declared-research gate, the memo and API attachments, and the pages that show it. Fixtures only; the page tests read
the committed snapshot like tests/test_memo.py does."""
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import db, emit, matching, memo, ocean_impact, store, thesis
from radar.adapters import ecosystem

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
PRH = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId="


def _company(conn, key, name, code, desc, group="feed"):
    emit.upsert_company(conn, company_key=key, name=name, source_url=PRH + key, y_tunnus=key, country="FI", founded="2020-01-01",
                        industry_code=code, industry_desc=desc, group_tag=group)
    emit.emit_signal(conn, company_key=key, signal_type="register_entry", date="2020-01-01", source_url=PRH + key, confidence="high", adapter="prh")


def _project(conn, key, text, n=1):
    for i in range(n):
        url = f"https://cordis.europa.eu/project/id/{key}-{i}"
        emit.emit_signal(conn, company_key=key, signal_type="eu_project", date=f"2024-0{i + 1}-01", source_url=url, confidence="high",
                         adapter="cordis", detail="EU project participation")
        sid = conn.execute("SELECT id FROM signals WHERE source_url=? AND company_key=?", (url, key)).fetchone()[0]
        conn.execute("INSERT INTO signal_text (signal_id, field, text) VALUES (?,?,?)", (sid, "objective", text))


def _programme(conn, key):
    emit.emit_signal(conn, company_key=key, signal_type="programme_entry", date="2026-02-09", source_url="https://www.apelago.fi/nordic-blue-2026-batch/",
                     confidence="high", adapter="ecosystem", detail="Accelerator or programme entry")


def _declared(conn, key, oir, conf, evidence="(a) stated aim; (b) KPI in tCO2e with method"):
    conn.execute("INSERT INTO eco_readiness (company_key, oi_score, oir_score, oir_evidence, sources, confidence, last_verified) VALUES (?,?,?,?,?,?,?)",
                 (key, 2, oir, evidence, "https://example.test/report", conf, "2026-10-16"))


@pytest.fixture()
def world(tmp_path_factory):
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    _company(conn, "9300001-1", "Fixture Software Oy", "62100", "Software publishing")             # nothing names an area
    _company(conn, "9300002-1", "Fixture Nets Oy", "03210", "Business support services")            # the code family alone
    _company(conn, "9300003-1", "Fixture Labs Oy", "62100", "Software publishing")                  # own text only
    _project(conn, "9300003-1", "A new seaweed and algae cultivation method for cold seas")
    _company(conn, "9300004-1", "Fixture Farm Oy", "03210", "Marine aquaculture", group="cohort")  # code + line of business, a second family, a programme
    _project(conn, "9300004-1", "Recirculating aquaculture for northern waters")
    _programme(conn, "9300004-1")
    _declared(conn, "9300004-1", 4, "medium")
    _company(conn, "9300005-1", "Fixture Farm Two Oy", "03210", "Marine aquaculture", group="cohort")  # same, but the dataset is low confidence
    _project(conn, "9300005-1", "Recirculating aquaculture for northern waters")
    _programme(conn, "9300005-1")
    _declared(conn, "9300005-1", 4, "low")
    _company(conn, "9300006-1", "Aquaculture Fixture Oy", "62100", "Software publishing")                   # a name word, no second source
    conn.commit()
    yield th, conn
    conn.close()


def _oi(world, key):
    th, conn = world
    return ocean_impact.for_company(conn, th, key)


def test_the_shape_is_always_complete(world):
    th, conn = world
    keys = [r[0] for r in conn.execute("SELECT company_key FROM companies ORDER BY company_key")]
    for k in keys:
        d = _oi(world, k)
        assert tuple(d) == ocean_impact.SHAPE, k
        assert isinstance(d["evidence"], list) and set(d["scalability"]) == {"text", "basis"} and d["level_max"] == 9
        assert d["confidence"] in ("high", "medium", "low") and d["confidence_reason"] and d["level_rule"] and isinstance(d["raise"], str)
        assert d["band"] in (None, "Low", "Medium", "High") and (d["level"] is not None or d["band"] is None) and (d["band"] is not None or d["level"] is None or d["level"] < 3)
        assert all(set(e) == {"text", "date", "source_label", "url", "family"} for e in d["evidence"])
    blank = ocean_impact.empty(th["impact_readiness"])        # and when the thesis defines nothing
    assert tuple(blank) == ocean_impact.SHAPE and blank["level"] is None and blank["area"] is None
    assert tuple(ocean_impact.assess(conn, matching.company_context(conn, keys[0]), keys[0], {"id": "x"})) == ocean_impact.SHAPE


def test_four_companies_span_the_ladder(world):
    none = _oi(world, "9300001-1")
    assert none["area"] is None and none["level"] is None and none["band"] is None and none["confidence"] == "low"
    assert "No rung applies" in none["level_rule"] and none["scalability"] == {"text": "not assessed from public records", "basis": None}
    one = _oi(world, "9300002-1")
    assert one["level"] == 1 and one["band"] is None and one["confidence"] == "low" and one["area_basis"] == "industry code family"
    assert one["area"] == "Sustainable ocean resources: aquaculture and fisheries"
    three = _oi(world, "9300003-1")
    assert three["level"] == 3 and three["band"] == "Medium" and three["confidence"] == "medium" and three["area_basis"] == "own text"
    assert three["evidence"][0]["url"].startswith("https://cordis.europa.eu/") and three["evidence"][0]["family"] == "cordis"
    assert any(w in three["evidence"][0]["text"] for w in ("seaweed", "algae"))
    eight = _oi(world, "9300004-1")
    assert eight["level"] == 8 and eight["band"] == "High" and eight["confidence"] == "high"
    assert {e["family"] for e in eight["evidence"]} >= {"prh", "cordis", "ecosystem"}
    assert eight["level_rule"].startswith("Level 8:") and eight["raise"]


def test_declared_research_sets_rungs_seven_and_eight_only_at_medium_or_high_confidence(world):
    low = _oi(world, "9300005-1")
    assert low["level"] == 6 and low["band"] == "Medium"                  # corroborated twice; a low-confidence reading is a lead
    assert any("a lead and sets no rung" in e["text"] for e in low["evidence"])
    assert "low confidence" in low["raise"]
    th, conn = world
    conn.execute("UPDATE eco_readiness SET confidence='high', oir_score=2 WHERE company_key='9300005-1'")
    d7 = _oi(world, "9300005-1")
    assert d7["level"] == 7 and d7["band"] == "Medium"                     # an assessment on record, no measured outcome: not High
    conn.execute("UPDATE eco_readiness SET oir_evidence=NULL WHERE company_key='9300005-1'")
    assert _oi(world, "9300005-1")["level"] == 6                           # a score without its evidence text sets nothing


def test_nothing_reaches_rung_nine_and_a_bare_name_word_gives_no_area(world):
    th, conn = world
    levels = [_oi(world, r[0])["level"] for r in conn.execute("SELECT company_key FROM companies")]
    assert 9 not in levels
    d = _oi(world, "9300006-1")                                            # 'Aquaculture' in the legal name, no second source family
    assert d["area"] is None and d["level"] is None
    emit.emit_signal(conn, company_key="9300006-1", signal_type="bf_funding", date="2024-01-01", source_url="https://tietopankki.example.test/x",
                     confidence="high", adapter="businessfinland", detail="Business Finland funding granted")
    d = _oi(world, "9300006-1")
    assert d["area_basis"] == "corroborated name word" and d["level"] == 1 and d["confidence"] == "low"   # still sector implied only


def test_the_area_is_words_never_a_dataset_slug(world):
    th, conn = world
    areas = th["impact_readiness"]["areas"]
    labels = {a["label"] for a in areas.values()}
    from radar import frameworks
    slugs = set(frameworks.CATEGORIES) | set(areas) | {"aquatech", "ocean data", "water quality", "emissions"}
    for r in conn.execute("SELECT company_key FROM companies"):
        a = _oi(world, r[0])["area"]
        assert a is None or (a in labels and "_" not in a and a.casefold() not in slugs)
    assert all(a["label"][0].isupper() and " " in a["label"] for a in areas.values())


def test_the_ladder_in_the_thesis_files_is_complete():
    for tid, path in thesis.available().items():
        ir = thesis.load(path).get("impact_readiness")
        assert ir is not None, tid
        if not ir.get("areas"):
            assert tid == "health_tech_turku"               # no impact areas: no assessment
            continue
        assert [r["level"] for r in ir["levels"]] == list(range(1, 10)) and ir["level_max"] == 9
        assert all(r["rule"] and r["raise"] for r in ir["levels"]) and ir["no_level"]["rule"] and ir["bands"]["low_max"] < ir["bands"]["high_min"]


def test_the_memo_and_the_api_carry_the_assessment(world):
    th, conn = world
    m = memo.build(conn, th, "9300004-1", today="2026-10-16")
    assert m["ocean_impact"] == _oi(world, "9300004-1")
    assert 3 <= len(m["plain_why"]) <= 5
    health = thesis.load(thesis.available()["health_tech_turku"])
    assert ocean_impact.settings(health) is None and ocean_impact.for_company(conn, health, "9300004-1") is None


def test_the_bullets_are_plain_words(world):
    th, conn = world
    for key in ("9300001-1", "9300002-1", "9300004-1"):
        m = memo.build(conn, th, key, today="2026-10-16")
        for b in m["plain_why"]:
            t = re.sub(r"\d{4}-\d{2}-\d{2}|\b\d{1,2} [A-Z][a-z]{2} \d{4}|\b\d{4}\b", "", b["text"])
            assert not re.search(r"\d", t), b["text"]
            assert not re.search(r"\blevel\b \d|\brow\b|\brule [a-z0-9]\b|_", b["text"]), b["text"]
            assert b["text"][0].isupper() and b["text"].endswith(".")


def test_words_only_strips_ids_and_counts():
    assert memo.words_only("Industry code 30120 (Building of boats, PRH) is on the thesis list; 2 more reasons.") == \
        "Registered industry (Building of boats) is on the thesis list"
    assert memo.words_only("Business readiness Medium (level 6): first public contract") == "Business readiness Medium: first public contract"


# ---- the pages, on the committed snapshot -------------------------------------------------------------------------
@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    try:
        ecosystem.run(conn, th)
        conn.commit()
    except Exception:
        pytest.skip("ecosystem dataset not available")
    conn.close()
    return th


@pytest.mark.parametrize("key", ["2962040-6", "3166759-6"])
def test_the_company_page_shows_the_assessment_and_the_bullets(snap, key):
    from app import app
    html = TestClient(app).get(f"/c/{key}").text
    block = html[html.index('id="ocean-impact"'):]
    block = block[:block.index("</section>")]
    for part in ("Ocean Impact Assessment", "Impact area", "Evidence", "Scalability", "Ocean Impact Readiness", "Confidence", "To raise it"):
        assert part in block, part
    assert re.search(r"level \d of 9", block) or "no level on record" in block
    assert html.index('id="why-this-verdict"') < html.index('id="ocean-impact"') < html.index('class="cc-sec cc-ks"')   # headline, bullets, block, then key statistics
    bullets = re.findall(r"<li>(.*?)</li>", html[html.index('id="why-this-verdict"'):html.index('id="ocean-impact"')], re.S)
    assert 3 <= len(bullets) <= 5
    assert "aquatech" not in block and "ocean_impact" not in block


def test_the_home_rows_carry_the_ocean_mark(snap):
    from app import app
    html = TestClient(app).get("/").text
    assert html.count('class="hc-oi') >= 10 and 'oi-dot oi-dot-' in html


def test_the_api_has_the_assessment(snap):
    from app import app
    d = TestClient(app).get("/api/company/3166759-6").json()
    assert tuple(d["ocean_impact"]) == ocean_impact.SHAPE
