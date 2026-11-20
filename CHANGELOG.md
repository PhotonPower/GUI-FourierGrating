# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach SemVer.

## [0.15.0] – 2026-11-20

### Hinzugefügt
- **NURBS-Linie in 1D (G12, FourierGrating M24):** Schichttyp `profile1d` mit `shape: nurbs` im Editor, ohne STEP:
  Material unten/oben, Kontrollpunkte als Tabelle (x, y, Gewicht), Grad, Knotenvektor (Knopf „Knoten neu erzeugen“:
  gleichmäßig, geklemmt), optionale Tiefe (0 = Maximum der Kurve), Scheiben, Tschebyschow-Knoten, Faktorisierung.
  Neue Schichten starten mit einer flachen Linie mit einer Beule. Hinweis bei falscher Knotenzahl. Das Schnittbild
  zeichnet die Linie (auch mit Überhängen) und nimmt die Höhe aus der Kurve, wenn `depth_um` fehlt.
- Der STEP-Import der einfachen Linie (0.14.0) bleibt als Alternative erhalten.
- Tests: Hilfsfunktionen, Zeichnen, Editor (AppTest) und der echte Löser (Energiebilanz mit Beispiel und Startwert).

### Hinweis
- Das Feature steckt in FourierGrating `main` (PR #32), noch ohne neues Versions-Tag (weiter 0.20.0); die GUI braucht
  einen Stand mit M24 (`pip install` aus `main`). Ältere Kerne melden die Form `nurbs` als Fehler.

## [0.14.0] – 2026-11-19

### Hinzugefügt
- **Einfache Linie aus STEP im Editor (G11, 1D):** Reiter *Schichten* → Menü „Neue Schicht“ → „cad: Linie aus STEP-Datei“ (nur 1D). Die Datei
  enthält genau einen Körper mit den richtigen Proportionen (Fläche unter der Linie über die ganze Periode, entlang z
  extrudiert). Die GUI skaliert die STEP-Koordinaten (Punkte, Radien) so, dass die Breite (CAD x) der Periode Λ
  entspricht; die Höhe folgt aus den Proportionen und wird vorab angezeigt. Material unterhalb = Körper, Material
  oberhalb = `background`; die Schicht (`unit: um`) wird mit der skalierten Datei in `uploads/` angelegt. Die
  komplizierte Variante (mehrere Körper, Einstellungen) bleibt auf der Seite *CAD*.
- `cad.step_extent`, `cad.scale_step`, `cad.line_info`, `cad.line_layer`; Tests (Einheit, AppTest, echter Löser).

## [0.13.0] – 2026-11-19

### Hinzugefügt
- **CAD in 1D-Gittern (G10, FourierGrating M23):** Seite *CAD* für `dimension: 1D` – Hinweis auf z-invariante Körper,
  Zellursprung nur x₀, Schnittebene `z_cut_um` (optional), kein sigma beim Normalenfeld, keine Schnitthöhen. *Prüfen*
  zeigt Bänder (`homogeneous`/`lamellar1d`/`sectioned1d`) mit Längenanteilen und das Profil in (x, y) als einzige
  Vorschau (`solver.cad_check`: `y_um` ist dort `None`); Befundcode `NOT_Z_INVARIANT` erklärt. Warnung bei `z_cut_um`
  in 2D. Reiter *Struktur* des Editors nutzt Bänder und Profil in 1D wie in 2D.
- Tests mit dem echten Löser (`-m solver`): Prüfbericht, Energiebilanz, `z_cut_um`, `NOT_Z_INVARIANT` (Säulen als 1D);
  Kopie von `cad_line_grating_1d.json` und `line_grating.step` in `tests/data/`.

### Geändert
- Mindestversion FourierGrating 0.20.0 (`solver.MIN_VERSION`, Extra `solver`): CAD-Schichten in 1D-Gittern (M23).
  Roadmap korrigiert: 1D-CAD ist in FourierGrating vorhanden (z-invariante Körper; nicht z-invariante melden
  `NOT_Z_INVARIANT`), offen ist die Freigabe in der GUI.

## [0.12.2] – 2026-11-19

### Hinzugefügt
- Nahfeld (2D): Rechenart **Nur eine Linie entlang x** – eingereicht wird `ny = 1`, `y_range_um = [y, y]`, `nz = 1`;
  FourierGrating rechnet genau eine Linie an der exakten Position (Test mit dem echten Löser: gleich der Karten-Zeile).
  Anzeige als Kurve, Rohdaten beider Schnitte im Export.

## [0.12.1] – 2026-11-19

### Hinzugefügt
- Reiter *Struktur*: CAD-Schichten erscheinen mit Höhe und Bändern aus dem Prüfbericht der Seite *CAD* (wahre Höhen,
  Flächenanteile der Materialien je Band, Draufsicht der Bänder, Bänder als Tabellenzeilen). Ohne Prüfung bleibt die
  Höhe angenommen und gekennzeichnet; geänderte Schichten seit der Prüfung werden vermerkt.

## [0.12.0] – 2026-11-19

### Hinzugefügt (Rückmeldung der Nutzer)
- **HDF5-Download** einer fertigen Rechnung (*Rechnungen*, *Scan*, *Nahfeld*): Konfiguration, Metadaten, Ergebnis
  (Ordnungen, Scan-Spalten, Nahfeldfelder und Achsen, Optimierungsverlauf), Diagnose und dispersive Materialien.
  Neue Abhängigkeit `h5py`; Aufbau in `docs/user_guide.md` („HDF5-Export“).
- **Nahfeld, 1D-Schnitte:** Linien aus den Karten (entlang x bei festem y bzw. y bei festem x; bei 2D-Strukturen
  innerhalb des z-Schnitts) am nächsten Gitterpunkt, ohne Interpolation und ohne neue Rechnung; Kurve und CSV.
- **Editor, Reiter *Struktur*:** Schnittbild x–y mit Maßen (Perioden, Dicken, Lamellenbreiten, Profiltiefen, Schnitt
  bei z für 2D-Schichten) und Draufsicht x–z auf `polygon2d`/`contour2d` mit Formmaßen, aus der Konfiguration
  gezeichnet; PNG-Download. Neues Modul `structure.py` (nur Darstellung).

## [0.11.1] – 2026-11-17

### Geändert
- Die Abfrage `solver.info().dispersion_available` entfällt; die dispersiven Materialarten sind immer verfügbar.
- `solver.MIN_VERSION` ist jetzt **0.19.0** (FourierGrating v0.19.0 enthält M22, dispersive Materialien); `pyproject.toml`:
  `fouriergrating>=0.19`. Ältere Kerne meldet die Seite *System* als zu alt.

## [0.11.0] – 2026-11-16

### Hinzugefügt (G8, setzt FourierGrating M22 voraus)
- Editor, Reiter *Materialien*: neue Arten **Tabelle (n, k)**, **Tabelle (ε)**, **Sellmeier**, **Cauchy** und
  **Drude–Lorentz** neben n, ε, Hauptwerten und Tensor. Tabellen als Zeilen mit Einheit (µm, nm, eV), Interpolation
  (`linear`/`cubic`) und Verhalten außerhalb (`error`/`constant`); CSV einfügen oder hochladen. Hauptwerte mit Modellen
  je Komponente als JSON. Unveränderte Werte bleiben im Roundtrip bitgleich.
- Tabellen werden immer inline (`data`) gespeichert: Konfigurationen mit `file` werden beim Laden (Beispiel, Upload) und
  beim Rechnen in `data` umgewandelt; Dateien nur aus Uploads, der Materialbibliothek und dem Beispielverzeichnis
  (Wächter wie bei CAD). Rechnungen bleiben dadurch reproduzierbar und als JSON vollständig herunterladbar.
- Import: **Materialbibliothek** `FG_GUI_DATA_DIR/materials/` (CSV/YAML, vom Betrieb gepflegt, für Nutzer nur lesbar;
  die Auswahl kopiert das Material in die Konfiguration), CSV und **refractiveindex.info-YAML**
  (`fouriergrating.materials.from_refractiveindex`, neue Abhängigkeit `pyyaml`).
- Vorschau ε′(λ), ε″(λ) je dispersivem Material (Werte von `fg.material_eps`, Bereich aus dem Einfall); Fehler des Kerns
  (Bereich, Pol) erscheinen mit JSON-Pointer am Material (`config_form.error_material`).
- Seite *Einzelrechnung*: n und ε der dispersiven Materialien am Rechenpunkt (Diagnose `materials`); Seite *Scan*:
  ε über den Wellenlängen des Scans mit `materials.csv`; ZIP-Download enthält `materials.csv`.
- Seite *Optimierung*: Modellwerte (`/materials/<name>/n/sellmeier/B/0` …) sind Parameter; die Wellenlängenspalte
  einer Tabelle nicht.
- Die neuen Materialarten erscheinen, sobald FourierGrating M22 enthält (ab v0.19.0, siehe 0.11.1).
 – 2026-11-09

### Hinzugefügt
- systemd-Benutzerdienst für herkules3: `deploy/fg-gui.user.service`, `deploy/fg-gui.user.env.example` und
  `scripts/install_user_service.sh` (`systemctl --user … fg-gui`, Neustart bei Absturz, CUDA-Laufzeit gesetzt).
  Der Entwicklungsstart `scripts/run_dev.sh` bleibt für lokale Arbeit.

## [0.10.0] – 2026-11-09

### Hinzugefügt
- Seite *Rechnungen*, Abschnitt „Meine Sitzung löschen“ (mit Bestätigung): entfernt alle eigenen Rechnungen samt
  Dateien und den gemerkten Editor-Entwurf und beginnt eine neue Sitzung mit neuer Kennung. Wartende Rechnungen werden
  abgebrochen; eine laufende bleibt bis zum Ende bestehen. Hochgeladene STEP-Dateien bleiben (Aufräumen: Betreiber).

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
