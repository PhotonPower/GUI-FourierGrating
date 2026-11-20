"""Abnahme mit dem echten Löser (Server): nur mit installiertem fouriergrating, sonst übersprungen."""

import json
from pathlib import Path

import pytest

from conftest import EXAMPLE
from fg_gui import results, solver


@pytest.mark.solver
def test_lamellar_energy_conservation():
    info = solver.info()
    assert info.available and info.version_ok, info
    res = solver.solve(EXAMPLE)  # V3-Lamelle, verlustfrei: ΣR + ΣT = 1
    tot = results.totals(res)
    assert tot["ΣR"] + tot["ΣT"] == pytest.approx(1.0, abs=1e-10)
    assert not results.orders_frame(res).empty


@pytest.mark.solver
def test_editor_template_solves_and_error_is_located():
    from fg_gui import config_form, solver

    cfg = config_form.default_config()
    assert solver.solve(cfg).transmitted is not None
    cfg["layers"][0]["materials"][1] = "zzz"
    with pytest.raises(Exception) as e:
        solver.solve(cfg)
    assert config_form.locate_error(str(e.value), cfg) == ("layers", 0)


@pytest.mark.solver
def test_scan_columns_and_curves_with_real_solver():
    import copy

    import numpy as np

    from fg_gui import scans

    cfg = copy.deepcopy(EXAMPLE)
    cfg["incidence"]["lambda_um"] = {"from": 0.5, "to": 0.7, "steps": 3}
    scan = solver.solve_scan(cfg)
    frame = scans.scan_frame(scan)
    assert list(frame.columns) == list(scan.columns)
    assert scans.varying_axes(frame) == ["lambda_um"]
    curve = scans.curves(frame, "lambda_um", ["R(0,0)", "T(0,0)"])
    assert len(curve) == 3
    # verlustfrei: ΣR + ΣT = 1 an jedem Punkt
    sums = scans.curves(frame, "lambda_um", [], sums=("ΣR", "ΣT"))
    assert np.allclose(sums["ΣR"] + sums["ΣT"], 1.0, atol=1e-10)
    assert scans.to_csv(frame, scan.sweep_parameter).startswith(b"lambda_um")


@pytest.mark.solver
def test_sweep_example():
    from pathlib import Path

    from fg_gui import config_io, scans

    path = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples" / "sweep_lamellar_depth.json"
    if not path.is_file():
        pytest.skip("Beispiel nicht vorhanden")
    scan = solver.solve_scan(config_io.parse(path.read_bytes()))
    frame = scans.scan_frame(scan)
    assert "sweep_value" in scans.varying_axes(frame)
    assert scans.csv_frame(frame, scan.sweep_parameter).columns[0] == "sweep_parameter"


@pytest.mark.solver
@pytest.mark.parametrize("name", ["nearfield_lamellar_1d.json", "nearfield_pillars_2d.json"])
def test_nearfield_examples(name):
    import io
    import zipfile
    from pathlib import Path

    import numpy as np

    from fg_gui import config_io
    from fg_gui import nearfield as nfm

    path = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples" / name
    if not path.is_file():
        pytest.skip("Beispiel nicht vorhanden")
    nf = solver.near_field(config_io.parse(path.read_bytes()))
    cuts = nfm.cut_names(nf)
    assert cuts == ["horizontal", "vertical"]
    for c in cuts:
        cut = nf[c]
        q = nfm.quantities(cut)
        assert "absE2" in q and "Ex" in q
        # Felder unverändert: |E|² aus der Auswahl ist exakt das Array von FourierGrating
        assert nfm.select(cut, "absE2") is cut["absE2"]
        assert nfm.png_bytes(nfm.figure(cut, "absE2")).startswith(b"\x89PNG")
    z = zipfile.ZipFile(io.BytesIO(nfm.export_zip(nf)))
    assert np.array_equal(np.load(io.BytesIO(z.read("nearfield_vertical/absE2.npy"))), nf["vertical"]["absE2"])


