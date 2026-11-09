"""Umwandlungen des Konfigurationseditors (ohne Streamlit)."""

import json

import pytest

from fg_gui import config_form as cf


@pytest.mark.parametrize(
    "value",
    [0.6328, 20, [0.5, 0.6, 0.7], [1], {"from": 0.4, "to": 0.8, "steps": 5}, 0.0, 1e-8],
)
def test_scan_roundtrip(value):
    assert cf.parse_scan(cf.format_scan(value)) == value
    assert type(cf.parse_scan(cf.format_scan(value))) is type(value)


def test_scan_forms():
    assert cf.parse_scan("0.5") == 0.5
    assert cf.parse_scan("5") == 5 and isinstance(cf.parse_scan("5"), int)
    assert cf.parse_scan("0.5; 0.6") == [0.5, 0.6]
    assert cf.parse_scan("0.4:0.8:5") == {"from": 0.4, "to": 0.8, "steps": 5}
    for bad in ("", "abc", "1:2", "1:2:3.5"):
        with pytest.raises(cf.FormError):
            cf.parse_scan(bad)


def test_scan_not_editable_with_extra_keys():
    assert not cf.scan_is_editable({"from": 1, "to": 2, "steps": 3, "x": 1})
    assert cf.scan_is_editable([1, 2])


def test_assign_keeps_original_when_equal():
    d = {"a": 20, "b": [1, 2]}
    cf.assign(d, "a", 20.0)
    assert d["a"] == 20 and isinstance(d["a"], int)
    cf.assign(d, "c", 0, shown_default=0)
    assert "c" not in d
    cf.assign(d, "c", 3, shown_default=0)
    assert d["c"] == 3
    cf.assign(d, "a", 21)
    assert d["a"] == 21


def test_auto_int():
    assert cf.parse_auto_int("auto") == "auto"
    assert cf.parse_auto_int(" 4 ") == 4
    with pytest.raises(cf.FormError):
        cf.parse_auto_int("2.5")


def test_complex():
    assert cf.complex_parts(1.5) == (1.5, 0.0)
    assert cf.complex_parts([1.38, 7.62]) == (1.38, 7.62)
    assert cf.complex_value(1.5, 0) == 1.5
    assert cf.complex_value(1.38, 7.62) == [1.38, 7.62]


def test_material_kind_precedence():
    assert cf.material_kind({"n": 1}) == "n"
    assert cf.material_kind({"eps_tensor": []}) == "eps_tensor"
    assert cf.material_kind({"foo": 1}) is None
    for kind in cf.MATERIAL_KINDS:
        assert cf.material_kind(cf.material_defaults(kind)) == kind


def test_lamellae_roundtrip_and_edit():
    layer = {"breakpoints_um": [0, 0.45, 1.0], "materials": ["bar", "air"], "type": "lamellar1d"}
    rows = cf.lamellae_rows(layer)
    assert rows == [
        {"von_um": 0, "bis_um": 0.45, "material": "bar"},
        {"von_um": 0.45, "bis_um": 1.0, "material": "air"},
    ]
    before = {k: list(v) if isinstance(v, list) else v for k, v in layer.items()}
    cf.lamellae_apply(layer, rows)
    assert layer == before and layer["breakpoints_um"][0] == 0 and isinstance(layer["breakpoints_um"][0], int)
    rows.append({"von_um": float("nan"), "bis_um": 1.5, "material": "bar"})
    cf.lamellae_apply(layer, rows)
    assert layer["breakpoints_um"] == [0, 0.45, 1.0, 1.5] and layer["materials"] == ["bar", "air", "bar"]


def test_new_layers_and_move():
    for kind in cf.FORM_LAYER_TYPES:
        assert cf.new_layer(kind, ["air", "si"])["type"] == kind
    with pytest.raises(cf.FormError):
        cf.new_layer("cad", [])
    items = [1, 2, 3]
    cf.move(items, 0, -1)
    cf.move(items, 0, 1)
    assert items == [2, 1, 3]
    assert cf.unique_name("air", {"air", "air2"}) == "air3"


def test_locate_error():
    cfg = {"layers": [{"material": "a"}, {"type": "lamellar1d", "materials": ["a", "zzz"]}]}
    assert cf.locate_error("x.cpp:9: unknown material 'zzz'", cfg) == ("layers", 1)
    assert cf.locate_error("unknown material 'q'", cfg) == ("materials", None)
    assert cf.locate_error('dimension must be "1D" or "2D"', cfg) == ("basis", None)
    assert cf.locate_error("truncation orders must be non-negative", cfg) == ("basis", None)
    assert cf.locate_error("something odd", cfg) == (None, None)


