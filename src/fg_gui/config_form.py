"""Logik des Konfigurationseditors (G1) ohne Streamlit: Texteingaben ↔ Werte, Vorlagen, Fehlerzuordnung.

Der Editor verändert die Konfiguration an Ort und Stelle und fasst nur an, was der Nutzer ändert
(:func:`assign`). Unbekannte Schlüssel, Reihenfolge, ``1`` statt ``1.0`` usw. bleiben dadurch erhalten
(Roundtrip Konfiguration → Formular → Konfiguration). Keine Physik, keine Schemaprüfung (AGENTS.md, Abschnitt 2).
"""

from __future__ import annotations

import re
from typing import Any

#: Schichttypen, für die es ein Formular gibt; alle anderen werden als JSON bearbeitet
LAYER_TYPES_1D = ("homogeneous", "lamellar1d", "profile1d")
LAYER_TYPES_2D = ("polygon2d", "contour2d", "profile2d")  # nur bei "dimension": "2D"
FORM_LAYER_TYPES = LAYER_TYPES_1D + LAYER_TYPES_2D
MATERIAL_KINDS = {
    "n": "Brechzahl n",
    "eps": "Permittivität ε",
    "eps_principal": "Hauptwerte ε (gedreht)",
    "eps_tensor": "Tensor ε (JSON)",
}
PROFILE_SHAPES = ("sinus", "triangle", "points")
PROFILE2D_SHAPES = ("egg_crate", "sinus_x")
POLYGON_FACTORIZATIONS = ("auto", "FFF_sym", "FFF_iso", "FFF_B", "laurent")
PROFILE_FACTORIZATIONS = ("auto", "laurent", "li_lamellar", "FFF_iso", "FFF_sym", "FFF_rig", "FFF_A", "FFF_B")


class FormError(ValueError):
    """Eingabe lässt sich nicht in einen Konfigurationswert umwandeln."""


# ---------------------------------------------------------------- Zuweisung
def assign(d: dict, key: str, value: Any, shown_default: Any = None) -> None:
    """Setzt ``d[key]`` nur, wenn der Nutzer etwas geändert hat.

    Ist der Schlüssel vorhanden, zählt der Vergleich mit dem Wert (``20 == 20.0`` lässt ``20`` stehen). Fehlt er,
    entspricht ``shown_default`` dem Wert, den das Formular anzeigte; nur eine Abweichung legt ihn an.
    """
    if key in d:
        if d[key] != value:
            d[key] = value
    elif value != shown_default:
        d[key] = value


# ---------------------------------------------------------------- Zahlen, Listen, Bereiche
def _number(text: str) -> int | float:
    t = text.strip()
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError as e:
        raise FormError(f"„{text.strip()}“ ist keine Zahl") from e


def format_number(v: Any) -> str:
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, int):
        return str(v)
    return repr(float(v))


def parse_list(text: str) -> list[int | float]:
    """``"0, 0.45, 1"`` → ``[0, 0.45, 1]``; Trenner Komma oder Semikolon."""
    parts = [p for p in re.split(r"[;,\s]+", text.strip()) if p]
    return [_number(p) for p in parts]


def format_list(values: list) -> str:
    return ", ".join(format_number(v) for v in values)


def parse_scan(text: str) -> Any:
    """Einfall: Zahl, Liste ``a, b, c`` oder Bereich ``von:bis:Schritte`` → JSON-Wert wie in config_format.md."""
    t = text.strip()
    if not t:
        raise FormError("Eingabe fehlt")
    if ":" in t:
        parts = [p.strip() for p in t.split(":")]
        if len(parts) != 3:
            raise FormError("Bereich als von:bis:Schritte angeben")
        lo, hi, steps = _number(parts[0]), _number(parts[1]), _number(parts[2])
        if not isinstance(steps, int):
            raise FormError("Schrittzahl muss eine ganze Zahl sein")
        return {"from": lo, "to": hi, "steps": steps}
    values = parse_list(t)
    if not values:
        raise FormError("Eingabe fehlt")
    return values[0] if len(values) == 1 and not re.search(r"[;,]", t) else values


def format_scan(v: Any) -> str:
    if isinstance(v, dict) and {"from", "to", "steps"} <= v.keys():
        return f"{format_number(v['from'])}:{format_number(v['to'])}:{format_number(v['steps'])}"
    if isinstance(v, list):
        return format_list(v) + ("," if len(v) == 1 else "")  # Komma: Liste mit einem Element, kein Skalar
    if isinstance(v, (int, float)):
        return format_number(v)
    return str(v)


