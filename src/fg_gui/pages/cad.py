"""Seite „CAD“: STEP-Datei laden, Körper Materialien zuordnen, Geometrie prüfen, Schnitte ansehen (G5)."""

import streamlit as st

from fg_gui import cad, solver
from fg_gui import config_form as cf
from fg_gui.jobs import DONE, FAILED
from fg_gui.state import job_manager, settings, solver_info, submit_job, uploads_dir
from fg_gui.widgets import choice, integer, number, text_list, wkey

st.title("CAD")
st.caption(
    "Eine STEP-Datei beschreibt den Inhalt der Einheitszelle (ein benannter Körper je Material, Koordinaten in µm "
    "empfohlen; docs/cad.md in FourierGrating). FourierGrating zerlegt sie entlang y in Bänder. Hier lädst du die "
    "Datei, ordnest die Körper Materialien zu und prüfst die Geometrie."
)

if "fg_cfg" not in st.session_state:
    st.info("Zuerst im *Editor* eine Konfiguration laden oder anlegen.")
    st.stop()

info = solver_info()
if not info.available:
    st.warning("FourierGrating ist nicht installiert (Seite „System“).")
    st.stop()
if not info.cad_available:
    st.warning(
        "Dieses FourierGrating wurde ohne den CAD-Slicer gebaut (`FG_ENABLE_NURBFORGE`, docs/cad.md); "
        "CAD-Schichten sind nicht verfügbar."
    )
    st.stop()

cfg = st.session_state["fg_cfg"]
name = st.session_state.get("fg_cfg_label") or st.session_state["fg_cfg_name"].split(":", 1)[-1]
layers = cfg.setdefault("layers", []) if isinstance(cfg.get("layers"), list) else []
mat_names = list(cfg.get("materials") or {})
s = settings()


def bump() -> None:
    st.session_state["fg_gen"] = st.session_state.get("fg_gen", 0) + 1


# ---------------------------------------------------------------- Schicht wählen oder anlegen
found = cad.cad_layers(cfg)
if not found:
    st.write("Die Konfiguration hat noch keine CAD-Schicht.")
    if st.button("CAD-Schicht hinzufügen"):
        layers.append(cad.new_layer(mat_names))
        cfg["layers"] = layers
        bump()
        st.rerun()
    st.stop()

index = st.selectbox("CAD-Schicht", [i for i, _ in found], format_func=lambda i: f"Schicht {i}", key="fg_cad_layer")
layer = dict(found)[index]

# ---------------------------------------------------------------- STEP-Datei
st.subheader("STEP-Datei")
current = layer.get("file")
if isinstance(current, str):
    st.write(f"Aktuell: `{current}`")
elif layer.get("step"):
    st.write("Aktuell: eingebetteter Dateiinhalt (`step`)")
examples = cad.list_steps(s.examples_dir)
c = st.columns(2)
up = c[0].file_uploader("Hochladen (.step, .stp)", type=["step", "stp"], key=f"fg_cad_up_{index}")
if up is not None:
    try:
        path = cad.save_upload(up.getvalue(), uploads_dir())
        if layer.get("file") != str(path):
            layer["file"], _ = str(path), layer.pop("step", None)
            bump()
            st.rerun()
    except cad.CadFileError as e:
        c[0].error(str(e))
if examples:
    pick = c[1].selectbox(
        "oder Beispiel",
        [None, *examples],
        format_func=lambda p: "–" if p is None else str(p.relative_to(s.examples_dir)),
    )
    if pick is not None and layer.get("file") != str(pick) and c[1].button("Verwenden"):
        layer["file"] = str(pick)
        layer.pop("step", None)
        bump()
        st.rerun()


def step_text() -> str:
    f = layer.get("file")
    if isinstance(f, str):
        try:
            roots = [uploads_dir()] + ([s.examples_dir] if s.examples_dir else [])
            p = cad.resolve_files({"layers": [layer]}, roots, roots)["layers"][0]["file"]
            return open(p, encoding="utf-8", errors="replace").read()
        except (cad.CadFileError, OSError):
            return ""
    return layer.get("step", "") if isinstance(layer.get("step"), str) else ""


names = cad.body_names(step_text())
if names:
    st.caption("Körper in der Datei: " + ", ".join(n or f"#{i}" for i, n in enumerate(names)))

# ---------------------------------------------------------------- Einstellungen
st.subheader("Einstellungen")
_detached: dict[str, dict] = {}


def nested(key: str) -> dict:
    v = layer.get(key)
    return v if isinstance(v, dict) else _detached.setdefault(key, {})


c = st.columns(3)
choice(c[0], "Einheit der Datei", layer, "unit", cad.UNITS, "auto")
axes = nested("axes")
choice(c[1], "CAD-Achse für y (Stapelrichtung)", axes, "y", cad.AXES, "+Z")
choice(c[2], "CAD-Achse für x", axes, "x", cad.AXES, "+X")
c = st.columns(2)
if "y_range_um" in layer or c[0].checkbox("y-Bereich festlegen", key=wkey("cad_yr", index)):
    text_list(c[0], "y-Bereich (µm, von, bis)", layer, "y_range_um")