# ---------------------------------------------------------------- 2D-Schichten (Einschlüsse, Regionen)
def test_layer_types_by_dimension():
    assert cf.layer_types("1D") == ["homogeneous", "lamellar1d", "profile1d"]
    assert "polygon2d" in cf.layer_types("2D") and "homogeneous" in cf.layer_types("2D")
    assert cf.layer_types("1D", "polygon2d")[-1] == "polygon2d"  # vorhandene Schicht bleibt wählbar


def test_new_2d_layers():
    for kind in cf.LAYER_TYPES_2D:
        layer = cf.new_layer(kind, ["air", "si"], 0.6, 0.4)
        assert layer["type"] == kind
    assert cf.new_layer("polygon2d", ["air", "si"], 0.6, 0.4)["inclusions"][0]["rectangle_um"]["center"] == [0.3, 0.2]


def _rows(layer, kind):
    return [cf.shape_row(e, kind) for e in layer[kind]]


def test_shapes_roundtrip_unchanged():
    layer = {
        "inclusions": [
            {"material": "si", "rectangle_um": {"center": [0, 0.3], "size": [0.3, 1]}},
            {"material": "air", "vertices_um": [[0, 0], [0.1, 0], [0.1, 0.1]], "extra": 1},
        ]
    }
    orig = json.loads(json.dumps(layer))
    cf.shapes_apply(layer, "inclusions", _rows(layer, "inclusions"))
    assert layer == orig
    # NaN aus der Tabelle (leere Zellen) ändert nichts
    rows = _rows(layer, "inclusions")
    rows[1]["x"] = float("nan")
    cf.shapes_apply(layer, "inclusions", rows)
    assert layer == orig


def test_regions_roundtrip_and_edit_keeps_holes():
    nurbs = {"degree": 2, "knots": [0, 0, 0, 1, 1, 1], "points_um": [[0, 0], [1, 0], [1, 1]], "weights": [1, 1, 1]}
    layer = {
        "regions": [
            {"material": "si", "circle": {"center_um": [0.25, 0.25], "radius_um": 0.1},
             "holes": [{"circle": {"center_um": [0.25, 0.25], "radius_um": 0.02}}]},
            {"material": "si", "ellipse": {"center_um": [0.6, 0.6], "radii_um": [0.12, 0.06], "angle_deg": 30}},
            {"material": "sio2", "polygon_um": [[0, 0], [0.1, 0], [0.1, 0.1]]},
            {"material": "si", "nurbs": nurbs},
        ]
    }  # fmt: skip
    orig = json.loads(json.dumps(layer))
    cf.shapes_apply(layer, "regions", _rows(layer, "regions"))
    assert layer == orig
    rows = _rows(layer, "regions")
    rows[0]["a"] = 0.15
    rows[1]["Winkel"] = 45
    cf.shapes_apply(layer, "regions", rows)
    assert layer["regions"][0]["circle"]["radius_um"] == 0.15 and "holes" in layer["regions"][0]
    assert layer["regions"][1]["ellipse"]["angle_deg"] == 45
    assert layer["regions"][3]["nurbs"] == nurbs


def test_shapes_add_change_form_and_bad_points():
    layer = {"inclusions": [{"material": "si", "rectangle_um": {"center": [0, 0], "size": [1, 1]}}]}
    rows = _rows(layer, "inclusions")
    rows.append({"Material": "air", "Form": "Rechteck", "x": 0.5, "z": 0.5, "a": 0.2, "b": 0.1, "Winkel": None,
                 "Eckpunkte": ""})  # fmt: skip
    rows[0]["Form"], rows[0]["Eckpunkte"] = "Polygon", "0 0; 1 0; 1 1"
    cf.shapes_apply(layer, "inclusions", rows)
    assert layer["inclusions"][0] == {"material": "si", "vertices_um": [[0, 0], [1, 0], [1, 1]]}
    assert layer["inclusions"][1]["rectangle_um"] == {"center": [0.5, 0.5], "size": [0.2, 0.1]}
    with pytest.raises(cf.FormError):
        cf.parse_points("0 0; 1")
