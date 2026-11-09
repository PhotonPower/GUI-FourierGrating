"""Optimierung mit Gradienten (G6): Zielfunktion aus Ordnungen und Gewichten, Parameter per JSON-Pointer, L-BFGS-B.

Der Gradient kommt aus ``Simulation.value_and_grad`` von FourierGrating (diskrete Adjungierte); hier steht nur die
Steuerung: Eingaben prüfen, ``scipy.optimize.minimize`` aufrufen, den Verlauf festhalten. Die Simulation wird als
Objekt übergeben (``solver.simulation``), damit sich alles ohne FourierGrating testen lässt.
"""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import numpy as np

SIDES = ("R", "T")
#: Vorlage: Littrow-Gitter aus FourierGrating/examples/python/optimize_littrow.py
LITTROW_PERIOD, LITTROW_LAMBDA = 0.5, 0.6328


class SpecError(ValueError):
    """Ungültige Eingabe der Optimierung."""


class _Stopped(Exception):
    pass


# ---------------------------------------------------------------- JSON-Pointer (RFC 6901)
def _tokens(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise SpecError(f"JSON-Pointer muss mit „/“ beginnen: {pointer!r}")
    return [t.replace("~1", "/").replace("~0", "~") for t in pointer[1:].split("/")]


def get_pointer(cfg: Any, pointer: str) -> Any:
    node = cfg
    for tok in _tokens(pointer):
        try:
            node = node[int(tok)] if isinstance(node, list) else node[tok]
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise SpecError(f"Parameter {pointer!r} existiert in der Konfiguration nicht") from e
    return node


def set_pointer(cfg: dict, pointer: str, value: Any) -> dict:
    """Kopie der Konfiguration mit geändertem Wert."""
    out = copy.deepcopy(cfg)
    toks = _tokens(pointer)
    if not toks:
        raise SpecError("Leerer Pointer")
    node = out
    for tok in toks[:-1]:
        node = node[int(tok)] if isinstance(node, list) else node[tok]
    last = toks[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    return out


def numeric_pointers(
    cfg: dict, roots: tuple[str, ...] = ("layers", "materials", "incidence")
) -> list[tuple[str, float]]:
    """Zahlen der Konfiguration unter ``roots`` (Kandidaten für Parameter), z. B. ``/layers/0/thickness_um``."""
    out: list[tuple[str, float]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            out.append((path, float(node)))
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}/{str(k).replace('~', '~0').replace('/', '~1')}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")

    for r in roots:
        if r in cfg:
            walk(cfg[r], f"/{r}")
    return out


def apply_to_config(cfg: dict, values: dict[str, float]) -> dict:
    out = copy.deepcopy(cfg)
    for pointer, v in values.items():
        out = set_pointer(out, pointer, float(v))
    return out


# ---------------------------------------------------------------- Eingaben
@dataclass
class Param:
    pointer: str
    start: float
    lower: float
    upper: float


@dataclass
class Spec:
    terms: list[tuple[str, int, int, float]]  # (Seite, n, m, Gewicht): L = Σ w · e
    params: list[Param]
    maximize: bool = True
    maxiter: int = 200
    ftol: float = 1e-12

    def validate(self) -> None:
        if not self.terms:
            raise SpecError("Mindestens eine Ordnung für die Zielfunktion angeben.")
        for side, _, _, w in self.terms:
            if side not in SIDES:
                raise SpecError(f"Seite muss R oder T sein, nicht {side!r}")
            if not np.isfinite(w):
                raise SpecError("Gewichte müssen endliche Zahlen sein.")
        if not any(w != 0 for *_, w in self.terms):
            raise SpecError("Alle Gewichte sind 0.")
        if not self.params:
            raise SpecError("Mindestens einen Parameter wählen.")
        seen = set()
        for p in self.params:
            if p.pointer in seen:
                raise SpecError(f"Parameter {p.pointer} doppelt")
            seen.add(p.pointer)
            if not (np.isfinite(p.lower) and np.isfinite(p.upper) and np.isfinite(p.start)):
                raise SpecError(f"{p.pointer}: Start und Grenzen müssen Zahlen sein.")
            if p.lower >= p.upper:
                raise SpecError(f"{p.pointer}: Untergrenze muss kleiner als die Obergrenze sein.")
            if not p.lower <= p.start <= p.upper:
                raise SpecError(f"{p.pointer}: Start {p.start:g} liegt außerhalb [{p.lower:g}, {p.upper:g}].")
        if self.maxiter < 1:
            raise SpecError("Höchstzahl der Iterationen muss ≥ 1 sein.")

    def objective(self) -> dict[tuple[str, int, int], float]:
        obj: dict[tuple[str, int, int], float] = {}
        for side, n, m, w in self.terms:
            obj[(side, int(n), int(m))] = obj.get((side, int(n), int(m)), 0.0) + float(w)
        return obj

    def to_json(self) -> dict:
        return {
            "terms": [list(t) for t in self.terms],
            "params": [asdict(p) for p in self.params],
            "maximize": self.maximize,
            "maxiter": self.maxiter,
            "ftol": self.ftol,
        }

    @staticmethod
    def from_json(d: dict) -> Spec:
        return Spec(
            terms=[(str(s), int(n), int(m), float(w)) for s, n, m, w in d["terms"]],
            params=[Param(p["pointer"], p["start"], p["lower"], p["upper"]) for p in d["params"]],
            maximize=bool(d.get("maximize", True)),
            maxiter=int(d.get("maxiter", 200)),
            ftol=float(d.get("ftol", 1e-12)),
        )


class Simulation(Protocol):
    def set_parameter(self, pointer: str, value: float) -> None: ...
    def value_and_grad(self, objective: Any, params: list[str]) -> tuple[float, Any]: ...


# ---------------------------------------------------------------- Verlauf (live lesbar)
@dataclass
class History:
    """Verlauf einer laufenden Optimierung; vom Job beschrieben, von der Seite gelesen (threadsicher)."""

    rows: list[dict] = field(default_factory=list)
    stop: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, row: dict) -> None:
        with self._lock:
            self.rows.append(row)

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self.rows)


