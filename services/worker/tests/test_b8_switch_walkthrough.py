"""Kill-switch walkthrough (AT-B8-07 rehearsal, §7.6), against the running stack: each switch is flipped through
the Admin API by someone allowed to, behaves as §7.6 says where a person would see it, and is switched back on.
`ai.all` is checked by its banner here; its effect on scans, and the agent, matching and email switches (which
show only on the screens they affect), are covered by the B4, B5 and B6 tests."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from core.db import connect
from tests.test_b3_submissions_api import full_canvas
from tests.web import Browser, people

pytestmark = pytest.mark.stack


@pytest.fixture
def dev_db() -> Iterator[Any]:
    with connect(autocommit=True) as conn:
        yield conn


@contextmanager
def off(b: Browser, name: str) -> Iterator[None]:
    """Switch `name` off, then back to the state it was in before (on, normally)."""
    before = {x["name"]: x["state"] for x in b.get("/api/admin/kill-switches").json()["switches"]}[name]

    def flip(state: str) -> None:
        r = b.request(
            "PUT",
            "/api/admin/kill-switches",
            json={"name": name, "state": state, "reason": "Switch walkthrough"},
        )
        assert r.status_code == 200, (name, state, r.status_code)

    flip("off")
    try:
        yield
    finally:
        flip(before)
        time.sleep(CACHE_S)  # let every process see it again before the next switch


CACHE_S = 10.5  # §7.6: switches are read on every request through a 10-second cache


def soon(check: Callable[[], bool]) -> bool:
    """True once `check` holds, within the switch cache's 10 seconds."""
    deadline = time.monotonic() + CACHE_S + 2
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.5)
    return False


def test_every_switch_behaves_as_section_7_6_says(dev_db: Any) -> None:
    with people(dev_db) as make:
        admin = make((("admin", None),)).browser()
        infosec = make((("infosec", None),)).browser()
        person = make().browser()
        draft = person.post("/api/submissions", json={"mode": "full", "canvas": full_canvas()}).json()["id"]

        with off(admin, "submissions"):  # read-only mode: browse and track, not submit or edit
            # Probe with an autosave of the existing draft, so waiting for the cache creates nothing.
            assert soon(
                lambda: (
                    person.request("PUT", f"/api/submissions/{draft}", json={"canvas": {}}).status_code == 503
                )
            )
            assert person.post("/api/submissions", json={"mode": "quick"}).status_code == 503
            assert person.get("/api/me/ideas").status_code == 200
            assert "Sharing and editing ideas is paused" in person.get("/my-ideas").text

        with off(admin, "attachments.upload"):  # upload refused; nothing else changes
            files = {"file": ("notes.txt", b"synthetic notes", "text/plain")}
            assert soon(
                lambda: person.post(f"/api/submissions/{draft}/attachments", files=files).status_code == 503
            )
            assert person.post("/api/submissions", json={"mode": "quick"}).status_code == 201

        with off(infosec, "attachments.open"):  # nobody can open or download a file
            assert soon(
                lambda: person.get("/api/attachments/00000000-0000-0000-0000-000000000000").status_code == 503
            )

        with off(admin, "wall.public"):  # the wall is hidden
            assert soon(lambda: person.get("/api/wall").status_code == 503)
            assert soon(
                lambda: person.get("/api/ideas").json() == {"ideas": []}
            )  # the worker has its own cache
            assert soon(lambda: "The ideas wall is resting for now" in person.get("/wall").text)

        with off(admin, "ai.all"):  # no model calls; scans queue (B4 tests); everyone is told
            assert soon(lambda: "The assistant is taking a break" in person.get("/").text)
