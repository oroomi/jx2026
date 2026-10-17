"""Hygiene fixes from the independent judge's pass on the live site (PROJECT_RULES D36 to D41), on a copy of the committed snapshot with
synthetic rows added where the snapshot is thin (briefs, stitcher log). The synthetic rows hold the exact shapes the live store holds."""
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import ask, db, emit, home_list, matchmaker, matchtext, store, thesis, words

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
VIVA, ARCTIC, FEEDCO = "2962040-6", "3166759-6", "3648578-3"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")

RUN = "2026-10-17T10:00:00Z"
VIVA_BRIEF = ("The memo recommends an accelerator under fallback c2 (ocean impact Medium (implied by the sector), business readiness Medium). "
              "Elsewhere it points to a partner introduction under rule e, but the trigger is a tender. It sits on the watchlist under row 7 (all four Medium).")


def _seed(dst: Path) -> None:
    """Briefs that name decision rules by id, and a stitcher run whose quote, queries and signal text hold a redaction marker."""
    import json
    conn = db.connect(dst / "radar_redstone_apelago_blue.sqlite")
    for key, text in ((VIVA, VIVA_BRIEF), (ARCTIC, "The memo puts it on the watchlist under row 7 (ocean impact Medium).")):
        conn.execute("INSERT OR REPLACE INTO company_brief_slots (company_key, written, slots_json, imported_at) VALUES (?,?,?,?)",
                     (key, "2026-10-17", json.dumps({"what_the_fund_should_do": {"text": text, "cites": []}}), "2026-10-17"))
    rows = [("search", "query", '"Viva Jets Oy"', None, None), ("search", "llm_query", '"WESI System" OR "WESI [name]"', None, None),
            ("search", "llm_query", '"viva jets" [name] stage 1 OR stage 2', None, None), ("read", "proposed", None, None, None),
            ("verify", "kept", None, "where we participated in the [name] with our dealer [name]", "site_customer"),
            ("verify", "kept", None, "Viva Jets showed its jets at the sea fair", "site_customer")]
    for i, (step, outcome, query, quote, stype) in enumerate(rows):
        conn.execute("INSERT INTO stitch_log (run_id, company_key, step, outcome, query, signal_type, date, date_precision, source_url, quote, confidence, name_match, ts) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (RUN, VIVA, step, outcome, query, stype, "2026-04-30" if stype else None, "day" if stype else None,
                      f"https://example.test/viva/{i}" if stype else None, quote, "medium" if stype else None, "legal_name" if stype else None, RUN))
    emit.emit_signal(conn, company_key=VIVA, signal_type="site_customer", date="2026-02-28", source_url="https://example.test/viva/sig", confidence="medium",
                     adapter="stitcher", detail='"where we participated in the [name] with our dealer [name]" (vivaelectricjets.com) Month only. Page first archived 2026-04-23.')
    conn.commit()
    conn.close()


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    d = tmp_path_factory.mktemp("hyg")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, d / f.name)
    _seed(d)
    return d


@pytest.fixture()
def site(seeded, monkeypatch):
    """Per test, after the autouse fixture that points RADAR_DATA_DIR at an empty directory."""
    monkeypatch.setenv("RADAR_DATA_DIR", str(seeded))
    monkeypatch.delenv("RADAR_DB", raising=False)
    monkeypatch.delenv("RADAR_THESIS", raising=False)
    import app
    return TestClient(app.app), seeded


def _visible(text: str) -> str:
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))


# What the judge found on screen (item 1 and 2 of the pass). Each is a string a reader must never meet.
FORBIDDEN = {
    "dataset match N of 100": r"dataset match \d",
    "dataset impact rating": r"dataset impact rating",
    "dataset score": r"dataset score",
    "Rank = the dataset's score": r"Rank = the dataset",
    "fallback id": r"fallback c\d",
    "rule letter": r"\brule [a-g]\b(?![\w-])",
    "decision row id": r"\brow \d{1,2}\b(?! of)",
    "capability tag": r"capability tag|\bC(?:[1-9]|1[0-2])\b",
    "masked code": r"\bmasked\b|\b\d{2,3}xx+\b",
    "redaction marker": r"\[name",
    "list working note": r"task brief|marine relevance not checked|Brief item|Thesis not verified|returned HTTP|named in (?:the )?brief",
    "group tag as a word": r"· (?:feed|intake|ecosystem)\b|· cohort(?! company)|· portfolio(?! company)",
}
PAGES = ["/", f"/c/{VIVA}", f"/c/{ARCTIC}", f"/c/{FEEDCO}", "/match", "/match?org=apelago", "/match?org=apelago&tab=connected", "/method", "/data"]


