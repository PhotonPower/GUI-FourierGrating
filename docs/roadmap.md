# Roadmap

Abnahme = alle genannten Tests grün (`pytest`; mit `-m solver` zusätzlich auf dem Server mit echtem Löser).
Reihenfolge wie aufgeführt (AGENTS.md).

- [x] **G0** Gerüst, Doku, CI, Server-Installation
  - Seiten *Einzelrechnung* (JSON laden, erster Scanpunkt, Tabelle/Diagramm/Diagnose/CSV), *Rechnungen*, *System*
  - Hintergrundrechnungen (`JobManager`), Tests ohne Löser, systemd/nginx
  - Abnahme: `pytest` grün (CI); auf dem Server `pytest -m solver` grün, Seite *System* zeigt Kern `cuda12` und die
    RTX 6000 Ada – **auf dem Zielsystem zu bestätigen**
- [x] **G1** Konfigurationseditor (2D-Schichttypen und CAD vorerst als JSON je Schicht)
  - Formulare für Grundeinstellungen (Dimension, Löser, Abbruch, Periode), Einfall (Zahl/Liste/Bereich),
    Materialien (n, [Re, Im], eps, Tensor), Superstrat/Substrat, Schichtliste (homogeneous, lamellar1d, profile1d;
    2D-Typen danach), Löseroptionen (rk, rcwa, backend, precision, threads)
  - JSON-Ansicht mit direkter Bearbeitung; Download/Upload; Konfiguration → Formular → Konfiguration verlustfrei
    (unbekannte Schlüssel bleiben erhalten)
  - Abnahme: Roundtrip-Tests über alle Beispiele von FourierGrating; Fehler von FourierGrating erscheinen am Feld
- [x] **G2** Scans und Sweeps
  - `solve_scan`, Spektren/Winkelgänge je Ordnung, Sweep-Kurven, Mehrfachauswahl von Ordnungen und Polarisation
  - Export wie `efficiencies.csv`; Vergleich mehrerer Rechnungen in einem Diagramm
  - Abnahme: Spalten identisch zu `ScanResult.columns`; Diagrammdaten-Test
- [x] **G3** Nahfeld
  - `near_field`: horizontale und vertikale Schnitte, Größen (|E|², Komponenten, Poynting), Materialgrenzen als Kontur
  - Export `.npy`/`meta.json` wie `fgsolve`
  - Abnahme: Achsen und Felder unverändert durchgereicht (Test mit Ersatzdaten), Vergleich mit `plot_nearfield.py`
- [x] **G4** Rechnungsverwaltung
  - Persistenz in `FG_GUI_DATA_DIR` (Konfiguration, Ergebnis, Diagnose, Laufzeit), Liste über Neustarts hinweg
  - Abbruch wartender Jobs, Warteschlange mit Position, Speicherbedarf grob abschätzen und anzeigen
  - Abnahme: Neustart-Test; gleichzeitige Sitzungen
- [x] **G5** CAD
  - STEP-Upload, `fouriergrating.cad.check` (Prüfcodes, Bänder), Vorschau der Schnitte; Körper → Materialien
  - Abnahme: Beispiel `cad_pillar_array.json` von FourierGrating durchgängig
- [x] **G6** Optimierung
  - `Simulation.value_and_grad`: Zielfunktion aus Ordnungen/Gewichten, Parameterwahl per JSON-Pointer,
    L-BFGS-B mit Grenzen, Verlauf live
  - Abnahme: `optimize_littrow.py` von FourierGrating reproduziert
- [x] **G7** Betrieb
  - Anmeldung am vorgeschalteten Proxy (nginx Basic-Auth oder OIDC), Benutzer aus dem Header in den Rechnungen, Logging,
    Aufräumen alter Ergebnisse und Uploads, Health-Check (`fg-gui-health`) fürs Monitoring

## Anforderungen an FourierGrating

Was der GUI fehlt, wird dort ergänzt (AGENTS.md, Abschnitt 1), nicht hier nachgebaut:

- Fehlermeldungen mit Feldpfad (JSON-Pointer, z. B. `/layers/1/materials/1`) in `FourierGratingError`, damit der
  Editor Fehler am Feld anzeigen kann. Heute enthalten sie nur Quelltextposition und Text (`unknown material 'x'`);
  `config_form.locate_error` rät über Stichwörter. Negative Schichtdicken werden nicht abgelehnt.
