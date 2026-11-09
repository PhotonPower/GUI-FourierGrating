"""Health-Check für das Monitoring (G7): ``fg-gui-health``, Exit-Code 0 = gesund, 1 = Fehler.

Prüft den Streamlit-Endpunkt ``/_stcore/health`` und lokal: beschreibbares Datenverzeichnis, FourierGrating
importierbar (nur Warnung, wenn die GUI ohne Löser betrieben wird).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

from . import settings as _settings


def check_data_dir(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".health"):
            pass
    except OSError as e:
        return False, f"{path} nicht beschreibbar: {e}"
    return True, f"{path} beschreibbar"


def check_url(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (feste, vom Betreiber gesetzte URL)
            body = r.read().decode().strip()
            return (r.status == 200 and body == "ok"), f"{url}: {r.status} {body}"
    except (OSError, ValueError) as e:
        return False, f"{url}: {e}"


def check_solver() -> tuple[bool, str]:
    from . import solver

    info = solver.info()
    return info.available, f"FourierGrating {info.version}" if info.available else f"FourierGrating fehlt: {info.error}"


def run(settings: _settings.Settings, url: str | None) -> tuple[bool, list[tuple[str, bool, str]]]:
    """(alles gesund, [(Name, ok, Text)]). Der Löser zählt nur mit ``FG_GUI_HEALTH_REQUIRE_SOLVER=1``."""
    results = [("Datenverzeichnis", *check_data_dir(settings.data_dir))]
    if url:
        results.append(("Streamlit", *check_url(url)))
    ok_solver, text = check_solver()
    require = os.environ.get("FG_GUI_HEALTH_REQUIRE_SOLVER", "") == "1"
    results.append(("Löser", ok_solver or not require, text))
    return all(r[1] for r in results), results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Health-Check der FourierGrating-GUI")
    ap.add_argument("--url", help="Basis-URL der GUI, z. B. http://herkules3.ito.uni-stuttgart.de:8505")
    args = ap.parse_args(argv)
    url = args.url.rstrip("/") + "/_stcore/health" if args.url else None
    ok, rows = run(_settings.load(), url)
    for name, good, text in rows:
        print(f"{'OK  ' if good else 'FAIL'} {name}: {text}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
