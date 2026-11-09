"""CAD-Hilfen (ohne Streamlit, ohne FourierGrating)."""

import copy
from pathlib import Path

import pytest

from conftest import FAKE_STEP
from fg_gui import cad


def test_body_names_in_file_order():
    assert cad.body_names(FAKE_STEP) == ["Pillar", "Lid", ""]
    assert cad.body_names("nichts") == []


def test_real_example_names():
    f = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples" / "cad" / "pillar_array.step"
    if not f.is_file():
        pytest.skip("Beispiel nicht vorhanden")
    assert cad.body_names(f.read_text()) == ["Pillar", "Lid"]


def test_upload_saved_by_content_hash(tmp_path):
    p1 = cad.save_upload(FAKE_STEP.encode(), tmp_path / "up")
    p2 = cad.save_upload(FAKE_STEP.encode(), tmp_path / "up")
    assert (
        p1 == p2
        and p1.suffix == ".step"
        and p1.read_text() == FAKE_STEP
        and len(list((tmp_path / "up").iterdir())) == 1
    )
    assert cad.save_upload((FAKE_STEP + " ").encode(), tmp_path / "up") != p1
    with pytest.raises(cad.CadFileError):
        cad.save_upload(b"kein STEP", tmp_path / "up")
    assert cad.looks_like_step("﻿  ISO-10303-21;") and not cad.looks_like_step("x")


def test_list_steps(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.step").write_text("s")
    (tmp_path / "y.stp").write_text("s")
    (tmp_path / "z.json").write_text("{}")
    assert [p.name for p in cad.list_steps(tmp_path)] == ["x.step", "y.stp"]
    assert cad.list_steps(None) == [] and cad.list_steps(tmp_path / "nix") == []


def _cfg(file):
    return {"layers": [{"type": "homogeneous"}, {"type": "cad", "file": file, "bodies": []}]}


def test_resolve_files_relative_and_absolute(tmp_path):
    root = tmp_path / "ex"
    (root / "cad").mkdir(parents=True)
    f = root / "cad" / "p.step"
    f.write_text(FAKE_STEP)
    cfg = _cfg("cad/p.step")
    out = cad.resolve_files(cfg, bases=[root], roots=[root])
    assert out["layers"][1]["file"] == str(f.resolve())
    assert cfg["layers"][1]["file"] == "cad/p.step"  # Original unverändert
    assert cad.resolve_files(_cfg(str(f)), [], [root])["layers"][1]["file"] == str(f.resolve())


def test_resolve_files_rejects_outside_and_missing(tmp_path):
    root = tmp_path / "ex"
    root.mkdir()
    secret = tmp_path / "geheim.step"
    secret.write_text(FAKE_STEP)
    with pytest.raises(cad.CadFileError, match="außerhalb"):
        cad.resolve_files(_cfg(str(secret)), [root], [root])
    with pytest.raises(cad.CadFileError, match="außerhalb"):
        cad.resolve_files(_cfg("../geheim.step"), [root], [root])  # .. führt hinaus
    link = root / "link.step"
    link.symlink_to(secret)
    with pytest.raises(cad.CadFileError, match="außerhalb"):
        cad.resolve_files(_cfg(str(link)), [root], [root])  # Symlink aus dem Verzeichnis heraus
    with pytest.raises(cad.CadFileError, match="nicht gefunden"):
        cad.resolve_files(_cfg("nix.step"), [root], [root])


def test_resolve_files_without_cad_or_with_embedded_step():
    cfg = {"layers": [{"type": "homogeneous"}, {"type": "cad", "step": FAKE_STEP}]}
    out = cad.resolve_files(cfg, [], [])
    assert out == cfg and out is not cfg
    assert cad.resolve_files({}, [], []) == {}


def test_bodies_roundtrip_unchanged():
    layer = {"bodies": [{"name": "Pillar", "material": "si"}, {"index": 1, "material": "sio2", "x": 1}]}
    before = copy.deepcopy(layer)
    rows = cad.bodies_rows(layer)
    assert rows == [{"Körper": "Pillar", "Material": "si"}, {"Körper": "#1", "Material": "sio2"}]
    cad.bodies_apply(layer, rows)
    assert layer == before


def test_bodies_rows_add_step_bodies_and_apply():
    layer = {"bodies": [{"name": "Pillar", "material": "si"}]}
    rows = cad.bodies_rows(layer, ["Pillar", "Lid", ""])
    assert [r["Körper"] for r in rows] == ["Pillar", "Lid", "#2"]
    rows[1]["Material"] = "sio2"
    rows[2]["Material"] = "air"
    rows[0]["Material"] = "glass"
    cad.bodies_apply(layer, rows)
    assert layer["bodies"] == [
        {"name": "Pillar", "material": "glass"},
        {"name": "Lid", "material": "sio2"},
        {"index": 2, "material": "air"},
    ]
    # leeres Material fügt keinen Eintrag hinzu und löscht keinen
    layer2 = {}
    cad.bodies_apply(layer2, [{"Körper": "A", "Material": ""}])
    assert layer2 == {}


def test_findings_bands_heights():
    report = {
        "ok": False,
        "errors": [{"code": "SHELL_OPEN", "message": "offen", "where_um": [0.1, 0.2, 0.3]}],
        "warnings": [{"code": "FEATURE_SMALL", "message": "klein"}],
        "bands": [{"y0_um": 0.0, "y1_um": 0.2, "kind": "extrusion", "area_fractions": {"air": 0.75, "si": 0.25}}],
    }
    rows = cad.findings_rows(report)
    assert [r["Stufe"] for r in rows] == ["Fehler", "Warnung"]
    assert (
        rows[0]["Code"] == "SHELL_OPEN"
        and rows[0]["Ort (µm)"] == "0.1, 0.2, 0.3"
        and "nicht geschlossen" in rows[0]["Bedeutung"]
    )
    assert cad.bands_rows(report)[0]["Flächenanteile"] == "air 75.0%, si 25.0%"
    assert cad.band_heights(report) == [0.1]
    assert set(cad.CODES) >= {"SHELL_OPEN", "BODY_UNASSIGNED", "STEP_UNSUPPORTED"}
