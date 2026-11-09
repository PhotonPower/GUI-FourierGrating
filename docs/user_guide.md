# Bedienung

Die GUI ist im Browser erreichbar (Adresse und Zugang: Betreiber, siehe `deployment_rtx6000.md`). Links steht die
Navigation, darunter Version und Kern von FourierGrating sowie die Zahl der laufenden Rechnungen.

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
