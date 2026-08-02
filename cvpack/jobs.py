"""Petit gestionnaire de taches de fond (import, decoupe, transcription, build)."""

from __future__ import annotations

import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cvpack")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class Job:
    def __init__(self, job_id: str, label: str):
        self.id = job_id
        self.label = label

    def progress(self, fraction: float, message: str = "") -> None:
        with _lock:
            job = _jobs.get(self.id)
            if job is None:
                return
            job["progress"] = max(0.0, min(1.0, float(fraction)))
            if message:
                job["message"] = message

    def cancelled(self) -> bool:
        with _lock:
            return bool(_jobs.get(self.id, {}).get("cancel"))


def submit(label: str, func, *args, **kwargs) -> str:
    job_id = uuid.uuid4().hex[:10]
    with _lock:
        _jobs[job_id] = {
            "id": job_id, "label": label, "state": "running",
            "progress": 0.0, "message": "", "result": None, "error": None,
        }
    job = Job(job_id, label)

    def runner():
        try:
            result = func(job, *args, **kwargs)
            with _lock:
                _jobs[job_id].update(state="done", progress=1.0, result=result)
        except Exception as exc:  # noqa: BLE001 - on remonte tout au client
            with _lock:
                _jobs[job_id].update(
                    state="error",
                    error=str(exc) or exc.__class__.__name__,
                    traceback=traceback.format_exc()[-2000:],
                )

    _executor.submit(runner)
    return job_id


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def cancel(job_id: str) -> bool:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["state"] != "running":
            return False
        job["cancel"] = True
        return True


def prune(keep: int = 60) -> None:
    with _lock:
        if len(_jobs) <= keep:
            return
        finished = [j for j in _jobs.values() if j["state"] != "running"]
        for job in finished[: len(_jobs) - keep]:
            _jobs.pop(job["id"], None)
