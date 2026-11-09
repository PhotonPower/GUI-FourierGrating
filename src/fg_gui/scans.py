"""Scanergebnisse (``fg.ScanResult``) → Tabellen und Kurvendaten für Diagramme und Export (G2).

Die Spalten kommen unverändert aus ``ScanResult.columns``; hier wird nur ausgewählt, gruppiert und umgeformt.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

#: mögliche x-Achsen in der Reihenfolge von efficiencies.csv
AXES = {
    "lambda_um": "Wellenlänge λ (µm)",
    "phi_deg": "Einfallswinkel φ (°)",
    "psi_deg": "Azimut ψ (°)",
    "delta_deg": "Polarisation δ (°)",
    "sweep_value": "Sweep-Wert",
}
QUANTITIES = {"efficiency": "gesamt", "eff_s": "s (TE)", "eff_p": "p (TM)"}
COMPLEX_COLUMNS = ("amp_s", "amp_p")


def scan_frame(scan: Any) -> pd.DataFrame:
    """Tabelle mit genau den Spalten von ``ScanResult.columns`` (eine Zeile je Ordnung)."""
    return pd.DataFrame({k: np.asarray(v) for k, v in dict(scan.columns).items()})


def varying_axes(df: pd.DataFrame) -> list[str]:
    """Achsen, die im Scan mehr als einen Wert annehmen (nur sie taugen als x-Achse)."""
    return [a for a in AXES if a in df.columns and df[a].nunique() > 1]


def fixed_choices(df: pd.DataFrame, x: str) -> dict[str, list[float]]:
    """Für jede veränderliche Achse außer ``x`` die Werte, aus denen eine festgehalten werden muss."""
    return {a: sorted(df[a].unique().tolist()) for a in varying_axes(df) if a != x}


def order_labels(df: pd.DataFrame) -> list[str]:
    """``R(-1,0)``, ``T(0,0)`` … (Seite, n, m) in sortierter Reihenfolge."""
    if df.empty:
        return []
    keys = df[["side", "n", "m"]].drop_duplicates().sort_values(["side", "n", "m"])
    return [order_label(s, n, m) for s, n, m in keys.itertuples(index=False)]


def order_label(side: str, n: int, m: int) -> str:
    return f"{side}({int(n)},{int(m)})"


def curves(
    df: pd.DataFrame,
    x: str,
    orders: list[str],
    quantity: str = "efficiency",
    fixed: dict[str, float] | None = None,
    sums: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Kurven über ``x``: eine Spalte je Ordnung (``R(-1,0)``) und je gewünschter Summe (``ΣR``, ``ΣT``).

    ``fixed`` hält die übrigen veränderlichen Achsen fest. Eine Ordnung, die bei einem x-Wert nicht propagiert
    (fehlt in den Spalten), zählt als 0 – wie ``Result.efficiency``.
    """
    if quantity not in QUANTITIES:
        raise ValueError(f"Unbekannte Größe: {quantity}")
    d = df
    for axis, value in (fixed or {}).items():
        d = d[np.isclose(d[axis], value)]
    xs = np.sort(d[x].unique())
    out = pd.DataFrame(index=pd.Index(xs, name=x))
    labels = d.apply(lambda r: order_label(r["side"], r["n"], r["m"]), axis=1) if len(d) else pd.Series(dtype=str)
    for lab in orders:
        sel = d[labels == lab] if len(d) else d
        out[lab] = sel.groupby(x)[quantity].sum().reindex(xs, fill_value=0.0)
    for s in sums:
        side = s[-1]
        out[s] = d[d["side"] == side].groupby(x)[quantity].sum().reindex(xs, fill_value=0.0)
    return out


def compare(runs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Mehrere Kurventabellen (gleiche x-Achse) in eine; Spalten ``Lauf: Kurve``. x-Werte werden vereinigt."""
    parts = [t.rename(columns=lambda c, name=name: f"{name}: {c}") for name, t in runs.items()]
    return pd.concat(parts, axis=1).sort_index() if parts else pd.DataFrame()


def csv_frame(df: pd.DataFrame, sweep_parameter: str = "") -> pd.DataFrame:
    """Spalten wie ``efficiencies.csv``: Sweep-Spalten vorn (falls vorhanden), komplexe Amplituden als Re/Im."""
    out = df.copy()
    for c in COMPLEX_COLUMNS:
        if c in out:
            out[f"{c}_re"] = out[c].astype(complex).map(lambda z: z.real)
            out[f"{c}_im"] = out[c].astype(complex).map(lambda z: z.imag)
            out = out.drop(columns=c)
    if sweep_parameter:
        out.insert(0, "sweep_parameter", sweep_parameter)
    else:
        out = out.drop(columns=["sweep_value"], errors="ignore")
    return out


def to_csv(df: pd.DataFrame, sweep_parameter: str = "") -> bytes:
    return csv_frame(df, sweep_parameter).to_csv(index=False).encode()
