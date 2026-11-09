"""Seite „Editor“: Konfiguration per Formular oder JSON bearbeiten und rechnen (G1)."""

import hashlib
import json

import pandas as pd
import streamlit as st

from fg_gui import config_form as cf
from fg_gui import config_io, results, solver
from fg_gui.jobs import DONE, FAILED
from fg_gui.state import job_manager, session_id, settings, solver_info
from fg_gui.widgets import choice, complex_input, integer, number, text_list

st.title("Editor")
st.caption(
    "Konfiguration für FourierGrating (docs/config_format.md) per Formular. Nicht angefasste Schlüssel bleiben "
    "unverändert; Schichttypen ohne Formular (2D, CAD) bearbeitest du als JSON. Einheiten: µm und Grad."
)


# ---------------------------------------------------------------- Sitzungszustand
def _load(cfg: dict, name: str) -> None:
    st.session_state["fg_cfg"] = cfg
    st.session_state["fg_cfg_name"] = name
    st.session_state["fg_gen"] = st.session_state.get("fg_gen", 0) + 1
    st.session_state.pop("fg_editor_error", None)


def _bump() -> None:
    st.session_state["fg_gen"] += 1


def _cfg() -> dict:
    return st.session_state["fg_cfg"]


def _k(*parts) -> str:
    return f"fg{st.session_state['fg_gen']}_" + "_".join(str(p) for p in parts)


# ---------------------------------------------------------------- Quelle
examples = config_io.list_examples(settings().examples_dir)
sources = ["Neu"] + (["Beispiel"] if examples else []) + ["Datei hochladen"]
with st.container(border=True):
    source = st.radio("Quelle", sources, horizontal=True, key="fg_editor_source")
    try:
        if source == "Neu":
            if st.button("Neue Konfiguration") or "fg_cfg" not in st.session_state:
                _load(cf.default_config(), "neu.json")
        elif source == "Beispiel":
            path = st.selectbox("Beispiel", examples, format_func=lambda p: p.name, key="fg_editor_example")
            if path is not None and st.session_state.get("fg_cfg_name") != "beispiel:" + path.name:
                _load(config_io.parse(path.read_bytes()), "beispiel:" + path.name)
        else:
            up = st.file_uploader("Konfiguration (.json)", type=["json"], key="fg_editor_upload")
            if up is not None and st.session_state.get("fg_cfg_name") != "datei:" + up.file_id:
                _load(config_io.parse(up.getvalue()), "datei:" + up.file_id)
                st.session_state["fg_cfg_label"] = up.name
    except config_io.ConfigError as e:
        st.error(str(e))

if "fg_cfg" not in st.session_state:
    st.stop()

cfg = _cfg()
label = st.session_state.get("fg_cfg_label") or st.session_state["fg_cfg_name"].split(":")[-1]
if st.session_state["fg_cfg_name"].startswith("beispiel:"):
    label = st.session_state["fg_cfg_name"].split(":", 1)[1]
_detached: dict[str, dict] = {}


def sub(name: str) -> dict:
    """Unterobjekt der Konfiguration; fehlt es, ein loses Objekt, das erst bei Änderung angehängt wird."""
    v = cfg.get(name)
    if isinstance(v, dict):
        return v
    return _detached.setdefault(name, {})


materials: dict = cfg["materials"] if isinstance(cfg.get("materials"), dict) else {}
mat_names = list(materials)
_job = job_manager().get(st.session_state.get("fg_editor_job", ""))
if _job is not None and _job.status == FAILED and "fg_editor_error" not in st.session_state:
    st.session_state["fg_editor_error"] = (_job.error, *cf.locate_error(_job.error or "", cfg))
err = st.session_state.get("fg_editor_error")  # (Meldung, Abschnitt, Schichtindex)


def section_error(section: str, layer: int | None = None) -> None:
    if err and err[1] == section and (layer is None or err[2] in (None, layer)):
        st.error(err[0])


# ---------------------------------------------------------------- Reiter
tab_basis, tab_inc, tab_mat, tab_layers, tab_solver, tab_json = st.tabs(
    ["Grundeinstellungen", "Einfall", "Materialien", "Schichten", "Löser", "JSON"]
)

