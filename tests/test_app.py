"""Rauchtests der Seiten mit streamlit.testing (ohne Browser)."""

import json
from pathlib import Path

import pytest
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


EXAMPLES = Path(__file__).resolve().parents[2] / "FourierGrating" / "examples"


def _editor(monkeypatch, directory: Path, name: str) -> AppTest:
    monkeypatch.setenv("FG_GUI_EXAMPLES_DIR", str(directory))
    at = _run("editor.py")
    at.radio[0].set_value("Beispiel").run()
    at.selectbox(key="fg_editor_example").select(
        [p for p in sorted(directory.glob("*.json")) if p.name == name][0]
    ).run()
    assert not at.exception, at.exception
    return at


def test_editor_new_config_unchanged(fake_fg):
    from fg_gui import config_form

    at = _run("editor.py")
    assert at.session_state["fg_cfg"] == config_form.default_config()
    assert not at.error


def test_editor_roundtrip_example(fake_fg, tmp_path, monkeypatch):
    (tmp_path / "v3.json").write_text(json.dumps(EXAMPLE))
    at = _editor(monkeypatch, tmp_path, "v3.json")
    assert at.session_state["fg_cfg"] == EXAMPLE


def test_editor_edit_wavelength(fake_fg, tmp_path, monkeypatch):
    (tmp_path / "v3.json").write_text(json.dumps(EXAMPLE))
    at = _editor(monkeypatch, tmp_path, "v3.json")
    gen = at.session_state["fg_gen"]
    at.text_input(key=f"fg{gen}_inc_lambda_um").set_value("0.5, 0.6").run()
    assert at.session_state["fg_cfg"]["incidence"]["lambda_um"] == [0.5, 0.6]
    at.text_input(key=f"fg{gen}_inc_lambda_um").set_value("abc").run()
    assert any("keine Zahl" in e.value for e in at.error)


@pytest.mark.skipif(not EXAMPLES.is_dir(), reason="FourierGrating-Beispiele nicht vorhanden")
@pytest.mark.parametrize("name", sorted(p.name for p in EXAMPLES.glob("*.json")))
def test_editor_roundtrip_all_fourier_grating_examples(fake_fg, monkeypatch, name):
    expected = json.loads((EXAMPLES / name).read_text(encoding="utf-8-sig"))
    at = _editor(monkeypatch, EXAMPLES, name)
    assert at.session_state["fg_cfg"] == expected
