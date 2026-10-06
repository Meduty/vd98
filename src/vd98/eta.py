"""Smoothed ETA from the download rate over the most recent half of what was downloaded.

yt-dlp's own ETA follows its instantaneous speed, so it jumps with every burst and
stall. Here the rate is measured from the moment the download had half of its current
size to now: at 400 MB downloaded, from when it hit 200 MB. That window grows with the
download, so the estimate gets steadier over time but still follows a real slowdown.
"""


class HalfWindowEta:
    MAX_SAMPLES = 512  # thinned beyond 2x this; the reference only needs coarse samples

    def __init__(self) -> None:
        # (time, bytes), bytes non-decreasing within one file
        self._samples: list[tuple[float, int]] = []

    def add(self, t: float, downloaded: int) -> None:
        if self._samples and downloaded < self._samples[-1][1]:
            self._samples = []  # a new file started (e.g. audio after video)
        self._samples.append((t, downloaded))
        self._prune()

    def eta(self, total: int | None) -> float | None:
        """Seconds left, or None when it can't be estimated yet."""
        if not total or len(self._samples) < 2:
            return None
        t_now, done = self._samples[-1]
        if done >= total:
            return 0.0
        t_ref, done_ref = self._reference(done / 2)
        elapsed, gained = t_now - t_ref, done - done_ref
        if elapsed <= 0 or gained <= 0:
            return None  # stalled or no time passed: unknown, not infinite
        return (total - done) / (gained / elapsed)

    def _reference(self, half: float) -> tuple[float, int]:
        """Latest sample at or below the halfway mark, else the oldest one."""
        ref = self._samples[0]
        for sample in self._samples:
            if sample[1] > half:
                break
            ref = sample
        return ref

    def _prune(self) -> None:
        if len(self._samples) < 2:
            return
        half = self._samples[-1][1] / 2
        ref = self._reference(half)
        # samples older than the reference are never needed again (half only grows)
        i = self._samples.index(ref)
        if i > 0:
            del self._samples[:i]
        if len(self._samples) > 2 * self.MAX_SAMPLES:
            last = self._samples[-1]
            self._samples = self._samples[:-1:2] + [last]
