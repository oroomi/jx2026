"""Matchmaking (D28 to D30): filter then rank, every rank explained in words, on the committed snapshot store and the declared lists."""
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import matchmaker, matchmaker_orgs, matchtext, memo, store, thesis

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
TODAY = "2026-10-17"
VIVA, ARCTIC = "2962040-6", "3166759-6"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")

# A digit string in reason text is allowed only as one of these: a date, a TRL range, an 'N of M' count, a number with a unit word, a code or a year.
_OK_NUM = re.compile(r"\d{4}-\d{2}-\d{2}|TRL \d(?: to \d)?|\d+ of (?:the |its )?\d+|\d+ to \d+|\b\d+ (?:days|years|declared|of|are|companies|startups)\b|"
                     r"(?:window|from|in|founded|than|under|over|code|group|family|limit of) \d+(?![\d-])(?: to \d+)?|\b[CQ]\d{1,2}\b|\d+\b(?=[a-z' ]*\))")

@pytest.fixture(scope="module")
def env(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("RADAR_DATA_DIR", str(SNAP))
    mp.delenv("RADAR_DB", raising=False)
    th = thesis.load()
    conn = store.open_db(thesis=th)
    yield th, conn
    conn.close()
    mp.undo()


def _texts(res):
    for row in res.get("counterparts") or res.get("startups") or []:
        for c in row["components"]:
            for k in ("reason", "chip"):
                if c.get(k):
                    yield c[k].replace(row["name"], "NAME")      # a programme's own name may hold a year; it is a name, not a bare number


def _bare_numbers(text: str) -> list[str]:
    left = _OK_NUM.sub(" ", text)
    return re.findall(r"\d+(?:[.,]\d+)?%?", left)


@pytest.mark.parametrize("key", [VIVA, ARCTIC])
def test_demo_companies_get_counterparts_each_with_reasons(env, key):
    th, conn = env
    res = matchmaker.match_company(key, th, conn=conn, today=TODAY, limit=10)
    assert res and res["counterparts"], "a demo company must have next steps"
    for r in res["counterparts"]:
        met = [c for c in r["components"] if c["met"]]
        assert met, f"{r['name']} is listed with no satisfied component"
        assert all(c["reason"] and c["chip"] for c in met), "every satisfied component carries a sentence and a chip"
        assert any(c["id"] in ("sector", "lookalike", "keywords", "readiness") for c in met)


@pytest.mark.parametrize("key", [VIVA, ARCTIC])
def test_reason_text_has_no_bare_numbers_and_no_score(env, key):
    th, conn = env
    res = matchmaker.match_company(key, th, conn=conn, today=TODAY, limit=50)
    assert "score" not in str(res.keys()).lower() and all("score" not in r for r in res["counterparts"])
    seen = 0
    for t in _texts(res):
        seen += 1
        assert "score" not in t.lower(), t
        assert not _bare_numbers(t), f"bare number in: {t}"
    assert seen


def test_org_view_lists_declared_cohort_first(env):
    """Revealed matching sanity: A'Pelago's declared cohort (cohort_portfolio_companies.csv, group cohort) is at the top of its own view."""
    th, conn = env
    res = matchmaker.match_org("apelago", th, conn=conn, today=TODAY, limit=40)
    cohort = {r[0] for r in conn.execute("SELECT company_key FROM companies WHERE group_tag='cohort'")}
    rows = res["startups"]
    head = [r for r in rows[: len(cohort)]]
    assert cohort <= {r["key"] for r in head}, "every declared cohort company is in the first rows"
    assert all(r["member"] for r in head), "members come before any non-member"
    assert all(r["components"][0]["id"] == "member" and "Declared member" in r["components"][0]["reason"] for r in head)
    assert res["org"]["revealed"]["members_in_records"] >= len(cohort)


def test_declared_portfolio_is_in_redstone_view_and_connected_in_company_view(env):
    th, conn = env
    org = matchmaker.match_org("redstone-blue", th, conn=conn, today=TODAY, limit=40)
    assert VIVA in {r["key"] for r in org["startups"] if r["member"]}
    comp = matchmaker.match_company(VIVA, th, conn=conn, today=TODAY, limit=50)
    assert "redstone-blue" in {c["id"] for c in comp["connected"]}
    assert "redstone-blue" not in {r["id"] for r in comp["counterparts"]}, "an organisation that already selected the startup is not a next step"


def test_verdict_path_filters_kinds(env, monkeypatch):
    th, conn = env
    cfg = matchtext.config(th)
    real = matchmaker._verdict
    for decision, want in (("INVEST", {"investor"}), ("ACCELERATOR", {"accelerator", "programme", "funder"})):
        monkeypatch.setattr(matchmaker, "_verdict", lambda c, t, k, d=decision: {**real(c, t, k), "decision": d})
        res = matchmaker.match_company(VIVA, th, conn=conn, today=TODAY, limit=50)
        kinds = {r["kind"] for r in res["counterparts"]}
        assert kinds <= want | set(cfg["always_kinds"]), (decision, kinds)
        assert kinds & want, decision
    monkeypatch.setattr(matchmaker, "_verdict", lambda c, t, k: {**real(c, t, k), "decision": "REJECT / LOW FIT"})
    res = matchmaker.match_company(VIVA, th, conn=conn, today=TODAY, limit=50)
    assert {r["kind"] for r in res["counterparts"]} <= set(cfg["always_kinds"])


def _org(**kw):
    o = {"id": "x", "name": "Test Fund", "kind": "investor", "programme": False, "groups": {"ship_design": ["declared words 'boat'"]},
         "stems_free": {}, "has_declared": True, "geo": set(), "geo_text": None, "lookalikes": {}, "trl_window": None, "age_limit": None,
         "stage_text": None, "stages": None, "url": "https://example.org", "deadline": {"open": True, "date": None, "text": ""}}
    o.update(kw)
    return o


def _sp(**kw):
    s = {"key": "k", "name": "Boat Oy", "country": "FI", "family": "301", "band": None, "url": "https://example.org/k", "founded": "2020-01-01",
         "groups": {"ship_design": ["its industry code 30120 (boats)"]}, "stems": {}, "trl": 5, "stage": None, "eco_stage": None, "group_tag": "feed"}
    s.update(kw)
    return s


def test_hard_filters_geography_window_closed_and_topic(env):
    th, _ = env
    cfg = matchtext.config(th)
    t = date.fromisoformat(TODAY)
    ev = lambda sp, org: matchmaker.evaluate(sp, org, cfg, {}, {}, t)
    assert ev(_sp(), _org())["excluded"] is None
    assert "does not include FI" in ev(_sp(), _org(geo={"SE"}, geo_text="Sweden"))["excluded"]                 # filter 2
    assert ev(_sp(), _org(geo={"FI"}, geo_text="Finland"))["excluded"] is None
    assert "outside the stated window" in ev(_sp(trl=3), _org(trl_window=(6, 8)))["excluded"]               # filter 3
    assert ev(_sp(trl=7), _org(trl_window=(6, 8)))["excluded"] is None
    assert "age limit" in ev(_sp(founded="2012-05-01"), _org(age_limit=5))["excluded"]
    assert "no sector, word or lookalike" in ev(_sp(groups={}), _org())["excluded"]                          # the topic gate
    assert matchmaker._open(_org(deadline={"open": False, "date": None, "text": "closed"}), t).startswith("closed")
    assert "passed" in matchmaker._open(_org(deadline={"open": True, "date": "2026-10-01", "text": ""}), t)


def test_timing_and_agnostic_programme(env):
    th, _ = env
    cfg = matchtext.config(th)
    t = date.fromisoformat(TODAY)
    soon = _org(groups={}, stems_free={}, has_declared=False, deadline={"open": True, "date": "2026-11-04", "text": "2026-11-04"}, trl_window=(4, 9))
    ev = matchmaker.evaluate(_sp(groups={}), soon, cfg, {}, {}, t)
    by = {c["id"]: c for c in ev["components"]}
    assert ev["excluded"] is None, "a programme that names no sector is listed when the startup is inside its window"
    assert by["timing"]["met"] and "18 days" in by["timing"]["reason"]
    far = _org(deadline={"open": True, "date": "2027-06-01", "text": ""})
    assert matchmaker.evaluate(_sp(), far, cfg, {}, {}, t)["components"][4]["met"] is False


def test_light_verdict_equals_memo_build(env):
    th, conn = env
    for key in (VIVA, ARCTIC):
        m = memo.build(conn, th, key, today=TODAY)
        v = matchmaker._verdict(conn, th, key)
        assert v["decision"] == m["recommendation"]["decision"]
        assert {d: v["bands"][d] for d in ("impact", "business", "investment", "fit")} == {d: m["levels"][d]["band"] for d in ("impact", "business", "investment", "fit")}
        assert v["bands"]["technology"] == m["levels"]["technology"]["band"]


def test_orgs_are_organisations_with_declared_and_revealed_parts(env):
    th, conn = env
    reg = matchmaker_orgs.registry(conn, th)
    assert len(reg["orgs"]) > 100
    assert len({o["id"] for o in reg["orgs"]}) == len(reg["orgs"])
    no_text = [o for o in reg["orgs"] if not o["has_declared"]]
    rows = {r["id"]: r for r in matchmaker.org_list(th, conn=conn)}
    for o in no_text:
        assert "no declared text" in rows[o["id"]]["demand"] or "revealed" in rows[o["id"]]["demand"]
    assert any(o["lookalikes"] for o in reg["orgs"]) and all(isinstance(o["geo"], set) for o in reg["orgs"])


def test_no_sector_words_or_people_table_in_code():
    th = thesis.load()
    src = "\n".join((ROOT / "radar" / f).read_text(encoding="utf-8") for f in ("matchtext.py", "matchmaker.py", "matchmaker_orgs.py"))
    for g in th["matching"]["keyword_groups"]:
        for stem in g["stems"]:
            if len(stem) >= 6:
                assert f'"{stem}"' not in src and f"'{stem}'" not in src, f"sector word {stem!r} is in code, it belongs in the thesis file"
    assert not re.search(r"FROM\s+person\b|JOIN\s+person\b", src, re.I), "the dataset's people table is out of scope"
    assert 'cfg["weights"]' in src, "the weights come from the thesis file (matching: weights)"


def test_thesis_without_matchmaking_config_is_handled(env, monkeypatch):
    _, conn = env
    th = dict(thesis.load(), matching={"investors": "x"})
    assert matchmaker.match_company(VIVA, th, conn=conn) is None and matchmaker.org_list(th, conn=conn) is None


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))     # after the autouse fixture that points it at an empty directory
    monkeypatch.delenv("RADAR_DB", raising=False)
    from app import app
    return TestClient(app)


