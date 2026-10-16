import sqlite3
import sys
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import store_fixture as fx  # noqa: E402

from radar import store, thesis as thesis_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def conn(tmp_path):
    c = fx.build(tmp_path / "t.sqlite")
    yield c
    c.close()


@pytest.fixture
def th():
    return thesis_mod.load()


def keys(rows):
    return [r["company_key"] for r in rows]


def test_window_boundary(conn, th):
    k = keys(store.feed(conn, th, today=fx.TODAY))
    assert "T-edge90" in k and "T-edge91" not in k


def test_future_dropped_and_counted(conn, th):
    assert "T-future" not in keys(store.feed(conn, th, today=fx.TODAY))
    assert store.feed_counts(conn, th, today=fx.TODAY)["future_dated"] == 1


def test_declared_excluded_by_default(conn, th):
    k = keys(store.feed(conn, th, today=fx.TODAY))
    assert "T-cohort" not in k and "T-port" not in k
    assert store.feed_counts(conn, th, today=fx.TODAY)["excluded_declared"] == 2
    k2 = keys(store.feed(conn, th, today=fx.TODAY, group=None))
    assert "T-cohort" in k2 and "T-port" in k2
    assert keys(store.feed(conn, th, today=fx.TODAY, group="cohort")) == ["T-cohort"]


def test_earliest_in_window_signal_and_counts(conn, th):
    row = next(r for r in store.feed(conn, th, today=fx.TODAY) if r["company_key"] == "T-multi")
    assert row["signal_type"] == "register_entry" and row["date"] == fx.day(40)
    assert row["signal_count"] == 2 and row["earlier_count"] == 1


def test_off_thesis_types_ignored(conn, th):
    assert "T-offlist" not in keys(store.feed(conn, th, today=fx.TODAY))


def test_tie_broken_by_confidence(conn, th):
    row = next(r for r in store.feed(conn, th, today=fx.TODAY) if r["company_key"] == "T-tie")
    assert row["confidence"] == "high" and row["signal_type"] == "public_contract"


def test_type_filter(conn, th):
    rows = store.feed(conn, th, today=fx.TODAY, signal_type="eu_project")
    assert keys(rows) == ["T-ita"]


def test_newest_first(conn, th):
    dates = [r["date"] for r in store.feed(conn, th, today=fx.TODAY)]
    assert dates == sorted(dates, reverse=True)


def test_low_confidence_carried(conn, th):
    row = next(r for r in store.feed(conn, th, today=fx.TODAY) if r["company_key"] == "T-low")
    assert row["confidence"] == "low"
    assert row["evidence"]["label"] == "jobs.example.test"


def test_counts_shape(conn, th):
    c = store.feed_counts(conn, th, today=fx.TODAY)
    assert set(c["by_type"]) == set(th["feed_signal_types"])
    assert c["by_type"]["blueinvest"] == 0
    assert sum(c["by_type"].values()) == c["companies"] == sum(c["by_confidence"].values())
    assert c["window_days"] == 90 and c["last_fetched"]


def test_search_diacritics(conn):
    assert [r["company_key"] for r in store.search(conn, "itameri")] == ["T-ita"]
    assert [r["company_key"] for r in store.search(conn, "ITÄMERI")] == ["T-ita"]
    assert store.search(conn, "0000009") and store.search(conn, "t-edge90")
    assert store.search(conn, "") == [] and store.search(conn, "   ") == []


def test_company_ordering(conn):
    c = store.company(conn, "T-multi")
    assert [s["date"] for s in c["signals"]] == [fx.day(5), fx.day(40), fx.day(120)]
    assert c["counts"]["signals"] == 3 and c["signals"][0]["evidence"]["label"] == "Business Finland export"
    assert store.company(conn, "nope") is None


def test_cohort_count(conn):
    assert store.cohort_count(conn) == 1


def test_evidence_labels():
    base = {"source_url": "https://www.example.test/a", "date": "2026-01-01", "fetched_at": "2026-02-02T00:00:00Z", "confidence": "medium"}
    assert store.evidence({**base, "adapter": "prh"})["label"] == "PRH/YTJ register"
    assert store.evidence({**base, "adapter": "hilma"})["label"] == "Hilma notice"
    assert store.evidence({**base, "adapter": "cordis"})["label"] == "CORDIS"
    ev = store.evidence({**base, "adapter": "mystery"})
    assert ev["label"] == "www.example.test" and ev["url"] == base["source_url"]
    assert ev["confidence_rule"].startswith("matched by an exact legal name")


def test_open_db_missing_and_readonly(tmp_path, conn):
    assert store.open_db(tmp_path / "missing.sqlite") is None
    ro = store.open_db(tmp_path / "t.sqlite")
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("DELETE FROM signals")
    ro.close()
    rw = store.open_db(tmp_path / "w.sqlite", readonly=False)
    rw.execute("SELECT 1 FROM companies")
    rw.close()


def test_open_db_env(tmp_path, conn, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "t.sqlite"))
    c = store.open_db()
    assert c.execute("SELECT COUNT(*) FROM companies").fetchone()[0] > 0
    c.close()


def test_context_is_single_seam(tmp_path, conn, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "t.sqlite"))
    t, c = store.context(None)
    assert t["geography"]["feed_window_days"] == 90 and c is not None
    c.close()
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "none.sqlite"))
    assert store.context(None)[1] is None


def test_rule_text(th):
    assert "90 days" in store.rule_text(th) and chr(0x2014) not in store.rule_text(th)


def test_chip_macros_render():
    env = Environment(loader=FileSystemLoader(ROOT / "radar" / "templates"))
    tpl = env.from_string('{% from "_chip.html" import chip, missing %}{{ chip(ev, True) }}{{ missing() }}')
    ev = store.evidence({"adapter": "prh", "source_url": "https://example.test/x", "date": "2026-09-01",
                         "fetched_at": "2026-10-16T10:00:00Z", "confidence": "high"})
    html = tpl.render(ev=ev)
    assert 'href="https://example.test/x"' in html and 'rel="noopener"' in html and 'target="_blank"' in html
    assert "fetched 2026-10-16" in html and "high confidence" in html
    assert "ev-missing" in html and "not in public records" in html
