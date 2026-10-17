"""A broad consultancy or research industry code (thesis `code_alone_weak`) is never enough for the main list.
It needs a sector word from the registered line of business, the source's own text, or a corroborated legal-name word.
A boat-building, repair, water or aquaculture code is unchanged. Synthetic companies only."""
from datetime import date, timedelta

import pytest

from radar import db, emit, store, thesis

TODAY = date.today()
CONSULT_DESC = "Engineering design and technical consultancy"


def _day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


@pytest.fixture()
def feed_rows(tmp_path):
    conn = db.connect(tmp_path / "alone.sqlite")

    def co(key, name, code, desc):
        emit.upsert_company(conn, company_key=key, name=name, industry_code=code, industry_desc=desc,
                            source_url=f"https://example.test/fixture/{key}")

    def sig(key, typ, d, adapter="prh", **kw):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=d, confidence="medium", adapter=adapter,
                         source_url=f"https://example.test/fixture/{key}/{adapter}/{typ}/{d}", **kw)

    co("A-alone", "Fixture Design Oy", "71121", CONSULT_DESC)                  # 711 code, nothing else
    sig("A-alone", "register_entry", _day(10))
    co("A-lob", "Fixture Studio Oy", "71121", "Engineering design for marine structures")   # 711 code + a sector word in the line of business
    sig("A-lob", "register_entry", _day(11))
    co("A-own", "Fixture Planning Oy", "71121", CONSULT_DESC)                  # 711 code + a sector word in the source's own text
    sig("A-own", "public_contract", _day(12), adapter="hilma", detail="Fixture Buyer: Tutkimus vesistön tilasta (EUR 1,000)")
    co("A-corr", "Fixture Marine Design Oy", "71121", CONSULT_DESC)            # 711 code + a name word backed by a second source family
    sig("A-corr", "register_entry", _day(13))
    sig("A-corr", "public_contract", _day(400), adapter="hilma", detail="Fixture Buyer: Office chairs (EUR 10)")
    co("A-name", "Fixture Marine Notes Oy", "71121", CONSULT_DESC)             # 711 code + a name word, one source family only
    sig("A-name", "register_entry", _day(14))
    co("A-r200", "Fixture Testing Oy", "71200", "Technical testing and analysis")  # 712 family
    sig("A-r200", "register_entry", _day(15))
    co("A-boat", "Fixture Yard Oy", "30110", "Fixture shipbuilding")           # 301: unchanged
    sig("A-boat", "register_entry", _day(16))
    co("A-repair", "Fixture Repair Oy", "33150", "Repair of boats")            # 331: unchanged
    sig("A-repair", "register_entry", _day(17))
    conn.commit()
    th = thesis.load("config/thesis.yaml")
    rows = {r["company_key"]: r for r in store.feed(conn, th, limit=1000)}
    return conn, th, rows


def test_711_code_alone_is_weak_with_a_plain_reason(feed_rows):
    _, _, rows = feed_rows
    r = rows["A-alone"]
    assert r["strength"] == "weak"
    assert r["why"].startswith("Weak: industry code 711xx alone; a consultancy code needs a sector word.")
    assert f"'{CONSULT_DESC}' (71121)" in r["why"]
    assert "_" not in r["why"]  # plain words on the page, never snake_case
    assert rows["A-r200"]["strength"] == "weak" and "industry code 712xx alone" in rows["A-r200"]["why"]


def test_711_with_a_sector_word_from_the_line_of_business_is_strong(feed_rows):
    _, _, rows = feed_rows
    r = rows["A-lob"]
    assert r["strength"] == "strong"
    assert r["reasons"] == ["line_of_business", "industry_code"]  # the sufficient reason leads, the code follows
    assert r["why"] == "Why: The registered line of business 'Engineering design for marine structures' contains 'marin'; 1 more reason."


def test_711_with_the_source_text_or_a_corroborated_name_is_strong(feed_rows):
    _, _, rows = feed_rows
    assert rows["A-own"]["strength"] == "strong" and "own_text" in rows["A-own"]["reasons"]
    assert rows["A-corr"]["strength"] == "strong" and "corroborated_keyword" in rows["A-corr"]["reasons"]
    assert rows["A-name"]["strength"] == "weak"  # a name word with no second source family is not enough, with or without the code


def test_301_and_331_codes_alone_are_unchanged(feed_rows):
    _, _, rows = feed_rows
    assert rows["A-boat"]["strength"] == "strong" and rows["A-boat"]["reasons"] == ["industry_code"]
    assert rows["A-boat"]["why"] == "Why: Industry code 30110 (Fixture shipbuilding, PRH) is on the thesis list."
    assert rows["A-repair"]["strength"] == "strong" and rows["A-repair"]["reasons"] == ["industry_code"]


def test_counts_main_list_only_and_by_reason_follow_the_rule(feed_rows):
    conn, th, rows = feed_rows
    c = store.feed_counts(conn, th)
    assert c["companies"] == len(rows) == 8
    assert (c["main"], c["weak"]) == (5, 3)  # lob, own, corr, boat, repair strong; alone, name, r200 weak
    # all 8 rows carry a code on the list; only the 5 main-list rows count it, the 3 weak rows' codes are not main-list reasons
    assert c["by_reason"]["industry_code"] == 5


def test_family_lookup_ignores_dots_and_is_off_without_the_key():
    th = thesis.load("config/thesis.yaml")
    assert store.code_alone_family("71121", th) == "711"
    assert store.code_alone_family("71.12", th) == "711"  # the NACE spelling is the same family
    assert store.code_alone_family("72190", th) == "721"
    assert store.code_alone_family("30110", th) is None and store.code_alone_family(None, th) is None
    assert store.code_alone_family("71121", {}) is None


def test_without_the_key_the_old_rule_holds(feed_rows):
    conn, th, _ = feed_rows
    off = {k: v for k, v in th.items() if k != "code_alone_weak"}
    rows = {r["company_key"]: r for r in store.feed(conn, off, limit=1000)}
    assert rows["A-alone"]["strength"] == "strong" and rows["A-alone"]["reasons"] == ["industry_code"]


def test_every_shipped_thesis_names_its_families_and_the_rule_text_says_so():
    for name, fams in (("thesis", ["711", "712", "721"]), ("thesis_baltic_blue", ["711", "712", "721"]),
                       ("thesis_health_turku", ["702", "721"])):
        th = thesis.load(f"config/{name}.yaml")
        assert [str(f) for f in th["code_alone_weak"]] == fams
        assert ", ".join(fams) in store.rule_text(th) and "needs a sector word" in store.rule_text(th)
    assert "needs a sector word" not in store.rule_text({"geography": {"feed_window_days": 90}})


def test_a_malformed_key_is_refused(tmp_path):
    f = tmp_path / "t.yaml"
    f.write_text("id: x\ntitle: x\ngeography: {feed_window_days: 5}\nindustry_codes: []\nfeed_signal_types: []\nname_keywords: [a]\n"
                 "code_alone_weak: 711\n")
    with pytest.raises(thesis.ThesisError, match="code_alone_weak"):
        thesis.load(f)
