"""Umwandlungen des Konfigurationseditors (ohne Streamlit)."""

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
        cf.new_layer("polygon2d", [])
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
