"""Rechnungen im Hintergrund.

Streamlit führt das Seitenskript bei jeder Interaktion neu aus; eine Rechnung darf es daher nie blockieren.
Ein prozessweiter ``JobManager`` (über ``st.cache_resource`` für alle Sitzungen geteilt) führt die Aufrufe in
einem Threadpool aus. FourierGrating gibt während der Rechnung den GIL frei, Threads genügen also.

Mit einem :class:`~fg_gui.store.RunStore` bleiben Rechnungen über Neustarts erhalten (G4): Metadaten, Konfiguration
und Ergebnis werden gespeichert, beim Start geladen (Ergebnisse erst beim Anzeigen). Wartende Jobs lassen sich
abbrechen; eine laufende Rechnung nicht (FourierGrating bietet keinen Abbruch).
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

from .store import RunStore

WAITING, RUNNING, DONE, FAILED, CANCELLED = "wartend", "läuft", "fertig", "Fehler", "abgebrochen"
INTERRUPTED = "Server wurde neu gestartet"


@dataclass
class Job:
    id: str
    label: str
    owner: str
    submitted: float
    future: Future | None = field(default=None, repr=False)
    started: float | None = None
    finished: float | None = None
    error: str = ""
    traceback: str = ""
    kind: str = ""  # "solve" | "scan" | "nearfield" | ""
    cancelled: bool = False
    #: Lader für Ergebnisse, die von der Festplatte kommen (nach einem Neustart)
    loader: Callable[[], Any] | None = field(default=None, repr=False)
    _loaded: Any = field(default=None, repr=False)

    @property
    def status(self) -> str:
        if self.finished is not None:
            if self.cancelled:
                return CANCELLED
            return FAILED if self.error else DONE
        return RUNNING if self.started is not None else WAITING

    @property
    def runtime(self) -> float | None:
        if self.started is None:
            return None
        return (self.finished or time.time()) - self.started

    def result(self) -> Any:
        """Ergebnis eines fertigen Jobs (None, solange er läuft oder bei Fehler/Abbruch)."""
        if self.status != DONE:
            return None
        if self.loader is not None:
            if self._loaded is None:
                self._loaded = self.loader()
            return self._loaded
        return self.future.result() if self.future is not None else None

    def meta(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "owner": self.owner,
            "kind": self.kind,
            "submitted": self.submitted,
            "started": self.started,
            "finished": self.finished,
            "status": self.status,
            "cancelled": self.cancelled,
            "error": self.error,
            "traceback": self.traceback,
        }


class JobManager:
    def __init__(self, workers: int = 1, history: int = 50, store: RunStore | None = None):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fg-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._history = history
        self.workers = workers
        self.store = store
        if store is not None:
            self._restore()

    # ------------------------------------------------------------ Wiederherstellen
    def _restore(self) -> None:
        """Gespeicherte Rechnungen laden. Was beim Beenden wartete oder lief, gilt als unterbrochen."""
        assert self.store is not None
        for m in self.store.list_meta():
            job = Job(
                id=m["id"],
                label=m.get("label", m["id"]),
                owner=m.get("owner", ""),
                submitted=float(m.get("submitted") or 0.0),
                started=m.get("started"),
                finished=m.get("finished"),
                error=m.get("error", ""),
                traceback=m.get("traceback", ""),
                kind=m.get("kind", ""),
                cancelled=bool(m.get("cancelled")),
            )
            if job.finished is None:
                job.finished, job.error = time.time(), INTERRUPTED
                self._persist(job)
            if job.status == DONE:
                if self.store.has_result(job.id, job.kind):
                    job.loader = lambda j=job: self.store.load_result(j.id, j.kind)  # type: ignore[union-attr]
                else:
                    job.error = "Ergebnis fehlt auf der Festplatte"
            self._jobs[job.id] = job

    def _persist(self, job: Job) -> None:
        if self.store is not None:
            try:
                self.store.write_meta(job.id, job.meta())
            except OSError:
                pass  # Speichern ist Zugabe; eine volle Platte soll die Rechnung nicht verwerfen

    # ------------------------------------------------------------ Einreichen
    def submit(
        self,
        label: str,
        fn: Callable[..., Any],
        *args: Any,
        owner: str = "",
        kind: str = "",
        config: dict | None = None,
        **kwargs: Any,
    ) -> Job:
        job_id = uuid.uuid4().hex[:12]

        def run() -> Any:
            job = self._jobs[job_id]
            job.started = time.time()
            self._persist(job)
            try:
                result = fn(*args, **kwargs)
                if self.store is not None and kind:
                    try:
                        self.store.save_result(job_id, kind, result)
                    except Exception as e:  # Ergebnis bleibt im Speicher nutzbar
                        job.traceback = f"Ergebnis nicht gespeichert: {type(e).__name__}: {e}"
                return result
            except BaseException as e:
                job.error = f"{type(e).__name__}: {e}"
                job.traceback = traceback.format_exc()
                raise
            finally:
                job.finished = time.time()
                self._persist(job)

        with self._lock:
            job = Job(id=job_id, label=label, owner=owner, submitted=time.time(), kind=kind)
            self._jobs[job_id] = job
            if self.store is not None:
                try:
                    self.store.write_config(job_id, config)
                except OSError:
                    pass
            self._persist(job)
            job.future = self._pool.submit(run)
            self._trim()
        return job

    # ------------------------------------------------------------ Abfragen
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

    def queue_position(self, job_id: str) -> int:
        """Platz in der Warteschlange (1 = als Nächstes); 0, wenn der Job nicht wartet."""
        with self._lock:
            waiting = sorted((j for j in self._jobs.values() if j.status == WAITING), key=lambda j: j.submitted)
        for i, j in enumerate(waiting, start=1):
            if j.id == job_id:
                return i
        return 0

    def config(self, job_id: str) -> dict | None:
        return self.store.read_config(job_id) if self.store is not None else None

    # ------------------------------------------------------------ Eingriffe
    def cancel(self, job_id: str) -> bool:
        """Bricht einen wartenden Job ab. Laufende und fertige Jobs bleiben unberührt (False)."""
        job = self._jobs.get(job_id)
        if job is None or job.status != WAITING or job.future is None:
            return False
        if not job.future.cancel():  # inzwischen gestartet
            return False
        job.cancelled, job.finished = True, time.time()
        self._persist(job)
        return True

    def delete(self, job_id: str) -> bool:
        """Entfernt einen beendeten Job samt gespeicherten Dateien (nicht: wartend oder laufend)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in (WAITING, RUNNING):
                return False
            del self._jobs[job_id]
        if self.store is not None:
            self.store.delete(job_id)
        return True

    def _trim(self) -> None:
        if self.store is not None:
            return  # die Liste ist das Verzeichnis der gespeicherten Rechnungen; Aufräumen: G7
        done = sorted((j for j in self._jobs.values() if j.finished is not None), key=lambda j: j.submitted)
        while len(self._jobs) > self._history and done:
            self._jobs.pop(done.pop(0).id, None)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
