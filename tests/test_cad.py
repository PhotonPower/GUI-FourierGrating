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


# ---------------------------------------------------------------- 1D-Gitter (M23)
def test_bands_rows_use_length_fractions_in_1d():
    report = {
        "dimension": "1D",
        "bands": [{"y0_um": 0.0, "y1_um": 0.1, "kind": "sectioned1d", "area_fractions": {"air": 0.7, "resist": 0.3}}],
    }
    row = cad.bands_rows(report)[0]
    assert row["Längenanteile"] == "air 70.0%, resist 30.0%" and "Flächenanteile" not in row
    assert cad.is_1d(report) and not cad.is_1d({"bands": []})
    assert "NOT_Z_INVARIANT" in cad.CODES


def test_cad_check_in_1d_has_one_profile_preview(fake_fg):
    from fg_gui import solver

    cfg = {"dimension": "1D", "layers": [{"type": "cad", "bodies": [{"name": "Line", "material": "resist"}]}]}
    out = solver.cad_check(cfg, extra_heights=(0.05,))  # extra_heights sind in 1D ohne Bedeutung
    assert out["report"]["dimension"] == "1D" and len(out["previews"]) == 1
    assert out["previews"][0]["y_um"] is None and out["previews"][0]["svg"].startswith("<svg")
    out2 = solver.cad_check({"dimension": "2D", **{k: v for k, v in cfg.items() if k != "dimension"}})
    assert len(out2["previews"]) == len(out2["report"]["bands"]) and out2["previews"][0]["y_um"] == 0.1


# ---------------------------------------------------------------- einfache Linie (1D)
LINE_STEP = Path(__file__).parent / "data" / "cad" / "line_grating.step"


def test_line_info_scales_width_to_period():
    text = LINE_STEP.read_text()
    info = cad.line_info(text, 0.3)
    assert info["name"] == "Line"
    assert info["height_um"] == pytest.approx(0.1 * 0.3 / info["width"])
    lo, hi = cad.step_extent(cad.scale_step(text, info["scale"]))
    assert hi[0] - lo[0] == pytest.approx(0.3)  # Breite = Periode
    assert hi[2] - lo[2] == pytest.approx(info["height_um"])  # Proportionen bleiben


def test_scale_step_scales_radii_but_not_angles_or_directions():
    text = (
        "#1=CARTESIAN_POINT('',(1.,2.,3.));\n#2=DIRECTION('',(0.,0.,1.));\n#3=CIRCLE('',#9,0.5);\n"
        "#4=CONICAL_SURFACE('',#9,2.,0.3);\n#5=ELLIPSE('',#9,2.,1.);\n"
    )
    out = cad.scale_step(text, 10.0)
    assert "(10.0,20.0,30.0)" in out
    assert "DIRECTION('',(0.,0.,1.))" in out
    assert "CIRCLE('',#9,5.0)" in out
    assert "CONICAL_SURFACE('',#9,20.0,0.3)" in out
    assert "ELLIPSE('',#9,20.0,10.0)" in out


def test_line_info_rejects_several_bodies_and_bad_period():
    with pytest.raises(cad.CadFileError, match="genau einen"):
        cad.line_info(FAKE_STEP, 0.3)
    with pytest.raises(cad.CadFileError, match="Periode"):
        cad.line_info(LINE_STEP.read_text(), 0.0)


def test_line_layer_maps_below_to_body_and_above_to_background():
    layer = cad.line_layer({"name": "Line"}, "/x.step", "si", "air")
    assert layer["bodies"] == [{"name": "Line", "material": "si"}]
    assert layer["background"] == "air" and layer["unit"] == "um" and layer["type"] == "cad"
    assert cad.line_layer({"name": ""}, "/x.step", "si", "air")["bodies"][0]["index"] == 0


def test_line_info_explains_open_surface_models():
    sheet = "ISO-10303-21;\n#1=SHELL_BASED_SURFACE_MODEL('',(#2));\n#2=OPEN_SHELL('',(#3));\n"
    assert cad.body_names(sheet) == [""]  # FourierGrating liest das Flächenmodell als Körper
    with pytest.raises(cad.CadFileError, match="offenes Flächenmodell"):
        cad.line_info(sheet, 0.3)
