"""Eingabefelder, die direkt in ein Konfigurations-``dict`` schreiben (Editor, Nahfeld).

Jedes Feld zeigt den Wert aus dem ``dict`` und schreibt nur bei einer Änderung zurück (:func:`config_form.assign`).
Die Widget-Schlüssel enthalten die Ladegeneration ``fg_gen``: Wird eine Konfiguration geladen oder die Struktur
geändert, beginnen alle Felder neu.
"""

from __future__ import annotations

import streamlit as st

from fg_gui import config_form as cf


def wkey(*parts) -> str:
    return f"fg{st.session_state.get('fg_gen', 0)}_" + "_".join(str(p) for p in parts)


def number(container, label_, d: dict, key: str, default: float = 0.0, **kw) -> None:
    cur = d.get(key, default)
    cur = float(cur) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else float(default)
    v = container.number_input(label_, value=cur, format="%.10g", key=wkey(id(d), key), **kw)
    cf.assign(d, key, v, float(default))


def integer(container, label_, d: dict, key: str, default: int = 0, minimum: int = 0) -> None:
    cur = d.get(key, default)
    cur = int(cur) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else default
    v = container.number_input(label_, value=cur, min_value=minimum, step=1, key=wkey(id(d), key))
    cf.assign(d, key, int(v), default)


def choice(container, label_, d: dict, key: str, options, default: str | None = None) -> None:
    options = list(options)
    cur = d.get(key, default if default is not None else (options[0] if options else ""))
    if cur not in options:
        options.append(cur)
    v = container.selectbox(label_, options, index=options.index(cur), key=wkey(id(d), key))
    cf.assign(d, key, v, cur if key not in d else None)


def text_list(container, label_: str, d: dict, key: str) -> None:
    cur = d.get(key, [])
    raw = container.text_input(
        label_, value=cf.format_list(cur) if isinstance(cur, list) else str(cur), key=wkey(id(d), key)
    )
    try:
        cf.assign(d, key, cf.parse_list(raw), cur if key in d else [])
    except cf.FormError as e:
        container.error(f"{label_}: {e}")


def complex_input(container, label_: str, d: dict, key: str, default: float = 1.0) -> None:
    cur = d.get(key, default)
    re_, im = cf.complex_parts(cur)
    c1, c2 = container.columns(2)
    nr = c1.number_input(f"{label_} Re", value=re_, format="%.10g", key=wkey(id(d), key, "re"))
    ni = c2.number_input(f"{label_} Im", value=im, format="%.10g", key=wkey(id(d), key, "im"))
    if (nr, ni) != (re_, im):
        d[key] = cf.complex_value(nr, ni)
