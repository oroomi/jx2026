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
    assert 'id="hc-count"' in t and t.count('hx-swap-oob="innerHTML"') == 2          # the result count and the Ask bar's count line
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
    chips = [tuple(htmllib.unescape(x) for x in c) for c in re.findall(r'<a class="hc-chip" id="([^"]+)" href="([^"]+)" hx-get="([^"]+)" hx-replace-url="([^"]+)" aria-label="([^"]+)"><span>(?:<img[^>]*>)?([^<]+)</span>', t)]
    assert [c[5] for c in chips] == ["Verdict: Accelerator", "Country: Finland"]
    # each chip removes exactly its own value and keeps the rest of the state, group included
    assert chips[0][1] == "/?group=fit&country=FI" and chips[1][1] == "/?group=fit&verdict=ACCELERATOR"
    for _id, href, hx, rep, label, _t in chips:
        assert hx == href.replace("/?", "/home/list?", 1) and rep == href and label.startswith("Remove filter ")
    clear = re.search(r'<a class="hc-clearall" href="([^"]+)" hx-get="([^"]+)" hx-replace-url="([^"]+)">Clear all</a>', t)
    assert clear and clear.groups() == ("/?group=fit", "/home/list?group=fit", "/?group=fit")
    # nothing selected: no chips and no Clear all
    plain = client.get("/home/list", headers=HX).text
    assert '<a class="hc-chip"' not in plain and 'class="hc-clearall"' not in plain      # only the sector's default chip, which is not a control


def test_the_empty_state_says_so_and_offers_the_chips_to_remove(client, H):
    q = "verdict=INVEST&country=FI&trl=7-9&irl=none"
    if home_filter.apply(H["rows"], home_filter.parse(_qp("/?" + q))):
        pytest.skip("the snapshot has a company matching that combination")
    t = client.get("/home/list?" + q, headers=HX).text
    box = t[t.index('<div class="hc-empty"'):t.index('class="hc-note"')]
    assert "No startup matches these filters" in box and 'class="hc-rows"' not in t
    assert len(re.findall(r'<a class="hc-chip"', box)) == 4          # the chips live in the box, once (not also above it)
    assert t.count('<a class="hc-chip"') == 4 and 'class="hc-clearall"' in box and t.count('class="hc-clearall"') == 1
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


# ---- the hook for a facet listed in the config only (the real taxonomy facet, `subsector`, is tested in tests/test_sectors.py) --------------------------------------------------------------------------------------------------
def test_a_facet_listed_in_the_config_is_offered_without_touching_the_code(tmp_path, monkeypatch):
    src = (ROOT / "config" / "home_filters.yaml").read_text()
    cfg = tmp_path / "home_filters.yaml"
    cfg.write_text(src.replace("  - {param: age,", "  - {param: focus, heading: Focus, section: more, open: true}\n  - {param: age,"), encoding="utf-8")
    monkeypatch.setattr(home_config, "PATH", cfg)
    assert "focus" in home_filter.params()
    rows = [{"company_key": "a", "facets": {"focus": ["Kelp farming"], "verdict": ["INVEST"]}},
            {"company_key": "b", "facets": {"focus": ["Port robotics"], "verdict": ["INVEST"]}}]
    R = home_filter.rail(rows, {"focus": ["Port robotics"]}, {})
    f = next(f for f in R["facets"] if f["param"] == "focus")
    assert [(o["value"], o["on"], o["count"]) for o in f["options"]] == [("Kelp farming", False, 1), ("Port robotics", True, 1)] and R["shown"] == 1
    assert home_filter.parse(_qp("/?focus=Port+robotics")) == {"focus": ["Port robotics"]}
    assert home_filter.href({"focus": ["Kelp farming"]}, {}) == "/?focus=Kelp+farming"


def test_the_country_name_table_is_complete_and_iso():
    names = home_config.country_names()
    assert len(names) == 249 and all(isinstance(k, str) and re.fullmatch(r"[A-Z]{2}", k) for k in names)
    assert names["NO"] == "Norway" and home_config.country_name("FI") == "Finland" and home_config.country_name("ZZ") == "ZZ"   # NO must not read as a YAML false


# ---- Step 2: the sector is a filter group, the header block is gone ------------------------------------------------------------------------
HEALTH = "health_tech_turku"
BLUE = "redstone_apelago_blue"


