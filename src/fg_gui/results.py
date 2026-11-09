"""Umwandlung der Ergebnisobjekte von FourierGrating in Tabellen für die Anzeige."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

COLUMNS = ["Seite", "n", "m", "Effizienz", "eff_s", "eff_p"]


def orders_frame(result: Any) -> pd.DataFrame:
    """Beugungsordnungen (reflektiert und transmittiert) eines ``fg.Result`` als Tabelle."""
    parts = []
    for side, arr in (("R", result.reflected), ("T", result.transmitted)):
        arr = np.asarray(arr)
        if arr.size == 0:
            continue
        parts.append(
            pd.DataFrame(
                {
                    "Seite": side,
                    "n": arr["n"].astype(int),
                    "m": arr["m"].astype(int),
                    "Effizienz": arr["eff"].astype(float),
                    "eff_s": arr["eff_s"].astype(float),
                    "eff_p": arr["eff_p"].astype(float),
                }
            )
        )
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)


def totals(result: Any) -> dict[str, float]:
    """Summen R, T und Absorption, wie von FourierGrating geliefert (Diagnose: energy_balance)."""
    r = float(np.sum(np.asarray(result.reflected)["eff"])) if len(result.reflected) else 0.0
    t = float(np.sum(np.asarray(result.transmitted)["eff"])) if len(result.transmitted) else 0.0
    out = {"ΣR": r, "ΣT": t, "Absorption": float(result.absorption)}
    eb = (result.diagnostics or {}).get("energy_balance")
    if eb is not None:
        out["Energiebilanz"] = float(eb)
    return out
