"""The private individuals the guards look for (D80). The public ecosystem file carries no person table, so the names come from the
team's full copy when RADAR_PERSON_GUARD_DB points at it, else from a person table if one exists, else there are none to find."""
import os
import sqlite3
from pathlib import Path

ECO = Path(__file__).resolve().parents[1] / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"


def person_names(min_len: int = 0) -> list[str]:
    for p in (os.environ.get("RADAR_PERSON_GUARD_DB"), str(ECO)):
        if p and Path(p).is_file():
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='person'").fetchone():
                return sorted({r[0] for r in conn.execute("SELECT name FROM person") if r[0] and len(r[0]) > min_len})
    return []
