"""Optimierung (ohne FourierGrating): Eingaben, JSON-Pointer, L-BFGS-B gegen eine analytische Funktion."""

import threading

import numpy as np
import pytest

from conftest import FakeSimulation
from fg_gui import optimize as opt

CFG = {
    "layers": [
        {"type": "lamellar1d", "thickness_um": 0.15, "breakpoints_um": [0.0, 0.25, 0.5], "materials": ["a", "b"]}
    ],
    "materials": {"a": {"n": [1.38, 7.62]}, "b": {"n": 1.0}},
    "incidence": {"lambda_um": 0.6328, "phi_deg": [0, 10], "flag": True},
    "truncation": {"Nx": 12},
}


def test_pointer_get_set_and_escape():
    assert opt.get_pointer(CFG, "/layers/0/breakpoints_um/1") == 0.25
    assert opt.get_pointer(CFG, "/materials/a/n/1") == 7.62
    out = opt.set_pointer(CFG, "/layers/0/breakpoints_um/1", 0.3)
    assert out["layers"][0]["breakpoints_um"] == [0.0, 0.3, 0.5] and CFG["layers"][0]["breakpoints_um"][1] == 0.25
    assert opt.set_pointer({"a/b": {"c~d": 1}}, "/a~1b/c~0d", 2) == {"a/b": {"c~d": 2}}
    with pytest.raises(opt.SpecError):
        opt.get_pointer(CFG, "/layers/5/thickness_um")
    with pytest.raises(opt.SpecError):
        opt.get_pointer(CFG, "layers")


def test_numeric_pointers_lists_only_numbers_under_roots():
    ptrs = dict(opt.numeric_pointers(CFG))
    assert ptrs["/layers/0/thickness_um"] == 0.15 and ptrs["/materials/a/n/0"] == 1.38
    assert ptrs["/incidence/phi_deg/1"] == 10.0 and "/incidence/flag" not in ptrs  # bool ist keine Zahl
    assert not any(p.startswith("/truncation") for p in ptrs)
    assert all(opt.get_pointer(CFG, p) == v for p, v in ptrs.items())


def test_apply_to_config_keeps_the_rest():
    out = opt.apply_to_config(CFG, {"/layers/0/thickness_um": 0.2, "/materials/a/n/1": 7.0})
    assert out["layers"][0]["thickness_um"] == 0.2 and out["materials"]["a"]["n"] == [1.38, 7.0]
    assert out["truncation"] == CFG["truncation"] and CFG["layers"][0]["thickness_um"] == 0.15


def _spec(**kw):
    base = dict(
        terms=[("R", 0, 0, 1.0)],
        params=[
            opt.Param("/layers/0/thickness_um", 0.15, 0.03, 0.4),
            opt.Param("/layers/0/breakpoints_um/1", 0.3, 0.05, 0.45),
        ],
    )
    base.update(kw)
    return opt.Spec(**base)


def test_spec_validation():
    _spec().validate()
    bad = [
        _spec(terms=[]),
        _spec(terms=[("X", 0, 0, 1.0)]),
        _spec(terms=[("R", 0, 0, 0.0)]),
        _spec(terms=[("R", 0, 0, float("nan"))]),
        _spec(params=[]),
        _spec(params=[opt.Param("/a", 0.5, 0.5, 0.5)]),
        _spec(params=[opt.Param("/a", 0.9, 0.1, 0.5)]),
        _spec(params=[opt.Param("/a", 0.2, 0.1, 0.5), opt.Param("/a", 0.2, 0.1, 0.5)]),
        _spec(maxiter=0),
    ]
    for s in bad:
        with pytest.raises(opt.SpecError):
            s.validate()


def test_objective_sums_duplicate_terms_and_json_roundtrip():
    s = _spec(terms=[("R", -1, 0, 1.0), ("T", 0, 0, -0.5), ("R", -1, 0, 0.5)], maximize=False, maxiter=7, ftol=1e-9)
    assert s.objective() == {("R", -1, 0): 1.5, ("T", 0, 0): -0.5}
    back = opt.Spec.from_json(s.to_json())
    assert back == s


