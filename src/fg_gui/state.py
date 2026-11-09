"""Gemeinsame Ressourcen und Sitzungszustand für die Seiten.

Schlüssel in ``st.session_state`` beginnen mit ``fg_`` (AGENTS.md, Abschnitt 4).
"""

from __future__ import annotations

import json
import re
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
        return housekeeping.sweep(
            jm or job_manager(), uploads_dir(), s.retention_days, s.max_runs, sessions=drafts_dir()
        )


def sweep_if_due() -> None:
    if time.time() - _last_sweep > SWEEP_INTERVAL:
        sweep_now()


@st.cache_data(ttl=60)
def solver_info() -> solver.SolverInfo:
    return solver.info()


SESSION_RE = re.compile(r"^[0-9a-f]{8,32}$")


def session_id() -> str:
    """Kennung der Arbeitssitzung; steht als ``?s=…`` in der Adresszeile.

    Wer die Adresse (Lesezeichen, anderes Gerät, nach Neustart) wieder öffnet, arbeitet an denselben Rechnungen und
    derselben Konfiguration weiter. Wer die Kennung kennt, sieht diese Rechnungen: sie ist ein Zugangsschlüssel.
    """
    if "fg_session" not in st.session_state:
        wanted = st.query_params.get("s", "")
        st.session_state["fg_session"] = wanted if SESSION_RE.match(wanted) else uuid.uuid4().hex[:12]
    sid = st.session_state["fg_session"]
    if st.query_params.get("s") != sid:  # auch nach einem Seitenwechsel wieder eintragen
        st.query_params["s"] = sid
    return sid


def drafts_dir():
    return settings().data_dir / "sessions"


def save_draft() -> None:
    """Merkt sich die Konfiguration im Editor je Sitzung (nur bei Änderung), damit sie nach Neustart wieder da ist."""
    cfg = st.session_state.get("fg_cfg")
    if not isinstance(cfg, dict) or "fg_session" not in st.session_state:
        return
    data = {
        "config": cfg,
        "name": st.session_state.get("fg_cfg_name", ""),
        "label": st.session_state.get("fg_cfg_label", ""),
    }
    text = json.dumps(data, ensure_ascii=False, default=str)
    if st.session_state.get("fg_draft_saved") == text:
        return
    try:
        from .store import _write_json

        drafts_dir().mkdir(parents=True, exist_ok=True)
        _write_json(drafts_dir() / f"{st.session_state['fg_session']}.json", data)
        st.session_state["fg_draft_saved"] = text
    except OSError:
        pass  # Zugabe: eine volle Platte soll die Bedienung nicht stören


def restore_draft() -> None:
    """Lädt die gemerkte Konfiguration der Sitzung, falls im Editor noch keine liegt."""
    if "fg_cfg" in st.session_state:
        return
    f = drafts_dir() / f"{session_id()}.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(data, dict) and isinstance(data.get("config"), dict):
        st.session_state["fg_cfg"] = data["config"]
        st.session_state["fg_cfg_name"] = data.get("name") or "wiederhergestellt"
        if data.get("label"):
            st.session_state["fg_cfg_label"] = data["label"]
        st.session_state["fg_gen"] = st.session_state.get("fg_gen", 0) + 1


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
