"""Home list filters in place (D32): one state in the URL, the list section swapped alone, the address rewritten and never pushed, chips and
Clear all, an empty state, a count in a live region, and no control that loads a page. On the committed snapshot store (data/snapshot)."""
import html as htmllib
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import home_config, home_filter, home_list, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")


def _use_snapshot(mp):
    mp.setenv("RADAR_DATA_DIR", str(SNAP))
    mp.delenv("RADAR_DB", raising=False)
    mp.delenv("RADAR_THESIS", raising=False)
    mp.setenv("RADAR_NO_WARM", "1")


@pytest.fixture(autouse=True)
def _snapshot_env(monkeypatch):
    _use_snapshot(monkeypatch)


@pytest.fixture(scope="module")
def H():
    mp = pytest.MonkeyPatch()
    _use_snapshot(mp)
    try:
        yield home_list.for_template(thesis_mod.load(), wait=None)
    finally:
        mp.undo()


@pytest.fixture()
def client(H):
    import app
    return TestClient(app.app)


HX = {"HX-Request": "true"}


def list_section(html: str) -> str:
    start = html.index('<div id="hc-list"')
    end = html.index("</p>\n</div>", html.index('class="hc-note"', start)) + len("</p>\n</div>")
    return html[start:end]


def tags(html: str, name: str = "a") -> list[str]:
    return re.findall(rf"<{name}\b[^>]*>", html)


# ---- the fragment -------------------------------------------------------------------------------------------------------------------
def test_an_in_place_swap_returns_only_the_list_section_and_the_count(client):
    r = client.get("/home/list?verdict=ACCELERATOR&country=FI", headers=HX)
    assert r.status_code == 200
    t = r.text
    assert t.lstrip().startswith('<div id="hc-list"')
    for page_only in ("<html", "<head", "<body", '<section class="hc"', 'id="ask-form"', "<h1", 'class="top"', "c-tabbar"):
        assert page_only not in t, page_only
    # the count is a separate node, swapped out of band into the live region that stays on the page
    assert t.rstrip().endswith("</p>") and 'id="hc-count"' in t and 'hx-swap-oob="innerHTML"' in t
    assert r.headers["cache-control"] == "no-store"


def test_the_count_is_a_live_region_that_the_page_keeps(client, H):
    page = client.get("/").text
    m = re.search(r'<p id="hc-count"[^>]*>([^<]*)</p>', page)
    assert m and 'aria-live="polite"' in m.group(0) and 'role="status"' in m.group(0) and "hx-swap-oob" not in m.group(0)
    assert m.group(1) == f"{len(H['rows'])} of {len(H['rows'])} startups"
    # it sits outside the swapped section, so the live region survives every swap
    assert page.index('id="hc-count"') < page.index('<div id="hc-list"')
    n = sum(1 for r in H["rows"] if r["verdict"] == "ACCELERATOR")
    part = client.get("/home/list?verdict=ACCELERATOR", headers=HX).text
    assert re.search(r'<p id="hc-count"[^>]*hx-swap-oob="innerHTML">' + f"{n} of {len(H['rows'])} startups</p>", part)


def test_the_response_names_the_url_to_write_to_the_address_bar(client):
    r = client.get("/home/list?country=fi&src=prh&group=fit&verdict=ACCELERATOR", headers=HX)
    assert r.headers["hx-replace-url"] == "/?group=fit&verdict=ACCELERATOR&country=FI&source=prh"   # canonical: group first, filters in rail order, old names mapped
    assert "hx-push-url" not in r.text and "HX-Push-Url" not in r.headers


