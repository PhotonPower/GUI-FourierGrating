"""Seite „Scan“: alle Scanpunkte und Sweep-Werte mit ``fouriergrating.solve_scan``, Kurven und Vergleich (G2)."""

import streamlit as st

from fg_gui import config_io, scans, solver
from fg_gui.cad import CadFileError
from fg_gui.jobs import DONE, FAILED
from fg_gui.state import job_manager, solver_info, submit_job
from fg_gui.widgets import show_estimate

st.title("Scan")
st.caption(
    "Rechnet alle Werte von λ, φ, ψ, δ und den Sweep der Konfiguration aus dem Editor (Reiter *Einfall*; Sweep im "
    "Reiter *JSON*). Gerechnet wird in der Reihenfolge der Warteschlange; mehrere Scanpunkte laufen parallel."
)

if "fg_cfg" not in st.session_state:
    st.info("Zuerst im *Editor* eine Konfiguration laden oder anlegen.")
    st.stop()

cfg = st.session_state["fg_cfg"]
name = st.session_state.get("fg_cfg_label") or st.session_state["fg_cfg_name"].split(":", 1)[-1]
info = solver_info()
if not info.available:
    st.warning("FourierGrating ist nicht installiert – Rechnen nicht möglich (Seite „System“).")
    st.stop()

runs: list[dict] = st.session_state.setdefault("fg_scan_runs", [])
st.write(f"Konfiguration: **{name}**")
show_estimate(cfg)
if st.button("Scan rechnen", type="primary"):
    snapshot = config_io.parse(config_io.dumps(cfg))  # Kopie: Bearbeiten im Editor ändert den Lauf nicht
    title = f"Scan {len(runs) + 1}: {name}"
    try:
        job = submit_job(title, solver.solve_scan, snapshot, kind="scan")
        runs.append({"id": job.id, "title": title})
    except CadFileError as e:
        st.error(str(e))


@st.fragment(run_every=1.0)
def wait_for(job_id: str) -> None:
    job = job_manager().get(job_id)
    if job is None or job.status in (DONE, FAILED):
        st.rerun()
    st.info(f"{job.label}: {job.status} …")


jobs = {r["id"]: job_manager().get(r["id"]) for r in runs}
for r in runs:
    j = jobs[r["id"]]
    if j is not None and j.status not in (DONE, FAILED):
        wait_for(j.id)
    elif j is not None and j.status == FAILED:
        st.error(f"{r['title']}: {j.error}")
        with st.expander(f"Details – {r['title']}"):
            st.code(j.traceback)

done = [r for r in runs if jobs[r["id"]] is not None and jobs[r["id"]].status == DONE]
if not done:
    st.stop()

titles = {r["id"]: r["title"] for r in done}
main_id = st.selectbox("Rechnung", [r["id"] for r in reversed(done)], format_func=titles.get)
scan = jobs[main_id].result()
frame = scans.scan_frame(scan)
st.success(f"{titles[main_id]}: fertig in {jobs[main_id].runtime:.2f} s, {len(frame)} Zeilen")

# ---------------------------------------------------------------- Auswahl
axes = scans.varying_axes(frame)
if not axes:
    st.info(
        "Der Scan hat nur einen Punkt – keine Kurve möglich. Mehrere Werte (Reiter *Einfall*) oder einen Sweep angeben."
    )
else:
    c = st.columns(3)
    x = c[0].selectbox("x-Achse", axes, format_func=scans.AXES.get)
    quantity = c[1].selectbox("Größe", list(scans.QUANTITIES), format_func=scans.QUANTITIES.get)
    available = scans.order_labels(frame)
    default = [lab for lab in available if lab in ("R(0,0)", "T(0,0)")] or available[:2]
    orders = c[2].multiselect("Ordnungen", available, default=default)
    sums = tuple(st.multiselect("Summen", ["ΣR", "ΣT"], default=[]))
    fixed = {}
    choices = scans.fixed_choices(frame, x)
    if choices:
        cols = st.columns(len(choices))
        for col, (axis, values) in zip(cols, choices.items(), strict=True):
            fixed[axis] = col.selectbox(f"{scans.AXES[axis]} festhalten", values, key=f"fg_scan_fixed_{axis}")

    by_title = {r["title"]: r["id"] for r in done if r["id"] != main_id}
    chosen = st.multiselect("Vergleichen mit", list(by_title)) if by_title else []
    compare_ids = [by_title[c] for c in chosen]

    tables = {titles[main_id]: scans.curves(frame, x, orders, quantity, fixed, sums)}
    for rid in compare_ids:
        other = scans.scan_frame(jobs[rid].result())
        if x not in other.columns or x not in scans.varying_axes(other):
            st.warning(f"{titles[rid]}: ändert „{scans.AXES[x]}“ nicht, übersprungen.")
            continue
        tables[titles[rid]] = scans.curves(other, x, orders, quantity, fixed, sums)
    table = tables[titles[main_id]] if len(tables) == 1 else scans.compare(tables)
    if table.empty or table.shape[1] == 0:
        st.info("Ordnung oder Summe wählen.")
    else:
        st.line_chart(table, x_label=scans.AXES[x], y_label=scans.QUANTITIES[quantity])
        with st.expander("Kurvendaten"):
            st.dataframe(table, width="stretch")

# ---------------------------------------------------------------- Tabelle und Export
with st.expander("Alle Zeilen (Spalten wie ScanResult.columns)"):
    st.dataframe(scans.csv_frame(frame), hide_index=True, width="stretch")  # komplexe Amplituden als Re/Im
base = titles[main_id].split(": ", 1)[-1].rsplit(".", 1)[0] or "scan"
st.download_button(
    "efficiencies.csv",
    scans.to_csv(frame, getattr(scan, "sweep_parameter", "") or ""),
    file_name=f"{base}_efficiencies.csv",
    mime="text/csv",
)
