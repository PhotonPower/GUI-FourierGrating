"""Gemeinsame Ressourcen und Sitzungszustand für die Seiten.

Schlüssel in ``st.session_state`` beginnen mit ``fg_`` (AGENTS.md, Abschnitt 4).
"""

from __future__ import annotations

import threading
import time
import uuid

import streamlit as st

from . import cad, housekeeping, logs, solver, users
from . import settings as _settings
from .jobs import Job, JobManager
from .store import RunStore


@st.cache_resource
def settings() -> _settings.Settings:
    return _settings.load()


@st.cache_resource
def job_manager() -> JobManager:
    s = settings()
    logs.configure(s.log_level, s.log_file)
    jm = JobManager(workers=s.workers, history=s.job_history, store=RunStore(s.data_dir / "runs"))
    sweep_now(jm)
    return jm


_sweep_lock = threading.Lock()
_last_sweep = 0.0
SWEEP_INTERVAL = 3600.0


def sweep_now(jm: JobManager | None = None) -> housekeeping.Report:
    """Räumt nach ``FG_GUI_RETENTION_DAYS``/``FG_GUI_MAX_RUNS`` auf (ohne Vorgaben passiert nichts)."""
    global _last_sweep
    s = settings()
    with _sweep_lock:
        _last_sweep = time.time()
        if not (s.retention_days or s.max_runs):
            return housekeeping.Report()
        return housekeeping.sweep(jm or job_manager(), uploads_dir(), s.retention_days, s.max_runs)


def sweep_if_due() -> None:
    if time.time() - _last_sweep > SWEEP_INTERVAL:
        sweep_now()


@st.cache_data(ttl=60)
def solver_info() -> solver.SolverInfo:
    return solver.info()


def session_id() -> str:
    """Kennung der Browsersitzung (Zuordnung der Jobs; keine Anmeldung)."""
    if "fg_session" not in st.session_state:
        st.session_state["fg_session"] = uuid.uuid4().hex[:8]
    return st.session_state["fg_session"]


def current_user() -> str:
    """Angemeldeter Benutzer laut Proxy-Header (``FG_GUI_USER_HEADER``); ``""`` ohne Anmeldung."""
    header = settings().user_header
    if not header:
        return ""
    try:
        return users.user_from_headers(st.context.headers, header)
    except Exception:  # außerhalb einer Sitzung (Tests) gibt es keinen Kontext
        return ""


def owner_id() -> str:
    """Besitzer neuer Rechnungen: der Benutzer, sonst die Browsersitzung."""
    return current_user() or session_id()


def open_in_editor(cfg: dict, name: str) -> None:
    """Konfiguration (z. B. einer früheren Rechnung) in den Editor übernehmen; Felder beginnen neu."""
    st.session_state["fg_cfg"] = cfg
    st.session_state["fg_cfg_name"] = f"rechnung:{name}"
    st.session_state["fg_cfg_label"] = name
    st.session_state["fg_editor_source"] = "Neu"  # sonst lädt eine gewählte Beispielquelle ihre Datei erneut
    st.session_state["fg_gen"] = st.session_state.get("fg_gen", 0) + 1
    st.session_state.pop("fg_editor_error", None)


def uploads_dir():
    """Hochgeladene STEP-Dateien liegen unter ``FG_GUI_DATA_DIR/uploads``."""
    return settings().data_dir / "uploads"


def submit_job(label: str, fn, cfg: dict, *, kind: str, **kwargs) -> Job:
    """Reicht eine Rechnung für ``cfg`` ein. CAD-Dateien dürfen nur aus Uploads oder dem Beispielverzeichnis kommen.

    Wirft ``cad.CadFileError``, wenn eine Datei fehlt oder außerhalb liegt. Gerechnet und gespeichert wird die
    Konfiguration mit aufgelösten absoluten Pfaden.
    """
    s = settings()
    sweep_if_due()
    roots = [uploads_dir()] + ([s.examples_dir] if s.examples_dir else [])
    prepared = cad.resolve_files(cfg, bases=roots, roots=roots)
    return job_manager().submit(label, fn, prepared, owner=owner_id(), kind=kind, config=prepared, **kwargs)