def test_none_of_the_judged_strings_is_on_any_judged_page(site):
    client, _ = site
    bad = []
    for p in PAGES:
        r = client.get(p)
        assert r.status_code == 200, p
        t = _visible(r.text)
        t = re.sub(r"<span class=\"cc-rule\".*?</span>", " ", t)          # the verdict block's own rule label belongs to the coherence work
        for name, rx in FORBIDDEN.items():
            for m in re.finditer(rx, t):
                bad.append((p, name, t[max(0, m.start() - 40):m.end() + 40]))
    assert not bad, bad[:8]


def test_rule_ids_in_a_stored_brief_are_said_in_the_rules_words(site):
    # The stored brief sentences that named a rule now disagree with the coherent memo (D46-D53) and are dropped by the stale guard,
    # so the words are checked on the helper, and the pages are checked for any leftover id.
    client, _ = site
    from radar import thesis as thesis_mod, words
    th = thesis_mod.load()
    assert "the fallback rule for business readiness Low or Medium" in words.rule_words("recommends an accelerator under fallback c2.", th)
    for key in (VIVA, ARCTIC):
        t = _visible(client.get(f"/c/{key}").text)
        assert not re.search(r"\b(?:fallback|rule) c\d\b", t), key

def test_rule_words_leave_unknown_ids_and_ordinary_sentences_alone():
    th = thesis.load()
    assert words.rule_words("a rule a company must follow", th) == "a rule a company must follow"
    assert words.rule_words("under rule x, then row 99.", th) == "under rule x, then row 99."
    assert words.rule_words("and fallback c2 of the decision rules applies.", th) == "and the fallback rule for business readiness Low or Medium applies."
    assert words.rule_words("under fallback c2 (x)", None) == "under fallback c2 (x)"


def test_scores_become_words_and_the_rank_rule_names_no_dataset_score():
    from radar import matching
    s = matching.plain_why("caps ['C10', 'C3']; kw []; stage 1.0; impact 1/5", 67.5)
    assert "the declared ecosystem research rates the fit and its impact" in s
    assert not re.search(r"\d+ of (?:100|5)|67|C\d", s) and "dataset" not in s
    assert "dataset" not in matching.RANK_RULE.split("Rank =")[1].split(".")[0] and "rating itself is not printed" in matching.RANK_RULE


def test_group_tags_are_printed_as_words():
    from radar import labels
    assert labels.group_label("feed") == "found in the early-signal feed" and labels.group_label("cohort") == "cohort company"
    assert labels.group_label("something_new") == "something new"


# ---- the redaction marker: a quote or a query with a gap is dropped, never shown with the gap ---------------------------------------------
def test_a_marked_quote_query_or_signal_text_is_not_shown(site):
    client, _ = site
    t = _visible(client.get(f"/c/{VIVA}").text)
    assert "[name" not in t and "with our dealer" not in t
    assert "Viva Jets showed its jets at the sea fair" in t, "a quote without a marker stays"
    assert "(quote not shown: it names a person or place we do not print)" in t
    assert '"WESI System"' in t and "WESI [name]" not in t, "the marked OR-term goes, the rest of the query stays"
    assert "1 search is not listed, because it holds a name we do not print." in t, "the query that is not made of OR-terms is not listed, and the page says so"
    assert int(re.search(r"(\d+) searches run", t).group(1)) == 3, "the count is of searches run, not of searches listed"


def test_marker_helpers():
    assert words.drop_marked_terms('"A" OR "B [name]"') == '"A"'
    assert words.drop_marked_terms('"A" [name] stage 1 OR stage 2') is None
    assert words.drop_marked_terms('"A [name redacted]"') is None
    assert words.drop_marked_terms('"A" OR "B"') == '"A" OR "B"'
    assert words.drop_marked_quotes('"hello [name] there" (host) tail') == f"{words.QUOTE_GONE} (host) tail"
    assert words.drop_marked_quotes('"fine" (host)') == '"fine" (host)'


# ---- stop words and the declared lists' own notes -------------------------------------------------------------------------------------
def test_stop_words_never_count_as_shared_words():
    th = thesis.load()
    cfg = matchtext.config(th)
    for w in ("include", "included", "member", "members", "challenges", "dataset", "organisation"):
        assert w in cfg["stop"], w
    a = matchtext.stems("Seafarer wellbeing programmes include members and challenges", cfg)
    assert "includ" not in a and "member" not in a and "challe" not in a and "seafar" in a
    sp = {"stems": matchtext.stems("seafarer include member", cfg)}
    org = {"has_declared": True, "stems_free": matchtext.stems("seafarers include challenges", cfg), "name": "X", "url": None}
    sp["url"] = None
    res = matchmaker._keywords(sp, org, cfg, {})
    assert res["met"] is False, "one real word in common is not enough, and a stop word never makes the second"


