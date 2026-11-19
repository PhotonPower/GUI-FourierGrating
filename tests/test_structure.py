"""Schnittbild der Struktur: Geometrie, Maße und Zeichnen (ohne Löser)."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from fg_gui import config_form as cf
from fg_gui import structure as st

EXAMPLES = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples"


def cfg_1d(*layers):
    return {
        "dimension": "1D",
        "period_um": {"x": 1.0, "z": 0.0},
        "materials": {"air": {"n": 1.0}, "glass": {"n": 1.5}, "si": {"n": 3.5}},
        "superstrate": "air",
        "substrate": "glass",
        "layers": list(layers),
    }


def test_stack_heights_bottom_to_top():
    cfg = cfg_1d(
        {"type": "homogeneous", "thickness_um": 0.1, "material": "si"},
        {"type": "profile1d", "shape": "sinus", "depth_um": 0.3, "below": "si", "above": "air"},
        {"type": "cad"},
    )
    layers = st.stack(cfg)
    assert [(lay.y0, lay.y1) for lay in layers[:2]] == [(0.0, 0.1), (0.1, pytest.approx(0.4))]
    assert layers[2].nominal and layers[2].height == pytest.approx(0.2)  # Median der bekannten Dicken
    assert st.stack({}) == [] and st.period(cfg) == (1.0, 0.0) and st.period({"period_um": 0.5}) == (0.5, 0.0)


def test_profile_shapes():
    x = np.linspace(0, 1, 5)
    sinus = st.profile_height({"type": "profile1d", "shape": "sinus", "depth_um": 0.2}, x, 1.0)
    assert sinus[0] == pytest.approx(0.2) and sinus[2] == pytest.approx(
        0.0, abs=1e-12
    )  # Maximum bei x0, Minimum bei Λ/2
    tri = st.profile_height({"type": "profile1d", "shape": "triangle", "depth_um": 0.25, "apex_x_um": 0.5}, x, 1.0)
    assert list(tri) == pytest.approx([0.0, 0.125, 0.25, 0.125, 0.0])
    pts = st.profile_height({"type": "profile1d", "shape": "points", "x_um": [0.0, 0.5], "y_um": [0.0, 1.0]}, x, 1.0)
    assert list(pts) == pytest.approx([0.0, 0.5, 1.0, 0.5, 0.0])  # periodisch fortgesetzt
    assert st.profile_height({"type": "profile1d", "shape": "unbekannt"}, x, 1.0) is None
    egg = {"type": "profile2d", "shape": "egg_crate", "depth_um": 0.4, "_pz": 1.0}
    assert st.profile_height(egg, np.array([0.0]), 1.0, 0.0)[0] == pytest.approx(0.4)  # Maximum bei x0, z0
    assert st.profile_height({**egg, "_pz": 0.0}, np.array([0.0]), 1.0, 0.0) is None
    sx = st.profile_height({"type": "profile2d", "shape": "sinus_x", "depth_um": 0.4}, np.array([0.5]), 1.0)
    assert sx[0] == pytest.approx(0.0, abs=1e-12)


def test_inclusion_shapes_become_polygons():
    layer = {
        "background": "air",
        "regions": [
            {"material": "si", "circle": {"center_um": [0.25, 0.25], "radius_um": 0.1}},
            {"material": "si", "ellipse": {"center_um": [0.6, 0.6], "radii_um": [0.12, 0.06], "angle_deg": 30}},
            {"material": "glass", "polygon_um": [[0, 0], [0.1, 0], [0.1, 0.1]]},
            {"material": "si",
             "nurbs": {"degree": 1, "knots": [0, 0, 1, 2, 3, 3], "points_um": [[0, 0], [1, 0], [1, 1], [0, 1]]},
             "holes": [{"circle": {"center_um": [0.5, 0.5], "radius_um": 0.1}}]},
            {"material": "x", "unbekannt": 1},
        ],
    }  # fmt: skip
    inc = st.inclusions(layer)
    assert [m for m, _, _ in inc] == ["si", "si", "glass", "si"]  # unbekannte Form entfällt
    circle = inc[0][1]
    assert np.allclose(np.hypot(circle[:, 0] - 0.25, circle[:, 1] - 0.25), 0.1)
    assert len(inc[3][2]) == 1  # Loch
    rect = st.inclusions(
        {"inclusions": [{"material": "si", "rectangle_um": {"center": [0.5, 0.5], "size": [0.2, 0.4]}}]}
    )
    assert rect[0][1].min(axis=0) == pytest.approx([0.4, 0.3]) and rect[0][1].max(axis=0) == pytest.approx([0.6, 0.7])


def test_xy_runs_cut_a_square_pillar_at_z():
    layer = {"background": "air", "inclusions": [
        {"material": "si", "rectangle_um": {"center": [0.5, 0.5], "size": [0.4, 0.4]}}]}  # fmt: skip
    runs = st.xy_runs(layer, 1.0, 1.0, 0.5)
    assert [r[2] for r in runs] == ["air", "si", "air"]
    assert runs[1][0] == pytest.approx(0.3, abs=2e-3) and runs[1][1] == pytest.approx(0.7, abs=2e-3)
    assert [r[2] for r in st.xy_runs(layer, 1.0, 1.0, 0.1)] == ["air"]  # außerhalb des Pfeilers
    wrap = {"background": "air", "inclusions": [  # ragt über den Zellrand: erscheint links und rechts
        {"material": "si", "rectangle_um": {"center": [1.0, 0.5], "size": [0.2, 0.2]}}]}  # fmt: skip
    assert [r[2] for r in st.xy_runs(wrap, 1.0, 1.0, 0.5)] == ["si", "air", "si"]


def test_describe_rows():
    cfg = cfg_1d({"type": "lamellar1d", "thickness_um": 0.4, "breakpoints_um": [0, 0.5, 1], "materials": ["si", "air"]})
    rows = st.describe(cfg)
    assert rows == [
        {
            "Nr": 1,
            "Typ": "lamellar1d",
            "Dicke (µm)": 0.4,
            "y von (µm)": 0.0,
            "y bis (µm)": 0.4,
            "Materialien": "si, air",
        }
    ]


def test_figures_for_all_layer_types():
    cfg = cf.default_config()
    cfg["dimension"] = "2D"
    cfg["period_um"] = {"x": 1.0, "z": 0.8}
    mats = ["air", "glass", "bar"]
    cfg["layers"] = [
        cf.new_layer(k, mats, 1.0, 0.8)
        for k in ("homogeneous", "lamellar1d", "profile1d", "polygon2d", "contour2d", "profile2d")
    ]
    cfg["layers"].append({"type": "cad", "file": "x.step"})
    fig = st.figure_xy(cfg, z0=0.4, periods=2)
    assert fig.axes[0].get_title().startswith("Schnitt x–y, Schnitt bei z = 0.4")
    assert st.figure_xz(cfg, 3).axes and st.figure_xz(cfg, 4, periods=2).axes
    with pytest.raises(ValueError):
        st.figure_xz(cfg, 0)  # homogene Schicht: keine Draufsicht
    assert st.figure_xy({"period_um": {"x": 1}}).axes  # ohne Schichten: leerer Rahmen, kein Fehler


@pytest.mark.skipif(not EXAMPLES.is_dir(), reason="FourierGrating-Beispiele nicht gefunden")
def test_all_fourier_grating_examples_draw():
    for f in sorted(EXAMPLES.glob("*.json")):
        cfg = json.loads(f.read_text())
        if not cfg.get("period_um"):
            continue  # rotationssymmetrisch o. Ä.: keine Periode
        z0 = 0.5 * (cfg["period_um"].get("z") or 0.0)
        assert st.figure_xy(cfg, z0=z0).axes, f.name
        for lay in st.stack(cfg):
            if lay.type in st.TWO_D_TYPES:
                assert st.figure_xz(cfg, lay.index).axes, f.name


def test_nan_free_geometry():
    x = np.linspace(0, 1, 50)
    assert not np.isnan(st.profile_height({"type": "profile1d", "shape": "sinus", "depth_um": 0.1}, x, 1.0)).any()
    assert math.isfinite(st.stack(cfg_1d({"type": "homogeneous", "thickness_um": 0.1, "material": "si"}))[0].y1)


# ---------------------------------------------------------------- CAD-Schicht mit Prüfbericht
CAD_REPORT = {
    "bands": [
        {"y0_um": 0.0, "y1_um": 0.2, "kind": "sectioned", "area_fractions": {"air": 0.77, "si": 0.23}},
        {"y0_um": 0.2, "y1_um": 0.26, "kind": "extrusion", "area_fractions": {"air": 0.85, "sio2": 0.15}},
    ],
    "ok": True,
}


def cad_cfg():
    cfg = cfg_1d({"type": "homogeneous", "thickness_um": 0.1, "material": "si"}, {"type": "cad", "file": "x.step"})
    cfg["materials"]["sio2"] = {"n": 1.45}
    cfg["layers"][1]["bodies"] = [{"name": "Pillar", "material": "si"}, {"name": "Lid", "material": "sio2"}]
    return cfg


def test_cad_layer_without_report_is_nominal():
    lay = st.stack(cad_cfg())[1]
    assert lay.nominal and lay.bands == [] and lay.height == pytest.approx(0.1)


def test_cad_layer_takes_height_and_bands_from_report():
    lays = st.stack(cad_cfg(), CAD_REPORT)
    cad = lays[1]
    assert not cad.nominal and cad.y0 == pytest.approx(0.1) and cad.y1 == pytest.approx(0.36)
    assert [(b["y0_um"], b["y1_um"]) for b in cad.bands] == [
        (pytest.approx(0.1), pytest.approx(0.3)),
        (pytest.approx(0.3), pytest.approx(0.36)),
    ]
    # Bänder in beliebiger Reihenfolge und mit Höhe 0 werden geordnet bzw. verworfen
    messy = {"bands": [CAD_REPORT["bands"][1], CAD_REPORT["bands"][0], {"y0_um": 1.0, "y1_um": 1.0}, {"kind": "x"}]}
    assert len(st.cad_bands(messy)) == 2 and st.cad_bands(messy)[0]["y0_um"] == 0.0 and st.cad_bands(None) == []


def test_cad_report_only_applies_to_first_cad_layer_and_not_to_given_heights():
    cfg = cad_cfg()
    cfg["layers"].append({"type": "cad", "file": "y.step"})
    cfg["layers"].append({"type": "cad", "thickness_um": 0.5, "file": "z.step"})
    lays = st.stack(cfg, CAD_REPORT)
    assert lays[1].bands and not lays[2].bands and lays[2].nominal
    assert not lays[3].bands and lays[3].height == pytest.approx(0.5)


def test_describe_lists_bands_and_body_materials():
    rows = st.describe(cad_cfg(), CAD_REPORT)
    assert [r["Nr"] for r in rows] == [1, 2, "2.1", "2.2"]
    assert rows[1]["Materialien"] == "si, sio2" and rows[2]["Typ"] == "CAD-Band (sectioned)"
    assert rows[2]["Dicke (µm)"] == pytest.approx(0.2) and "si 23.0%" in rows[2]["Materialien"]
    assert st.describe(cad_cfg())[1]["Dicke (µm)"] is None  # ohne Bericht: Höhe unbekannt


def test_figure_with_cad_bands_draws_labels():
    fig = st.figure_xy(cad_cfg(), periods=2, cad_report=CAD_REPORT)
    texts = [t.get_text() for t in fig.axes[0].texts]
    assert sum("sectioned" in t for t in texts) == 1 and sum("extrusion" in t for t in texts) == 1  # nur 1. Periode
    assert any("Gesamtdicke der Schichten 0.36" in fig.axes[0].get_title() for _ in [0])
    assert any("angenommen" in t.get_text() for t in st.figure_xy(cad_cfg()).axes[0].texts)  # ohne Bericht
