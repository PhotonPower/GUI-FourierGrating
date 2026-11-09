"""Betrieb (G7): Benutzer, Logging, Aufräumen, Health-Check."""

import logging
import os
import time

from conftest import FakeResult
from fg_gui import health, housekeeping, logs, users
from fg_gui import settings as st_settings
from fg_gui.jobs import JobManager
from fg_gui.store import RunStore

DAY = 86400.0


def test_user_from_headers():
    h = {"X-Remote-User": " anna@uni.de "}
    assert users.user_from_headers(h, "x-remote-user") == "anna@uni.de"
    assert users.user_from_headers(h, "") == ""
    assert users.user_from_headers(None, "X-Remote-User") == ""
    assert users.user_from_headers({"X-Remote-User": "a b\n<x>"}, "X-Remote-User") == "a_b__x_"
    assert len(users.user_from_headers({"U": "x" * 500}, "U")) == users.MAX_LEN


def test_settings_defaults_and_env(monkeypatch):
    s = st_settings.load()
    assert s.user_header == "" and s.retention_days == 0 and s.max_runs == 0 and s.log_file is None
    monkeypatch.setenv("FG_GUI_USER_HEADER", "X-Remote-User")
    monkeypatch.setenv("FG_GUI_RETENTION_DAYS", "30")
    monkeypatch.setenv("FG_GUI_LOG_LEVEL", "debug")
    s = st_settings.load()
    assert (s.user_header, s.retention_days, s.log_level) == ("X-Remote-User", 30, "DEBUG")


def _manager(tmp_path, n=3):
    jm = JobManager(store=RunStore(tmp_path / "runs"))
    jobs = [jm.submit(f"r{i}", FakeResult, owner="u", kind="solve", config={"i": i}) for i in range(n)]
    for j in jobs:
        j.future.result()
    return jm, jobs


def test_purge_runs_by_age(tmp_path):
    jm, jobs = _manager(tmp_path)
    now = time.time()
    jobs[0].finished = now - 40 * DAY
    jobs[1].finished = now - 10 * DAY
    rep = housekeeping.purge_runs(jm, retention_days=30, now=now)
    assert rep.runs == 1 and rep.freed_bytes > 0
    assert jm.get(jobs[0].id) is None and jm.get(jobs[1].id) is not None
    assert not jm.store.path(jobs[0].id).exists()


def test_purge_runs_by_count_keeps_newest(tmp_path):
    jm, jobs = _manager(tmp_path, 4)
    for i, j in enumerate(jobs):
        j.finished = time.time() - (10 - i) * 60
    rep = housekeeping.purge_runs(jm, max_runs=2)
    assert rep.runs == 2
    assert {j.id for j in jm.jobs()} == {jobs[2].id, jobs[3].id}


def test_purge_runs_off_and_keeps_running(tmp_path):
    jm, jobs = _manager(tmp_path)
    assert housekeeping.purge_runs(jm).runs == 0
    jobs[0].finished = None  # gilt als laufend
    jobs[0].started = time.time()
    assert housekeeping.purge_runs(jm, retention_days=1, now=time.time() + 100 * DAY).runs == 2
    assert jm.get(jobs[0].id) is not None


def test_purge_uploads_keeps_referenced_and_young(tmp_path):
    jm = JobManager(store=RunStore(tmp_path / "runs"))
    up = tmp_path / "uploads"
    up.mkdir()
    old_used, old_free, young = up / "used.step", up / "free.step", up / "young.step"
    for f in (old_used, old_free, young):
        f.write_text("x")
    for f in (old_used, old_free):
        os.utime(f, (time.time() - 40 * DAY,) * 2)
    jm.submit("r", FakeResult, kind="solve", config={"file": str(old_used)}).future.result()
    rep = housekeeping.purge_uploads(up, jm, retention_days=30)
    assert rep.uploads == 1 and not old_free.exists() and old_used.exists() and young.exists()
    assert housekeeping.purge_uploads(up, jm, retention_days=0).uploads == 0


def test_jobs_are_logged(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="fg_gui"):
        jm = JobManager(store=RunStore(tmp_path / "runs"))
        ok = jm.submit("gut", FakeResult, owner="anna", kind="solve", config={})
        ok.future.result()
        bad = jm.submit("schlecht", lambda: 1 / 0, owner="anna", kind="solve", config={})
        try:
            bad.future.result()
        except ZeroDivisionError:
            pass
        jm.delete(ok.id)
    text = caplog.text
    assert "eingereicht" in text and "Benutzer anna" in text and "fertig" in text
    assert "fehlgeschlagen" in text and "gelöscht" in text


def test_logs_configure_writes_file_and_is_idempotent(tmp_path):
    f = tmp_path / "log" / "fg.log"
    log = logs.configure("INFO", f)
    logs.configure("INFO", f)
    assert sum(getattr(h, "_fg_gui", False) for h in log.handlers) == 2
    log.info("hallo")
    for h in log.handlers:
        h.flush()
    assert "hallo" in f.read_text()
    logs.configure("INFO", None)


def test_health_data_dir_and_url(tmp_path, monkeypatch):
    assert health.check_data_dir(tmp_path / "d")[0]
    f = tmp_path / "f"
    f.write_text("x")
    assert not health.check_data_dir(f / "sub")[0]
    assert not health.check_url("http://127.0.0.1:9/_stcore/health", timeout=1)[0]


def test_health_run_exit_code(tmp_path, monkeypatch, capsys, fake_fg):
    monkeypatch.setenv("FG_GUI_DATA_DIR", str(tmp_path))
    try:
        health.main([])
    except SystemExit as e:
        assert e.code == 0
    assert "OK" in capsys.readouterr().out
    try:
        health.main(["--url", "http://127.0.0.1:9"])
    except SystemExit as e:
        assert e.code == 1


def test_purge_drafts(tmp_path):
    d = tmp_path / "sessions"
    d.mkdir()
    old, new = d / "a.json", d / "b.json"
    old.write_text("{}")
    new.write_text("{}")
    os.utime(old, (time.time() - 40 * DAY,) * 2)
    assert housekeeping.purge_drafts(d, 30) == 1 and not old.exists() and new.exists()
    assert housekeeping.purge_drafts(d, 0) == 0
