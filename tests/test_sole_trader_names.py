"""Companies only (A16): a sole trader's legal name that carries the owner's full name is a private person's name and never reaches a list."""
from radar import fit, store

TH = {"non_person_words": ["group", "solutions", "engineering"], "name_keywords": ["aqua", "marine", "fish"]}


def test_sole_trader_names_with_an_owner_name_read_as_a_person():
    for name in ["Aqua Project Przemysław Czerniejewski", "FIRMA HANDLOWO USŁUGOWA „HERO” TOMASZ GIZA", "EcoFishCon – Monika Rechulicz",
                 "Nowak Krzysztof Sprzedaż Ryb", "Stefan Bruckbauer Hobby Freizeit und Mehr", "Leszek Jaworski, Michał Jaworski"]:
        assert fit.sole_trader_name(name, TH), name
        assert fit.looks_like_person(name, TH), name


def test_companies_with_a_legal_form_and_plain_business_names_do_not():
    for name in ["GENERAL ENGINEERING KOWAL Sp. z o.o.", "Insinööritoimisto Johan Forsström OyAb", "Since Labs Oy", "Arctic Fry Oy",
                 "Unique Docks", "Race for Oceans Technology", "Uniwersytet Przyrodniczy w Poznaniu", "Anna", "Sterna Group"]:
        assert not fit.sole_trader_name(name, TH), name


def test_the_baltic_feed_names_no_sole_trader():
    """On the built Baltic store (the repo's data/, gitignored, or RADAR_LIVE_DATA; skipped where it is not built; conftest points
    RADAR_DATA_DIR at an empty folder) no feed row is a sole trader's name, and the hidden count grew."""
    import os, sqlite3, pytest
    from radar import thesis as thesis_mod
    root = os.environ.get("RADAR_LIVE_DATA") or os.path.join(os.path.dirname(__file__), "..", "data")
    db = os.path.join(root, "radar_baltic_blue.sqlite")
    if not os.path.exists(db):
        pytest.skip("Baltic store not built here")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    th = thesis_mod.load("config/thesis_baltic_blue.yaml")
    rows, hidden = store._feed(conn, th, limit=500)
    assert rows and not [r["name"] for r in rows if fit.sole_trader_name(r["name"], th)]
    assert "Aqua Project Przemysław Czerniejewski" not in {r["name"] for r in rows}
    assert hidden >= 5
