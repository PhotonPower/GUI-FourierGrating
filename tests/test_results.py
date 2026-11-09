import pytest

from conftest import FakeResult
from fg_gui import results


def test_orders_frame():
    df = results.orders_frame(FakeResult())
    assert list(df.columns) == results.COLUMNS
    assert list(df["Seite"]) == ["R", "R", "T"]
    assert df["Effizienz"].sum() == pytest.approx(1.0)


def test_totals():
    t = results.totals(FakeResult())
    assert t["ΣR"] == pytest.approx(0.3) and t["ΣT"] == pytest.approx(0.7) and t["Energiebilanz"] == 1.0


def test_empty():
    r = FakeResult()
    r.reflected = r.reflected[:0]
    r.transmitted = r.transmitted[:0]
    assert results.orders_frame(r).empty
    assert results.totals(r)["ΣR"] == 0.0
