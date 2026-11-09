# Bedienung

Die GUI ist im Browser erreichbar (Adresse und Zugang: Betreiber, siehe `deployment_rtx6000.md`). Links steht die
Navigation, darunter Version und Kern von FourierGrating sowie die Zahl der laufenden Rechnungen.

## Editor

Startseite zum Bearbeiten und Rechnen. **Quelle**: *Neu* (1D-Lamellengitter als Vorlage), *Beispiel* oder
*Datei hochladen*. Reiter:

* **Grundeinstellungen** – Dimension, Löser, Fourier-Ordnungen, Periode, Superstrat und Substrat.
* **Einfall** – λ, φ, ψ, δ als Zahl, Liste (`0.5, 0.6, 0.7`; ein Element als `0.5,`) oder Bereich `von:bis:Schritte`.
* **Materialien** – Art wählen (n, ε, Hauptwerte, Tensor), hinzufügen, entfernen.
* **Schichten** – von unten nach oben; ↑ ↓ ✕ ordnen bzw. löschen. `homogeneous`, `lamellar1d` (Tabelle der Lamellen),
  `profile1d` haben Formulare; andere Typen (2D, CAD) bearbeitest du als JSON der Schicht.
* **Löser** – RK/RCWA-Optionen, Rechenkern, Genauigkeit, Threads.
* **JSON** – ganze Konfiguration; „Übernehmen“ ersetzt die Formularwerte; „Herunterladen“ speichert die Datei.

Das Formular ändert nur, was du änderst; unbekannte Schlüssel bleiben stehen. Schlägt die Rechnung fehl, erscheint die
Meldung von FourierGrating, und der vermutete Reiter (bzw. die Schicht) zeigt sie ebenfalls an.

## Scan

Rechnet die Konfiguration aus dem *Editor* vollständig: alle Werte von λ, φ, ψ, δ (Liste oder Bereich im Reiter
*Einfall*) und den `sweep`-Block (Reiter *JSON*). Mit **Scan rechnen** startet ein Hintergrundjob; jeder Lauf bleibt
in der Sitzung und lässt sich auswählen.

* **x-Achse**: eine Größe, die im Scan mehrere Werte hat. Die übrigen veränderlichen Größen hältst du fest.
* **Ordnungen** `R(n,m)`, `T(n,m)` und **Summen** ΣR, ΣT; **Größe** gesamt, s (TE) oder p (TM). Eine Ordnung, die bei
  einem Wert nicht propagiert, steht als 0.
* **Vergleichen mit**: weitere Läufe derselben Sitzung im selben Diagramm (gleiche x-Achse).
* **efficiencies.csv**: alle Zeilen; bei einem Sweep stehen `sweep_parameter` und `sweep_value` vorn.

## Nahfeld

Feldschnitte für den **ersten Scanpunkt** der Konfiguration aus dem *Editor*.

1. **Nahfeld-Einstellungen**: fehlt der Block `nearfield`, legt ein Knopf ihn mit Beispielwerten an. Danach Lage der
   Schnitte (y₀ für den horizontalen, z₀ für den vertikalen Schnitt), y-Bereich, Punktzahlen, Perioden, Größen und
   Rekonstruktion (`fff` hält E-tangential und D-normal an Materialgrenzen stetig, `direct` zeigt Gibbs-Schwingungen).
2. **Nahfeld rechnen** startet den Job (`enabled` wird für die Rechnung auf `true` gesetzt).
3. **Schnitt**, **Größe** (|E|², |H|², S_y, Ex…Hz) und **Anteil** (Betrag, Re, Im, Phase; nur bei komplexen Größen)
   wählen. Karten zeigen die Materialgrenzen als weiße Linien; 1D-Linienschnitte erscheinen als Kurve.
4. **Alle Schnitte (.zip)** enthält `nearfield_horizontal/` und `nearfield_vertical/` wie `fgsolve`
   (`<Größe>.npy`, `material.npy`, `meta.json`); `scripts/plot_nearfield.py` aus FourierGrating liest sie.

