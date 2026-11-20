"""Profillinie aus einer STEP-Flächendatei als NURBS für ``profile1d`` (``shape: nurbs``, FourierGrating M24).

Keine Physik und kein Aufruf des Kerns: Die B-Spline-Kanten des Profils (Ebene CAD x, z; Extrusion entlang CAD y,
Achsen wie ``x = +X``, ``y = +Z``) werden gelesen, zu einer Kette verbunden, in rationale Bézier-Stücke zerlegt, auf
einen gemeinsamen Grad gebracht und zu einer NURBS-Kurve mit C⁰-Knoten zusammengesetzt. Die Breite der Kette wird auf
die Periode skaliert. Unterstützt werden nur B-Spline-Kanten (wie Nurbforge sie schreibt).
"""

from __future__ import annotations

import re

import numpy as np

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


class StepProfileError(ValueError):
    """Aus der Datei lässt sich keine Profillinie lesen."""


# ---------------------------------------------------------------- STEP lesen
def _entities(text: str) -> dict[int, str]:
    return {
        int(m.group(1)): m.group(2) for m in re.finditer(r"#(\d+)\s*=\s*(.*?);\s*(?=\n\s*#|\n\s*ENDSEC)", text, re.S)
    }


def _floats(s: str) -> list[float]:
    return [float(v) for v in re.findall(_NUM, s)]


def _ids(s: str) -> list[int]:
    return [int(v) for v in re.findall(r"#(\d+)", s)]


def _expand(mults: list[float], knots: list[float]) -> list[float]:
    return [k for m, k in zip(mults, knots, strict=True) for _ in range(int(m))]


def _bspline(body: str, points: dict[int, list[float]]) -> tuple[int, np.ndarray, list[float]] | None:
    """(Grad, homogene Kontrollpunkte [x·w, y·w, z·w, w], Knotenvektor) oder ``None``, wenn keine B-Spline-Kurve."""
    weights = None
    if body.lstrip().startswith("("):  # komplexe Entität (rational)
        m = re.search(r"B_SPLINE_CURVE\s*\(\s*(\d+)\s*,\s*\(([^)]*)\)", body)
        k = re.search(r"B_SPLINE_CURVE_WITH_KNOTS\s*\(\s*\(([^)]*)\)\s*,\s*\(([^)]*)\)", body)
        w = re.search(r"RATIONAL_B_SPLINE_CURVE\s*\(\s*\(([^)]*)\)", body)
        if not (m and k):
            return None
        degree, ids, knots = int(m.group(1)), _ids(m.group(2)), _expand(_floats(k.group(1)), _floats(k.group(2)))
        weights = _floats(w.group(1)) if w else None
    else:
        m = re.match(
            r"B_SPLINE_CURVE_WITH_KNOTS\s*\(\s*'[^']*'\s*,\s*(\d+)\s*,\s*\(([^)]*)\)\s*,\s*\.\w+\.\s*,\s*\.\w\.\s*,"
            r"\s*\.\w\.\s*,\s*\(([^)]*)\)\s*,\s*\(([^)]*)\)",
            body,
        )
        if not m:
            return None
        degree, ids, knots = int(m.group(1)), _ids(m.group(2)), _expand(_floats(m.group(3)), _floats(m.group(4)))
    if any(i not in points for i in ids) or len(knots) != len(ids) + degree + 1:
        return None
    if weights is not None and len(weights) != len(ids):
        return None
    xyz = np.array([points[i] for i in ids], dtype=float)
    w_arr = np.ones(len(ids)) if weights is None else np.asarray(weights, dtype=float)
    return degree, np.column_stack([xyz * w_arr[:, None], w_arr]), knots


# ---------------------------------------------------------------- Bézier-Stücke
def _insert_knot(p: int, knots: list[float], pts: np.ndarray, u: float) -> tuple[list[float], np.ndarray]:
    """Einmaliges Knoteneinfügen (Boehm) in homogenen Koordinaten."""
    k = max(i for i in range(p, len(knots) - p - 1) if knots[i] <= u < knots[i + 1])
    n = len(pts)
    out = np.empty((n + 1, pts.shape[1]))
    for i in range(n + 1):
        if i <= k - p:
            out[i] = pts[i]
        elif i >= k + 1:
            out[i] = pts[i - 1]
        else:
            a = (u - knots[i]) / (knots[i + p] - knots[i])
            out[i] = a * pts[i] + (1 - a) * pts[i - 1]
    return knots[: k + 1] + [u] + knots[k + 1 :], out


