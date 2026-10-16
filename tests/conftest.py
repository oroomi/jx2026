import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """Per-thesis databases live under RADAR_DATA_DIR; tests never see or write the real data/ directory."""
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path_factory.mktemp("data")))
