# Roadmap

Abnahme = alle genannten Tests grün (`pytest`; mit `-m solver` zusätzlich auf dem Server mit echtem Löser).
Reihenfolge wie aufgeführt (AGENTS.md).

- [x] **G0** Gerüst, Doku, CI, Server-Installation
  - Seiten *Einzelrechnung* (JSON laden, erster Scanpunkt, Tabelle/Diagramm/Diagnose/CSV), *Rechnungen*, *System*
  - Hintergrundrechnungen (`JobManager`), Tests ohne Löser, systemd/nginx
  - Abnahme: `pytest` grün (CI); auf dem Server `pytest -m solver` grün, Seite *System* zeigt Kern `cuda12` und die
    RTX 6000 Ada – **auf dem Zielsystem zu bestätigen**
- [ ] **G1** Konfigurationseditor
  - Formulare für Grundeinstellungen (Dimension, Löser, Abbruch, Periode), Einfall (Zahl/Liste/Bereich),
    Materialien (n, [Re, Im], eps, Tensor), Superstrat/Substrat, Schichtliste (homogeneous, lamellar1d, profile1d;
    2D-Typen danach), Löseroptionen (rk, rcwa, backend, precision, threads)
  - JSON-Ansicht mit direkter Bearbeitung; Download/Upload; Konfiguration → Formular → Konfiguration verlustfrei
    (unbekannte Schlüssel bleiben erhalten)
  - Abnahme: Roundtrip-Tests über alle Beispiele von FourierGrating; Fehler von FourierGrating erscheinen am Feld
- [ ] **G2** Scans und Sweeps
  - `solve_scan`, Spektren/Winkelgänge je Ordnung, Sweep-Kurven, Mehrfachauswahl von Ordnungen und Polarisation
  - Export wie `efficiencies.csv`; Vergleich mehrerer Rechnungen in einem Diagramm
  - Abnahme: Spalten identisch zu `ScanResult.columns`; Diagrammdaten-Test
- [ ] **G3** Nahfeld
  - `near_field`: horizontale und vertikale Schnitte, Größen (|E|², Komponenten, Poynting), Materialgrenzen als Kontur
  - Export `.npy`/`meta.json` wie `fgsolve`
  - Abnahme: Achsen und Felder unverändert durchgereicht (Test mit Ersatzdaten), Vergleich mit `plot_nearfield.py`
- [ ] **G4** Rechnungsverwaltung
  - Persistenz in `FG_GUI_DATA_DIR` (Konfiguration, Ergebnis, Diagnose, Laufzeit), Liste über Neustarts hinweg
  - Abbruch wartender Jobs, Warteschlange mit Position, Speicherbedarf grob abschätzen und anzeigen
  - Abnahme: Neustart-Test; gleichzeitige Sitzungen
- [ ] **G5** CAD
  - STEP-Upload, `fouriergrating.cad.check` (Prüfcodes, Bänder), Vorschau der Schnitte; Körper → Materialien
  - Abnahme: Beispiel `cad_pillar_array.json` von FourierGrating durchgängig
- [ ] **G6** Optimierung
  - `Simulation.value_and_grad`: Zielfunktion aus Ordnungen/Gewichten, Parameterwahl per JSON-Pointer,
    L-BFGS-B mit Grenzen, Verlauf live
  - Abnahme: `optimize_littrow.py` von FourierGrating reproduziert
- [ ] **G7** Betrieb
  - Anmeldung (nginx/OIDC), Benutzer in Jobs, Logging, Aufräumen alter Ergebnisse, Health-Check im Monitoring

## Anforderungen an FourierGrating

Was der GUI fehlt, wird dort ergänzt (AGENTS.md, Abschnitt 1), nicht hier nachgebaut:

- (noch keine)