with tab_basis:
    section_error("basis")
    c = st.columns(3)
    choice(c[0], "Dimension", cfg, "dimension", ["1D", "2D"], "1D")
    choice(c[1], "Löser", cfg, "solver", ["rcwa", "rk"], "rcwa")
    two_d = cfg.get("dimension") == "2D"
    st.subheader("Abbruch (Fourier-Ordnungen)")
    trunc = sub("truncation")
    c = st.columns(2)
    integer(c[0], "Nx", trunc, "Nx", 15)
    if two_d:
        integer(c[1], "Nz", trunc, "Nz", 0)
    st.subheader("Periode (µm)")
    per = sub("period_um")
    c = st.columns(2)
    number(c[0], "x", per, "x", 1.0, min_value=0.0)
    if two_d:
        number(c[1], "z", per, "z", 1.0, min_value=0.0)
    st.subheader("Umgebung")
    c = st.columns(2)
    choice(c[0], "Superstrat (oben)", cfg, "superstrate", mat_names)
    choice(c[1], "Substrat (unten)", cfg, "substrate", mat_names)

with tab_inc:
    section_error("incidence")
    st.caption("Zahl, Liste `0.5, 0.6, 0.7` oder Bereich `von:bis:Schritte`. Mehrere Werte ergeben einen Scan.")
    inc = sub("incidence")
    for key, name, default in (
        ("lambda_um", "Wellenlänge λ (µm)", 0.6328),
        ("phi_deg", "Einfallswinkel φ (°, zur y-Achse)", 0),
        ("psi_deg", "Azimut ψ (°, gegen x)", 0),
        ("delta_deg", "Polarisation δ (°; 0 = s/TE, 90 = p/TM)", 0),
    ):
        cur = inc.get(key, default)
        if not cf.scan_is_editable(cur):
            st.text_input(
                name, value=str(cur), disabled=True, help="Form nur im Reiter JSON bearbeitbar", key=_k("inc", key)
            )
            continue
        raw = st.text_input(name, value=cf.format_scan(cur), key=_k("inc", key))
        try:
            cf.assign(inc, key, cf.parse_scan(raw), default)
        except cf.FormError as e:
            st.error(f"{name}: {e}")

with tab_mat:
    section_error("materials")
    for name in list(materials):
        mat = materials[name]
        kind = cf.material_kind(mat)
        with st.expander(f"{name} · {cf.MATERIAL_KINDS.get(kind, 'andere Angabe')}"):
            if not isinstance(mat, dict) or kind is None:
                st.warning("Unbekannte Materialform – Reiter JSON.")
            else:
                keys = list(cf.MATERIAL_KINDS)
                new_kind = st.selectbox(
                    "Art", keys, index=keys.index(kind), format_func=cf.MATERIAL_KINDS.get, key=_k("mk", name)
                )
                if new_kind != kind:
                    materials[name] = cf.material_defaults(new_kind)
                    _bump()
                    st.rerun()
                if kind in ("n", "eps"):
                    complex_input(st, "n" if kind == "n" else "ε", mat, kind)
                elif kind == "eps_principal":
                    text_list(st, "Hauptwerte ε (3 Werte)", mat, "eps_principal")
                    text_list(st, "Euler-Winkel (°, z-x-z)", mat, "euler_deg")
                else:
                    raw = st.text_area(
                        "Tensor ε (JSON, 3×3 komplex)", value=config_io.dumps(mat[kind]), key=_k("mt", name)
                    )
                    try:
                        cf.assign(mat, kind, json.loads(raw))
                    except ValueError as e:
                        st.error(f"Kein gültiges JSON: {e}")
            if st.button("Material entfernen", key=_k("md", name)):
                del materials[name]
                _bump()
                st.rerun()
    c = st.columns([3, 1])
    new_name = c[0].text_input(
        "Name des neuen Materials", key=_k("newmat"), label_visibility="collapsed", placeholder="Name"
    )
    if c[1].button("Hinzufügen", disabled=not new_name.strip()):
        materials[cf.unique_name(new_name.strip(), materials)] = cf.material_defaults("n")
        cfg["materials"] = materials
        _bump()
        st.rerun()

