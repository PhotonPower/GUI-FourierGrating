"""Dispersive Materialien (G8, FourierGrating M22) ohne Streamlit: Modelle erkennen, Tabellen, CSV, Dateizugriff.

Ein Materialwert unter ``n``, ``eps`` oder in einem Eintrag von ``eps_principal`` ist eine Zahl, ``[Re, Im]`` oder ein
Modell (``sellmeier``, ``cauchy``, ``drude_lorentz``, ``table``; ``docs/config_format.md`` von FourierGrating).
Ausgewertet wird im Kern. Hier steht nur Formatarbeit: Erkennen, Zeilen ↔ Daten, CSV lesen, ``file`` → ``data``
(Dateien nur aus erlaubten Verzeichnissen, AGENTS.md Abschnitt 7). Keine Brechzahlen, keine Interpolation.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

MODELS = ("sellmeier", "cauchy", "drude_lorentz", "table")
UNITS = ("um", "nm", "eV")
INTERPOLATIONS = ("linear", "cubic")
EXTRAPOLATIONS = ("error", "constant")
#: Spalten der Tabellenzeilen im Editor: Wellenlänge/Energie, Wert (n bzw. Re ε), Verlust (k bzw. Im ε)
TABLE_COLUMNS = ["x", "re", "im"]
#: FourierGrating-Spalten von ``materials.csv``
MATERIALS_CSV_COLUMNS = ["lambda_um", "material", "component", "n_re", "n_im", "eps_re", "eps_im"]


class DispersionError(ValueError):
    """Tabelle/CSV unlesbar oder Datei fehlt bzw. liegt außerhalb der erlaubten Verzeichnisse."""


# ---------------------------------------------------------------- erkennen
def model_name(value: Any) -> str | None:
    """Name des Modells, wenn ``value`` ein Modellobjekt ist (``{"sellmeier": {...}}``), sonst ``None``."""
    if isinstance(value, dict):
        for m in MODELS:
            if m in value:
                return m
    return None


def entries(mat: Any) -> list[tuple[str, Any]]:
    """Materialwerte eines Materials als (Schlüsselpfad, Wert): ``n``, ``eps``, ``eps_principal/0`` …"""
    if not isinstance(mat, dict):
        return []
    out: list[tuple[str, Any]] = []
    for k in ("n", "eps"):
        if k in mat:
            out.append((k, mat[k]))
    pr = mat.get("eps_principal")
    if isinstance(pr, list):
        out += [(f"eps_principal/{i}", v) for i, v in enumerate(pr)]
    return out


def is_dispersive(mat: Any) -> bool:
    return any(model_name(v) for _, v in entries(mat))


def dispersive_materials(cfg: dict) -> list[str]:
    mats = cfg.get("materials")
    return [n for n, m in mats.items() if is_dispersive(m)] if isinstance(mats, dict) else []


def model_container(mat: dict) -> tuple[str, str] | None:
    """(``"n"`` | ``"eps"``, Modellname) für Materialien mit einem Modell direkt unter ``n``/``eps``."""
    for k in ("n", "eps"):
        m = model_name(mat.get(k))
        if m:
            return k, m
    return None


def defaults(kind: str) -> dict:
    """Neues Material der Art ``table_n``, ``table_eps``, ``sellmeier``, ``cauchy`` oder ``drude_lorentz``."""
    return {
        "table_n": {"n": {"table": {"data": [[0.4, 1.5, 0.0], [0.8, 1.5, 0.0]]}}},
        "table_eps": {"eps": {"table": {"data": [[0.4, 2.25, 0.0], [0.8, 2.25, 0.0]]}}},
        # Quarzglas (Beispiel in docs/config_format.md von FourierGrating)
        "sellmeier": {
            "n": {
                "sellmeier": {
                    "A": 1.0,
                    "B": [0.6961663, 0.4079426, 0.8974794],
                    "C_um2": [0.00467914826, 0.0135120631, 97.9340025],
                }
            }
        },
        "cauchy": {"n": {"cauchy": {"A": 1.5, "B_um2": 0.004}}},
        "drude_lorentz": {"eps": {"drude_lorentz": {"eps_inf": 1.0, "omega_p_eV": 9.0, "f0": 1.0, "gamma0_eV": 0.05}}},
    }[kind]


# ---------------------------------------------------------------- Einfallsbereich
def lambda_range(cfg: dict) -> tuple[float, float] | None:
    """Kleinste und größte Wellenlänge der Konfiguration (Zahl, Liste oder ``{"from","to","steps"}``)."""
    v = (cfg.get("incidence") or {}).get("lambda_um") if isinstance(cfg.get("incidence"), dict) else None
    vals: list[float] = []
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        vals = [float(v)]
    elif isinstance(v, list):
        vals = [float(x) for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
    elif isinstance(v, dict) and {"from", "to"} <= v.keys():
        vals = [float(v["from"]), float(v["to"])]
    return (min(vals), max(vals)) if vals else None


def first_lambda(cfg: dict) -> float | None:
    """Wellenlänge des ersten Scanpunkts (Einzelrechnungen rechnen genau diesen)."""
    inc = cfg.get("incidence")
    v = inc.get("lambda_um") if isinstance(inc, dict) else None
    if isinstance(v, list) and v:
        v = v[0]
    elif isinstance(v, dict) and "from" in v:
        v = v["from"]
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ---------------------------------------------------------------- Tabellen als Zeilen
def table_rows(table: dict) -> list[dict]:
    data = table.get("data") if isinstance(table, dict) else None
    rows = []
    for r in data if isinstance(data, list) else []:
        if isinstance(r, list) and len(r) >= 2:
            rows.append({"x": r[0], "re": r[1], "im": r[2] if len(r) > 2 else None})
    return rows


def _num(v: Any) -> float | None:
    return None if v is None or isinstance(v, bool) or (isinstance(v, float) and v != v) else float(v)


def rows_to_data(rows: list[dict], old: list | None = None) -> list[list[float]]:
    """Zeilen → ``data``. Zeilen ohne Wellenlänge oder Wert entfallen; fehlt überall der Verlust, bleiben es 2 Spalten.

    Unveränderte Zeilen übernehmen den alten Eintrag (``1`` bleibt ``1``).
    """
    clean = []
    for r in rows:
        x, re_, im = _num(r.get("x")), _num(r.get("re")), _num(r.get("im"))
        if x is not None and re_ is not None:
            clean.append((x, re_, im))
    three = any(im is not None for *_, im in clean) or any(isinstance(r, list) and len(r) > 2 for r in old or [])
    data = []
    for i, (x, re_, im) in enumerate(clean):
        row = [x, re_, im if im is not None else 0.0] if three else [x, re_]
        if old and i < len(old) and isinstance(old[i], list) and len(old[i]) == len(row) and old[i] == row:
            row = old[i]
        data.append(row)
    return data


def table_apply(table: dict, rows: list[dict]) -> None:
    """Schreibt die Tabelle zurück; ohne Änderung bleibt ``data`` unverändert (auch bei fehlender dritter Spalte)."""
    old = table.get("data") if isinstance(table.get("data"), list) else []
    data = rows_to_data(rows, old)
    if data and data != old:
        table["data"] = data


# ---------------------------------------------------------------- CSV
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def parse_csv(text: str) -> list[list[float]]:
    """CSV wie FourierGrating (Komma, Semikolon oder Leerraum; ``#``-Zeilen und eine Kopfzeile ohne Zahlen entfallen).

    Ergebnis: Zeilen mit 2 oder 3 Zahlen (Wellenlänge, Wert[, Verlust]). Mehr Spalten oder ein anderes Spaltenmaß
    je Zeile ist ein Fehler mit Zeilennummer.
    """
    rows: list[list[float]] = []
    for ln, line in enumerate(text.splitlines(), start=1):
        s = line.strip().lstrip("﻿")
        if not s or s.startswith("#"):
            continue
        parts = [p for p in re.split(r"[,;\s]+", s) if p]
        if not any(_NUMBER.match(p) for p in parts):
            if rows:
                raise DispersionError(f"Zeile {ln}: keine Zahlen („{s[:40]}“)")
            continue  # Kopfzeile
        if not all(_NUMBER.match(p) for p in parts):
            raise DispersionError(f"Zeile {ln}: Zahl erwartet („{s[:40]}“)")
        if not 2 <= len(parts) <= 3:
            raise DispersionError(
                f"Zeile {ln}: 2 oder 3 Spalten erwartet (Wellenlänge, Wert[, Verlust]), gefunden {len(parts)}"
            )
        vals = [float(p) for p in parts]
        if rows and len(rows[0]) != len(vals):
            raise DispersionError(f"Zeile {ln}: {len(vals)} Spalten, vorher {len(rows[0])}")
        rows.append(vals)
    if len(rows) < 2:
        raise DispersionError("Mindestens zwei Zeilen mit Zahlen erforderlich")
    return rows


def csv_text(data: list[list[float]]) -> str:
    return "\n".join(", ".join(repr(float(v)) for v in r) for r in data)


def table_material(kind: str, data: list[list[float]], unit: str = "um") -> dict:
    """Material der Art ``table_n``/``table_eps`` aus CSV-Zeilen; ``unit`` nur, wenn nicht ``um`` (Standard)."""
    table: dict[str, Any] = {"data": data}
    if unit != "um":
        table["unit"] = unit
    return {"n" if kind == "table_n" else "eps": {"table": table}}


# ---------------------------------------------------------------- file → data
def _tables(cfg: dict) -> list[tuple[str, dict]]:
    out = []
    mats = cfg.get("materials")
    for name, mat in mats.items() if isinstance(mats, dict) else []:
        for path, v in entries(mat):
            if model_name(v) == "table" and isinstance(v["table"], dict):
                out.append((f"{name}/{path}", v["table"]))
    return out


def inline_files(cfg: dict, bases: list[Path], roots: list[Path]) -> dict:
    """Kopie der Konfiguration, in der Tabellen mit ``file`` durch ``data`` ersetzt sind.

    Relative Pfade werden gegen ``bases`` aufgelöst; die Datei muss unter ``roots`` liegen, sonst
    ``DispersionError``. So bleiben Rechnungen reproduzierbar und als JSON vollständig. Ohne ``file`` gleich (Kopie).
    """
    out = copy.deepcopy(cfg)
    for where, table in _tables(out):
        name = table.get("file")
        if not isinstance(name, str):
            continue
        candidates = [Path(name)] if Path(name).is_absolute() else [b / name for b in bases]
        found = next((c for c in candidates if c.is_file()), None)
        if found is None:
            raise DispersionError(f"Material {where}: Tabellendatei „{name}“ nicht gefunden.")
        p = found.resolve()
        if not any(p == r.resolve() or r.resolve() in p.parents for r in roots):
            raise DispersionError(f"Material {where}: Die Datei „{name}“ liegt außerhalb der erlaubten Verzeichnisse.")
        try:
            data = parse_csv(p.read_text(encoding="utf-8", errors="replace"))
        except DispersionError as e:
            raise DispersionError(f"Material {where}, Datei „{name}“: {e}") from e
        del table["file"]
        table["data"] = data
    return out


def has_files(cfg: dict) -> bool:
    return any(isinstance(t.get("file"), str) for _, t in _tables(cfg))


# ---------------------------------------------------------------- Ausgaben
def library_files(directory: Path | None) -> list[Path]:
    """Materialdateien (``.csv``, ``.yml``, ``.yaml``) der gemeinsamen Bibliothek, sortiert; nur Lesen."""
    if directory is None or not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".yml", ".yaml"))


def eps_frame(lambdas: list[float], eps: Any) -> Any:
    """Tabelle ``lambda_um, eps_re, eps_im`` aus Werten von ``material_eps`` (komplexes Array; bei Hauptwerten ein
    zweites Achsenmaß, dann je Komponente ``eps1_re`` …)."""
    import numpy as np
    import pandas as pd

    a = np.asarray(eps, dtype=complex)
    data: dict[str, Any] = {"lambda_um": list(lambdas)}
    if a.ndim == 1:
        data["eps_re"], data["eps_im"] = a.real, a.imag
    else:
        for j in range(a.shape[-1]):
            data[f"eps{j + 1}_re"], data[f"eps{j + 1}_im"] = a[:, j].real, a[:, j].imag
    return pd.DataFrame(data)


def materials_frame(cfg: dict, lambdas: list[float], eps_fn: Callable[[dict, str, Any], Any]) -> Any:
    """``materials.csv``-Auszug für die dispersiven Materialien: ``lambda_um, material, component, eps_re, eps_im``.

    ``eps_fn(cfg, name, lambdas)`` ist ``fg.material_eps`` (über ``solver.py``); die Werte werden unverändert
    durchgereicht. ``component``: ``iso`` oder Hauptachse ``1``–``3``.
    """
    import pandas as pd

    rows = []
    for name in dispersive_materials(cfg):
        vals = eps_fn(cfg, name, list(lambdas))
        frame = eps_frame(list(lambdas), vals)
        comps = (
            [("iso", "eps_re", "eps_im")]
            if "eps_re" in frame
            else [(str(j + 1), f"eps{j + 1}_re", f"eps{j + 1}_im") for j in range(3)]
        )
        for comp, cre, cim in comps:
            for lam, re_, im in zip(frame["lambda_um"], frame[cre], frame[cim], strict=True):
                rows.append({"lambda_um": lam, "material": name, "component": comp, "eps_re": re_, "eps_im": im})
    return pd.DataFrame(rows, columns=["lambda_um", "material", "component", "eps_re", "eps_im"])


def _cx(v: Any) -> complex:
    """Komplexe Zahl, auch als gespeichertes ``[Re, Im]`` (JSON)."""
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return complex(float(v[0]), float(v[1]))
    return complex(v)


def diagnostics_frame(diag: dict | None, lambda_um: float | None = None) -> Any:
    """``diagnostics["materials"]`` (n und ε je dispersivem Material am Rechenpunkt) als Tabelle im Format von
    ``materials.csv``: ``lambda_um, material, component, n_re, n_im, eps_re, eps_im``. Leer ohne dispersive Materialien.
    """
    import pandas as pd

    rows = []
    for m in (diag or {}).get("materials") or []:
        if not isinstance(m, dict):
            continue
        n, eps = _cx(m.get("n", 0)), _cx(m.get("eps", 0))
        comp = m.get("component", 0)
        rows.append(
            {
                "lambda_um": lambda_um,
                "material": m.get("name", ""),
                "component": "iso" if comp in (0, "iso", None) else str(comp),
                "n_re": n.real,
                "n_im": n.imag,
                "eps_re": eps.real,
                "eps_im": eps.imag,
            }
        )
    return pd.DataFrame(rows, columns=MATERIALS_CSV_COLUMNS)
