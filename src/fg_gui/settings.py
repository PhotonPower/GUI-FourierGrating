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
    #: HTTP-Header, in dem ein vorgeschalteter Proxy den angemeldeten Benutzer übergibt (z. B. ``X-Remote-User``);
    #: leer = keine Anmeldung, Rechnungen gehören der Browsersitzung
    user_header: str
    #: fertige Rechnungen (und nicht mehr gebrauchte Uploads) nach so vielen Tagen löschen; 0 = nie
    retention_days: int
    #: höchstens so viele Rechnungen behalten (die ältesten fertigen fallen heraus); 0 = unbegrenzt
    max_runs: int
    log_level: str
    #: zusätzliche Logdatei (rotierend); leer = nur Standardfehlerausgabe (systemd-Journal)
    log_file: Path | None


def load() -> Settings:
    data = Path(os.environ.get("FG_GUI_DATA_DIR", "data")).expanduser()
    ex = os.environ.get("FG_GUI_EXAMPLES_DIR", "").strip()
    return Settings(
        data_dir=data,
        examples_dir=Path(ex).expanduser() if ex else None,
        workers=_int("FG_GUI_WORKERS", 1),
        job_history=_int("FG_GUI_JOB_HISTORY", 50),
        user_header=os.environ.get("FG_GUI_USER_HEADER", "").strip(),
        retention_days=_int("FG_GUI_RETENTION_DAYS", 0, minimum=0),
        max_runs=_int("FG_GUI_MAX_RUNS", 0, minimum=0),
        log_level=os.environ.get("FG_GUI_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        log_file=Path(lf).expanduser() if (lf := os.environ.get("FG_GUI_LOG_FILE", "").strip()) else None,
    )