@pytest.mark.solver
def test_export_readable_by_plot_nearfield(tmp_path):
    """Der ZIP-Export lässt sich mit scripts/plot_nearfield.py (FourierGrating) lesen und zeichnen."""
    import importlib.util
    import io
    import zipfile
    from pathlib import Path

    import numpy as np

    from fg_gui import config_io
    from fg_gui import nearfield as nfm

    root = Path(__file__).resolve().parents[2] / "FourierGrating"
    script, example = root / "scripts" / "plot_nearfield.py", root / "examples" / "nearfield_lamellar_1d.json"
    if not (script.is_file() and example.is_file()):
        pytest.skip("FourierGrating-Quellen nicht vorhanden")
    spec = importlib.util.spec_from_file_location("plot_nearfield", script)
    pn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pn)
    nf = solver.near_field(config_io.parse(example.read_bytes()))
    zipfile.ZipFile(io.BytesIO(nfm.export_zip(nf))).extractall(tmp_path)
    meta, data = pn.load_cut(str(tmp_path / "nearfield_vertical"))
    assert np.array_equal(data["absE2"], nf["vertical"]["absE2"])
    assert np.array_equal(data["material"], nf["vertical"]["material"])
    assert np.allclose(meta["axes"]["axis1"]["values_um"], nf["vertical"]["axis1_um"])
    for part in ("abs", "re"):
        assert np.array_equal(pn.select_part(data["Ex"], part), nfm.select(nf["vertical"], "Ex", part))


@pytest.mark.solver
def test_runs_survive_restart_with_real_solver(tmp_path):
    import numpy as np

    from fg_gui import results
    from fg_gui.jobs import DONE, JobManager
    from fg_gui.store import RunStore

    jm = JobManager(workers=1, store=RunStore(tmp_path / "runs"))
    job = jm.submit("echt", solver.solve, EXAMPLE, kind="solve", config=EXAMPLE)
    job.future.result()
    before = results.totals(job.result())
    jm.shutdown()
    jm2 = JobManager(workers=1, store=RunStore(tmp_path / "runs"))
    again = jm2.get(job.id)
    assert again.status == DONE and jm2.config(job.id) == EXAMPLE
    after = results.totals(again.result())
    assert after == before and np.isclose(after["ΣR"] + after["ΣT"], 1.0, atol=1e-10)
    jm2.shutdown()


def _cad_example():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples" / "cad_pillar_array.json"
    if not path.is_file() or not solver.info().cad_available:
        pytest.skip("CAD-Beispiel oder CAD-Slicer nicht vorhanden")
    cfg = json.loads(path.read_text())
    cfg["layers"][0]["file"] = str(path.parent / cfg["layers"][0]["file"])
    return cfg


@pytest.mark.solver
def test_cad_check_with_real_slicer():
    from fg_gui import cad

    cfg = _cad_example()
    out = solver.cad_check(cfg, extra_heights=(0.05,))
    assert out["report"]["ok"] and not out["report"]["errors"]
    assert [b["kind"] for b in out["report"]["bands"]] == ["sectioned", "extrusion"]
    assert len(out["previews"]) == 3 and all(p["svg"].startswith("<svg") for p in out["previews"])
    assert cad.band_heights(out["report"]) == [p["y_um"] for p in out["previews"][:2]]
    # Körper ohne Material: genau der Prüfcode von FourierGrating erscheint in den Befunden
    cfg["layers"][0]["bodies"] = [{"name": "Pillar", "material": "si"}]
    rows = cad.findings_rows(solver.cad_check(cfg)["report"])
    assert [r["Code"] for r in rows] == ["BODY_UNASSIGNED"] and rows[0]["Stufe"] == "Fehler"


@pytest.mark.solver
def test_cad_example_runs_through_job_and_survives_restart(tmp_path):
    from fg_gui import results
    from fg_gui.cad import resolve_files
    from fg_gui.jobs import DONE, JobManager
    from fg_gui.store import RunStore

    cfg = _cad_example()
    root = tmp_path  # Dateischutz: Beispielordner als erlaubtes Verzeichnis
    examples = __import__("pathlib").Path(cfg["layers"][0]["file"]).parent.parent
    prepared = resolve_files(cfg, [examples], [examples])
    jm = JobManager(workers=1, store=RunStore(root / "runs"))
    job = jm.submit("cad", solver.solve, prepared, kind="solve", config=prepared)
    job.future.result()
    assert job.status == DONE
    tot = results.totals(job.result())
    assert 0.0 < tot["ΣR"] + tot["ΣT"] <= 1.0 + 1e-6  # verlustbehaftetes Silizium
    jm.shutdown()
    again = JobManager(workers=1, store=RunStore(root / "runs")).get(job.id)
    assert results.totals(again.result()) == tot


