"""Pre-delivery consistency check (jx40): PASS on a copy of the snapshot with candidates and provenance built, and each
check fails on the one kind of row it exists to catch."""
import shutil
import sqlite3
from pathlib import Path

import pytest

from radar import candidates, consistency, provenance, thesis

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot" / "radar_redstone_apelago_blue.sqlite"
pytestmark = pytest.mark.skipif(not SNAP.is_file() or not consistency.RULES.is_file(), reason="snapshot store or PROJECT_RULES.md missing")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("cons") / "built.sqlite"
    shutil.copy(SNAP, path)
    conn = sqlite3.connect(str(path))
    rows, _ = candidates.collect(conn, thesis.load(), skip=("prh", "hilma"))
    candidates.write(conn, rows)
    provenance.seed(conn)
    conn.close()
    return path


@pytest.fixture()
def copy(built, tmp_path):
    p = tmp_path / "c.sqlite"
    shutil.copy(built, p)
    return sqlite3.connect(str(p)), p


def _result(conn):
    return {r["name"]: r for r in consistency.check(conn)}


def test_snapshot_passes(copy):
    conn, p = copy
    res = _result(conn)
    assert all(r["ok"] for r in res.values()), {k: r["examples"] for k, r in res.items() if not r["ok"]}
    assert res["confidence"]["checked"] == 1423 and res["provenance"]["checked"] == 20
    assert consistency.main(["--db", str(p)]) == 0


@pytest.mark.parametrize("name, sql", [
    ("pending", "UPDATE companies SET name='Viva Electric Jets' WHERE company_key='2962040-6'"),  # a pending value went live
    ("confidence", "UPDATE signals SET confidence='low' WHERE id=(SELECT MIN(id) FROM signals WHERE adapter='hilma')"),
    ("labels", "UPDATE signals SET signal_type='made_up_type' WHERE id=(SELECT MIN(id) FROM signals)"),
    ("dates", "UPDATE signals SET date='2026-02-30' WHERE id=(SELECT MIN(id) FROM signals)"),
    ("business_ids", "UPDATE companies SET y_tunnus='2962040-5' WHERE company_key='2962040-6'"),
    ("countries", "UPDATE companies SET country='XX' WHERE company_key='2962040-6'"),
    ("amounts", "UPDATE signals SET detail='SEK 100 000' WHERE id=(SELECT MIN(id) FROM signals WHERE amount_eur IS NOT NULL)"),
    ("provenance", "INSERT INTO provenance (at, rule_id, kind, action, recorded_at) VALUES ('2026-10-17T00:00:00Z','A99','run','x','2026-10-17T00:00:00Z')"),
])
def test_each_check_fails_on_its_case(copy, name, sql):
    conn, p = copy
    conn.execute(sql)
    conn.commit()
    res = _result(conn)
    assert not res[name]["ok"] and res[name]["failed"] >= 1
    failed = {k for k, r in res.items() if not r["ok"]}
    # and only that check; a broken Business ID also breaks the ID match a high Business Finland row rests on
    assert failed == {name} or (name == "business_ids" and failed == {"business_ids", "confidence"})
    assert consistency.main(["--db", str(p)]) == 1


def test_an_applied_row_cannot_be_pending(copy):
    conn, _ = copy
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE field_candidates SET status='PENDING_DECISION' WHERE applied=1")


def test_confidence_rules():
    assert consistency.expected_confidence("prh", "Registered in PRH/YTJ on 2020-01-01; matched because industry code 30110 is in the thesis.", True) == {"low"}
    assert consistency.expected_confidence("cordis", "Matched by VAT number FI29020072 to Y-tunnus 2902007-2.", True) == {"high"}
    assert consistency.expected_confidence("businessfinland", "x", False) == {"medium"}
    assert consistency.expected_confidence("ecosystem", "x", True) is None  # the dataset's own confidence (A24)