## CAD

Für Schichten vom Typ `cad` (STEP-Körper, FourierGrating `docs/cad.md`); setzt einen FourierGrating-Build mit CAD-Slicer
voraus (Seite *System*: „CAD-Slicer“). Die Seite arbeitet an der Konfiguration aus dem *Editor*.

1. **CAD-Schicht**: fehlt sie, legt ein Knopf eine an.
2. **STEP-Datei**: hochladen (.step/.stp) oder ein Beispiel aus `FG_GUI_EXAMPLES_DIR` verwenden. Hochgeladene Dateien
   liegen unter `FG_GUI_DATA_DIR/uploads/`. Aus anderen Verzeichnissen liest die GUI nicht.
3. **Körper → Material**: die Namen der Körper werden aus der Datei gelesen; jedem ein Material zuordnen (ein
   benannter Körper je Material). Weitere Einstellungen: Einheit, Achsen (CAD-Achse für y = Stapelrichtung und x),
   y-Bereich, Zellursprung, Hintergrundmaterial, Überlappung, Zerlegung in Bänder, Normalenfeld.
4. **Prüfen** startet `fouriergrating.cad.check` als Job und zeigt Befunde (Code, Meldung, Ort in µm), die Bänder
   (von unten nach oben, mit Flächenanteilen) und die **Schnittvorschau** je Band (Bandmitte) oder bei einer
   eigenen Höhe.

Danach rechnet *Einzelrechnung*, *Scan* oder *Nahfeld* die Konfiguration wie jede andere.

## Optimierung

Maximiert oder minimiert L = Σ wᵢ·eᵢ über die Effizienzen von Beugungsordnungen, indem Zahlen der Konfiguration
verändert werden. Gradienten: `Simulation.value_and_grad` (diskrete Adjungierte, Aufwand ≈ 1,3–2,5 Vorwärtsrechnungen
unabhängig von der Parameterzahl); Verfahren: L-BFGS-B mit Grenzen. Gerechnet wird am **ersten Scanpunkt**.

1. **Zielfunktion**: Tabelle aus Seite (R/T), Ordnung n, m und Gewicht; mehrere Zeilen sind erlaubt
   (z. B. R(−1,0) mit +1 und T(0,0) mit −0,5). **Ziel**: Maximieren oder Minimieren.
2. **Parameter**: Zahlen der Konfiguration als JSON-Pointer wählen (`/layers/0/thickness_um`,
   `/layers/0/breakpoints_um/1`, `/materials/al/n/1`, `/incidence/lambda_um` …; was FourierGrating ableitet, steht in
   dessen `docs/python.md`, Abschnitt „Gradienten“). Je Parameter **Start**, **Untergrenze** und **Obergrenze**; die
   Vorgabe ±50 % des Werts ist nur ein Platzhalter. Der Start muss innerhalb der Grenzen liegen.
3. **Optimieren** startet den Job. Der Verlauf erscheint live; **Stoppen** beendet nach der laufenden Auswertung und behält
   das beste Ergebnis.
4. **Ergebnis**: Zielwert am Start und am Optimum, Parameter (Start → Optimum), Verlauf (auch als CSV);
   **Optimum in den Editor übernehmen** schreibt die Werte in die Konfiguration.

Die **Vorlage** „Littrow-Gitter“ lädt das Beispiel `optimize_littrow.py` von FourierGrating (Aluminium, Periode 0,5 µm,
TM): Tiefe und Stegbreite für die −1. reflektierte Ordnung.

## Einzelrechnung

1. **Quelle** wählen: *Beispiel* (Konfigurationen aus `FG_GUI_EXAMPLES_DIR`, z. B. die Referenzfälle von
   FourierGrating) oder *Datei hochladen* (`.json` im Format von FourierGrating, `docs/config_format.md` dort).
