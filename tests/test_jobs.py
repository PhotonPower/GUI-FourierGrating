import threading

from fg_gui.jobs import DONE, FAILED, RUNNING, JobManager


def test_success_and_failure():
    jm = JobManager(workers=1)
    ok = jm.submit("ok", lambda x: x * 2, 21, owner="s1")
    bad = jm.submit("bad", lambda: 1 / 0, owner="s2")
    ok.future.result()
    bad.future.exception()
    assert ok.status == DONE and ok.result() == 42 and ok.runtime is not None
    assert bad.status == FAILED and "ZeroDivisionError" in bad.error and bad.result() is None
    assert [j.label for j in jm.jobs(owner="s1")] == ["ok"]
    assert len(jm.jobs()) == 2
    jm.shutdown()


def test_serial_with_one_worker():
    jm = JobManager(workers=1)
    gate = threading.Event()
    first = jm.submit("1", gate.wait, 5)
    second = jm.submit("2", lambda: None)
    while first.status != RUNNING:
        pass
    assert second.status == "wartend" and jm.busy() == 2
    gate.set()
    second.future.result()
    assert jm.busy() == 0
    jm.shutdown()


def test_history_trim():
    jm = JobManager(workers=1, history=3)
    for i in range(6):
        jm.submit(str(i), lambda: None).future.result()
    jm.submit("last", lambda: None).future.result()
    assert len(jm.jobs()) <= 4  # beim Einreichen wird gekürzt; der neue Job zählt mit
    jm.shutdown()


# ---------------------------------------------------------------- G4: Persistenz, Abbruch, Warteschlange
import time  # noqa: E402

import numpy as np  # noqa: E402

from conftest import FakeResult, FakeScan, make_fake_nearfield  # noqa: E402
from fg_gui.jobs import CANCELLED, INTERRUPTED, WAITING  # noqa: E402
from fg_gui.store import RunStore  # noqa: E402


def test_restart_keeps_runs(tmp_path):
    store = RunStore(tmp_path / "runs")
    jm = JobManager(workers=1, store=store)
    cfg = {"dimension": "1D", "truncation": {"Nx": 3}}
    a = jm.submit("einzel", FakeResult, owner="s1", kind="solve", config=cfg)
    b = jm.submit("scan", lambda: FakeScan("/p"), owner="s2", kind="scan", config=cfg)
    c = jm.submit("nahfeld", make_fake_nearfield, owner="s1", kind="nearfield", config=cfg)
    bad = jm.submit("kaputt", lambda: 1 / 0, owner="s1", kind="solve", config=cfg)
    for j in (a, b, c):
        j.future.result()
    bad.future.exception()
    jm.shutdown()

    jm2 = JobManager(workers=1, store=RunStore(tmp_path / "runs"))  # „Neustart“
    assert {j.id for j in jm2.jobs()} == {a.id, b.id, c.id, bad.id}
    assert [j.id for j in jm2.jobs(owner="s2")] == [b.id]
    ra = jm2.get(a.id)
    assert ra.status == DONE and ra.kind == "solve" and ra.runtime is not None and ra.label == "einzel"
    assert np.array_equal(ra.result().reflected, FakeResult().reflected)
    assert jm2.get(b.id).result().sweep_parameter == "/p"
    assert set(jm2.get(c.id).result()) >= {"horizontal", "vertical"}
    assert jm2.config(a.id) == cfg
    failed = jm2.get(bad.id)
    assert failed.status == FAILED and "ZeroDivisionError" in failed.error and failed.result() is None
    jm2.shutdown()


def test_unfinished_runs_are_interrupted_after_restart(tmp_path):
    store = RunStore(tmp_path / "runs")
    store.write_meta("w1", {"id": "w1", "label": "wartete", "owner": "s", "submitted": 1.0, "kind": "solve"})
    store.write_meta("w2", {"id": "w2", "label": "lief", "owner": "s", "submitted": 2.0, "started": 3.0})
    jm = JobManager(store=store)
    for i in ("w1", "w2"):
        j = jm.get(i)
        assert j.status == FAILED and j.error == INTERRUPTED
    assert jm.busy() == 0
    assert RunStore(tmp_path / "runs").list_meta()[0]["status"] == FAILED  # auch auf der Platte vermerkt
    jm.shutdown()


def test_cancel_waiting_only(tmp_path):
    store = RunStore(tmp_path / "runs")
    jm = JobManager(workers=1, store=store)
    gate = threading.Event()
    first = jm.submit("1", gate.wait, 5)
    while first.status != RUNNING:
        time.sleep(0.001)
    second = jm.submit("2", lambda: 1)
    assert jm.cancel(first.id) is False  # läuft
    assert jm.cancel(second.id) is True
    assert second.status == CANCELLED and second.result() is None and jm.busy() == 1
    assert jm.cancel(second.id) is False  # nicht mehr wartend
    gate.set()
    first.future.result()
    assert jm.cancel(first.id) is False  # fertig
    jm.shutdown()
    assert JobManager(store=RunStore(tmp_path / "runs")).get(second.id).status == CANCELLED


def test_queue_position_and_order():
    jm = JobManager(workers=1)
    gate = threading.Event()
    first = jm.submit("1", gate.wait, 5)
    while first.status != RUNNING:
        time.sleep(0.001)
    waiting = [jm.submit(str(i), lambda: None) for i in range(3)]
    assert jm.queue_position(first.id) == 0
    assert [jm.queue_position(j.id) for j in waiting] == [1, 2, 3]
    jm.cancel(waiting[0].id)
    assert [jm.queue_position(j.id) for j in waiting] == [0, 1, 2]
    gate.set()
    waiting[2].future.result()
    assert all(jm.queue_position(j.id) == 0 for j in waiting)
    assert all(j.status in (DONE, CANCELLED) for j in waiting)
    jm.shutdown()


def test_delete_removes_files(tmp_path):
    store = RunStore(tmp_path / "runs")
    jm = JobManager(workers=1, store=store)
    gate = threading.Event()
    blocker = jm.submit("b", gate.wait, 5)
    while blocker.status != RUNNING:
        time.sleep(0.001)
    queued = jm.submit("q", lambda: 1)
    assert jm.delete(blocker.id) is False and jm.delete(queued.id) is False  # läuft / wartet
    gate.set()
    queued.future.result()
    done = jm.submit("d", FakeResult, kind="solve", config={"a": 1})
    done.future.result()
    assert store.path(done.id).is_dir()
    assert jm.delete(done.id) is True
    assert jm.get(done.id) is None and not store.path(done.id).exists()
    jm.shutdown()


def test_concurrent_submissions_from_sessions(tmp_path):
    jm = JobManager(workers=2, store=RunStore(tmp_path / "runs"))
    submitted = []
    lock = threading.Lock()

    def session(name):
        for i in range(5):
            j = jm.submit(f"{name}-{i}", FakeResult, owner=name, kind="solve", config={"i": i})
            with lock:
                submitted.append(j)

    threads = [threading.Thread(target=session, args=(f"s{n}",)) for n in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    for j in submitted:
        j.future.result()
    assert len({j.id for j in submitted}) == 20
    for n in range(4):
        mine = jm.jobs(owner=f"s{n}")
        assert len(mine) == 5 and all(j.owner == f"s{n}" and j.status == DONE for j in mine)
    assert len(RunStore(tmp_path / "runs").list_meta()) == 20
    jm.shutdown()


def test_status_values_constant():
    assert WAITING == "wartend"