# ---------------------------------------------------------------- Lauf
def run(sim: Simulation, spec: Spec, history: History | None = None) -> dict:
    """L-BFGS-B mit den Gradienten der Simulation. Ergebnis ist ein JSON-fähiges ``dict`` (wird gespeichert)."""
    from scipy.optimize import minimize

    spec.validate()
    history = history or History()
    pointers = [p.pointer for p in spec.params]
    objective = spec.objective()
    sign = -1.0 if spec.maximize else 1.0
    t0 = time.time()
    best: dict[str, Any] = {"value": None, "x": None}

    def fun(x: np.ndarray):
        if history.stop.is_set():
            raise _Stopped
        for ptr, v in zip(pointers, x, strict=True):
            sim.set_parameter(ptr, float(v))
        value, grad = sim.value_and_grad(objective, pointers)
        value = float(value)
        better = best["value"] is None or (value > best["value"] if spec.maximize else value < best["value"])
        if better:
            best["value"], best["x"] = value, [float(v) for v in x]
        history.add(
            {
                "eval": len(history.rows) + 1,
                "value": value,
                "best": best["value"],
                "x": [float(v) for v in x],
                "grad_norm": float(np.linalg.norm(grad)),
                "t": time.time() - t0,
            }
        )
        return sign * value, sign * np.asarray(grad, dtype=float)

    x0 = [p.start for p in spec.params]
    bounds = [(p.lower, p.upper) for p in spec.params]
    stopped, nit, message, success = False, 0, "", True
    try:
        res = minimize(
            fun, x0=x0, jac=True, method="L-BFGS-B", bounds=bounds, options={"ftol": spec.ftol, "maxiter": spec.maxiter}
        )
        x_opt, value = [float(v) for v in res.x], sign * float(res.fun)
        nit, message, success = int(res.nit), str(res.message), bool(res.success)
    except _Stopped:
        stopped, message, success = True, "Vom Nutzer gestoppt", False
        x_opt, value = best["x"] or x0, best["value"]
    rows = history.snapshot()
    return {
        "success": success,
        "stopped": stopped,
        "message": message,
        "nit": nit,
        "nfev": len(rows),
        "value": value,
        "maximize": spec.maximize,
        "start": dict(zip(pointers, x0, strict=True)),
        "x": dict(zip(pointers, x_opt, strict=True)),
        "history": rows,
        "spec": spec.to_json(),
        "runtime_s": time.time() - t0,
    }


# ---------------------------------------------------------------- Anzeige
def history_frame(rows: list[dict], pointers: list[str]):
    import pandas as pd

    data = {
        "Auswertung": [r["eval"] for r in rows],
        "Zielwert": [r["value"] for r in rows],
        "Bester": [r["best"] for r in rows],
    }
    for i, ptr in enumerate(pointers):
        data[ptr] = [r["x"][i] for r in rows]
    data["|Gradient|"] = [r["grad_norm"] for r in rows]
    return pd.DataFrame(data)


def littrow_preset() -> dict:
    """Konfiguration, Parameter, Grenzen und Ordnung des Beispiels ``optimize_littrow.py`` (FourierGrating)."""
    import math

    cfg = {
        "dimension": "1D",
        "solver": "rcwa",
        "truncation": {"Nx": 12},
        "period_um": {"x": LITTROW_PERIOD},
        "incidence": {
            "lambda_um": LITTROW_LAMBDA,
            "phi_deg": math.degrees(math.asin(LITTROW_LAMBDA / (2 * LITTROW_PERIOD))),
            "delta_deg": 90,
        },
        "materials": {"air": {"n": 1.0}, "al": {"n": [1.38, 7.62]}},
        "superstrate": "air",
        "substrate": "al",
        "layers": [
            {
                "type": "lamellar1d",
                "thickness_um": 0.15,
                "breakpoints_um": [0.0, 0.25, LITTROW_PERIOD],
                "materials": ["al", "air"],
            }
        ],
    }
    spec = Spec(
        terms=[("R", -1, 0, 1.0)],
        params=[
            Param("/layers/0/thickness_um", 0.2, 0.03, 0.40),
            Param("/layers/0/breakpoints_um/1", 0.3, 0.05, 0.45),
        ],
    )
    return {"config": cfg, "spec": spec}
