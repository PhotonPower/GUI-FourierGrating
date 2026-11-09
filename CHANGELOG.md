# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach SemVer.

## [0.1.0] – 2026-11-09

### Hinzugefügt (G0)
- Projektgerüst: Paket `fg_gui` (`src/`-Layout), `pyproject.toml`, Startbefehl `fg-gui`, `.streamlit/config.toml`.
- Seiten *Einzelrechnung* (Beispiel oder hochgeladene JSON-Konfiguration, erster Scanpunkt mit
  `fouriergrating.solve`, Effizienztabelle, Balkendiagramm, Diagnose, CSV-Download), *Rechnungen* (Jobliste),
  *System* (FourierGrating-Kern, CUDA, CAD-Slicer, GPU über `nvidia-smi`, Einstellungen).
- Hintergrundrechnungen über `JobManager` (Threadpool, Standard eine Rechnung gleichzeitig).
- Tests ohne Löser (Ersatzmodul), Seiten-Rauchtests mit `streamlit.testing`, CI (ruff, pytest, Python 3.10/3.12).
- Server: `scripts/install_server.sh`, `deploy/fg-gui.service`, `deploy/nginx-fg-gui.conf`,
  `deploy/fg-gui.env.example`.
- Dokumentation: README, AGENTS.md, Architektur, Roadmap G0–G7, Installation RTX-6000-Server, Entwicklung,
  Bedienung.
- Geprüft gegen FourierGrating 0.18.0 (`solver.MIN_VERSION`).
