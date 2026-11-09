"""Seite „Einzelrechnung“: Konfiguration laden, erster Scanpunkt mit ``fouriergrating.solve`` (G0)."""

import streamlit as st

from fg_gui import config_io, results, solver
from fg_gui.jobs import DONE, FAILED
from fg_gui.state import job_manager, session_id, settings, solver_info

st.title("Einzelrechnung")
st.caption(
    "Konfiguration im JSON-Format von FourierGrating (docs/config_format.md). Gerechnet wird der erste Scanpunkt; "
    "Scans, Sweeps und Nahfeld folgen in G2/G3 (docs/roadmap.md)."
)

# ---------------------------------------------------------------- Konfiguration wählen
examples = config_io.list_examples(settings().examples_dir)
sources = (["Beispiel"] if examples else []) + ["Datei hochladen"]
source = st.radio("Quelle", sources, horizontal=True)

cfg, name = None, ""
try:
    if source == "Beispiel":
        path = st.selectbox("Beispiel", examples, format_func=lambda p: p.name)
        if path is not None:
            cfg, name = config_io.parse(path.read_bytes()), path.name
    else:
        up = st.file_uploader("Konfiguration (.json)", type=["json"])
        if up is not None:
            cfg, name = config_io.parse(up.getvalue()), up.name
except config_io.ConfigError as e:
    st.error(str(e))

if cfg is None:
    st.stop()

cols = st.columns([1, 2])
with cols[0]:
    st.table({k: [str(v)] for k, v in config_io.summary(cfg).items()})
with cols[1], st.expander("JSON", expanded=False):
    st.json(cfg)

# ---------------------------------------------------------------- rechnen
info = solver_info()
if not info.available:
    st.warning("FourierGrating ist nicht installiert – Rechnen nicht möglich (Seite „System“).")
    st.stop()

if st.button("Rechnen", type="primary"):
    job = job_manager().submit(name or "Konfiguration", solver.solve, cfg, owner=session_id())
    st.session_state["fg_single_job"] = job.id


def show_result(job) -> None:
    if job.status == FAILED:
        st.error(job.error)
        with st.expander("Details"):
            st.code(job.traceback)
        return
    res = job.result()
    st.success(f"{job.label}: fertig in {job.runtime:.2f} s")
    tot = results.totals(res)
    for c, (k, v) in zip(st.columns(len(tot)), tot.items(), strict=True):
        c.metric(k, f"{v:.6g}")
    df = results.orders_frame(res)
    st.dataframe(df, hide_index=True, width="stretch")
    if not df.empty:
        chart = df.assign(Ordnung=df["Seite"] + df["n"].astype(str) + "," + df["m"].astype(str))
        st.bar_chart(chart, x="Ordnung", y="Effizienz")
    warnings = (res.diagnostics or {}).get("warnings")
    if warnings:
        st.warning("\n".join(map(str, warnings)))
    with st.expander("Diagnose"):
        st.json(res.diagnostics or {})
    st.download_button(
        "Tabelle als CSV",
        df.to_csv(index=False).encode(),
        file_name=(job.label.rsplit(".", 1)[0] or "ergebnis") + "_efficiencies.csv",
        mime="text/csv",
    )


@st.fragment(run_every=1.0)
def wait_for(job_id: str) -> None:
    """Fragt nur den Status ab; sobald der Job fertig ist, wird die ganze Seite neu aufgebaut."""
    job = job_manager().get(job_id)
    if job is None or job.status in (DONE, FAILED):
        st.rerun()
    st.info(f"{job.label}: {job.status} …")


current = job_manager().get(st.session_state.get("fg_single_job", ""))
if current is not None:
    if current.status in (DONE, FAILED):
        show_result(current)
    else:
        wait_for(current.id)