with tab_layers:
    section_error("layers")
    st.caption("Reihenfolge von unten (Substrat) nach oben (Superstrat).")
    layers = cfg["layers"] if isinstance(cfg.get("layers"), list) else []
    n_layers = len(layers)
    for i, layer in enumerate(layers):
        ltype = layer.get("type", "?") if isinstance(layer, dict) else "?"
        with st.expander(f"Schicht {i}: {ltype}", expanded=err is not None and err[1] == "layers" and err[2] == i):
            section_error("layers", i)
            head = st.columns([1, 1, 1, 5])
            if head[0].button("↑", key=_k("up", i), disabled=i == 0):
                cf.move(layers, i, -1)
                _bump()
                st.rerun()
            if head[1].button("↓", key=_k("dn", i), disabled=i == n_layers - 1):
                cf.move(layers, i, +1)
                _bump()
                st.rerun()
            if head[2].button("✕", key=_k("rm", i)):
                del layers[i]
                _bump()
                st.rerun()
            if ltype in cf.FORM_LAYER_TYPES:
                new_type = st.selectbox(
                    "Typ", cf.FORM_LAYER_TYPES, index=cf.FORM_LAYER_TYPES.index(ltype), key=_k("lt", i)
                )
                if new_type != ltype:
                    layers[i] = cf.new_layer(new_type, mat_names, per.get("x", 1.0))
                    _bump()
                    st.rerun()
                if ltype == "homogeneous":
                    number(st, "Dicke (µm)", layer, "thickness_um", 0.1, min_value=0.0)
                    choice(st, "Material", layer, "material", mat_names)
                elif ltype == "lamellar1d":
                    number(st, "Dicke (µm)", layer, "thickness_um", 0.1, min_value=0.0)
                    rows = cf.lamellae_rows(layer)
                    edited = st.data_editor(
                        pd.DataFrame(rows, columns=["von_um", "bis_um", "material"]),
                        num_rows="dynamic",
                        hide_index=True,
                        key=_k("lam", i),
                        column_config={
                            "von_um": st.column_config.NumberColumn("von x (µm)", disabled=True, format="%.10g"),
                            "bis_um": st.column_config.NumberColumn("bis x (µm)", format="%.10g"),
                            "material": st.column_config.SelectboxColumn("Material", options=mat_names),
                        },
                    )
                    cf.lamellae_apply(layer, edited.to_dict("records"))
                else:  # profile1d
                    choice(st, "Form", layer, "shape", cf.PROFILE_SHAPES, "sinus")
                    shape = layer.get("shape", "sinus")
                    c = st.columns(3)
                    number(c[0], "Tiefe (µm)", layer, "depth_um", 0.1, min_value=0.0)
                    choice(c[1], "Material unten", layer, "below", mat_names)
                    choice(c[2], "Material oben", layer, "above", mat_names)
                    if shape == "triangle":
                        c = st.columns(2)
                        number(c[0], "Blazewinkel (°)", layer, "blaze_deg", 10.0)
                        number(c[1], "Scheitelwinkel (°)", layer, "apex_deg", 90.0)
                    elif shape == "points":
                        text_list(st, "x (µm)", layer, "x_um")
                        text_list(st, "y (µm)", layer, "y_um")
                    c = st.columns(2)
                    integer(c[0], "Scheiben (0 = automatisch)", layer, "slices", 0)
                    choice(c[1], "Faktorisierung", layer, "factorization", cf.PROFILE_FACTORIZATIONS, "auto")
            else:
                st.info(f"Für „{ltype}“ gibt es noch kein Formular (folgt); bearbeite die Schicht als JSON.")
                raw = st.text_area("Schicht (JSON)", value=config_io.dumps(layer), height=240, key=_k("lj", i))
                if st.button("Übernehmen", key=_k("lja", i)):
                    try:
                        layers[i] = config_io.parse(raw)
                        _bump()
                        st.rerun()
                    except config_io.ConfigError as e:
                        st.error(str(e))
    c = st.columns([2, 1])
    add_type = c[0].selectbox("Neue Schicht", cf.FORM_LAYER_TYPES, key=_k("addtype"), label_visibility="collapsed")
    if c[1].button("Schicht hinzufügen"):
        layers.append(cf.new_layer(add_type, mat_names, per.get("x", 1.0)))
        cfg["layers"] = layers
        _bump()
        st.rerun()

