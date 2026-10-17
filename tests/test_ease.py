"""Ease of use (jx20): plain words on screen, 390 px phone layout, tap targets of at least 44 px. Data is the synthetic company fixture."""
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import company_fixture as fx  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BANNED = ("signal_type", "adapter", "thesis.yaml", "slug", "TOL", "cohort DB", "rc0")
BANNED_RE = re.compile(r"(?<![\w.])(" + "|".join(re.escape(w) for w in BANNED) + r")(?![\w])")
PAGES = ("/", "/c/9000001-1", "/radar", "/how", "/method", "/backtest", "/c/nope-0", "/no-such-page")


@pytest.fixture()
def dbpath(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    fx.build(path).close()
    monkeypatch.setenv("RADAR_DB", str(path))
    return path


def _template_text():
    """Template source with every Jinja tag removed, so only literal screen words remain."""
    out = []
    for f in sorted((ROOT / "radar" / "templates").glob("*.html")):
        t = re.sub(r"\{#.*?#\}|\{%.*?%\}|\{\{.*?\}\}", " ", f.read_text(), flags=re.S)
        out.append((f.name, t))
    return out


def test_no_banned_internal_words_in_template_text():
    hits = [(n, m.group(1)) for n, t in _template_text() for m in BANNED_RE.finditer(t)]
    assert hits == []


def test_no_banned_internal_words_on_rendered_pages(dbpath):
    import app
    c = TestClient(app.app)
    for url in PAGES:
        body = re.sub(r"<(script|style|code)\b.*?</\1>", " ", c.get(url).text, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", body)
        assert BANNED_RE.findall(text) == [], url


def test_first_screen_words(dbpath):
    import app
    t = TestClient(app.app).get("/").text
    for s in ("Early signals of blue-economy startups, for fund and accelerator teams.", "Every line links to the public record.",
              'placeholder="Type a startup name, for example Viva Jets"', "New this quarter", "Judge one startup", "The Nordic Blue 19"):
        assert s in t


def test_not_found_pages_are_styled_plain_words(dbpath):
    import app
    c = TestClient(app.app)
    r = c.get("/no-such-page")
    assert r.status_code == 404 and "<h1>" in r.text and "Traceback" not in r.text
    r = c.get("/c/nope-0")
    assert r.status_code == 404 and "No public record found for this name yet." in r.text and "ending in Oy" in r.text
    r = c.get("/search?q=zzzz")
    assert "No public record found for zzzz in" in r.text
    assert c.get("/healthz").json() == {"ok": True}


def test_how_is_gone_and_old_links_land_on_the_rules(dbpath):
    """The 60-second guide described a start page that no longer exists (D73): /how sends visitors to the rules page, and no page links to it."""
    import app
    c = TestClient(app.app)
    r = c.get("/how", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/method"
    assert "Rules" in c.get("/how").text and 'href="/how"' not in c.get("/").text
    assert not (ROOT / "radar" / "templates" / "how.html").exists() and not (ROOT / "radar" / "static" / "how").exists()


def test_company_questions_in_order_with_see_why(dbpath):
    import app
    t = TestClient(app.app).get("/c/9000001-1").text
    h = [t.index(x) for x in ("</span> Who is most promising", "</span> How ready are they", "</span> Who comes next", "</span> What should happen next")]
    assert h == sorted(h) and 'class="why-box"' in t and "See why" in t
    if "Connections across records" in t:  # the connection sentence sits directly under the name, before question 01
        assert t.index("<h1>") < t.index("Connections across records") < t.index('id="q1"')


@pytest.fixture()
def live_server(dbpath):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    env = {**__import__("os").environ, "RADAR_DB": str(dbpath)}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        yield f"http://127.0.0.1:{port}"
    finally:
        p.terminate()
        p.wait(timeout=10)


MEASURE = """() => {
  const out = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, summary')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    out.push({tag: el.tagName, text: (el.textContent || el.name || '').trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height)});
  }
  return {items: out, scrollW: document.documentElement.scrollWidth};
}"""


def test_phone_390_no_horizontal_scroll_and_44px_targets(live_server):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"no browser: {e}")
        page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
        small = []
        for url in ("/", "/c/9000001-1", "/radar", "/how"):
            page.goto(live_server + url)
            res = page.evaluate(MEASURE)
            assert res["scrollW"] <= 390, (url, res["scrollW"])
            for i in res["items"]:
                if i["w"] < 44 or (i["tag"] != "A" and i["h"] < 44):  # links sit in prose lines, so only their width is held to 44
                    small.append((url, i))
        browser.close()
    assert small == [], small
