"""Provenance log (jx40): the seeded decisions and the entries a run appends, on a copy of the snapshot store."""
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from radar import provenance

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot" / "radar_redstone_apelago_blue.sqlite"
RULES = ROOT / "PROJECT_RULES.md"


def test_seed_covers_the_named_decisions():
    ids = [d["rule_id"] for d in provenance.SEED]
    assert ids == [f"D{i}" for i in range(1, 21)]
    text = " ".join(d["action"] for d in provenance.SEED)
    for needle in ("72190", "03210", "582", "different source family", "c1 GRANT SUPPORT", "consultancy", "NO is one of its countries",
                   "Oyj", "TOL 86", "person-shaped"):
        assert needle in text, needle
    for d in provenance.SEED:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", d["at"]) and d["affected"] and d["evidence"]
        assert "—" not in d["action"] + d["affected"]


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="no git history in this checkout")
def test_seed_times_are_the_commit_times():
    for d in provenance.SEED:
        out = subprocess.run(["git", "-C", str(ROOT), "show", "-s", "--format=%ad", "--date=format-local:%Y-%m-%dT%H:%M", d["commit_sha"]],
                             capture_output=True, text=True, env={"TZ": "UTC", "PATH": "/usr/bin:/bin:/usr/local/bin"}).stdout.strip()
        if out:  # a shallow clone may not hold the commit
            assert out == d["at"][:16], (d["rule_id"], out)


@pytest.mark.skipif(not SNAP.is_file(), reason="snapshot store not in this checkout")
def test_seed_and_record_on_a_copy(tmp_path):
    path = tmp_path / "copy.sqlite"
    shutil.copy(SNAP, path)
    conn = sqlite3.connect(str(path))
    assert provenance.seed(conn) == 20 and provenance.seed(conn) == 0  # recorded once
    assert provenance.record(conn, rule_id="A1", kind="run", action="test run")
    with pytest.raises(ValueError):
        provenance.record(conn, rule_id="B1-01", kind="run", action="an issue id is not a rule")
    log = provenance.entries(conn)
    assert len(log) == 21 and [r["at"] for r in log] == sorted(r["at"] for r in log)
    assert "D12" in provenance.render(provenance.entries(conn, "D12")) and "1 entries" in provenance.render(provenance.entries(conn, "D12"))


def test_log_prints_without_a_store():
    text = provenance.render(provenance.entries(None))
    assert text.endswith("20 entries") and "baad087" in text


@pytest.mark.skipif(not RULES.is_file(), reason="PROJECT_RULES.md not written yet")
def test_every_cited_id_is_in_project_rules():
    rules = set(re.findall(r"\*\*([AD]\d+)\.", RULES.read_text(encoding="utf-8")))
    assert {d["rule_id"] for d in provenance.SEED} <= rules
