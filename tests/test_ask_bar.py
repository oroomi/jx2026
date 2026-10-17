"""Ask Aava bar: GET /api/ask answers (deterministic, vocabulary from the thesis file), the home hero (no 'companies surfaced', the bar and
its one-line count), and the header Menu with the old tab-row links kept in the menu and the footer. Data: a copy of data/snapshot."""
import re
import shutil
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from radar import ask, home_list, thesis

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
VIVA = "2962040-6"
OLD_NAV = ("/", "/radar", "/method", "/data")
OFF_MENU = ("/backtest",)                # D81: the earliness test still answers, but is not in the menu, the footer or the tab bar


@pytest.fixture()
def client(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    import app
    return TestClient(app.app)


def _ask(client, q: str) -> dict:
    r = client.get("/api/ask", params={"q": q})
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("intent", "say", "url", "action"):
        assert k in d
    return d


# ---- intents ----------------------------------------------------------------------------------------------------------------------------
def test_company_name_gets_aavas_first_answer_and_the_memo_link(client):
    d = _ask(client, "Viva Jets")
    assert d["intent"] == "company" and d["action"] == "open"
    assert d["url"] == f"/c/{VIVA}?demo=1" and d["label"] == "Open the full memo"
    assert d["say"].startswith("Based on what the radar holds on Viva Jets Oy, I think ")
    seg = d["segments"][0]
    assert seg["text"] == d["say"] and len(seg["sha"]) == 16 and d["audio_dir"] == VIVA
    # the same answer the company page's Aava question 1 embeds
    from radar import aava
    assert seg["sha"] == aava.text_sha(seg["text"])


def test_lead_ins_ids_and_spelling_variants_reach_the_same_company(client):
    for q in ("Tell me about Viva Jets", "viva jets oy", "VIVA JETS?", VIVA, "Viva Jet", "viva  jets"):
        d = _ask(client, q)
        assert d["intent"] == "company" and d["url"] == f"/c/{VIVA}?demo=1", q


def test_what_is_new_is_the_feed_answer(client):
    for q in ("what is new", "What is new on the radar?", "latest", "anything new"):
        d = _ask(client, q)
        assert d["intent"] == "feed", q
        assert d["audio_dir"] == "feed" and d["segments"] and d["say"] == " ".join(s["text"] for s in d["segments"])
        assert all(i["url"].startswith("/c/") for i in d["items"])


def test_the_high_thesis_fit_example_chip_sets_the_fit_filter(client):
    """Judge-fix: the home chip "Show high thesis fit companies in Finland" must read "high thesis fit" as the fit filter, not drop the words."""
    d = _ask(client, "Show high thesis fit companies in Finland")
    assert d["intent"] == "filter" and d["filters"] == {"fit": ["High"], "country": ["FI"]}
    assert "did not use" not in d["say"]
    d = _ask(client, "portfolio support companies")
    assert d["filters"] == {"verdict": ["PORTFOLIO SUPPORT"]}


def test_verdict_and_country_words_become_the_filter_rail_querystring_with_a_count(client):
    d = _ask(client, "watchlist companies in Finland")   # D65: no company reads ACCELERATOR in the snapshot now
    assert d["intent"] == "filter" and d["action"] == "filter"
    assert d["url"] == "/?verdict=WATCHLIST&country=FI"
    assert d["filters"] == {"verdict": ["WATCHLIST"], "country": ["FI"]}
    assert isinstance(d["count"], int) and 1 <= d["count"] <= d["total"]
    assert d["say"].startswith(f"{d['count']} of {d['total']} companies on the list match: on the watchlist, in Finland.")
    assert len(d["items"]) == min(d["count"], ask.LIST_ITEMS)
    # the count is the cached home list's own count
    rows = home_list.for_template(thesis.load())["rows"]
    assert d["total"] == len(rows) and d["count"] == sum(1 for r in rows if r["verdict"] == "WATCHLIST" and r["country"] == "FI")


def test_a_sector_word_names_the_rail_sector(client):
    d = _ask(client, "aquaculture")
    assert d["intent"] == "filter" and d["url"] == "/?sector=Aquatech" and d["filters"] == {"sector": ["Aquatech"]}
    assert d["say"].endswith("match: in the aquatech sector.") or "aquatech sector" in d["say"]


def test_trl_above_n_names_the_bands_that_reach_above_n(client):
    d = _ask(client, "Aquaculture startups with a TRL above 4")
    assert d["intent"] == "filter" and d["filters"] == {"sector": ["Aquatech"], "trl": ["4-6", "7-9"]}
    assert d["url"] == "/?sector=Aquatech&trl=4-6&trl=7-9"
    assert "TRL above 4 (bands 4 to 6 and 7 to 9)" in d["say"]
    assert _ask(client, "BRL below 3")["filters"] == {"brl": ["1-3"]}
    assert _ask(client, "TRL 5")["filters"] == {"trl": ["4-6"]}


def test_investment_ready_uses_the_investor_ready_group_not_a_verdict(client):
    d = _ask(client, "Show investment-ready companies in Finland")
    assert d["intent"] == "filter" and d["filters"] == {"group": ["ready"], "country": ["FI"]}
    assert d["url"] == "/?group=ready&country=FI"


def test_who_should_an_organisation_meet_is_the_match_intent(client):
    for q in ("Who should A'Pelago meet", "who should a pelago meet?", "match A'Pelago", "A'Pelago"):
        d = _ask(client, q)
        assert d["intent"] == "match" and d["org"]["name"] == "A'Pelago", q
        assert "accelerator" in d["say"]
    d = _ask(client, "Redstone Blue")
    assert d["intent"] == "match" and "venture capital" in d["say"]
    # a link only when the /match page is in this build (a link to a missing page would be worse than none); the merged branch selects by id
    if client.get("/match").status_code == 200:
        assert d["url"].startswith("/match?org=") and d["action"] == "open" and client.get(d["url"]).status_code == 200
    else:
        assert d["url"] is None and d["action"] == "none"


def test_who_should_a_company_meet_is_aavas_question_four(client):
    d = _ask(client, "Who should Viva Jets meet")
    assert d["intent"] == "company" and d["url"] == f"/c/{VIVA}?demo=1"
    q4 = [s for s in client.get(f"/aava/script/{VIVA}", params={"intent": "meet"}).json()["segments"] if s.get("q") == 4][0]
    assert d["say"] == q4["text"] and d["segments"][0]["sha"] == q4["sha"]
    assert not d["say"].startswith("Based on what the radar holds on")


def test_an_unknown_word_says_nothing_matches_and_links_nowhere(client):
    d = _ask(client, "zebra pancakes")
    assert d["intent"] == "nothing" and d["action"] == "none" and d["url"] is None
    assert d["say"] == "Nothing on the radar matches zebra pancakes. Try a company name, a country, or a sector."   # D40


def test_an_ambiguous_part_of_a_name_lists_candidates_instead_of_guessing(client):
    d = _ask(client, "water")
    assert d["intent"] == "search" and d["items"] and all(i["url"].startswith("/c/") for i in d["items"])


def test_empty_and_one_letter_questions_get_help_not_an_error(client):
    for q in ("", " ", "a", "?!"):
        d = _ask(client, q)
        assert d["intent"] == "help" and d["url"] is None


def test_partner_organisations_are_not_companies_to_ask_about(client):
    th = thesis.load()
    from radar import store
    conn = store.open_db(thesis=th)
    try:
        kind, hit = ask.find_company(conn, th, "A'Pelago Experience")
    finally:
        conn.close()
    assert kind == "none" or (hit and "pelago" not in str(hit).casefold())


def test_a_thesis_without_its_own_ask_block_inherits_the_words_but_not_the_blue_sectors():
    blue = thesis.load("config/thesis.yaml")
    health = thesis.load("config/thesis_health_turku.yaml")
    assert ask.config(blue)["sectors"] and ask.config(health)["sectors"] == {}
    assert ask.config(health)["filters"] == ask.config(blue)["filters"] and ask.examples(health) != ask.examples(blue)


# ---- the vocabulary is data ---------------------------------------------------------------------------------------------------------
def test_every_example_question_is_answerable(client):
    for th_path in ("config/thesis.yaml",):
        for q in ask.examples(thesis.load(th_path)):
            assert _ask(client, q)["intent"] not in ("help",), q


def test_no_sector_verdict_or_country_word_in_the_python(client):
    src = (ROOT / "radar" / "ask.py").read_text() + (ROOT / "radar" / "routes" / "ask.py").read_text()
    code = re.sub(r'""".*?"""|#.*', " ", src, flags=re.S)
    for word in ("aquacult", "aquatech", "accelerator", "watchlist", "due diligence", "finland", "sweden", "emission", "wastewater", "hydrogen"):
        assert word not in code.casefold(), word


def test_sector_values_are_the_framework_categories_the_rail_filters_on():
    cats = {c.capitalize() for c in yaml.safe_load((ROOT / "config" / "frameworks.yaml").read_text())["impact_categories"]}
    assert set(ask.config(thesis.load())["sectors"]) <= cats


def test_filter_words_use_only_rail_parameters():
    allowed = set(ask.FILTER_PARAMS) | {"group"}
    for rule in ask.config(thesis.load())["filters"]:
        assert set(rule["set"]) <= allowed, rule


# ---- the home page ---------------------------------------------------------------------------------------------------------------------
def test_home_has_the_bar_and_not_the_old_count_block(client):
    t = client.get("/").text
    assert "companies surfaced" not in t and "company surfaced" not in t and "hc-kicker" not in t and "hc-up" not in t
    assert 'id="ask-form"' in t and 'id="ask-q"' in t and 'id="ask-mic"' in t and 'id="ask-send"' in t and 'id="ask-voice"' in t
    assert '<h1 id="ask-h" class="ask-title">Ask <em>Aava</em></h1>' in t
    shown = [e for e in ask.examples(thesis.load()) if e.replace("'", "&#39;") in t or e in t]   # D40: only the examples that have an answer
    assert shown and shown[0] == ask.examples(thesis.load())[0] and f'placeholder="{shown[0]}"' in t
    # the mic is shipped hidden: only the Aava demo flag (aava.js's gate) shows it, so without the flag the bar is text-only
    assert re.search(r'<button class="ask-mic" id="ask-mic" type="button" hidden', t)
    assert "/static/askbar.js" in t and "/static/askbar.css" in t


def test_the_one_line_count_reads_the_numbers_the_old_block_read(client):
    t = client.get("/").text
    H = home_list.for_template(thesis.load())
    days = thesis.load()["geography"]["feed_window_days"]
    n, total = H["headline"]["new"], len(H["rows"])
    word = "company" if n == 1 else "companies"
    assert f"{n} {word} first seen in the last {days} days, {total} on the list." in t


def test_the_bar_works_without_javascript(client):
    t = client.get("/").text
    assert re.search(r'<form class="ask-bar" id="ask-form" action="/search" method="get"', t)
    assert client.get("/search", params={"q": "Viva Jets"}, follow_redirects=False).status_code == 302


def test_static_files_of_the_bar_are_served(client):
    for f, kind in (("askbar.js", "javascript"), ("askbar.css", "css")):
        r = client.get(f"/static/{f}")
        assert r.status_code == 200 and kind in r.headers["content-type"]
    js = client.get("/static/askbar.js").text
    for needle in ("webkitSpeechRecognition", "createAnalyser", "prefers-reduced-motion", "AAVA_DEMO", "/api/ask", 'rec.lang = "en-US"', "Escape"):
        assert needle in js, needle


# ---- the header Menu and the footer -------------------------------------------------------------------------------------------------------
def test_the_tab_row_is_gone_from_the_header_and_lives_in_the_menu_and_the_footer(client):
    t = client.get("/").text
    head = t[t.index("<header"):t.index("</header>")]
    foot = t[t.index('<footer class="wrap foot">'):]
    foot = foot[:foot.index("</footer>")]
    assert 'aria-label="Main"' not in head and "<nav" not in head
    assert '<details class="navmenu"' in head and "<summary" in head and ">Menu<" in head
    for href in OLD_NAV:
        want = "/?group=new" if href == "/" else href      # "New this quarter" opens the tab of that name (D73), not the unsorted home page
        assert f'href="{want}"' in head, href     # the menu sheet
        assert f'href="{want}"' in foot, href     # plain links in the footer
    for label in ("New this quarter", "The Nordic Blue 19", "Rules", "Data"):
        assert label in head and label in foot, label
    for href in OFF_MENU:
        assert f'href="{href}"' not in head and f'href="{href}"' not in foot, href
    assert "Earliness test" not in head and "Earliness test" not in foot
    bar = t[t.index('<nav class="c-tabbar"'):]
    assert 'href="/backtest"' not in bar[:bar.index("</nav>")] and ">Backtest<" not in t
    assert "c-tabbar" in t and 'aria-label="Sections"' in t   # the phone bottom tab bar stays


def test_the_old_nav_links_still_resolve(client):
    for href in OLD_NAV + OFF_MENU:
        assert client.get(href).status_code == 200, href


def test_the_header_sector_block_is_gone_and_the_sector_lives_in_the_filter(client):
    for url in ("/", "/radar", "/match", "/method", "/data", "/backtest"):
        t = client.get(url).text
        assert 'class="thesis-bar"' not in t and "thesis-select" not in t and "Change sector or region" not in t and 'class="thesis-switch"' not in t, url


# ---- the site pages list: one source for the Menu and the footer; Match only when its route exists ------------------------------------------
def test_site_pages_lists_match_only_when_the_route_exists():
    from types import SimpleNamespace as NS
    from radar.routes.ask import site_pages
    cur = {"cohort_label": "The Nordic Blue 19"}
    without = NS(app=NS(routes=[NS(path="/"), NS(path="/radar")]))
    withm = NS(app=NS(routes=[NS(path="/"), NS(original_router=NS(routes=[NS(path="/match")]))]))   # reached through an include_router wrapper
    assert [k for _h, _l, k in site_pages(without, cur)] == ["feed", "radar", "backtest", "method", "data"]
    assert [k for _h, _l, k in site_pages(withm, cur)] == ["feed", "radar", "match", "backtest", "method", "data"]
    assert site_pages(without, cur)[1][1] == "The Nordic Blue 19" and site_pages(without, {})[1][1] == "Cohort radar"


def test_the_api_index_and_unknown_api_paths(client):
    assert any(e["path"].startswith("/api/ask") for e in client.get("/api").json()["endpoints"])
    r = client.get("/api/no-such-endpoint")
    assert r.status_code == 404 and "no API endpoint" in r.json()["error"]
