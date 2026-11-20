# Roadmap

Abnahme = alle genannten Tests grün (`pytest`; mit `-m solver` zusätzlich auf dem Server mit echtem Löser).
Reihenfolge wie aufgeführt (AGENTS.md).

- [x] **G0** Gerüst, Doku, CI, Server-Installation
  - Seiten *Einzelrechnung* (JSON laden, erster Scanpunkt, Tabelle/Diagramm/Diagnose/CSV), *Rechnungen*, *System*
  - Hintergrundrechnungen (`JobManager`), Tests ohne Löser, systemd/nginx
  - Abnahme: `pytest` grün (CI); auf dem Server `pytest -m solver` grün, Seite *System* zeigt Kern `cuda12` und die
    RTX 6000 Ada – auf dem Zielsystem bestätigt (herkules3, 17.11.2026)
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
  - Danach ergänzt (0.8.1–0.9.1): Formulare für 2D-Schichten im Editor, Sitzungskennung `?s=` mit wiederhergestelltem
    Editor-Entwurf, Download fertiger Rechnungen (ZIP) und Modelle (JSON)
- [x] **G8** Dispersive Materialien (setzt FourierGrating M22 voraus, enthalten ab v0.19.0; Plan v2.18 Teil 8)
  - Materialformular: neue Arten *Tabelle (n, k)*, *Tabelle (ε)*, *Sellmeier*, *Cauchy*, *Drude–Lorentz* neben n, ε,
    Hauptwerten und Tensor; bei Hauptwerten je Komponente fest oder Modell (vorerst als JSON je Komponente)
  - Tabellen: CSV hochladen oder einfügen, Einheit (µm, nm, eV), Interpolation (`linear`/`cubic`), Extrapolation
    (`error`/`constant`). Gespeichert wird immer inline (`data`), nie ein Serverpfad – Rechnungen bleiben
    reproduzierbar und als JSON vollständig herunterladbar. Hochgeladene Konfigurationen mit `file` werden beim
    Laden inline umgewandelt (Pfade nur innerhalb `FG_GUI_DATA_DIR`, wie bei CAD)
  - Import einer refractiveindex.info-YAML über `fouriergrating.materials.from_refractiveindex` (in `solver.py`)
  - Materialbibliothek: gemeinsamer, vom Betrieb gepflegter Ordner `FG_GUI_DATA_DIR/materials/` (CSV/YAML, nur
    lesbar für Nutzer); Auswahl kopiert das Modell inline in die Konfiguration. `docs/deployment_rtx6000.md` ergänzen
  - Vorschau im Formular: n, k (bzw. ε′, ε″) über λ aus `fg.material_eps`, Einfallsbereich des Scans hinterlegt;
    Bereichsfehler und Sellmeier-Pole von FourierGrating erscheinen am Material (JSON-Pointer aus der Meldung)
  - Seite *Scans*: optional n, k der dispersiven Materialien je Scanpunkt aus `diagnostics["materials"]`;
    `materials.csv` im ZIP-Download; Seite *Optimierung*: Modellwerte als Parameter anbietbar
    (`/materials/<name>/n/sellmeier/B/0` usw.)
  - Voraussetzung FourierGrating ab v0.19.0 (`solver.MIN_VERSION`); Ersatzmodul um `material_eps` und `materials.from_refractiveindex` erweitert
  - Abnahme: Roundtrip Formular ↔ Konfiguration für alle neuen Beispiele von FourierGrating (verlustfrei, unbekannte
    Schlüssel bleiben); `file` → `data` gleichwertig; Vorschau-Daten unverändert aus `material_eps` durchgereicht
    (Ersatzdaten); mit `-m solver`: `examples/dispersive_metal_grating.json` (Kopie in `tests/data/`) rechnet, Vorschau-
    und Diagnosewerte stimmen überein, `file` und `data` liefern bitgleiche Ergebnisse
- [x] **G9** Rückmeldungen der Nutzer (0.12.0–0.12.2)
  - HDF5-Download je Rechnung (`h5export.py`, Abhängigkeit `h5py`), Aufbau in `docs/user_guide.md`
  - Nahfeld: 1D-Schnitte (Linien) aus den Karten am nächsten Gitterpunkt, mit CSV
  - Editor: Reiter *Struktur* – Schnittbild x–y und Draufsicht x–z mit Maßen (`structure.py`); CAD-Schichten mit
    Bändern aus der CAD-Prüfung (0.12.1)
  - Nahfeld: Rechenart „Nur eine Linie“ (2D; `ny = 1`, `nz = 1`) (0.12.2)
  - Abnahme: HDF5 lesbar für alle Arten (Test mit `h5py`); Linien identisch zu Zeile/Spalte der Karte; alle Beispiele
    von FourierGrating lassen sich zeichnen; mit `-m solver`: gerechnete Linie (1D und 2D) gleich der Karten-Zeile