@pytest.fixture(scope="module")
def H_health():
    mp = pytest.MonkeyPatch()
    _use_snapshot(mp)
    try:
        yield home_list.for_template(thesis_mod.load(thesis_mod.available()[HEALTH]), wait=None)
    finally:
        mp.undo()


def test_the_header_sector_block_is_gone_from_the_layout():
    base = (ROOT / "radar" / "templates" / "base.html").read_text()
    for gone in ("thesis-bar", "thesis-switch", "thesis-select", "Change sector or region", "thesis_options", 'class="sector"'):
        assert gone not in base, gone
    css = "".join((ROOT / "radar" / "static" / f).read_text() for f in ("app.css", "site.css", "home_c.css", "askbar.css"))
    assert "thesis-bar" not in css and "thesis-switch" not in css and ".sector>summary" not in css


def test_the_sector_group_lists_the_configured_theses_with_the_current_one_as_a_default_chip(client, H, H_health):
    t = client.get("/").text
    group = t[t.index('data-f="thesis"'):]
    group = group[:group.index("</details>")]
    ids = re.findall(r'<a id="f-thesis-([^"]+)"', group)
    assert ids == [i.replace("_", "-") for i in thesis_mod.available()]
    assert group.count('aria-checked="true"') == 1 and 'role="radiogroup"' in group
    assert "<span>Sector</span>" in t[t.index('data-f="thesis"'):][:400]
    # the current sector is the default chip: its title without the bracket, no cross, not a link
    assert '<span class="hc-chip hc-chip-default"' in t and "<span>Blue economy, Finland and Nordics</span>" in t
    assert home_filter.short_title("Blue economy, Finland and Nordics (Redstone Blue x A'Pelago)") == "Blue economy, Finland and Nordics"
    # a sector that has a list shows how many startups it holds
    assert f'{len(H_health["rows"])}</span></a></li>' in group


def test_choosing_another_sector_swaps_the_list_in_place_for_that_thesis(client, H, H_health):
    r = client.get(f"/home/list?thesis={HEALTH}", headers=HX)
    assert r.status_code == 200 and r.text.lstrip().startswith('<div id="hc-list"')
    assert f'data-thesis="{HEALTH}"' in r.text and f">{len(H_health['rows'])} of {len(H_health['rows'])} startups</p>" in r.text
    assert r.headers["hx-replace-url"] == f"/?thesis={HEALTH}"            # the address follows, replaced and not pushed
    assert f"radar_thesis={HEALTH}" in r.headers["set-cookie"]               # the other pages follow the sector chosen
    assert 'id="ask-count-text" hx-swap-oob="innerHTML"' in r.text         # the Ask bar's count belongs to the sector in view
    assert f'<span class="hc-chip hc-chip-default"' in r.text
    # the whole page for the same address renders the same list (a refresh, a shared link, an old /?thesis= link)
    page = client.get(f"/?thesis={HEALTH}")
    assert list_section(page.text) == list_section(r.text)
    # and the default sector again
    back = client.get(f"/home/list?thesis={BLUE}", headers=HX)
    assert f'data-thesis="{BLUE}"' in back.text and back.headers["hx-replace-url"] == f"/?thesis={BLUE}"


def test_a_sector_switch_keeps_only_the_filters_the_new_sector_offers():
    st = home_filter.parse_state(_qp("/?group=ready&verdict=INVEST&verdict=WATCHLIST&country=FI&trl=7-9"))
    sectors = [{"id": "a", "title": "Alpha (note)", "rows": 5, "offered": {"verdict": {"INVEST"}, "country": {"FI"}}, "groups": ["all", "ready"]},
               {"id": "b", "title": "Beta", "rows": 3, "offered": {"verdict": {"WATCHLIST"}, "country": {"SE"}, "trl": {"7-9"}}, "groups": ["all", "new"]},
               {"id": "c", "title": "Gamma", "rows": None, "offered": None, "groups": None}]
    o = {x["value"]: x for x in home_filter.sector_options(st, sectors, "a")}
    assert o["a"]["on"] and o["a"]["href"] == "/?group=ready&thesis=a&verdict=INVEST&verdict=WATCHLIST&trl=7-9&country=FI"     # the current sector keeps its state
    assert o["b"]["href"] == "/?thesis=b&verdict=WATCHLIST&trl=7-9"        # INVEST, FI and the group "ready" are not offered there
    assert o["b"]["hx"] == "/home/list?thesis=b&verdict=WATCHLIST&trl=7-9"
    assert o["c"]["href"] == "/?thesis=c"                                    # its list is not known yet: nothing is carried
    assert [x["label"] for x in o.values()] == ["Alpha", "Beta", "Gamma"] and o["a"]["count"] == 5 and o["c"]["count"] is None


