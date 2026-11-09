"""CAD-Schichten (G5): STEP-Dateien verwalten, Körper-Material-Zuordnung, Dateizugriff absichern.

Geometrie, Schnitte und Prüfcodes liefert ``fouriergrating.cad`` (über ``solver.py``); hier stehen nur Dinge ohne
Physik: Namen der Körper aus dem STEP-Text lesen, die Tabelle der Zuordnung, Hochladen und die Prüfung, dass eine
Konfiguration nur Dateien in erlaubten Verzeichnissen liest (AGENTS.md, Abschnitt 7).
"""

from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from . import config_form as cf

AXES = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
UNITS = ("auto", "mm", "um")
OVERLAPS = ("error", "priority")
Y_INTERPOLATIONS = ("none", "chebyshev")
STEP_MAGIC = "ISO-10303-21"
#: Befundcodes von fouriergrating.cad.check (docs/cad.md) mit kurzer Erklärung
CODES = {
    "SHELL_OPEN": "Körper nicht geschlossen (freie Kanten)",
    "SHELL_ORIENTATION": "Orientierung inkonsistent oder Volumen negativ",
    "BODY_OVERLAP": "zwei Körper überlappen",
    "PERIODIC_OVERLAP": "Körper überlappt sein periodisches Bild",
    "OUT_OF_RANGE": "Geometrie außerhalb des y-Bereichs",
    "UNIT_SUSPECT": "Abmessungen passen nicht zu Periode/Wellenlänge (Einheit?)",
    "FEATURE_SMALL": "Merkmal oder Band sehr klein",
    "BODY_UNASSIGNED": "Körper ohne Material oder Zuordnung ohne Körper",
    "STEP_UNSUPPORTED": "Datei nicht lesbar oder Entität nicht unterstützt",
}


class CadFileError(ValueError):
    """STEP-Datei fehlt, ist keine STEP-Datei oder liegt außerhalb der erlaubten Verzeichnisse."""


# ---------------------------------------------------------------- Schichten finden
def cad_layers(cfg: dict) -> list[tuple[int, dict]]:
    return [(i, L) for i, L in enumerate(cfg.get("layers") or []) if isinstance(L, dict) and L.get("type") == "cad"]


def new_layer(material_names: list[str]) -> dict:
    return {
        "type": "cad",
        "unit": "auto",
        "axes": {"y": "+Z", "x": "+X"},
        "background": "superstrate",
        "bodies": [],
    }


# ---------------------------------------------------------------- STEP-Datei
def looks_like_step(data: bytes | str) -> bool:
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    return text.lstrip("﻿ \t\r\n").startswith(STEP_MAGIC)


def body_names(step_text: str) -> list[str]:
    """Namen der Volumenkörper in Dateireihenfolge (``MANIFOLD_SOLID_BREP('Name',…)``); leer = Positionsnummer."""
    return [m.group(1) for m in re.finditer(r"MANIFOLD_SOLID_BREP\s*\(\s*'([^']*)'", step_text)]


def save_upload(data: bytes, directory: Path) -> Path:
    """Legt eine hochgeladene STEP-Datei unter ``<sha256 (16 Zeichen)>.step`` ab (gleicher Inhalt = gleiche Datei)."""
    if not looks_like_step(data):
        raise CadFileError("Das ist keine STEP-Datei (sie beginnt nicht mit „ISO-10303-21“).")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{hashlib.sha256(data).hexdigest()[:16]}.step"
    if not path.exists():
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path


def list_steps(directory: Path | None) -> list[Path]:
    """STEP-Dateien unterhalb eines Verzeichnisses (z. B. ``FourierGrating/examples``), sortiert."""
    if directory is None or not directory.is_dir():
        return []
    return sorted({p for ext in ("*.step", "*.stp") for p in directory.rglob(ext) if p.is_file()})


# ---------------------------------------------------------------- Dateizugriff
def _inside(path: Path, roots: list[Path]) -> bool:
    p = path.resolve()
    return any(p == r.resolve() or r.resolve() in p.parents for r in roots)


