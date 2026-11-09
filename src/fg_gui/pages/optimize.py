"""Seite „Optimierung“: Parameter der Konfiguration mit Gradienten (L-BFGS-B) optimieren (G6)."""

import pandas as pd
import streamlit as st

from fg_gui import optimize as opt
from fg_gui import solver
from fg_gui.cad import CadFileError
from fg_gui.jobs import DONE, FAILED, WAITING
from fg_gui.state import job_manager, open_in_editor, solver_info, submit_job
from fg_gui.widgets import show_estimate, wkey

st.title("Optimierung")
st.caption(
    "Maximiert oder minimiert L = Σ wᵢ·eᵢ über die Effizienzen gewählter Beugungsordnungen. Die Gradienten liefert "
    "`Simulation.value_and_grad` von FourierGrating (diskrete Adjungierte); optimiert wird mit L-BFGS-B und Grenzen. "
    "Gerechnet wird am ersten Scanpunkt der Konfiguration aus dem *Editor*."
)

info = solver_info()
if not info.available:
    st.warning("FourierGrating ist nicht installiert – Rechnen nicht möglich (Seite „System“).")
    st.stop()

# ---------------------------------------------------------------- Vorlage
with st.expander("Vorlage"):
    st.write(
        "Binäres Aluminiumgitter (Periode 0,5 µm, λ = 0,6328 µm, TM) in Littrow-Anordnung: Tiefe und Stegbreite "
        "für die −1. reflektierte Ordnung (Beispiel `optimize_littrow.py` von FourierGrating)."
    )
    if st.button("Littrow-Vorlage laden"):
        preset = opt.littrow_preset()
        open_in_editor(preset["config"], "littrow.json")
        spec = preset["spec"]
        st.session_state["fg_opt_preset"] = spec
        st.session_state.pop("fg_opt_job", None)
        st.rerun()

if "fg_cfg" not in st.session_state:
    st.info("Zuerst im *Editor* eine Konfiguration laden oder anlegen – oder die Vorlage oben laden.")
    st.stop()

cfg = st.session_state["fg_cfg"]
name = st.session_state.get("fg_cfg_label") or st.session_state["fg_cfg_name"].split(":", 1)[-1]
preset: opt.Spec | None = st.session_state.get("fg_opt_preset")

# ---------------------------------------------------------------- Zielfunktion
st.subheader("Zielfunktion")
terms_default = (
    [{"Seite": s, "n": n, "m": m, "Gewicht": w} for s, n, m, w in preset.terms]
    if preset
    else [{"Seite": "R", "n": 0, "m": 0, "Gewicht": 1.0}]
)
terms_df = st.data_editor(
    pd.DataFrame(terms_default),
    num_rows="dynamic",
    hide_index=True,
    key=wkey("opt_terms"),
    column_config={
        "Seite": st.column_config.SelectboxColumn(options=list(opt.SIDES), required=True),
        "n": st.column_config.NumberColumn(step=1, required=True),
        "m": st.column_config.NumberColumn(step=1, required=True),
        "Gewicht": st.column_config.NumberColumn(format="%.6g", required=True),
    },
)
maximize = st.radio("Ziel", ["Maximieren", "Minimieren"], horizontal=True, key=wkey("opt_sense")) == "Maximieren"

# ---------------------------------------------------------------- Parameter
st.subheader("Parameter")
candidates = dict(opt.numeric_pointers(cfg))
labels = {p: f"{p}  (= {v:g})" for p, v in candidates.items()}
default_sel = [p.pointer for p in preset.params if p.pointer in candidates] if preset else []
selected = st.multiselect("Zahlen der Konfiguration (JSON-Pointer)", list(candidates), default=default_sel,
                          format_func=labels.get, key=wkey("opt_sel"))  # fmt: skip
extra = st.text_input("Weitere Pointer (kommagetrennt, falls nicht in der Liste)", key=wkey("opt_extra"))
for ptr in [x.strip() for x in extra.split(",") if x.strip()]:
    if ptr not in selected:
        selected.append(ptr)

preset_params = {p.pointer: p for p in preset.params} if preset else {}
rows = []
for ptr in selected:
    if ptr in preset_params:
        p = preset_params[ptr]
        rows.append({"Parameter": ptr, "Start": p.start, "Untergrenze": p.lower, "Obergrenze": p.upper})
        continue
    try:
        v = float(opt.get_pointer(cfg, ptr))
    except (opt.SpecError, TypeError, ValueError):
        st.error(f"{ptr}: keine Zahl in der Konfiguration")
        continue
    lo, hi = (0.5 * v, 1.5 * v) if v > 0 else ((1.5 * v, 0.5 * v) if v < 0 else (-0.1, 0.1))
    rows.append({"Parameter": ptr, "Start": v, "Untergrenze": lo, "Obergrenze": hi})
params_df = None
if rows:
    params_df = st.data_editor(
        pd.DataFrame(rows),
        hide_index=True,
        num_rows="fixed",
        key=wkey("opt_params", hash(tuple(selected))),
        column_config={
            "Parameter": st.column_config.TextColumn(disabled=True),
            "Start": st.column_config.NumberColumn(format="%.6g"),
            "Untergrenze": st.column_config.NumberColumn(format="%.6g"),
            "Obergrenze": st.column_config.NumberColumn(format="%.6g"),
        },
    )
    st.caption("Vorgaben für Start und Grenzen sind ±50 % des aktuellen Werts – bitte physikalisch sinnvoll anpassen.")