def test_the_rail_links_to_the_other_sectors_with_only_what_they_offer(client, H, H_health):
    have = home_filter.offered(H_health["rows"])
    st_vals = {v for r in H["rows"] for v in r["facets"]["verdict"]}
    missing = sorted(v for v in st_vals if v not in have.get("verdict", set()))
    common = sorted(have.get("country", set()) & {v for r in H["rows"] for v in r["facets"]["country"]})
    if not missing or not common:
        pytest.skip("the snapshot sectors do not differ in verdicts or share no country")
    q = f"verdict={missing[0].replace(' ', '+')}&country={common[0]}"
    t = client.get("/?" + q).text
    href = htmllib.unescape(re.search(rf'<a id="f-thesis-{HEALTH.replace("_", "-")}" class="[^"]*" href="([^"]+)"', t).group(1))
    assert f"thesis={HEALTH}" in href and f"country={common[0]}" in href and "verdict=" not in href


def test_the_sector_group_is_a_link_with_htmx_so_nothing_loads_a_page(client):
    t = client.get("/").text
    for a in tags(t[t.index('role="radiogroup"'):t.index("</details>", t.index('role="radiogroup"'))]):
        if a.startswith("<a "):
            assert 'hx-get="/home/list?' in a and 'hx-replace-url="/?' in a and 'role="radio"' in a, a
    assert 'id="hc-stale"' in t and 'id="all-records" data-thesis="' in t        # the records below name the sector they belong to


def test_other_pages_still_work_with_the_default_sector(client):
    for url in ("/radar", "/backtest", "/method", "/data", "/search?q=zzz", "/c/does-not-exist"):
        assert client.get(url).status_code in (200, 404), url
    assert client.get("/").status_code == 200 and client.get(f"/?thesis={BLUE}").status_code == 200


# ---- Step 4: the country filter -----------------------------------------------------------------------------------------------------
def test_country_values_are_iso_alpha_2_and_names_come_from_the_config(H):
    codes = {v for r in H["rows"] for v in r["facets"]["country"]}
    assert codes and all(re.fullmatch(r"[A-Z]{2}", c) or c == "none" for c in codes)
    R = home_filter.rail(H["rows"], {}, {})
    country = next(f for f in R["facets"] if f["param"] == "country")
    names = home_config.country_names()
    for o in country["options"]:
        assert o["label"] == (names[o["value"]] if o["value"] != "none" else "Not stated")
    assert "Finland" in [o["label"] for o in country["options"]] and "FI" not in [o["label"] for o in country["options"]]


def test_country_options_come_only_from_the_countries_in_the_current_list(H):
    for key in ("all", "fit", "new"):
        rows = next((rs for k, _l, rs in H["groups"] if k == key), None)
        if not rows:
            continue
        R = home_filter.rail(rows, {}, {})
        offered = {o["value"] for f in R["facets"] if f["param"] == "country" for o in f["options"]}
        assert offered == {v for r in rows for v in r["facets"]["country"]}, key
    # a selected country that this list has no row for stays visible (with 0), so it can be switched off
    R = home_filter.rail(H["rows"], {"country": ["ZZ"]}, {})
    country = next(f for f in R["facets"] if f["param"] == "country")
    assert [(o["value"], o["on"], o["count"]) for o in country["options"] if o["value"] == "ZZ"] == [("ZZ", True, 0)]