text_list(c[1], "Zellursprung x₀, z₀ (µm; leer = Minimum der Körper)", layer, "cell_origin_um")
if layer.get("cell_origin_um") == []:
    layer.pop("cell_origin_um")
c = st.columns(3)
bg_options = ["superstrate", "substrate", *mat_names]
choice(c[0], "Material außerhalb der Körper", layer, "background", bg_options, "superstrate")
choice(c[1], "Überlappende Körper", layer, "overlap", cad.OVERLAPS, "error")
pu = c[2].checkbox("Mit periodischen Bildern vereinigen", value=bool(layer.get("periodic_union", False)))
cf.assign(layer, "periodic_union", pu, False)

st.markdown("**Körper → Material**")
rows = cad.bodies_rows(layer, names)
if rows:
    import pandas as pd

    edited = st.data_editor(
        pd.DataFrame(rows, columns=["Körper", "Material"]),
        hide_index=True,
        num_rows="fixed",
        key=wkey("cad_bodies", index),
        column_config={
            "Körper": st.column_config.TextColumn(disabled=True),
            "Material": st.column_config.SelectboxColumn(options=["", *mat_names]),
        },
    )
    cad.bodies_apply(layer, edited.to_dict("records"))
else:
    st.info("Noch keine Körper: STEP-Datei wählen oder die Zuordnung im Reiter *JSON* des Editors eintragen.")

with st.expander("Zerlegung in Bänder (slicing) und Normalenfeld"):
    sl = nested("slicing")
    c = st.columns(3)
    number(c[0], "Kritische Höhen zusammenlegen (µm)", sl, "critical_tol_um", 1e-6, min_value=0.0)
    number(c[1], "Dünnstes Band (µm)", sl, "min_band_um", 1e-5, min_value=0.0)
    integer(c[2], "RCWA-Scheiben je y-variablem Band", sl, "rcwa_slices", 40, minimum=1)
    c = st.columns(2)
    choice(c[0], "y-Interpolation", sl, "y_interpolation", cad.Y_INTERPOLATIONS, "none")
    integer(c[1], "Tschebyschow-Knoten", sl, "chebyshev_nodes", 16, minimum=2)
    nfield = nested("normal_field")
    c = st.columns(2)
    integer(c[0], "Normalenfeld: Raster", nfield, "grid", 512, minimum=8)
    number(c[1], "Normalenfeld: sigma", nfield, "sigma", 3.0, min_value=0.0)
    choice(st, "Faktorisierung", layer, "factorization", ["auto", "FFF_sym", "FFF_iso", "FFF_B", "laurent"], "auto")

for key, d in _detached.items():
    if d:
        layer[key] = d

# ---------------------------------------------------------------- Prüfen
st.subheader("Geometrie prüfen")
extra = st.text_input("Weitere Schnitthöhen y (µm, optional; je Band wird die Mitte immer gezeigt)", key=wkey("cad_y"))
if st.button("Prüfen", type="primary"):
    try:
        heights = tuple(float(v) for v in cf.parse_list(extra))
    except (cf.FormError, ValueError) as e:
        st.error(f"Schnitthöhen: {e}")
    else:
        try:
            job = submit_job(f"CAD-Prüfung: {name}", solver.cad_check, cfg, kind="cad", extra_heights=heights)
            st.session_state["fg_cad_job"] = job.id
        except cad.CadFileError as e:
            st.error(str(e))


@st.fragment(run_every=1.0)
def wait_for(job_id: str) -> None:
    job = job_manager().get(job_id)
    if job is None or job.status in (DONE, FAILED):
        st.rerun()
    st.info(f"{job.label}: {job.status} …")


job = job_manager().get(st.session_state.get("fg_cad_job", ""))
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

data = job.result()
report, previews = data["report"], data.get("previews", [])
(st.success if report.get("ok") else st.error)(
    f"{job.label}: "
    + ("Geometrie in Ordnung" if report.get("ok") else "Geometrie hat Fehler")
    + f" ({job.runtime:.2f} s)"
)
findings = cad.findings_rows(report)
if findings:
    st.dataframe(findings, hide_index=True, width="stretch")
bands = cad.bands_rows(report)
if bands:
    st.markdown("**Bänder** (von unten nach oben)")
    st.dataframe(bands, hide_index=True, width="stretch")
if previews:
    st.markdown("**Schnittvorschau**")
    pick = st.selectbox(
        "Höhe y (µm)",
        range(len(previews)),
        format_func=lambda i: f"y = {previews[i]['y_um']:.6g}",
        key=wkey("cad_prev"),
    )
    pv = previews[pick]
    if pv.get("svg"):
        st.image(pv["svg"], width=420)
        st.download_button(
            "Schnitt als SVG", pv["svg"], file_name=f"schnitt_y{pv['y_um']:.4g}.svg", mime="image/svg+xml"
        )
    else:
        st.warning(pv.get("error", "Kein Schnitt."))
with st.expander("Bericht (JSON)"):
    st.json(report, expanded=False)
