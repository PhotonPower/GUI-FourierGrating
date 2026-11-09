# Installation auf dem RTX-6000-Server (AlmaLinux 10)

Ziel: GUI als systemd-Dienst unter einem eigenen Benutzer, FourierGrating mit CUDA (sm_89) im selben venv,
Zugriff über nginx mit TLS und Anmeldung oder über einen SSH-Tunnel.

## 1. Voraussetzungen

* NVIDIA-Treiber installiert, `nvidia-smi` zeigt die RTX 6000 Ada.
* Build-Abhängigkeiten von FourierGrating inkl. CUDA-Toolkit ≥ 12.6 Update 2:
  `sudo ./scripts/setup_almalinux10.sh --with-cuda` im FourierGrating-Checkout (dort `docs/build_almalinux10.md`).
* Python 3.12 (`python3`), `git`.

## 2. Benutzer und Checkouts

```bash
sudo useradd --system --create-home --home-dir /opt/fg-gui --shell /sbin/nologin fggui
sudo usermod -aG video fggui            # falls /dev/nvidia* nur für die Gruppe video lesbar ist
sudo -u fggui git clone https://github.com/PhotonPower/FourierGrating.git     /opt/fg-gui/FourierGrating
sudo -u fggui git clone https://github.com/PhotonPower/GUI-FourierGrating.git /opt/fg-gui/GUI-FourierGrating
```

Für private Repositories einen Deploy-Key oder den Git-Credential-Helper verwenden – **keine Tokens in URLs**.
Für reproduzierbare Stände FourierGrating auf ein Tag setzen (`git -C /opt/fg-gui/FourierGrating checkout v0.18.0`).

## 3. Installation

```bash
sudo -u fggui /opt/fg-gui/GUI-FourierGrating/scripts/install_server.sh --prefix /opt/fg-gui
```

Das Skript legt `/opt/fg-gui/venv` an, baut FourierGrating mit
`-C cmake.define.FG_ENABLE_CUDA=ON -C cmake.define.CMAKE_CUDA_ARCHITECTURES=89` und installiert die GUI editierbar.
Am Ende muss `Kern: cuda12  CUDA: True` erscheinen. Prüfung mit echtem Löser:

```bash
cd /opt/fg-gui/GUI-FourierGrating
sudo -u fggui /opt/fg-gui/venv/bin/pip install -e ".[dev]"
sudo -u fggui /opt/fg-gui/venv/bin/pytest -m solver
```

## 4. Dienst

```bash
sudo mkdir -p /etc/fg-gui
sudo cp deploy/fg-gui.env.example /etc/fg-gui/fg-gui.env     # anpassen
sudo cp deploy/fg-gui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fg-gui
systemctl status fg-gui
curl -s http://herkules3.ito.uni-stuttgart.de:8505/_stcore/health    # "ok"
journalctl -u fg-gui -f                         # Protokoll
```

Wichtige Variablen in `/etc/fg-gui/fg-gui.env`:

| Variable | Bedeutung | Standard |
|---|---|---|
| `FG_GUI_DATA_DIR` | Laufzeitdaten | `data` (Dienst: `/var/lib/fg-gui`) |
| `FG_GUI_EXAMPLES_DIR` | Beispielkonfigurationen | – (Dienst: `FourierGrating/examples`) |
| `FG_GUI_WORKERS` | gleichzeitige Rechnungen | 1 |
| `FG_GUI_JOB_HISTORY` | Rechnungen im Speicher; ohne Datenverzeichnis-Speicher relevant (mit Speicher bleibt alles erhalten; Aufräumen siehe unten) | 50 |
| `FG_GUI_USER_HEADER` | Header mit dem vom Proxy angemeldeten Benutzer (`X-Remote-User`); leer = keine Anmeldung | – |
| `FG_GUI_RETENTION_DAYS` | beendete Rechnungen und ungenutzte Uploads nach so vielen Tagen löschen | 0 (aus) |
| `FG_GUI_MAX_RUNS` | höchstens so viele Rechnungen behalten (älteste zuerst löschen) | 0 (unbegrenzt) |
| `FG_GUI_LOG_LEVEL`, `FG_GUI_LOG_FILE` | Protokollstufe; zusätzliche rotierende Logdatei | `INFO`, – |
| `FG_GUI_HEALTH_REQUIRE_SOLVER` | `1`: `fg-gui-health` meldet Fehler, wenn FourierGrating fehlt | – |
| `FG_NUM_THREADS`, `FG_CORE`, `FG_PRECISION`, `FG_GPU_STREAMS` | an FourierGrating | siehe dort |

