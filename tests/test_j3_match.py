"""Judge round 3, matching (D70): an investor's early pipeline, one ranking behind the Match page and the home Top matching tab,
and an Ask bar that answers "top startups". Data: the committed snapshot store and the declared lists."""
import html as htmllib
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import home_orgs, matchmaker, matchtext, store, thesis

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
TODAY = "2026-10-17"
HX = {"HX-Request": "true"}
HONEST = "No startup on the radar is at due diligence yet; these are the closest, in the order below."
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")


@pytest.fixture(scope="module")
def env():
    mp = pytest.MonkeyPatch()
    mp.setenv("RADAR_DATA_DIR", str(SNAP))
    mp.delenv("RADAR_DB", raising=False)
    th = thesis.load()
    conn = store.open_db(thesis=th)
    yield th, conn
    conn.close()
    mp.undo()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.delenv("RADAR_DB", raising=False)
    from app import app
    return TestClient(app)


def _pipeline_verdicts(th):
    return set(matchtext.config(th)["org_pipeline"]["investor"]["verdicts"])


# ---- 1. an investor's early pipeline ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("org", ["redstone-blue", "katapult-ocean"])
def test_an_investor_gets_an_early_pipeline_not_zero(env, org):
    th, conn = env
    res = matchmaker.match_org(org, th, conn=conn, today=TODAY, limit=25)
    assert res["startups"], f"{org} must list the closest startups, not 0"
    assert {s["verdict"] for s in res["startups"]} <= _pipeline_verdicts(th)
    for s in res["startups"]:
        met = [c for c in s["components"] if c["met"]]
        assert met and all(c["chip"] and c["reason"] for c in met), s["name"]      # every row says why, in words
    assert [s["rank"] for s in res["startups"]] == list(range(1, len(res["startups"]) + 1))


def test_the_page_says_honestly_that_nobody_is_at_due_diligence(env):
    th, conn = env
    res = matchmaker.match_org("redstone-blue", th, conn=conn, today=TODAY, limit=25)
    ready = [s for s in res["startups"] if s["verdict"] in ("DUE DILIGENCE", "INVEST")]
    assert res["pipeline"]["ready"] == len(ready)
    if not ready:
        assert res["pipeline"]["note"] == HONEST
    else:
        assert "due diligence" in res["pipeline"]["note"] and str(len(ready)) in res["pipeline"]["note"]
        first_early = next((i for i, s in enumerate(res["startups"]) if s not in ready), len(ready))
        assert all(s in ready for s in res["startups"][:first_early]) and not any(s in ready for s in res["startups"][first_early:])


def test_redstones_own_portfolio_is_connected_not_ranked(env):
    th, conn = env
    res = matchmaker.match_org("redstone-blue", th, conn=conn, today=TODAY, limit=1000)
    conn_keys = {c["key"] for c in res["connected"]}
    assert len(conn_keys) == 9 and not conn_keys & {s["key"] for s in res["startups"]}


def test_the_startup_side_for_the_accelerator_is_unchanged(env):
    th, conn = env
    res = matchmaker.match_org("apelago", th, conn=conn, today=TODAY, limit=1000)
    assert res["startups"] and {s["verdict"] for s in res["startups"]} <= {"ACCELERATOR", "GRANT SUPPORT", "WATCHLIST", "PORTFOLIO SUPPORT"}
    assert "pipeline" not in res or not res["pipeline"]
    comp = matchmaker.match_company("2962040-6", th, conn=conn, today=TODAY, limit=10)
    assert comp["counterparts"] and {r["kind"] for r in comp["counterparts"]} <= set(matchtext.config(th)["path_kinds"][comp["company"]["verdict"]]) | set(matchtext.config(th)["always_kinds"])


def test_an_investor_that_ranks_nobody_says_why_in_words(env):
    th, conn = env
    rows = [o for o in matchmaker.org_list(th, conn=conn) if o["kind"] == "investor"][:12]
    assert rows
    for o in rows:
        res = matchmaker.match_org(o["id"], th, conn=conn, today=TODAY)
        if res["startups"]:
            continue
        why = res["org"]["empty_reason"] or res["org"]["closed_note"]
        assert why and "'..." not in why and not re.search(r"\b[A-Z]{2}\b", why), (o["name"], why)      # a reason, with no placeholder and no country code


def test_the_early_pipeline_is_read_deeper_than_the_default(env):
    th, conn = env
    pc = matchmaker.pipeline_config(matchtext.config(th), "investor")
    assert int(pc["candidates"]) > int(matchtext.config(th).get("candidates", 300))
    res = matchmaker.match_org("redstone-blue", th, conn=conn, today=TODAY)
    assert res["candidates_profiled"] <= int(pc["candidates"])
    assert res["candidates_profiled"] > int(matchtext.config(th).get("candidates", 300)) or res["unprofiled"] == 0      # every candidate is checked, or the deeper depth was used