@pytest.mark.solver
def test_littrow_optimization_reproduces_fourier_grating_example():
    """Abnahme G6: gleiche Konfiguration, Start, Grenzen und Ordnung wie examples/python/optimize_littrow.py."""
    import numpy as np
    from scipy.optimize import minimize

    from fg_gui import optimize as opt

    preset = opt.littrow_preset()
    cfg, spec = preset["config"], preset["spec"]
    pointers = [p.pointer for p in spec.params]
    bounds = [(p.lower, p.upper) for p in spec.params]

    # 1) das Beispielskript, unverändert in seiner Logik
    sim = solver.simulation(cfg)
    objective = {("R", -1, 0): 1.0}

    def fun(x):
        for ptr, v in zip(pointers, x, strict=True):
            sim.set_parameter(ptr, float(v))
        value, grad = sim.value_and_grad(objective, pointers)
        return -value, -grad

    ref = minimize(fun, x0=[0.2, 0.3], jac=True, method="L-BFGS-B", bounds=bounds, options={"ftol": 1e-12})

    # 2) die GUI-Optimierung
    res = opt.run(solver.simulation(cfg), spec)
    assert res["value"] == pytest.approx(-ref.fun, abs=1e-9)
    assert [res["x"][p] for p in pointers] == pytest.approx(list(ref.x), abs=1e-6)

    # 3) Rasterscan (gröber als im Beispiel): Optimum >= bester Rasterwert - 1e-3
    grid_sim = solver.simulation(cfg)
    best = 0.0
    for h in np.linspace(*bounds[0], 14):
        for w in np.linspace(*bounds[1], 16):
            grid_sim.set_parameter(pointers[0], float(h))
            grid_sim.set_parameter(pointers[1], float(w))
            best = max(best, grid_sim.solve().efficiency("R", -1))
    assert res["value"] >= best - 1e-3
    assert 0.0 < res["value"] <= 1.0 and res["nfev"] >= 3

    # 4) das Ergebnis lässt sich speichern und nach einem Neustart laden
    import tempfile
    from pathlib import Path

    from fg_gui.store import load_result, save_result

    with tempfile.TemporaryDirectory() as d:
        save_result("optimize", res, Path(d))
        assert load_result("optimize", Path(d))["x"] == res["x"]


# ---------------------------------------------------------------- G8: dispersive Materialien (FourierGrating M22)
DISPERSIVE_EXAMPLE = Path(__file__).parent / "data" / "dispersive_metal_grating.json"  # Kopie aus FourierGrating


@pytest.mark.solver
def test_dispersive_example_solves_and_matches_preview_values():
    import copy

    import numpy as np

    from fg_gui import dispersion

    cfg = json.loads(DISPERSIVE_EXAMPLE.read_text())
    assert dispersion.dispersive_materials(cfg) == ["ag"]
    one = copy.deepcopy(cfg)
    one["incidence"]["lambda_um"] = 0.5
    res = solver.solve(one)
    diag = dispersion.diagnostics_frame(res.diagnostics, 0.5)
    eps = solver.material_eps(cfg, "ag", [0.5])  # Vorschau-Weg
    assert diag.iloc[0].eps_re == pytest.approx(eps[0].real, rel=1e-12)
    assert diag.iloc[0].eps_im == pytest.approx(eps[0].imag, rel=1e-12)
    frame = dispersion.eps_frame([0.5], eps)
    assert np.allclose(frame.eps_re, eps.real)
    scan = solver.solve_scan(cfg)
    assert len(set(scan.columns["lambda_um"])) == 31


@pytest.mark.solver
def test_table_file_and_inline_data_give_identical_results(tmp_path):
    import copy

    import numpy as np

    from fg_gui import dispersion

    cfg = json.loads(DISPERSIVE_EXAMPLE.read_text())
    cfg["incidence"]["lambda_um"] = {"from": 0.45, "to": 0.9, "steps": 4}
    rows = [[0.4 + 0.1 * i, -4.0 - 3.0 * i, 0.2 + 0.05 * i] for i in range(7)]
    (tmp_path / "ag.csv").write_text("# test\n" + "\n".join(", ".join(repr(v) for v in r) for r in rows))
    with_file = copy.deepcopy(cfg)
    with_file["materials"]["ag"] = {"eps": {"table": {"file": str(tmp_path / "ag.csv"), "interpolation": "cubic"}}}
    inline = dispersion.inline_files(with_file, bases=[tmp_path], roots=[tmp_path])
    assert "file" not in inline["materials"]["ag"]["eps"]["table"]
    a, b = solver.solve_scan(with_file), solver.solve_scan(inline)
    for k in a.columns:
        assert np.array_equal(a.columns[k], b.columns[k]), k


