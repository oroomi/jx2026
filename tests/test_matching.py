import pytest

from radar import emit, matching, store, thesis
from radar.adapters import ecosystem
from tests.fixtures import ecosystem_fixture as fx

TODAY = "2026-10-16"


@pytest.fixture()
def world(tmp_path):
    ds = tmp_path / "eco.sqlite"
    fx.build_dataset(ds)
    conn = fx.build_radar(tmp_path / "r.sqlite")
    ecosystem.run(conn, None, path=ds)
    prog = tmp_path / "programmes.csv"
    fx.write_programmes(prog, [
        {"name": "Fixture Open Grant", "type": "grant", "stage_window": "companies under 5 years", "TRL_window_if_stated": "TRL 4-6",
         "next_deadline": "2026-12-01", "source_url": "https://prog.example.test/open"},
        {"name": "Fixture Late Call", "type": "grant", "stage_window": "any", "next_deadline": "2027-03-01", "source_url": "https://prog.example.test/late"},
        {"name": "Fixture Past Call", "type": "grant", "next_deadline": "2026-01-01", "source_url": "https://prog.example.test/past"},
        {"name": "Fixture Closed Call", "type": "grant", "next_deadline": "closed", "source_url": "https://prog.example.test/closed"},
        {"name": "Fixture High TRL Call", "type": "grant", "TRL_window_if_stated": "TRL 7-9", "next_deadline": "rolling", "source_url": "https://prog.example.test/hi"},
        {"name": "Fixture Old Firms Call", "type": "grant", "stage_window": "companies under 1 years", "next_deadline": "rolling", "source_url": "https://prog.example.test/old"},
        {"name": "Fixture Equity Pot", "type": "equity", "next_deadline": "rolling", "source_url": "https://prog.example.test/eq"},
    ])
    inv = tmp_path / "investors.csv"
    inv.write_text("name,type,stage,ticket_eur_min,ticket_eur_max,source_url\nFixture Capital,vc,seed,100000,500000,https://cap1.example.test\n", encoding="utf-8")
    th = dict(thesis.load())
    th["matching"] = {"programmes": str(prog), "investors": str(inv)}
    return conn, th


def test_lists_are_ranked_by_score_and_carry_the_reason_and_a_link(world):
    conn, th = world
    n = matching.who_comes_next("9100001-1", th, conn=conn, today=TODAY)
    assert [r["name"] for r in n["investors"]] == ["Fixture Angels", "Fixture Capital"]
    assert [r["rank"] for r in n["investors"]] == [1, 2]
    assert n["investors"][1]["reason"] == "caps ['C1']; kw ['x']; stage 1.0"
    assert n["investors"][1]["facts"] == "investors.csv: stage seed, ticket EUR 100000 to 500000"
    assert all(r["source_url"].startswith("https://") for k in n for r in n[k])
    assert n["investors"][0]["confidence"] == "low"       # the weaker of the two entities' dataset words (angel low, startup medium)
    assert [r["name"] for r in n["partners"]] == ["Fixture Buyer"]


def test_funding_list_keeps_open_programmes_only_and_a_slot_for_the_soonest(world):
    conn, th = world
    f = matching.who_comes_next("9100001-1", th, limit=2, conn=conn, today=TODAY)["funding"]
    assert [r["name"] for r in f] == ["Fixture Fund", "Fixture Open Grant"]    # scored first, last slot = soonest open programme
    names = [r["name"] for r in matching.who_comes_next("9100001-1", th, limit=9, conn=conn, today=TODAY)["funding"]]
    for gone in ("Fixture Past Call", "Fixture Closed Call", "Fixture High TRL Call", "Fixture Old Firms Call", "Fixture Equity Pot"):
        assert gone not in names
    assert "Fixture Late Call" in names


def test_limit_and_empty_state(world):
    conn, th = world
    assert len(matching.who_comes_next("9100001-1", th, limit=1, conn=conn, today=TODAY)["investors"]) == 1
    n = matching.who_comes_next("name:lonely", th, conn=conn, today=TODAY)
    assert n["investors"] == [] and n["partners"] == []
    assert matching.who_comes_next("no-such-key", th, conn=conn) == {"investors": [], "funding": [], "partners": []}


