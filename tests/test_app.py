"""Rauchtests der Seiten mit streamlit.testing (ohne Browser)."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from conftest import EXAMPLE

APP = str(Path(__file__).resolve().parents[1] / "src" / "fg_gui" / "app.py")


def _run(page: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    if page:
        at.switch_page(str(Path(APP).parent / "pages" / page))
        at.run()
    assert not at.exception, at.exception
    return at


def test_pages_without_solver(no_fg):
    _run()
    at = _run("system.py")
    assert any("nicht importierbar" in e.value for e in at.error)
    _run("jobs.py")


def test_single_with_example(fake_fg, tmp_path, monkeypatch):
    (tmp_path / "v3.json").write_text(json.dumps(EXAMPLE))
    monkeypatch.setenv("FG_GUI_EXAMPLES_DIR", str(tmp_path))
    at = _run("single.py")
    assert at.selectbox[0].value.name == "v3.json"
    at.button[0].click().run()
    for _ in range(20):  # Job läuft im Hintergrund; Seite neu ausführen, bis das Ergebnis da ist
        if at.success:
            break
        at.run()
    assert not at.exception, at.exception
    assert at.success and "fertig" in at.success[0].value
    assert at.dataframe
