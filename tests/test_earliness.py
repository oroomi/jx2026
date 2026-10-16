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
    assert r["total"] == 10 and "F-feed" not in by(r)


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
    assert r["earlier"] + r["later"] + r["none"] == r["total"]
    assert (r["earlier"], r["later"], r["none"]) == (4, 3, 3)


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
                   "1 January", "year only", "30.44", "rounded down", "N months before", "N months after", "strictly before",
                   "on or after", "later or same", "No public signal", "add up to the cohort size", "BlueInvest", "never moves", "Confidence", "never proof"):
        assert clause in t, clause
    assert "—" not in t
