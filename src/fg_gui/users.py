"""Benutzer aus einem Proxy-Header (G7). Streamlit selbst kennt keine Anmeldung.

Ein vorgeschalteter Proxy (nginx mit Basic-Auth oder OIDC, z. B. oauth2-proxy) meldet an und trägt den Namen in einen
Header ein (``FG_GUI_USER_HEADER``). Das ist nur sicher, wenn Streamlit ausschließlich über den Proxy erreichbar ist:
sonst kann jeder den Header selbst setzen (docs/deployment_rtx6000.md).
"""

from __future__ import annotations

import re
from collections.abc import Mapping

MAX_LEN = 64
_BAD = re.compile(r"[^\w@.+\-]")


def user_from_headers(headers: Mapping[str, str] | None, header: str) -> str:
    """Bereinigter Benutzername aus ``headers[header]`` (ohne Beachtung der Groß-/Kleinschreibung); sonst ``""``."""
    if not header or not headers:
        return ""
    wanted = header.lower()
    for k, v in headers.items():
        if k.lower() == wanted:
            return _BAD.sub("_", str(v).strip())[:MAX_LEN]
    return ""
