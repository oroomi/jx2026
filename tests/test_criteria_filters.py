"""Home list: the criteria box on every row, the filter rail, and the filtered page, on the committed snapshot store (data/snapshot).
The rows are built once per module (the memos are the slow part, as the home list's own docstring says)."""
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import home_filter, home_list, thesis as thesis_mod

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")
KEYS = ("impact", "trl", "brl", "irl", "fit")


def _use_snapshot(mp):
    mp.setenv("RADAR_DATA_DIR", str(SNAP))
    mp.delenv("RADAR_DB", raising=False)
    mp.delenv("RADAR_THESIS", raising=False)
    mp.setenv("RADAR_NO_WARM", "1")


@pytest.fixture(autouse=True)
def _snapshot_env(monkeypatch):
    """tests/conftest.py points every test at an empty data directory; these tests read the committed snapshot instead."""
    _use_snapshot(monkeypatch)


@pytest.fixture(scope="module")
def H():
    mp = pytest.MonkeyPatch()
    _use_snapshot(mp)
    try:
        yield home_list.for_template(thesis_mod.load())
    finally:
        mp.undo()


@pytest.fixture()
def client():
    import app
    return TestClient(app.app)


def keys_in(html: str) -> list[str]:
    return re.findall(r'class="hc-row" href="/c/([^"]+)"', html)


def section(html: str) -> str:
    """The list section (#hc-list) of a page or of the /home/list fragment: from its opening tag to the note that closes it."""
    start = html.index('<div id="hc-list"')
    return html[start:html.index("</p>\n</div>", html.index('class="hc-note"', start)) + len("</p>\n</div>")]


# ---- 1. rows carry the criteria -----------------------------------------------------------------------------------------------------
def test_every_row_carries_the_five_criteria_and_the_verdict(H):
    assert H["rows"], "the snapshot has rows"
    for r in H["rows"]:
        assert set(KEYS) <= set(r["criteria"]) and "verdict" in r["criteria"]
        for k in ("trl", "brl", "irl"):
            c = r["criteria"][k]
            assert (c["level"] is None) == (c["text"] is None)
            if c["level"] is not None:
                assert 1 <= c["level"] <= 9 and c["text"] == f"{c['level']} of 9"
            else:
                assert "no public record" in c["title"]
        for k in ("impact", "fit"):
            c = r["criteria"][k]
            assert c["text"] in (None, "Low", "Medium", "High", "Not yet evidenced") or c["text"].endswith(" of 9")
            assert c["text"] is not None or "no public record" in c["title"]
        assert r["criteria"]["verdict"]["text"] == (r["verdict"].capitalize() if r["verdict"] else None)


def test_a_level_without_a_record_is_a_dash_and_never_a_number(H, client):
    none_trl = [r for r in H["rows"] if r["criteria"]["trl"]["level"] is None]
    assert none_trl, "some snapshot company has no TRL record"
    html = client.get("/").text
    for r in none_trl[:5]:
        li = html[html.index(f'href="/c/{r["company_key"]}"'):]
        li = li[:li.index("</li>")]
        cell = re.search(r'<span class="cr cr-trl cr-empty" title="([^"]*)">(.*?)</span>\s*<i class="cr-bar"', li, re.S)
        assert cell, "an empty TRL cell is marked cr-empty"
        assert "no public record" in cell.group(1)
        assert "of 9" not in cell.group(2) and "cr-none" in cell.group(2)


def test_levels_equal_the_company_page_levels(H):
    """The row never says a level the company page does not print: both read radar.frameworks.page_levels."""
    from radar import matching, store
    th = thesis_mod.load()
    conn = store.open_db(thesis=th)
    try:
        for r in H["rows"][:12]:
            fw = matching.company_context(conn, r["company_key"])["fw"]
            for k in ("trl", "brl", "irl"):
                assert r["criteria"][k]["level"] == fw[k]["level"], (r["name"], k)
    finally:
        conn.close()


