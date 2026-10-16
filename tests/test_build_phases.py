"""build.discover() orders adapters by (PHASE, name); PHASE defaults to 1."""
import sys
import types

from radar import adapters, build


def test_phase_order(monkeypatch):
    specs = {"aaa_enrich": 2, "bbb_default": None, "ccc_declared": 0, "ddd_disc": 1}
    mods = {}
    for n, ph in specs.items():
        m = types.ModuleType(f"radar.adapters.{n}")
        m.NAME = n
        m.run = lambda conn, th: {}
        if ph is not None:
            m.PHASE = ph
        mods[n] = m
        monkeypatch.setitem(sys.modules, f"radar.adapters.{n}", m)
    monkeypatch.setattr(build.pkgutil, "iter_modules", lambda path: [types.SimpleNamespace(name=n) for n in specs])
    assert [n for n, _ in build.discover()] == ["ccc_declared", "bbb_default", "ddd_disc", "aaa_enrich"]


def test_real_adapter_phases():
    names = [n for n, _ in build.discover()]
    assert names.index("declared") < names.index("hilma") < names.index("businessfinland")
    assert names.index("prh") < names.index("businessfinland")