def test_match_page_renders_in_both_views(client):
    r = client.get("/match")
    assert r.status_code == 200 and "Match startups and counterparts" in r.text and "Choose a counterpart" in r.text
    assert "Declared member" in client.get("/match?org=apelago").text
    r = client.get(f"/match?company={VIVA}")
    assert r.status_code == 200 and "Next steps" in r.text and "Viva Jets" in r.text and "Why this match" in r.text
    assert client.get("/match?view=company").status_code == 200
    assert client.get("/match?q=arctic").status_code == 200 and "Arctic Fry" in client.get("/match?q=arctic").text
    assert client.get("/match?org=no-such-org").status_code == 200


def test_company_page_has_next_steps_block_and_one_include(client):
    r = client.get(f"/c/{VIVA}")
    assert r.status_code == 200 and 'aria-labelledby="mn-h"' in r.text and "Next steps" in r.text
    assert r.text.count('class="mn-item"') == 3, "the top three counterparts"
    html = (ROOT / "radar" / "templates" / "company.html").read_text(encoding="utf-8")
    assert html.count('{% include "_match_next.html" %}') == 1


def test_api_company_org_orgs_and_errors(client):
    j = client.get(f"/api/match/company/{VIVA}").json()
    assert j["company"]["key"] == VIVA and j["counterparts"] and j["weights"] and j["rule"]
    assert j["counterparts"][0]["rank"] == 1 and j["counterparts"][0]["components"]
    o = client.get("/api/match/org/apelago").json()
    assert o["org"]["id"] == "apelago" and o["startups"][0]["member"] is True
    assert client.get("/api/match/orgs").json()["count"] > 100
    assert client.get("/api/match/org/no-such-org").status_code == 404
    assert client.get("/api/match/company/no-such-key").status_code == 404
    assert client.get("/api/match/company/" + VIVA + "?thesis=nope").status_code == 400
    assert client.get("/api/no-such-endpoint").status_code == 404 and "endpoints" in client.get("/api/no-such-endpoint").json()


def test_phone_tab_bar_and_header_link_to_match(client):
    t = client.get("/match").text
    assert '<a href="/match" aria-current="page">' in t and t.count('href="/match"') >= 2