def resolve_files(cfg: dict, bases: list[Path], roots: list[Path]) -> dict:
    """Kopie der Konfiguration mit absoluten ``file``-Pfaden der CAD-Schichten.

    Relative Pfade werden gegen ``bases`` aufgelöst (Beispielverzeichnis, Uploads); das Ergebnis muss in ``roots``
    liegen, sonst ``CadFileError``. Ohne CAD-Schicht bleibt die Konfiguration gleich (Kopie).
    """
    out = copy.deepcopy(cfg)
    for i, layer in cad_layers(out):
        name = layer.get("file")
        if not isinstance(name, str):
            continue  # "step" mit Dateiinhalt: kein Dateizugriff
        candidates = [Path(name)] if Path(name).is_absolute() else [b / name for b in bases]
        found = next((c for c in candidates if c.is_file()), None)
        if found is None:
            raise CadFileError(f"Schicht {i}: STEP-Datei „{name}“ nicht gefunden.")
        if not _inside(found, roots):
            raise CadFileError(f"Schicht {i}: Die Datei „{name}“ liegt außerhalb der erlaubten Verzeichnisse.")
        layer["file"] = str(found.resolve())
    return out


# ---------------------------------------------------------------- Körper → Material
def body_key(entry: dict) -> str:
    return str(entry["name"]) if "name" in entry else f"#{entry.get('index', '?')}"


def bodies_rows(layer: dict, step_names: list[str] | None = None) -> list[dict]:
    """Zeilen ``{"Körper", "Material"}``: erst die Zuordnungen der Schicht, dann Körper der STEP-Datei ohne Eintrag."""
    rows = [
        {"Körper": body_key(e), "Material": e.get("material", "")}
        for e in (layer.get("bodies") or [])
        if isinstance(e, dict)
    ]
    known = {r["Körper"] for r in rows}
    for i, n in enumerate(step_names or []):
        key = n or f"#{i}"
        if key not in known:
            rows.append({"Körper": key, "Material": ""})
    return rows


def bodies_apply(layer: dict, rows: list[dict]) -> None:
    """Schreibt geänderte Materialien zurück; bestehende Einträge behalten ihre übrigen Schlüssel."""
    bodies = layer.get("bodies")
    if not isinstance(bodies, list):
        bodies = []
    by_key = {body_key(e): e for e in bodies if isinstance(e, dict)}
    changed = False
    for r in rows:
        key, mat = r.get("Körper"), r.get("Material") or ""
        if not key:
            continue
        if key in by_key:
            if by_key[key].get("material", "") != mat and mat:
                by_key[key]["material"] = mat
        elif mat:
            entry = {"index": int(key[1:])} if key.startswith("#") and key[1:].isdigit() else {"name": key}
            entry["material"] = mat
            bodies.append(entry)
            by_key[key] = entry
            changed = True
    if changed or "bodies" in layer:
        layer["bodies"] = bodies


# ---------------------------------------------------------------- Befunde
def findings_rows(report: dict) -> list[dict]:
    rows = []
    for level, key in (("Fehler", "errors"), ("Warnung", "warnings")):
        for f in report.get(key) or []:
            where = f.get("where_um")
            rows.append(
                {
                    "Stufe": level,
                    "Code": f.get("code", ""),
                    "Bedeutung": CODES.get(f.get("code", ""), ""),
                    "Meldung": f.get("message", ""),
                    "Ort (µm)": cf.format_list(list(where)) if where else "",
                }
            )
    return rows


def bands_rows(report: dict) -> list[dict]:
    rows = []
    for b in report.get("bands") or []:
        fr = b.get("area_fractions") or {}
        rows.append(
            {
                "y von (µm)": b.get("y0_um"),
                "y bis (µm)": b.get("y1_um"),
                "Art": b.get("kind", ""),
                "Flächenanteile": ", ".join(f"{k} {v:.1%}" for k, v in fr.items()),
            }
        )
    return rows


def band_heights(report: dict) -> list[float]:
    """Mitte jedes Bandes (Höhen für die Schnittvorschau)."""
    return [(b["y0_um"] + b["y1_um"]) / 2 for b in report.get("bands") or [] if "y0_um" in b and "y1_um" in b]
