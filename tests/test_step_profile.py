"""Profillinie aus einem STEP-Flächenmodell (ohne Streamlit, ohne FourierGrating)."""

from pathlib import Path

import numpy as np
import pytest

from fg_gui import cad, step_profile
from fg_gui import structure as st

SURFACE = Path(__file__).parent / "data" / "cad" / "grating_line_surface.step"


def test_surface_model_is_recognised_and_rejected_as_solid():
    text = SURFACE.read_text()
    assert cad.is_surface_model(text)
    assert not cad.is_surface_model((Path(__file__).parent / "data" / "cad" / "line_grating.step").read_text())
    with pytest.raises(cad.CadFileError, match="offenes Flächenmodell"):
        cad.line_info(text, 0.3)


def test_nurbs_profile_from_surface_model_is_scaled_and_periodic():
    nurbs, info = step_profile.nurbs_profile(SURFACE.read_text(), 0.3)
    pts = np.array(nurbs["points_um"])
    assert info["pieces"] == 9 and nurbs["degree"] == 2
    assert len(nurbs["knots"]) == len(pts) + nurbs["degree"] + 1
    assert pts[0, 0] == 0.0 and pts[-1, 0] == pytest.approx(0.3)  # Breite = Periode
    assert pts[-1, 1] == pytest.approx(pts[0, 1])  # periodisch: gleiche Höhe an beiden Enden
    assert pts[:, 1].min() == pytest.approx(0.0, abs=1e-12)
    assert info["height_um"] == pytest.approx(0.05 * 0.3 / 0.25)  # Proportionen der Datei bleiben
    assert len(nurbs["weights"]) == len(pts) and min(nurbs["weights"]) > 0  # gerundete Ecken sind rational
    curve = st._nurbs(nurbs)  # dieselbe Kurve, wie das Schnittbild sie zeichnet
    assert curve[:, 1].max() == pytest.approx(info["height_um"], rel=1e-6)
    assert np.all(np.diff(curve[:, 0]) >= -1e-12)  # kein Überhang in diesem Profil: x wächst


def test_nurbs_profile_scales_with_the_period():
    a, ia = step_profile.nurbs_profile(SURFACE.read_text(), 0.25)
    b, ib = step_profile.nurbs_profile(SURFACE.read_text(), 0.5)
    assert ib["height_um"] == pytest.approx(2 * ia["height_um"])
    assert np.array(b["points_um"]) == pytest.approx(2 * np.array(a["points_um"]))


def test_nurbs_profile_rejects_bad_input():
    with pytest.raises(step_profile.StepProfileError, match="Periode"):
        step_profile.nurbs_profile(SURFACE.read_text(), 0.0)
    with pytest.raises(step_profile.StepProfileError, match="B-Spline"):
        step_profile.nurbs_profile("ISO-10303-21;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\n", 0.3)


def test_degree_elevation_keeps_the_curve():
    line = np.array([[0.0, 0.0, 0.0, 1.0], [1.0, 0.0, 2.0, 1.0]])
    q = step_profile._elevate(line, 3)
    assert len(q) == 4
    t = np.linspace(0, 1, 5)

    def bez(p):
        from math import comb

        n = len(p) - 1
        return sum(comb(n, i) * (1 - t) ** (n - i) * t**i * p[i][:, None] for i in range(n + 1)).T

    assert bez(q) == pytest.approx(bez(line))


def test_knot_insertion_decomposes_into_bezier_pieces():
    # quadratische B-Spline mit einem inneren Knoten -> zwei Bézier-Stücke, gleiche Kurve
    pts = np.array([[0, 0, 0, 1], [1, 2, 0, 1], [2, 0, 0, 1], [3, 2, 0, 1]], dtype=float)
    knots = [0, 0, 0, 1, 2, 2, 2]
    from scipy.interpolate import BSpline

    pieces = step_profile._bezier_pieces(2, list(knots), pts)
    assert len(pieces) == 2 and np.allclose(pieces[0][-1], pieces[1][0])
    ref = BSpline(np.array(knots, dtype=float), pts[:, :2], 2)
    first = pieces[0]
    t = 0.5
    p0 = (1 - t) ** 2 * first[0] + 2 * (1 - t) * t * first[1] + t**2 * first[2]
    assert p0[:2] == pytest.approx(ref(0.5))
