"""Seite „Rechnungen“: alle Rechnungen dieses Serverprozesses."""

import time

import pandas as pd
import streamlit as st

from fg_gui.state import job_manager, session_id

st.title("Rechnungen")
only_mine = st.toggle("Nur diese Sitzung", value=True)


@st.fragment(run_every=2.0)
def table() -> None:
    jobs = job_manager().jobs(owner=session_id() if only_mine else None)
    if not jobs:
        st.info("Keine Rechnungen.")
        return
    st.dataframe(
        pd.DataFrame(
            {
                "ID": [j.id for j in jobs],
                "Bezeichnung": [j.label for j in jobs],
                "Status": [j.status for j in jobs],
                "Eingereicht": [time.strftime("%H:%M:%S", time.localtime(j.submitted)) for j in jobs],
                "Laufzeit [s]": [round(j.runtime, 2) if j.runtime is not None else None for j in jobs],
                "Fehler": [j.error for j in jobs],
            }
        ),
        hide_index=True,
        width="stretch",
    )


table()
