import pytest


@pytest.fixture(autouse=True)
def _patient_home_list(monkeypatch):
    """The home list and the Top matching ranking are built in a background thread, and a request waits for them at most 3 s (D26) before it
    gets the plain feed with a "still being prepared" note. On a loaded machine (a shared VPS, a CI runner) a build of the snapshot store
    takes longer than that, and every test that reads the built list then saw an empty one. Tests wait up to two minutes instead; the tests
    of the warming behaviour set their own wait inside the test, which runs after this fixture."""
    from radar import home_list, home_orgs
    monkeypatch.setattr(home_list, "WAIT_SECONDS", 120.0)
    for fn in (home_orgs.ranking, home_orgs.context):
        if fn.__defaults__ == (home_orgs.WAIT_SECONDS,):
            monkeypatch.setattr(fn, "__defaults__", (120.0,))


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """Per-thesis databases live under RADAR_DATA_DIR; tests never see or write the real data/ directory."""
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path_factory.mktemp("data")))