def test_impact_cell_reads_an_ocean_impact_level_when_the_memo_has_one():
    fw = {"category": {"category": None}}
    m = {"ocean_impact": {"level": 6, "band": "Medium", "evidence": [{"source_label": "PRH/YTJ register"}], "level_max": 9},
         "levels": {"impact": {"band": "unknown"}}, "recommendation": {}}
    cell = home_list._impact_cell(m, fw)
    assert cell["text"] == "6 of 9" and cell["band"] == "Medium" and "PRH/YTJ register" in cell["title"]
    none = home_list._impact_cell({"levels": {"impact": {"band": "unknown"}}, "recommendation": {}}, fw)
    assert none["text"] is None and "no public record" in none["title"]
    cat = home_list._impact_cell({"levels": {"impact": {"band": "Medium"}}, "recommendation": {}}, {"category": {"category": "x", "keyword": "k", "evidence": {"label": "OpenAlex"}}})
    assert cat["text"] == "Medium" and "OpenAlex" in cat["title"] and "not a measured impact" in cat["title"]


def test_band_range_follows_the_thesis_cut():
    spec = {"low_max": 3, "high_min": 7}
    assert [home_list._band_range(n, spec) for n in (None, 1, 3, 4, 6, 7, 9)] == ["none", "1-3", "1-3", "4-6", "4-6", "7-9", "7-9"]
    assert home_list._age_band(None, date(2026, 10, 17)) == "none"
    assert [home_list._age_band(d, date(2026, 10, 17)) for d in ("2026-06-01", "2024-10-01", "2022-01-01", "2015-05-05")] == ["lt1", "1-3", "3-5", "gt5"]


# ---- 2. filtering -------------------------------------------------------------------------------------------------------------------
def test_filter_combination_returns_the_expected_subset(H):
    rows = H["rows"]
    sel = {"verdict": ["ACCELERATOR", "PARTNER INTRODUCTION"], "country": ["FI"], "fit": ["High"]}
    expected = [r["company_key"] for r in rows if r["verdict"] in sel["verdict"] and r["country"] == "FI" and r["fit"] == "High"]
    assert expected, "the combination is not empty on the snapshot"
    assert [r["company_key"] for r in home_filter.apply(rows, sel)] == expected
    # range on a level, and "no record" as a value
    sel = {"brl": ["4-6"], "trl": ["none"]}
    expected = [r["company_key"] for r in rows if r["criteria"]["brl"]["level"] in (4, 5, 6) and r["criteria"]["trl"]["level"] is None]
    assert [r["company_key"] for r in home_filter.apply(rows, sel)] == expected
    # member and deadline facets
    assert {r["group_tag"] for r in home_filter.apply(rows, {"member": ["cohort"]})} == {"cohort"}
    assert all(r["facets"]["deadline"] == ["90"] for r in home_filter.apply(rows, {"deadline": ["90"]}))


def test_counts_hold_the_other_facets_and_equal_the_rows_that_would_show(H):
    rows = H["rows"]
    sel = {"country": ["FI"], "brl": ["4-6"]}
    R = home_filter.rail(rows, sel, {})
    by = {f["param"]: {o["value"]: o["count"] for o in f["options"]} for f in R["facets"]}
    for v, n in by["verdict"].items():       # a facet that is not selected: counted inside the selection
        assert n == sum(1 for r in home_filter.apply(rows, sel) if v in r["facets"]["verdict"]), v
    for v, n in by["country"].items():       # the selected facet itself: counted with every OTHER facet held, so a sibling is a real alternative
        assert n == sum(1 for r in home_filter.apply(rows, {"brl": ["4-6"]}) if v in r["facets"]["country"]), v
    assert R["shown"] == len(home_filter.apply(rows, sel)) and R["of"] == len(rows) and R["n_active"] == 2