def test_several_countries_are_alternatives_and_other_filters_all_have_to_hold(client, H):
    rows = H["rows"]
    two = [c for c, _n in __import__("collections").Counter(r["country"] for r in rows).most_common(2)]
    assert len(two) == 2
    either = [r["company_key"] for r in rows if r["country"] in two]                                    # OR inside the country filter
    q = "&".join(f"country={c}" for c in two)
    page = client.get("/?" + q).text
    assert sorted(re.findall(r'class="hc-row" href="/c/([^"]+)"', page)) == sorted(either)
    both = [r["company_key"] for r in rows if r["country"] in two and r["verdict"] == "WATCHLIST"]       # AND across filters
    page = client.get("/?" + q + "&verdict=WATCHLIST").text
    assert sorted(re.findall(r'class="hc-row" href="/c/([^"]+)"', page)) == sorted(both)
    assert len(both) < len(either)
    # the count line says so, and one chip per country is offered for removal
    n = len(both)
    part = client.get("/home/list?" + q + "&verdict=WATCHLIST", headers=HX).text
    assert f"{n} of {len(rows)} startups</p>" in part
    assert [htmllib.unescape(c) for c in re.findall(r'<span>(?:<img[^>]*>)?(Country: [^<]+)</span>', part)] == [f"Country: {home_config.country_name(c)}" for c in two]


def test_a_country_link_adds_or_removes_one_country_and_keeps_the_rest(client, H):
    t = client.get("/home/list?country=FI&verdict=WATCHLIST", headers=HX).text
    nav = t[t.index('<nav class="hc-countries"'):t.index("</nav>", t.index('<nav class="hc-countries"'))]
    links = {htmllib.unescape(m.group(1)): htmllib.unescape(m.group(2)) for m in re.finditer(r'<a class="hc-cc[^"]*" href="([^"]+)" [^>]*?aria-checked="[^"]+">(?:<img[^>]*>)?([^<]+)</a>', nav)}
    by_name = {name: href for href, name in links.items()}
    assert by_name["Finland"] == "/?verdict=WATCHLIST"                                    # on: following it switches Finland off
    other = next(n for n in by_name if n not in ("Finland", "Not stated"))
    assert by_name[other].startswith("/?verdict=WATCHLIST&country=FI&country=")           # off: following it adds a second country
    assert nav.count('aria-checked="true"') == 1


def test_a_flag_is_shown_beside_a_country_only_when_its_file_is_vendored(client, H, monkeypatch):
    t = client.get("/?country=FI").text
    sec = list_section(t)
    assert '<img class="hc-flag" src="/static/vendor/flags/fi.svg" width="16" height="12" alt="" loading="lazy">' in sec
    assert sec.count("/static/vendor/flags/fi.svg") >= 3        # the rail option, the country link and the chip
    folder = ROOT / "radar" / "static" / "vendor" / "flags"
    present = {r["country"] for r in H["rows"] if r["country"]}
    assert {c.lower() + ".svg" for c in present} <= {p.name for p in folder.glob("*.svg")}
    for svg in folder.glob("*.svg"):
        assert svg.read_text().lstrip().startswith("<svg") and client.get(f"/static/vendor/flags/{svg.name}").status_code == 200
    readme = (folder / "README.md").read_text()
    assert "MIT" in readme and "flag-icons" in readme and "MIT License" in (folder / "LICENSE").read_text()
    monkeypatch.setattr(home_config, "flag_codes", lambda: frozenset({"DK"}))
    sec = list_section(client.get("/?country=FI&country=DK").text)
    assert "/static/vendor/flags/dk.svg" in sec and "/static/vendor/flags/fi.svg" not in sec        # no file: the name alone
    assert home_config.flag_url("FI") is None and home_config.flag_url("none") is None


def test_no_country_name_is_written_in_the_python_that_builds_the_filter():
    names = set(home_config.country_names().values())
    for rel in ("radar/home_filter.py", "radar/home_config.py", "radar/home_list.py", "radar/routes/home_rail.py", "radar/routes/feed.py", "radar/ask.py"):
        src = (ROOT / rel).read_text()
        code = re.sub(r'""".*?"""|#.*', " ", src, flags=re.S)
        for n in names:
            assert not re.search(rf"\b{re.escape(n)}\b", code), (rel, n)


# ---- Step 5: Top matching startups for an investor or accelerator ---------------------------------------------------------------------
from radar import home_orgs, matchmaker  # noqa: E402


