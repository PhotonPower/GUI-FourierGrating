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
