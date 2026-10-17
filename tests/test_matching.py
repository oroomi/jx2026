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
    n = matching.who_comes_next("no-such-key", th, conn=conn)
    assert set(n) >= {"investors", "funding", "partners"} and not any(n.values())  # added groups are empty too


def test_defunct_company_gets_no_leads(world):
    conn, th = world
    key = conn.execute("SELECT company_key FROM eco_entity WHERE entity_id='S3'").fetchone()[0]
    n = matching.who_comes_next(key, th, conn=conn, today=TODAY)
    assert set(n) >= {"investors", "funding", "partners"} and not any(n.values())  # added groups are empty too
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


def _names(conn, th, key="9100001-1", kind="funding"):
    return [r["name"] for r in matching.who_comes_next(key, th, limit=20, conn=conn, today=TODAY)[kind]]


def test_row_without_a_reason_is_hidden(world):
    conn, th = world
    assert "Fixture Angels" in _names(conn, th, kind="investors")
    conn.execute("UPDATE eco_match SET why='' WHERE target_id=(SELECT entity_id FROM eco_entity WHERE name='Fixture Angels')")
    names = _names(conn, th, kind="investors")
    assert "Fixture Angels" not in names and "Fixture Capital" in names
    assert all(r["reason"].strip() for k in ("investors", "funding", "partners") for r in matching.who_comes_next("9100001-1", th, conn=conn, today=TODAY)[k])


def test_trl_window_applies_to_a_dataset_funding_row(world, tmp_path):
    conn, th = world
    assert "Fixture Fund" in _names(conn, th)
    prog = tmp_path / "p2.csv"
    fx.write_programmes(prog, [{"name": "Fixture Fund", "type": "grant", "TRL_window_if_stated": "TRL 7-9", "next_deadline": "rolling", "source_url": "https://prog.example.test/fund"}])
    assert "Fixture Fund" not in _names(conn, dict(th, matching={"programmes": str(prog)}))     # company TRL 6 is outside the window
    fx.write_programmes(prog, [{"name": "Fixture Fund", "type": "grant", "TRL_window_if_stated": "TRL 4-6", "next_deadline": "rolling", "source_url": "https://prog.example.test/fund"}])
    row = next(r for r in matching.who_comes_next("9100001-1", dict(th, matching={"programmes": str(prog)}), limit=20, conn=conn, today=TODAY)["funding"] if r["name"] == "Fixture Fund")
    assert "inside the stated window 4 to 6" in row["reason"]


def test_stage_check_is_two_way(world, tmp_path):
    conn, th = world
    prog = tmp_path / "p3.csv"
    fx.write_programmes(prog, [
        {"name": "Fixture Studio", "type": "accelerator", "stage_window": "pre-seed, seed or early-stage with an MVP", "next_deadline": "2027-01-01", "source_url": "https://prog.example.test/studio"},
        {"name": "Fixture Scale Programme", "type": "accelerator", "stage_window": "growth and scale-up companies", "next_deadline": "2027-01-01", "source_url": "https://prog.example.test/scale"},
        {"name": "Fixture Both", "type": "accelerator", "stage_window": "seed to growth", "next_deadline": "2027-01-01", "source_url": "https://prog.example.test/both"}])
    th2 = dict(th, matching={"programmes": str(prog)})
    assert matching.stage_mismatch("series_a", "pre-seed, seed or early-stage") and matching.stage_mismatch("seed", "growth and scale-up companies")
    assert matching.stage_mismatch("seed", "seed to growth") is None and matching.stage_mismatch(None, "growth") is None
    names = _names(conn, th2)                                   # S1 is seed
    assert "Fixture Studio" in names and "Fixture Both" in names and "Fixture Scale Programme" not in names
    conn.execute("UPDATE eco_entity SET stage='series_a' WHERE business_id='9100001-1' OR company_key='9100001-1'")
    names = _names(conn, th2)
    assert "Fixture Studio" not in names and "Fixture Scale Programme" in names and "Fixture Both" in names