def test_working_notes_of_the_declared_lists_are_never_printed_or_read():
    cfg = matchtext.config(thesis.load())
    for note in ("Thesis not verified; listed in task brief as a Finnish investor candidate.", "Brief item; ABB Ventures marine relevance not checked.",
                 "Brief lists marine/tech grants; not verified.", "Finnish foundation named in brief."):
        assert matchtext.organisation_words(note, cfg) == "", note
    mixed = "Funds ocean data startups. Finnish relevance not checked. Pilot sites in Turku."
    assert matchtext.organisation_words(mixed, cfg) == "Funds ocean data startups. Pilot sites in Turku."


def test_no_counterpart_line_on_match_holds_a_note(site):
    client, _ = site
    th = thesis.load()
    conn = store.open_db(thesis=th)
    try:
        rows = matchmaker.org_list(th, conn=conn)
    finally:
        conn.close()
    assert rows
    for r in rows:
        assert not re.search(r"task brief|not checked|not verified|named in (?:the )?brief|Brief item|\.csv|returned HTTP", r["focus"], re.I), (r["name"], r["focus"])
    kinds_only = [r for r in rows if r["name"] in ("Inventure", "Korkia", "Kiuas Accelerator")]
    assert kinds_only and all(r["focus"] and "brief" not in r["focus"].casefold() for r in kinds_only)


# ---- the org view: connected companies are their own list (D38) -----------------------------------------------------------------------
def test_org_view_has_a_connected_tab_and_ranks_only_the_others(site):
    client, _ = site
    first = _visible(client.get("/match?org=apelago").text)
    assert "Best fits" in first and "Already connected" in first and "Declared member" not in first
    tab = _visible(client.get("/match?org=apelago&tab=connected").text)
    assert "Declared member" in tab and "not ranked, it already knows them" in tab and "Startups that fit, not yet connected" not in tab
    th = thesis.load()
    conn = store.open_db(thesis=th)
    try:
        res = matchmaker.match_org("apelago", th, conn=conn, limit=25)
    finally:
        conn.close()
    cohort = {k for k, in sqlite3_rows(site[1], "SELECT company_key FROM companies WHERE group_tag='cohort'")}
    assert cohort <= {r["key"] for r in res["connected"]} and not cohort & {r["key"] for r in res["startups"]}
    assert not any(r["member"] for r in res["startups"])


def sqlite3_rows(d: Path, sql: str):
    import sqlite3
    c = sqlite3.connect(d / "radar_redstone_apelago_blue.sqlite")
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def test_the_ask_card_for_an_organisation_does_not_promise_a_ranking(site):
    client, _ = site
    d = client.get("/api/ask", params={"q": "Who should A'Pelago meet?"}).json()
    assert d["intent"] == "match" and "ranked" not in d["say"] and "already connected" in d["say"]


# ---- the thesis cookie trap (D39) -----------------------------------------------------------------------------------------------------
def test_a_company_page_finds_the_sector_that_holds_the_company(site):
    client, d = site
    health = "health_tech_turku"
    assert not sqlite3_rows_in(d / "radar_health_tech_turku.sqlite", VIVA), "the health store does not hold Viva Jets (the case under test)"
    c = TestClient(client.app)
    assert c.get(f"/?thesis={health}").status_code == 200
    assert c.cookies.get("radar_thesis") == health
    r = c.get(f"/c/{VIVA}?demo=1")
    assert r.status_code == 200 and "Viva Jets" in r.text, "was a 404 while the cookie held another sector"
    assert c.cookies.get("radar_thesis") == thesis.load()["id"], "the cookie follows the sector that holds the company"
    assert _sector(c.get("/").text) == thesis.load()["id"]
    assert c.get("/c/no-such-company-key").status_code == 404, "a company in no sector is still a 404"


def _sector(page_html: str) -> str:
    """The sector the page shows: the checked option of the Sector filter group (the header switcher moved there, D33)."""
    return re.search(r'href="/\?thesis=([a-z_]+)"[^>]*role="radio" aria-checked="true"', page_html).group(1)


def sqlite3_rows_in(path: Path, key: str):
    import sqlite3
    c = sqlite3.connect(path)
    try:
        return c.execute("SELECT 1 FROM companies WHERE company_key=?", (key,)).fetchall()
    finally:
        c.close()


