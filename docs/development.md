# Entwicklung

## Umgebung

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install fouriergrating          # optional (CPU-Wheel), oder: pip install ../FourierGrating
./scripts/run_dev.sh                # lädt bei Dateiänderungen neu
```

`FG_GUI_EXAMPLES_DIR=../FourierGrating/examples` macht die Beispiele von FourierGrating auf der Seite
*Einzelrechnung* auswählbar.

## Tests

```bash
pytest                  # ohne Löser: Ersatzmodul aus tests/conftest.py
pytest -m solver        # nur mit installiertem fouriergrating (Server-Abnahme)
ruff check src tests && ruff format --check src tests
```

* `fake_fg`: ersetzt `fouriergrating` durch ein Modul mit festen Ergebnissen; `no_fg`: simuliert ein fehlendes Paket.
* Seiten testet `streamlit.testing.v1.AppTest` (`tests/test_app.py`); Hintergrundjobs werden durch wiederholtes
  `at.run()` abgewartet.
* Die Streamlit-Caches (`st.cache_resource`, `st.cache_data`) werden vor jedem Test geleert.

## Neue Seite

1. Datei `src/fg_gui/pages/<name>.py` (Skript, keine Funktion nötig).
2. In `app.py` in `st.navigation` eintragen.
3. Logik in ein Modul ohne Streamlit auslagern, dort Unit-Tests.
4. Rauchtest in `tests/test_app.py`.
5. Bedienung in `docs/user_guide.md`, Status in `docs/roadmap.md`.

## Stil

Python ≥ 3.10, `ruff` (Zeilenlänge 120), Typannotationen, `from __future__ import annotations` in Modulen.
Oberfläche und Doku Deutsch, Code-Bezeichner Englisch. Regeln: [`AGENTS.md`](../AGENTS.md).
