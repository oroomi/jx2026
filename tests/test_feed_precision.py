import re

import pytest
from fastapi.testclient import TestClient

from radar import fit, store, thesis
from tests.fixtures import feed_precision_fixture as fx

HEALTH_ID = "health_tech_turku"
DEFAULT_ID = "redstone_apelago_blue"


@pytest.fixture()
def built(tmp_path):
    conn = fx.build(tmp_path / "p.sqlite")
    th = thesis.load(thesis.resolve(None))
    rows = {r["company_key"]: r for r in store.feed(conn, th, limit=1000)}
    return conn, th, rows


def test_each_reason_admits_a_row(built):
    _, _, rows = built
    assert rows["F-code"]["reasons"] == ["industry_code"] and rows["F-code"]["strength"] == "strong"
    assert rows["F-lob"]["reasons"] == ["line_of_business"] and rows["F-lob"]["strength"] == "strong"
    assert rows["F-own"]["reasons"] == ["own_text"] and rows["F-own"]["strength"] == "strong"
    assert rows["F-corr"]["reasons"] == ["corroborated_keyword"] and rows["F-corr"]["strength"] == "strong"


def test_name_keyword_only_row_is_weak_and_kept(built):
    _, _, rows = built
    r = rows["F-weak"]
    assert r["strength"] == "weak" and r["reasons"] == []
    assert r["why"].startswith("Weak: only the legal name ('Fixture Sea Weak Oy') contains 'sea'")
    assert "'Software publishing' (58290)" in r["why"]


def test_corroboration_needs_a_different_adapter(built):
    _, _, rows = built
    assert "corroborated_keyword" in rows["F-corr"]["reasons"]
    assert rows["F-one"]["strength"] == "weak"  # two signals, one adapter


def test_year_only_bf_is_not_entry_but_corroborates(built):
    conn, th, rows = built
    assert rows["F-year"]["signal_type"] == "register_entry"
    assert "corroborated_keyword" in rows["F-year"]["reasons"]
    assert "Business Finland export record from %d (year only)" % (fx.TODAY.year - 1) in rows["F-year"]["why"]
    assert "F-yearonly" not in rows  # its only in-window signal is year-only: no entry date
    assert store.feed_counts(conn, th)["year_only_not_entry"] == 2


def test_why_text_uses_stored_values_and_only_row_names(built):
    _, _, rows = built
    assert rows["F-code"]["why"] == "Why: Industry code 30110 (Fixture shipbuilding, PRH) is on the thesis list."
    assert rows["F-lob"]["why"] == "Why: The registered line of business 'Construction of water projects' contains 'water'."
    for r in rows.values():
        for m in re.findall(r"'(Fixture [^']+)'", r["why"]):
            assert m == r["name"]
    assert "'vesi'" in rows["F-own"]["why"]


def test_counts_and_footer_equal_rendered_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    fx.build(tmp_path / f"radar_{DEFAULT_ID}.sqlite")
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get("/").text
    head, _, weak_part = t.partition('<details class="weak"')
    main_n, weak_n = head.count('class="feed-row'), weak_part.count('class="feed-row')
    assert main_n == int(re.search(r'n-main">(\d+)<', t).group(1)) == 5
    assert weak_n == int(re.search(r'n-weak">(\d+)<', t).group(1)) == 2
    assert f"Weak matches ({weak_n})" in t
    th = thesis.load(thesis.resolve(None))
    c = store.feed_counts(store.open_db(tmp_path / f"radar_{DEFAULT_ID}.sqlite"), th)
    assert (c["main"], c["weak"]) == (main_n, weak_n)
    assert set(c["by_reason"]) == set(store.REASON_IDS)
    m = TestClient(app.app).get("/method").text
    assert "Feed precision" in m and "a hint, not proof" in m and f"{c['main']} companies in the main list" in m


def test_health_swap_main_feed_non_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    fx.build(tmp_path / f"radar_{DEFAULT_ID}.sqlite")
    fx.build(tmp_path / f"radar_{HEALTH_ID}.sqlite", words=("health", "bio"), code="32500", hilma_kw="terveys")
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get(f"/?thesis={HEALTH_ID}").text
    head = t.partition('<details class="weak"')[0]
    assert head.count('class="feed-row') >= 1 and "industry code 32500" in t.lower()


# ---- jx20b: circular own-text, whole-word keywords, name-only rule, personal names, BlueInvest TRL ----------------------
from radar import db, emit  # noqa: E402


def _co(conn, key, name, **kw):
    emit.upsert_company(conn, company_key=key, name=name, source_url=f"https://example.test/fixture/{key}", **kw)


def _sig(conn, key, typ, d, adapter="prh", conf="medium", text=None, **kw):
    url = f"https://example.test/fixture/{key}/{adapter}/{typ}/{d}"
    emit.emit_signal(conn, company_key=key, signal_type=typ, date=d, source_url=url, confidence=conf, adapter=adapter, **kw)
    sid = conn.execute("SELECT id FROM signals WHERE source_url=?", (url,)).fetchone()[0]
    for field, t in (text or {}).items():
        conn.execute("INSERT INTO signal_text (signal_id, field, text) VALUES (?,?,?)", (sid, field, t))
    conn.commit()