@pytest.mark.solver
def test_range_error_carries_pointer_to_the_material():
    from fg_gui import config_form

    cfg = json.loads(DISPERSIVE_EXAMPLE.read_text())
    cfg["incidence"]["lambda_um"] = 0.25
    cfg["materials"]["ag"] = {"eps": {"table": {"data": [[0.3, -2.0, 0.1], [0.9, -20.0, 0.5]]}}}
    with pytest.raises(Exception) as e:
        solver.solve(cfg)
    assert "/materials/ag/" in str(e.value)
    assert config_form.error_material(str(e.value)) == "ag"
    assert config_form.locate_error(str(e.value), cfg) == ("materials", None)


@pytest.mark.solver
def test_import_refractiveindex_yaml_gives_a_working_material():
    pytest.importorskip("yaml")
    text = """
REFERENCES: test
DATA:
  - type: tabulated nk
    data: |
        0.30 1.50 0.10
        0.60 1.60 0.20
        0.90 1.70 0.30
"""
    mat = solver.from_refractiveindex(text)
    assert mat == {"n": {"table": {"data": [[0.3, 1.5, 0.1], [0.6, 1.6, 0.2], [0.9, 1.7, 0.3]]}}}
    cfg = json.loads(DISPERSIVE_EXAMPLE.read_text())
    cfg["incidence"]["lambda_um"] = 0.6
    cfg["materials"]["ag"] = mat
    assert solver.solve(cfg).transmitted is not None


# ---------------------------------------------------------------- gerechnete Linie (Nahfeld ny = 1, nz = 1)
@pytest.mark.solver
def test_computed_nearfield_line_equals_row_of_the_map():
    import copy

    import numpy as np

    from fg_gui import config_form, nearfield

    cfg = config_form.default_config()
    cfg["nearfield"] = nearfield.default_block("1D")
    cfg["nearfield"].update({"y_range_um": [-0.1, 0.5], "ny": 7, "nx": 40, "periods": 1, "vertical_z_um": 0.0})
    full = solver.near_field(cfg)["vertical"]
    y = float(full["axis2_um"][3])  # ein Gitterpunkt der Karte
    run_cfg = copy.deepcopy(cfg)
    run_cfg["nearfield"] = nearfield.line_block(cfg["nearfield"], y)
    run = solver.near_field(run_cfg)
    assert nearfield.is_line_run(run) or run["vertical"]["axis2_um"].size == 1
    row = run["vertical"]
    assert row["axis2_um"].size == 1 and float(row["axis2_um"][0]) == pytest.approx(y)
    for q in ("Ex", "Ey", "absE2"):
        np.testing.assert_allclose(row[q][0], full[q][3], rtol=1e-9, atol=1e-12)
    line = nearfield.squeeze_line(row)
    assert not nearfield.is_map(line) and len(line["axis1_um"]) == 40


@pytest.mark.solver
def test_computed_nearfield_line_in_2d_matches_map_row_and_is_a_line_run():
    import copy

    import numpy as np

    from fg_gui import nearfield

    cfg = json.loads(
        (Path(__file__).parent / "data" / "nearfield_pillars_2d.json").read_text()
    )  # Kopie aus FourierGrating
    full = solver.near_field(cfg)
    i = len(full["vertical"]["axis2_um"]) // 2
    run_cfg = copy.deepcopy(cfg)
    run_cfg["nearfield"] = nearfield.line_block(cfg["nearfield"], float(full["vertical"]["axis2_um"][i]))
    run = solver.near_field(run_cfg)
    assert nearfield.is_line_run(run) and nearfield.visible_cuts(run) == ["vertical"]
    assert run["vertical"]["Ex"].shape == (1, cfg["nearfield"]["nx"])
    np.testing.assert_allclose(run["vertical"]["Ex"][0], full["vertical"]["Ex"][i], rtol=1e-9, atol=1e-12)


# ---------------------------------------------------------------- CAD in 1D (FourierGrating M23, ab 0.20.0)
EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples"


def _line_grating_cfg() -> dict:
    data = Path(__file__).parent / "data"
    cfg = json.loads((data / "cad_line_grating_1d.json").read_text())  # Kopie aus FourierGrating
    cfg["layers"][0]["file"] = str(data / "cad" / "line_grating.step")
    return cfg


@pytest.mark.solver
def test_cad_check_1d_reports_profile_and_length_fractions():
    from fg_gui import cad, structure

    cfg = _line_grating_cfg()
    out = solver.cad_check(cfg, extra_heights=(0.05,))
    report = out["report"]
    assert report["ok"] and report["dimension"] == "1D" and report["cell_origin_um"] == [0.0]
    assert report["z_cut_um"] == pytest.approx(-0.15)
    assert {b["kind"] for b in report["bands"]} == {"sectioned1d"} and cad.is_1d(report)
    assert len(out["previews"]) == 1 and out["previews"][0]["y_um"] is None and out["previews"][0]["svg"]
    assert "Längenanteile" in cad.bands_rows(report)[0]
    lay = structure.stack(cfg, report)[0]  # Bänder und Höhe 0,1 µm aus dem Bericht
    assert not lay.nominal and lay.height == pytest.approx(0.1, abs=1e-6) and len(lay.bands) == 3
    assert structure.figure_xy(cfg, cad_report=report).axes


