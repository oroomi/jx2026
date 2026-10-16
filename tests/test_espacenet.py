"""Espacenet / EPO OPS adapter. tests/fixtures/espacenet_ops_search.json is a SYNTHETIC OPS-shaped response (made-up
applicants and numbers); no test touches the network."""
import csv
import json
import re
from pathlib import Path

import httpx
import pytest

from radar import build, db, emit
from radar.adapters import declared
from radar.adapters import espacenet as es

FIX = json.loads((Path(__file__).parent / "fixtures" / "espacenet_ops_search.json").read_text(encoding="utf-8"))
TOKEN = "fixture-token-not-a-secret"


class FakeOps:
    """MockTransport handler: token endpoint, then fixture pages keyed by the first pa= term, 404 for anything else."""

    def __init__(self, stop: dict[int, int] | None = None):
        self.stop = stop or {}  # n-th request (1-based, token included) -> status to answer instead
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        assert request.headers["user-agent"] == es.UA
        if len(self.calls) in self.stop:
            return httpx.Response(self.stop[len(self.calls)])
        if request.url.path == "/3.2/auth/accesstoken":
            assert request.method == "POST" and request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": TOKEN, "token_type": "BearerToken", "expires_in": "1199"})
        assert request.url.path == "/3.2/rest-services/published-data/search/biblio"
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        first = re.search(r'pa="([^"]+)"', request.url.params["q"]).group(1)
        if first in FIX:
            return httpx.Response(200, json=FIX[first])
        return httpx.Response(404, text="<fault><code>SERVER.EntityNotFound</code><message>No results found</message></fault>")


