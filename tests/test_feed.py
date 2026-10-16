import re

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import feed_fixture


@pytest.fixture()
def client(tmp_path, monkeypatch):
    p = tmp_path / "feed.sqlite"
    feed_fixture.build(p)
    monkeypatch.setenv("RADAR_DB", str(p))
    import app
    return TestClient(app.app, follow_redirects=False)


@pytest.fixture()
def empty_client(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "missing.sqlite"))
    import app
    return TestClient(app.app, follow_redirects=False)


def names(html):
    return re.findall(r'class="co" href="/c/[^"]+">([^<]+)<', html)


def test_rows_and_order(client):
    r = client.get("/")
    assert r.status_code == 200
    assert names(r.text) == ["Synthetic Alpha", "Synthetic Beta", "Synthetic Gamma"]
    assert r.text.count('class="feed-row') == 3
    assert "250" in r.text and "EUR" in r.text
    assert "1 earlier signal" in r.text
    assert "How sure: low, matched on" in r.text and "keyword or code match only" not in r.text
    assert 'class="feed-row low"' in r.text


def test_footer_n_equals_rows(client):
    t = client.get("/").text
    n = int(re.search(r"(\d+) companies", t).group(1))
    assert n == t.count('class="feed-row') == 3
    assert "By confidence: high 2, medium 0, low 1" in t
    assert "excluded (1)" in t
    assert 'href="/method"' in t


def test_type_filter_and_partial(client):
    r = client.get("/feed/rows?type=register_entry")
    assert names(r.text) == ["Synthetic Beta", "Synthetic Gamma"]
    assert "<html" not in r.text and "<h1" not in r.text
    page = client.get("/?type=register_entry").text
    assert names(page) == ["Synthetic Beta", "Synthetic Gamma"]
    assert "<h1" in page


def test_unknown_type_ignored(client):
    assert len(names(client.get("/?type=nonsense").text)) == 3


def test_zero_type_shows_no_signals(client):
    t = client.get("/?type=job_ad").text
    assert names(t) == []
    assert "no signals of this type in the window" in t
    assert "no signals" in client.get("/").text


def test_search_unique_redirects(client):
    r = client.get("/search?q=alpha")
    assert r.status_code == 302 and r.headers["location"] == "/c/T-alpha"


def test_search_multiple_and_none(client):
    t = client.get("/search?q=synthetic").text
    assert "matches for" in t and "Synthetic Cohort" in t
    t = client.get("/search?q=zzzz").text
    assert "No public record found for zzzz in Finland." in t and "Try the registered legal name" in t and "Switch sector" in t
    assert 'class="feed-row' not in t


def test_search_escapes(client):
    t = client.get("/search", params={"q": "<script>alert(1)</script>"}).text
    assert "<script>alert(1)</script>" not in t
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in t


def test_empty_state(empty_client):
    t = empty_client.get("/").text
    assert t.count("no signals yet") == 1
    assert "Rule:" in t and 'class="feed-row' not in t


def test_zero_rows_in_db(tmp_path, monkeypatch):
    from radar import db
    p = tmp_path / "z.sqlite"
    db.connect(p).close()
    monkeypatch.setenv("RADAR_DB", str(p))
    import app
    t = TestClient(app.app).get("/").text
    assert "no signals yet" in t and 'class="feed-row' not in t


def test_no_absolute_asset_urls(client):
    t = client.get("/").text
    for m in re.finditer(r'<(?:link|script|img)[^>]+(?:href|src)="([^"]+)"', t):
        assert not m.group(1).startswith(("http:", "https:", "//")), m.group(1)
    assert "@import" not in t and "\u2014" not in t
