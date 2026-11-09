"""Auswahl, Diagramm und Export der Nahfeldschnitte (mit Ersatzdaten)."""

import io
import json
import zipfile

import numpy as np
import pytest

from conftest import make_fake_nearfield
from fg_gui import nearfield as nfm


@pytest.fixture
def nf():
    return make_fake_nearfield()


def test_cuts_and_quantities(nf):
    assert nfm.cut_names(nf) == ["horizontal", "vertical"]  # "incidence" ist kein Schnitt
    assert not nfm.is_map(nf["horizontal"]) and nfm.is_map(nf["vertical"])
    assert nfm.quantities(nf["vertical"])[:3] == ["absE2", "absH2", "Sy"]
    assert "material" not in nfm.quantities(nf["vertical"])


def test_values_pass_through_unchanged(nf):
    cut = nf["vertical"]
    assert nfm.select(cut, "absE2") is cut["absE2"]  # reell: dasselbe Array
    assert nfm.select(cut, "Sy", "phase") is cut["Sy"]
    assert np.array_equal(nfm.select(cut, "Ex", "re"), cut["Ex"].real)
    assert np.array_equal(nfm.select(cut, "Ex", "im"), cut["Ex"].imag)
    assert np.array_equal(nfm.select(cut, "Ex", "abs"), np.abs(cut["Ex"]))
    assert np.array_equal(nfm.select(cut, "Ex", "phase"), np.angle(cut["Ex"]))
    (n1, x), (n2, y) = nfm.axes(cut)
    assert (n1, n2) == ("x", "y")
    assert x is cut["axis1_um"] or np.array_equal(x, cut["axis1_um"])
    assert np.array_equal(y, cut["axis2_um"])
    with pytest.raises(ValueError):
        nfm.select(cut, "Ex", "nix")


def test_line_frame(nf):
    df = nfm.line_frame(nf["horizontal"], "absE2")
    assert list(df.columns) == ["x (µm)", "|E|²"]
    assert df["|E|²"].to_numpy().tolist() == nf["horizontal"]["absE2"].tolist()


def test_figures_for_map_line_and_2d(nf):
    for cut, q, part in (
        (nf["vertical"], "absE2", "abs"),
        (nf["vertical"], "Ex", "re"),
        (nf["horizontal"], "Ey", "im"),
    ):
        fig = nfm.figure(cut, q, part)
        assert fig.axes
        assert nfm.png_bytes(fig).startswith(b"\x89PNG")
    map_fig = nfm.figure(nf["vertical"], "Sy")
    assert map_fig.axes[0].collections  # pcolormesh
    nf2 = make_fake_nearfield(two_d=True)
    assert nfm.is_map(nf2["horizontal"])
    assert nfm.axes(nf2["horizontal"])[1][0] == "z"
    nfm.figure(nf2["horizontal"], "absE2", contours=False)


def test_export_zip_readable_like_fgsolve(nf):
    z = zipfile.ZipFile(io.BytesIO(nfm.export_zip(nf)))
    names = set(z.namelist())
    assert {"nearfield_vertical/meta.json", "nearfield_vertical/absE2.npy", "nearfield_vertical/material.npy"} <= names
    assert "nearfield_vertical/axis1_um.npy" not in names and not any("incidence" in n for n in names)
    arr = np.load(io.BytesIO(z.read("nearfield_vertical/Ex.npy")))
    assert np.array_equal(arr, nf["vertical"]["Ex"])
    assert json.loads(z.read("nearfield_horizontal/meta.json"))["cut"] == "horizontal"


def test_default_block():
    assert nfm.default_block("1D")["enabled"] is True and "nz" not in nfm.default_block("1D")
    assert nfm.default_block("2D")["nz"] == 120
