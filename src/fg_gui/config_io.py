"""Konfigurationen lesen und auflisten. Das Schema prüft FourierGrating selbst (Fehler beim Rechnen)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Datei ist kein JSON-Objekt."""


def parse(text: str | bytes) -> dict:
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Kein gültiges JSON (Zeile {e.lineno}, Spalte {e.colno}): {e.msg}") from e
    if not isinstance(cfg, dict):
        raise ConfigError("Die Konfiguration muss ein JSON-Objekt sein.")
    return cfg


def dumps(cfg: dict) -> str:
    return json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"


def list_examples(directory: Path | None) -> list[Path]:
    """JSON-Dateien eines Beispielverzeichnisses (nicht rekursiv), sortiert."""
    if directory is None or not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.json") if p.is_file())


def summary(cfg: dict) -> dict[str, Any]:
    """Kurzübersicht für die Anzeige (nur Ablesen der Schlüssel, keine Auswertung)."""
    layers = cfg.get("layers") or []
    return {
        "Dimension": cfg.get("dimension", "?"),
        "Löser": cfg.get("solver", "?"),
        "Schichten": len(layers) if isinstance(layers, list) else "?",
        "Schichttypen": ", ".join(sorted({str(L.get("type", "?")) for L in layers if isinstance(L, dict)})) or "–",
        "Materialien": ", ".join(cfg.get("materials", {}) or {}) or "–",
        "Sweep": (cfg.get("sweep") or {}).get("parameter", "–"),
        "Nahfeld": "ja" if (cfg.get("nearfield") or {}).get("enabled") else "nein",
    }
