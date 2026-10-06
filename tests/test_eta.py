"""Smoothed ETA (SPEC T.16): rate over the most recent half of what was downloaded."""

import pytest

from vd98.eta import HalfWindowEta


def feed(est, samples):
    for t, done in samples:
        est.add(t, done)


def test_no_estimate_before_two_samples():
    est = HalfWindowEta()
    assert est.eta(1000) is None
    est.add(0.0, 100)
    assert est.eta(1000) is None


def test_no_estimate_without_total():
    est = HalfWindowEta()
    feed(est, [(0, 0), (1, 100)])
    assert est.eta(None) is None


def test_steady_rate():
    est = HalfWindowEta()
    feed(est, [(t, t * 100) for t in range(11)])  # 100 B/s, 1000 B after 10 s
    assert est.eta(2000) == pytest.approx(10.0)


def test_uses_most_recent_half_not_whole_history():
    """Slow first half, fast second half: ETA follows the recent (second-half) rate."""
    est = HalfWindowEta()
    # 0..500 B at 10 B/s (50 s), then 500..1000 B at 100 B/s (5 s)
    samples = [(t, t * 10) for t in range(51)]
    samples += [(50 + t, 500 + t * 100) for t in range(1, 6)]
    feed(est, samples)
    # reference = latest sample at or below 500 B -> (50 s, 500 B); rate = 500 / 5 = 100 B/s
    assert est.eta(2000) == pytest.approx(10.0)


def test_single_spike_does_not_swing_estimate():
    """A burst in the last second barely moves a half-window rate (unlike instant speed)."""
    est = HalfWindowEta()
    samples = [(t, t * 100) for t in range(20)]  # 1900 B at 100 B/s
    samples.append((20, 1900 + 1000))  # one 1000 B/s burst
    feed(est, samples)
    eta = est.eta(10_000)
    # window: ~1450 B at t=14.5 .. 2900 B at t=20 -> ~263 B/s -> ETA ~27 s
    # (instantaneous 1000 B/s would claim ~7 s)
    assert 20 < eta < 35


def test_new_file_resets_window():
    """yt-dlp downloads video then audio as separate files: bytes drop -> start over."""
    est = HalfWindowEta()
    feed(est, [(t, t * 100) for t in range(11)])
    est.add(11.0, 50)  # second stream starts
    assert est.eta(1000) is None  # only one sample in the new window
    est.add(12.0, 150)
    assert est.eta(1000) == pytest.approx(8.5)


def test_finished_or_stalled():
    est = HalfWindowEta()
    feed(est, [(0, 0), (1, 1000)])
    assert est.eta(1000) == 0.0
    stalled = HalfWindowEta()
    feed(stalled, [(0, 500), (5, 500)])
    assert stalled.eta(1000) is None  # no progress -> unknown, not infinite


def test_stall_after_progress_clears_eta():
    """PR #3 review finding 3: progress, then no growth for STALL_SECONDS -> no ETA."""
    est = HalfWindowEta()
    feed(est, [(0, 0), (1, 100), (1 + HalfWindowEta.STALL_SECONDS, 100)])
    assert est.eta(1000) is None


def test_brief_pause_keeps_eta():
    """A one-second hiccup is not a stall: the estimate stays."""
    est = HalfWindowEta()
    feed(est, [(0, 0), (1, 100), (2, 100)])
    assert est.eta(1000) is not None


def test_memory_stays_bounded():
    est = HalfWindowEta()
    feed(est, [(t / 10, t) for t in range(100_000)])
    assert len(est._samples) <= 2 * est.MAX_SAMPLES
