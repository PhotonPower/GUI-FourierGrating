"""Speichern und Laden der Rechnungsergebnisse (ohne Streamlit)."""

import json

import numpy as np
import pytest

from conftest import FakeResult, FakeScan, make_fake_nearfield
from fg_gui import results, store


def test_solve_roundtrip(tmp_path):
    res = FakeResult()
    s = store.RunStore(tmp_path)
    s.save_result("r1", "solve", res)
    back = s.load_result("r1", "solve")
    assert np.array_equal(back.reflected, res.reflected) and back.reflected.dtype == res.reflected.dtype
    assert np.array_equal(back.transmitted, res.transmitted)
    assert back.absorption == res.absorption and back.diagnostics == res.diagnostics
    # die Anzeigefunktionen arbeiten mit dem geladenen Ersatzobjekt
    assert results.totals(back) == results.totals(res)
    assert results.orders_frame(back).equals(results.orders_frame(res))


def test_scan_roundtrip(tmp_path):
    scan = FakeScan("/layers/0/thickness_um")
    s = store.RunStore(tmp_path)
    s.save_result("r2", "scan", scan)
    back = s.load_result("r2", "scan")
    assert back.sweep_parameter == "/layers/0/thickness_um"
    assert list(back.columns) == list(scan.columns)
    for k, v in scan.columns.items():
        assert np.array_equal(back.columns[k], v) and back.columns[k].dtype == v.dtype


def test_nearfield_roundtrip(tmp_path):
    nf = make_fake_nearfield()
    s = store.RunStore(tmp_path)
    s.save_result("r3", "nearfield", nf)
    back = s.load_result("r3", "nearfield")
    assert set(back) == set(nf)
    for cut in ("horizontal", "vertical"):
        assert set(back[cut]) == set(nf[cut])
        for k, v in nf[cut].items():
            if isinstance(v, np.ndarray):
                assert np.array_equal(back[cut][k], v)
            else:
                assert back[cut][k] == v
    assert back["incidence"] == nf["incidence"]


def test_meta_list_skips_damaged(tmp_path):
    s = store.RunStore(tmp_path)
    s.write_meta("a", {"id": "a", "label": "x"})
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "meta.json").write_text("{kaputt")
    s.write_meta("c", {"id": "falsch", "label": "y"})  # Verzeichnis und Kennung passen nicht
    assert [m["id"] for m in s.list_meta()] == ["a"]
    assert not list(tmp_path.rglob("*.tmp"))


def test_config_and_delete(tmp_path):
    s = store.RunStore(tmp_path)
    s.write_config("a", {"dimension": "1D", "x": [1, 2]})
    s.write_meta("a", {"id": "a"})
    assert s.read_config("a") == {"dimension": "1D", "x": [1, 2]}
    assert s.read_config("nix") is None
    assert s.size_bytes("a") > 0
    s.delete("a")
    assert not (tmp_path / "a").exists() and s.size_bytes("a") == 0


def test_json_default_handles_numpy(tmp_path):
    s = store.RunStore(tmp_path)
    s.write_meta("n", {"id": "n", "v": np.float64(1.5), "arr": np.arange(3)})
    assert json.loads((tmp_path / "n" / "meta.json").read_text())["arr"] == [0, 1, 2]


def test_unknown_kind_raises(tmp_path):
    with pytest.raises(ValueError):
        store.RunStore(tmp_path).load_result("a", "nix")
