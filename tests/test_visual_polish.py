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


# One-line answers for questions 02 and 03 (radar/templates/_answers.html), built only from values the page shows.

def _answer(t, qid):
    m = re.search(r'<p class="answer-line" id="%s-answer">(.*?)</p>' % qid, t, re.S)
    return m and m.group(1)


def _section(t, qid):
    return t.split('<section id="%s"' % qid, 1)[1].split("</section>", 1)[0]


def test_answer_lines_on_kelluu(client):
    t = client.get("/c/2902007-2").text
    q2 = _answer(t, "q2")
    assert q2 == "Business readiness 4 of 9, technology 4 of 9, investment 4 of 9; ocean impact: no public evidence."
    sec = _section(t, "q2")
    assert sec.index("q2-answer") < sec.index('class="ready"'), "the answer comes before the evidence"
    assert sec.count("<strong>level 4 of 9</strong>") == 3, "every number in the line is a level the table shows"
    q3 = _answer(t, "q3")
    rows = [len(re.findall(r"<li>", part.split("</ol>")[0])) if "<ol>" in part else 0
            for part in _section(t, "q3").split('<div class="nx-list">')[1:]]
    assert q3.endswith("match; the first one is listed with its reason.")
    for n, word in zip(rows, ("investor", "funding programme", "partner")):
        assert (f"{n} {word}" in q3) == (n > 0), (rows, q3)


def test_answer_lines_on_a_company_with_no_evidence(client):
    t = client.get("/c/no-tunisea").text
    q2 = _answer(t, "q2")
    assert q2 == ("Business readiness: no public evidence, technology: no public evidence, "
                  "investment: no public evidence; ocean impact: no public evidence.")
    assert not re.search(r"\d", q2), "a missing level is never a number"
    assert _answer(t, "q3"), "question 03 always has its line"


def test_answer_macros_on_their_own():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(ROOT / "radar" / "templates")))
    mod = env.get_template("_answers.html").module
    none = {"level": None}
    assert "Business readiness: no public evidence, technology: no public evidence" in str(
        mod.ready_answer({"brl": none, "trl": none, "irl": none, "category": {"category": None}}))
    some = str(mod.ready_answer({"brl": {"level": 7}, "trl": none, "irl": {"level": 3}, "category": {"category": "Ocean data"}}))
    assert "Business readiness 7 of 9, technology: no public evidence, investment 3 of 9; ocean impact category Ocean data." in some
    assert "No investor, funding programme or partner matches in the dataset yet." in str(
        mod.next_answer({"investors": [], "funding": [], "partners": []}))
    two = str(mod.next_answer({"investors": [{}], "funding": [{}, {}], "partners": []}))
    assert "1 investor and 2 funding programmes match; the first one is listed with its reason." in two
    three = str(mod.next_answer({"investors": [{}] * 5, "funding": [{}] * 5, "partners": [{}] * 5}))
    assert "5 investors, 5 funding programmes and 5 partners match;" in three