def test_the_rail_offers_every_asked_for_filter(H):
    R = home_filter.rail(H["rows"], {}, {})
    assert [f["param"] for f in R["facets"]] == ["verdict", "impact", "trl", "brl", "irl", "fit", "country", "sector", "age", "source", "deadline", "member"]
    irl = next(f for f in R["facets"] if f["param"] == "irl")
    assert {o["value"] for o in irl["options"]} == {"known", "none"}


def test_hrefs_toggle_one_value_and_keep_group_and_thesis():
    sel = {"verdict": ["INVEST"], "trl": ["4-6"]}
    extra = {"group": "fit", "thesis": "redstone_apelago_blue"}
    assert home_filter.href(sel, extra, ("verdict", "INVEST")) == "/?group=fit&thesis=redstone_apelago_blue&trl=4-6"
    assert home_filter.href(sel, extra, ("verdict", "WATCHLIST")).count("verdict=") == 2
    assert home_filter.href({}, {"group": "", "thesis": ""}) == "/"
    parsed = home_filter.parse({"verdict": "x" * 200, "bogus": "1"})
    assert parsed == {}


# ---- 3. the pages -------------------------------------------------------------------------------------------------------------------
def test_page_renders_without_filters_with_box_and_rail(client, H):
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert len(keys_in(html)) == len(H["rows"])
    assert html.count('class="hc-crit"') == len(H["rows"])
    assert 'id="hc-rail"' in html and "Clear all" not in html and f'>{len(H["rows"])} of {len(H["rows"])} startups</p>' in html
    for label in ("Verdict", "Ocean impact", "Technology readiness (TRL)", "Business readiness (BRL)", "Investment readiness (IRL)", "Thesis fit", "Country", "Impact category", "Registered", "Source records", "Programme deadline", "Declared company"):
        assert f"<span>{label}</span>" in html, label
    assert 'hx-replace-url="/?' in html and 'hx-get="/home/list' in html and "hx-push-url" not in html


def test_page_with_filters_shows_the_subset_and_can_be_cleared(client, H):
    expected = [r["company_key"] for r in H["rows"] if r["verdict"] == "ACCELERATOR" and r["country"] == "FI"]
    r = client.get("/?verdict=ACCELERATOR&country=FI")
    assert r.status_code == 200 and keys_in(r.text) == expected
    assert "Clear all" in r.text and f'>{len(expected)} of {len(H["rows"])} startups</p>' in r.text
    assert 'aria-checked="true"' in r.text
    # a group, a filter and the headline number: the headline counts the whole window, the list shrinks
    g = client.get("/?group=fit&for=any&verdict=ACCELERATOR")        # for=any: the plain Top matching list (the sponsor's ranking is tested in test_filters_inplace)
    fit_keys = {r["company_key"] for r in H["rows"] if r["verdict"] in home_list.TOP_VERDICTS or r["fit"] == "High"}
    assert set(keys_in(g.text)) == {k for k in fit_keys if next(x for x in H["rows"] if x["company_key"] == k)["verdict"] == "ACCELERATOR"}


def test_a_filter_that_matches_nothing_says_so_and_offers_the_way_back(client, H):
    r = client.get("/?verdict=INVEST&country=FI&trl=7-9&irl=none")
    assert r.status_code == 200
    if keys_in(r.text):
        pytest.skip("the snapshot has a company matching that combination")
    assert "No startup matches these filters" in r.text and 'class="hc-rows"' not in r.text
    assert client.get("/?verdict=%3Cscript%3E&country=ZZ").status_code == 200


def test_the_htmx_partial_returns_the_same_section_as_the_full_page(client):
    for q in ("", "?verdict=ACCELERATOR&trl=none", "?group=fit&country=FI"):
        full = client.get("/" + q)
        part = client.get("/home/list" + q, headers={"HX-Request": "true"})
        assert part.status_code == 200
        assert section(full.text) == section(part.text)