def scan_is_editable(v: Any) -> bool:
    """False bei Formen, die der Text nicht verlustfrei darstellt (z. B. Bereich mit weiteren Schlüsseln)."""
    if isinstance(v, dict):
        return set(v) == {"from", "to", "steps"}
    return isinstance(v, (int, float, list)) and not isinstance(v, bool)


def parse_auto_int(text: str) -> int | str:
    """``"auto"`` oder ganze Zahl (Threads)."""
    t = text.strip()
    if t.lower() == "auto":
        return "auto"
    v = _number(t)
    if not isinstance(v, int):
        raise FormError("„auto“ oder eine ganze Zahl angeben")
    return v


# ---------------------------------------------------------------- komplexe Werte, Materialien
def complex_parts(v: Any) -> tuple[float, float]:
    """``1.5`` → ``(1.5, 0)``; ``[1.38, 7.62]`` → ``(1.38, 7.62)``."""
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return float(v[0]), float(v[1])
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v), 0.0
    return 0.0, 0.0


def complex_value(re_: float, im: float) -> Any:
    return re_ if im == 0 else [re_, im]


def material_kind(mat: Any) -> str | None:
    """Art der Materialangabe in der Rangfolge von FourierGrating (n, eps, eps_tensor, eps_principal)."""
    if not isinstance(mat, dict):
        return None
    for k in ("n", "eps", "eps_tensor", "eps_principal"):
        if k in mat:
            return k
    return None


def material_defaults(kind: str) -> dict:
    return {
        "n": {"n": 1.0},
        "eps": {"eps": 1.0},
        "eps_principal": {"eps_principal": [1.0, 1.0, 1.0], "euler_deg": [0, 0, 0]},
        "eps_tensor": {
            "eps_tensor": [[[1.0, 0.0], [0, 0], [0, 0]], [[0, 0], [1.0, 0.0], [0, 0]], [[0, 0], [0, 0], [1.0, 0.0]]]
        },
    }[kind]


def unique_name(base: str, existing) -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"


# ---------------------------------------------------------------- Vorlagen
def default_config() -> dict:
    """Kleinste lauffähige Konfiguration: 1D-Lamellengitter."""
    return {
        "dimension": "1D",
        "solver": "rcwa",
        "truncation": {"Nx": 15, "Nz": 0},
        "period_um": {"x": 1.0, "z": 0.0},
        "incidence": {"lambda_um": 0.6328, "phi_deg": 0, "psi_deg": 0, "delta_deg": 0},
        "materials": {"air": {"n": 1.0}, "glass": {"n": 1.5}, "bar": {"n": 2.0}},
        "superstrate": "air",
        "substrate": "glass",
        "layers": [
            {"type": "lamellar1d", "thickness_um": 0.4, "breakpoints_um": [0.0, 0.5, 1.0], "materials": ["bar", "air"]}
        ],
    }


def layer_types(dimension: Any, current: str | None = None) -> list[str]:
    """Schichttypen zur Auswahl: in 1D die 1D-Typen, in 2D alle (z-invariante 1D-Schichten sind dort erlaubt)."""
    types = list(FORM_LAYER_TYPES if dimension == "2D" else LAYER_TYPES_1D)
    if current in FORM_LAYER_TYPES and current not in types:
        types.append(current)
    return types


def new_layer(kind: str, materials: list[str], period_x: float = 1.0, period_z: float = 1.0) -> dict:
    first = materials[0] if materials else ""
    second = materials[1] if len(materials) > 1 else first
    if kind == "polygon2d":
        return {
            "type": "polygon2d",
            "thickness_um": 0.1,
            "background": first,
            "inclusions": [
                {"material": second, "rectangle_um": {"center": [period_x / 2, period_z / 2],
                                                      "size": [period_x / 2, period_z / 2]}}
            ],
        }  # fmt: skip
    if kind == "contour2d":
        return {
            "type": "contour2d",
            "thickness_um": 0.1,
            "background": first,
            "regions": [
                {"material": second, "circle": {"center_um": [period_x / 2, period_z / 2],
                                                "radius_um": min(period_x, period_z) / 4}}
            ],
        }  # fmt: skip
    if kind == "profile2d":
        return {"type": "profile2d", "shape": "egg_crate", "depth_um": 0.1, "below": first, "above": second}
    if kind == "homogeneous":
        return {"type": "homogeneous", "thickness_um": 0.1, "material": first}
    if kind == "lamellar1d":
        return {
            "type": "lamellar1d",
            "thickness_um": 0.1,
            "breakpoints_um": [0.0, period_x / 2, period_x],
            "materials": [first, second],
        }
    if kind == "profile1d":
        return {"type": "profile1d", "shape": "sinus", "depth_um": 0.1, "below": first, "above": second}
    raise FormError(f"Kein Formular für Schichttyp „{kind}“")


