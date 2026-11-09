"""Rechnungen im Hintergrund.

Streamlit führt das Seitenskript bei jeder Interaktion neu aus; eine Rechnung darf es daher nie blockieren.
Ein prozessweiter ``JobManager`` (über ``st.cache_resource`` für alle Sitzungen geteilt) führt die Aufrufe in
einem Threadpool aus. FourierGrating gibt während der Rechnung den GIL frei, Threads genügen also.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

WAITING, RUNNING, DONE, FAILED = "wartend", "läuft", "fertig", "Fehler"


@dataclass
class Job:
    id: str
    label: str
    owner: str
    submitted: float
    future: Future = field(repr=False)
    started: float | None = None
    finished: float | None = None
    error: str = ""
    traceback: str = ""

    @property
    def status(self) -> str:
        if self.finished is not None:
            return FAILED if self.error else DONE
        return RUNNING if self.started is not None else WAITING

    @property
    def runtime(self) -> float | None:
        if self.started is None:
            return None
        return (self.finished or time.time()) - self.started

    def result(self) -> Any:
        """Ergebnis eines fertigen Jobs (None, solange er läuft oder bei Fehler)."""
        if self.status != DONE:
            return None
        return self.future.result()


class JobManager:
    def __init__(self, workers: int = 1, history: int = 50):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fg-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._history = history
        self.workers = workers

    def submit(self, label: str, fn: Callable[..., Any], *args: Any, owner: str = "", **kwargs: Any) -> Job:
        job_id = uuid.uuid4().hex[:12]

        def run() -> Any:
            job = self._jobs[job_id]
            job.started = time.time()
            try:
                return fn(*args, **kwargs)
            except BaseException as e:
                job.error = f"{type(e).__name__}: {e}"
                job.traceback = traceback.format_exc()
                raise
            finally:
                job.finished = time.time()

        with self._lock:
            # Job vor dem Start registrieren, damit run() ihn findet
            fut: Future = Future()
            job = Job(id=job_id, label=label, owner=owner, submitted=time.time(), future=fut)
            self._jobs[job_id] = job
            job.future = self._pool.submit(run)
            self._trim()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def jobs(self, owner: str | None = None) -> list[Job]:
        """Neueste zuerst; mit ``owner`` nur die Jobs dieser Sitzung."""
        with self._lock:
            js = list(self._jobs.values())
        if owner is not None:
            js = [j for j in js if j.owner == owner]
        return sorted(js, key=lambda j: j.submitted, reverse=True)

    def busy(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status in (WAITING, RUNNING))

    def _trim(self) -> None:
        done = sorted((j for j in self._jobs.values() if j.finished is not None), key=lambda j: j.submitted)
        while len(self._jobs) > self._history and done:
            self._jobs.pop(done.pop(0).id, None)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
