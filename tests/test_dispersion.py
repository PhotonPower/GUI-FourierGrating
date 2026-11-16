"""Dispersive Materialien (G8): Erkennen, Tabellen, CSV, Dateizugriff, Roundtrip, Ausgaben (ohne Löser)."""

import copy
import json

import numpy as np
import pytest

from fg_gui import config_form as cf
from fg_gui import dispersion as dp

SIO2 = {
    "sellmeier": {
        "A": 1.0,
        "B": [0.6961663, 0.4079426, 0.8974794],
        "C_um2": [0.00467914826, 0.0135120631, 97.9340025],
        "range_um": [0.21, 6.7],
    }
}
AG = {"drude_lorentz": {"eps_inf": 1.0, "omega_p_eV": 9.01, "f0": 0.845, "gamma0_eV": 0.048,
                        "oscillators": [{"f": 0.065, "omega_eV": 0.816, "gamma_eV": 3.886}]}}  # fmt: skip
CFG = {
    "dimension": "1D",
    "incidence": {"lambda_um": {"from": 0.4, "to": 1.0, "steps": 31}, "phi_deg": 10},
    "materials": {
        "air": {"n": 1.0},
        "sio2": {"n": SIO2},
        "ag": {"eps": AG},
        "au": {"n": {"table": {"data": [[0.4, 1.5, 1.9], [0.8, 0.2, 5.0]], "interpolation": "cubic"}}},
        "tio2": {"n": {"cauchy": {"A": 2.4, "B_um2": 0.03}}},
        "lnb": {"eps_principal": [SIO2, 4.98, {"cauchy": {"A": 2.1}}], "euler_deg": [10, 30, 0]},
    },
}


def test_model_detection_and_kinds():
    assert dp.model_name(SIO2) == "sellmeier" and dp.model_name(1.5) is None and dp.model_name([1, 2]) is None
    assert dp.dispersive_materials(CFG) == ["sio2", "ag", "au", "tio2", "lnb"]
    assert not dp.is_dispersive({"n": 1.5}) and not dp.is_dispersive({"eps_tensor": [[1]]})
    kinds = {n: cf.material_kind(m) for n, m in CFG["materials"].items()}
    assert kinds == {"air": "n", "sio2": "sellmeier", "ag": "drude_lorentz", "au": "table_n", "tio2": "cauchy",
                     "lnb": "eps_principal"}  # fmt: skip
    assert cf.material_kind({"eps": {"table": {"data": []}}}) == "table_eps"


def test_defaults_are_recognised_as_their_kind():
    for kind in cf.DISPERSIVE_KINDS:
        assert cf.material_kind(cf.material_defaults(kind)) == kind


def test_lambda_ranges():
    assert dp.lambda_range(CFG) == (0.4, 1.0) and dp.first_lambda(CFG) == 0.4
    assert dp.lambda_range({"incidence": {"lambda_um": [0.7, 0.5]}}) == (0.5, 0.7)
    assert dp.first_lambda({"incidence": {"lambda_um": [0.7, 0.5]}}) == 0.7
    assert dp.lambda_range({"incidence": {"lambda_um": 0.63}}) == (0.63, 0.63)
    assert dp.lambda_range({}) is None


def test_table_rows_roundtrip_keeps_originals():
    table = {"data": [[0.4, 1, 0.5], [0.8, 2, 0]]}
    orig = copy.deepcopy(table)
    dp.table_apply(table, dp.table_rows(table))
    assert table == orig
    two = {"data": [[0.4, 1.5], [0.8, 1.6]]}
    dp.table_apply(two, dp.table_rows(two))  # fehlender Verlust bleibt fehlend
    assert two == {"data": [[0.4, 1.5], [0.8, 1.6]]}
    rows = dp.table_rows(table)
    rows[1]["re"] = 2.5
    rows.append({"x": 1.2, "re": 3.0, "im": None})
    rows.append({"x": None, "re": 9.0, "im": None})  # unvollständig: entfällt
    dp.table_apply(table, rows)
    assert table["data"] == [[0.4, 1, 0.5], [0.8, 2.5, 0], [1.2, 3.0, 0.0]]


def test_parse_csv_variants():
    text = "# Quelle\nlambda, n, k\n0.4, 1.5, 0.1\n0.5;1.4;0.2\n0.6 1.3 0.3\n\n"
    assert dp.parse_csv(text) == [[0.4, 1.5, 0.1], [0.5, 1.4, 0.2], [0.6, 1.3, 0.3]]
    assert dp.parse_csv("0.4 1.5\n0.5 1.6") == [[0.4, 1.5], [0.5, 1.6]]
    assert dp.parse_csv("﻿1e-1, 2\n2.5E0, 3") == [[0.1, 2.0], [2.5, 3.0]]
    for bad, msg in [("0.4 1.5\n0.5", "Zeile 2"), ("0.4 1.5 0 7", "Zeile 1"), ("0.4 1.5\n0.5 x", "Zeile 2"),
                     ("0.4 1.5", "zwei Zeilen"), ("0.4 1.5\n0.5 1.6 0.1", "Zeile 2")]:  # fmt: skip
        with pytest.raises(dp.DispersionError, match=msg):
            dp.parse_csv(bad)


def test_table_material_units():
    assert dp.table_material("table_n", [[1, 2]], "um") == {"n": {"table": {"data": [[1, 2]]}}}
    assert dp.table_material("table_eps", [[1, 2]], "eV") == {"eps": {"table": {"data": [[1, 2]], "unit": "eV"}}}