def _bezier_pieces(p: int, knots: list[float], pts: np.ndarray) -> list[np.ndarray]:
    for u in sorted({k for k in knots[p + 1 : -p - 1]}):
        while knots.count(u) < p:
            knots, pts = _insert_knot(p, knots, pts, u)
    return [pts[j * p : j * p + p + 1] for j in range((len(pts) - 1) // p)]


def _elevate(piece: np.ndarray, to: int) -> np.ndarray:
    """Gradanhebung eines Bézier-Stücks (homogen, also auch rational)."""
    while len(piece) - 1 < to:
        p = len(piece) - 1
        out = [piece[0]]
        out += [(i / (p + 1)) * piece[i - 1] + (1 - i / (p + 1)) * piece[i] for i in range(1, p + 1)]
        out.append(piece[-1])
        piece = np.array(out)
    return piece


# ---------------------------------------------------------------- Kette
def _profile_curves(text: str) -> list[tuple[int, np.ndarray, list[float]]]:
    ents = _entities(text)
    points = {i: _floats(b.split("(", 2)[-1]) for i, b in ents.items() if b.startswith("CARTESIAN_POINT")}
    used = {int(m.group(1)) for m in re.finditer(r"EDGE_CURVE\s*\(\s*'[^']*'\s*,\s*#\d+\s*,\s*#\d+\s*,\s*#(\d+)", text)}
    curves = [c for i in sorted(used) if i in ents and (c := _bspline(ents[i], points)) is not None]
    if not curves:
        raise StepProfileError("Die Datei enthält keine B-Spline-Kanten (nur diese kann die GUI als Profil lesen).")
    return curves


def _chain(curves: list[tuple[int, np.ndarray, list[float]]], tol: float):
    """Kurven (Ebene x, z) zu einer offenen Kette in Richtung +x verbinden (Grad, Punkte, Knoten, Anfang, Ende)."""
    segs = []
    for p, h, k in curves:
        xz = h[:, [0, 2]] / h[:, 3:4]
        segs.append((p, h, k, xz[0], xz[-1]))
    # doppelte Kanten (gleiche Endpunkte, auch umgekehrt) entfernen
    uniq, seen = [], set()
    for s in segs:
        key = tuple(sorted([tuple(np.round(s[3] / tol)), tuple(np.round(s[4] / tol))])) + (len(s[1]),)
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    ends = [(i, 0, s[3]) for i, s in enumerate(uniq)] + [(i, 1, s[4]) for i, s in enumerate(uniq)]

    def near(a, b):
        return float(np.max(np.abs(a - b))) <= tol

    free = [e for e in ends if sum(near(e[2], o[2]) for o in ends) == 1]
    if len(free) != 2:
        raise StepProfileError("Die Profilkanten bilden keine offene Kette (zwei freie Enden erwartet).")
    start = min(free, key=lambda e: e[2][0])  # Kette läuft netto in +x
    order, used, cur = [], set(), start
    while True:
        i, side, _ = cur
        used.add(i)
        p, h, k, a, b = uniq[i]
        if side == 0:
            order.append((p, h, k, a, b))
            tip = b
        else:  # Kurve rückwärts durchlaufen
            kk = [k[0] + k[-1] - v for v in reversed(k)]
            order.append((p, h[::-1], kk, b, a))
            tip = a
        nxt = [e for e in ends if e[0] not in used and near(e[2], tip)]
        if not nxt:
            break
        cur = nxt[0]
    if len(order) != len(uniq):
        raise StepProfileError("Die Profilkanten sind nicht zu einer einzigen Kette verbunden.")
    return order


def nurbs_profile(step_text: str, period_um: float) -> tuple[dict, dict]:
    """NURBS-Objekt (``degree``, ``knots``, ``points_um``, ``weights``) und Maße; Breite der Linie = Periode.

    ``info``: ``width`` und ``height`` in Dateieinheiten, ``scale``, ``height_um``, ``pieces``, ``degree``.
    """
    if period_um <= 0:
        raise StepProfileError("Die Periode muss größer als 0 sein.")
    curves = _profile_curves(step_text)

    def cad_y(c):
        return c[1][:, 1] / c[1][:, 3]

    best, err = None, "Kein Profil in der Ebene (CAD x, z) gefunden."
    for y in sorted({round(float(cad_y(c)[0]), 9) for c in curves}):  # Profilebene: alle Punkte mit gleichem CAD y
        sel = [c for c in curves if np.ptp(cad_y(c)) <= 1e-9 * max(1.0, abs(y)) and abs(float(cad_y(c)[0]) - y) < 1e-8]
        allp = np.concatenate([c[1][:, [0, 2]] / c[1][:, 3:4] for c in sel])
        tol = 1e-6 * max(float(np.ptp(allp[:, 0])), float(np.ptp(allp[:, 1])), 1e-12)
        try:
            best = _chain(sel, tol)
            break
        except StepProfileError as e:
            err = str(e)
    if best is None:
        raise StepProfileError(err)
    pieces = []
    for p, h, k, _a, _b in best:
        pieces += [(p, q) for q in _bezier_pieces(p, list(k), h)]
    deg = max(p for p, _ in pieces)
    pieces = [_elevate(q, deg) for _, q in pieces]
    homo = [pieces[0][0]] + [pt for q in pieces for pt in q[1:]]
    h = np.array(homo)
    xz = h[:, [0, 2]] / h[:, 3:4]
    n = len(pieces)
    knots = [0.0] * (deg + 1) + [float(j) for j in range(1, n) for _ in range(deg)] + [float(n)] * (deg + 1)
    width = float(xz[-1, 0] - xz[0, 0])
    junction = xz[::deg]  # Endpunkte der Stücke liegen auf der Kurve
    zmin = float(junction[:, 1].min())
    height = float(xz[:, 1].max() - zmin)
    if width <= 0 or height <= 0:
        raise StepProfileError("Breite oder Höhe des Profils ist 0.")
    if abs(float(xz[-1, 1] - xz[0, 1])) > 1e-6 * height:
        raise StepProfileError("Anfang und Ende der Linie liegen nicht gleich hoch (Profil nicht periodisch).")
    s = period_um / width
    pts = [[float((x - xz[0, 0]) * s), float((z - zmin) * s)] for x, z in xz]
    weights = [float(w) for w in h[:, 3]]
    out = {"degree": deg, "knots": knots, "points_um": pts}
    if any(abs(w - 1.0) > 1e-12 for w in weights):
        out["weights"] = weights
    info = {
        "width": width,
        "height": height,
        "scale": s,
        "height_um": float(xz[:, 1].max() - zmin) * s,
        "pieces": n,
        "degree": deg,
    }
    return out, info