def test_the_rule_text_names_the_early_pipeline(env):
    assert "early pipeline" in matchmaker.RULE and "due diligence" in matchmaker.RULE


def test_match_page_shows_the_sentence_and_ranked_investor_rows(client):
    t = client.get("/match?org=redstone-blue").text
    assert "No startup passes the filters" not in t and 'class="mt-res"' in t
    assert HONEST in htmllib.unescape(t)
    assert "Best fits" in t and "Already connected" in t
    assert 'class="mt-chip"' in t


# ---- 2. the home tab is the matchmaker's ranking --------------------------------------------------------------------------------------

def _tab_rows(html: str) -> list[str]:
    return re.findall(r'class="hc-row" href="/c/([^"]+)"', html)


def _tab_count(html: str) -> int:
    return int(re.search(r'data-key="2"[^>]*>.*?<span>(\d+)</span>', html).group(1))


@pytest.mark.parametrize("org", ["apelago", "redstone-blue", "katapult-ocean"])
def test_the_home_tab_shows_exactly_the_matchmakers_ranking(client, env, org):
    th, conn = env
    n = matchmaker.org_limit(th)
    want = matchmaker.match_org(org, th, conn=conn, today=TODAY, limit=n)
    assert want["startups"], org
    home_orgs.ranking(th, org, wait=None)                                    # the background build, done here so the request does not time out
    t = client.get(f"/home/list?group=fit&for={org}", headers=HX).text
    assert _tab_rows(t) == [s["key"] for s in want["startups"]]              # same order, same count
    assert _tab_count(t) == len(want["startups"])
    items = t.split("<li ")[1:]
    assert len(items) >= len(want["startups"])
    for li in items:
        if 'class="hc-row"' in li:
            assert 'class="hc-whyl">Why<' in li and 'class="hc-whyc"' in li     # a Why line in words on every row


def test_group_fit_is_that_ranking_not_alphabetical_yards(client, env):
    th, conn = env
    home_orgs.ranking(th, "apelago", wait=None)
    t = client.get("/?group=fit").text
    want = [s["key"] for s in matchmaker.match_org("apelago", th, conn=conn, today=TODAY, limit=matchmaker.org_limit(th))["startups"]]
    assert _tab_rows(t[t.index('class="hc-list"'):]) == want
    assert "Matched for" in t


def test_the_picker_for_an_investor_is_no_longer_empty(client, env):
    th, conn = env
    home_orgs.ranking(th, "redstone-blue", wait=None)
    t = htmllib.unescape(client.get("/home/list?group=fit&for=redstone-blue", headers=HX).text)
    assert "No startup on this list is matched to" not in t and "No startup on the radar" not in t.replace(HONEST, "")
    assert HONEST in t
    assert "/match?org=redstone-blue&tab=connected" in t or "/match?org=redstone-blue&amp;tab=connected" in t     # the 9 portfolio companies point to the other tab


# ---- 3. the Ask bar -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("q", ["top startups", "best startups", "best investment", "top matches", "Top matching startups"])
def test_ask_top_questions_go_to_the_accelerators_ranking(client, env, q):
    th, conn = env
    home_orgs.ranking(th, "apelago", wait=None)
    d = client.get("/api/ask", params={"q": q}).json()
    assert d["intent"] == "top_match" and d["url"] == "/?group=fit&for=apelago", d
    want = matchmaker.match_org("apelago", th, conn=conn, today=TODAY, limit=matchmaker.org_limit(th))["startups"]
    assert [i["label"] for i in d["items"]] == [s["name"] for s in want][:len(d["items"])] and d["items"]
    assert "A'Pelago" in d["say"] and "Nothing on the radar" not in d["say"]


def test_ask_who_should_redstone_invest_in(client, env):
    th, conn = env
    home_orgs.ranking(th, "redstone-blue", wait=None)
    d = client.get("/api/ask", params={"q": "who should Redstone invest in"}).json()
    assert d["intent"] == "top_match" and d["url"] == "/?group=fit&for=redstone-blue", d
    want = matchmaker.match_org("redstone-blue", th, conn=conn, today=TODAY, limit=matchmaker.org_limit(th))["startups"]
    assert d["items"] and d["items"][0]["label"] == want[0]["name"]
    assert "Redstone Blue" in d["say"]


def test_ask_still_answers_the_old_questions(client):
    assert client.get("/api/ask", params={"q": "Show accelerator candidates in Finland"}).json()["intent"] == "filter"
    assert client.get("/api/ask", params={"q": "who should A'Pelago meet"}).json()["intent"] == "match"
    assert client.get("/api/ask", params={"q": "zzqqxx"}).json()["intent"] == "nothing"
