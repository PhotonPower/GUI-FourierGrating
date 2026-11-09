"""Gemeinsame Hilfen: ein Ersatzmodul für ``fouriergrating``, damit die Tests ohne Löser laufen (CI)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ORDER_DTYPE = np.dtype(
    [("n", "i4"), ("m", "i4"), ("eff", "f8"), ("eff_s", "f8"), ("eff_p", "f8"), ("amp_s", "c16"), ("amp_p", "c16")]
)


class FakeResult:
    def __init__(self):
        self.reflected = np.array([(-1, 0, 0.1, 0.0, 0.1, 0j, 0j), (0, 0, 0.2, 0.0, 0.2, 0j, 0j)], dtype=ORDER_DTYPE)
        self.transmitted = np.array([(0, 0, 0.7, 0.0, 0.7, 0j, 0j)], dtype=ORDER_DTYPE)
        self.absorption = 0.0
        self.diagnostics = {"energy_balance": 1.0, "warnings": []}


class FakeScan:
    """Zwei Wellenlängen × zwei Winkel, je R(0,0) und T(0,0) – Spalten wie ``ScanResult.columns``."""

    def __init__(self, sweep_parameter: str = ""):
        self.sweep_parameter = sweep_parameter
        rows = []
        for lam in (0.5, 0.6):
            for phi in (0.0, 10.0):
                r = 0.1 + lam * 0.1 + phi * 0.001
                rows.append((0.0, lam, phi, 0.0, 0.0, "R", 0, 0, r, 0.0, r, 0j, 0j))
                rows.append((0.0, lam, phi, 0.0, 0.0, "T", 0, 0, 1 - r, 0.0, 1 - r, 0j, 0j))
                if phi > 0:  # R(-1,0) propagiert nur bei schrägem Einfall
                    rows.append((0.0, lam, phi, 0.0, 0.0, "R", -1, 0, 0.01, 0.0, 0.01, 0j, 0j))
        keys = ["sweep_value", "lambda_um", "phi_deg", "psi_deg", "delta_deg", "side", "n", "m", "efficiency"]
        keys += ["eff_s", "eff_p", "amp_s", "amp_p"]
        dtypes = {"side": "U1", "n": "i4", "m": "i4", "amp_s": "c16", "amp_p": "c16"}
        self.columns = {k: np.asarray([r[i] for r in rows], dtype=dtypes.get(k, "f8")) for i, k in enumerate(keys)}
        self.points = [FakeResult() for _ in range(4)]


def make_fake_fg(version: str = "0.18.0") -> types.ModuleType:
    fg = types.ModuleType("fouriergrating")
    fg.__version__ = version
    fg.core_variant = lambda: "cpu"
    fg.cuda_available = lambda: False
    fg.get_backend = lambda: {"preference": "auto", "threshold": 1000}
    fg.solve = lambda cfg: FakeResult()
    fg.solve_scan = lambda cfg: FakeScan()
    cad = types.ModuleType("fouriergrating.cad")
    cad.available = lambda: False
    fg.cad = cad
    return fg


@pytest.fixture
def fake_fg(monkeypatch):
    fg = make_fake_fg()
    monkeypatch.setitem(sys.modules, "fouriergrating", fg)
    return fg


@pytest.fixture
def no_fg(monkeypatch):
    # None in sys.modules lässt den Import mit ImportError scheitern
    monkeypatch.setitem(sys.modules, "fouriergrating", None)


EXAMPLE = {
    "dimension": "1D",
    "solver": "rcwa",
    "truncation": {"Nx": 15, "Nz": 0},
    "period_um": {"x": 1.0, "z": 0.0},
    "incidence": {"lambda_um": 0.6328, "phi_deg": 20, "psi_deg": 0, "delta_deg": 90},
    "materials": {"air": {"n": 1.0}, "glass": {"n": 1.5}, "bar": {"n": 2.0}},
    "superstrate": "air",
    "substrate": "glass",
    "layers": [
        {"type": "lamellar1d", "thickness_um": 0.4, "breakpoints_um": [0.0, 0.45, 1.0], "materials": ["bar", "air"]}
    ],
}


@pytest.fixture(autouse=True)
def _clear_streamlit_caches():
    """Einstellungen, Jobverwaltung und Löserinfo sind prozessweit gecacht; jeder Test beginnt frisch."""
    import streamlit as st

    st.cache_resource.clear()
    st.cache_data.clear()
    yield


def pytest_collection_modifyitems(config, items):
    if importlib.util.find_spec("fouriergrating") is not None:
        return
    skip = pytest.mark.skip(reason="fouriergrating nicht installiert")
    for item in items:
        if "solver" in item.keywords:
            item.add_marker(skip)
