# GUI-FourierGrating

Streamlit-Oberfläche für [FourierGrating](https://github.com/PhotonPower/FourierGrating) – Beugung an periodischen
und isolierten Strukturen mit der Differentialmethode (implizites Runge–Kutta) und RCWA. Zielsystem ist ein
AlmaLinux-10-Server mit **NVIDIA RTX 6000 Ada**; bedient wird im Browser.

Die GUI enthält **keine Physik**: Sie liest und schreibt Konfigurationen im JSON-Format von FourierGrating und ruft
dessen Python-API (`fouriergrating`) auf. Rechnungen laufen im Hintergrund, die Oberfläche bleibt bedienbar.

> **Status (v0.2.0):** G0, G1 umgesetzt – Gerüst, Seiten *Editor*, *Einzelrechnung*, *Rechnungen*, *System*; Hintergrundrechnung,
> Tests, CI, Server-Installation (systemd, nginx). Nächster Schritt: G2 Scans und Sweeps
> (siehe [`docs/roadmap.md`](docs/roadmap.md)).

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [`docs/user_guide.md`](docs/user_guide.md) | **Bedienung** der Oberfläche |
| [`docs/deployment_rtx6000.md`](docs/deployment_rtx6000.md) | Installation auf dem Server (AlmaLinux 10, CUDA, systemd, nginx/SSH-Tunnel) |
| [`docs/development.md`](docs/development.md) | Entwicklung: lokale Umgebung, Tests ohne Löser, Stil |
| [`docs/architecture.md`](docs/architecture.md) | Module, Datenfluss, Hintergrundrechnungen, Schnittstelle zu FourierGrating |
| [`docs/roadmap.md`](docs/roadmap.md) | Meilensteine G0–G7 mit Abnahmekriterien und Status |
| [`AGENTS.md`](AGENTS.md) | Arbeitsregeln für KI-Agenten und Entwickler |
| [`CHANGELOG.md`](CHANGELOG.md) | Änderungen je Version |

Maßgeblich für Konfigurationsformat und API sind die Dokumente von FourierGrating:
`docs/config_format.md`, `docs/python.md`, `docs/user_guide.md`.

## Schnellstart (Entwicklung)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install fouriergrating                    # optional: CPU-Wheel; ohne Löser startet die GUI trotzdem
FG_GUI_EXAMPLES_DIR=../FourierGrating/examples ./scripts/run_dev.sh
pytest                                        # läuft ohne fouriergrating
```

Auf dem Server: [`docs/deployment_rtx6000.md`](docs/deployment_rtx6000.md) (FourierGrating mit CUDA aus den Quellen,
`scripts/install_server.sh`, `deploy/fg-gui.service`).

## Verzeichnisse

```
src/fg_gui/          Python-Paket
  app.py             Einstieg (Navigation), Start: fg-gui bzw. streamlit run src/fg_gui/app.py
  pages/             Streamlit-Seiten (single, jobs, system)
  solver.py          einzige Stelle, die fouriergrating importiert
  jobs.py            Hintergrundrechnungen (JobManager)
  config_io.py       JSON lesen/schreiben, Beispiele auflisten
  results.py         Ergebnisobjekte -> Tabellen
  settings.py        Einstellungen aus FG_GUI_*-Variablen
  state.py           geteilte Ressourcen (st.cache_resource), Sitzungszustand
tests/               pytest, inkl. Seiten-Rauchtests (streamlit.testing), Ersatzmodul für fouriergrating
deploy/              systemd-Unit, nginx-Beispiel, Umgebungsdatei
scripts/             Server-Installation, Entwicklungsstart
docs/                Dokumentation
.streamlit/          Streamlit-Konfiguration (gilt beim Start im Repository-Verzeichnis)
```

## Lizenz

MIT, siehe [`LICENSE`](LICENSE).