@pytest.fixture(scope="module")
def ranked(H):
    """The matchmaker's own order for the sponsor, and what it lists of the home list (read straight from the matchmaker, not through the page)."""
    mp = pytest.MonkeyPatch()
    _use_snapshot(mp)
    try:
        th = thesis_mod.load()
        orgs = home_orgs.organisations(th)
        if not any(o["id"] == "apelago" for o in orgs):
            pytest.skip("the matchmaker does not know the sponsor in this checkout")
        res = matchmaker.match_org("apelago", th, limit=10 ** 6)
        keys = {r["company_key"] for r in H["rows"]}
        yield {"orgs": orgs, "order": [s["key"] for s in res["startups"] if s["key"] in keys], "rows": {s["key"]: s for s in res["startups"]}}
    finally:
        mp.undo()


def tab(html: str, key: str = "2") -> str:
    return htmllib.unescape(re.search(rf'<a [^>]*data-key="{key}"[^>]*><kbd[^>]*>{key}</kbd>(.*?) <span>(\d+)</span></a>', html).group(1))


def row_keys(html: str) -> list[str]:
    return re.findall(r'class="hc-row" href="/c/([^"]+)"', html)


def test_the_tab_is_named_for_the_sponsor_by_default(client, ranked):
    t = client.get("/").text
    assert tab(t) == "Top matching startups for A'Pelago"
    assert "Top fits" not in t
    n = re.search(r'data-key="2"[^>]*>.*?<span>(\d+)</span>', t).group(1)
    assert int(n) == len(ranked["order"])


def test_the_tab_lists_the_matchmakers_ranking_for_that_organisation_intersected_with_the_home_list(client, ranked):
    t = client.get("/?group=fit").text
    assert row_keys(t) == ranked["order"]                    # the matchmaker's order, nothing re-ranked
    assert 'data-key="2" aria-current="true"' in t
    # other filters apply on top, in the same order
    q = client.get("/home/list?group=fit&verdict=WATCHLIST", headers=HX).text
    from radar import home_list as hl
    rows = {r["company_key"]: r for r in hl.for_template(thesis_mod.load(), wait=None)["rows"]}
    assert row_keys(q) == [k for k in ranked["order"] if rows[k]["verdict"] == "WATCHLIST"] and row_keys(q)


def test_each_row_shows_its_top_two_reasons_in_words(client, ranked):
    t = client.get("/?group=fit").text
    items = [(re.search(r'href="/c/([^"]+)"', li).group(1), li) for li in section_of(t).split("</li>") if 'class="hc-row"' in li]
    assert items
    seen = 0
    for key, li in items:
        chips = [htmllib.unescape(c) for c in re.findall(r'<span class="hc-whyc">([^<]*)</span>', li)]
        assert 1 <= len(chips) <= 2, (key, chips)
        comps = [c for c in ranked["rows"][key]["components"] if c["met"] and c.get("chip")]
        assert chips[0] == (comps[0]["chip"] if comps[0]["id"] == "member" else sorted(comps, key=lambda c: -int(c["weight"]))[0]["chip"])
        assert not re.search(r"\bCovers [A-Z]{2}\b", " ".join(chips))          # a country is named, not coded
        seen += 1
    assert seen == len(ranked["order"])


def section_of(html: str) -> str:
    start = html.index('class="hc-rows"')
    return html[start:html.index('class="hc-note"', start)]


def test_top_reasons_keep_the_matchmakers_words_and_name_countries():
    comps = [{"id": "geography", "met": True, "weight": 1, "chip": "Covers FI, SE"}, {"id": "readiness", "met": True, "weight": 2, "chip": "Stage pre-seed fits"},
             {"id": "sector", "met": True, "weight": 3, "chip": "Sector: ocean data and sensing"}, {"id": "timing", "met": False, "weight": 1, "chip": "Deadline in 30 days"},
             {"id": "member", "met": True, "weight": 0, "chip": "In its declared cohort or portfolio"}]
    assert home_orgs.top_reasons(comps, 2) == ["In its declared cohort or portfolio", "Sector: ocean data and sensing"]
    assert home_orgs.top_reasons(comps[:3], 2) == ["Sector: ocean data and sensing", "Stage pre-seed fits"]
    assert home_orgs.top_reasons(comps[:1], 2) == ["Covers Finland, Sweden"]
    assert home_orgs.top_reasons([], 2) == []


