"""AT-B1-01: `make up` starts every service and each health endpoint returns 200 within 120 seconds.

`make up` itself runs `python -m core.health --timeout 120`; this test re-checks the running stack and fails
if any service is missing. The cold-start timing is recorded in docs/BUILD_LOG.md (BLD-024).
"""

import pytest

from core.health import checks, wait_healthy

pytestmark = pytest.mark.stack

EXPECTED = {"postgres", "s3", "clamav", "mock-oidc", "mailpit", "worker", "web"}


def test_every_service_is_checked() -> None:
    assert set(checks()) == EXPECTED


def test_every_health_endpoint_answers_within_120_seconds() -> None:
    ready = wait_healthy(timeout=120)
    missing = sorted(name for name, secs in ready.items() if secs is None)
    assert missing == [], f"not healthy within 120 s: {missing}"
