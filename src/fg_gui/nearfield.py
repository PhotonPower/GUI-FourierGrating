"""Nahfeldergebnisse (``fg.near_field``) → Auswahl, Diagramm und Export (G3).

Felder und Achsen werden unverändert durchgereicht; hier wird nur gewählt (Betrag/Realteil/…), gezeichnet und
verpackt. Der Export entspricht dem Verzeichnis von ``fgsolve`` (``nearfield_<schnitt>/``: ``*.npy``,
``meta.json``), sodass ``scripts/plot_nearfield.py`` aus FourierGrating ihn lesen kann.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import numpy as np
import pandas as pd

CUT_NAMES = {"horizontal": "Horizontaler Schnitt", "vertical": "Vertikaler Schnitt"}
COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
SCALARS = {"absE2": "|E|²", "absH2": "|H|²", "Sy": "Poynting S_y"}
PARTS = {"abs": "Betrag", "re": "Realteil", "im": "Imaginärteil", "phase": "Phase"}
BLOCK_QUANTITIES = ("E", "H", "absE2", "absH2", "poynting")
_NOT_FIELDS = {"axis1_um", "axis2_um"}


def default_block(dimension: str = "1D") -> dict:
    """Beispielwerte aus docs/user_guide.md von FourierGrating (Ausgangspunkt zum Anpassen)."""
    block = {
        "enabled": True,
        "horizontal_y_um": 0.0,
        "vertical_z_um": 0.0,
        "y_range_um": [-0.3, 0.6],
        "nx": 400,
        "ny": 300,
        "periods": 2,
        "quantities": ["E", "H", "absE2"],
        "reconstruction": "fff",
    }
    if dimension == "2D":
        block.update({"nx": 120, "ny": 110, "nz": 120})
    return block


def cut_names(nf: dict) -> list[str]:
    return [k for k in CUT_NAMES if isinstance(nf.get(k), dict)]


def is_map(cut: dict) -> bool:
    return np.size(cut.get("axis2_um", [])) > 0


def quantities(cut: dict) -> list[str]:
    """Größen, die der Schnitt enthält: zuerst die Skalare, dann die Feldkomponenten."""
    names = [q for q in (*SCALARS, *COMPONENTS) if isinstance(cut.get(q), np.ndarray)]
    return names


def is_complex(cut: dict, quantity: str) -> bool:
    return np.iscomplexobj(cut[quantity])


def quantity_label(q: str) -> str:
    return SCALARS.get(q, q)


def select(cut: dict, quantity: str, part: str = "abs") -> np.ndarray:
    """Reelle Werte einer Größe. Reelle Größen (|E|², S_y …) kommen unverändert zurück."""
    arr = cut[quantity]
    if not np.iscomplexobj(arr):
        return arr
    if part not in PARTS:
        raise ValueError(f"Unbekannter Anteil: {part}")
    return {"abs": np.abs, "re": np.real, "im": np.imag, "phase": np.angle}[part](arr)


def axes(cut: dict) -> tuple[tuple[str, np.ndarray], tuple[str, np.ndarray] | None]:
    a1 = (str(cut["axis1_name"]), np.asarray(cut["axis1_um"]))
    a2 = (str(cut["axis2_name"]), np.asarray(cut["axis2_um"])) if is_map(cut) else None
    return a1, a2


def line_frame(cut: dict, quantity: str, part: str = "abs") -> pd.DataFrame:
    """Linienschnitt (1D, horizontal) als Tabelle: Spalte der Achse und der Größe."""
    (name, x), _ = axes(cut)
    return pd.DataFrame({f"{name} (µm)": x, quantity_label(quantity): select(cut, quantity, part)})


def figure(cut: dict, quantity: str, part: str = "abs", contours: bool = True):
    """Karte oder Linie wie ``plot_nearfield.py``; Materialgrenzen als weiße Kontur."""
    from matplotlib.figure import Figure  # ohne pyplot: kein globaler Zustand, threadsicher

    (n1, x), a2 = axes(cut)
    val = select(cut, quantity, part)
    fig = Figure(figsize=(7, 4.5))
    ax = fig.subplots()
    title = quantity_label(quantity) + (f" ({PARTS[part].lower()})" if is_complex(cut, quantity) else "")
    title += f", {cut.get('cut', '')}, λ = {cut.get('lambda_um', '?')} µm"
    if a2 is not None:
        n2, y = a2
        signed = val.size > 0 and float(np.nanmin(val)) < 0
        kw = {"cmap": "RdBu_r"} if signed else {"cmap": "inferno"}
        if signed:
            lim = float(np.nanmax(np.abs(val)))
            kw.update(vmin=-lim, vmax=lim)
        im = ax.pcolormesh(x, y, val, shading="auto", **kw)
        fig.colorbar(im, ax=ax)
        mat = cut.get("material")
        if contours and isinstance(mat, np.ndarray) and mat.shape == val.shape and np.unique(mat).size > 1:
            ax.contour(x, y, mat, levels=np.unique(mat)[:-1] + 0.5, colors="w", linewidths=0.6)
        ax.set_ylabel(f"{n2} (µm)")
        ax.set_aspect("equal")
    else:
        ax.plot(x, val)
        ax.set_ylabel(quantity_label(quantity))
    ax.set_xlabel(f"{n1} (µm)")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    return fig


def png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    return buf.getvalue()


def export_zip(nf: dict) -> bytes:
    """ZIP mit ``nearfield_<schnitt>/{<Größe>.npy, material.npy, meta.json}`` wie ``fgsolve``."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in cut_names(nf):
            cut = nf[name]
            for key, value in cut.items():
                if isinstance(value, np.ndarray) and key not in _NOT_FIELDS:
                    b = io.BytesIO()
                    np.save(b, value)
                    z.writestr(f"nearfield_{name}/{key}.npy", b.getvalue())
            z.writestr(f"nearfield_{name}/meta.json", json.dumps(cut.get("meta", {}), indent=2))
    return buf.getvalue()


def describe(cut: dict) -> dict[str, Any]:
    (n1, x), a2 = axes(cut)
    out: dict[str, Any] = {"Schnitt": cut.get("cut", "?"), "λ (µm)": cut.get("lambda_um"), f"{n1}-Punkte": len(x)}
    if a2 is not None:
        out[f"{a2[0]}-Punkte"] = len(a2[1])
    return out