@pytest.mark.solver
def test_cad_1d_solves_with_energy_balance():
    cfg = _line_grating_cfg()
    cfg["incidence"]["lambda_um"] = 0.5
    cfg["truncation"]["Nx"] = 6
    res = solver.solve(cfg)
    tot = results.totals(res)
    assert tot["ΣR"] + tot["ΣT"] + tot["Absorption"] == pytest.approx(1.0, abs=1e-6)
    assert not results.orders_frame(res).empty


@pytest.mark.solver
def test_cad_1d_with_explicit_z_cut():
    cfg = _line_grating_cfg()
    cfg["layers"][0]["z_cut_um"] = -0.15
    assert solver.cad_check(cfg)["report"]["z_cut_um"] == pytest.approx(-0.15)
    cfg["layers"][0]["z_cut_um"] = 10.0  # außerhalb des z-Bereichs der Linie
    report = solver.cad_check(cfg)["report"]
    assert not report["ok"] and any(e["code"] == "OUT_OF_RANGE" for e in report["errors"])


@pytest.mark.solver
@pytest.mark.skipif(not (EXAMPLES_DIR / "cad" / "pillar_array.step").is_file(), reason="Beispiele nicht gefunden")
def test_cad_1d_rejects_non_z_invariant_body_quickly():
    cfg = _line_grating_cfg()
    cfg["layers"][0]["file"] = str(EXAMPLES_DIR / "cad" / "pillar_array.step")  # Säulen: nicht z-invariant
    cfg["layers"][0]["bodies"] = [{"name": "Pillar", "material": "si"}, {"name": "Lid", "material": "resist"}]
    report = solver.cad_check(cfg)["report"]
    assert not report["ok"] and any(e["code"] == "NOT_Z_INVARIANT" for e in report["errors"])


@pytest.mark.solver
def test_cad_1d_line_scaled_to_period(tmp_path):
    """Skalierte Linie (Editor): Breite = Periode, die Höhe stimmt mit dem Prüfbericht überein."""
    from fg_gui import cad

    text = (Path(__file__).parent / "data" / "cad" / "line_grating.step").read_text()
    info = cad.line_info(text, 0.5)
    path = cad.save_upload(cad.scale_step(text, info["scale"]).encode(), tmp_path)
    cfg = _line_grating_cfg()
    cfg["period_um"]["x"] = 0.5
    cfg["layers"] = [cad.line_layer(info, str(path), "resist", "air")]
    report = solver.cad_check(cfg)["report"]
    assert report["ok"], report
    assert report["bands"][-1]["y1_um"] - report["bands"][0]["y0_um"] == pytest.approx(info["height_um"], rel=1e-6)
    res = solver.solve({**cfg, "incidence": {**cfg["incidence"], "lambda_um": 0.5}})
    tot = results.totals(res)
    assert tot["ΣR"] + tot["ΣT"] + tot["Absorption"] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.solver
def test_profile1d_nurbs_solves_with_energy_balance():
    """Neue 1D-Linie (FourierGrating M24, ``profile1d`` mit ``shape: nurbs``) ohne STEP."""
    cfg = json.loads((Path(__file__).parent / "data" / "profile1d_nurbs_1d.json").read_text())
    cfg["incidence"]["lambda_um"] = 0.5
    cfg["truncation"]["Nx"] = 6
    tot = results.totals(solver.solve(cfg))
    assert tot["ΣR"] + tot["ΣT"] + tot["Absorption"] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.solver
def test_profile1d_nurbs_default_layer_is_accepted_by_the_core():
    from fg_gui import config_form as cf

    cfg = json.loads((Path(__file__).parent / "data" / "profile1d_nurbs_1d.json").read_text())
    cfg["layers"] = [
        {"type": "profile1d", "shape": "nurbs", "below": "resist", "above": "air", "nurbs": cf.nurbs_default(0.3, 0.1)}
    ]
    cfg["incidence"]["lambda_um"] = 0.5
    cfg["truncation"]["Nx"] = 6
    tot = results.totals(solver.solve(cfg))
    assert tot["ΣR"] + tot["ΣT"] + tot["Absorption"] == pytest.approx(1.0, abs=1e-6)
