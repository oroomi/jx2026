import pytest

from radar import earliness, thesis
from tests.fixtures import earliness_fixture as fx


@pytest.fixture()
def res(tmp_path):
    conn = fx.build(tmp_path / "e.sqlite")
    th = thesis.load(thesis.resolve(None))
    return earliness.backtest(conn, th, entry_dates_path=tmp_path / "absent.csv"), conn, th, tmp_path


def by(res):
    return {r["company_key"]: r for r in res["rows"]}


def test_population_is_cohort_only(res):
    r = res[0]
    assert r["total"] == 15 and "F-feed" not in by(r)


def test_earlier_and_months(res):
    r = by(res[0])["F-early"]
    assert r["group"] == "earlier" and r["months"] == 7 and r["timing"] == "7 months before"
    assert r["first_signal"]["confidence"] == "high" and r["first_signal"]["source_url"].startswith("https://example.test/")


def test_first_signal_is_the_earliest_counted(res):
    r = by(res[0])["F-earlier"]
    assert r["first_signal"]["type"] == "eu_project" and r["first_signal"]["date"] == "2024-03-01"
    assert [o["type"] for o in r["others"]] == ["register_entry"] and r["others"][0]["counted"] is True


def test_later_and_same_day_are_later(res):
    b = by(res[0])
    assert b["F-later"]["group"] == "later" and b["F-later"]["months"] < 0 and "months after" in b["F-later"]["timing"]
    assert b["F-same"]["group"] == "later" and b["F-same"]["months"] == 0


def test_year_only_counts_as_january_first_and_is_labelled(res):
    b = by(res[0])
    y = b["F-yearafter"]
    assert y["first_signal"]["date"] == "2026-01-01" and y["first_signal"]["year_only"] is True
    assert y["first_signal"]["date_label"] == "2026 (year only)" and y["group"] == "later" and "year only" in y["timing"]
    assert b["F-yearbefore"]["group"] == "earlier" and b["F-yearbefore"]["first_signal"]["date_label"] == "2024 (year only)"


def test_old_register_entry_listed_not_counted(res):
    r = by(res[0])["F-old"]
    assert r["group"] == "none" and r["first_signal"] is None and r["months"] is None
    assert len(r["others"]) == 1 and r["others"][0]["counted"] is False
    assert r["others"][0]["reason"] == "registered 2015-05-05, older than the radar's 5-year cut, not counted"


def test_blank_has_no_months_and_totals_sum(res):
    r = res[0]
    blank = by(r)["F-none"]
    assert blank["group"] == "none" and blank["months"] is None and blank["first_signal"] is None
    assert r["earlier"] + r["declared"] + r["later"] + r["none"] == r["total"]
    assert (r["earlier"], r["declared"], r["later"], r["none"]) == (5, 1, 3, 6)


def test_ordering_months_desc_blanks_last(res):
    rows = res[0]["rows"]
    months = [r["months"] for r in rows if r["months"] is not None]
    assert months == sorted(months, reverse=True)
    flags = [r["months"] is None for r in rows]
    assert flags == sorted(flags)


def test_blueinvest_note_never_changes_group(res):
    r = by(res[0])["F-bi"]
    assert r["group"] == "none" and r["first_signal"] is None
    assert r["notes"][0]["text"] == "listed in the BlueInvest pipeline, TRL 5, no date stated, not counted"


def test_csv_entry_date_replaces_reference(res, tmp_path):
    _, conn, th, _ = res
    csv = tmp_path / "entry.csv"
    csv.write_text("company,entry_date,source\nFixture Csv Oy,2025-09-01,https://example.test/fixture/entry\n", encoding="utf-8")
    out = by(earliness.backtest(conn, th, entry_dates_path=csv))
    r = out["F-csv"]
    assert r["reference_date"] == "2025-09-01" and r["reference_from_csv"] and "https://example.test/fixture/entry" in r["reference_source"]
    assert r["group"] == "later"           # 2025-11-01 is after its own entry date
    assert out["F-early"]["reference_date"] == "2026-01-01" and not out["F-early"]["reference_from_csv"]


def test_thesis_reference_key_wins(res):
    _, conn, th, tmp = res
    th2 = dict(th, backtest={**th.get("backtest", {}), "reference_date": "2025-08-01"})
    out = earliness.backtest(conn, th2, entry_dates_path=tmp / "absent.csv")
    assert out["reference_date"] == "2025-08-01" and out["reference_source"] == "thesis key backtest.reference_date"
    assert by(out)["F-early"]["group"] == "earlier"
    assert earliness.DEFAULT_REFERENCE_DATE == "2026-01-01"


def test_rule_text_has_every_clause(res):
    t = earliness.rule_text(res[2])
    for clause in ("group_tag cohort", "2026-01-01", "programme start month", "feed signal types", "no more than 5 years", "not counted",
                   "outside the thesis rule", "declared research", "medium or high", "four groups",
                   "1 January", "year only", "30.44", "rounded down", "N months before", "N months after", "strictly before",
                   "later or same", "No public signal", "add up to the cohort size", "BlueInvest", "never moves", "Confidence", "never proof"):
        assert clause in t, clause
    assert chr(0x2014) not in t


def test_register_entry_outside_the_thesis_rule_is_not_counted(res):
    r = by(res[0])["F-outside"]          # code 62100 is not on the thesis list, no thesis word anywhere
    assert r["group"] == "none" and r["first_signal"] is None
    assert [o["reason"] for o in r["others"]] == ["registered 2025-06-01, outside the thesis rule"] and not r["others"][0]["counted"]


def test_name_word_needs_a_second_source(res):
    b = by(res[0])
    assert b["F-name-only"]["group"] == "none"           # 'marine' in the legal name alone never admits
    c = b["F-corrob"]                                    # the register entry fails, the later CORDIS record is backed by the name word
    assert c["group"] == "earlier" and c["first_signal"]["type"] == "eu_project" and c["first_signal"]["date"] == "2025-07-01"
    assert "'marin'" in c["first_signal"]["rule"] and "register record" in c["first_signal"]["rule"]
    assert any(o["reason"] == "registered 2025-05-01, outside the thesis rule" for o in c["others"])


def test_first_signal_carries_the_admitting_rule(res):
    f = by(res[0])["F-early"]["first_signal"]
    assert "Industry code 03211" in f["rule"] and f["source_url"].startswith("https://example.test/")


def test_declared_research_is_a_separate_group(res):
    b = by(res[0])
    r = b["F-research"]       # declared research in March 2025, live CORDIS signal only after the reference date
    assert r["group"] == "declared" and r["first_signal"]["research"] is True and r["months"] == 10
    assert b["F-research-low"]["group"] == "none"        # low confidence research is not counted
    assert b["F-research-low"]["others"][0]["reason"] == "declared research with low confidence, not counted"


def test_headline_is_built_from_the_counts(res):
    r = res[0]
    h = r["headline"]
    assert h == earliness.headline(r)
    for n in (r["total"], r["earlier"], r["declared"], r["later"], r["none"]):
        assert str(n) in h
    assert "live public records" in h and "eclared research" in h and "January 2026" in h