with tab_solver:
    section_error("solver")
    if cfg.get("solver") == "rk":
        rk = sub("rk")
        c = st.columns(2)
        choice(c[0], "Runge-Kutta-Tableau", rk, "tableau", ["gauss2", "gauss3", "gauss4"], "gauss2")
        number(c[1], "Toleranz", rk, "tol", 1e-8, min_value=0.0)
    else:
        rc = sub("rcwa")
        integer(st, "Scheiben je Profilschicht", rc, "slices", 60, minimum=1)
    c = st.columns(3)
    choice(c[0], "Rechenkern", cfg, "backend", ["auto", "cpu", "cuda"], "auto")
    integer(c[1], "GPU ab Matrixgröße", cfg, "backend_threshold", 1000)
    choice(c[2], "Genauigkeit", cfg, "precision", ["auto", "fp64", "mixed", "fp32"], "auto")
    c = st.columns(2)
    choice(c[0], "Reduktion", cfg, "reduction", ["sequential", "tree"], "sequential")
    thr = sub("threads")
    st.markdown("**Threads** („auto“ oder ganze Zahl)")
    c = st.columns(3)
    for col, key, default in zip(c, ("scan", "slices", "blas"), ("auto", "auto", 1), strict=True):
        raw = col.text_input(key, value=str(thr.get(key, default)), key=_k("thr", key))
        try:
            cf.assign(thr, key, cf.parse_auto_int(raw), default)
        except cf.FormError as e:
            col.error(str(e))
    c = st.columns(2)
    for col, key, name in (
        (c[0], "split_polarizations", "TE/TM getrennt (1D, ψ = 0, isotrop)"),
        (c[1], "fft_sampling", "Koeffizienten per FFT"),
    ):
        v = col.checkbox(name, value=bool(cfg.get(key, False)), key=_k("cb", key))
        cf.assign(cfg, key, v, False)

with tab_json:
    st.caption("Gesamte Konfiguration. Änderungen hier ersetzen die Formularwerte nach „Übernehmen“.")
    text = config_io.dumps(cfg)
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    raw = st.text_area("JSON", value=text, height=420, key=_k("json", h), label_visibility="collapsed")
    c = st.columns([1, 1, 4])
    if c[0].button("Übernehmen", key=_k("jsonapply")):
        try:
            _load(config_io.parse(raw), st.session_state["fg_cfg_name"])
            st.rerun()
        except config_io.ConfigError as e:
            st.error(str(e))
    c[1].download_button(
        "Herunterladen", text.encode(), file_name=label.rsplit(".", 1)[0] + ".json", mime="application/json"
    )

for _name, _d in _detached.items():
    if _d:
        cfg[_name] = _d

# ---------------------------------------------------------------- rechnen
st.divider()
info = solver_info()
if not info.available:
    st.warning("FourierGrating ist nicht installiert – Rechnen nicht möglich (Seite „System“).")
    st.stop()

if st.button("Rechnen", type="primary"):
    job = job_manager().submit(
        label or "Konfiguration", solver.solve, config_io.parse(config_io.dumps(cfg)), owner=session_id()
    )
    st.session_state["fg_editor_job"] = job.id
    st.session_state.pop("fg_editor_error", None)


def show_result(job) -> None:
    if job.status == FAILED:
        _, section, idx = err or (job.error, None, None)
        where = {
            "basis": "Grundeinstellungen",
            "incidence": "Einfall",
            "materials": "Materialien",
            "layers": f"Schicht {idx}" if idx is not None else "Schichten",
            "solver": "Löser",
        }.get(section or "")
        st.error(job.error + (f"  \n→ vermutlich im Reiter „{where}“" if where else ""))
        with st.expander("Details"):
            st.code(job.traceback)
        return
    res = job.result()
    st.success(f"{job.label}: fertig in {job.runtime:.2f} s")
    tot = results.totals(res)
    for c, (k, v) in zip(st.columns(len(tot)), tot.items(), strict=True):
        c.metric(k, f"{v:.6g}")
    st.dataframe(results.orders_frame(res), hide_index=True, width="stretch")


@st.fragment(run_every=1.0)
def wait_for(job_id: str) -> None:
    job = job_manager().get(job_id)
    if job is None or job.status in (DONE, FAILED):
        st.rerun()
    st.info(f"{job.label}: {job.status} …")


current = job_manager().get(st.session_state.get("fg_editor_job", ""))
if current is not None:
    if current.status in (DONE, FAILED):
        show_result(current)
    else:
        wait_for(current.id)
