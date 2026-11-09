"""Logging der GUI (G7): Logger ``fg_gui``, Ausgabe auf stderr (systemd-Journal) und optional in eine Datei."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

NAME = "fg_gui"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure(level: str = "INFO", file: Path | None = None) -> logging.Logger:
    """Richtet den Logger ein (idempotent: ein erneuter Aufruf ersetzt die eigenen Handler)."""
    log = logging.getLogger(NAME)
    log.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in [h for h in log.handlers if getattr(h, "_fg_gui", False)]:
        log.removeHandler(h)
        h.close()
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if file is not None:
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.handlers.RotatingFileHandler(file, maxBytes=5_000_000, backupCount=5,
                                                                 encoding="utf-8"))  # fmt: skip
        except OSError as e:
            log.warning("Logdatei %s nicht nutzbar: %s", file, e)
    for h in handlers:
        h.setFormatter(logging.Formatter(_FORMAT))
        h._fg_gui = True  # type: ignore[attr-defined]
        log.addHandler(h)
    return log