## 5. Zugriff

**Variante A – SSH-Tunnel** (einzelne Nutzer, nichts weiter zu konfigurieren):

```bash
ssh -N -L 8505:herkules3.ito.uni-stuttgart.de:8505 benutzer@server     # dann http://localhost:8505
```

**Variante B – nginx** mit TLS und Basic-Auth (`deploy/nginx-fg-gui.conf`):

```bash
sudo dnf install nginx httpd-tools
sudo htpasswd -c /etc/nginx/fg-gui.htpasswd <benutzer>
sudo cp deploy/nginx-fg-gui.conf /etc/nginx/conf.d/fg-gui.conf   # server_name, Zertifikat anpassen
sudo setsebool -P httpd_can_network_connect 1                    # SELinux: Proxy zu herkules3.ito.uni-stuttgart.de:8505
sudo firewall-cmd --permanent --add-service=https && sudo firewall-cmd --reload
sudo nginx -t && sudo systemctl enable --now nginx
```

Den Port 8505 **nicht** nach außerhalb der Institutsfirewall öffnen: Streamlit hat keine Anmeldung.

### Benutzer und Anmeldung

Die GUI meldet nicht selbst an. Setzt man `FG_GUI_USER_HEADER=X-Remote-User`, übernimmt sie den Namen, den der Proxy
nach erfolgreicher Anmeldung in diesen Header schreibt; Rechnungen gehören dann dem Benutzer (sichtbar in der Liste
und im Log). nginx überschreibt den Header mit `$remote_user` (Basic-Auth, siehe Vorlage). Für OIDC (Uni-Konto,
Keycloak, …) schaltet man `oauth2-proxy` vor Streamlit bzw. nginx per `auth_request` und gibt dessen Benutzer als
`X-Remote-User` weiter. **Voraussetzung:** Streamlit ist nur über den Proxy erreichbar; wer den Port direkt
erreicht, kann den Header selbst setzen. Dann Streamlit an `127.0.0.1` binden (`--server.address 127.0.0.1`) oder
den Port per Firewall auf den Proxy beschränken. Es gibt keine Rollen: jeder Angemeldete sieht alle Rechnungen
(Schalter „Nur meine Rechnungen“) und kann sie löschen.

### Monitoring, Log, Aufräumen

```bash
fg-gui-health --url http://herkules3.ito.uni-stuttgart.de:8505    # Exit-Code 0 = gesund (Nagios/Icinga/cron)
journalctl -u fg-gui -f                                           # Log: eingereicht/gestartet/fertig/Fehler
```

Die Laufzeitdaten wachsen mit jeder Rechnung. `FG_GUI_RETENTION_DAYS=90` und/oder `FG_GUI_MAX_RUNS=500` räumen beim
Start, danach stündlich beim Einreichen und per Knopf auf der Seite *System* auf. Wartende und laufende Rechnungen
bleiben immer; Uploads nur, wenn keine gespeicherte Konfiguration sie nennt.

## 6. Aktualisieren

```bash
sudo -u fggui git -C /opt/fg-gui/GUI-FourierGrating pull
sudo -u fggui git -C /opt/fg-gui/FourierGrating fetch --tags && sudo -u fggui git -C /opt/fg-gui/FourierGrating checkout <tag>
sudo -u fggui /opt/fg-gui/GUI-FourierGrating/scripts/install_server.sh --prefix /opt/fg-gui
sudo systemctl restart fg-gui
```

Laufende Rechnungen gehen beim Neustart verloren (bis G4).

## 7. Fehlersuche

| Symptom | Ursache / Abhilfe |
|---|---|
| *System*: „nicht importierbar“ | falsches venv im Dienst (`ExecStart`), oder Build gescheitert – `install_server.sh` erneut |
| Kern `cpu` statt `cuda12` | kein CUDA-Build, `FG_CORE=cpu` gesetzt oder GPU nicht sichtbar (Gruppe `video`, `CUDA_VISIBLE_DEVICES`) |
| keine GPU-Tabelle | `nvidia-smi` fehlt im `PATH` des Dienstes oder Treiberproblem |
| Seite lädt, bleibt leer (nginx) | WebSocket-Header fehlen (`Upgrade`, `Connection`) |
| 502 Bad Gateway | Dienst läuft nicht, oder SELinux-Boolean nicht gesetzt |
