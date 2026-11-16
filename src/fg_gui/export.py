"""Download einer fertigen Rechnung als ZIP (G7+): Konfiguration, Rohdateien und gut lesbare Tabellen.

Keine Physik: es werden nur gespeicherte Ergebnisse umgewandelt (CSV, JSON) und Dateien gepackt.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any

from . import dispersion, nearfield, optimize, results, scans, solver
from .jobs import DONE, Job
from .store import RunStore


def safe_name(label: str, fallback: str = "rechnung") -> str:
    """Dateiname ohne Pfadzeichen aus der Bezeichnung (``Nahfeld: neu.json`` → ``Nahfeld_neu``)."""
    base = re.sub(r"[^\w.\-]+", "_", label.rsplit(".", 1)[0] if label.endswith(".json") else label).strip("._")
    return base or fallback


def _material_tables(kind: str, result: Any, cfg: dict | None) -> dict[str, bytes]:
    """``materials.csv`` für dispersive Materialien: Einzelrechnung aus der Diagnose (n und ε wie vom Kern
    geliefert), Scan aus ``fg.material_eps`` über die Wellenlängen des Scans (nur ε); ohne Löser entfällt es."""
    if not cfg or not dispersion.dispersive_materials(cfg):
        return {}
    if kind == "solve":
        frame = dispersion.diagnostics_frame(result.diagnostics, dispersion.first_lambda(cfg))
    elif kind == "scan":
        lams = sorted({float(x) for x in scans.scan_frame(result)["lambda_um"]})
        try:
            frame = dispersion.materials_frame(cfg, lams, lambda c, n, lam: solver.material_eps(c, n, lam))
        except Exception:  # Löser fehlt oder FourierGrating ohne M22: Auszug entfällt, der Rest bleibt gültig
            return {}
    else:
        return {}
    return {"materials.csv": frame.to_csv(index=False).encode()} if not frame.empty else {}


def _tables(kind: str, result: Any) -> dict[str, bytes]:
    """Lesbare Auszüge je Art des Ergebnisses (Pfad → Inhalt)."""
    out: dict[str, bytes] = {}
    if kind == "solve":
        out["orders.csv"] = results.orders_frame(result).to_csv(index=False).encode()
        out["totals.json"] = json.dumps(results.totals(result), indent=2).encode()
        out["diagnostics.json"] = json.dumps(result.diagnostics or {}, indent=2, default=str).encode()
    elif kind == "scan":
        frame = scans.scan_frame(result)
        out["efficiencies.csv"] = scans.to_csv(frame, getattr(result, "sweep_parameter", "") or "")
    elif kind == "nearfield":
        out.update(nearfield.export_files(result))
    elif kind == "optimize":
        out["history.csv"] = optimize.history_frame(result["history"], list(result["x"])).to_csv(index=False).encode()
        out["optimum.json"] = json.dumps({"value": result["value"], "x": result["x"]}, indent=2).encode()
    return out


def run_zip(job: Job, store: RunStore | None) -> bytes:
    """ZIP einer fertigen Rechnung: ``<Name>/{config.json, meta.json, <Tabellen>, raw/<gespeicherte Dateien>}``."""
    if job.status != DONE:
        raise ValueError("Nur fertige Rechnungen lassen sich herunterladen")
    root = safe_name(job.label) + "_" + job.id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{root}/meta.json", json.dumps(job.meta(), indent=2, ensure_ascii=False, default=str))
        if store is not None:
            cfg = store.read_config(job.id)
            if cfg is not None:
                z.writestr(f"{root}/config.json", json.dumps(cfg, indent=2, ensure_ascii=False))
        cfg = store.read_config(job.id) if store is not None else None
        tables = _tables(job.kind, job.result())
        tables.update(_material_tables(job.kind, job.result(), cfg))
        for path, data in tables.items():
            z.writestr(f"{root}/{path}", data)
        if store is not None and store.path(job.id).is_dir():
            for f in sorted(store.path(job.id).iterdir()):
                if f.is_file() and not f.name.endswith(".tmp") and f.name not in ("meta.json", "config.json"):
                    z.write(f, f"{root}/raw/{f.name}")
    return buf.getvalue()