def test_inline_files_and_guard(tmp_path):
    root = tmp_path / "materials"
    root.mkdir()
    (root / "au.csv").write_text("# Johnson\n0.4, 1.5, 1.9\n0.8, 0.2, 5.0\n")
    cfg = {"materials": {"au": {"n": {"table": {"file": "au.csv", "unit": "um", "interpolation": "cubic"}}}}}
    orig = copy.deepcopy(cfg)
    assert dp.has_files(cfg)
    out = dp.inline_files(cfg, bases=[root], roots=[root])
    assert cfg == orig  # Kopie
    assert out["materials"]["au"]["n"]["table"] == {
        "unit": "um", "interpolation": "cubic", "data": [[0.4, 1.5, 1.9], [0.8, 0.2, 5.0]]
    }  # fmt: skip
    assert not dp.has_files(out)
    # außerhalb der erlaubten Verzeichnisse, fehlend, kaputt
    secret = tmp_path / "secret.csv"
    secret.write_text("1 2\n2 3\n")
    for name, msg in [(str(secret), "außerhalb"), ("../secret.csv", "außerhalb"), ("fehlt.csv", "nicht gefunden")]:
        c = {"materials": {"m": {"eps": {"table": {"file": name}}}}}
        with pytest.raises(dp.DispersionError, match=msg):
            dp.inline_files(c, bases=[root], roots=[root])
    (root / "kaputt.csv").write_text("1 2\n3\n")
    with pytest.raises(dp.DispersionError, match="kaputt.csv"):
        dp.inline_files({"materials": {"m": {"n": {"table": {"file": "kaputt.csv"}}}}}, [root], [root])


def test_symlink_out_of_root_is_refused(tmp_path):
    root = tmp_path / "materials"
    root.mkdir()
    outside = tmp_path / "geheim.csv"
    outside.write_text("1 2\n2 3\n")
    (root / "link.csv").symlink_to(outside)
    with pytest.raises(dp.DispersionError, match="außerhalb"):
        dp.inline_files({"materials": {"m": {"n": {"table": {"file": "link.csv"}}}}}, [root], [root])


def test_library_files(tmp_path):
    assert dp.library_files(None) == [] and dp.library_files(tmp_path / "fehlt") == []
    for n in ("b.csv", "a.yml", "c.txt", "d.YAML"):
        (tmp_path / n).write_text("x")
    assert [p.name for p in dp.library_files(tmp_path)] == ["a.yml", "b.csv", "d.YAML"]


def test_eps_frame_and_materials_frame_pass_values_through():
    calls = []

    def eps_fn(cfg, name, lams):
        calls.append(name)
        lam = np.asarray(lams)
        if name == "lnb":
            return np.stack([lam + 1j, lam + 2j, lam + 3j], axis=-1)
        return lam * 2 + 0.5j * lam

    lams = [0.4, 0.5, 0.6]
    df = dp.materials_frame(CFG, lams, eps_fn)
    assert calls == dp.dispersive_materials(CFG)
    assert list(df.columns) == ["lambda_um", "material", "component", "eps_re", "eps_im"]
    ag = df[df.material == "ag"]
    assert list(ag.lambda_um) == lams and list(ag.eps_re) == [0.8, 1.0, 1.2] and (ag.component == "iso").all()
    lnb = df[df.material == "lnb"]
    assert sorted(set(lnb.component)) == ["1", "2", "3"] and len(lnb) == 9
    assert list(lnb[lnb.component == "3"].eps_im) == [3.0, 3.0, 3.0]


def test_diagnostics_frame_accepts_complex_and_stored_pairs():
    live = {"materials": [{"name": "ag", "component": 0, "n": 0.13 + 2.77j, "eps": -7.6 + 0.7j}]}
    stored = json.loads(json.dumps({"materials": [{"name": "ag", "component": 0, "n": [0.13, 2.77],
                                                    "eps": [-7.6, 0.7]}]}))  # fmt: skip
    a, b = dp.diagnostics_frame(live, 0.5), dp.diagnostics_frame(stored, 0.5)
    assert a.equals(b)
    assert list(a.columns) == dp.MATERIALS_CSV_COLUMNS and a.iloc[0].component == "iso"
    assert dp.diagnostics_frame({}, 0.5).empty and dp.diagnostics_frame(None).empty
    assert (
        dp.diagnostics_frame({"materials": [{"name": "l", "component": 2, "n": 1, "eps": 1}]}).iloc[0].component == "2"
    )


def test_locate_error_with_json_pointer():
    cfg = {"layers": [{"type": "homogeneous"}], "materials": {"au": {}}}
    msg = "/materials/au/n/table: lambda 0.25 um outside [0.3, 1.9] um"
    assert cf.locate_error(msg, cfg) == ("materials", None) and cf.error_material(msg) == "au"
    assert cf.locate_error("x.cpp:3 /layers/0/thickness_um: negative", cfg) == ("layers", 0)
    assert cf.error_material("unknown material 'x'") is None
    assert cf.error_material("/materials/a~1b/n: x") == "a/b"


def test_optimization_pointers_exclude_table_lambda_column():
    from fg_gui import optimize

    ptrs = dict(optimize.numeric_pointers(CFG))
    assert "/materials/sio2/n/sellmeier/B/0" in ptrs and "/materials/au/n/table/data/0/1" in ptrs
    assert "/materials/au/n/table/data/0/0" not in ptrs and "/materials/au/n/table/data/1/0" not in ptrs