def test_demo_flag_on_the_home_page_resets_to_the_default_sector(site):
    client, _ = site
    default = thesis.load()["id"]
    c = TestClient(client.app)
    c.get("/?thesis=health_tech_turku")
    assert _sector(c.get("/").text) == "health_tech_turku", "the cookie holds health"
    assert _sector(c.get("/?demo=1").text) == default and c.cookies.get("radar_thesis") == default
    assert _sector(c.get("/").text) == default, "and it stays on the default afterwards"
    assert _sector(c.get("/?demo=1&thesis=health_tech_turku").text) == "health_tech_turku", "an explicit ?thesis= still wins"
    c.get("/?thesis=health_tech_turku")
    assert _sector(c.get("/").text) == "health_tech_turku", "the cookie is still honoured without the demo flag"


# ---- the ask bar (D40) --------------------------------------------------------------------------------------------------------------
def _H(rows):
    return {"rows": rows, "headline": {"new": 0, "month": 0}, "groups": [], "countries": []}


def _row(verdict, country="FI"):
    return {"company_key": "k", "name": "K", "facets": {"verdict": [verdict], "country": [country], "fit": ["High"], "sector": ["none"], "trl": ["none"],
                                                       "brl": ["none"], "irl": ["none"], "impact": ["none"]}}


def test_example_chips_are_shown_only_when_their_answer_is_not_empty(site, monkeypatch):
    th = thesis.load()
    conn = store.open_db(thesis=th)
    try:
        monkeypatch.setattr(home_list, "for_template", lambda t, *a, **k: _H([_row("WATCHLIST")]))
        ask._examples_cache.clear()
        ex = ask.live_examples(th, conn)
        assert "Show accelerator candidates in Finland" not in ex, "no accelerator candidate on this list: the chip would open an empty answer"
        assert "Show companies on the watchlist" in ex and "What is new on the radar?" in ex
        assert "Show investment-ready companies in Finland" not in ask.examples(th), "the empty example is out of the configuration"
        ask._examples_cache.clear()
        monkeypatch.setattr(home_list, "for_template", lambda t, *a, **k: _H([_row("ACCELERATOR")]))
        assert "Show accelerator candidates in Finland" in ask.live_examples(th, conn)
        ask._examples_cache.clear()
        monkeypatch.setattr(home_list, "for_template", lambda t, *a, **k: None)           # the list is not built yet: filter chips wait
        assert not [q for q in ask.live_examples(th, conn) if q.startswith("Show ")]
    finally:
        ask._examples_cache.clear()
        conn.close()


def test_home_chips_are_a_subset_of_the_configured_examples_with_answers(site):
    client, _ = site
    home_list.warm(thesis.load())            # build the list here, so a slow machine's 3 second wait cannot turn the chips off
    t = client.get("/").text
    chips = [html.unescape(x) for x in re.findall(r'class="ask-chip" data-q="([^"]*)"', t)]
    assert chips and set(chips) <= set(ask.examples(thesis.load()))
    for q in chips:
        d = client.get("/api/ask", params={"q": q}).json()
        assert d["intent"] not in ("help", "nothing", "search") and (d["count"] != 0), (q, d["say"])


def test_an_unknown_word_says_so(site):
    client, _ = site
    for q in ("xyzzyqq", "tell me about zorbulon"):
        d = client.get("/api/ask", params={"q": q}).json()
        word = q.split()[-1]
        assert d["intent"] == "nothing" and d["url"] is None and d["action"] == "none"
        assert d["say"] == f"Nothing on the radar matches {word}. Try a company name, a country, or a sector."
    assert client.get("/api/ask", params={"q": "Arctic"}).json()["intent"] != "nothing", "a real name still answers"


def test_what_is_new_is_read_by_the_home_feed_reader(site, monkeypatch):
    """The ask bar and the home page's embedded answer are the same function of the same rows, so neither opens with a utility-code-only row."""
    client, _ = site
    from radar.routes import aava as aava_routes
    utility = {"company_key": "u1", "name": "Vesi Co-op Oy", "date": "2026-10-10", "strength": "strong", "reasons": ["industry_code"], "industry_code": "36000",
               "industry_desc": "Water collection, treatment and supply", "signal_type": "register_entry", "source_url": "https://example.test/u"}
    boat = {"company_key": "b1", "name": "Boat Oy", "date": "2026-10-05", "strength": "strong", "reasons": ["own_text"], "industry_code": "30120",
            "industry_desc": "Building of pleasure boats", "signal_type": "register_entry", "source_url": "https://example.test/b"}
    monkeypatch.setattr(store, "feed", lambda conn, th, **k: [utility, boat])
    d = client.get("/api/ask", params={"q": "what is new"}).json()
    assert d["intent"] == "feed" and "Vesi Co-op" not in d["say"].split(":")[0] and d["say"].startswith("Here ") and "Boat Oy" in d["say"].split(":")[0]
    home = aava_routes.feed_reader([utility, boat], thesis.load())["segments"]
    assert [s["text"] for s in d["segments"]] == [s["text"] for s in home]


