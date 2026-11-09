# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach SemVer.

## [0.9.1] – 2026-11-09

### Hinzugefügt
- Seite *Rechnungen*: **Rechnung herunterladen (.zip)** für fertige Rechnungen (Konfiguration, Metadaten, lesbare
  Tabellen je Art – `orders.csv`/`totals.json`, `efficiencies.csv`, Nahfeld-Arrays wie `fgsolve`, `history.csv`/
  `optimum.json` – sowie die gespeicherten Rohdateien unter `raw/`) und **Modell herunterladen (.json)** (Konfiguration
  im Format von FourierGrating). Der Editor konnte das Modell schon im Reiter *JSON* herunterladen.

### Behoben
- Seite *Rechnungen*: Bei Optimierungen und CAD-Prüfungen waren die Schaltflächen „In der Optimierung/im CAD öffnen“
  doppelt vorhanden (doppelte Widget-Kennung).

## [0.9.0] – 2026-11-09

### Hinzugefügt
- Sitzungskennung in der Adresszeile (`…/?s=1a2b3c4d5e6f`): Wer die Adresse öffnet (Lesezeichen, anderes Gerät, nach einem
  Neustart des Servers), arbeitet an denselben Rechnungen weiter („Nur meine Rechnungen“) und findet die zuletzt
  bearbeitete Konfiguration im Editor wieder (`FG_GUI_DATA_DIR/sessions/<Kennung>.json`, wird mit
  `FG_GUI_RETENTION_DAYS` aufgeräumt). Die Kennung steht auch in der Seitenleiste. Mit Anmeldung am Proxy
  (`FG_GUI_USER_HEADER`) gehören die Rechnungen weiter dem Benutzer.
- Die Kennung ist ein Zugangsschlüssel: wer sie kennt, sieht diese Rechnungen. Ungültige Kennungen werden ignoriert.

## [0.8.1] – 2026-11-09

### Hinzugefügt
- Editor, Reiter *Schichten*: bei `"dimension": "2D"` Formulare für `polygon2d` (Einschlüsse als Tabelle: Rechteck
  oder Polygon), `contour2d` (Regionen: Kreis, Ellipse, Polygon; NURBS und Löcher bleiben erhalten und sind im JSON
  der Schicht bearbeitbar), `profile2d` (egg_crate, sinus_x), jeweils mit Faktorisierung und Normalenfeld. In 1D
  werden weiter nur die 1D-Typen angeboten. Unveränderte Einträge bleiben im Roundtrip bitgleich.

### Geändert
- Aufräumen nach 90 Tagen ist in `scripts/run_dev.sh` und in `deploy/fg-gui.env.example` voreingestellt.

## [0.8.0] – 2026-11-09

### Hinzugefügt (G7)
- Benutzer: `FG_GUI_USER_HEADER` (z. B. `X-Remote-User`) liest den vom Proxy gesetzten Namen; Rechnungen gehören dem
  Benutzer statt der Browsersitzung („Nur meine Rechnungen“ gilt dann über Sitzungen und Geräte hinweg); Anzeige in
  der Seitenleiste und in der Rechnungsliste. Ohne Angabe bleibt alles wie bisher.
- Logging (`fg_gui.*`): Einreichen, Start, Ende, Fehler, Abbruch, Löschen mit Benutzer und Laufzeit; stderr
  (journald) und optional rotierende Datei (`FG_GUI_LOG_FILE`, `FG_GUI_LOG_LEVEL`).
- Aufräumen: `FG_GUI_RETENTION_DAYS` und `FG_GUI_MAX_RUNS` löschen beendete Rechnungen; Uploads nur, wenn sie alt und
  in keiner gespeicherten Konfiguration mehr genannt sind. Beim Start, danach höchstens stündlich beim Einreichen und
  per Knopf auf der Seite *System*. Standard: aus.
- Health-Check `fg-gui-health [--url …]` (Exit-Code 0/1; Datenverzeichnis, `/_stcore/health`, Löser) und Abschnitt
  „Betrieb“ auf der Seite *System* (Gesundheit, Speicherbedarf).
- nginx-Vorlage reicht den Benutzer als `X-Remote-User` durch; Anleitung für OIDC (oauth2-proxy).

## [0.7.0] – 2026-11-09

### Hinzugefügt (G6)
- Seite *Optimierung*: Zielfunktion L = Σ w·e aus Ordnungen (Seite, n, m, Gewicht), Maximieren oder Minimieren;
  Parameter als JSON-Pointer (Auswahl aus den Zahlen der Konfiguration oder frei eingegeben) mit Start und Grenzen;
  L-BFGS-B (`scipy`) mit den Gradienten von `Simulation.value_and_grad`.
- Verlauf live (Zielwert und bester Wert je Auswertung, |Gradient|); „Stoppen“ beendet nach der laufenden
  Auswertung und behält das beste Ergebnis; wartende Optimierungen lassen sich abbrechen.
- Ergebnis gespeichert (Art „Optimierung“): Start, Optimum, Verlauf, Eingaben; Optimum per Knopf in den Editor
  übernehmen; Verlauf als CSV.
- Vorlage *Littrow-Gitter* (Konfiguration, Parameter, Grenzen und Ordnung von `optimize_littrow.py`).
- Module `fg_gui.optimize` (ohne FourierGrating testbar) mit Tests; Abnahme: gleiches Optimum wie das Beispielskript
  (1e-9) und nicht schlechter als ein Rasterscan − 1e-3.