# ---- the state in the URL -----------------------------------------------------------------------------------------------------------
def test_the_url_state_round_trips():
    q = "group=new&for=apelago&thesis=redstone_apelago_blue&verdict=ACCELERATOR&verdict=WATCHLIST&trl=4-6&irl=none&country=FI&country=SE&age=lt1&source=prh&deadline=90&member=cohort&impact=High&fit=Medium&brl=1-3&sector=Aquaculture"
    st = home_filter.parse_state(_qp("/?" + q))
    assert st.group == "new" and st.org == "apelago" and st.thesis == "redstone_apelago_blue"
    assert st.sel["verdict"] == ["ACCELERATOR", "WATCHLIST"] and st.sel["country"] == ["FI", "SE"] and st.sel["sector"] == ["Aquaculture"]
    back = st.url
    # canonical order: group, investor, sector, then the filters in the rail's order
    assert back.startswith("/?group=new&for=apelago&thesis=redstone_apelago_blue&verdict=ACCELERATOR&verdict=WATCHLIST&impact=High&trl=4-6&brl=1-3&irl=none&fit=Medium&country=FI&country=SE&sector=Aquaculture")
    again = home_filter.parse_state(_qp(back))
    assert again == st and again.url == back
    assert st.partial == back.replace("/?", "/home/list?", 1)


def _qp(url: str):
    from starlette.datastructures import QueryParams
    return QueryParams(url.split("?", 1)[1] if "?" in url else "")


def test_old_links_still_mean_the_same_view():
    assert home_filter.parse_state(_qp("/?src=prh")).sel == {"source": ["prh"]}
    st = home_filter.parse_state(_qp("/?group=cc-dk&verdict=INVEST"))
    assert st.group == "" and st.sel == {"verdict": ["INVEST"], "country": ["DK"]}
    assert home_filter.parse_state(_qp("/?group=all")).group == ""
    assert home_filter.parse_state(_qp("/?verdict=" + "x" * 200)).sel == {}


def test_a_refresh_or_a_shared_url_renders_the_view_a_swap_produced(client):
    for q in ("verdict=ACCELERATOR&country=FI", "group=fit&trl=none", "group=new&brl=4-6&country=FI&country=DK", "src=prh&group=cc-FI"):
        page = client.get("/?" + q)
        part = client.get("/home/list?" + q, headers=HX)
        assert list_section(page.text) == list_section(part.text), q
        canonical = part.headers["hx-replace-url"]
        again = client.get(canonical)
        assert list_section(again.text) == list_section(page.text), q


# ---- chips, Clear all, the empty state ----------------------------------------------------------------------------------------------
def test_active_filters_are_removable_chips_with_clear_all(client, H):
    t = client.get("/home/list?group=fit&verdict=ACCELERATOR&country=FI", headers=HX).text
    chips = [tuple(htmllib.unescape(x) for x in c) for c in re.findall(r'<a class="hc-chip" id="([^"]+)" href="([^"]+)" hx-get="([^"]+)" hx-replace-url="([^"]+)" aria-label="([^"]+)"><span>([^<]+)</span>', t)]
    assert [c[5] for c in chips] == ["Verdict: Accelerator", "Country: Finland"]
    # each chip removes exactly its own value and keeps the rest of the state, group included
    assert chips[0][1] == "/?group=fit&country=FI" and chips[1][1] == "/?group=fit&verdict=ACCELERATOR"
    for _id, href, hx, rep, label, _t in chips:
        assert hx == href.replace("/?", "/home/list?", 1) and rep == href and label.startswith("Remove filter ")
    clear = re.search(r'<a class="hc-clearall" href="([^"]+)" hx-get="([^"]+)" hx-replace-url="([^"]+)">Clear all</a>', t)
    assert clear and clear.groups() == ("/?group=fit", "/home/list?group=fit", "/?group=fit")
    # nothing selected: no chips and no Clear all
    plain = client.get("/home/list", headers=HX).text
    assert 'class="hc-chip"' not in plain and 'class="hc-clearall"' not in plain and "hc-active" not in plain


def test_the_empty_state_says_so_and_offers_the_chips_to_remove(client, H):
    q = "verdict=INVEST&country=FI&trl=7-9&irl=none"
    if home_filter.apply(H["rows"], home_filter.parse(_qp("/?" + q))):
        pytest.skip("the snapshot has a company matching that combination")
    t = client.get("/home/list?" + q, headers=HX).text
    box = t[t.index('<div class="hc-empty"'):t.index('class="hc-note"')]
    assert "No startup matches these filters" in box and 'class="hc-rows"' not in t
    assert len(re.findall(r'class="hc-chip"', box)) == 4          # the chips live in the box, once (not also above it)
    assert t.count('class="hc-chip"') == 4 and 'class="hc-active"' not in t
    assert 'class="hc-clearall"' in box and ">0 of " in t


