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


def make_fake_nearfield(two_d: bool = False) -> dict:
    """Zwei Schnitte wie ``fg.near_field``: vertikale Karte (4 × 6) und horizontale Linie bzw. Karte."""
    rng = np.random.default_rng(1)

    def cut(name, ax2, n2):
        shape = (n2, 6) if n2 else (6,)
        E = rng.normal(size=shape) + 1j * rng.normal(size=shape)
        d = {
            "cut": name,
            "axis1_name": "x",
            "axis2_name": ax2,
            "axis1_um": np.linspace(0, 1, 6),
            "axis2_um": np.linspace(-0.2, 0.4, n2) if n2 else np.zeros(0),
            "lambda_um": 0.6328,
            "meta": {"axes": {"axis1": {"name": "x"}}, "cut": name},
        }
        for q in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
            d[q] = E.copy()
        d["absE2"] = np.abs(E) ** 2
        d["absH2"] = np.abs(E) ** 2 * 0.5
        d["Sy"] = rng.normal(size=shape)
        d["material"] = (np.arange(np.prod(shape)).reshape(shape) % 3 > 0).astype(float)
        return d

    return {
        "horizontal": cut("horizontal", "z" if two_d else "y", 4 if two_d else 0),
        "vertical": cut("vertical", "y", 4),
        "incidence": {"lambda_um": 0.6328, "phi_deg": 10.0, "psi_deg": 0.0, "delta_deg": 90.0},
    }


class FakeSimulation:
    """Analytische Zielfunktion L = 1 − Σ (x − c)² mit Maximum bei c = 0,25 (Gradient exakt, wie value_and_grad)."""

    CENTER = 0.25

    def __init__(self, cfg):
        from fg_gui.optimize import get_pointer

        self._cfg, self._get = cfg, get_pointer
        self.values: dict[str, float] = {}
        self.calls = 0

    def set_parameter(self, pointer, value):
        self.values[pointer] = float(value)

    def value_and_grad(self, objective, params):
        self.calls += 1
        x = [self.values.get(p, float(self._get(self._cfg, p))) for p in params]
        w = sum(objective.values())
        d = [xi - self.CENTER for xi in x]
        return w * (1.0 - sum(di * di for di in d)), np.array([-2.0 * w * di for di in d])


def make_fake_fg(version: str = "0.18.0") -> types.ModuleType:
    fg = types.ModuleType("fouriergrating")
    fg.__version__ = version
    fg.core_variant = lambda: "cpu"
    fg.cuda_available = lambda: False
    fg.get_backend = lambda: {"preference": "auto", "threshold": 1000}
    fg.solve = lambda cfg: FakeResult()
    fg.solve_scan = lambda cfg: FakeScan()
    fg.Simulation = FakeSimulation
    fg.near_field = lambda cfg: make_fake_nearfield(cfg.get("dimension") == "2D")
    cad = types.ModuleType("fouriergrating.cad")
    cad.available = lambda: True

    def check(step, cfg):
        layers = [L for L in cfg.get("layers", []) if L.get("type") == "cad"]
        if not layers or not layers[0].get("bodies"):
            err = {
                "code": "BODY_UNASSIGNED",
                "message": "body 0 ('Pillar') has no material",
                "where_um": [0.25, 0.1, 0],
            }
            return {"ok": False, "errors": [err], "warnings": [], "bands": []}
        warn = {"code": "FEATURE_SMALL", "message": "band thin", "where_um": [0.1, 0.2, 0.3]}
        bands = [
            {"y0_um": 0.0, "y1_um": 0.2, "kind": "sectioned", "area_fractions": {"air": 0.8, "si": 0.2}},
            {"y0_um": 0.2, "y1_um": 0.26, "kind": "extrusion", "area_fractions": {"air": 0.85, "sio2": 0.15}},
        ]
        return {"ok": True, "errors": [], "warnings": [warn], "bands": bands}

    cad.check = check
    cad.preview = lambda step, cfg, y: (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><title>{y}</title></svg>'
    )
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
def _data_dir(tmp_path, monkeypatch):
    """Laufzeitdaten (gespeicherte Rechnungen) je Test in einem eigenen Verzeichnis, nie im Repository."""
    monkeypatch.setenv("FG_GUI_DATA_DIR", str(tmp_path / "data"))


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


#: kleinster brauchbarer STEP-Text für Tests (nur Kopf und zwei benannte Körper)
FAKE_STEP = (
    "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n"
    "#1=CLOSED_SHELL('Pillar',(#2));\n#3=MANIFOLD_SOLID_BREP('Pillar',#1);\n"
    "#4=CLOSED_SHELL('Lid',(#5));\n#6=MANIFOLD_SOLID_BREP('Lid',#4);\n#7=MANIFOLD_SOLID_BREP('',#4);\nENDSEC;\nEND-ISO-10303-21;\n"
)
