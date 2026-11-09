"""Abnahme mit dem echten Löser (Server): nur mit installiertem fouriergrating, sonst übersprungen."""

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
