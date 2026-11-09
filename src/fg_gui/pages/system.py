"""Seite „System“: FourierGrating-Kern, GPU, Einstellungen."""

import pandas as pd
import streamlit as st

from fg_gui import health, solver, system
from fg_gui.state import job_manager, settings, solver_info, sweep_now, uploads_dir

st.title("System")

st.subheader("FourierGrating")
if st.button("Neu prüfen"):
    solver_info.clear()
info = solver_info()
if not info.available:
    st.error(
        "Das Python-Paket `fouriergrating` ist nicht importierbar. Installation siehe "
        "`docs/deployment_rtx6000.md`.\n\n" + f"`{info.error}`"
    )
else:
    if not info.version_ok:
        st.warning(
            f"FourierGrating {info.version} ist älter als die geprüfte Mindestversion "
            f"{'.'.join(map(str, solver.MIN_VERSION))}."
        )
    st.table(
        pd.DataFrame(
            {
                "Wert": [
                    info.version,
                    info.core_variant,
                    "ja" if info.cuda_available else "nein",
                    "ja" if info.cad_available else "nein",
                    ", ".join(f"{k}={v}" for k, v in info.backend.items()) or "–",
                ]
            },
            index=["Version", "Kern", "CUDA nutzbar", "CAD-Slicer", "Backend"],
        )
    )

st.subheader("GPU")
rows = system.gpus()
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
else:
    st.info("Keine NVIDIA-GPU gefunden (nvidia-smi fehlt oder meldet keinen Treiber).")

st.subheader("Einstellungen")
s = settings()
jm = job_manager()
st.table(
    pd.DataFrame(
        {
            "Wert": [
                str(s.data_dir),
                str(s.examples_dir or "–"),
                str(jm.workers),
                str(s.job_history),
                s.user_header or "– (keine Anmeldung)",
                str(s.retention_days or "aus"),
                str(s.max_runs or "unbegrenzt"),
                f"{s.log_level}, Datei: {s.log_file or '–'}",
            ]
        },
        index=[
            "FG_GUI_DATA_DIR",
            "FG_GUI_EXAMPLES_DIR",
            "FG_GUI_WORKERS",
            "FG_GUI_JOB_HISTORY",
            "FG_GUI_USER_HEADER",
            "FG_GUI_RETENTION_DAYS",
            "FG_GUI_MAX_RUNS",
            "FG_GUI_LOG_LEVEL / _FILE",
        ],
    )
)

st.subheader("Betrieb")
ok, rows = health.run(s, None)
st.table(pd.DataFrame({"Ergebnis": ["OK" if g else "FEHLER" for _, g, _ in rows], "Detail": [t for *_, t in rows]},
                      index=[n for n, *_ in rows]))  # fmt: skip
store = jm.store
runs = jm.jobs()
size = sum(store.size_bytes(j.id) for j in runs) if store else 0
up = sum(f.stat().st_size for f in uploads_dir().glob("*") if f.is_file()) if uploads_dir().is_dir() else 0
st.caption(f"{len(runs)} gespeicherte Rechnungen, {size / 1e6:.1f} MB; Uploads {up / 1e6:.1f} MB.")
if st.button("Jetzt aufräumen", disabled=not (s.retention_days or s.max_runs)):
    rep = sweep_now(jm)
    st.success(f"{rep.runs} Rechnungen und {rep.uploads} Uploads gelöscht, {rep.freed_bytes / 1e6:.1f} MB frei.")
