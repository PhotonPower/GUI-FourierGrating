"""Seite „Nahfeld“: Schnitte mit ``fouriergrating.near_field`` rechnen, darstellen und exportieren (G3)."""

import streamlit as st

from fg_gui import config_form as cf
from fg_gui import config_io, nearfield, solver
from fg_gui.cad import CadFileError
from fg_gui.jobs import DONE, FAILED
from fg_gui.state import job_manager, solver_info, submit_job
from fg_gui.widgets import choice, integer, number, text_list

st.title("Nahfeld")
st.caption(
    "Feldschnitte für den ersten Scanpunkt der Konfiguration aus dem Editor (Block `nearfield`, "
    "docs/config_format.md). Vertikaler Schnitt: Karte (x, y) bei z = z₀; horizontaler Schnitt: Linie (1D) bzw. "
    "Karte (x, z) (2D) bei y = y₀."
)

if "fg_cfg" not in st.session_state:
    st.info("Zuerst im *Editor* eine Konfiguration laden oder anlegen.")
    st.stop()

cfg = st.session_state["fg_cfg"]
name = st.session_state.get("fg_cfg_label") or st.session_state["fg_cfg_name"].split(":", 1)[-1]
two_d = cfg.get("dimension") == "2D"

# ---------------------------------------------------------------- Einstellungen (Block "nearfield")
block = cfg.get("nearfield")
with st.expander("Nahfeld-Einstellungen", expanded="fg_nf_job" not in st.session_state):
    if not isinstance(block, dict):
        st.write("Die Konfiguration hat noch keinen Block `nearfield`.")
        if st.button("Block mit Beispielwerten anlegen"):
            cfg["nearfield"] = nearfield.default_block(cfg.get("dimension", "1D"))
            st.session_state["fg_gen"] = st.session_state.get("fg_gen", 0) + 1
            st.rerun()
    else:
        c = st.columns(2)
        number(c[0], "Horizontaler Schnitt: y₀ (µm)", block, "horizontal_y_um", 0.0)
        number(c[1], "Vertikaler Schnitt: z₀ (µm)", block, "vertical_z_um", 0.0)
        text_list(st, "y-Bereich des vertikalen Schnitts (µm, von, bis)", block, "y_range_um")
        c = st.columns(4 if two_d else 3)
        integer(c[0], "nx (Punkte je Periode)", block, "nx", 400, minimum=2)
        integer(c[1], "ny", block, "ny", 300, minimum=2)
        integer(c[2], "Perioden", block, "periods", 1, minimum=1)
        if two_d:
            integer(c[3], "nz", block, "nz", 100, minimum=2)
        c = st.columns(2)
        options = list(dict.fromkeys([*nearfield.BLOCK_QUANTITIES, *block.get("quantities", [])]))
        chosen = c[0].multiselect("Größen", options, default=block.get("quantities", []), key=f"fg_nf_q_{id(block)}")
        cf.assign(block, "quantities", chosen, block.get("quantities", []))
        choice(c[1], "Rekonstruktion", block, "reconstruction", ["fff", "direct"], "fff")

info = solver_info()
if not info.available:
    st.warning("FourierGrating ist nicht installiert – Rechnen nicht möglich (Seite „System“).")
    st.stop()

if isinstance(block, dict) and st.button("Nahfeld rechnen", type="primary"):
    snapshot = config_io.parse(config_io.dumps(cfg))  # Kopie
    snapshot["nearfield"]["enabled"] = True  # die Seite verlangt das Nahfeld ausdrücklich
    try:
        st.session_state["fg_nf_job"] = submit_job(f"Nahfeld: {name}", solver.near_field, snapshot, kind="nearfield").id
    except CadFileError as e:
        st.error(str(e))


@st.fragment(run_every=1.0)
def wait_for(job_id: str) -> None:
    job = job_manager().get(job_id)
    if job is None or job.status in (DONE, FAILED):
        st.rerun()
    st.info(f"{job.label}: {job.status} …")


job = job_manager().get(st.session_state.get("fg_nf_job", ""))
if job is None:
    st.stop()
if job.status not in (DONE, FAILED):
    wait_for(job.id)
    st.stop()
if job.status == FAILED:
    st.error(job.error)
    with st.expander("Details"):
        st.code(job.traceback)
    st.stop()

# ---------------------------------------------------------------- Ergebnis
nf = job.result()
st.success(f"{job.label}: fertig in {job.runtime:.2f} s")
cuts = nearfield.cut_names(nf)
if not cuts:
    st.warning("Das Ergebnis enthält keinen Schnitt.")
    st.stop()

c = st.columns(4)
cut_name = c[0].selectbox("Schnitt", cuts, format_func=nearfield.CUT_NAMES.get)
cut = nf[cut_name]
available = nearfield.quantities(cut)
quantity = c[1].selectbox("Größe", available, format_func=nearfield.quantity_label)
complex_q = nearfield.is_complex(cut, quantity)
part = c[2].selectbox("Anteil", list(nearfield.PARTS), format_func=nearfield.PARTS.get, disabled=not complex_q)
contours = c[3].checkbox("Materialgrenzen", value=True, disabled=not nearfield.is_map(cut))

if nearfield.is_map(cut):
    fig = nearfield.figure(cut, quantity, part, contours)
    st.pyplot(fig, clear_figure=False)
    png = nearfield.png_bytes(fig)
else:
    df = nearfield.line_frame(cut, quantity, part)
    st.line_chart(df, x=df.columns[0], y=df.columns[1])
    png = None

c = st.columns(3)
c[0].download_button(
    "Alle Schnitte (.zip: .npy + meta.json)",
    nearfield.export_zip(nf),
    file_name="nearfield.zip",
    mime="application/zip",
)
if png is not None:
    c[1].download_button("Bild (.png)", png, file_name=f"{cut_name}_{quantity}_{part}.png", mime="image/png")
with st.expander("Angaben zum Schnitt"):
    st.json(nearfield.describe(cut))
    st.json(cut.get("meta", {}), expanded=False)