def test_run_finds_the_analytic_optimum():
    sim = FakeSimulation(CFG)
    hist = opt.History()
    res = opt.run(sim, _spec(), hist)
    assert res["success"] and not res["stopped"]
    assert res["value"] == pytest.approx(1.0, abs=1e-10)
    assert res["x"]["/layers/0/thickness_um"] == pytest.approx(0.25, abs=1e-6)
    assert res["x"]["/layers/0/breakpoints_um/1"] == pytest.approx(0.25, abs=1e-6)
    assert res["start"] == {"/layers/0/thickness_um": 0.15, "/layers/0/breakpoints_um/1": 0.3}
    assert res["nfev"] == len(res["history"]) == len(hist.snapshot()) == sim.calls
    assert res["history"][0]["x"] == [0.15, 0.3]
    assert res["history"][-1]["best"] == pytest.approx(res["value"])
    assert all(r["best"] >= r["value"] - 1e-15 for r in res["history"])  # „Bester“ ist nie schlechter


def test_run_minimize_and_bounds():
    # Minimieren: das Optimum liegt auf einer Grenze (Maximum bei 0,25 ist außerhalb [0.4, 0.45])
    s = _spec(
        maximize=False,
        params=[
            opt.Param("/layers/0/thickness_um", 0.42, 0.4, 0.45),
            opt.Param("/layers/0/breakpoints_um/1", 0.3, 0.05, 0.45),
        ],
    )
    res = opt.run(FakeSimulation(CFG), s)
    assert res["x"]["/layers/0/thickness_um"] == pytest.approx(
        0.45, abs=1e-9
    )  # entfernt sich vom Maximum bis zur Grenze
    assert all(0.4 <= r["x"][0] <= 0.45 for r in res["history"])
    assert res["value"] == min(r["value"] for r in res["history"])


def test_run_respects_weights_sign():
    res = opt.run(FakeSimulation(CFG), _spec(terms=[("R", 0, 0, 2.0), ("T", 0, 0, -0.5)]))
    assert res["value"] == pytest.approx(1.5, abs=1e-9)  # w = 1,5 · (1 − 0)


def test_stop_returns_best_so_far():
    hist = opt.History()

    class StoppingSim(FakeSimulation):
        def value_and_grad(self, objective, params):
            out = super().value_and_grad(objective, params)
            if self.calls == 2:
                hist.stop.set()
            return out

    sim = StoppingSim(CFG)
    res = opt.run(sim, _spec(), hist)
    assert res["stopped"] and not res["success"] and res["nfev"] == 2
    assert res["value"] == max(r["value"] for r in res["history"])
    assert res["x"]["/layers/0/thickness_um"] in [r["x"][0] for r in res["history"]]


def test_history_is_readable_while_running():
    hist = opt.History()
    seen = []
    started = threading.Event()

    class SlowSim(FakeSimulation):
        def value_and_grad(self, objective, params):
            started.set()
            seen.append(len(hist.snapshot()))
            return super().value_and_grad(objective, params)

    t = threading.Thread(target=lambda: opt.run(SlowSim(CFG), _spec(), hist))
    t.start()
    started.wait(5)
    t.join()
    assert seen[0] == 0 and seen[-1] == len(hist.snapshot()) - 1 and seen == sorted(seen)


def test_history_frame_and_preset():
    res = opt.run(FakeSimulation(CFG), _spec())
    df = opt.history_frame(res["history"], list(res["x"]))
    assert list(df.columns) == ["Auswertung", "Zielwert", "Bester", *res["x"], "|Gradient|"]
    assert len(df) == res["nfev"]
    p = opt.littrow_preset()
    assert np.isclose(p["config"]["incidence"]["phi_deg"], np.degrees(np.arcsin(0.6328 / (2 * 0.5))))
    assert [q.pointer for q in p["spec"].params] == ["/layers/0/thickness_um", "/layers/0/breakpoints_um/1"]
    p["spec"].validate()
    for q in p["spec"].params:
        assert opt.get_pointer(p["config"], q.pointer) is not None