def shape_defaults(shape: str) -> dict:
    if shape == "triangle":
        return {"blaze_deg": 10.0, "apex_deg": 90.0}
    if shape == "points":
        return {"x_um": [0.0, 0.5], "y_um": [0.0, 1.0]}
    return {}


def move(items: list, index: int, delta: int) -> None:
    j = index + delta
    if 0 <= index < len(items) and 0 <= j < len(items):
        items[index], items[j] = items[j], items[index]


# ---------------------------------------------------------------- lamellar1d als Tabelle
def lamellae_rows(layer: dict) -> list[dict]:
    bp, mats = layer.get("breakpoints_um") or [], layer.get("materials") or []
    n = min(len(mats), max(len(bp) - 1, 0))
    return [{"von_um": bp[i], "bis_um": bp[i + 1], "material": mats[i]} for i in range(n)]


def lamellae_apply(layer: dict, rows: list[dict]) -> None:
    """Schreibt die Tabelle zurück; unvollständige Zeilen werden verworfen, ``von`` der ersten Zeile gilt als Start."""
    rows = [r for r in rows if r.get("bis_um") is not None and r.get("material") and r["bis_um"] == r["bis_um"]]
    if not rows:
        return
    first = rows[0].get("von_um")
    start = layer["breakpoints_um"][0] if first is None or first != first else first
    bp = [start] + [r["bis_um"] for r in rows]
    mats = [r["material"] for r in rows]
    # Zahlen unverändert lassen, wenn sie dem Original entsprechen (1 bleibt 1)
    old = layer.get("breakpoints_um") or []
    bp = [old[i] if i < len(old) and old[i] == v else v for i, v in enumerate(bp)]
    assign(layer, "breakpoints_um", bp)
    assign(layer, "materials", mats)


# ---------------------------------------------------------------- 2D-Einschlüsse und -Regionen als Tabelle
#: Spalten: Material, Form, Mitte x/z, a/b (Rechteck: Größe; Kreis: Radius; Ellipse: Halbachsen), Winkel, Eckpunkte
SHAPE_COLUMNS = ["Material", "Form", "x", "z", "a", "b", "Winkel", "Eckpunkte"]
INCLUSION_FORMS = ("Rechteck", "Polygon")
REGION_FORMS = ("Kreis", "Ellipse", "Polygon", "NURBS")
#: (Schlüssel in der Konfiguration, Formname) je Liste
_GEOMETRY = {
    "inclusions": {"rectangle_um": "Rechteck", "vertices_um": "Polygon"},
    "regions": {"circle": "Kreis", "ellipse": "Ellipse", "polygon_um": "Polygon", "nurbs": "NURBS"},
}


def _clean(v: Any) -> Any:
    return None if v is None or (isinstance(v, float) and v != v) else v


def format_points(points: Any) -> str:
    if not isinstance(points, list):
        return ""
    return "; ".join(" ".join(format_number(c) for c in p) for p in points if isinstance(p, (list, tuple)))


def parse_points(text: str) -> list[list[int | float]]:
    """``"0 0; 0.1 0; 0.1 0.1"`` → ``[[0, 0], [0.1, 0], [0.1, 0.1]]`` (Eckpunkte x z, getrennt durch ``;``)."""
    pts = []
    for part in text.split(";"):
        if not part.strip():
            continue
        xy = parse_list(part)
        if len(xy) != 2:
            raise FormError(f"Eckpunkt „{part.strip()}“: zwei Zahlen x z erwartet")
        pts.append(xy)
    return pts


def shape_row(entry: Any, kind: str) -> dict:
    """Eine Einschluss-/Regionsangabe der Konfiguration als Tabellenzeile (``kind``: ``inclusions`` | ``regions``)."""
    row: dict = dict.fromkeys(SHAPE_COLUMNS)
    row["Eckpunkte"] = ""
    if not isinstance(entry, dict):
        return row
    row["Material"] = entry.get("material")
    for key, form in _GEOMETRY[kind].items():
        if key not in entry:
            continue
        g = entry[key]
        row["Form"] = form
        if form == "Rechteck" and isinstance(g, dict):
            (row["x"], row["z"]), (row["a"], row["b"]) = g.get("center", [None, None]), g.get("size", [None, None])
        elif form in ("Kreis", "Ellipse") and isinstance(g, dict):
            row["x"], row["z"] = g.get("center_um", [None, None])
            if form == "Kreis":
                row["a"] = g.get("radius_um")
            else:
                row["a"], row["b"] = g.get("radii_um", [None, None])
                row["Winkel"] = g.get("angle_deg")
        elif form == "Polygon":
            row["Eckpunkte"] = format_points(g)
        break
    return row


