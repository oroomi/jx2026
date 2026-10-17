import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import db, emit, frameworks

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

U = "https://example.test/fixture/"


def _co(conn, key, name="Fixture Oy", **kw):
    emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key, country="FI", group_tag="cohort",
                        source_url=U + "reg/" + key, **kw)


def _sig(conn, key, ty, date, n=1, detail="Fixture signal."):
    emit.emit_signal(conn, company_key=key, signal_type=ty, date=date, source_url=f"{U}{ty}/{key}/{n}",
                     confidence="high", adapter="fixture", detail=detail)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    conn = db.connect(path)
    _co(conn, "9100001-1", industry_desc="Fixture wastewater treatment")
    _sig(conn, "9100001-1", "register_entry", "2024-06-10")
    _sig(conn, "9100001-1", "bf_funding", "2025-01-01", detail="Fixture funding granted in 2025 (year only).")
    _sig(conn, "9100001-1", "public_contract", "2026-09-04", detail="Port Fixture: dredging (EUR 10)")
    _co(conn, "9100002-2", name="Fixture Solo Oy")
    _sig(conn, "9100002-2", "register_entry", "2024-06-10")
    _sig(conn, "9100002-2", "register_entry", "2025-06-10", n=2)
    sid = conn.execute("SELECT id FROM signals WHERE company_key='9100001-1' AND signal_type='bf_funding'").fetchone()[0]
    conn.execute("INSERT INTO signal_meta (signal_id, date_precision) VALUES (?, 'year')", (sid,))
    conn.commit()
    conn.close()
    monkeypatch.setenv("RADAR_DB", str(path))
    import app
    return TestClient(app.app)


def test_four_labels_in_brief_words(client):
    t = client.get("/c/9100001-1").text
    for label in ("Ocean Impact Readiness (Ocean Impact Navigator)", "Business Readiness Level (KTH BRL) 1-9",
                  "Technology Readiness Level (Aalto TRL) 1-9",
                  "Investment Readiness 1-9, read from the ten Investment Potential dimensions"):
        assert label in t
    assert "measured outcome published:" in t
    assert not re.search(r"Business 1-5|IRL 1-9|Ocean impact 1-5", t)


def test_levels_follow_printed_rules(client):
    t = client.get("/c/9100001-1").text
    assert "level 6 of 9" in t   # BRL: first public contract
    assert "level 4 of 9" in t   # TRL: the Business Finland grant; a public contract sets no TRL (D84)
    assert "level 7 of 9" not in t
    assert "level 3 of 9" in t   # IRL: public non-dilutive funding
    assert "wastewater" in t and "water quality" in t


def test_ten_dimensions_with_only_sourced_chips(client):
    t = client.get("/c/9100001-1").text
    for d in frameworks.DIMENSIONS:
        assert d.replace("&", "&amp;") in t
    sparse = client.get("/c/9100002-2").text
    assert sparse.count("not in public records") >= 10


def test_dimensions_without_source_never_filled():
    a = frameworks.assess({}, [])
    assert [d["name"] for d in a["dimensions"]] == list(frameworks.DIMENSIONS)
    assert all(not d["evidence"] for d in a["dimensions"])
    assert a["brl"]["level"] is None and a["trl"]["level"] is None and a["irl"]["level"] is None


def test_connection_sentence_needs_two_source_types(client):
    rich = client.get("/c/9100001-1").text
    assert "Connections across records" in rich
    i = rich.index("Connections across records")
    seg = rich[i:i + 1500]
    assert seg.index("June 2024") < seg.index("2025 (year only)") < seg.index("September 2026")
    assert "https://example.test/fixture/register_entry/9100001-1/1" in seg
    solo = client.get("/c/9100002-2").text
    assert "Connections across records" not in solo and 'class="connect"' not in solo


def test_method_frameworks_and_connectors(client):
    t = client.get("/method").text
    for url in frameworks.URLS.values():
        assert url in t
    for n in ("LinkedIn", "Dealroom", "Tracxn", "PitchBook", "Crunchbase"):
        assert f"{n}: connector slot: not connected, no data shown" in t
    assert "coming soon" not in t.lower()


def test_no_em_dash_in_owned_files():
    files = list((ROOT / "radar/templates").glob("company*.html")) + list((ROOT / "radar/templates").glob("method*.html"))
    files += [ROOT / "radar/frameworks.py", ROOT / "config/frameworks.yaml", Path(__file__)]
    for f in files:
        assert chr(0x2014) not in f.read_text(encoding="utf-8"), f
