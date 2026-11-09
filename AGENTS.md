# Arbeitsregeln für KI-Agenten (und Menschen)

Diese Datei gilt für jeden, der an GUI-FourierGrating arbeitet. Lies sie vollständig, bevor du Code änderst.

## 1. Quelle der Wahrheit

1. **FourierGrating** (`PhotonPower/FourierGrating`) definiert Konfigurationsformat, Semantik und API:
   `docs/config_format.md`, `docs/python.md`, `docs/user_guide.md` dort. Die GUI folgt diesen Dokumenten; bei
   Widerspruch gilt FourierGrating.
2. **`docs/roadmap.md`** legt fest, was als Nächstes gebaut wird; `docs/architecture.md` beschreibt, wie.
3. Die Schwesterprojekte **FourierGrating** und **Nurbforge** werden aus diesem Repository heraus **nur gelesen**.
   Fehlt dort etwas (API, Felder, Fehlermeldungen), wird es im jeweiligen Projekt nach dessen Regeln ergänzt –
   nicht in der GUI nachgebaut. Den Bedarf in `docs/roadmap.md` unter „Anforderungen an FourierGrating“ notieren.

## 2. Keine Physik in der GUI

* Die GUI baut Konfigurations-`dict`s, ruft `fouriergrating` auf und stellt Ergebnisse dar. Sie berechnet keine
  Effizienzen, Felder, Brechzahlen oder Geometrien selbst und prüft das Schema nicht nach – Fehlermeldungen von
  FourierGrating (`FourierGratingError`) werden angezeigt.
* Nur `src/fg_gui/solver.py` importiert `fouriergrating` (später auch `fouriergrating.cad`, `.torch`). Seiten rufen
  `solver`-Funktionen auf. So bleibt die GUI ohne installierten Löser testbar.
* Einheiten wie im JSON-Format: µm und Grad. Keine Umrechnung in der GUI.
* Mindestversion von FourierGrating: `solver.MIN_VERSION`; bei Nutzung neuer API anheben und im CHANGELOG nennen.

## 3. Rechnungen

* Eine Rechnung läuft **nie** im Seitenskript selbst, sondern über `state.job_manager().submit(...)`.
  Streamlit führt das Skript bei jeder Interaktion neu aus; eine blockierende Rechnung legt die Sitzung lahm.
* Standard ist eine Rechnung gleichzeitig (`FG_GUI_WORKERS=1`): eine GPU, und FourierGrating nutzt pro Rechnung
  alle Kerne (OpenMP). Mehr Parallelität nur mit Messung (`fgbench`, `docs/benchmarks.md` in FourierGrating).
* Ein `fg.Simulation`-Objekt ist nicht threadsicher: höchstens ein Job je Objekt.
* Statusabfragen mit `st.fragment(run_every=...)`, nur solange der Job läuft.

## 4. Streamlit-Konventionen

* Mehrseitig über `st.navigation`/`st.Page` in `app.py`; je Seite eine Datei in `src/fg_gui/pages/`.
* Prozessweite Objekte über `st.cache_resource` in `state.py`; Schlüssel in `st.session_state` beginnen mit `fg_`.
* Logik, die sich ohne Streamlit testen lässt (Umwandlung, Tabellen, Dateien), gehört in Module außerhalb von
  `pages/`.
* Oberfläche und Doku auf Deutsch, Bezeichner im Code auf Englisch.

## 5. Tests

* `pytest` muss vor jedem Commit grün sein, **ohne** installiertes `fouriergrating` (Ersatzmodul in
  `tests/conftest.py`). Jede Seite hat mindestens einen Rauchtest mit `streamlit.testing.v1.AppTest`.
* Neue Umwandlungen (Ergebnis → Tabelle/Plot-Daten, Formular → Konfiguration) bekommen Unit-Tests; Formular →
  Konfiguration zusätzlich einen Roundtrip-Test (Konfiguration → Formular → gleiche Konfiguration).
* Tests mit echtem Löser markieren: `@pytest.mark.solver` (werden übersprungen, wenn das Paket fehlt).
* `ruff check` und `ruff format --check` grün.

## 6. Git

* Kleine, thematisch abgeschlossene Commits; Präfix mit Meilenstein, z. B. `G1: Materialtabelle`.
* **Niemals Zugangsdaten (Tokens, Passwörter, htpasswd-Dateien, Zertifikatsschlüssel) ins Repository schreiben**,
  auch nicht in Remote-URLs in Skripten. Server-Umgebung nur als `*.env.example`.
* Laufzeitdaten (`data/`, Ergebnisse) gehören nicht ins Repo.
* Nach jedem Meilenstein: Status in `docs/roadmap.md`, Eintrag in `CHANGELOG.md`, Version in `pyproject.toml` und
  `src/fg_gui/__init__.py`.

## 7. Zielsystem

Server AlmaLinux 10 (x86_64, Python 3.12), NVIDIA RTX 6000 Ada (sm_89, 48 GB), FourierGrating aus den Quellen mit
CUDA. Die GUI lauscht nur auf `127.0.0.1`; Zugriff über nginx (TLS, Anmeldung) oder SSH-Tunnel. Streamlit hat keine
eigene Benutzerverwaltung – keine Funktionen bauen, die ohne Anmeldung Dateien außerhalb von `FG_GUI_DATA_DIR`
lesen oder schreiben.