def shape_entry(row: dict, orig: Any, kind: str) -> dict:
    """Tabellenzeile → Konfigurationseintrag. Von ``orig`` bleiben nicht angezeigte Schlüssel (``holes`` …) erhalten."""
    form = row["Form"]
    same_form = isinstance(orig, dict) and shape_row(orig, kind)["Form"] == form
    entry = dict(orig) if same_form else {}
    entry["material"] = row["Material"]
    num = lambda k: 0.0 if _clean(row.get(k)) is None else float(row[k])  # noqa: E731
    old_geo = (orig or {}) if same_form else {}
    if form == "Rechteck":
        old = old_geo.get("rectangle_um", {})
        entry["rectangle_um"] = {**old, "center": [num("x"), num("z")], "size": [num("a"), num("b")]}
    elif form == "Kreis":
        old = old_geo.get("circle", {})
        entry["circle"] = {**old, "center_um": [num("x"), num("z")], "radius_um": num("a")}
    elif form == "Ellipse":
        old = old_geo.get("ellipse", {})
        g = {**old, "center_um": [num("x"), num("z")], "radii_um": [num("a"), num("b")]}
        if _clean(row.get("Winkel")) is not None or "angle_deg" in old:
            g["angle_deg"] = num("Winkel")
        entry["ellipse"] = g
    elif form == "Polygon":
        key = "vertices_um" if kind == "inclusions" else "polygon_um"
        entry[key] = parse_points(row.get("Eckpunkte") or "")
    # NURBS: Geometrie bleibt unverändert (nur als JSON bearbeitbar)
    return entry


def shapes_apply(layer: dict, kind: str, rows: list[dict]) -> None:
    """Schreibt die Tabelle zurück. Unveränderte Zeilen behalten ihren Originaleintrag (Zahlenform, Zusatzschlüssel)."""
    old = layer.get(kind) if isinstance(layer.get(kind), list) else []
    new = []
    for i, r in enumerate(rows):
        r = {k: _clean(r.get(k)) for k in SHAPE_COLUMNS}
        if not r["Material"] or not r["Form"] or r["Form"] == "?":
            continue
        r["Eckpunkte"] = r["Eckpunkte"] or ""
        orig = old[i] if i < len(old) else None
        if orig is not None and shape_row(orig, kind) == r:
            new.append(orig)
        else:
            new.append(shape_entry(r, orig, kind))
    assign(layer, kind, new, [])


# ---------------------------------------------------------------- Fehler von FourierGrating → Abschnitt
SECTIONS = ("basis", "incidence", "materials", "layers", "solver")


def locate_error(message: str, cfg: dict) -> tuple[str | None, int | None]:
    """Ordnet eine Fehlermeldung von FourierGrating einem Abschnitt (und ggf. einer Schicht) zu.

    FourierGrating nennt keinen Feldpfad (Anforderung in docs/roadmap.md); daher Stichwörter und Namen.
    Unbekannt: ``(None, None)``.
    """
    msg = message.lower()
    m = re.search(r"unknown material '([^']*)'", message)
    if m:
        name = m.group(1)
        for i, layer in enumerate(cfg.get("layers") or []):
            if isinstance(layer, dict) and name in _layer_materials(layer):
                return "layers", i
        return "materials", None
    for i in range(len(cfg.get("layers") or [])):
        if re.search(rf"layers?[/\[ #]*{i}\b", msg):
            return "layers", i
    if re.search(r"layer|breakpoint|thickness|depth|profile|lamell|polygon|contour|slices", msg):
        return "layers", None
    if re.search(r"material|\beps\b|eps_|refractive|\bn\b", msg):
        return "materials", None
    if re.search(r"lambda|phi|psi|delta|incidence|wavelength", msg):
        return "incidence", None
    if re.search(r"dimension|truncation|period|\bnx\b|\bnz\b|superstrate|substrate", msg):
        return "basis", None
    if re.search(r"\brk\b|rcwa|solver|backend|precision|thread|tableau|reduction", msg):
        return "solver", None
    return None, None


def _layer_materials(layer: dict) -> set[str]:
    names: set[str] = set()
    for k in ("material", "below", "above", "background"):
        if isinstance(layer.get(k), str):
            names.add(layer[k])
    if isinstance(layer.get("materials"), list):
        names.update(x for x in layer["materials"] if isinstance(x, str))
    return names
