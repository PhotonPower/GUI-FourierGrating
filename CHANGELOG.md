# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach SemVer.

## [0.2.0] – 2026-11-09

### Hinzugefügt (G1)
- Seite *Editor* (Startseite): Konfiguration neu anlegen, aus Beispiel oder Datei laden, per Formular bearbeiten,
  als JSON ansehen/ändern und herunterladen; Rechnen mit Fehleranzeige.
- Formulare: Grundeinstellungen (Dimension, Löser, Abbruch, Periode, Superstrat/Substrat), Einfall (Zahl, Liste
  `a, b`, Bereich `von:bis:Schritte`), Materialien (n, ε, Hauptwerte ε mit Euler-Winkeln, Tensor als JSON),
  Schichten (`homogeneous`, `lamellar1d` als Tabelle, `profile1d`; andere Typen als JSON je Schicht), Löseroptionen.
- Nur geänderte Felder werden geschrieben: unbekannte Schlüssel, Reihenfolge und Zahlenformate bleiben erhalten;
  Roundtrip-Tests über alle Beispiele von FourierGrating.
- Fehler von FourierGrating werden dem Reiter bzw. der Schicht zugeordnet (Stichwörter; Feldpfade fehlen dort noch,
  siehe `docs/roadmap.md`).

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
