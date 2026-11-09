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
