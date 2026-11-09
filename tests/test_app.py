"""Rauchtests der Seiten mit streamlit.testing (ohne Browser)."""

import json
import time
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


def _wait(at: AppTest, cond) -> None:
    for _ in range(40):
        if cond():
            return
        time.sleep(0.1)  # Jobs laufen in einem Thread (z. B. scipy-Import beim ersten Mal)
        at.run()


def test_scan_page_without_config(fake_fg):
    at = AppTest.from_file(str(Path(APP).parent / "pages" / "scan.py"), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("Editor" in i.value for i in at.info)


def test_scan_compare_runs(fake_fg):
    from fg_gui import config_form

    at = _run("editor.py")  # legt die Vorlage an
    at.switch_page(str(Path(APP).parent / "pages" / "scan.py"))
    at.run()
    at.button[0].click().run()
    _wait(at, lambda: at.success)
    assert at.success and "fertig" in at.success[0].value
    assert at.session_state["fg_cfg"] == config_form.default_config()
    # x-Achse und Kurve vorhanden; zweiter Lauf → Vergleich möglich
    at.button[0].click().run()
    _wait(at, lambda: len(at.session_state["fg_scan_runs"]) == 2 and not at.info)
    _wait(at, lambda: any(m.label == "Vergleichen mit" for m in at.multiselect))
    cmp_ = next(m for m in at.multiselect if m.label == "Vergleichen mit")
    cmp_.select(cmp_.options[0]).run()
    assert not at.exception, at.exception


def test_nearfield_page(fake_fg):
    at = _run("editor.py")
    at.switch_page(str(Path(APP).parent / "pages" / "nearfield.py"))
    at.run()
    assert not at.exception, at.exception
    at.button[0].click().run()  # Block mit Beispielwerten anlegen
    assert "nearfield" in at.session_state["fg_cfg"]
    at.button[0].click().run()  # Nahfeld rechnen
    _wait(at, lambda: at.success)
    assert not at.exception, at.exception
    assert at.success and "fertig" in at.success[0].value
    assert at.session_state["fg_cfg"]["nearfield"]["enabled"] is True
    assert {s.label for s in at.selectbox} >= {"Schnitt", "Größe", "Anteil"}
    # Linienschnitt (horizontal, 1D) wählen
    next(s for s in at.selectbox if s.label == "Schnitt").select("horizontal").run()
    assert not at.exception, at.exception


def test_nearfield_page_without_config(fake_fg):
    at = AppTest.from_file(str(Path(APP).parent / "pages" / "nearfield.py"), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("Editor" in i.value for i in at.info)


def _run_editor_job(fake_fg) -> tuple[AppTest, str]:
    at = _run("editor.py")
    next(b for b in at.button if b.label == "Rechnen").click().run()
    _wait(at, lambda: at.success)
    assert at.success
    return at, at.session_state["fg_editor_job"]


def test_jobs_page_lists_persisted_run_and_deletes(fake_fg):
    at, _ = _run_editor_job(fake_fg)
    at.switch_page(str(Path(APP).parent / "pages" / "jobs.py"))
    at.run()
    assert not at.exception, at.exception
    assert at.dataframe and at.selectbox
    next(b for b in at.button if b.label == "Löschen").click().run()
    assert not at.exception, at.exception
    assert any("Keine Rechnungen" in i.value for i in at.info)


def test_jobs_page_survives_restart_and_other_session(fake_fg):
    import streamlit as st

    _, job_id = _run_editor_job(fake_fg)
    st.cache_resource.clear()  # „Neustart“: die Jobverwaltung wird neu aufgebaut und liest die Festplatte
    other = AppTest.from_file(str(Path(APP).parent / "pages" / "jobs.py"), default_timeout=30).run()
    assert not other.exception, other.exception
    assert any("Keine Rechnungen" in i.value for i in other.info)  # eine andere Sitzung sieht nur ihre eigenen
    other.toggle[0].set_value(False).run()  # „Nur diese Sitzung“ aus
    assert not other.exception, other.exception
    assert any(o.startswith(job_id) and "fertig" in o for o in other.selectbox[0].options)


# ---------------------------------------------------------------- G5: CAD
def _cad_cfg(file: str, bodies=None) -> dict:
    cfg = json.loads(json.dumps(EXAMPLE))
    cfg["layers"] = [
        {"type": "cad", "file": file, "unit": "auto", "axes": {"y": "+Z", "x": "+X"}, "bodies": bodies or []}
    ]
    return cfg


def _cad_page(cfg: dict) -> AppTest:
    at = _run("editor.py")
    at.session_state["fg_cfg"] = cfg
    at.session_state["fg_cfg_name"] = "datei:x"
    at.switch_page(str(Path(APP).parent / "pages" / "cad.py"))
    at.run()
    assert not at.exception, at.exception
    return at


def test_cad_page_without_cad_layer_offers_to_add(fake_fg):
    at = _cad_page(json.loads(json.dumps(EXAMPLE)))
    assert any(b.label == "CAD-Schicht hinzufügen" for b in at.button)
    next(b for b in at.button if b.label == "CAD-Schicht hinzufügen").click().run()
    assert [L["type"] for L in at.session_state["fg_cfg"]["layers"]][-1] == "cad"


def test_cad_page_check_shows_findings_bands_and_preview(fake_fg, tmp_path, monkeypatch):
    from conftest import FAKE_STEP
    from fg_gui import cad

    monkeypatch.setenv("FG_GUI_DATA_DIR", str(tmp_path / "data"))
    step = cad.save_upload(FAKE_STEP.encode(), tmp_path / "data" / "uploads")
    at = _cad_page(_cad_cfg(str(step), [{"name": "Pillar", "material": "bar"}]))
    assert any("Pillar" in c.value for c in at.caption)  # Körper aus der Datei gelesen
    next(b for b in at.button if b.label == "Prüfen").click().run()
    _wait(at, lambda: at.success)
    assert not at.exception, at.exception
    assert at.success and "in Ordnung" in at.success[0].value
    assert len(at.dataframe) >= 2  # Befunde (Warnung) und Bänder
    assert any(s.label.startswith("Höhe y") for s in at.selectbox)
    # die Prüfung ist ein gespeicherter Job der Art „cad“
    from fg_gui.state import job_manager

    job = job_manager().get(at.session_state["fg_cad_job"])
    assert job.kind == "cad" and job.result()["previews"][0]["y_um"] == pytest.approx(0.1)


def test_cad_page_reports_errors(fake_fg, tmp_path, monkeypatch):
    from conftest import FAKE_STEP
    from fg_gui import cad

    monkeypatch.setenv("FG_GUI_DATA_DIR", str(tmp_path / "data"))
    step = cad.save_upload(FAKE_STEP.encode(), tmp_path / "data" / "uploads")
    at = _cad_page(_cad_cfg(str(step)))  # keine Zuordnung → BODY_UNASSIGNED
    next(b for b in at.button if b.label == "Prüfen").click().run()
    _wait(at, lambda: at.error)
    assert any("Fehler" in e.value for e in at.error)


def test_files_outside_allowed_directories_are_refused(fake_fg, tmp_path, monkeypatch):
    outside = tmp_path / "geheim.step"
    outside.write_text("ISO-10303-21;")
    monkeypatch.setenv("FG_GUI_DATA_DIR", str(tmp_path / "data"))
    at = _run("editor.py")
    at.session_state["fg_cfg"] = _cad_cfg(str(outside))
    at.session_state["fg_cfg_name"] = "datei:x"
    at.run()
    next(b for b in at.button if b.label == "Rechnen").click().run()
    assert any("außerhalb der erlaubten Verzeichnisse" in e.value for e in at.error)
    assert "fg_editor_job" not in at.session_state


def test_cad_page_without_slicer(fake_fg):
    fake_fg.cad.available = lambda: False
    at = _cad_page(json.loads(json.dumps(EXAMPLE)))
    assert any("ohne den CAD-Slicer" in w.value for w in at.warning)


# ---------------------------------------------------------------- G6: Optimierung
def _opt_page_with_preset(fake_fg) -> AppTest:
    at = _run("editor.py")
    at.switch_page(str(Path(APP).parent / "pages" / "optimize.py"))
    at.run()
    assert not at.exception, at.exception
    next(b for b in at.button if b.label == "Littrow-Vorlage laden").click().run()
    assert not at.exception, at.exception
    assert at.session_state["fg_cfg"]["period_um"] == {"x": 0.5}
    return at


def test_optimize_page_runs_preset_and_applies_result(fake_fg):
    at = _opt_page_with_preset(fake_fg)
    assert any(df.value.shape[0] == 2 for df in at.dataframe if "Start" in df.value.columns)  # zwei Parameter
    next(b for b in at.button if b.label == "Optimieren").click().run()
    _wait(at, lambda: any(m.label == "Zielwert am Optimum" for m in at.metric))
    assert not at.exception, at.exception
    best = next(m for m in at.metric if m.label == "Zielwert am Optimum")
    assert float(best.value) == pytest.approx(1.0, abs=1e-6)
    from fg_gui.state import job_manager

    job = job_manager().get(at.session_state["fg_opt_job"])
    assert job.kind == "optimize" and job.result()["success"]
    next(b for b in at.button if b.label == "Optimum in den Editor übernehmen").click().run()
    cfg = at.session_state["fg_cfg"]
    assert cfg["layers"][0]["thickness_um"] == pytest.approx(0.25, abs=1e-5)
    assert cfg["layers"][0]["breakpoints_um"][1] == pytest.approx(0.25, abs=1e-5)


def test_optimize_page_shows_input_errors(fake_fg):
    at = _opt_page_with_preset(fake_fg)
    next(t for t in at.text_input if t.label.startswith("Weitere Pointer")).set_value("/layers/0/nix").run()
    assert any("keine Zahl" in e.value or "existiert" in e.value for e in at.error)


def test_optimize_page_without_config(fake_fg):
    at = AppTest.from_file(str(Path(APP).parent / "pages" / "optimize.py"), default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("Editor" in i.value for i in at.info)


def test_editor_2d_layers_have_forms(fake_fg, tmp_path, monkeypatch):
    cfg = {
        "dimension": "2D", "solver": "rcwa", "truncation": {"Nx": 3, "Nz": 3}, "period_um": {"x": 0.6, "z": 0.6},
        "incidence": {"lambda_um": 0.63, "phi_deg": 0, "psi_deg": 0, "delta_deg": 0},
        "materials": {"air": {"n": 1.0}, "si": {"n": 3.9}}, "superstrate": "air", "substrate": "si",
        "layers": [
            {"type": "polygon2d", "thickness_um": 0.15, "background": "air",
             "inclusions": [{"material": "si", "rectangle_um": {"center": [0.3, 0.3], "size": [0.3, 0.3]}}]},
            {"type": "contour2d", "thickness_um": 0.1, "background": "air",
             "regions": [{"material": "si", "circle": {"center_um": [0.3, 0.3], "radius_um": 0.1}}]},
            {"type": "profile2d", "shape": "egg_crate", "depth_um": 0.1, "below": "si", "above": "air"},
        ],
    }  # fmt: skip
    (tmp_path / "p2d.json").write_text(json.dumps(cfg))
    at = _editor(monkeypatch, tmp_path, "p2d.json")
    assert at.session_state["fg_cfg"] == cfg
    assert not any("kein Formular" in i.value for i in at.info)
