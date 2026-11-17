"""Formulare für dispersive Materialien (G8): Sellmeier, Cauchy, Drude–Lorentz, Tabellen, Import, Vorschau.

Wie ``widgets.py``: Felder schreiben nur bei Änderung in das Konfigurations-``dict``. Ausgewertet wird im Kern von
FourierGrating (``solver.material_eps``); hier steht keine Physik.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st

from fg_gui import config_form as cf
from fg_gui import dispersion, solver
from fg_gui.widgets import choice, number, text_list, wkey

PREVIEW_POINTS = 120
_AXIS = {"um": "λ (µm)", "nm": "λ (nm)", "eV": "E (eV)"}


def _optional_range(container, params: dict) -> None:
    """``range_um`` (zwei Zahlen) – leeres Feld entfernt den Eintrag."""
    cur = params.get("range_um")
    raw = container.text_input(
        "Gültigkeitsbereich range_um (µm, „von, bis“; leer = keiner)",
        value=cf.format_list(cur) if isinstance(cur, list) else "",
        key=wkey(id(params), "range_um"),
    )
    if not raw.strip():
        params.pop("range_um", None)
        return
    try:
        vals = cf.parse_list(raw)
    except cf.FormError as e:
        container.error(f"range_um: {e}")
        return
    if len(vals) != 2:
        container.error("range_um: zwei Zahlen angeben")
    else:
        cf.assign(params, "range_um", vals)


def _oscillators(container, params: dict, gen_key: str) -> None:
    cols = ["f", "omega_eV", "gamma_eV"]
    old = params.get("oscillators") if isinstance(params.get("oscillators"), list) else []
    df = pd.DataFrame([{c: o.get(c) for c in cols} for o in old if isinstance(o, dict)], columns=cols)
    container.markdown("**Oszillatoren** (f, ω in eV, Γ in eV)")
    edited = container.data_editor(
        df, num_rows="dynamic", hide_index=True, key=wkey("osc", id(params)),
        column_config={c: st.column_config.NumberColumn(format="%.10g") for c in cols},
    )  # fmt: skip
    new = []
    for i, r in enumerate(edited.to_dict("records")):
        vals = {c: (None if pd.isna(r[c]) else float(r[c])) for c in cols}
        if any(v is None for v in vals.values()):
            continue
        orig = old[i] if i < len(old) and isinstance(old[i], dict) else None
        new.append(orig if orig is not None and all(orig.get(c) == vals[c] for c in cols) else {**(orig or {}), **vals})
    cf.assign(params, "oscillators", new, [])


def _table(container, name: str, key: str, params: dict, bump: Callable[[], None]) -> None:
    unit_default = "um"
    c = container.columns(3)
    choice(c[0], "Einheit der ersten Spalte", params, "unit", dispersion.UNITS, unit_default)
    choice(c[1], "Interpolation", params, "interpolation", dispersion.INTERPOLATIONS, "linear")
    choice(c[2], "Außerhalb der Tabelle", params, "extrapolate", dispersion.EXTRAPOLATIONS, "error")
    if isinstance(params.get("file"), str):
        container.info(
            f"Tabelle aus der Datei „{params['file']}“: sie wird beim Rechnen als Daten eingelesen "
            "(nur aus Uploads, Materialbibliothek und Beispielverzeichnis)."
        )
        return
    unit = params.get("unit", unit_default)
    eps = key != "n"
    rows = dispersion.table_rows(params)
    df = pd.DataFrame(rows, columns=dispersion.TABLE_COLUMNS)
    edited = container.data_editor(
        df,
        num_rows="dynamic",
        hide_index=True,
        key=wkey("tbl", name),
        column_config={
            "x": st.column_config.NumberColumn(_AXIS.get(unit, unit), format="%.10g"),
            "re": st.column_config.NumberColumn("Re ε" if eps else "n", format="%.10g"),
            "im": st.column_config.NumberColumn("Im ε" if eps else "k", format="%.10g"),
        },
    )
    dispersion.table_apply(params, edited.to_dict("records"))
    container.caption("Spalten in aufsteigender Reihenfolge der ersten Spalte; „Im ε“/„k“ darf leer bleiben.")
    with container.expander("Tabelle aus CSV ersetzen"):
        text = st.text_area("CSV einfügen", key=wkey("csvtext", name), height=120, placeholder="0.4, 1.47, 0.0")
        up = st.file_uploader("oder CSV-Datei", type=["csv", "txt", "dat"], key=wkey("csvup", name))
        if st.button("Übernehmen", key=wkey("csvgo", name)):
            try:
                body = up.getvalue().decode("utf-8", errors="replace") if up is not None else text
                params["data"] = dispersion.parse_csv(body)
                params.pop("file", None)
                bump()
                st.rerun()
            except dispersion.DispersionError as e:
                st.error(str(e))


def dispersive_form(container, name: str, mat: dict, bump: Callable[[], None]) -> None:
    """Formular für ein Material mit Modell unter ``n``/``eps`` (Tabelle, Sellmeier, Cauchy, Drude–Lorentz)."""
    found = dispersion.model_container(mat)
    if found is None:
        container.warning("Unbekannte Materialform – Reiter JSON.")
        return
    key, model = found
    params = mat[key][model]
    if not isinstance(params, dict):
        container.warning("Modellparameter sind kein Objekt – Reiter JSON.")
        return
    container.caption(
        {
            "sellmeier": "ε = A + Σ B_k λ²/(λ² − C_k), C_k in µm²; reell.",
            "cauchy": "n = A + B/λ² + C/λ⁴ + i·k.",
            "drude_lorentz": "ε = ε∞ − f₀ωp²/(ω(ω + iΓ₀)) + Σ f_j ωp²/(ω_j² − ω² − iωΓ_j); Energien in eV.",
            "table": "Werte je Wellenlänge; zwischen den Zeilen wird interpoliert. "
            + ("Spalten: λ, n, k." if key == "n" else "Spalten: λ, Re ε, Im ε."),
        }[model]
    )
    if model == "sellmeier":
        number(container, "A", params, "A", 1.0)
        text_list(container, "B (Liste)", params, "B")
        text_list(container, "C (µm², Liste)", params, "C_um2")
        _optional_range(container, params)
    elif model == "cauchy":
        c = container.columns(4)
        number(c[0], "A", params, "A", 1.0)
        number(c[1], "B (µm²)", params, "B_um2", 0.0)
        number(c[2], "C (µm⁴)", params, "C_um4", 0.0)
        number(c[3], "k", params, "k", 0.0, min_value=0.0)
    elif model == "drude_lorentz":
        c = container.columns(4)
        number(c[0], "ε∞", params, "eps_inf", 1.0)
        number(c[1], "ωp (eV)", params, "omega_p_eV", 0.0, min_value=0.0)
        number(c[2], "f₀", params, "f0", 0.0)
        number(c[3], "Γ₀ (eV)", params, "gamma0_eV", 0.0, min_value=0.0)
        _oscillators(container, params, "osc")
    else:
        _table(container, name, key, params, bump)


# ---------------------------------------------------------------- Vorschau
def preview(container, cfg: dict, name: str) -> None:
    """ε(λ) des Materials, ausgewertet von FourierGrating (``material_eps``), im Bereich des Einfalls."""
    with container.expander("Vorschau ε(λ)"):
        if not st.toggle("Vorschau zeigen", key=wkey("pv_on", name)):
            return
        rng = dispersion.lambda_range(cfg)
        lo, hi = rng if rng and rng[1] > rng[0] else ((0.8 * rng[0], 1.2 * rng[0]) if rng else (0.4, 1.0))
        c = st.columns(2)
        lo = c[0].number_input("λ von (µm)", value=float(lo), format="%.6g", key=wkey("pv_lo", name))
        hi = c[1].number_input("λ bis (µm)", value=float(hi), format="%.6g", key=wkey("pv_hi", name))
        if not hi > lo > 0:
            st.error("Bereich: 0 < von < bis")
            return
        lams = [lo + (hi - lo) * i / (PREVIEW_POINTS - 1) for i in range(PREVIEW_POINTS)]
        try:
            frame = dispersion.eps_frame(lams, solver.material_eps(cfg, name, lams))
        except Exception as e:  # FourierGratingError: Bereich, Pol, … mit JSON-Pointer
            st.error(str(e))
            return
        comps = [c for c in frame.columns if c.endswith("_re")]
        for col in comps:
            stem = col[:-3]
            st.caption("ε′ (Realteil)" if len(comps) == 1 else f"ε′ Hauptwert {stem[3:]}")
            st.line_chart(frame, x="lambda_um", y=col, height=180)
            st.caption("ε″ (Imaginärteil)" if len(comps) == 1 else f"ε″ Hauptwert {stem[3:]}")
            st.line_chart(frame, x="lambda_um", y=f"{stem}_im", height=180)


# ---------------------------------------------------------------- Import und Bibliothek
def _stem_name(text: str) -> str:
    return re.sub(r"[^\w\-]+", "_", Path(text).stem).strip("_") or "material"


def import_material(
    cfg: dict,
    materials: dict,
    library: list[Path],
    bump: Callable[[], None],
    roots_ok: Callable[[Path], bool] = lambda p: True,
) -> None:
    """Neues Material aus der Materialbibliothek, aus CSV oder aus einer refractiveindex.info-YAML anlegen."""
    sources = (["Bibliothek"] if library else []) + ["CSV", "refractiveindex.info (YAML)"]
    src = st.radio("Quelle", sources, horizontal=True, key=wkey("imp_src"))
    material: dict | None = None
    default_name = "material"
    try:
        if src == "Bibliothek":
            path = st.selectbox("Datei", library, format_func=lambda p: p.name, key=wkey("imp_lib"))
            default_name = _stem_name(path.name)
            st.caption("Die Bibliothek ist für alle gemeinsam und schreibgeschützt; das Material wird in die "
                       "Konfiguration kopiert.")  # fmt: skip
            if path.suffix.lower() == ".csv":
                material = _csv_material(path.read_text(encoding="utf-8", errors="replace"), "lib")
            else:
                material = solver.from_refractiveindex(path.read_text(encoding="utf-8", errors="replace"))
        elif src == "CSV":
            text = st.text_area("CSV einfügen", key=wkey("imp_text"), height=120, placeholder="0.4, 1.47, 0.0")
            up = st.file_uploader("oder CSV-Datei", type=["csv", "txt", "dat"], key=wkey("imp_up"))
            body = up.getvalue().decode("utf-8", errors="replace") if up is not None else text
            default_name = _stem_name(up.name) if up is not None else "tabelle"
            if body.strip():
                material = _csv_material(body, "csv")
        else:
            up = st.file_uploader("YAML-Datei der Datenbank", type=["yml", "yaml"], key=wkey("imp_yaml"))
            st.caption("Lizenz der Daten beachten (refractiveindex.info). Unterstützt: tabellierte n/k-Daten und "
                       "Sellmeier-Formeln 1 und 2.")  # fmt: skip
            if up is not None:
                default_name = _stem_name(up.name)
                material = solver.from_refractiveindex(up.getvalue().decode("utf-8", errors="replace"))
    except Exception as e:
        st.error(f"Import nicht möglich: {e}")
        return
    name = st.text_input("Name des Materials", value=default_name, key=wkey("imp_name", src, default_name))
    if st.button("Material anlegen", disabled=material is None or not name.strip(), key=wkey("imp_go")):
        materials[cf.unique_name(name.strip(), materials)] = material
        cfg["materials"] = materials
        bump()
        st.rerun()


def _csv_material(text: str, tag: str) -> dict:
    c = st.columns(2)
    kind = c[0].radio("Werte sind", ["n, k", "ε"], horizontal=True, key=wkey("imp_kind", tag))
    unit = c[1].selectbox("Einheit der ersten Spalte", dispersion.UNITS, key=wkey("imp_unit", tag))
    data = dispersion.parse_csv(text)
    st.caption(f"{len(data)} Zeilen, {len(data[0])} Spalten")
    return dispersion.table_material("table_n" if kind == "n, k" else "table_eps", data, unit)