# ---- numbers that disagree (D41) ----------------------------------------------------------------------------------------------------------
def test_method_names_both_counts_of_the_home_list(site):
    client, d = site
    t = _visible(client.get("/method").text)
    m = re.search(r"Now: (\d+) companies in the main list .*? The list on the home page is these (\d+) plus the (\d+) declared cohort and portfolio companies, (\d+) in all", t)
    assert m, t[t.find("Now:"):t.find("Now:") + 400]
    main, again, declared, total = map(int, m.groups())
    assert main == again and main + declared == total
    assert declared == sqlite3_rows(d, "SELECT COUNT(*) FROM companies WHERE group_tag IN ('cohort','portfolio')")[0][0]
    th = thesis.load()
    conn = store.open_db(thesis=th)
    try:
        assert len(home_list.build(conn, th)["rows"]) == total, "the sentence's total is the home list's own length"
    finally:
        conn.close()


def test_radar_company_and_backtest_name_their_measures(site):
    client, _ = site
    radar = _visible(client.get("/radar").text)
    assert re.search(r"\d+ with at least one dated public event of the seven kinds this page ranks", radar)
    page = _visible(client.get(f"/c/{ARCTIC}").text)
    m = re.search(r"(\d+) dated signals? of every kind \((\d+) of the seven kinds the cohort radar ranks\)", page)
    assert m and int(m.group(2)) <= int(m.group(1))
    row = re.search(r"Arctic Fry Oy \S+ (\d+) ", radar)
    assert row and int(row.group(1)) == int(m.group(2)), "the company page and /radar print the same ranked count"
    bt = _visible(client.get("/backtest").text)
    assert re.search(r"\d+ of 19 companies have a counted signal \(every kind counted on this page", bt)


def test_method_ladder_is_d27_and_levels_one_and_two_are_not_called_low(site):
    client, _ = site
    t = _visible(client.get("/method").text)
    assert "the ladder is ours (D27)" in t and "(D22)" not in t
    assert re.search(r'levels 1 to 2 carry no band and read "not yet evidenced"', t) and "Low is level 1" not in t


# ---- the criteria cell on a phone (D41) -----------------------------------------------------------------------------------------------
def test_not_yet_evidenced_has_a_short_form_and_never_breaks_mid_word():
    css = (ROOT / "radar" / "static" / "criteria.css").read_text(encoding="utf-8")
    cv = re.search(r"\.cr-v \{[^}]*\}", css).group(0)
    assert "overflow-wrap: anywhere" not in cv and "overflow-wrap: break-word" in cv
    assert re.search(r"@media \(max-width: 520px\) \{ \.cr-full \{ display: none; \} \.cr-short \{ display: inline; \} \}", css)
    box = (ROOT / "radar" / "templates" / "_criteria_box.html").read_text(encoding="utf-8")
    gap = re.search(r'GAP_TEXT = "([^"]+)"', box).group(1)
    assert gap == home_list.GAP, "the template's gap words are the module's"
    assert 'class="cr-full"' in box and 'class="cr-short" aria-hidden="true">Gap<' in box


def test_the_criteria_box_marks_a_category_band_next_to_no_impact_area():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(ROOT / "radar" / "templates"), autoescape=True)
    tpl = env.get_template("_criteria_box.html")
    cell = lambda **k: {"level": None, "band": None, "text": None, "title": "t", **k}   # noqa: E731
    K = {"impact": cell(band="Medium", text="Medium"), "trl": cell(), "brl": cell(), "irl": cell(), "fit": cell(band="High", text="High"),
         "verdict": {"text": "Watchlist", "title": "t"}}
    out = tpl.render(r={"name": "K", "criteria": K, "ocean": {"area": None, "level": None, "band": None}})
    assert "Medium" in out and 'class="cr-basis">by category<' in out
    out = tpl.render(r={"name": "K", "criteria": K, "ocean": {"area": "Ocean data and monitoring", "level": 3, "band": "Medium"}})
    assert "by category" not in out
    K["impact"] = cell(level=1, text=home_list.GAP)
    assert 'class="cr-full">Not yet evidenced<' in tpl.render(r={"name": "K", "criteria": K, "ocean": None})
