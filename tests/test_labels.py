"""Plain labels: one table (radar/labels.py) and no snake_case token in the visible text of the home, company, backtest and /data pages."""
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import round3_fixture as fx  # noqa: E402

SNAKE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")


def visible(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"https?://\S+", " ", text)  # a printed link is the source's own address, not our wording


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    fx.build(path).close()
    monkeypatch.setenv("RADAR_DB", str(path))
    import app
    return TestClient(app.app)


def test_every_signal_type_has_a_plain_label():
    from radar import emit, labels
    from radar.adapters import ecosystem, prh_notices, stitcher  # noqa: F401
    for t in (*emit.SIGNAL_TYPES, "eu_grant"):
        assert t in labels.SIGNAL_LABELS, t
        assert "_" not in labels.signal_label(t)
    assert labels.signal_label("some_new_type") == "Some new type"
    assert labels.source_label("prh_notices") == "PRH registered notices"


def test_store_and_method_use_the_one_table():
    from radar import labels, store
    from radar.routes import method
    assert store.TYPE_LABELS is labels.SIGNAL_LABELS and store.SOURCE_LABELS is labels.SOURCE_LABELS
    assert not hasattr(method, "EXTRA_TYPE_LABELS")


@pytest.mark.parametrize("url", ["/", "/c/9300001-1", "/c/9300005-5", "/c/dk-synthetic", "/backtest", "/data",
                                 "/data?view=signals", "/data?view=signals&source=prh_notices"])
def test_no_snake_case_token_on_the_page(client, url):
    r = client.get(url)
    assert r.status_code == 200
    found = sorted(set(SNAKE.findall(visible(r.text))))
    assert found == [], f"{url}: {found}"
