"""Einstieg der Streamlit-App: ``streamlit run src/fg_gui/app.py`` bzw. ``fg-gui``."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from fg_gui import __version__
from fg_gui.state import current_user, job_manager, restore_draft, save_draft, session_id, solver_info

PAGES = Path(__file__).parent / "pages"

st.set_page_config(page_title="FourierGrating", page_icon="🌈", layout="wide")

session_id()  # trägt ?s=<Kennung> in die Adresszeile ein
restore_draft()
nav = st.navigation(
    {
        "Rechnen": [
            st.Page(PAGES / "editor.py", title="Editor", icon="✏️", default=True),
            st.Page(PAGES / "single.py", title="Einzelrechnung", icon="▶️"),
            st.Page(PAGES / "scan.py", title="Scan", icon="📈"),
            st.Page(PAGES / "nearfield.py", title="Nahfeld", icon="🔦"),
            st.Page(PAGES / "cad.py", title="CAD", icon="🧊"),
            st.Page(PAGES / "optimize.py", title="Optimierung", icon="🎯"),
        ],
        "Betrieb": [
            st.Page(PAGES / "jobs.py", title="Rechnungen", icon="📋"),
            st.Page(PAGES / "system.py", title="System", icon="🖥️"),
        ],
    }
)

with st.sidebar:
    info = solver_info()
    if info.available:
        st.caption(f"FourierGrating {info.version} · Kern: {info.core_variant or '?'}")
    else:
        st.caption("FourierGrating: nicht installiert")
    if user := current_user():
        st.caption(f"Angemeldet: {user}")
    st.caption(f"Sitzung: `{session_id()}` (steht in der Adresszeile – Adresse merken, um später weiterzuarbeiten)")
    st.caption(f"GUI {__version__} · aktive Rechnungen: {job_manager().busy()}")

try:
    nav.run()
finally:
    save_draft()