- [x] **G10** CAD in 1D-Gittern (FourierGrating M23, ab 0.20.0) (0.13.0)
  - Seite *CAD*: Hinweis auf z-invariante Körper, Zellursprung nur x₀, `z_cut_um` optional, keine Schnitthöhen, Normalenfeld
    nur Raster; Bänder mit Längenanteilen, eine Vorschau (Profil in (x, y)); `NOT_Z_INVARIANT` erklärt; Warnung bei
    `z_cut_um` in 2D
  - Reiter *Struktur*: Bänder und Profil in 1D wie in 2D
  - Abnahme: AppTest mit Ersatzmodul; mit `-m solver`: `cad_line_grating_1d.json` (Kopie in `tests/data/`) prüft und rechnet
    (Energiebilanz), `z_cut_um` außerhalb → `OUT_OF_RANGE`, Säulen als 1D → `NOT_Z_INVARIANT`
- [x] **G11** Einfache Linie aus STEP im Editor (1D): auf die Periode skaliert, Material unter/über der Linie (0.14.0)
  - STEP-Datei mit genau einem Körper (Fläche unter der Linie), Breite auf die Periode skaliert (`cad.scale_step`),
    Material unten = Körper, oben = Hintergrund; als Menüpunkt „cad: Linie aus STEP-Datei“ in „Neue Schicht“
- [x] **G12** NURBS-Linie in 1D: Schichttyp `profile1d` mit `shape: nurbs` im Editor (FourierGrating M24) (0.15.0)
  - Formular für `profile1d` mit `shape: nurbs` (Kontrollpunkt-Tabelle, Grad, Knoten, Tiefe), Schnittbild zeichnet
    die Linie; Abnahme: AppTest, mit `-m solver` rechnet das Beispiel und der Startwert (Energiebilanz)
- [x] **G13** STEP-Flächenmodell (offene extrudierte Linie, z. B. Nurbforge) als NURBS-Schicht importieren (0.16.0)
  - STEP-Flächenmodell (offene extrudierte Linie, `SHELL_OPEN` im CAD-Weg) wird in `step_profile.py` zu einer
    NURBS-Kurve; Abnahme: Kette, Skalierung, Gradanhebung (Tests), mit `-m solver` rechnet die Nurbforge-Datei

## Anforderungen an FourierGrating

Was der GUI fehlt, wird dort ergänzt (AGENTS.md, Abschnitt 1), nicht hier nachgebaut:

- Nahfeld: Lage des Schnitts in x wählbar (z. B. `vertical_x_um`) bzw. x-Gitter ab beliebigem Startwert. Heute beginnt
  das x-Gitter immer bei 0, daher lässt sich ein Tiefenprofil (Linie entlang y) nur bei x = 0 rechnen; die GUI wählt
  sonst nur die nächste Spalte einer Karte aus.
- CAD-Schichten in 1D-Konfigurationen (`dimension: 1D`, Periode z = 0): **in FourierGrating seit v0.20.0 vorhanden**
  (M23, `docs/cad.md` dort; `solver.MIN_VERSION` ist 0.20.0). Erlaubt sind z-invariante Körper, also Linien, die entlang
  FG z extrudiert sind (Standard −CAD Y). FourierGrating schneidet sie einmal in der Ebene (x, y), die Bänder werden
  `homogeneous`, `lamellar1d` oder `sectioned1d`. Beispiel: `examples/cad_line_grating_1d.json` mit
  `cad/line_grating.step`. Nicht z-invariante Körper wie die Säulen von `cad_pillar_array.json` meldet `cad.check`
  sofort als `NOT_Z_INVARIANT`. Das beobachtete endlose Rechnen betraf 0.19.0, die noch keinen 1D-Pfad hatte. Die
  Freigabe in der GUI ist erledigt (G10, 0.13.0).
- NURBS-Linie in 1D (FourierGrating M24, `profile1d` mit `shape: nurbs`): **auf `main` (PR #32), noch nicht getaggt**
  (Tag weiter v0.20.0). Die GUI hat dafür ein Formular (G12) und einen STEP-Import (G13); sobald ein Tag mit M24
  existiert, `solver.MIN_VERSION` anheben und die Versionsangaben in README und `docs/deployment_rtx6000.md` anpassen.
- Fehlermeldungen mit Feldpfad (JSON-Pointer, z. B. `/layers/1/materials/1`) in `FourierGratingError`, damit der
  Editor Fehler am Feld anzeigen kann. Heute enthalten sie nur Quelltextposition und Text (`unknown material 'x'`);
  `config_form.locate_error` rät über Stichwörter. Negative Schichtdicken werden nicht abgelehnt.
- Dispersion (FourierGrating M22): seit v0.19.0 in FourierGrating (`solver.MIN_VERSION` ist inzwischen 0.20.0). Für
  die GUI offen: `material_eps` und `diagnostics["materials"]` kennen nur ε bzw. n der Rechenpunkte – eine
  Brechzahl-Vorschau (n, k) über λ ohne Rechnung bräuchte ein öffentliches `fg.material_n` (heute nur privat
  `_core.material_values`); die Vorschau zeigt deshalb ε′ und ε″.
