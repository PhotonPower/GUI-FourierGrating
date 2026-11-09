"""Seite „Rechnungen“: alle Rechnungen dieses Serverprozesses, gespeichert über Neustarts hinweg (G4)."""

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from fg_gui import config_io, estimate, results
from fg_gui.jobs import CANCELLED, DONE, FAILED, RUNNING, WAITING
from fg_gui.state import job_manager, open_in_editor, session_id
from fg_gui.store import KIND_LABELS

PAGES = Path(__file__).parent

st.title("Rechnungen")
st.caption(
    "Alle Rechnungen bleiben nach einem Neustart des Servers erhalten (`FG_GUI_DATA_DIR/runs`). Es läuft jeweils "
    "eine Rechnung zugleich; die übrigen warten in der Reihenfolge des Einreichens. Wartende lassen sich abbrechen, "
    "eine laufende nicht (FourierGrating bietet keinen Abbruch)."
)
only_mine = st.toggle("Nur diese Sitzung", value=True)
jm = job_manager()


def fmt_time(t: float | None) -> str:
    return time.strftime("%d.%m. %H:%M:%S", time.localtime(t)) if t else "–"


@st.fragment(run_every=2.0)
def table() -> None:
    jobs = jm.jobs(owner=session_id() if only_mine else None)
    if not jobs:
        st.info("Keine Rechnungen.")
        return
    st.dataframe(
        pd.DataFrame(
            {
                "ID": [j.id for j in jobs],
                "Art": [KIND_LABELS.get(j.kind, j.kind) for j in jobs],
                "Bezeichnung": [j.label for j in jobs],
                "Status": [j.status for j in jobs],
                "Platz": [jm.queue_position(j.id) or None for j in jobs],
                "Eingereicht": [fmt_time(j.submitted) for j in jobs],
                "Laufzeit [s]": [round(j.runtime, 2) if j.runtime is not None else None for j in jobs],
                "Fehler": [j.error for j in jobs],
            }
        ),
        hide_index=True,
        width="stretch",
    )


table()

# ---------------------------------------------------------------- Einzelne Rechnung
jobs = jm.jobs(owner=session_id() if only_mine else None)
if not jobs:
    st.stop()

st.subheader("Einzelne Rechnung")
by_id = {j.id: j for j in jobs}
job_id = st.selectbox(
    "Rechnung",
    list(by_id),
    format_func=lambda i: f"{by_id[i].id} · {by_id[i].label} · {by_id[i].status}",
    key="fg_jobs_selected",
)
job = jm.get(job_id)
if job is None:
    st.stop()

cols = st.columns(4)
cols[0].metric("Status", job.status)
pos = jm.queue_position(job.id)
cols[1].metric("Warteschlange", f"Platz {pos}" if pos else "–")
cols[2].metric("Laufzeit", f"{job.runtime:.2f} s" if job.runtime is not None else "–")
if jm.store is not None:
    cols[3].metric("Auf der Festplatte", estimate.format_bytes(jm.store.size_bytes(job.id)))

cfg = jm.config(job.id)
if cfg is not None:
    e = estimate.summary(cfg)
    st.caption(
        f"Abschätzung zur Konfiguration: {e['scan_points'] * e['sweep_values']} Rechnung(en) · n = {e['matrix_size']} "
        f"· Speicher grob {e['memory_text']}"
    )

b = st.columns(5)
if b[0].button("Abbrechen", disabled=job.status != WAITING, help="Nur wartende Rechnungen"):
    if jm.cancel(job.id):
        st.rerun()
    st.warning("Die Rechnung hat inzwischen begonnen und kann nicht abgebrochen werden.")
if b[1].button("Löschen", disabled=job.status in (WAITING, RUNNING), help="Entfernt auch die gespeicherten Dateien"):
    jm.delete(job.id)
    st.session_state.pop("fg_jobs_selected", None)
    st.rerun()
if b[2].button("Im Editor öffnen", disabled=cfg is None):
    open_in_editor(cfg, job.label)
    st.switch_page(PAGES / "editor.py")
if job.status == DONE and job.kind == "scan" and b[3].button("Im Scan öffnen"):
    runs = st.session_state.setdefault("fg_scan_runs", [])
    if job.id not in {r["id"] for r in runs}:
        runs.append({"id": job.id, "title": job.label})
    st.switch_page(PAGES / "scan.py")
if job.status == DONE and job.kind == "cad" and b[3].button("Im CAD öffnen"):
    st.session_state["fg_cad_job"] = job.id
    st.switch_page(PAGES / "cad.py")
if job.status == DONE and job.kind == "cad" and b[3].button("Im CAD öffnen"):
    st.session_state["fg_cad_job"] = job.id
    st.switch_page(PAGES / "cad.py")
if job.status == DONE and job.kind == "nearfield" and b[3].button("Im Nahfeld öffnen"):
    st.session_state["fg_nf_job"] = job.id
    st.switch_page(PAGES / "nearfield.py")

if job.status == FAILED:
    st.error(job.error)
elif job.status == CANCELLED:
    st.info("Abgebrochen.")
if job.traceback:
    with st.expander("Details zum Fehler"):
        st.code(job.traceback)

if job.status == DONE and job.kind == "solve":
    res = job.result()
    tot = results.totals(res)
    for c, (k, v) in zip(st.columns(len(tot)), tot.items(), strict=True):
        c.metric(k, f"{v:.6g}")
    st.dataframe(results.orders_frame(res), hide_index=True, width="stretch")
    with st.expander("Diagnose"):
        st.json(res.diagnostics or {})
if cfg is not None:
    with st.expander("Konfiguration"):
        st.code(config_io.dumps(cfg), language="json")
