"""TEST FIXTURE ONLY: a tiny synthetic imitation of the tenderhub awards archive. Invented rows, never loaded by the app."""
import sqlite3

SCHEMA = """
CREATE TABLE awards (noticeId TEXT, published TEXT, buyer TEXT, title TEXT, winners TEXT, amountEur REAL, cpv TEXT, procedure_id TEXT);
CREATE TABLE award_winners (noticeId TEXT, businessId TEXT, rawName TEXT);
CREATE TABLE companies (businessId TEXT, name TEXT, officialName TEXT, firstWin TEXT, registered TEXT, tolCode TEXT, tolDesc TEXT, city TEXT, website TEXT);
"""
# (noticeId, published, buyer, title, amount, cpv, procedure_id, businessId, name)
AWARDS = [
    ("EF-1", "2026-03-01T03:00:00Z", "Testbuyer A", "Fixture survey", 50000.0, "71000000", "11", "1111111-1", "Young Fixture Oy"),
    ("EF-2", "2026-05-01T03:00:00Z", "Testbuyer B", "Fixture second win", 1000.0, "71000000", "12", "1111111-1", "Young Fixture Oy"),
    ("EF-3", "2026-03-02T03:00:00Z", "Testbuyer C", "Fixture survey", 40000.0, "71000000", "13", "2222222-2", "Old Fixture Oy"),
    ("EF-4", "2026-03-03T03:00:00Z", "Testbuyer D", "Fixture catering", 9000.0, "55000000", "14", "3333333-3", "Offtopic Young Oy"),
    ("EF-5", "2026-03-04T03:00:00Z", "Testbuyer E", "Meriväylän mittaus", None, "79000000", "15", "4444444-4", "Keyword Young Oy"),
    ("EF-6", "2026-03-05T03:00:00Z", "Testbuyer F", "Fixture survey", 7000.0, "71000000", "16", "5555555-5", "No Date Oy"),
    ("EF-0", "2025-01-01T03:00:00Z", "Testbuyer G", "Fixture catering", 100.0, "55000000", "10", "6666666-6", "Earlier Offtopic Oy"),
    ("EF-7", "2026-03-06T03:00:00Z", "Testbuyer G", "Fixture survey", 100.0, "71000000", "17", "6666666-6", "Earlier Offtopic Oy"),
    ("EF-8", "2026-04-01T03:00:00Z", "Testbuyer H", "Fixture catering", 300.0, "55000000", "18", "7777777-7", "Fixture Cohort Oy"),
]
COMPANIES = [
    ("1111111-1", "Young Fixture Oy", "Young Fixture Oy", "2026-03-01", "2024-06-01", "71129", "Testing", "TURKU", "https://young.example"),
    ("2222222-2", "Old Fixture Oy", "Old Fixture Oy", "2026-03-02", "2001-01-01", "71129", "Testing", "TURKU", None),
    ("3333333-3", "Offtopic Young Oy", "Offtopic Young Oy", "2026-03-03", "2025-01-01", "56210", "Catering", "TURKU", None),
    ("4444444-4", "Keyword Young Oy", "Keyword Young Oy", "2026-03-04", "2025-02-01", "71129", "Testing", "TURKU", None),
    ("5555555-5", "No Date Oy", "No Date Oy", "2026-03-05", None, None, None, None, None),
    ("6666666-6", "Earlier Offtopic Oy", "Earlier Offtopic Oy", "2025-01-01", "2024-01-01", "71129", "Testing", "TURKU", None),
    ("7777777-7", "Fixture Cohort Oy", "Fixture Cohort Oy", "2026-04-01", "2001-01-01", "56210", "Catering", "TURKU", None),
]


def build(path=":memory:", with_cohort_win=True) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for a in AWARDS:
        if a[7] == "7777777-7" and not with_cohort_win:
            continue
        conn.execute("INSERT INTO awards VALUES (?,?,?,?,?,?,?,?)", (a[0], a[1], a[2], a[3], None, a[4], a[5], a[6]))
        conn.execute("INSERT INTO award_winners VALUES (?,?,?)", (a[0], a[7], a[8]))
    conn.executemany("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?)", COMPANIES)
    conn.commit()
    return conn
