"""Persistenz der Rechnungen unter ``FG_GUI_DATA_DIR/runs/<id>/`` (G4).

Je Rechnung ein Verzeichnis: ``meta.json`` (Bezeichnung, Art, Besitzer, Status, Zeiten, Fehler), ``config.json``
und – je nach Art – das Ergebnis (``*.npz`` für Arrays, ``*.json`` für den Rest). Ergebnisse werden beim Anzeigen
nachgeladen, nicht beim Start. Keine Physik: es wird nur geschrieben und gelesen, was FourierGrating geliefert hat.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

KINDS = ("solve", "scan", "nearfield", "cad", "optimize")
KIND_LABELS = {
    "solve": "Einzelrechnung",
    "scan": "Scan",
    "nearfield": "Nahfeld",
    "cad": "CAD-Prüfung",
    "optimize": "Optimierung",
    "": "–",
}


def _json_default(o: Any) -> Any:
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, complex):
        return [o.real, o.imag]
    return str(o)


def _write_json(path: Path, data: Any) -> None:
    """Atomar schreiben: erst Temporärdatei, dann umbenennen (ein Absturz hinterlässt keine halbe Datei)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- Ersatzobjekte für geladene Ergebnisse
@dataclass
class StoredResult:
    """Wie ``fg.Result`` (nur Lesen): genug für ``results.orders_frame`` und ``results.totals``."""

    reflected: np.ndarray
    transmitted: np.ndarray
    absorption: float
    diagnostics: dict
    incidence: dict | None = None
    scattering: dict | None = None
    modal: dict | None = None


@dataclass
class StoredScan:
    """Wie ``fg.ScanResult`` (nur Spalten); ``points`` wird nicht gespeichert."""

    columns: dict
    sweep_parameter: str = ""
    points: list = field(default_factory=list)


# ---------------------------------------------------------------- Ergebnisse schreiben und lesen
def save_result(kind: str, result: Any, directory: Path) -> None:
    if kind == "solve":
        np.savez_compressed(directory / "result.npz", reflected=result.reflected, transmitted=result.transmitted)
        _write_json(
            directory / "result.json",
            {
                "absorption": float(result.absorption),
                "diagnostics": result.diagnostics,
                "incidence": getattr(result, "incidence", None),
                "scattering": getattr(result, "scattering", None),
                "modal": getattr(result, "modal", None),
            },
        )
    elif kind == "scan":
        np.savez_compressed(directory / "columns.npz", **{k: np.asarray(v) for k, v in result.columns.items()})
        _write_json(directory / "scan.json", {"sweep_parameter": getattr(result, "sweep_parameter", "")})
    elif kind in ("cad", "optimize"):
        _write_json(directory / f"{kind}.json", result)
    elif kind == "nearfield":
        rest: dict[str, Any] = {}
        for name, cut in result.items():
            if not isinstance(cut, dict):
                rest[name] = cut  # z. B. "incidence"
                continue
            np.savez_compressed(
                directory / f"cut_{name}.npz", **{k: v for k, v in cut.items() if isinstance(v, np.ndarray)}
            )
            rest[name] = {k: v for k, v in cut.items() if not isinstance(v, np.ndarray)}
        _write_json(directory / "nearfield.json", rest)


def load_result(kind: str, directory: Path) -> Any:
    if kind == "solve":
        with np.load(directory / "result.npz") as z:
            refl, trans = z["reflected"], z["transmitted"]
        info = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        return StoredResult(refl, trans, info["absorption"], info["diagnostics"], info.get("incidence"),
                            info.get("scattering"), info.get("modal"))  # fmt: skip
    if kind == "scan":
        with np.load(directory / "columns.npz") as z:
            cols = {k: z[k] for k in z.files}
        info = json.loads((directory / "scan.json").read_text(encoding="utf-8"))
        return StoredScan(cols, info.get("sweep_parameter", ""))
    if kind in ("cad", "optimize"):
        return json.loads((directory / f"{kind}.json").read_text(encoding="utf-8"))
    if kind == "nearfield":
        out = json.loads((directory / "nearfield.json").read_text(encoding="utf-8"))
        for name, cut in out.items():
            f = directory / f"cut_{name}.npz"
            if isinstance(cut, dict) and f.is_file():
                with np.load(f) as z:
                    cut.update({k: z[k] for k in z.files})
        return out
    raise ValueError(f"Kein gespeichertes Ergebnis für Art „{kind}“")


# ---------------------------------------------------------------- Verzeichnis der Rechnungen
class RunStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, run_id: str) -> Path:
        return self.root / run_id

    def write_meta(self, run_id: str, meta: dict) -> None:
        d = self.path(run_id)
        d.mkdir(parents=True, exist_ok=True)
        _write_json(d / "meta.json", meta)

    def write_config(self, run_id: str, config: dict | None) -> None:
        if config is not None:
            d = self.path(run_id)
            d.mkdir(parents=True, exist_ok=True)
            _write_json(d / "config.json", config)

    def read_config(self, run_id: str) -> dict | None:
        f = self.path(run_id) / "config.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None

    def save_result(self, run_id: str, kind: str, result: Any) -> None:
        d = self.path(run_id)
        d.mkdir(parents=True, exist_ok=True)
        save_result(kind, result, d)

    def has_result(self, run_id: str, kind: str) -> bool:
        names = {
            "solve": "result.npz",
            "scan": "columns.npz",
            "nearfield": "nearfield.json",
            "cad": "cad.json",
            "optimize": "optimize.json",
        }
        return kind in names and (self.path(run_id) / names[kind]).is_file()

    def load_result(self, run_id: str, kind: str) -> Any:
        return load_result(kind, self.path(run_id))

    def list_meta(self) -> list[dict]:
        """Alle lesbaren ``meta.json``; beschädigte Verzeichnisse werden übersprungen."""
        out = []
        if not self.root.is_dir():
            return out
        for d in sorted(self.root.iterdir()):
            f = d / "meta.json"
            try:
                meta = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(meta, dict) and meta.get("id") == d.name:
                out.append(meta)
        return out

    def delete(self, run_id: str) -> None:
        d = self.path(run_id)
        if d.is_dir() and d.parent == self.root:
            shutil.rmtree(d, ignore_errors=True)

    def size_bytes(self, run_id: str) -> int:
        d = self.path(run_id)
        return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0
