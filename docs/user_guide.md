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

Alle Rechnungen dieses Serverprozesses mit Status (*wartend*, *läuft*, *fertig*, *Fehler*), Laufzeit und
Fehlermeldung; standardmäßig nur die eigene Sitzung. Es rechnet immer nur eine bestimmte Zahl gleichzeitig
(`FG_GUI_WORKERS`, Standard 1); weitere warten. Nach einem Neustart des Dienstes ist die Liste leer.

## System

Version und Kern von FourierGrating (`cpu` oder `cuda12`), ob CUDA nutzbar und der CAD-Slicer eingebaut ist,
Backend-Voreinstellung, GPU-Zustand (Speicher, Auslastung, Temperatur) und die Einstellungen der GUI.
*Neu prüfen* liest die Angaben zum Löser erneut.
