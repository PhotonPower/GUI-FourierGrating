"""Startbefehl ``fg-gui``: ``streamlit run`` auf die App, weitere Argumente gehen an Streamlit.

Beispiel: ``fg-gui --server.port 8502``. Ohne Angabe gelten .streamlit/config.toml im Arbeitsverzeichnis bzw. die
Streamlit-Standards.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    from streamlit.web import cli as stcli

    app = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app), *(sys.argv[1:] if argv is None else argv)]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
