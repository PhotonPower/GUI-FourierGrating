#!/usr/bin/env bash
# Installiert die GUI als systemd-Benutzerdienst (kein root nötig). Aufruf im Checkout:
#   scripts/install_user_service.sh [--no-start]
# Legt ~/.config/fg-gui/env aus deploy/fg-gui.user.env.example an (nur wenn sie fehlt) und aktiviert den Dienst.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
START=1
[[ "${1:-}" == "--no-start" ]] && START=0

[[ -x "$REPO/.venv/bin/fg-gui" ]] || { echo "Fehlt: $REPO/.venv/bin/fg-gui (pip install -e . im venv)" >&2; exit 1; }
[[ "$REPO" == "$HOME/GUI-FourierGrating" ]] || echo "Hinweis: die Unit erwartet das Repository unter \$HOME/GUI-FourierGrating (jetzt: $REPO)" >&2

mkdir -p "$HOME/.config/systemd/user" "$HOME/.config/fg-gui"
cp deploy/fg-gui.user.service "$HOME/.config/systemd/user/fg-gui.service"
if [[ ! -f "$HOME/.config/fg-gui/env" ]]; then
  sed "s#/home/BENUTZER#$HOME#g" deploy/fg-gui.user.env.example > "$HOME/.config/fg-gui/env"
  echo "Angelegt: $HOME/.config/fg-gui/env (bitte prüfen)"
fi
mkdir -p "$(sed -n 's/^FG_GUI_DATA_DIR=//p' "$HOME/.config/fg-gui/env")"

systemctl --user daemon-reload
if [[ $START -eq 1 ]]; then
  systemctl --user enable --now fg-gui.service
  systemctl --user restart fg-gui.service
  sleep 5
  systemctl --user --no-pager status fg-gui.service | head -5
fi
loginctl show-user "$USER" | grep -q '^Linger=yes' || echo "Hinweis: für Betrieb ohne Anmeldung 'loginctl enable-linger $USER' ausführen." >&2
echo "Protokoll: journalctl --user -u fg-gui -f"