else:
    st.info("Mindestens einen Parameter wählen.")

c = st.columns(2)
maxiter = c[0].number_input("Höchstzahl der Iterationen", min_value=1, value=preset.maxiter if preset else 200, step=10)
ftol = c[1].number_input("Abbruchschwelle ftol", min_value=0.0, value=preset.ftol if preset else 1e-12, format="%.1e")

# ---------------------------------------------------------------- Start
show_estimate(cfg)
if st.button("Optimieren", type="primary", disabled=params_df is None):
    try:
        terms = [
            (str(r["Seite"]), int(r["n"]), int(r["m"]), float(r["Gewicht"]))
            for r in terms_df.to_dict("records")
            if r.get("Seite") and r.get("n") is not None and r.get("m") is not None and r.get("Gewicht") is not None
        ]
        params = [
            opt.Param(r["Parameter"], float(r["Start"]), float(r["Untergrenze"]), float(r["Obergrenze"]))
            for r in params_df.to_dict("records")
        ]
        spec = opt.Spec(terms, params, maximize, int(maxiter), float(ftol))
        spec.validate()
        history = opt.History()
        job = submit_job(
            f"Optimierung: {name}",
            solver.run_optimization,
            cfg,
            kind="optimize",
            progress=history,
            spec=spec,
            history=history,
        )
        st.session_state["fg_opt_job"] = job.id
    except (opt.SpecError, CadFileError, ValueError, TypeError) as e:
        st.error(str(e))

jm = job_manager()
job = jm.get(st.session_state.get("fg_opt_job", ""))
if job is None:
    st.stop()


# ---------------------------------------------------------------- Verlauf live
def chart(rows: list[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame({"Auswertung": [r["eval"] for r in rows], "Zielwert": [r["value"] for r in rows],
                       "Bester": [r["best"] for r in rows]})  # fmt: skip
    st.line_chart(df, x="Auswertung", y=["Zielwert", "Bester"])


@st.fragment(run_every=1.0)
def live(job_id: str) -> None:
    j = jm.get(job_id)
    if j is None or j.status in (DONE, FAILED) or j.cancelled:
        st.rerun()
    if j.status == WAITING:
        st.info(f"{j.label}: wartend (Platz {jm.queue_position(j.id)})")
        if st.button("Abbrechen", key="fg_opt_cancel"):
            jm.cancel(j.id)
        return
    rows = j.progress.snapshot() if j.progress is not None else []
    st.info(f"{j.label}: läuft – {len(rows)} Auswertungen")
    chart(rows)
    if rows:
        last = rows[-1]
        st.caption(
            f"Zuletzt: Zielwert {last['value']:.6g}, bester {last['best']:.6g}, |Gradient| {last['grad_norm']:.3g}"
        )
    if st.button("Stoppen", key="fg_opt_stop", help="Beendet nach der laufenden Auswertung; das beste Ergebnis bleibt"):
        if j.progress is not None:
            j.progress.stop.set()


if job.status not in (DONE, FAILED) and not job.cancelled:
    live(job.id)
    st.stop()
if job.status == FAILED:
    st.error(job.error)
    with st.expander("Details"):
        st.code(job.traceback)
    st.stop()
if job.result() is None:
    st.info("Abgebrochen.")
    st.stop()

# ---------------------------------------------------------------- Ergebnis
res = job.result()
(st.success if res["success"] else st.warning)(
    f"{job.label}: {res['message']} ({res['nfev']} Auswertungen, {res['nit']} Iterationen, {res['runtime_s']:.1f} s)"
)
c = st.columns(3)
c[0].metric("Zielwert am Optimum", f"{res['value']:.6g}" if res["value"] is not None else "–")
start_val = res["history"][0]["value"] if res["history"] else None
c[1].metric("Zielwert am Start", f"{start_val:.6g}" if start_val is not None else "–")
c[2].metric("Ziel", "Maximieren" if res["maximize"] else "Minimieren")
st.dataframe(
    pd.DataFrame(
        {
            "Parameter": list(res["x"]),
            "Start": [res["start"][k] for k in res["x"]],
            "Optimum": [res["x"][k] for k in res["x"]],
            "Untergrenze": [p["lower"] for p in res["spec"]["params"]],
            "Obergrenze": [p["upper"] for p in res["spec"]["params"]],
        }
    ),
    hide_index=True,
    width="stretch",
)
chart(res["history"])
hist = opt.history_frame(res["history"], list(res["x"]))
c = st.columns(3)
if c[0].button("Optimum in den Editor übernehmen"):
    base = job_manager().config(job.id) or cfg
    open_in_editor(opt.apply_to_config(base, res["x"]), f"{name} (optimiert)")
    st.success("Übernommen: die Konfiguration im *Editor* enthält jetzt die optimierten Werte.")
c[1].download_button("Verlauf (.csv)", hist.to_csv(index=False).encode(), file_name="optimierung.csv", mime="text/csv")
with st.expander("Verlauf (Tabelle)"):
    st.dataframe(hist, hide_index=True, width="stretch")
