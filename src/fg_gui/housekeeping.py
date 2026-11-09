"""Aufräumen alter Ergebnisse und Uploads (G7). Keine Physik, nur Dateien unter ``FG_GUI_DATA_DIR``."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from .jobs import JobManager

log = logging.getLogger("fg_gui.housekeeping")
DAY = 86400.0


@dataclass
class Report:
    runs: int = 0
    uploads: int = 0
    freed_bytes: int = 0


def purge_runs(jm: JobManager, retention_days: int = 0, max_runs: int = 0, now: float | None = None) -> Report:
    """Löscht beendete Rechnungen, die älter als ``retention_days`` sind oder über ``max_runs`` hinausgehen.

    Wartende und laufende Rechnungen bleiben immer. 0 schaltet das jeweilige Kriterium ab.
    """
    now = time.time() if now is None else now
    rep = Report()
    finished = sorted((j for j in jm.jobs() if j.finished is not None), key=lambda j: j.finished or 0.0)
    doomed = []
    if retention_days > 0:
        doomed += [j for j in finished if now - (j.finished or now) > retention_days * DAY]
    if max_runs > 0:
        keep_total = len(jm.jobs()) - len(doomed)
        extra = [j for j in finished if j not in doomed][: max(0, keep_total - max_runs)]
        doomed += extra
    for j in doomed:
        size = jm.store.size_bytes(j.id) if jm.store is not None else 0
        if jm.delete(j.id):
            rep.runs += 1
            rep.freed_bytes += size
            log.info("Rechnung %s (%s) gelöscht: aufgeräumt", j.id, j.label)
    return rep


def purge_uploads(uploads: Path, jm: JobManager, retention_days: int, now: float | None = None) -> Report:
    """Löscht Uploads, die älter als ``retention_days`` sind und in keiner gespeicherten Konfiguration vorkommen."""
    rep = Report()
    if retention_days <= 0 or not uploads.is_dir() or jm.store is None:
        return rep
    now = time.time() if now is None else now
    configs = ""
    for j in jm.jobs():
        cfg = jm.store.path(j.id) / "config.json"
        try:
            configs += cfg.read_text(encoding="utf-8")
        except OSError:
            pass
    for f in sorted(uploads.iterdir()):
        try:
            if not f.is_file() or f.is_symlink() or now - f.stat().st_mtime <= retention_days * DAY:
                continue
            if f.name in configs:
                continue
            size = f.stat().st_size
            f.unlink()
        except OSError:
            continue
        rep.uploads += 1
        rep.freed_bytes += size
        log.info("Upload %s gelöscht: aufgeräumt", f.name)
    return rep


@dataclass
class SessionReport:
    runs: int = 0
    #: nicht gelöscht, weil sie noch laufen
    running: int = 0
    draft: bool = False


def delete_owner(jm: JobManager, owner: str, sessions: Path | None = None, session_id: str = "") -> SessionReport:
    """Löscht alle Rechnungen von ``owner`` und den gemerkten Editor-Entwurf der Sitzung.

    Wartende Rechnungen werden abgebrochen und gelöscht; eine laufende lässt sich nicht stoppen und bleibt.
    """
    rep = SessionReport()
    for j in jm.jobs(owner=owner):
        jm.cancel(j.id)
        if jm.delete(j.id):
            rep.runs += 1
        else:
            rep.running += 1
    if sessions is not None and session_id:
        f = sessions / f"{session_id}.json"
        try:
            if f.is_file() and not f.is_symlink() and f.parent == sessions:
                f.unlink()
                rep.draft = True
        except OSError:
            pass
    log.info("Sitzung %s: %d Rechnungen gelöscht, %d laufen noch", owner or session_id, rep.runs, rep.running)
    return rep


def purge_drafts(sessions: Path, retention_days: int, now: float | None = None) -> int:
    """Löscht gemerkte Editor-Konfigurationen (``sessions/<Kennung>.json``), die seit ``retention_days`` ruhen."""
    if retention_days <= 0 or not sessions.is_dir():
        return 0
    now = time.time() if now is None else now
    n = 0
    for f in sessions.glob("*.json"):
        try:
            if f.is_file() and not f.is_symlink() and now - f.stat().st_mtime > retention_days * DAY:
                f.unlink()
                n += 1
        except OSError:
            continue
    return n


def sweep(
    jm: JobManager,
    uploads: Path,
    retention_days: int,
    max_runs: int,
    now: float | None = None,
    sessions: Path | None = None,
) -> Report:
    a = purge_runs(jm, retention_days, max_runs, now)
    b = purge_uploads(uploads, jm, retention_days, now)
    if sessions is not None:
        purge_drafts(sessions, retention_days, now)
    return Report(a.runs, b.uploads, a.freed_bytes + b.freed_bytes)
