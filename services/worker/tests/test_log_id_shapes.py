"""L-AUDIT, non-negotiable 3 (BLD-A189): our own identifiers pass the strict log policy; personal data does not.

About 0.6% of random UUIDs hold a digit run shaped like a mobile, card or Aadhaar number. As `DRAFT-<uuid>` (the
gateway's `ref_id` for drafts and eval runs) or an upper-case UUID they were refused in strict mode (dev, the demo
and CI), so random tests failed and a gateway call could fail. Only the exact identifier shape is exempt.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from collections.abc import Callable

import generators as g
import pytest

from core import logging as klog
from pii.log_rules import scan_log_line, value_patterns
from pii.patterns import scan

SEED = 20261120
COUNT = 20000
# A fixed synthetic UUID that ends in a letter, so a number written after it cannot join its last digit run.
FIXED = "1b2c3d4e-5f60-4a1b-9c2d-0a1b2c3d4e5f"


def _quiet_log(monkeypatch: pytest.MonkeyPatch) -> klog.Log:
    """A strict-mode logger whose lines are checked by the policy but not written (20,000 x 5 lines would bloat
    the run's captured log; the scanner half is checked on each value below)."""
    monkeypatch.setenv("APP_ENV", "dev")
    name = "test.l_audit.id_shapes"
    logging.getLogger(name).setLevel(logging.CRITICAL + 1)  # a logger of this test's own
    return klog.get_logger(name)


def _shapes(u: uuid.UUID) -> list[str]:
    s = str(u)
    return [s, f"DRAFT-{s}", f"IDEA-{s}", s.upper(), f"DRAFT-{s.upper()}"]


def test_l_audit_nn3_seeded_uuids_as_ref_id_are_never_refused_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = _quiet_log(monkeypatch)
    rng = random.Random(SEED)
    would_have_tripped = 0
    for _ in range(COUNT):
        values = _shapes(uuid.UUID(int=rng.getrandbits(128)))
        if scan(values[1], kfin_domains=[]):
            would_have_tripped += (
                1  # the raw detection patterns still see a number in it; the log policy must not
            )
        for value in values:
            log.info("gateway.call", agent="gatekeeper", outcome="ok", ref_id=value)
            assert scan_log_line(json.dumps({"event": "gateway.call", "ref_id": value})) == [], value
        log.info("gateway.batch", ref_ids=values)  # the list branch
    # 121 with this seed today. Any positive count proves the test still exercises IDs that used to fail; an exact
    # count would break whenever a detection pattern is tuned.
    assert would_have_tripped > 0


def test_l_audit_nn3_ids_that_tripped_before_are_written_and_pass_the_scrubber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Written for real, so the end-of-run scan in conftest.py also sees them."""
    import io

    monkeypatch.setenv("APP_ENV", "dev")
    stream = io.StringIO()
    klog.configure("INFO", stream)
    try:
        log = klog.get_logger("test.l_audit.tripped")
        for u in (
            "9f7499ea-9c89-96af-8f52-9c6965331798",  # mobile-shaped
            "10fe3541-75dc-15f7-2993-4465871481aa",  # card-shaped
            "85536546-2506-e890-1a21-e17110cbe889",  # Aadhaar-shaped
        ):
            assert scan(f"DRAFT-{u}", kfin_domains=[]) != []
            for value in (u, f"DRAFT-{u}", f"IDEA-{u}", u.upper(), f"DRAFT-{u.upper()}"):
                log.info("gateway.call", ref_id=value, idea_uuid=value)
    finally:
        klog.configure("INFO")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 15
    assert all(scan_log_line(line) == [] for line in lines)


_CARDS = ("4111-1111-1111-1111", "4111111111111111", "4111 1111 1111 1111")


def _personal_values() -> list[str]:
    rng = g.default_rng(189)
    makers: list[Callable[[random.Random], str]] = [g.card, g.pan, g.ext_email, g.mobile, g.aadhaar]
    return [*_CARDS, *(make(rng) for make in makers), "+91 98765 43210", "9876543210"]


def _wrapped(value: str) -> list[str]:
    return [
        value,
        f"DRAFT-{value}",
        f"IDEA-{value}",
        f"DRAFT-{FIXED} {value}",
        f"{FIXED} {value}",
        f"user:{FIXED} {value}",
        f"ref for {value} here",
    ]


@pytest.mark.parametrize("value", _personal_values())
def test_l_audit_nn3_personal_data_is_still_refused_beside_or_inside_an_id(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    log = klog.get_logger("test.l_audit.refused")
    for wrapped in _wrapped(value):
        assert value_patterns(wrapped) != [], wrapped
        with pytest.raises(klog.LogPolicyError):
            log.info("gateway.call", ref_id=wrapped)
        with pytest.raises(klog.LogPolicyError):
            log.info("gateway.batch", ref_ids=[f"DRAFT-{FIXED}", wrapped])
        assert scan_log_line(json.dumps({"event": "gateway.call", "ref_id": wrapped})) != [], wrapped


def test_l_audit_nn3_only_the_exact_shape_is_exempt() -> None:
    """Near misses of the UUID shape are not exempt: they go through the value scan like any other text."""
    from pii.log_rules import _safe_value

    tripped = "10fe3541-75dc-15f7-2993-4465871481aa"  # card-shaped digits across its last three groups
    for exact in (tripped, f"DRAFT-{tripped}", f"IDEA-{tripped}", f"user:{tripped}", tripped.upper()):
        assert _safe_value().match(exact), exact
    for near in (
        "DRAFT-4111 1111 1111 1111",
        "DRAFT-4111-1111-1111-1111",
        "IDEA-4111-1111-1111-1111",
        f"DRAFT-{tripped} ",  # trailing space
        f"draft-{tripped}",  # not our prefix
        f"DRAFT-{tripped[:-2]}AA",  # mixed case is not a canonical UUID
        f"DRAFT-{tripped}-0",
        f"DRAFT-DRAFT-{tripped}",
        f"DRAFT:{tripped}",
    ):
        assert not _safe_value().match(near), near
        assert value_patterns(near) != [], near


def test_l_audit_nn3_prod_drops_personal_data_beside_an_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setenv("APP_ENV", "prod")
    stream = io.StringIO()
    klog.configure("INFO", stream)
    try:
        klog.get_logger("test.l_audit.prod").info(
            "gateway.call", ref_id=f"DRAFT-{FIXED} 4111 1111 1111 1111", idea_uuid=FIXED.upper()
        )
    finally:
        klog.configure("INFO")
    data = json.loads(stream.getvalue().strip())
    assert data["dropped_fields"] == ["ref_id"]
    assert data["idea_uuid"] == FIXED.upper()