2. Die Kurzübersicht zeigt Dimension, Löser, Schichten und Materialien; unter *JSON* steht die ganze Konfiguration.
3. **Rechnen** startet die Rechnung im Hintergrund. Gerechnet wird der **erste Scanpunkt** (wie `fg.solve`);
   Listen/Bereiche im Einfall und Sweeps werden erst mit G2 ausgewertet.
4. Ergebnis: ΣR, ΣT, Absorption und Energiebilanz, Tabelle aller propagierenden Ordnungen (Seite R/T, n, m,
   Effizienz, s-/p-Anteil), Balkendiagramm, Warnungen und Diagnose (Laufzeiten, Genauigkeit, Konditionszahlen).
   *Tabelle als CSV* lädt die Tabelle herunter.

Fehler in der Konfiguration meldet FourierGrating beim Rechnen; der Text erscheint rot, *Details* zeigt den
Traceback.

## Rechnungen

Alle Rechnungen (Einzelrechnung, Scan, Nahfeld) werden gespeichert (`FG_GUI_DATA_DIR/runs/<id>/`) und bleiben nach
einem Neustart des Servers in der Liste. Die Tabelle zeigt Art, Status, **Platz** in der Warteschlange und Laufzeit;
„Nur meine Rechnungen“ blendet die anderer Nutzer aus (mit Anmeldung am Proxy gilt das über Sitzungen und Geräte
hinweg, sonst nur für diese Browsersitzung). Der Betreiber kann alte Rechnungen automatisch löschen lassen. Unter *Einzelne Rechnung*:

* **Abbrechen** – nur für wartende Rechnungen (eine laufende lässt sich nicht unterbrechen).
* **Löschen** – entfernt eine beendete Rechnung samt Dateien.
* **Rechnung herunterladen (.zip)** – Konfiguration, Ergebnistabellen (CSV/JSON, beim Nahfeld `.npy`) und die
  gespeicherten Rohdateien; **Modell herunterladen (.json)** – nur die Konfiguration.
* **Im Editor öffnen** übernimmt die gespeicherte Konfiguration; **Im Scan / Nahfeld öffnen** zeigt das Ergebnis dort.
* Was beim Neustart noch wartete oder lief, steht als Fehler „Server wurde neu gestartet“ da; bitte neu einreichen.

Vor dem Rechnen zeigen Editor und Scan eine **Abschätzung** (Zahl der Rechnungen, Matrixgröße n = 4 n_f, Speicher).
Der Speicher ist ein Faustwert (12 komplexe n×n-Matrizen je gleichzeitigem Scanpunkt) und warnt ab 70 % des
Arbeitsspeichers; er kann bei RK-Löser, vielen Scheiben oder GPU weit danebenliegen.

## Sitzung und Adresse

Die Adresszeile enthält deine Sitzungskennung (`?s=…`). **Adresse als Lesezeichen merken:** Mit ihr kommst du – auch
von einem anderen Rechner oder nach einem Neustart des Servers – zu deinen Rechnungen und zur zuletzt bearbeiteten
Konfiguration im Editor zurück. Wer die Adresse kennt, sieht deine Rechnungen; gib sie nur weiter, wenn das gewollt ist.
Ohne Kennung in der Adresse beginnt eine neue Sitzung. Unter *Rechnungen → Meine Sitzung löschen* entfernst du
alle deine Rechnungen und den gemerkten Entwurf und beginnst neu (nach Bestätigung, nicht rückgängig zu machen).

## System

Version und Kern von FourierGrating (`cpu` oder `cuda12`), ob CUDA nutzbar und der CAD-Slicer eingebaut ist,
Backend-Voreinstellung, GPU-Zustand (Speicher, Auslastung, Temperatur) und die Einstellungen der GUI.
*Neu prüfen* liest die Angaben zum Löser erneut. Der Abschnitt „Betrieb“ zeigt die Gesundheitsprüfung, den
Speicherbedarf der gespeicherten Rechnungen und den Knopf *Jetzt aufräumen* (nur wenn der Betreiber eine Aufbewahrung
eingestellt hat).
