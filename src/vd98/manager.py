"""Download queue: one worker thread feeding URLs to yt-dlp sequentially."""

import itertools
import os
import queue
import re
import threading
from dataclasses import dataclass, field, fields
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError

from .formats import preset_opts
from .urls import normalize_url

TERMINAL = {"done", "error", "cancelled"}
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PREFIX = re.compile(r"^(ERROR:\s*)?(\[[^\]]+\]\s*)?")


@dataclass
class Job:
    id: int
    url: str
    preset: str
    dest_dir: str
    title: str = ""
    status: str = "queued"
    percent: float = 0.0
    speed: float | None = None
    eta: int | None = None
    filename: str = ""
    error: str = ""
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _tmpfiles: set = field(default_factory=set, repr=False)

    def public(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self) if not f.name.startswith("_")}


class _QuietLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def clean_error(exc: BaseException) -> str:
    msg = _ANSI.sub("", str(exc)).strip().splitlines()[0] if str(exc).strip() else ""
    msg = _PREFIX.sub("", msg).strip()
    return msg or exc.__class__.__name__


class DownloadManager:
    def __init__(self, ydl_factory=yt_dlp.YoutubeDL):
        self._factory = ydl_factory
        self._jobs: dict[int, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[int] = queue.Queue()
        self._ids = itertools.count(1)
        self._idle = threading.Event()
        self._idle.set()
        self.on_progress = None  # optional callback(job_dict) for UI/tests
        threading.Thread(target=self._worker, name="vd98-worker", daemon=True).start()

    # -- public API -------------------------------------------------------
    def add(self, url: str, preset: str, dest_dir: str) -> dict:
        url = normalize_url(url)
        preset_opts(preset)  # validates preset
        if not dest_dir or not Path(dest_dir).is_dir():
            raise ValueError("Download folder does not exist.")
        with self._lock:
            job = Job(id=next(self._ids), url=url, preset=preset, dest_dir=dest_dir)
            self._jobs[job.id] = job
            self._idle.clear()
        self._queue.put(job.id)
        return job.public()

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in TERMINAL:
                return False
            job._cancel.set()
            if job.status == "queued":
                job.status = "cancelled"
        return True

    def cancel_all(self) -> None:
        for job in self.jobs():
            self.cancel(job["id"])

    def remove(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status not in TERMINAL:
                return False
            del self._jobs[job_id]
        return True

    def clear_finished(self) -> None:
        with self._lock:
            for jid in [j.id for j in self._jobs.values() if j.status in TERMINAL]:
                del self._jobs[jid]

    def get(self, job_id: int) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.public() if job else None

    def jobs(self) -> list[dict]:
        with self._lock:
            return [j.public() for j in self._jobs.values()]

    def wait_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    # -- worker -----------------------------------------------------------
    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            with self._lock:
                job = self._jobs.get(job_id)
                runnable = job is not None and job.status == "queued"
                if runnable:
                    job.status = "downloading"
            if runnable:
                self._run(job)
            with self._lock:
                if self._queue.empty():
                    self._idle.set()

    def _run(self, job: Job) -> None:
        opts = preset_opts(job.preset)
        opts.update(
            paths={"home": job.dest_dir},
            outtmpl="%(title).150B [%(id)s].%(ext)s",
            noplaylist=True,
            quiet=True,
            no_warnings=True,
            noprogress=True,
            logger=_QuietLogger(),
            progress_hooks=[lambda d: self._on_hook(job, d)],
            postprocessor_hooks=[lambda d: self._on_pp_hook(job, d)],
        )
        try:
            with self._factory(opts) as ydl:
                info = ydl.extract_info(job.url, download=True) or {}
            if job._cancel.is_set():
                raise DownloadCancelled()
            downloads = info.get("requested_downloads") or [{}]
            self._update(
                job,
                status="done",
                percent=100.0,
                title=job.title or info.get("title") or job.url,
                filename=downloads[-1].get("filepath") or job.filename,
                speed=None,
                eta=None,
            )
        except DownloadCancelled:
            self._cleanup_partials(job)
            self._update(job, status="cancelled", speed=None, eta=None)
        except DownloadError as exc:
            self._update(job, status="error", error=clean_error(exc), speed=None, eta=None)
        except Exception as exc:  # noqa: BLE001 — surface anything to the UI
            self._update(job, status="error", error=clean_error(exc), speed=None, eta=None)

    def _on_hook(self, job: Job, d: dict) -> None:
        if job._cancel.is_set():
            raise DownloadCancelled()
        changes = {}
        title = (d.get("info_dict") or {}).get("title")
        if title and not job.title:
            changes["title"] = title
        if d.get("tmpfilename"):
            job._tmpfiles.add(d["tmpfilename"])
        if d.get("filename"):
            changes["filename"] = d["filename"]
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                changes["percent"] = round(100.0 * d.get("downloaded_bytes", 0) / total, 1)
            elif d.get("fragment_count"):
                changes["percent"] = round(100.0 * d.get("fragment_index", 0) / d["fragment_count"], 1)
            changes["speed"] = d.get("speed")
            changes["eta"] = d.get("eta")
        elif d.get("status") == "finished":
            changes.update(percent=100.0, speed=None, eta=None)
        self._update(job, **changes)

    def _on_pp_hook(self, job: Job, d: dict) -> None:
        if d.get("status") == "started":
            self._update(job, status="processing", percent=100.0, speed=None, eta=None)

    def _update(self, job: Job, **changes) -> None:
        with self._lock:
            if job.status in TERMINAL and job.status != changes.get("status"):
                # Terminal state is final; only a queued->cancelled race lands here.
                return
            for k, v in changes.items():
                setattr(job, k, min(v, 100.0) if k == "percent" and v is not None else v)
            snapshot = job.public()
        if self.on_progress:
            self.on_progress(snapshot)

    def _cleanup_partials(self, job: Job) -> None:
        dest = Path(job.dest_dir).resolve()
        candidates = set(job._tmpfiles)
        if job.filename:
            candidates.add(job.filename + ".part")
        for name in candidates:
            path = Path(name)
            if not path.is_absolute():
                path = dest / path
            try:
                path = path.resolve()
                if path.is_relative_to(dest) and path.is_file() and path.name.endswith((".part", ".ytdl")):
                    os.remove(path)
            except OSError:
                pass
