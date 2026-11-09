#!/usr/bin/env bash
# Entwicklungsstart mit automatischem Neuladen. Weitere Argumente gehen an Streamlit.
set -euo pipefail
cd "$(dirname "$0")/.."
export FG_GUI_DATA_DIR="${FG_GUI_DATA_DIR:-data}"
export FG_GUI_RETENTION_DAYS="${FG_GUI_RETENTION_DAYS:-90}"   # beendete Rechnungen nach 90 Tagen aufräumen
exec python -m streamlit run src/fg_gui/app.py --server.runOnSave true "$@"