- `Job.progress`: Fortschrittsobjekt, das eine Rechnung beschreibt und Seiten lesen. Neue Abhängigkeit: `scipy`.

## [0.6.0] – 2026-11-09

### Hinzugefügt (G5)
- Seite *CAD*: STEP-Datei hochladen (`FG_GUI_DATA_DIR/uploads/<hash>.step`) oder aus dem Beispielverzeichnis wählen,
  Körper der Datei lesen und Materialien zuordnen (Tabelle), Einstellungen der `cad`-Schicht (Einheit, Achsen,
  y-Bereich, Zellursprung, Hintergrund, Überlappung, Slicing, Normalenfeld).
- Prüfung mit `fouriergrating.cad.check` als Hintergrundjob (Art „CAD-Prüfung“, gespeichert): Befunde mit Code,
  Bedeutung und Ort, Bänder mit Flächenanteilen, Schnittvorschau (SVG) je Band und bei frei wählbaren Höhen.
- Dateischutz: CAD-Dateien dürfen nur aus `uploads/` oder dem Beispielverzeichnis kommen (relative Pfade werden
  dort aufgelöst, `..` und Symlinks hinaus werden abgewiesen); gilt für alle Rechnungen (`state.submit_job`).
- Seite *Rechnungen*: „Im CAD öffnen“.
- Module `fg_gui.cad` (ohne Streamlit) mit Tests; Abnahme mit `cad_pillar_array.json` von FourierGrating
  (Prüfung, Rechnung, Neustart).

## [0.5.0] – 2026-11-09

### Hinzugefügt (G4)
- Persistenz: jede Rechnung unter `FG_GUI_DATA_DIR/runs/<id>/` (`meta.json`, `config.json`, Ergebnis als
  `.npz`/`.json`); die Liste auf der Seite *Rechnungen* übersteht Neustarts, Ergebnisse werden erst beim Anzeigen
  geladen. Was beim Beenden wartete oder lief, erscheint als „Fehler: Server wurde neu gestartet“.
- Warteschlange mit Platznummer; wartende Rechnungen lassen sich abbrechen, beendete löschen (samt Dateien).
  Laufende Rechnungen sind nicht abbrechbar (FourierGrating bietet das nicht).
- Seite *Rechnungen*: Auswahl einer Rechnung mit Status, Platz, Laufzeit, Plattenbedarf, Fehler, Konfiguration;
  „Im Editor öffnen“, „Im Scan öffnen“, „Im Nahfeld öffnen“; Einzelrechnungen direkt dargestellt.
- Grobe Abschätzung von Rechnungszahl, Matrixgröße n = 4 n_f und Speicher (Faustwert) im Editor und im Scan,
  mit Warnung ab 70 % des Arbeitsspeichers (`fg_gui.estimate`).
- Tests: Neustart, Unterbrechung, Abbruch, Warteschlange, gleichzeitige Sitzungen, Speicherformat.
- Änderung: Alte Rechnungen werden nicht mehr nach `FG_GUI_JOB_HISTORY` gekürzt, solange der Speicher aktiv ist;
  das Aufräumen folgt in G7.

## [0.4.0] – 2026-11-09

### Hinzugefügt (G3)
- Seite *Nahfeld*: Block `nearfield` der Konfiguration bearbeiten (Schnittlagen, y-Bereich, Punktzahlen, Perioden,
  Größen, Rekonstruktion; Block mit Beispielwerten anlegbar), `fouriergrating.near_field` als Hintergrundrechnung.
- Darstellung: Karte (pcolormesh, Materialgrenzen als Kontur) oder Linie; Größen |E|², |H|², S_y und die Komponenten
  Ex…Hz mit Betrag, Real-/Imaginärteil oder Phase. Felder und Achsen werden unverändert durchgereicht.
- Export: ZIP mit `nearfield_<schnitt>/{*.npy, material.npy, meta.json}` wie `fgsolve` (liest `plot_nearfield.py`),
  Bild als PNG.
- Modul `fg_gui.nearfield` (ohne Streamlit) und `fg_gui.widgets` (Eingabefelder, vom Editor übernommen).
- Neue Abhängigkeit: `matplotlib`.

## [0.3.0] – 2026-11-09

### Hinzugefügt (G2)
- Seite *Scan*: `fouriergrating.solve_scan` für die Konfiguration aus dem Editor (alle Werte von λ, φ, ψ, δ und Sweep)
  als Hintergrundrechnung; mehrere Läufe je Sitzung.
- Kurven über eine wählbare x-Achse (λ, φ, ψ, δ, Sweep-Wert), Mehrfachauswahl von Ordnungen, Größe (gesamt, s, p),
  Summen ΣR/ΣT; übrige veränderliche Achsen werden festgehalten. Nicht propagierende Ordnungen zählen 0.
- Vergleich mehrerer Läufe in einem Diagramm; Tabelle mit den Spalten von `ScanResult.columns`.
- Export `efficiencies.csv` (Sweep-Spalten vorn, Amplituden als Re/Im).
- Modul `fg_gui.scans` (Umformung ohne Streamlit) mit Tests; Abnahmetests mit echtem Löser.

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
