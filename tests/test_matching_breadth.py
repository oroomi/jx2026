"""Who comes next, five groups (jx39), on the committed snapshot store and the declared ecosystem dataset."""
import sqlite3
from pathlib import Path

import pytest

from radar import matching, thesis

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
ECO = ROOT / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"
TODAY = "2026-10-17"
VIVA, ARCTIC = "2962040-6", "3166759-6"
GROUP_KEYS = [g for g, _ in matching.GROUPS]
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file() or not ECO.is_file(),
                                reason="snapshot store or ecosystem dataset not in this checkout")


@pytest.fixture()
def nxt(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.delenv("RADAR_DB", raising=False)
    th = thesis.load()
    return lambda key, limit=5: matching.who_comes_next(key, th, limit, today=TODAY)


@pytest.mark.parametrize("key", [VIVA, ARCTIC])
def test_demo_companies_get_three_groups_with_two_rows(nxt, key):
    n = nxt(key)
    full = [g for g in GROUP_KEYS if len(n[g]) >= 2]
    assert len(full) >= 3, {g: len(n[g]) for g in GROUP_KEYS}


@pytest.mark.parametrize("key", [VIVA, ARCTIC])
def test_every_row_has_reason_link_date_and_rank(nxt, key):
    n = nxt(key)
    assert set(n) >= {"investors", "funding", "partners", *GROUP_KEYS}  # the old keys stay, groups are added
    for g in GROUP_KEYS:
        assert [r["rank"] for r in n[g]] == list(range(1, len(n[g]) + 1))
        for r in n[g]:
            assert r["name"] and r["kind"] and r["reason"] and "date" in r
            assert r["source_url"].startswith(("http://", "https://")) and "linkedin.com" not in r["source_url"]


def test_organisations_only(nxt):
    people = {r[0] for r in sqlite3.connect(f"file:{ECO}?mode=ro", uri=True).execute("SELECT name FROM person") if r[0]}
    for key in (VIVA, ARCTIC):
        n = nxt(key, limit=50)
        names = {r["name"] for g in GROUP_KEYS for r in n[g]}
        assert not names & people
        assert not any(p in r["reason"] for g in GROUP_KEYS for r in n[g] for p in people if len(p) > 5)


def test_groups_rank_the_closest_evidence_first(nxt):
    viva = nxt(VIVA)
    assert viva["public_funding"][0]["name"] == "Business Finland" and "this company" in viva["public_funding"][0]["reason"]
    assert "same industry code 30120" in viva["buyers"][0]["reason"]
    arctic = nxt(ARCTIC, limit=20)
    assert any("aquacultur" in r["reason"] for r in arctic["project_partners"])
    assert {"Natural Resources Institute Finland (Luke)"} <= {r["name"] for r in arctic["research_institutes"]}
    funders = [r["name"] for r in arctic["public_funding"]]
    assert "Business Finland" in funders and any("EMKVR" in f for f in funders)  # stage ranks public funders, never removes them


def test_buyers_need_the_company_category_not_a_thesis_word_alone(nxt):
    arctic = nxt(ARCTIC, limit=50)
    assert not any("vesikat" in r["reason"].casefold() for r in arctic["buyers"])  # a roof repair is not water work


def test_cohort_company_still_gets_investors_from_the_lists(nxt):
    arctic = nxt(ARCTIC)
    assert len(arctic["investors"]) >= 2
    assert not any(r["name"].startswith(("Redstone", "A'Pelago")) for r in arctic["investors"])  # the partners themselves


def test_rank_rule_and_group_rules_are_printed():
    assert "five groups" in matching.RANK_RULE
    assert set(matching.GROUP_RULES) == set(GROUP_KEYS)


RAW = ("[", "]", "kw ", "caps ", "(", ")", '"')


def test_no_reason_carries_raw_tokens(nxt, monkeypatch):
    import sqlite3 as sq
    keys = [r[0] for r in sq.connect(f"file:{SNAP / 'radar_redstone_apelago_blue.sqlite'}?mode=ro", uri=True).execute(
        "SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio')")]
    seen = 0
    for key in [VIVA, ARCTIC, *keys]:
        n = nxt(key, limit=20)
        for g, rows in n.items():
            for r in rows:
                seen += 1
                assert not any(tok in r["reason"] for tok in RAW), (key, g, r["reason"])
                assert r["reason"].endswith(".") and r["reason"][0].isupper()
    assert seen > 50


def test_plain_why_reads_the_dataset_reason_string():
    s = matching.plain_why("caps ['C10', 'C3']; kw []; stage 1.0", 67.5)
    assert s.startswith("Shares Maritime decarbonisation and energy and Coastal tourism, boating and marine services with the company")
    assert "C3" not in s and "C10" not in s and "stage fits" in s and "the declared ecosystem research rates the fit" in s  # labels, never the bare codes (D24); no number (D36)
    assert "68" not in s and "dataset match" not in s
    assert "kw" not in s and "[" not in s and "shared keywords" not in s  # no empty keyword clause
    s = matching.plain_why("caps ['C5']; kw ['fish side-streams']; stage 0.5; impact 2/5")
    assert "shared keywords fish side-streams" in s and "stage overlap partial" in s and "the declared ecosystem research rates its impact" in s and "2 of 5" not in s
    assert matching._plain("the company's stage (seed) \"x\" [y]") == "the company's stage, seed, x, y"
