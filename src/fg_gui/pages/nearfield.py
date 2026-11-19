"""Seite „Nahfeld“: Schnitte mit ``fouriergrating.near_field`` rechnen, darstellen und exportieren (G3)."""

import streamlit as st

from fg_gui import config_form as cf
from fg_gui import config_io, h5export, nearfield, solver
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
line_mode, line_y = False, 0.0

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
        if two_d:
            mode = st.radio(
                "Rechnen",
                ["maps", "line"],
                format_func=lambda m: "Karten (x–y und x–z)" if m == "maps" else "Nur eine Linie entlang x",
                horizontal=True,
                key="fg_nf_mode",
                help="„Linie“ rechnet genau eine Linie bei y und z₀ (vertikaler Schnitt mit ny = 1, nz = 1): "
                "schneller, sparsamer und an der exakten Position, ohne Rundung auf ein Gitter.",
            )
            line_mode = mode == "line"
            if line_mode:
                line_y = st.number_input(
                    "Linie: y (µm); z = z₀ des vertikalen Schnitts, Auflösung über nx",
                    value=float(block.get("horizontal_y_um", 0.0)),
                    format="%.10g",
                    key="fg_nf_line_y",
                )
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
    if line_mode:
        snapshot["nearfield"] = nearfield.line_block(snapshot["nearfield"], line_y)
    label = f"Nahfeld (Linie): {name}" if line_mode else f"Nahfeld: {name}"
    try:
        st.session_state["fg_nf_job"] = submit_job(label, solver.near_field, snapshot, kind="nearfield").id
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
cuts = nearfield.visible_cuts(nf)
if not cuts:
    st.warning("Das Ergebnis enthält keinen Schnitt.")
    st.stop()

c = st.columns(4)
cut_name = c[0].selectbox("Schnitt", cuts, format_func=nearfield.CUT_NAMES.get)
cut = nearfield.squeeze_line(nf[cut_name])
if nearfield.is_line_run(nf):
    run_cfg = job_manager().config(job.id) or {}
    z_line = (run_cfg.get("nearfield") or {}).get("vertical_z_um", 0.0)
    st.caption(
        f"Gerechnete Linie entlang x bei y = {float(nf['vertical']['axis2_um'][0]):.6g} µm und z = {z_line:.6g} µm "
        f"({len(cut['axis1_um'])} Punkte). Der Export (.zip/.h5) enthält die Rohdaten beider Schnitte."
    )
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
c[2].download_button(
    "Rechnung (.h5)",
    h5export.run_h5(job, job_manager().store),
    file_name=f"nahfeld_{job.id}.h5",
    mime="application/x-hdf5",
)
if nearfield.is_map(cut):
    with st.expander("1D-Schnitt (Linie) aus dieser Karte"):
        (n1, x1), (n2, x2) = nearfield.axes(cut)
        st.caption(
            "Zeile bzw. Spalte der berechneten Karte am nächstgelegenen Gitterpunkt – keine Interpolation, keine neue "
            "Rechnung. Für eine feinere Linie nx/ny bzw. nz in den Einstellungen erhöhen."
        )
        c = st.columns(2)
        along = c[0].radio(
            "Richtung",
            [0, 1],
            format_func=lambda i: (
                f"Linie entlang {n1} bei festem {n2}" if i == 0 else f"Linie entlang {n2} bei festem {n1}"
            ),
            key="fg_nf_line_dir",
        )
        fix_name, fix_axis = (n2, x2) if along == 0 else (n1, x1)
        lo, hi = float(fix_axis.min()), float(fix_axis.max())
        at = c[1].number_input(
            f"Fester Wert {fix_name} (µm)", value=min(max(0.0, lo), hi), min_value=lo, max_value=hi, format="%.4f",
            key=f"fg_nf_line_at_{along}",
        )  # fmt: skip
        line, actual = nearfield.line_of_map(cut, along, float(at))
        st.caption(
            f"Gewählt: {fix_name} = {actual:.6g} µm "
            f"(Gitterpunkt {nearfield.nearest(fix_axis, float(at)) + 1} von {len(fix_axis)})"
        )
        df = nearfield.line_frame(line, quantity, part)
        st.line_chart(df, x=df.columns[0], y=df.columns[1])
        st.download_button(
            "Linie als Tabelle (.csv, alle Größen)",
            nearfield.line_table(line, fix_name, actual).to_csv(index=False).encode(),
            file_name=f"{cut_name}_linie_{fix_name}_{actual:.4g}.csv".replace("-", "m"),
            mime="text/csv",
        )

with st.expander("Angaben zum Schnitt"):
    st.json(nearfield.describe(cut))
    st.json(cut.get("meta", {}), expanded=False)
