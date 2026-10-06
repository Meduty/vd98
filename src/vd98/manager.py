"""Download queue: one worker thread feeding URLs to yt-dlp sequentially."""

import itertools
import os
import queue
import re
import threading
import time
from dataclasses import dataclass, field, fields
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError

from .eta import HalfWindowEta
from .formats import preset_opts
from .urls import normalize_url

TERMINAL = {"done", "error", "cancelled"}
UNFINISHED = {"queued", "downloading", "processing", "paused"}  # persisted (V.20)
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
    total_bytes: int | None = None
    size_estimated: bool = False
    downloaded_bytes: int | None = None
    filename: str = ""
    error: str = ""
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _tmpfiles: set = field(default_factory=set, repr=False)
    _eta: HalfWindowEta = field(default_factory=HalfWindowEta, repr=False)
    _suspend: bool = field(default=False, repr=False)

    def persisted(self) -> dict:
        """What the queue store keeps so the download can resume after a restart."""
        return {
            "url": self.url,
            "preset": self.preset,
            "dest_dir": self.dest_dir,
            "title": self.title,
            "filename": self.filename,
            "tmpfiles": sorted(self._tmpfiles),
            "percent": self.percent,
            "total_bytes": self.total_bytes,
            "size_estimated": self.size_estimated,
        }

    def public(self) -> dict:
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if not f.name.startswith("_")
        }


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
    def __init__(self, ydl_factory=yt_dlp.YoutubeDL, clock=time.monotonic, store=None):
        self._factory = ydl_factory
        self._clock = clock  # injectable for the ETA tests
        self._store = (
            store  # QueueStore or None: unfinished jobs survive restarts (V.20)
        )
        self._persist_lock = threading.Lock()
        self._suspending = False
        self._running: Job | None = None
        self._run_done = threading.Event()
        self._run_done.set()
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
            self._suspending = False
        self._queue.put(job.id)
        self._persist()
        return job.public()

    def cancel(self, job_id: int) -> bool:
        paused = None
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in TERMINAL:
                return False
            job._cancel.set()
            if job.status == "paused":
                paused = job  # not running: clean up its kept partials here
            if job.status in ("queued", "paused"):
                job.status = "cancelled"
        if paused is not None:
            self._cleanup_partials(paused)
        self._persist()
        return True

    def suspend(self, timeout: float = 5.0) -> bool:
        """Stop for app exit, keeping partial files (V.21): running and queued -> paused.

        Returns False if the running job didn't stop within `timeout` (e.g. ffmpeg was
        converting; that job may still finish as done).
        """
        with self._lock:
            self._suspending = True
            running = self._running
            for job in self._jobs.values():
                if job.status == "queued":
                    job.status = "paused"
            if running is not None and running.status not in TERMINAL:
                running._suspend = True
                running._cancel.set()
        stopped = self._run_done.wait(timeout)
        self._persist()
        return stopped

    def restore(self) -> int:
        """Load unfinished jobs from the store as paused; nothing runs until resumed."""
        if self._store is None:
            return 0
        entries = self._store.load()
        with self._lock:
            for e in entries:
                job = Job(
                    id=next(self._ids),
                    url=e["url"],
                    preset=e["preset"],
                    dest_dir=e["dest_dir"],
                    title=e["title"],
                    status="paused",
                    percent=e["percent"],
                    total_bytes=e["total_bytes"],
                    size_estimated=e["size_estimated"],
                    filename=e["filename"],
                )
                job._tmpfiles.update(e["tmpfiles"])
                self._jobs[job.id] = job
        return len(entries)

    def resume(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "paused":
                return False
            job.status = "queued"
            job._cancel = threading.Event()
            job._suspend = False
            job._eta = HalfWindowEta()
            self._suspending = False
            self._idle.clear()
        self._queue.put(
            job_id
        )  # yt-dlp continues the .part (continuedl is on by default)
        self._persist()
        return True

    def resume_all(self) -> int:
        paused = [j["id"] for j in self.jobs() if j["status"] == "paused"]
        return sum(self.resume(jid) for jid in paused)

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
                runnable = (
                    job is not None and job.status == "queued" and not self._suspending
                )
                if runnable:
                    job.status = "downloading"
                    self._running = job
                    self._run_done.clear()
            if runnable:
                self._persist()
                try:
                    self._run(job)
                finally:
                    with self._lock:
                        self._running = None
                    self._run_done.set()
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
            if job._suspend:  # app closing: keep partials so the download can resume
                self._update(job, status="paused", speed=None, eta=None)
            else:
                self._cleanup_partials(job)
                self._update(job, status="cancelled", speed=None, eta=None)
        except DownloadError as exc:
            self._update(
                job, status="error", error=clean_error(exc), speed=None, eta=None
            )
        except Exception as exc:  # noqa: BLE001 — surface anything to the UI
            self._update(
                job, status="error", error=clean_error(exc), speed=None, eta=None
            )

    def _on_hook(self, job: Job, d: dict) -> None:
        if job._cancel.is_set():
            raise DownloadCancelled()
        changes = {}
        title = (d.get("info_dict") or {}).get("title")
        if title and not job.title:
            changes["title"] = title
        new_partial = (
            bool(d.get("tmpfilename")) and d["tmpfilename"] not in job._tmpfiles
        )
        if d.get("tmpfilename"):
            job._tmpfiles.add(d["tmpfilename"])
        if d.get("filename"):
            changes["filename"] = d["filename"]
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes")
            if total:
                changes["percent"] = round(100.0 * (done or 0) / total, 1)
                changes["total_bytes"] = int(total)
                changes["size_estimated"] = not d.get("total_bytes")
            elif d.get("fragment_count"):
                changes["percent"] = round(
                    100.0 * d.get("fragment_index", 0) / d["fragment_count"], 1
                )
            if done is not None:
                changes["downloaded_bytes"] = int(done)
                job._eta.add(self._clock(), int(done))
            smoothed = job._eta.eta(int(total) if total else None)
            changes["speed"] = d.get("speed")
            if smoothed is not None:
                changes["eta"] = round(smoothed)
            elif job._eta.stalled():
                changes["eta"] = None  # V.22: no ETA in a stall, not yt-dlp's stale one
            else:
                changes["eta"] = d.get("eta")  # not enough samples yet
        elif d.get("status") == "finished":
            changes.update(percent=100.0, speed=None, eta=None)
        self._update(job, **changes)
        if new_partial:
            # save the .part path now, not only on the next status change, so a
            # killed (not closed) app still lets Cancel clean it up (PR #3 review)
            self._persist()

    def _on_pp_hook(self, job: Job, d: dict) -> None:
        if d.get("status") == "started":
            self._update(job, status="processing", percent=100.0, speed=None, eta=None)

    def _update(self, job: Job, **changes) -> None:
        with self._lock:
            if job.status in TERMINAL and job.status != changes.get("status"):
                # Terminal state is final; only a queued->cancelled race lands here.
                return
            for k, v in changes.items():
                setattr(
                    job, k, min(v, 100.0) if k == "percent" and v is not None else v
                )
            snapshot = job.public()
        if "status" in changes:
            self._persist()  # on status changes only, not on every progress tick
        if self.on_progress:
            self.on_progress(snapshot)

    def _persist(self) -> None:
        """Save unfinished jobs (V.20). Never raises; a full disk only loses resume info."""
        if self._store is None:
            return
        # Snapshot INSIDE the save lock: otherwise an older snapshot can wait for the lock
        # and overwrite a newer save (PR #3 review). Lock order: _persist_lock -> _lock.
        with (
            self._persist_lock
        ):  # one writer at a time: the store uses a fixed tmp name
            self._store.save(self._unfinished())

    def _unfinished(self) -> list[dict]:
        with self._lock:
            return [
                j.persisted() for j in self._jobs.values() if j.status in UNFINISHED
            ]

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
                if (
                    path.is_relative_to(dest)
                    and path.is_file()
                    and path.name.endswith((".part", ".ytdl"))
                ):
                    os.remove(path)
            except OSError:
                pass