def test_defunct_company_gets_no_leads(world):
    conn, th = world
    key = conn.execute("SELECT company_key FROM eco_entity WHERE entity_id='S3'").fetchone()[0]
    assert matching.who_comes_next(key, th, conn=conn, today=TODAY) == {"investors": [], "funding": [], "partners": []}
    assert "defunct" in matching.next_step(key, th, conn=conn, today=TODAY)["because"]


def test_next_step_rule_1_open_programme(world):
    conn, th = world
    s = matching.next_step("9100001-1", th, conn=conn, today=TODAY)
    assert s["rule"] == 1 and s["sentence"] == "Introduce them to Fixture Open Grant before 2026-12-01"
    assert s["source_url"] == "https://prog.example.test/open" and "TRL 6" in s["because"]


def test_next_step_rule_2_public_buyer(world):
    conn, th = world
    emit.emit_signal(conn, company_key="name:lonely", signal_type="public_contract", date="2026-05-02", source_url="https://hilma.example.test/1",
                     confidence="high", adapter="hilma", detail="Fixture Buyer Oy: water quality sampling service (EUR 5,000)")
    emit.emit_signal(conn, company_key="9100001-1", signal_type="job_ad", date="2026-10-01", source_url="https://jobs.example.test/x", confidence="medium",
                     adapter="prh", detail="synthetic water quality note")
    conn.execute("UPDATE eco_readiness SET trl=NULL")
    th2 = dict(th, matching={})
    c = matching.company_context(conn, "9100001-1")
    assert c["category"] == "water quality"
    s = matching.next_step("9100001-1", th2, conn=conn, today=TODAY)
    assert s["rule"] == 2 and s["sentence"] == "Ask about their water quality contract with Fixture Buyer Oy (2026-05-02)"
    assert s["source_url"] == "https://hilma.example.test/1"


def test_next_step_rule_3_raise(world):
    conn, th = world
    emit.emit_signal(conn, company_key="9100001-1", signal_type="public_contract", date="2025-09-01", source_url="https://contract.example.test/1", confidence="high",
                     adapter="synthetic", detail="Fixture Agency: unrelated service (EUR 1,000)")   # TRL 7 by the rule
    emit.emit_signal(conn, company_key="9100001-1", signal_type="bf_funding", date="2026-04-01", source_url="https://bf.example.test/1", confidence="high",
                     adapter="businessfinland", detail="grant")
    s = matching.next_step("9100001-1", th, conn=conn, today=TODAY)
    assert s["rule"] == 3 and s["sentence"] == "Meet now: judge a raise, and introduce them to Fixture Angels"


def test_next_step_rule_4_check_in_and_rule_5(world):
    conn, th = world
    k = "name:fixture-domain"
    emit.emit_signal(conn, company_key=k, signal_type="register_entry", date="2024-05-01", source_url="https://example.test/r", confidence="high", adapter="prh")
    s = matching.next_step(k, th, conn=conn, today=TODAY)
    assert s["rule"] == 4 and s["sentence"] == "Check in: no public signal since 2024-05-01"
    assert matching.next_step("name:lonely", th, conn=conn, today=TODAY)["sentence"].startswith("Check in: no dated public signal")
    five = matching.next_step("9100002-2", th, conn=conn, today=TODAY)
    assert five["rule"] == 5 and five["sentence"] == "Watch: not enough public evidence for a next step yet" and five["source_url"] is None


def test_partner_organisations_are_excluded_from_the_feed(tmp_path):
    conn = fx.build_radar(tmp_path / "p.sqlite")
    th = thesis.load()
    for key, name in (("name:a", "A'Pelago Experience Ab"), ("name:b", "APelago Fixture Oy"), ("name:c", "Redstone Fixture Oy"),
                      ("name:d", "Turku Science Park Fixture Oy"), ("name:e", "Voima Ventures Oy"), ("name:f", "Fixture Marine Oy")):
        emit.upsert_company(conn, company_key=key, name=name, source_url="https://example.test/x", industry_code="30110")
        emit.emit_signal(conn, company_key=key, signal_type="eu_project", date=TODAY, source_url="https://example.test/" + key, confidence="high", adapter="cordis")
    names = {r["name"] for r in store.feed(conn, th, today=TODAY, limit=100)}
    assert names == {"Fixture Marine Oy"}
    assert store.is_partner_org("Tesi") and not store.is_partner_org("Fixture Marine Oy")
