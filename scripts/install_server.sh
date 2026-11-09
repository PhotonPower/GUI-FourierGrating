#!/usr/bin/env bash
# Installiert GUI und FourierGrating (mit CUDA) in ein gemeinsames venv. AlmaLinux 10, siehe
# docs/deployment_rtx6000.md. Voraussetzung: FourierGrating-Build-Abhängigkeiten
# (FourierGrating/scripts/setup_almalinux10.sh --with-cuda) und NVIDIA-Treiber.
#
#   scripts/install_server.sh --prefix /opt/fg-gui [--cpu] [--python python3.12]
#
# Erwartet die Checkouts <prefix>/FourierGrating und <prefix>/GUI-FourierGrating. Keine Zugangsdaten in diesem
# Skript oder in Remote-URLs (AGENTS.md).
set -euo pipefail

PREFIX=/opt/fg-gui
PYTHON=python3
CUDA=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --python) PYTHON="$2"; shift 2 ;;
    --cpu) CUDA=0; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
done

FG_SRC="$PREFIX/FourierGrating"
GUI_SRC="$PREFIX/GUI-FourierGrating"
VENV="$PREFIX/venv"
[[ -d "$FG_SRC" ]] || { echo "Fehlt: $FG_SRC (git clone https://github.com/PhotonPower/FourierGrating.git)" >&2; exit 1; }
[[ -d "$GUI_SRC" ]] || { echo "Fehlt: $GUI_SRC" >&2; exit 1; }

"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip

if [[ $CUDA -eq 1 ]]; then
  # RTX 6000 Ada: sm_89 (FourierGrating docs/python.md, "Aus den Quellen mit CUDA")
  "$VENV/bin/python" -m pip install "$FG_SRC" \
    -C cmake.define.FG_ENABLE_CUDA=ON -C cmake.define.CMAKE_CUDA_ARCHITECTURES=89
else
  "$VENV/bin/python" -m pip install "$FG_SRC"
fi

"$VENV/bin/python" -m pip install -e "$GUI_SRC"

"$VENV/bin/python" - <<'PY'
import fouriergrating as fg
print("FourierGrating", fg.__version__, "Kern:", fg.core_variant(), "CUDA:", fg.cuda_available())
PY
echo "Fertig. Start: $VENV/bin/fg-gui (oder systemd, deploy/fg-gui.service)"