def _feed(conn):
    th = thesis.load(thesis.resolve(None))
    return th, {r["company_key"]: r for r in store.feed(conn, th, limit=1000)}


def test_annotation_is_never_read_as_project_text(tmp_path):
    conn = db.connect(tmp_path / "c.sqlite")
    ann = "Matched on project objective: 'hav'. X: Fixture project (Horizon), role participant, project start 2026-09-01"
    for key, text in (("F-ann", None), ("F-have", {"objective": "We have blueprints and havaintolaite for all."}),
                      ("F-real", {"objective": "A study of the Hav and its fish."})):
        _co(conn, key, f"Fixture {key} Oy", industry_code="58290", industry_desc="Software publishing")
        _sig(conn, key, "eu_project", fx.day(20), adapter="cordis", conf="low", detail=ann, text=text)
    _, rows = _feed(conn)
    for k in ("F-ann", "F-have"):
        assert rows[k]["strength"] == "weak" and "own_text" not in rows[k]["reasons"]
    assert rows["F-real"]["reasons"] == ["own_text"] and "'hav'" in rows["F-real"]["why"]


def test_keyword_matching_is_whole_word_or_long_prefix():
    th = thesis.load(thesis.resolve(None))
    m = lambda t: fit.matched_keywords(t, th)  # noqa: E731
    for t in ("have", "blueprints", "havaintolaite", "Oy Merinova Ab", "Meridian Vector Oy", "Aaltonen", "marinade"):
        assert m(t) == [], t
    assert m("Hav") == ["hav"] and m("the Hav is cold") == ["hav"]
    assert "ocean" in m("Oceanic Works") and "marine" in m("Marinemaster Oy")  # 5+ character words match as a word start
    assert m("Blue") == ["blue"] and m("Seaside") == []  # shorter words: whole word only


def test_name_keyword_alone_never_admits_a_company(tmp_path):
    conn = db.connect(tmp_path / "n.sqlite")
    _co(conn, "F-m", "Oy Merinova Ab", industry_code="70200", industry_desc="Management consulting")
    _sig(conn, "F-m", "register_entry", fx.day(10))
    _co(conn, "F-sea", "Fixture Sea Oy", industry_code="58290", industry_desc="Software publishing")
    _sig(conn, "F-sea", "register_entry", fx.day(10))
    _co(conn, "F-sea2", "Fixture Sea Two Oy", industry_code="58290", industry_desc="Software publishing")
    _sig(conn, "F-sea2", "register_entry", fx.day(10))
    _sig(conn, "F-sea2", "bf_funding", fx.day(300), adapter="businessfinland")
    _, rows = _feed(conn)
    assert rows["F-m"]["strength"] == "weak" and "contains" not in rows["F-m"]["why"].split("Weak:")[1][:40]
    assert rows["F-sea"]["strength"] == "weak"
    assert rows["F-sea2"]["reasons"] == ["corroborated_keyword"]


def test_personal_name_holding_is_hidden_unless_it_has_a_real_signal(tmp_path):
    conn = db.connect(tmp_path / "p.sqlite")
    for key, name in (("F-p1", "Fixtura Persona Holding Oy"), ("F-p2", "Fixtura Persona Invest Oy"), ("F-biz", "Fixture Design Consulting Oy"),
                      ("F-plain", "Fixture Words Oy")):
        _co(conn, key, name, industry_code="30110", industry_desc="Fixture shipbuilding")
        _sig(conn, key, "register_entry", fx.day(10))
    _sig(conn, "F-p2", "bf_funding", fx.day(5), adapter="businessfinland")
    th, rows = _feed(conn)
    assert "F-p1" not in rows and "F-p2" in rows and "F-biz" in rows and "F-plain" in rows
    assert store.feed_counts(conn, th)["hidden_personal"] == 1


def test_footer_prints_hidden_count(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    conn = db.connect(tmp_path / f"radar_{DEFAULT_ID}.sqlite")
    _co(conn, "F-p1", "Fixtura Persona Holding Oy", industry_code="30110")
    _sig(conn, "F-p1", "register_entry", fx.day(10))
    conn.close()
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get("/").text
    assert re.search(r'n-hidden">1</span> companies hidden: personal-name holding companies', t) and "Persona" not in t
    assert "whole word" in TestClient(app.app).get("/method").text


def test_company_page_reads_trl_from_blueinvest_profile(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    conn = db.connect(tmp_path / f"radar_{DEFAULT_ID}.sqlite")
    for key, trl in (("F-trl", 4), ("F-notrl", None)):
        _co(conn, key, f"Fixture {key} Oy")
        _sig(conn, key, "register_entry", fx.day(10))
        conn.execute("""INSERT INTO blueinvest_profiles (profile_id,company_key,title,trl,url,fetched_at)
                        VALUES (?,?,?,?,?,?)""", (key, key, "Fixture project", trl, f"https://example.test/blueinvest/{key}", "2026-10-16T00:00:00Z"))
    conn.commit()
    conn.close()
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get("/c/F-trl").text
    assert "level 4 of 9" in t and "the BlueInvest profile states TRL 4" in t and "https://example.test/blueinvest/F-trl" in t
    assert "level " not in TestClient(app.app).get("/c/F-notrl").text.split("Technology Readiness")[1].split("Investment Readiness")[0]
