"""Einstieg der Streamlit-App: ``streamlit run src/fg_gui/app.py`` bzw. ``fg-gui``."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from fg_gui import __version__
from fg_gui.state import job_manager, solver_info

PAGES = Path(__file__).parent / "pages"

st.set_page_config(page_title="FourierGrating", page_icon="🌈", layout="wide")

nav = st.navigation(
    {
        "Rechnen": [st.Page(PAGES / "single.py", title="Einzelrechnung", icon="▶️", default=True)],
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
    st.caption(f"GUI {__version__} · aktive Rechnungen: {job_manager().busy()}")

nav.run()