def test_a_group_with_no_rows_says_so_when_nothing_is_selected(client):
    t = client.get("/home/list?group=nosuchgroup", headers=HX).text
    assert 'class="hc-rows"' in t                                   # an unknown group falls back to the first tab


# ---- no control loads a page --------------------------------------------------------------------------------------------------------
def test_no_filter_control_is_a_full_page_link_without_htmx_attributes(client):
    for url in ("/", "/?verdict=ACCELERATOR&country=FI", "/?group=fit&country=DK&country=FI"):
        page = client.get(url).text
        sec = list_section(page)
        assert "hx-push-url" not in page
        for a in tags(sec):
            if re.search(r'href="/\?', a):
                assert 'hx-get="/home/list' in a and "hx-replace-url=" in a, a
        # the group tabs, the country links, the chips, Clear all and the rail's options are all such links
        for cls in ("hc-chip", "hc-cc", "hr-o", "hc-clearall"):
            for a in (x for x in tags(sec) if f'class="{cls}' in x):
                assert 'hx-get="/home/list' in a, a
        for a in (x for x in tags(sec) if 'data-key="' in x):
            assert 'hx-get="/home/list' in a and "hx-replace-url=" in a, a
        assert not re.search(r'href="/\?group=[^"]*"(?![^>]*hx-get)', sec)


def test_the_page_scripts_do_not_navigate_for_a_filter():
    ask = (ROOT / "radar" / "static" / "askbar.js").read_text()
    assert "Filters.apply" in ask and "preventDefault" in ask
    head = (ROOT / "radar" / "templates" / "_skin_head.html").read_text()
    assert "location.href = g.href" not in head and "g.click()" in head
    js = (ROOT / "radar" / "static" / "filters.js").read_text()
    assert "replaceState" in js and "pushState" not in js and "htmx.ajax" in js and "location.assign(page)" in js


def test_the_browser_module_mirrors_the_servers_parameters(client):
    t = client.get("/").text
    m = re.search(r'data-params="([^"]+)"', t)
    assert m and m.group(1).split(",") == list(home_filter.params())
    assert "/static/filters.js" in t and "/static/filters.css" in t
    assert client.get("/static/filters.js").status_code == 200


# ---- the hook for a later taxonomy --------------------------------------------------------------------------------------------------
def test_a_facet_listed_in_the_config_is_offered_without_touching_the_code(tmp_path, monkeypatch):
    src = (ROOT / "config" / "home_filters.yaml").read_text()
    cfg = tmp_path / "home_filters.yaml"
    cfg.write_text(src.replace("  - {param: age,", "  - {param: subsector, heading: Subsector, section: more, open: true}\n  - {param: age,"), encoding="utf-8")
    monkeypatch.setattr(home_config, "PATH", cfg)
    assert "subsector" in home_filter.params()
    rows = [{"company_key": "a", "facets": {"subsector": ["Kelp farming"], "verdict": ["INVEST"]}},
            {"company_key": "b", "facets": {"subsector": ["Port robotics"], "verdict": ["INVEST"]}}]
    R = home_filter.rail(rows, {"subsector": ["Port robotics"]}, {})
    f = next(f for f in R["facets"] if f["param"] == "subsector")
    assert [(o["value"], o["on"], o["count"]) for o in f["options"]] == [("Kelp farming", False, 1), ("Port robotics", True, 1)] and R["shown"] == 1
    assert home_filter.parse(_qp("/?subsector=Port+robotics")) == {"subsector": ["Port robotics"]}
    assert home_filter.href({"subsector": ["Kelp farming"]}, {}) == "/?subsector=Kelp+farming"


def test_the_country_name_table_is_complete_and_iso():
    names = home_config.country_names()
    assert len(names) == 249 and all(isinstance(k, str) and re.fullmatch(r"[A-Z]{2}", k) for k in names)
    assert names["NO"] == "Norway" and home_config.country_name("FI") == "Finland" and home_config.country_name("ZZ") == "ZZ"   # NO must not read as a YAML false
