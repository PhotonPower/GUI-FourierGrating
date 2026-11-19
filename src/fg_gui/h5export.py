"""Download einer fertigen Rechnung als HDF5-Datei (``.h5``).

Keine Physik: gespeicherte Ergebnisse werden nur umgeschrieben. Aufbau (alle Zeichenketten UTF-8):

``/``                    Attribute: ``format``, ``kind``, ``label``, ``job_id``, ``owner``, ``gui_version``,
                         ``fouriergrating``
``/config``              Konfiguration als JSON-Text (wie ``config.json``)
``/meta``                Metadaten der Rechnung als JSON-Text
``/result/...``          je Art des Ergebnisses (siehe ``_write_result``)
``/materials/<spalte>``  dispersive Materialien (n, ε über λ), falls vorhanden
"""

from __future__ import annotations

import io
import json
from typing import Any

import numpy as np
import pandas as pd

from . import __version__, export, nearfield, optimize, results, scans, solver
from .jobs import DONE, Job
from .store import RunStore, _json_default

FORMAT = "fg-gui-h5/1"


def _h5py():
    import h5py

    return h5py


def _text(group, name: str, value: str) -> None:
    group.create_dataset(name, data=value, dtype=_h5py().string_dtype("utf-8"))


def _json(group, name: str, value: Any) -> None:
    _text(group, name, json.dumps(value, indent=2, ensure_ascii=False, default=_json_default))


def _array(group, name: str, value: Any) -> None:
    """Feld schreiben; Unicode-Zeichenketten werden zu UTF-8-Zeichenketten (HDF5 kennt kein ``U``)."""
    arr = np.asarray(value)
    if arr.dtype.kind == "U" or (arr.dtype.kind == "O" and all(isinstance(v, str) for v in arr.ravel())):
        group.create_dataset(name, data=arr.astype(object), dtype=_h5py().string_dtype("utf-8"))
    elif arr.dtype.kind == "O":
        _json(group, name, value)
    else:
        group.create_dataset(name, data=arr, compression="gzip" if arr.size > 1000 else None)


def _frame(group, name: str, df: pd.DataFrame) -> None:
    """Tabelle als Gruppe: je Spalte ein Feld."""
    sub = group.create_group(name)
    for col in df.columns:
        _array(sub, str(col).replace("/", "_"), df[col].to_numpy())
        if "/" in str(col):  # JSON-Pointer als Spaltenname: der Feldname darf keinen Schrägstrich enthalten
            sub[str(col).replace("/", "_")].attrs["name"] = str(col)


def _write_result(h5, job: Job, result: Any) -> None:
    res = h5.create_group("result")
    if job.kind == "solve":
        for side, arr in (("reflected", result.reflected), ("transmitted", result.transmitted)):
            _array(res, side, np.asarray(arr))
        res.attrs.update({k: v for k, v in results.totals(result).items()})
        _json(res, "diagnostics", result.diagnostics or {})
    elif job.kind == "scan":
        sub = res.create_group("columns")
        for key, value in result.columns.items():
            _array(sub, key, value)
        res.attrs["sweep_parameter"] = getattr(result, "sweep_parameter", "") or ""
        _frame(res, "table", scans.scan_frame(result))
    elif job.kind == "nearfield":
        for name in nearfield.cut_names(result):
            cut = result[name]
            sub = res.create_group(name)
            for key, value in cut.items():
                if isinstance(value, np.ndarray):
                    _array(sub, key, value)
                elif key == "meta":
                    _json(sub, "meta", value)
                elif isinstance(value, str | int | float):
                    sub.attrs[key] = value
    elif job.kind == "optimize":
        _frame(res, "history", optimize.history_frame(result["history"], list(result["x"])))
        _array(res, "x", np.asarray(result["x"], dtype=float))
        res.attrs["value"] = float(result["value"])
    else:
        _json(res, "data", result)


def run_h5(job: Job, store: RunStore | None) -> bytes:
    """HDF5-Datei einer fertigen Rechnung (Bytes, im Speicher aufgebaut)."""
    if job.status != DONE:
        raise ValueError("Nur fertige Rechnungen lassen sich herunterladen")
    h5py = _h5py()
    cfg = store.read_config(job.id) if store is not None else None
    buf = io.BytesIO()
    with h5py.File(buf, "w") as h5:
        h5.attrs.update(
            {
                "format": FORMAT,
                "kind": job.kind,
                "label": job.label,
                "job_id": job.id,
                "owner": job.owner or "",
                "gui_version": __version__,
                "fouriergrating": solver.info().version or "",
            }
        )
        _json(h5, "meta", job.meta())
        if cfg is not None:
            _json(h5, "config", cfg)
        _write_result(h5, job, job.result())
        if cfg is not None:
            tables = export._material_tables(job.kind, job.result(), cfg)
            if "materials.csv" in tables:
                _frame(h5, "materials", pd.read_csv(io.BytesIO(tables["materials.csv"])))
    return buf.getvalue()
