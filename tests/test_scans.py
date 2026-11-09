"""Kurven- und Exportdaten der Scanergebnisse."""

import numpy as np
import pandas as pd
import pytest

from conftest import FakeScan
from fg_gui import scans


@pytest.fixture
def df():
    return scans.scan_frame(FakeScan())


def test_frame_columns_identical_to_scan_columns():
    scan = FakeScan()
    frame = scans.scan_frame(scan)
    assert list(frame.columns) == list(scan.columns)
    for k, v in scan.columns.items():
        assert np.array_equal(frame[k].to_numpy(), v)


def test_axes_and_fixed(df):
    assert scans.varying_axes(df) == ["lambda_um", "phi_deg"]
    assert scans.fixed_choices(df, "lambda_um") == {"phi_deg": [0.0, 10.0]}
    assert scans.order_labels(df) == ["R(-1,0)", "R(0,0)", "T(0,0)"]


def test_curves_values_pass_through(df):
    c = scans.curves(df, "lambda_um", ["R(0,0)", "T(0,0)"], fixed={"phi_deg": 10.0})
    assert list(c.index) == [0.5, 0.6]
    assert list(c.columns) == ["R(0,0)", "T(0,0)"]
    assert c["R(0,0)"].tolist() == pytest.approx([0.1 + 0.05 + 0.01, 0.1 + 0.06 + 0.01])
    assert c["T(0,0)"].tolist() == pytest.approx([1 - 0.16, 1 - 0.17])


def test_nonpropagating_order_counts_as_zero(df):
    c = scans.curves(df, "phi_deg", ["R(-1,0)"], fixed={"lambda_um": 0.5})
    assert c["R(-1,0)"].tolist() == [0.0, 0.01]


def test_sums_and_quantity(df):
    c = scans.curves(df, "phi_deg", [], quantity="eff_p", fixed={"lambda_um": 0.5}, sums=("ΣR", "ΣT"))
    assert c["ΣR"].tolist() == pytest.approx([0.15, 0.15 + 0.01 + 0.01])
    with pytest.raises(ValueError):
        scans.curves(df, "phi_deg", [], quantity="nix")


def test_compare_prefixes_and_unions_x(df):
    a = scans.curves(df, "lambda_um", ["R(0,0)"], fixed={"phi_deg": 0.0})
    b = pd.DataFrame({"R(0,0)": [0.3]}, index=pd.Index([0.55], name="lambda_um"))
    both = scans.compare({"A": a, "B": b})
    assert list(both.columns) == ["A: R(0,0)", "B: R(0,0)"]
    assert list(both.index) == [0.5, 0.55, 0.6]


def test_csv_like_efficiencies(df):
    out = scans.csv_frame(df)
    assert "sweep_value" not in out and "amp_s" not in out
    assert {"amp_s_re", "amp_s_im", "amp_p_re", "amp_p_im", "efficiency"} <= set(out.columns)
    with_sweep = scans.csv_frame(df, "/layers/0/thickness_um")
    assert list(with_sweep.columns[:2]) == ["sweep_parameter", "sweep_value"]
    text = scans.to_csv(df).decode()
    assert text.splitlines()[0].startswith("lambda_um,phi_deg")
    assert len(text.splitlines()) == len(df) + 1