def write_csvs(tmp_path):
    def write(src, rows):
        with open(src, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        p = tmp_path / src.name
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            for r in rows:
                w.writerow({h: r.get(h, "") for h in header})
        return p

    cohort = write(es.COHORT_CSV, [
        {"company": "Testimeri", "group": "cohort", "country": "FI", "y_tunnus": "9999991-1", "ytj_name": "Testimeri Oy",
         "ytj_source": "https://example.org/ytj/testimeri"},
        {"company": "Koeranta", "group": "cohort", "country": "SE", "website": "https://example.org/koeranta"},
        {"company": "Vesikoe", "group": "portfolio", "country": "FI", "website": "https://example.org/vesikoe"},
    ])
    universe = write(es.UNIVERSE_CSV, [
        {"name": "Kokeilu Marine Oy (Kokeilu)", "y_tunnus_if_found": "9999993-3", "source_url": "https://example.org/kokeilu"},
        {"name": "Nimeton", "source_url": "https://example.org/nimeton"},
    ])
    return cohort, universe


@pytest.fixture(autouse=True)
def slept(monkeypatch):
    calls = []
    monkeypatch.setattr(es.time, "sleep", calls.append)
    monkeypatch.setattr(es, "_last_call", 0.0)
    return calls


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("EPO_OPS_KEY", "fixture-key")
    monkeypatch.setenv("EPO_OPS_SECRET", "fixture-secret")


@pytest.fixture
def conn():
    return db.connect(":memory:")


def run(tmp_path, conn, handler):
    cohort, universe = write_csvs(tmp_path)
    return es.run(conn, {}, transport=httpx.MockTransport(handler), cache_dir=tmp_path / "cache",
                  cohort_csv=cohort, universe_csv=universe)


def signals(conn, key):
    return conn.execute("SELECT * FROM signals WHERE company_key=? ORDER BY date", (key,)).fetchall()


def test_fixture_emits_one_signal_per_family_at_earliest_filing(tmp_path, conn, key):
    ops = FakeOps()
    r = run(tmp_path, conn, ops)
    assert (r["listed"], r["skipped"], r["checked"], r["not_checked"]) == (5, 2, 3, 0)
    assert (r["companies"], r["signals"], r["matched_families"], r["records_no_date"]) == (2, 3, 3, 1)
    assert r["requests"] == len(ops.calls) == 4 and r["blocked"] == ""  # token + one search per Finnish company

    t = signals(conn, "9999991-1")
    assert [s["date"] for s in t] == ["2022-09-15", "2025-01-02"]  # priority date beats the EP application date
    assert [s["source_url"] for s in t] == ["https://worldwide.espacenet.com/patent/search?q=pn%3DEP9990001A1",
                                            "https://worldwide.espacenet.com/patent/search?q=pn%3DEP9990002A1"]
    assert {(s["signal_type"], s["confidence"], s["adapter"]) for s in t} == {("patent", "medium", "espacenet")}
    assert "earliest filing 2022-09-15, published as EP9990001A1 on 2024-03-20" in t[0]["detail"]
    assert "applicant as recorded: Testimeri Oy; title: TEST DEVICE FOR A FIXTURE" in t[0]["detail"]
    assert "exact legal name 'Testimeri Oy'" in t[0]["detail"]

    v = signals(conn, "fi-vesikoe")  # declared name only, no register name: low
    assert [(s["date"], s["confidence"]) for s in v] == [("2021-05-04", "low")]
    c = conn.execute("SELECT * FROM companies WHERE company_key='fi-vesikoe'").fetchone()
    assert (c["group_tag"], c["country"], c["source_url"]) == ("portfolio", "FI", "https://example.org/vesikoe")

    assert conn.execute("SELECT count(*) FROM companies WHERE company_key='9999993-3'").fetchone()[0] == 0  # 404: nothing
    queried = [c.url.params["q"] for c in ops.calls[1:]]
    assert queried == ['pa="testimeri"', 'pa="vesikoe"', 'pa="kokeilu marine" or pa="kokeilu"']  # SE and unconfirmed rows never asked


def test_same_name_other_country_longer_name_and_undated_never_match():
    doc = lambda name, **b: {"@family-id": "1", "bibliographic-data": {  # noqa: E731
        "parties": {"applicants": {"applicant": {"@sequence": "1", "applicant-name": {"name": {"$": name}}}}}, **b}}
    cands = es._candidates([("Testimeri Oy", True)])
    dated = {"application-reference": {"document-id": {"date": {"$": "20200101"}}}}
    assert es.match(doc("TESTIMERI AB [SE]", **dated), cands) is None
    assert es.match(doc("TESTIMERI SOLUTIONS OY [FI]", **dated), cands) is None
    assert es.match(doc("TESTIMERI OY", **dated), cands) is None  # no country stated: not a confirmed Finnish applicant
    assert es.match(doc("TESTIMERI OY [FI]", **dated), cands)["filed"] == "2020-01-01"
    assert es.match(doc("TESTIMERI OY [FI]"), cands)["filed"] is None


def test_requests_are_throttled_to_one_per_two_seconds(tmp_path, conn, key, slept):
    run(tmp_path, conn, FakeOps())
    assert len(slept) == 3 and all(1.9 < s <= es.MIN_INTERVAL for s in slept)  # 4 requests, a wait before each after the first


def test_no_key_is_blocked_and_sends_nothing(tmp_path, conn, monkeypatch):
    monkeypatch.delenv("EPO_OPS_KEY", raising=False)
    monkeypatch.delenv("EPO_OPS_SECRET", raising=False)
    ops = FakeOps()
    r = run(tmp_path, conn, ops)
    assert ops.calls == [] and r["requests"] == 0
    assert r["blocked"].startswith("BLOCKED: no OPS consumer key")
    assert (r["checked"], r["not_checked"], r["signals"]) == (0, 3, 0)
    assert conn.execute("SELECT count(*) FROM signals").fetchone()[0] == 0


@pytest.mark.parametrize("status", [403, 429])
def test_stops_at_first_403_or_429(tmp_path, conn, key, status):
    ops = FakeOps(stop={3: status})  # token, Testimeri search, then the Vesikoe search is refused
    r = run(tmp_path, conn, ops)
    assert len(ops.calls) == r["requests"] == 3  # nothing after the refusal
    assert f"HTTP {status}" in r["blocked"] and (r["checked"], r["not_checked"]) == (1, 2)
    assert len(signals(conn, "9999991-1")) == 2 and signals(conn, "fi-vesikoe") == []


@pytest.mark.parametrize("status", [400, 403, 500])
def test_refused_token_stops_everything(tmp_path, conn, key, status):
    ops = FakeOps(stop={1: status})
    r = run(tmp_path, conn, ops)
    assert len(ops.calls) == 1 and r["not_checked"] == 3 and r["signals"] == 0 and f"HTTP {status}" in r["blocked"]


def test_unreachable_host_stops_after_one_attempt(tmp_path, conn, key):
    calls = []

    def refuse(request):
        calls.append(request)
        raise httpx.ConnectError("CONNECT tunnel failed, response 403", request=request)

    r = run(tmp_path, conn, refuse)
    assert len(calls) == r["requests"] == 1 and r["blocked"].startswith("OPS unreachable (ConnectError")
    assert (r["checked"], r["not_checked"], r["errors"], r["signals"]) == (0, 3, 0, 0)


def test_cache_rebuilds_without_key_or_network_and_never_stores_the_token(tmp_path, key, monkeypatch):
    first = db.connect(":memory:")
    run(tmp_path, first, FakeOps())
    cached = list((tmp_path / "cache").glob("*.json"))
    assert len(cached) == 3 and not any(TOKEN in f.read_text(encoding="utf-8") for f in cached)
    monkeypatch.delenv("EPO_OPS_KEY")
    second, ops = db.connect(":memory:"), FakeOps()
    r = run(tmp_path, second, ops)
    assert ops.calls == [] and r["blocked"] == "" and r["signals"] == 3
    assert not run(tmp_path, second, FakeOps())["signals"]  # idempotent: nothing new on a rerun


def test_existing_company_row_is_not_overwritten(tmp_path, conn, key):
    emit.upsert_company(conn, company_key="9999991-1", name="Testimeri Oy", y_tunnus="9999991-1", group_tag="cohort",
                        source_url="https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=9999991-1")
    run(tmp_path, conn, FakeOps())
    c = conn.execute("SELECT source_url, group_tag FROM companies WHERE company_key='9999991-1'").fetchone()
    assert tuple(c) == ("https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=9999991-1", "cohort")


def test_real_declared_lists_select_finnish_companies_with_declared_keys():
    companies, skipped = es.declared_companies()
    assert (len(companies), skipped) == (56, 19)
    conn = db.connect(":memory:")
    declared.run(conn)
    known = {r[0] for r in conn.execute("SELECT company_key FROM companies")}
    cohort = [c for c in companies if c["group_tag"] in ("cohort", "portfolio")]
    assert len(cohort) == 15 and all(c["key"] in known for c in cohort)
    by_key = {c["key"]: c for c in companies}
    assert [(n, legal) for n, _, legal in by_key["2651724-3"]["names"]] == [("aellia finland", True), ("aeromon", False)]


def test_build_discovers_the_adapter():
    assert any(name == "espacenet" and not isinstance(mod, Exception) for name, mod in build.discover())
