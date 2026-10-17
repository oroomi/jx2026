"""D80: the ecosystem file in this public repo names no private individual: no person table, no personal LinkedIn profile, no first.last
e-mail address. RADAR_PERSON_GUARD_DB (optional) points at the team's full copy; when set, none of its names may occur in the public file."""
import os
import re
import sqlite3
from pathlib import Path

import pytest

ECO = Path(__file__).resolve().parents[1] / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"
PROFILE = re.compile(r"linkedin\.com/in/", re.I)
PERSONAL_MAIL = re.compile(r"\b(?!firstname\.lastname@)[a-z]+\.[a-z]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b", re.I)


def _cells(conn):
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for row in conn.execute(f"SELECT * FROM {t}"):
            for v in row:
                if isinstance(v, str):
                    yield t, v


def test_the_public_ecosystem_file_has_no_person_table_profile_or_personal_address():
    conn = sqlite3.connect(f"file:{ECO}?mode=ro", uri=True)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "person" not in tables and "entity" in tables
    bad = [(t, v[:80]) for t, v in _cells(conn) if PROFILE.search(v) or PERSONAL_MAIL.search(v)]
    assert not bad, bad


def test_no_name_from_the_full_copy_occurs_in_the_public_file():
    full = os.environ.get("RADAR_PERSON_GUARD_DB")
    if not full or not Path(full).is_file():
        pytest.skip("RADAR_PERSON_GUARD_DB is not set: the full copy lives outside the repo")
    names = {" ".join(r[0].split()).casefold() for r in sqlite3.connect(f"file:{full}?mode=ro", uri=True).execute("SELECT name FROM person")
             if r[0] and len(r[0].split()) >= 2}
    conn = sqlite3.connect(f"file:{ECO}?mode=ro", uri=True)
    hits = {n for _, v in _cells(conn) for n in names if n in " ".join(v.split()).casefold()}
    assert not hits, f"{len(hits)} names still in the public file"
