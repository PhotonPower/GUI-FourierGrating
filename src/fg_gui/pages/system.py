"""Seite „System“: FourierGrating-Kern, GPU, Einstellungen."""

import pandas as pd
import streamlit as st

from fg_gui import solver, system
from fg_gui.state import job_manager, settings, solver_info

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
            ]
        },
        index=["FG_GUI_DATA_DIR", "FG_GUI_EXAMPLES_DIR", "FG_GUI_WORKERS", "FG_GUI_JOB_HISTORY"],
    )
)
