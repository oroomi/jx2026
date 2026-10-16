"""Year-only signals print '<year> (year only)', never a day-level date."""
from jinja2 import Environment, FileSystemLoader

from radar import db, emit, store

ENV = Environment(loader=FileSystemLoader("radar/templates"))


def make():
    c = db.connect(":memory:")
    emit.upsert_company(c, company_key="1111111-1", name="Fixture Oy", y_tunnus="1111111-1", source_url="https://example.org", group_tag="cohort")
    emit.emit_signal(c, company_key="1111111-1", signal_type="bf_funding", date="2020-01-01", source_url="https://example.org/bf", confidence="high", adapter="businessfinland")
    emit.emit_signal(c, company_key="1111111-1", signal_type="register_entry", date="2021-03-04", source_url="https://example.org/p", confidence="high", adapter="prh")
    c.execute("INSERT INTO signal_meta (signal_id, date_precision) SELECT id,'year' FROM signals WHERE adapter='businessfinland'")
    return c


def test_company_signals_and_chip_render():
    c = make()
    d = store.company(c, "1111111-1")
    by = {s["signal_type"]: s for s in d["signals"]}
    assert by["bf_funding"]["date_label"] == "2020 (year only)" and by["bf_funding"]["evidence"]["date_precision"] == "year"
    assert by["register_entry"]["date_label"] == "2021-03-04"
    html = ENV.get_template("_chip.html").module.chip(by["bf_funding"]["evidence"])
    assert "2020 (year only)" in html and "2020-01-01" not in html and 'datetime="2020"' in html


def test_day_when_no_meta_table_or_row():
    c = db.connect(":memory:")
    c.execute("DROP TABLE signal_meta")
    ev = store.evidence({"date": "2020-01-01", "adapter": "businessfinland", "source_url": "https://x.org"})
    assert ev["date_precision"] == "day" and ev["date_label"] == "2020-01-01"
    rows = store.with_precision(c, [{"signal_id": 1, "date": "2020-01-01"}])
    assert rows[0]["date_label"] == "2020-01-01"


def test_blueinvest_label():
    assert store.SOURCE_LABELS["blueinvest"] == "BlueInvest pipeline"
