"""Grobe Abschätzung von Größe und Speicherbedarf einer Rechnung (G4) – nur zur Anzeige, keine Physik.

Aus der Konfiguration werden nur Zahlen abgelesen (Ordnungen, Länge der Scanlisten) und mit einem Faustfaktor
multipliziert. Die Zahlen können weit danebenliegen (RK-Löser, viele Scheiben, GPU); sie dienen als Warnung.
"""

from __future__ import annotations

import os
from typing import Any

#: komplexe Matrizen der Größe n × n gleichzeitig im Speicher je Rechnung (Faustwert: Eigenwertproblem, S-Matrizen)
MATRICES_PER_SOLVE = 12
BYTES_COMPLEX = 16


def _count(v: Any) -> int:
    """Anzahl der Werte einer Einfallsangabe (Zahl, Liste, Bereich)."""
    if isinstance(v, list):
        return max(len(v), 1)
    if isinstance(v, dict) and isinstance(v.get("steps"), int):
        return max(v["steps"], 1)
    return 1


def scan_points(cfg: dict) -> int:
    """Scanpunkte je Sweep-Wert: Produkt der Längen von λ, φ, ψ, δ (kartesisches Produkt)."""
    inc = cfg.get("incidence") if isinstance(cfg.get("incidence"), dict) else {}
    n = 1
    for k in ("lambda_um", "phi_deg", "psi_deg", "delta_deg"):
        n *= _count(inc.get(k, 0))
    return n


def sweep_values(cfg: dict) -> int:
    sw = cfg.get("sweep")
    return _count(sw.get("values")) if isinstance(sw, dict) else 1


def fourier_terms(cfg: dict) -> int:
    """n_f = (2 Nx + 1) (2 Nz + 1) in 2D, 2 Nx + 1 in 1D (config_format.md)."""
    t = cfg.get("truncation") if isinstance(cfg.get("truncation"), dict) else {}
    nx = int(t.get("Nx", 0) or 0)
    nz = int(t.get("Nz", 0) or 0)
    return (2 * nx + 1) * ((2 * nz + 1) if cfg.get("dimension") == "2D" else 1)


def matrix_size(cfg: dict) -> int:
    """n = 4 n_f (Größe der Eigenwertmatrix, docs/user_guide.md von FourierGrating)."""
    return 4 * fourier_terms(cfg)


def memory_bytes(cfg: dict, cores: int | None = None) -> int:
    """Faustwert: parallele Scanpunkte × Matrizen je Rechnung × n² × 16 Byte."""
    cores = cores or os.cpu_count() or 1
    parallel = min(scan_points(cfg), cores)
    n = matrix_size(cfg)
    return parallel * MATRICES_PER_SOLVE * n * n * BYTES_COMPLEX


def total_ram_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def format_bytes(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def summary(cfg: dict, cores: int | None = None) -> dict[str, Any]:
    mem = memory_bytes(cfg, cores)
    ram = total_ram_bytes()
    return {
        "scan_points": scan_points(cfg),
        "sweep_values": sweep_values(cfg),
        "matrix_size": matrix_size(cfg),
        "memory_bytes": mem,
        "memory_text": format_bytes(mem),
        "ram_fraction": (mem / ram) if ram else None,
    }
