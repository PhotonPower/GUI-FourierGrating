# Architektur

## Überblick

```text
Browser ──HTTPS──> nginx (TLS, Anmeldung) ──WebSocket──> Streamlit (herkules3.ito.uni-stuttgart.de:8505)
                                                           │
                         app.py ── st.navigation ── pages/*.py   (je Interaktion neu ausgeführt)
                                                           │
             state.py: settings(), job_manager(), solver_info()  (st.cache_resource / cache_data, prozessweit)
                                                           │
     config_io ── results ── system            jobs.JobManager (ThreadPoolExecutor, FG_GUI_WORKERS)
                                                           │
                                     solver.py ── import fouriergrating ── C++-Kern (CPU | CUDA, RTX 6000 Ada)
```

## Module

| Modul | Aufgabe | Streamlit? |
|---|---|---|
| `app.py` | Seitenkonfiguration, Navigation, Seitenleiste | ja |
| `pages/single.py` | Einzelrechnung: Konfiguration wählen, Job starten, Ergebnis anzeigen | ja |
| `pages/jobs.py` | Liste der Rechnungen (Sitzung oder alle) | ja |
| `pages/system.py` | Kern, CUDA, CAD-Slicer, GPU, Einstellungen | ja |
| `state.py` | prozessweite Ressourcen, Sitzungskennung | ja |
| `solver.py` | **einzige** Stelle mit `import fouriergrating`; Versionsprüfung, Weiterreichen | nein |
| `jobs.py` | Hintergrundrechnungen, Status, Fehler mit Traceback | nein |
| `config_io.py` | JSON lesen/schreiben, Beispiele auflisten, Kurzübersicht | nein |
| `results.py` | `fg.Result` → `pandas.DataFrame`, Summen | nein |
| `config_form.py`, `widgets.py` | Editor: Eingaben ↔ Konfiguration (nur Geändertes wird geschrieben), Felder | nein |
| `scans.py`, `nearfield.py`, `estimate.py` | Scan-/Nahfeld-Tabellen und -Bilder, Abschätzung von Aufwand und Speicher | nein |
| `cad.py`, `optimize.py` | CAD-Dateien (Dateiwächter), Zielfunktion/Parameter/Verlauf der Optimierung | nein |
| `store.py`, `export.py` | Rechnungen auf der Festplatte (`FG_GUI_DATA_DIR/runs`), ZIP-Download | nein |
| `users.py`, `logs.py`, `housekeeping.py`, `health.py` | Proxy-Benutzer, Logging, Aufräumen, Health-Check (`fg-gui-health`) | nein |
| `system.py` | `nvidia-smi` abfragen | nein |
| `settings.py` | `FG_GUI_*`-Variablen | nein |
| `cli.py` | Startbefehl `fg-gui` | – |

Module ohne Streamlit sind direkt mit pytest testbar; die Seiten werden mit `streamlit.testing.v1.AppTest`
geprüft.

## Datenfluss einer Rechnung

1. Die Seite erzeugt ein Konfigurations-`dict` (Datei, Beispiel, später Formular – G1).
2. `job_manager().submit(label, solver.solve, cfg, owner=session_id())` gibt sofort einen `Job` zurück; die Seite
   merkt sich `job.id` in `st.session_state`.
3. Der Job läuft in einem Pool-Thread. FourierGrating gibt während der Rechnung den GIL frei; die Oberfläche bleibt
   bedienbar.
4. Ein `st.fragment(run_every=1s)` fragt den Status ab und baut nach dem Ende die Seite neu auf.
5. `results` wandelt das Ergebnis in Tabellen; die Darstellung macht die Seite.

Jobs leben im Speicher des Serverprozesses (gehen bei Neustart verloren) und sind allen Sitzungen sichtbar
(Seite *Rechnungen*, Schalter „Nur diese Sitzung“). Persistenz und Abbruch folgen in G4.

## Schnittstelle zu FourierGrating

Genutzt (v0.18): `__version__`, `core_variant()`, `cuda_available()`, `get_backend()`, `cad.available()`,
`solve(cfg)`. Geplant: `solve_scan`, `near_field`, `Simulation` (`set_parameter`, `value_and_grad`), `cad.check`,
`load_config` (relative Pfade). Konfigurationen sind reine `dict`s im JSON-Schema von FourierGrating – die GUI
erzeugt nie eigene Formate, sodass jede Konfiguration auch mit `fgsolve` rechenbar ist.

Umgebungsvariablen von FourierGrating (`FG_NUM_THREADS`, `FG_CORE`, `FG_PRECISION`, `FG_GPU_STREAMS`) werden über
die Dienstumgebung gesetzt (`deploy/fg-gui.env.example`), nicht in der GUI.

## Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Threads statt Prozesse für Jobs | GIL frei während der Rechnung; Ergebnisse ohne Serialisierung; ein CUDA-Kontext |
| Standard 1 Worker | eine GPU; jede Rechnung nutzt bereits alle Kerne (OpenMP) bzw. die GPU |
| `fouriergrating` keine harte Abhängigkeit | Server baut es mit CUDA aus den Quellen; pip soll kein CPU-Wheel darüberlegen |
| Lauschen auf herkules3, Port 8505 | Streamlit hat keine Anmeldung; Schutz durch die Firewall des Instituts, nicht öffentlich erreichbar |
