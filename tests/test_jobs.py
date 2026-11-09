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
