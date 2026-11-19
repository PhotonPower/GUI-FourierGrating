"""Übersicht über die Struktur: Schnittbilder mit Maßen, nur aus der Konfiguration gezeichnet (kein Löser).

Die Zeichnung ist eine **Darstellung**, keine Rechengrundlage: Profile, Kreise, Ellipsen und NURBS-Ränder werden zum
Zeichnen abgetastet; gerechnet wird ausschließlich von FourierGrating. Koordinaten wie dort: ``y`` ist die
Schichtnormale (``y = 0`` an der Substratgrenze, nach oben), ``x`` und ``z`` liegen in der Gitterebene; ``layers``
laufen von unten (Substrat) nach oben (Superstrat).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

SAMPLES = 720  # Abtastpunkte entlang x für Profile und Schnitte
TWO_D_TYPES = ("polygon2d", "contour2d")
SIMPLE_NOTE = {
    "cad": "CAD-Körper – Höhe und Bänder liefert die Seite „CAD“ (Prüfen)",
    "rings": "Ringe (rotationssymmetrisch)",
}


# ---------------------------------------------------------------- Schichtstapel
@dataclass
class Layer:
    index: int
    type: str
    y0: float
    y1: float
    cfg: dict
    nominal: bool = False  # Höhe nicht aus der Konfiguration bekannt (z. B. CAD): nur angenommen
    bands: list[dict] = field(default_factory=list)  # CAD: Bänder aus dem Prüfbericht in Stapelkoordinaten

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def layer_height(layer: dict) -> float | None:
    """Dicke aus ``thickness_um`` bzw. ``depth_um`` (Profile); ``None``, wenn die Konfiguration keine nennt."""
    for key in ("thickness_um", "depth_um"):
        v = layer.get(key)
        if isinstance(v, int | float) and not isinstance(v, bool) and v >= 0:
            return float(v)
    return None


def cad_bands(report: dict | None) -> list[dict]:
    """Bänder (``y0_um`` < ``y1_um``) aus dem Prüfbericht von ``fouriergrating.cad.check``, von unten nach oben."""
    bands = [b for b in (report or {}).get("bands") or [] if isinstance(b, dict) and "y0_um" in b and "y1_um" in b]
    return sorted((b for b in bands if b["y1_um"] > b["y0_um"]), key=lambda b: b["y0_um"])


def stack(cfg: dict, cad_report: dict | None = None) -> list[Layer]:
    """Schichten von unten nach oben mit ``y0``/``y1``; Schichten ohne Dickenangabe erhalten eine Nennhöhe.

    Die erste CAD-Schicht erhält Höhe und Bänder aus ``cad_report`` (Prüfbericht der Seite „CAD“), sofern angegeben.
    """
    layers = [lay for lay in cfg.get("layers") or [] if isinstance(lay, dict)]
    known = [h for h in (layer_height(lay) for lay in layers) if h]
    nominal = float(np.median(known)) if known else 0.2
    bands = cad_bands(cad_report)
    out, y = [], 0.0
    for i, lay in enumerate(layers):
        h = layer_height(lay)
        kind = str(lay.get("type", "?"))
        cad_here = kind == "cad" and h is None and bands and not any(x.bands for x in out)
        if cad_here:
            base = bands[0]["y0_um"]
            h = bands[-1]["y1_um"] - base
        layer = Layer(i, kind, y, y + (h if h is not None else nominal), lay, h is None)
        if cad_here:
            layer.bands = [{**b, "y0_um": y + b["y0_um"] - base, "y1_um": y + b["y1_um"] - base} for b in bands]
        out.append(layer)
        y = layer.y1
    return out


def period(cfg: dict) -> tuple[float, float]:
    """(Periode x, Periode z); z ist 0 bei 1D."""
    p = cfg.get("period_um")
    if isinstance(p, dict):
        return float(p.get("x") or 0.0), float(p.get("z") or 0.0)
    if isinstance(p, int | float):
        return float(p), 0.0
    return 0.0, 0.0


def material_names(cfg: dict) -> list[str]:
    """Materialien in der Reihenfolge der Konfiguration (für feste Farben)."""
    mats = cfg.get("materials")
    return list(mats) if isinstance(mats, dict) else []


# ---------------------------------------------------------------- Geometrie (abgetastet)
def _poly_from(shape: dict) -> np.ndarray | None:
    """Umriss (x, z) einer Einschlussform als Polygon; ``None``, wenn die Form unbekannt ist."""
    if "vertices_um" in shape or "polygon_um" in shape:
        pts = shape.get("vertices_um", shape.get("polygon_um"))
        return np.asarray(pts, dtype=float).reshape(-1, 2)
    if "rectangle_um" in shape:
        r = shape["rectangle_um"]
        (cx, cz), (sx, sz) = r["center"], r["size"]
        return np.array(
            [
                [cx - sx / 2, cz - sz / 2],
                [cx + sx / 2, cz - sz / 2],
                [cx + sx / 2, cz + sz / 2],
                [cx - sx / 2, cz + sz / 2],
            ]
        )
    t = np.linspace(0.0, 2 * math.pi, 181)
    if "circle" in shape:
        c = shape["circle"]
        cx, cz = c["center_um"]
        return np.column_stack([cx + c["radius_um"] * np.cos(t), cz + c["radius_um"] * np.sin(t)])
    if "ellipse" in shape:
        c = shape["ellipse"]
        cx, cz = c["center_um"]
        rx, rz = c["radii_um"]
        a = math.radians(c.get("angle_deg", 0.0))
        ex, ez = rx * np.cos(t), rz * np.sin(t)
        return np.column_stack([cx + ex * math.cos(a) - ez * math.sin(a), cz + ex * math.sin(a) + ez * math.cos(a)])
    if "nurbs" in shape:
        return _nurbs(shape["nurbs"])
    return None


def _nurbs(n: dict) -> np.ndarray:
    """Rationale B-Spline abgetastet; bei ungültigen Angaben das Kontrollpolygon."""
    pts = np.asarray(n["points_um"], dtype=float).reshape(-1, 2)
    try:
        from scipy.interpolate import BSpline

        k = int(n["degree"])
        knots = np.asarray(n["knots"], dtype=float)
        w = np.asarray(n.get("weights") or np.ones(len(pts)), dtype=float)
        spline = BSpline(knots, np.column_stack([pts * w[:, None], w]), k)
        u = np.linspace(knots[k], knots[-k - 1], 200)
        v = spline(u)
        return v[:, :2] / v[:, 2:3]
    except Exception:  # noqa: BLE001 – nur zum Zeichnen: Kontrollpolygon als Ersatz
        return pts


def inclusions(layer: dict) -> list[tuple[str, np.ndarray, list[np.ndarray]]]:
    """(Material, Umriss, Löcher) je Einschluss bzw. Region einer 2D-Schicht, in Konfigurationsreihenfolge."""
    out = []
    for inc in layer.get("inclusions") or layer.get("regions") or []:
        if not isinstance(inc, dict):
            continue
        try:
            poly = _poly_from(inc)
            holes = [h for h in (_poly_from(h) for h in inc.get("holes") or []) if h is not None]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if poly is not None and len(poly) >= 3:
            out.append((str(inc.get("material", "")), poly, holes))
    return out


def profile_height(layer: dict, x: np.ndarray, px: float, z: float | None = None) -> np.ndarray | None:
    """Oberflächenhöhe g(x) (``profile1d``) bzw. g(x, z) (``profile2d``) zwischen 0 und der Tiefe, sonst ``None``."""
    depth = float(layer.get("depth_um") or 0.0)
    shape, x0 = layer.get("shape"), float(layer.get("x0_um") or 0.0)
    if px <= 0:
        return None
    if layer.get("type") == "profile2d":
        kx = 2 * math.pi / px
        if shape == "sinus_x":
            return depth / 2 * (1 + np.cos(kx * (x - x0)))
        if shape == "egg_crate":
            pz = float(layer.get("_pz") or 0.0)
            if pz <= 0 or z is None:
                return None
            return (
                depth
                / 4
                * (1 + np.cos(kx * (x - x0)))
                * (1 + math.cos(2 * math.pi / pz * (z - float(layer.get("z0_um") or 0.0))))
            )
        return None
    if shape == "sinus":
        return depth / 2 * (1 + np.cos(2 * math.pi / px * (x - x0)))
    if shape == "triangle":
        xs, ys = [0.0, float(layer["apex_x_um"])], [0.0, depth]
    elif shape == "points":
        xs, ys = list(map(float, layer["x_um"])), list(map(float, layer["y_um"]))
    else:
        return None
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    # periodisch fortgesetzt: nach dem letzten Punkt zurück zum Anfangswert bei x[0] + Periode
    return np.interp(np.mod(x - xs[0], px) + xs[0], xs + [xs[0] + px], ys + [ys[0]])


def xy_runs(layer: dict, px: float, pz: float, z0: float, background: str = "") -> list[tuple[float, float, str]]:
    """Materialverlauf einer 2D-Schicht entlang x bei z = z0 als Abschnitte (von, bis, Material) – nur zum Zeichnen."""
    from matplotlib.path import Path

    x = (np.arange(SAMPLES) + 0.5) / SAMPLES * px
    mat = np.full(SAMPLES, layer.get("background", background), dtype=object)
    for material, poly, holes in inclusions(layer):
        for dx in (-px, 0.0, px):  # Nachbarzellen: Einschlüsse dürfen über den Zellrand ragen
            for dz in (-pz, 0.0, pz):
                pts = np.column_stack([x - dx, np.full(SAMPLES, z0 - dz)])
                inside = Path(poly).contains_points(pts)
                for hole in holes:
                    inside &= ~Path(hole).contains_points(pts)
                mat[inside] = material
    runs, start = [], 0
    for i in range(1, SAMPLES + 1):
        if i == SAMPLES or mat[i] != mat[start]:
            runs.append((float(x[start] - px / SAMPLES / 2), float(x[i - 1] + px / SAMPLES / 2), str(mat[start])))
            start = i
    return runs


# ---------------------------------------------------------------- Zeichnen
def _colors(cfg: dict) -> dict[str, Any]:
    from matplotlib import colormaps

    cmap = colormaps["tab10"]
    names = material_names(cfg)
    for extra in (cfg.get("superstrate"), cfg.get("substrate")):
        if isinstance(extra, str) and extra not in names:
            names.append(extra)
    return {n: cmap(i % 10) for i, n in enumerate(names)}


def _fill(colors: dict, name: str) -> Any:
    return colors.get(name, (0.8, 0.8, 0.8, 1.0))


def _dim_h(ax, x0: float, x1: float, y: float, text: str, above: bool = False) -> None:
    ax.annotate("", (x0, y), (x1, y), arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": "k"}, annotation_clip=False)
    ax.annotate(
        text,
        ((x0 + x1) / 2, y),
        ha="center",
        va="bottom" if above else "top",
        fontsize=8,
        xytext=(0, 2 if above else -2),
        textcoords="offset points",
        annotation_clip=False,
    )


def _dim_v(ax, x: float, y0: float, y1: float, text: str) -> None:
    ax.annotate("", (x, y0), (x, y1), arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": "k"}, annotation_clip=False)
    ax.annotate(
        text,
        (x, (y0 + y1) / 2),
        ha="left",
        va="center",
        fontsize=8,
        xytext=(4, 0),
        textcoords="offset points",
        annotation_clip=False,
    )


def _legend(ax, colors: dict, used: set[str]) -> None:
    from matplotlib.patches import Patch

    handles = [Patch(facecolor=colors[n], edgecolor="k", label=n) for n in colors if n in used]
    if handles:
        ax.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(1.0, 1.0),
            fontsize=8,
            title="Material",
            title_fontsize=8,
            frameon=False,
        )


def _cad_bands(ax, lay: Layer, ox: float, px: float, box, label: bool) -> None:
    """Bänder einer CAD-Schicht: wahre Höhen; die Flächenanteile der Materialien teilen das Band in x nur ein.

    Die Lage der Materialien im Band ergibt sich aus der Draufsicht (Seite „CAD“), nicht aus diesem Bild.
    """
    for b in lay.bands:
        fr = {str(k): float(v) for k, v in (b.get("area_fractions") or {}).items() if v and v > 0}
        total = sum(fr.values()) or 1.0
        x = ox
        for name, v in sorted(fr.items(), key=lambda kv: -kv[1]):
            w = px * v / total
            box(x, x + w, b["y0_um"], b["y1_um"], name, hatch=None if len(fr) == 1 else "..")
            x += w
        if not fr:
            box(ox, ox + px, b["y0_um"], b["y1_um"], "", alpha=0.35, hatch="xx")
        if label:
            parts = ", ".join(f"{k} {v / total:.0%}" for k, v in fr.items())
            ax.text(
                ox + px / 2,
                (b["y0_um"] + b["y1_um"]) / 2,
                f"{b.get('kind', '')} · {b['y1_um'] - b['y0_um']:.4g} µm\n{parts}",
                ha="center",
                va="center",
                fontsize=7,
                bbox={"facecolor": "w", "alpha": 0.7, "lw": 0, "pad": 1.5},
            )


def figure_xy(cfg: dict, z0: float = 0.0, periods: int = 1, equal: bool = True, cad_report: dict | None = None):
    """Schnitt (x, y) durch den Stapel mit Maßen: Perioden, Schichtdicken, Lamellenbreiten, Profiltiefen.

    2D-Schichten werden bei z = ``z0`` geschnitten. Superstrat und Substrat sind halbunendlich und nur angedeutet.
    """
    from matplotlib.figure import Figure
    from matplotlib.patches import Polygon, Rectangle

    px, pz = period(cfg)
    layers = stack(cfg, cad_report)
    colors = _colors(cfg)
    used: set[str] = set()
    top = layers[-1].y1 if layers else 0.0
    cap = max(top * 0.35, 0.1 * px, 0.05)  # sichtbare Höhe von Substrat und Superstrat
    width = px * periods
    fig = Figure(figsize=(8.5, 5.5))
    ax = fig.subplots()

    def box(x0, x1, y0, y1, name, **kw):
        used.add(name)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=_fill(colors, name), edgecolor="k", lw=0.6, **kw))

    sub, sup = str(cfg.get("substrate", "")), str(cfg.get("superstrate", ""))
    box(0, width, -cap, 0, sub, alpha=0.45, hatch="//")
    box(0, width, top, top + cap, sup, alpha=0.45, hatch="\\\\")
    ax.text(width / 2, -cap / 2, f"Substrat: {sub}", ha="center", va="center", fontsize=8)
    ax.text(width / 2, top + cap / 2, f"Superstrat: {sup}", ha="center", va="center", fontsize=8)

    for lay in layers:
        c = lay.cfg
        for k in range(periods):
            ox = k * px
            if lay.type == "homogeneous":
                box(ox, ox + px, lay.y0, lay.y1, str(c.get("material", "")))
            elif lay.type == "lamellar1d":
                bp, mats = c.get("breakpoints_um") or [], c.get("materials") or []
                for i in range(min(len(mats), len(bp) - 1)):
                    box(ox + bp[i], ox + bp[i + 1], lay.y0, lay.y1, str(mats[i]))
                    if k == 0:  # Breite der Lamelle als Maß in der Mitte
                        ax.text(
                            (bp[i] + bp[i + 1]) / 2,
                            (lay.y0 + lay.y1) / 2,
                            f"{bp[i + 1] - bp[i]:.4g}",
                            ha="center",
                            va="center",
                            fontsize=7,
                            rotation=90 if bp[i + 1] - bp[i] < 0.06 * px else 0,
                        )
            elif lay.type in ("profile1d", "profile2d"):
                g = profile_height({**c, "_pz": pz}, np.linspace(0, px, SAMPLES + 1), px, z0)
                if g is None:
                    box(ox, ox + px, lay.y0, lay.y1, str(c.get("below", "")), alpha=0.5, hatch="..")
                    continue
                xs = np.linspace(0, px, SAMPLES + 1) + ox
                curve = lay.y0 + g
                for name, ys, base in ((c.get("below", ""), curve, lay.y0), (c.get("above", ""), curve, lay.y1)):
                    used.add(str(name))
                    verts = list(zip(xs, ys, strict=True)) + [(xs[-1], base), (xs[0], base)]
                    ax.add_patch(Polygon(verts, facecolor=_fill(colors, str(name)), edgecolor="none"))
                ax.plot(xs, curve, "k", lw=0.8)
                ax.plot([ox, ox + px], [lay.y1, lay.y1], "k:", lw=0.4)
            elif lay.type in TWO_D_TYPES:
                for a, b, name in xy_runs(c, px, pz, z0):
                    box(ox + a, ox + b, lay.y0, lay.y1, name)
            elif lay.bands:
                _cad_bands(ax, lay, ox, px, box, k == 0)
            else:
                box(ox, ox + px, lay.y0, lay.y1, "", alpha=0.35, hatch="xx", linestyle="--")
                ax.text(
                    ox + px / 2,
                    (lay.y0 + lay.y1) / 2,
                    SIMPLE_NOTE.get(lay.type, lay.type),
                    ha="center",
                    va="center",
                    fontsize=8,
                )
    # Maße: Schichtdicken rechts, Periode unten
    dx = width + 0.04 * max(width, 0.1)
    for lay in layers:
        _dim_v(
            ax,
            dx,
            lay.y0,
            lay.y1,
            f"{lay.index + 1}: {lay.type}\n{lay.height:.4g} µm" + (" (angenommen)" if lay.nominal else ""),
        )
    _dim_h(
        ax,
        0,
        width,
        -cap * 1.18,
        f"Periode Λx = {px:.4g} µm" + (f" (×{periods})" if periods > 1 else ""),
    )
    ax.set_xlim(-0.12 * width, width * 1.6)
    ax.set_ylim(-cap * 1.5, top + cap * 1.1)
    if equal:
        ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    z_note = (
        f", Schnitt bei z = {z0:.4g} µm" if any(layer.type in (*TWO_D_TYPES, "profile2d") for layer in layers) else ""
    )
    ax.set_title(f"Schnitt x–y{z_note} · Gesamtdicke der Schichten {top:.4g} µm", fontsize=10)
    _legend(ax, colors, used)
    fig.tight_layout()
    return fig


def figure_xz(cfg: dict, layer_index: int, periods: int = 1):
    """Draufsicht (x, z) auf eine 2D-Schicht (``polygon2d``/``contour2d``) mit Perioden- und Formmaßen."""
    from matplotlib.figure import Figure
    from matplotlib.patches import Polygon, Rectangle

    px, pz = period(cfg)
    lay = next((lay for lay in stack(cfg) if lay.index == layer_index), None)
    if lay is None or lay.type not in TWO_D_TYPES or px <= 0 or pz <= 0:
        raise ValueError("Draufsicht nur für polygon2d/contour2d-Schichten mit Perioden x und z")
    colors = _colors(cfg)
    used = {str(lay.cfg.get("background", ""))}
    fig = Figure(figsize=(7, 6))
    ax = fig.subplots()
    for i in range(periods):
        for j in range(periods):
            ox, oz = i * px, j * pz
            ax.add_patch(
                Rectangle(
                    (ox, oz),
                    px,
                    pz,
                    facecolor=_fill(colors, str(lay.cfg.get("background", ""))),
                    edgecolor="k",
                    lw=0.4,
                    ls=":",
                )
            )
            for material, poly, holes in inclusions(lay.cfg):
                used.add(material)
                ax.add_patch(Polygon(poly + [ox, oz], facecolor=_fill(colors, material), edgecolor="k", lw=0.8))
                for hole in holes:
                    ax.add_patch(
                        Polygon(
                            hole + [ox, oz],
                            facecolor=_fill(colors, str(lay.cfg.get("background", ""))),
                            edgecolor="k",
                            lw=0.6,
                            ls="--",
                        )
                    )
    for inc in lay.cfg.get("inclusions") or lay.cfg.get("regions") or []:
        _shape_dims(ax, inc)
    _dim_h(ax, 0, px, -0.05 * pz, f"Λx = {px:.4g} µm")
    _dim_v(ax, px * periods + 0.03 * px, 0, pz, f"Λz = {pz:.4g} µm")
    ax.set_xlim(-0.08 * px, px * periods * 1.25)
    ax.set_ylim(-0.12 * pz, pz * periods * 1.05)
    ax.set_aspect("equal")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("z (µm)")
    ax.set_title(f"Draufsicht x–z, Schicht {lay.index + 1} ({lay.type}), Dicke {lay.height:.4g} µm", fontsize=10)
    _legend(ax, colors, used)
    fig.tight_layout()
    return fig


def _shape_dims(ax, inc: Any) -> None:
    """Maße der ersten Periode: Rechteck (Breite × Tiefe), Kreis (Durchmesser), Ellipse (Halbachsen)."""
    if not isinstance(inc, dict):
        return
    try:
        if "rectangle_um" in inc:
            (cx, cz), (sx, sz) = inc["rectangle_um"]["center"], inc["rectangle_um"]["size"]
            _dim_h(ax, cx - sx / 2, cx + sx / 2, cz - sz / 2, f"{sx:.4g}")
            _dim_v(ax, cx + sx / 2, cz - sz / 2, cz + sz / 2, f"{sz:.4g}")
        elif "circle" in inc:
            (cx, cz), r = inc["circle"]["center_um"], inc["circle"]["radius_um"]
            _dim_h(ax, cx - r, cx + r, cz, f"⌀ {2 * r:.4g}", above=True)
        elif "ellipse" in inc:
            (cx, cz), (rx, rz) = inc["ellipse"]["center_um"], inc["ellipse"]["radii_um"]
            ax.annotate(f"a = {rx:.4g}, b = {rz:.4g}", (cx, cz), ha="center", va="center", fontsize=7)
    except (KeyError, TypeError, ValueError):
        return


def describe(cfg: dict, cad_report: dict | None = None) -> list[dict]:
    """Tabelle zur Struktur: Schicht, Typ, Dicke, Materialien – für die Übersicht neben dem Bild.

    Mit ``cad_report`` erscheinen die Bänder der CAD-Schicht als eigene Zeilen (Nr z. B. ``1.2``).
    """
    rows = []
    for lay in stack(cfg, cad_report):
        c = lay.cfg
        mats = (
            c.get("materials")
            or [b.get("material") for b in c.get("bodies") or [] if isinstance(b, dict) and b.get("material")]
            or [m for m in (c.get("background"), c.get("material"), c.get("below"), c.get("above")) if m]
        )
        rows.append(
            {
                "Nr": lay.index + 1,
                "Typ": lay.type,
                "Dicke (µm)": round(lay.height, 6) if not lay.nominal else None,
                "y von (µm)": round(lay.y0, 6),
                "y bis (µm)": round(lay.y1, 6),
                "Materialien": ", ".join(map(str, mats)),
            }
        )
        for j, b in enumerate(lay.bands):
            fr = b.get("area_fractions") or {}
            rows.append(
                {
                    "Nr": f"{lay.index + 1}.{j + 1}",
                    "Typ": f"CAD-Band ({b.get('kind', '')})",
                    "Dicke (µm)": round(b["y1_um"] - b["y0_um"], 6),
                    "y von (µm)": round(b["y0_um"], 6),
                    "y bis (µm)": round(b["y1_um"], 6),
                    "Materialien": ", ".join(f"{k} {v:.1%}" for k, v in fr.items()),
                }
            )
    return rows
