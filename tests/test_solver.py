import sys

from conftest import make_fake_fg
from fg_gui import solver


def test_parse_version():
    assert solver.parse_version("0.18.0") == (0, 18, 0)
    assert solver.parse_version("1.2.dev3") == (1, 2)
    assert solver.parse_version("") == ()


def test_info_without_package(no_fg):
    info = solver.info()
    assert not info.available and "fouriergrating" in info.error


def test_info_with_package(fake_fg):
    info = solver.info()
    assert info.available and info.version_ok and info.core_variant == "cpu" and not info.cad_available


def test_info_old_version(monkeypatch):
    monkeypatch.setitem(sys.modules, "fouriergrating", make_fake_fg("0.17.3"))
    assert not solver.info().version_ok


def test_solve_passes_through(fake_fg):
    seen = {}
    fake_fg.solve = lambda cfg: seen.setdefault("cfg", cfg)
    solver.solve({"a": 1})
    assert seen["cfg"] == {"a": 1}
