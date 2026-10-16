"""Visual polish (jx30), on the committed real-data snapshot: the first company row is the first thing after the
filters, kinds of record with no signals wait in one closed "More filters" disclosure, and type is readable."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
STATIC = ROOT / "radar" / "static"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot missing")

CLOSED_MORE = re.compile(r'<details class="more-filters">.*?</details>', re.S)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.delenv("RADAR_DB", raising=False)
    import app
    return TestClient(app.app)


def test_first_feed_row_comes_before_any_visible_zero_count_pill(client):
    t = client.get("/").text
    assert 'class="pill zero"' in t, "the snapshot has kinds of record with no signals"
    head = t[: t.index('class="feed-row')]
    # every zero-count pill before the first row sits inside the one closed disclosure, so none is on screen
    assert head.count('<details class="more-filters"') == 1 and "More filters" in head
    assert 'class="pill zero"' not in CLOSED_MORE.sub("", head)
    # and the pills with signals still come first, in the open
    nav = head[head.index('<nav class="pills"'):]
    assert nav.index('class="pill"') < nav.index('<details class="more-filters"')


def test_more_filters_opens_when_a_zero_kind_is_selected(client):
    t = client.get("/").text
    zero = re.search(r'class="pill zero" href="/\?type=(\w+)"', t).group(1)
    sel = client.get(f"/?type={zero}").text
    assert '<details class="more-filters" open>' in sel
    assert re.search(r'class="pill zero" href="/\?type=%s"[^>]*aria-current="true"' % zero, sel)


def test_body_text_is_at_least_17px_with_line_height_1_5():
    css = (STATIC / "app.css").read_text()
    m = re.search(r"body\{[^}]*font:\s*\d+\s+(\d+)px/([\d.]+)", css)
    assert m and int(m.group(1)) >= 17 and float(m.group(2)) >= 1.5
    assert not re.search(r"body\{[^}]*font-size:\s*1[0-6]px", css), "no rule shrinks body text again"


def test_no_text_under_14px_outside_the_svg_charts():
    small = []
    for f in sorted(STATIC.glob("*.css")):
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", f.read_text()):
            if re.search(r"\.bt-|\.mk|\.rd-tick|svg", sel):
                continue  # SVG text is sized in chart units and scaled with the chart
            for size in re.findall(r"font-size:\s*([\d.]+)(rem|px)", body):
                px = float(size[0]) * (16 if size[1] == "rem" else 1)
                if px < 14:
                    small.append((f.name, sel.strip(), size))
    assert not small, small
