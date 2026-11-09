"""Gemeinsame Ressourcen und Sitzungszustand für die Seiten.

Schlüssel in ``st.session_state`` beginnen mit ``fg_`` (AGENTS.md, Abschnitt 4).
"""

from __future__ import annotations

import uuid

import streamlit as st

from . import cad, solver
from . import settings as _settings
from .jobs import Job, JobManager
from .store import RunStore


@st.cache_resource
def settings() -> _settings.Settings:
    return _settings.load()


@st.cache_resource
def job_manager() -> JobManager:
    s = settings()
    return JobManager(workers=s.workers, history=s.job_history, store=RunStore(s.data_dir / "runs"))


@st.cache_data(ttl=60)
def solver_info() -> solver.SolverInfo:
    return solver.info()


def session_id() -> str:
    """Kennung der Browsersitzung (Zuordnung der Jobs; keine Anmeldung)."""
    if "fg_session" not in st.session_state:
        st.session_state["fg_session"] = uuid.uuid4().hex[:8]
    return st.session_state["fg_session"]


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
    roots = [uploads_dir()] + ([s.examples_dir] if s.examples_dir else [])
    prepared = cad.resolve_files(cfg, bases=roots, roots=roots)
    return job_manager().submit(label, fn, prepared, owner=session_id(), kind=kind, config=prepared, **kwargs)