def test_the_picker_lists_the_investors_and_accelerators_the_matchmaker_knows(client, ranked):
    t = client.get("/?group=fit").text
    form = t[t.index('<form class="hc-for"'):t.index("</form>", t.index('<form class="hc-for"'))]
    th = thesis_mod.load()
    known = {o["id"] for o in matchmaker.org_list(th) if o["kind"] in ("investor", "accelerator")}
    listed = set(re.findall(r'<option value="([^"]+)"', form)) - {"any"}
    assert listed == known and len(listed) > 10
    assert re.search(r'<option value="apelago" selected>', form) and 'hx-get="/home/list"' in form and 'hx-trigger="change"' in form
    assert '<optgroup label="Investor">' in form and '<optgroup label="Accelerator or incubator">' in form
    assert form.index('label="Investor"') < form.index('label="Accelerator or incubator"')
    # without scripts the same form is a plain GET of the page, carrying the tab
    assert 'action="/" method="get"' in form and '<input type="hidden" name="group" value="fit">' in form and "<noscript>" in form
    assert "hx-push-url" not in form
    # the picker belongs to the Top matching tab
    assert 'class="hc-for"' not in client.get("/").text


def test_picking_another_organisation_changes_the_tab_and_the_rows(client, ranked):
    t = client.get("/home/list?group=fit&for=redstone-blue", headers=HX)
    assert tab(t.text) == "Top matching startups for Redstone Blue" and t.headers["hx-replace-url"] == "/?group=fit&for=redstone-blue"
    th = thesis_mod.load()
    mine = [s["key"] for s in matchmaker.match_org("redstone-blue", th, limit=10 ** 6)["startups"]]
    assert row_keys(t.text) == [k for k in mine if k in {r["company_key"] for r in home_list.for_template(th, wait=None)["rows"]}]
    assert '<option value="redstone-blue" selected>' in t.text
    # the other links of the page keep the choice
    assert 'href="/?for=redstone-blue"' in t.text or "for=redstone-blue" in re.search(r'<a href="([^"]+)"[^>]*data-key="1"', t.text).group(1)


def test_without_an_organisation_the_tab_is_plain_top_matching(client, H, monkeypatch):
    any_ = client.get("/home/list?group=fit&for=any", headers=HX).text
    assert tab(any_) == "Top matching startups" and 'class="hc-whyc"' not in any_
    expected = [r["company_key"] for r in H["rows"] if r["verdict"] in home_list.TOP_VERDICTS or r["fit"] == "High"]
    assert row_keys(any_) == expected                                       # the old Top fits rows: no scoring changed
    # an organisation the matchmaker does not know falls back to the sponsor, not to an error
    assert tab(client.get("/home/list?group=fit&for=nobody", headers=HX).text) == "Top matching startups for A'Pelago"
    # no sponsor among the organisations: the plain label, and no picker
    monkeypatch.setattr(home_orgs, "default_org", lambda orgs: None)
    none = client.get("/home/list?group=fit", headers=HX).text
    assert tab(none) == "Top matching startups" and row_keys(none) == expected
    # a sector whose thesis has no matchmaking has no picker at all
    monkeypatch.setattr(home_orgs, "organisations", lambda th: [])
    bare = client.get("/home/list?group=fit", headers=HX).text
    assert tab(bare) == "Top matching startups" and 'class="hc-for"' not in bare and row_keys(bare) == expected


def test_a_still_pending_ranking_falls_back_to_the_plain_list_with_a_note(client, H, monkeypatch):
    monkeypatch.setattr(home_orgs, "ranking", lambda th, org, wait=None: None)
    t = client.get("/home/list?group=fit", headers=HX).text
    assert tab(t) == "Top matching startups" and "is still being prepared; this is the plain Top matching list" in t


def test_an_organisation_with_no_startup_on_the_list_says_so(client, ranked):
    th = thesis_mod.load()
    keys = {r["company_key"] for r in home_list.for_template(th, wait=None)["rows"]}
    empty = next((o for o in ranked["orgs"] if o["id"] != "apelago" and not {s["key"] for s in (matchmaker.match_org(o["id"], th, limit=10 ** 6) or {"startups": []})["startups"]} & keys), None)
    if empty is None:
        pytest.skip("every organisation lists a startup of this list")
    t = client.get(f"/home/list?group=fit&for={empty['id']}", headers=HX).text
    assert f"No startup on this list is matched to {htmllib.escape(empty['name'], quote=True)}" in t and "hc-rows" not in t.replace("hc-rows-", "")
