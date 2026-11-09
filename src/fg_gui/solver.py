"""Dünne Schicht über dem Python-Paket ``fouriergrating``.

Nur Import, Versionsprüfung und Weiterreichen von Aufrufen; keine Physik und keine eigene Prüfung des
Konfigurationsformats (AGENTS.md, Abschnitt 2). Fehlt das Paket, bleibt die GUI bedienbar und meldet es.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from typing import Any

#: älteste FourierGrating-Version, gegen die die GUI geprüft ist
MIN_VERSION = (0, 18, 0)


@dataclass(frozen=True)
class SolverInfo:
    available: bool
    version: str = ""
    version_ok: bool = False
    core_variant: str = ""  # "cpu" | "cuda12"
    cuda_available: bool = False
    cad_available: bool = False
    backend: dict = field(default_factory=dict)
    error: str = ""


def parse_version(text: str) -> tuple[int, ...]:
    """'0.18.0' -> (0, 18, 0); unlesbare Teile werden ignoriert."""
    m = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    return tuple(int(g) for g in m.groups() if g is not None) if m else ()


def module() -> Any:
    """Das Modul ``fouriergrating`` (ImportError, wenn es fehlt)."""
    return importlib.import_module("fouriergrating")


def info() -> SolverInfo:
    try:
        fg = module()
    except Exception as e:  # ImportError, aber auch fehlende CUDA-Bibliotheken beim Laden des Kerns
        return SolverInfo(available=False, error=f"{type(e).__name__}: {e}")

    def call(name: str, default: Any) -> Any:
        f = getattr(fg, name, None)
        try:
            return f() if callable(f) else default
        except Exception:
            return default

    version = str(getattr(fg, "__version__", ""))
    cad = getattr(fg, "cad", None)
    cad_ok = False
    if cad is not None and callable(getattr(cad, "available", None)):
        try:
            cad_ok = bool(cad.available())
        except Exception:
            cad_ok = False
    return SolverInfo(
        available=True,
        version=version,
        version_ok=parse_version(version) >= MIN_VERSION,
        core_variant=str(call("core_variant", "")),
        cuda_available=bool(call("cuda_available", False)),
        cad_available=cad_ok,
        backend=dict(call("get_backend", {}) or {}),
    )


def solve(cfg: dict) -> Any:
    """``fouriergrating.solve`` – erster Scanpunkt der Konfiguration (``fg.Result``)."""
    return module().solve(cfg)


def solve_scan(cfg: dict) -> Any:
    """``fouriergrating.solve_scan`` – alle Sweep-Werte und Scanpunkte (``fg.ScanResult``)."""
    return module().solve_scan(cfg)
