"""D76 and D77 (fix/aava_orgfits): Aava answers "who should <organisation> meet" from the match page's own list, and a programme whose call is
closed or whose deadline has passed is never named as a next step. Data: a copy of data/snapshot plus the declared lists in the repo; the model
is the scripted stand-in of tests/fixtures/aava_fakes.py (no network, no key, no spend)."""
import json
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import pytest

from radar import aava_entities, aava_llm, aava_tools, ask, briefs, home_orgs, matching, matchmaker, matchmaker_orgs, memo, sectors, store, thesis
from tests.fixtures.aava_fakes import FakeClient, call, tool_results

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
VIVA = "2962040-6"
CLOSED_CELL = "no open call found (5th call closed 2025-09-30; decisions announced 2026-01-28)"
TWIN = "Interreg Central Baltic Programme 2021-2027"


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    d = tmp_path_factory.mktemp("orgfits_data")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, d / f.name)
    conn = sqlite3.connect(d / "radar_redstone_apelago_blue.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        sectors.assign(conn, thesis.load())
    finally:
        conn.close()
    return d


@pytest.fixture()
def th(data_dir, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(data_dir))
    monkeypatch.delenv("RADAR_DB", raising=False)
    for k in ("ANTHROPIC_API_KEY", "AAVA_MODEL", "AAVA_THINKING_BUDGET", "AAVA_MAX_TOKENS", "AAVA_EFFORT", "AAVA_MAX_STEPS"):
        monkeypatch.delenv(k, raising=False)
    aava_llm._NO_THINKING.clear()
    return thesis.load()


def ctx_for(th):
    return aava_tools.ToolContext(th, limits=aava_llm.settings().limits)


# ---- D76: one rule for a closed call ----------------------------------------------------------------------------------------------------
def test_a_closed_cell_or_a_past_deadline_is_closed_and_a_future_one_is_open():
    today = date(2026, 10, 17)
    assert matching.call_closed(matching.parse_deadline(CLOSED_CELL), today).startswith("closed: no open call found")
    assert matching.call_closed(matching.parse_deadline("2026-10-16"), today) == "the deadline 2026-10-16 has passed"
    assert matching.call_closed(matching.parse_deadline("2026-10-17"), today) is None          # closes today: still open
    assert matching.call_closed(matching.parse_deadline("rolling"), today) is None
    assert matching.call_closed(matching.parse_deadline("not announced (last held end of Oct 2025)"), today)       # the last call is past, no new one
    assert matching.closed_words("closed: " + CLOSED_CELL).endswith(": watch for the next call")
    assert matching.closed_words("closed: " + CLOSED_CELL).startswith("no open call on record (no open call found, 5th call closed 2025-09-30")


def test_a_longer_dataset_name_is_the_same_programme_but_a_funders_programme_is_not():
    assert matching.same_programme("Interreg Central Baltic", TWIN)
    assert matching.same_programme("Interreg Baltic Sea Region", "Interreg Baltic Sea Region")
    assert not matching.same_programme("Business Finland Sprint Grant", "Business Finland")      # one programme of a funder: not the funder
    assert not matching.same_programme("Interreg Central Baltic", "Interreg")                     # a programme family
    assert not matching.same_programme("Interreg", "Interreg Central Baltic")                     # one word never names a call
    rows = [{"name": "Interreg Central Baltic", "next_deadline": CLOSED_CELL}, {"name": "Interreg Baltic Sea Region", "next_deadline": "not read"}]
    assert matching.declared_call(TWIN, rows)["name"] == "Interreg Central Baltic"
    assert matching._declared_programme(TWIN, rows)["name"] == "Interreg Central Baltic"
    assert matching.declared_call("Interreg", rows) is None


def test_the_matchmaker_reads_the_declared_closed_call_under_the_datasets_name_too(th):
    conn = store.open_db(thesis=th)
    try:
        reg = matchmaker_orgs.registry(conn, th)
        twin = next(o for o in reg["orgs"] if o["full_name"] == TWIN)
        assert twin["deadline"]["open"] is False and twin["deadline"]["text"] == CLOSED_CELL
        today = store._today(None)
        closed = {o["id"] for o in reg["orgs"] if matchmaker._open(o, today)}
        assert twin["id"] in closed
        for key in (VIVA, "3166759-6"):        # no company is ever pointed at a closed call
            res = matchmaker.match_company(key, th, conn=conn, limit=50)
            assert res and not {c["id"] for c in res["counterparts"]} & closed
        out = matchmaker.match_org(twin["id"], th, conn=conn)
        assert out["startups"] == [] and out["org"]["closed_note"]
    finally:
        conn.close()


def _fund_row(name, target_id):
    return {"target_id": target_id, "target_side": "capital", "target_type": "public_funder", "score": 0.6, "why": "caps ['C3']; stage 1.0",
            "confidence": "medium", "name": name, "source_url": "https://example.org/" + target_id, "status": "active"}


def test_a_closed_call_is_never_the_next_support_on_the_headline(th, monkeypatch):
    """The judge's case: Viva Jets was told to seek a grant from the Interreg Central Baltic programme, whose declared call closed in 2025."""
    rows = [_fund_row(TWIN, "BE0092"), _fund_row("Baltic Sea Action Plan (BSAP) Fund (NIB + NEFCO)", "BE0100")]
    monkeypatch.setattr(matching, "_eco_rows", lambda conn, key: [dict(r) for r in rows] if key == VIVA else [])
    conn = store.open_db(thesis=th)
    try:
        nxt = matching.who_comes_next(VIVA, th, conn=conn)
        names = [r["name"] for k in ("investors", "funding", "partners") for r in nxt[k]]
        assert TWIN not in names and "Baltic Sea Action Plan (BSAP) Fund (NIB + NEFCO)" in names
        m = memo.build(conn, th, VIVA)
        said = json.dumps({"note": m["recommendation"].get("note"), "actions": m.get("actions"), "meet": m.get("meet")}, ensure_ascii=False)
        assert "Interreg" not in said and "a grant from Baltic Sea Action Plan" in m["recommendation"]["note"]
        assert "Interreg" not in json.dumps(matching.next_step(VIVA, th, conn=conn))
    finally:
        conn.close()


def test_a_declared_deadline_in_the_past_leaves_the_programme_out_relative_to_today(th, monkeypatch):
    real = matching._programme_rows

    def rows(thesis_):
        out = [dict(r) for r in real(thesis_)]
        for r in out:
            if r["name"].startswith("BlueInvest E-Pitching"):
                r["next_deadline"] = "2026-10-01"
        return out

    monkeypatch.setattr(matching, "_programme_rows", rows)
    conn = store.open_db(thesis=th)
    try:
        before = [r["name"] for r in matching.who_comes_next(VIVA, th, conn=conn, today="2026-09-20")["funding"]]
        after = [r["name"] for r in matching.who_comes_next(VIVA, th, conn=conn, today="2026-10-02")["funding"]]
    finally:
        conn.close()
    assert any(n.startswith("BlueInvest E-Pitching") for n in before) and not any(n.startswith("BlueInvest E-Pitching") for n in after)


def test_public_funding_says_watch_for_the_next_call_and_ranks_a_closed_call_last(th):
    conn = store.open_db(thesis=th)
    try:
        ctx = matching.company_context(conn, VIVA)
        eco = matching._eco_db()
        if eco is None:
            pytest.skip("no ecosystem dataset")
        try:
            prof = matching._eco_profile(eco, ctx)
            got = matching._public_funding(conn, eco, prof, ctx, matching._topic_words(ctx, th, prof), store._today(None), matching._programme_rows(th))
        finally:
            eco.close()
    finally:
        conn.close()
    twin = [r for r in got if r["name"] == TWIN]
    if not twin:
        pytest.skip("the dataset does not offer the programme to this company")
    assert twin[0]["reason"].endswith("watch for the next call.") and twin[0]["_key"][0] == 4
    assert all(r["_key"][0] < 4 for r in got if "watch for the next call" not in r["reason"])


def test_a_stored_who_to_meet_sentence_naming_a_closed_call_is_left_out(th):
    now = {"decision": None, "fallback": False, "bands": {}, "impact": "", "closed": matching.closed_calls(th, store._today(None))}
    assert "Interreg Central Baltic" in now["closed"] and not any(len(n.split()) < 2 for n in now["closed"])
    stale = f"The who-comes-next lists name Meyer Turku as an investor, {TWIN} as a programme or funding source and Eckerö Line Abp as a partner."
    assert briefs.stale_reason(stale, "who_to_meet", now) == "names Interreg Central Baltic, whose call is closed"
    assert briefs.stale_reason("The lists name Meyer Turku as an investor.", "who_to_meet", now) is None
    assert briefs.current_text(stale + " Meyer Turku leads.", "who_to_meet", now) == "Meyer Turku leads."


def test_aava_tools_say_a_closed_call_takes_no_one(th):
    ctx = ctx_for(th)
    d = json.loads(aava_tools.run_tool(ctx, "list_organisations", {"text": "interreg central baltic"})[0])
    assert d["organisations"] and all(o["call"].endswith("watch for the next call") for o in d["organisations"])
    twin = next(o["org_id"] for o in d["organisations"] if o["name"] == TWIN)
    x = json.loads(aava_tools.run_tool(ctx, "explain_match", {"company_key": VIVA, "org_id": twin})[0])
    assert x["listed_as_a_counterpart"] is False and x["excluded_because"].endswith("watch for the next call")
    open_ones = json.loads(aava_tools.run_tool(ctx, "list_organisations", {"text": "redstone"})[0])
    assert all("call" not in o for o in open_ones["organisations"])
    ctx.close()


# ---- D77: who should an organisation meet ------------------------------------------------------------------------------------------------
def test_get_org_matches_is_the_match_page_list_in_its_order(th):
    ctx = ctx_for(th)
    page = matchmaker.match_org("apelago", th, conn=ctx.conn())       # what GET /match?org=apelago renders (radar/routes/match.py)
    text, ok = aava_tools.run_tool(ctx, "get_org_matches", {"org": "A'Pelago"})
    d = json.loads(text)
    assert ok and d["organisation"]["org_id"] == "apelago" and d["match_page"] == "/match?org=apelago"
    want = page["startups"][:5]
    assert [s["company_key"] for s in d["startups"]] == [s["key"] for s in want] and [s["rank"] for s in d["startups"]] == [1, 2, 3, 4, 5]
    for got, w in zip(d["startups"], want):
        assert got["reasons_that_hold"] == [c["chip"] for c in w["components"] if c["met"] and c.get("chip")]
        assert got["verdict_path"].startswith(w["verdict"]) and got["page"] == w["url"]
        assert ctx.seen[w["key"]] == w["name"]
    assert d["startups_listed"] == page["listed"] and d["already_connected"]["count"] == len(page["connected"])
    assert "apelago" in ctx.seen_orgs and "/match?org=apelago" in ctx.urls
    ctx.close()


def test_get_org_matches_reads_the_name_as_written_and_says_the_investor_pipeline(th):
    ctx = ctx_for(th)
    for ref in ("Redstone Blue", "redstone blue", "redstone-blue", "Redstone"):
        d = json.loads(aava_tools.run_tool(ctx, "get_org_matches", {"org": ref})[0])
        assert d["organisation"]["org_id"] == "redstone-blue", ref
    page = matchmaker.match_org("redstone-blue", th, conn=ctx.conn())
    assert d["pipeline_note"] == page["pipeline"]["note"]
    assert [s["company_key"] for s in d["startups"]] == [s["key"] for s in page["startups"][:5]]
    early = [s for s in d["startups"] if page["pipeline"]["early_label"] in s["verdict_path"]]
    assert len(early) == sum(1 for s in page["startups"][:5] if s["early"])
    bad = json.loads(aava_tools.run_tool(ctx, "get_org_matches", {"org": "No Such Fund"})[0])
    assert "error" in bad and bad["did_you_mean"] == []
    short = json.loads(aava_tools.run_tool(ctx, "get_org_matches", {"org": "apelago", "limit": 2})[0])
    assert short["showing"] == 2
    ctx.close()


def test_the_tool_is_in_the_schema_the_status_labels_and_the_prompt():
    names = [t["name"] for t in aava_tools.tools_for(None)]
    assert "get_org_matches" in names and "get_org_matches" in aava_tools.HANDLERS and aava_llm.TOOL_LABELS["get_org_matches"]
    schema = next(t for t in aava_tools.tools_for(None) if t["name"] == "get_org_matches")
    assert schema["input_schema"]["required"] == ["org"] and "who should <organisation> meet" in schema["description"]
    p = aava_llm.system_prompt()
    assert "get_org_matches" in p and "(/match?org=apelago)" in p and "watch for the next call" in p
    assert "60 words" in aava_llm.ANSWER_SHAPE


def test_the_match_page_link_survives_only_when_the_tool_returned_it():
    urls = {"/match?org=apelago"}
    assert aava_entities.check_link("the full match list", "/match?org=apelago", {}, urls)[0] == "[the full match list](/match?org=apelago)"
    assert aava_entities.check_link("the full match list", "/match?org=nobody", {}, urls)[0] == "the full match list"
    assert aava_entities.check_link("x", "//evil.example/match?org=apelago", {}, {"//evil.example/match?org=apelago"})[0] == "x"


def test_a_who_should_meet_turn_names_the_match_list_and_links_its_page(th):
    ctx = ctx_for(th)
    page = matchmaker.match_org("apelago", th, conn=ctx.conn())
    ctx.close()
    a, b = page["startups"][0], page["startups"][1]
    answer = (f"A'Pelago's best fits are [{a['name']}](/c/{a['key']}) and [{b['name']}]({b['url']}), both sharing its sector. "
              "See [the full match list](/match?org=apelago); a made-up [list](/match?org=other) is not kept.\n"
              "Follow-ups: Why Aellia? | Who else fits?")
    msgs = aava_llm.clean_messages([{"role": "user", "content": "Who should A'Pelago meet?"}], aava_llm.settings())
    client = FakeClient([call(tools=[("get_org_matches", {"org": "A'Pelago"})]), call(text=answer)])
    turn = aava_llm.Turn(msgs, th, client=client)
    evs = list(turn.events())
    turn.ctx.close()
    assert any(e["event"] == "status" and e["data"].get("label") == "reading the match list" for e in evs)
    done = evs[-1]["data"]
    assert "[the full match list](/match?org=apelago)" in done["text"] and "(/match?org=other)" not in done["text"]
    assert done["keys"][:2] == [a["key"], b["key"]] and done["unverified"] == []
    res = json.loads(tool_results(client.messages.calls[1]["messages"])[0]["content"])
    assert [s["company_key"] for s in res["startups"][:2]] == [a["key"], b["key"]]


def test_the_fallback_names_the_same_list_and_links_the_match_page(th):
    from radar.routes.aava import _inputs
    for oid in ("apelago", "redstone-blue"):
        home_orgs.ranking(th, oid, wait=None)
    conn = store.open_db(thesis=th)
    try:
        for q, oid in (("Who should A'Pelago meet?", "apelago"), ("Which startups fit Redstone Blue?", "redstone-blue")):
            got = ask.resolve(q, th, conn, inputs=_inputs, has_match=True, thesis_id=th["id"])
            page = matchmaker.match_org(oid, th, conn=conn)
            assert got["intent"] == "match" and got["url"].startswith(f"/match?org={oid}"), q
            first = [s["name"] for s in page["startups"][:3]]
            assert f"the match view puts {', '.join(first[:-1])} and {first[-1]} first" in got["say"], q
            assert "ranked" not in got["say"] and ("already connected" in got["say"]) == bool(page["connected"]), q      # D38
            assert [i["url"] for i in got["items"]] == [f"/c/{quote(s['key'], safe='')}" for s in page["startups"][:5]], q   # ask.py quotes a key ('name:...' keys too)
    finally:
        conn.close()


def test_the_chat_without_the_model_answers_who_should_meet_with_the_same_list(th, monkeypatch):
    from fastapi.testclient import TestClient
    from radar import home_list
    from radar.routes import aava_chat
    import app
    aava_chat.limiter.reset()
    home_list.for_template(th, wait=None)
    home_orgs.ranking(th, "apelago", wait=None)
    r = TestClient(app.app).post("/api/aava/chat", json={"messages": [{"role": "user", "content": "Who should A'Pelago meet?"}]}, headers={"X-Aava-Demo": "1"})
    events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in r.text.strip().split("\n\n")]
    done = dict(events)["done"]
    assert dict(events)["error"]["kind"] == "no_key" and done["fallback"] is True
    conn = store.open_db(thesis=th)
    try:
        first = matchmaker.match_org("apelago", th, conn=conn)["startups"][0]
    finally:
        conn.close()
    assert f"[{first['name']}](/c/{first['key']})" in done["text"] and "(/match?org=apelago" in done["text"]
