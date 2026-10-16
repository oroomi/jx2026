"""Judge-review fixes (items 4, 6, 7, 8, 9, 10), run on the committed real-data snapshot."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot missing")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.delenv("RADAR_DB", raising=False)
    import app
    return TestClient(app.app)


def test_item7_health_thesis_has_no_blue_wording(client):
    for path in ("/", "/how", "/method"):
        t = client.get(path + "?thesis=health_tech_turku").text
        body = t.split("<main", 1)[1].split("</main>", 1)[0]
        assert "blue" not in body.lower().replace("blueinvest", ""), path
        assert "Nordic Blue" not in t
    assert "health-tech startups" in client.get("/?thesis=health_tech_turku").text
    assert "blue-economy startups" in client.get("/?thesis=redstone_apelago_blue").text


def test_item8_unknown_name(client):
    t = client.get("/search?q=Zorbo%20Quantum").text
    assert "No public record found for Zorbo Quantum in Finland." in t
    assert "Try the registered legal name" in t and "Switch sector" in t and "appeared in public records" in t
    assert "thesis=health_tech_turku" in t
    assert 'class="feed-row' not in t


def test_item9_sources_never_bare_zero(client):
    t = client.get("/method").text
    # the Sources table is the tbody that lists sources (the Baltic country-depth table may come first)
    bodies = [b.split("</tbody>", 1)[0] for b in t.split("<tbody>")[1:]]
    table = next((b for b in bodies if "not loaded in this build" in b or "profiles" in b), bodies[0])
    cells = re.findall(r"<td>([^<]*)</td>", table)
    assert cells and all(c.strip() not in ("0", "") for c in cells)
    assert "Finnish profiles, no dated events" in table or "not loaded in this build" in table
    assert "not loaded in this build" in table


def test_item10_no_internal_text(client):
    t = client.get("/method").text
    for bad in ("RECON_", "The only way an source writes", "signal_type", "source_url", ".md</", ".csv"):
        assert bad not in t, bad
    assert "<pre" not in t
    assert "High:" in t and "Medium:" in t and "Low:" in t


def test_item6_business_finland_chip_and_sentence(client):
    t = client.get("/c/2902007-2").text
    assert "Business Finland funding export (year only), dashboard" in t
    assert "tietopankki.businessfinland.fi" in t
    assert "no link for each row" in client.get("/method").text


def test_item4_plain_confidence_and_sort(client):
    t = client.get("/").text
    assert "How sure: low, matched on industry code only" in t
    assert "keyword or code match only" not in t
    main = t.split('<details class="weak">')[0]
    order = [{"high": 0, "medium": 1, "low": 2}[c] for c in re.findall(r"conf conf-(high|medium|low)", main)]
    assert order == sorted(order)
