"""Einstellungen aus Umgebungsvariablen (``FG_GUI_*``), siehe docs/deployment_rtx6000.md."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, "")
    try:
        return max(minimum, int(raw)) if raw.strip() else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    #: Arbeitsverzeichnis für Laufzeitdaten (Ergebnisse, hochgeladene Dateien)
    data_dir: Path
    #: Verzeichnis mit Beispielkonfigurationen (z. B. FourierGrating/examples); None = keine Beispiele
    examples_dir: Path | None
    #: gleichzeitig laufende Rechnungen. Standard 1: eine GPU, und jede Rechnung nutzt alle CPU-Kerne (OpenMP)
    workers: int
    #: Anzahl aufbewahrter Rechnungen im Speicher (älteste fertige fallen heraus)
    job_history: int


def load() -> Settings:
    data = Path(os.environ.get("FG_GUI_DATA_DIR", "data")).expanduser()
    ex = os.environ.get("FG_GUI_EXAMPLES_DIR", "").strip()
    return Settings(
        data_dir=data,
        examples_dir=Path(ex).expanduser() if ex else None,
        workers=_int("FG_GUI_WORKERS", 1),
        job_history=_int("FG_GUI_JOB_HISTORY", 50),
    )
