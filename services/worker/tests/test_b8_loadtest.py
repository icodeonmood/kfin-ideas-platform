"""The load test's arithmetic (AT-B8-01): the error rate is per operation, and failed scans count."""

from __future__ import annotations

import random

from loadtest.__main__ import Stats, arrivals


def test_error_rate_is_per_operation_not_per_request() -> None:
    s = Stats()
    s.requests = 10_000  # thousands of polls must not dilute a failed submission
    for ok in [True] * 95 + [False] * 5:
        s.op("submission", ok)
    out = s.summary()
    assert out["error_rate"] == 0.05
    assert out["operations"]["submission"] == {"attempted": 100, "failed": 5}


def test_percentiles() -> None:
    s = Stats()
    for v in range(1, 101):
        s.add("scan", float(v))
    out = s.summary()["scan"]
    assert out["count"] == 100 and 94 <= out["p95_s"] <= 96 and out["max_s"] == 100.0


def test_arrivals_follow_the_rate() -> None:
    times = arrivals(150 / 3600, 3600, random.Random(7))
    assert 120 <= len(times) <= 180 and all(0 <= t < 3600 for t in times)
