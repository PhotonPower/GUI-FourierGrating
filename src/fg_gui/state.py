"""Gemeinsame Ressourcen und Sitzungszustand für die Seiten.

Schlüssel in ``st.session_state`` beginnen mit ``fg_`` (AGENTS.md, Abschnitt 4).
"""

from __future__ import annotations

import uuid

import streamlit as st

from . import settings as _settings
from . import solver
from .jobs import JobManager


@st.cache_resource
def settings() -> _settings.Settings:
    return _settings.load()


@st.cache_resource
def job_manager() -> JobManager:
    s = settings()
    return JobManager(workers=s.workers, history=s.job_history)


@st.cache_data(ttl=60)
def solver_info() -> solver.SolverInfo:
    return solver.info()


def session_id() -> str:
    """Kennung der Browsersitzung (Zuordnung der Jobs; keine Anmeldung)."""
    if "fg_session" not in st.session_state:
        st.session_state["fg_session"] = uuid.uuid4().hex[:8]
    return st.session_state["fg_session"]
