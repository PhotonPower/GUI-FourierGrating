"""Systeminformationen (GPU über nvidia-smi). Nur Anzeige."""

from __future__ import annotations

import shutil
import subprocess

_FIELDS = ["name", "memory.used", "memory.total", "utilization.gpu", "temperature.gpu", "driver_version"]
_LABELS = ["GPU", "Speicher belegt [MiB]", "Speicher gesamt [MiB]", "Auslastung [%]", "Temperatur [°C]", "Treiber"]


def gpus(timeout: float = 5.0) -> list[dict[str, str]]:
    """Eine Zeile je GPU; leere Liste, wenn nvidia-smi fehlt oder scheitert."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return []
    try:
        out = subprocess.run(
            [exe, f"--query-gpu={','.join(_FIELDS)}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_nvidia_smi(out)


def parse_nvidia_smi(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.strip().splitlines():
        vals = [v.strip() for v in line.split(",")]
        if len(vals) == len(_LABELS):
            rows.append(dict(zip(_LABELS, vals, strict=True)))
    return rows
