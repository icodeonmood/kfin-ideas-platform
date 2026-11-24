"""BLD-A242: the load test drives the 1% Club's Share path (J-SHARE; L-SORT, L-SUBMIT.send) as the browser does,
against a fake app on `httpx.MockTransport` that answers like the real routes (status codes and JSON shapes from
`apps/web/src/app/api/drafts/`, `api/ideas/[id]`, the worker's `submit/send.py` hand-over and `ideapage` view). No
stack, no database, no network: every request goes to the mock, and none of them leaves this process."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from loadtest import __main__ as lt

BASE = "http://web.test"
IDP = "http://idp.test"
DRAFT = "0b6f6b2e-4f51-4c43-9a43-6d3c2f9e0a11"
RUN = "5c1b7c1e-2a7d-4e4f-8f7a-0c4b9b1d2e33"
REF = "IDEA-2026-000123"
VERSION = "1pc-2026-11"
FAST = lt.Waits(scan_timeout=2.0, draft_timeout=2.0, poll=0.01, recover=0.01)


def _sse(*events: str) -> bytes:
    return "".join(f"event: {e}\ndata: {{}}\n\n" for e in events).encode()


class FakeClub:
    """The 1% Club's sign-in, Share path and S-06 as the routes answer them, recording every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []  # (method, host, path)
        self.requests: list[httpx.Request] = []
        self.accepted: set[str] = set()
        self.drafts = 0
        self.submitted_at: float | None = None
        self.polls = 0
        # What each test changes
        self.sorted_after_s = 0.0  # S-06 says Checking until this long after Submit
        self.end_state = "with_review_desk"  # the state it then says
        self.stream: bytes | None = _sse("run", "hidden", "part", "part", "receipt", "done")
        self.hang_stream = False
        self.sorting_complete = True
        self.problems: list[dict[str, Any]] = []
        self.draft_reads_running = 0  # GET /api/drafts/{id} says a run is building this many times

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def paths(self) -> list[str]:
        return [f"{m} {p}" for m, h, p in self.calls if h == "web.test"]

    def body(self, method: str, path: str) -> Any:
        r = next(q for q in self.requests if q.method == method and q.url.path == path)
        return json.loads(r.content)

    def header(self, method: str, path: str, name: str) -> str | None:
        r = next(q for q in self.requests if q.method == method and q.url.path == path)
        return r.headers.get(name)

    async def _hanging(self) -> AsyncIterator[bytes]:
        yield b"event: run\ndata: {}\n\n"
        await asyncio.sleep(30)

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, host, path = request.method, request.url.host, request.url.path
        self.calls.append((method, host, path))
        self.requests.append(request)
        if host == "idp.test":
            return httpx.Response(302, headers={"location": f"{BASE}/auth/callback?code=c&state=s"})
        if path == "/auth/login":
            return httpx.Response(302, headers={"location": f"{IDP}/authorize?client_id=web"})
        if path == "/auth/callback":
            token = f"tok{len(self.calls)}"
            return httpx.Response(
                307,
                headers={
                    "location": "/",
                    "set-cookie": f"kfin_session={token}; Path=/; HttpOnly; Secure; SameSite=Lax",
                },
            )
        token = (request.headers.get("cookie") or "").removeprefix("kfin_session=")
        if not token:
            return httpx.Response(401, json={"error": "sign_in_required"})
        if path == "/" and token not in self.accepted:
            return httpx.Response(307, headers={"location": "/privacy-notice?next=%2F"})
        if path == "/":
            return httpx.Response(307, headers={"location": "/home"})
        if path == "/api/me":
            return httpx.Response(200, json={"privacy_notice": {"version": "0.2", "accepted": False}})
        if path == "/api/me/privacy-notice":
            self.accepted.add(token)
            return httpx.Response(200, json={"accepted": True, "version": "0.2"})
        if not path.startswith("/api/"):
            return httpx.Response(200, text="<!doctype html><title>1% Club</title>")
        return self.api(request, method, path)

    def _draft(self, running: bool = False) -> dict[str, Any]:
        return {
            "id": DRAFT, "owner_id": "u1", "channel": "web", "messages": [], "parts": {}, "hidden": [],
            "files": [], "step": "tell", "ready": not running, "min_chars": 25, "char_count": 300,
            "archived": False, "run": {"id": RUN, "state": "running" if running else "done"},
        }  # fmt: skip

    def _sorting(self, confirmed: bool) -> dict[str, Any]:
        area = "Operations" if self.sorting_complete else None
        return {
            "affects": {"value": ["KFin teams"], "source": "suggested", "why": None, "why_line": None},
            "kind": {"value": "problem", "source": "suggested", "why": None, "why_line": None},
            "area": {"value": area, "source": "suggested", "why": None, "why_line": None},
            "brings": {"value": ["saves_time"], "source": "suggested", "why": None, "why_line": None},
            "confirmed": confirmed, "complete": self.sorting_complete or confirmed, "note": None,
        }  # fmt: skip

    def api(self, request: httpx.Request, method: str, path: str) -> httpx.Response:
        d = f"/api/drafts/{DRAFT}"
        if (method, path) == ("POST", "/api/drafts"):
            self.drafts += 1
            return httpx.Response(201, json={"draft": self._draft(running=True), "run_id": RUN})
        if (method, path) == ("GET", f"{d}/stream"):
            sse = {"content-type": "text/event-stream"}
            if self.hang_stream:
                return httpx.Response(200, headers=sse, content=self._hanging())
            return httpx.Response(200, headers=sse, content=self.stream)
        if (method, path) == ("GET", d):
            running = self.draft_reads_running > 0
            self.draft_reads_running -= 1
            return httpx.Response(200, json=self._draft(running=running))
        if (method, path) == ("GET", f"{d}/sorting"):
            return httpx.Response(200, json=self._sorting(confirmed=False))
        if (method, path) == ("PATCH", f"{d}/sorting"):
            body = json.loads(request.content)
            if not self.sorting_complete and not body.get("area"):
                return httpx.Response(422, json={"error": {"code": "sorting_incomplete", "message": "x"}})
            return httpx.Response(200, json=self._sorting(confirmed=True))
        if (method, path) == ("GET", "/api/config"):
            return httpx.Response(200, json={
                "sorting": {"affects": ["Investors", "KFin teams"], "areas": ["Investor service", "Operations"],
                            "brings": ["not_sure", "saves_time"], "helpers": [],
                            "controls": {"kind": {"options": [{"value": "problem", "label": "A problem to fix"}]}}},
                "declaration": {"version": VERSION}, "flags": {},
            })  # fmt: skip
        if (method, path) == ("GET", "/api/config/uploads"):
            return httpx.Response(200, json={"limit_mb": 10})
        if (method, path) == ("GET", f"/api/ideas/{DRAFT}/similar"):
            return httpx.Response(200, json=[])
        if (method, path) == ("GET", f"{d}/merge-request"):
            return httpx.Response(200, json={"state": "none", "after": None})
        if (method, path) == ("GET", f"{d}/send"):
            return httpx.Response(200, json={
                "id": DRAFT, "rows": [], "declaration": {"version": VERSION, "text": "x"}, "button": "Submit",
                "ready": not self.problems, "problems": self.problems,
            })  # fmt: skip
        if method == "PATCH" and path.startswith(f"{d}/parts/"):
            self.problems = []
            return httpx.Response(200, json={"run_id": None, "draft": self._draft()})
        if (method, path) == ("POST", f"{d}/submit"):
            self.submitted_at = time.monotonic()
            return httpx.Response(201, json={
                "idea_id": REF, "id": DRAFT, "ref": REF, "status": "checking", "pill": {}, "title": "",
                "stages": [], "next": {"to": f"/ideas/{REF}?from=share", "replace": True, "state": "just_shared"},
            })  # fmt: skip
        if (method, path) == ("GET", f"/api/ideas/{REF}"):
            self.polls += 1
            assert self.submitted_at is not None
            done = time.monotonic() - self.submitted_at >= self.sorted_after_s
            status = self.end_state if done else "checking"
            return httpx.Response(200, json={
                "view": "sharer", "screen": "S-06", "idea": {"id": DRAFT, "ref": REF, "status": status,
                                                              "sharer": {"id": "u1"}}, "page": {},
            })  # fmt: skip
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "x"}})


async def _signed_in(app: FakeClub, stats: lt.Stats, client: httpx.AsyncClient) -> lt.Session:
    s = lt.Session(client, BASE, stats)
    assert await s.sign_in("SYN-00018")
    app.calls.clear()
    app.requests.clear()
    return s


def _share(app: FakeClub, waits: lt.Waits = FAST) -> lt.Stats:
    stats = lt.Stats()

    async def go() -> None:
        async with httpx.AsyncClient(transport=app.transport) as client:
            s = await _signed_in(app, stats, client)
            await lt.submit_one(s, random.Random(7), stats, waits)

    asyncio.run(go())
    return stats


def test_a242_share_makes_the_share_screens_calls_in_their_order() -> None:
    app = FakeClub()
    stats = _share(app)
    d = f"/api/drafts/{DRAFT}"
    seen = app.paths()
    head = ["GET /share", "POST /api/drafts", f"GET /share/{DRAFT}", f"GET {d}/stream", f"GET {d}",
            f"GET /share/{DRAFT}/check"]  # fmt: skip
    assert seen[:6] == head
    assert set(seen[6:9]) == {f"GET {d}", f"GET {d}/sorting", "GET /api/config/uploads"}
    assert set(seen[9:11]) == {f"GET /api/ideas/{DRAFT}/similar", f"GET {d}/merge-request"}
    assert seen[11:14] == [f"PATCH {d}/sorting", f"GET {d}/send", f"POST {d}/submit"]
    after = seen[14:]
    assert f"GET /ideas/{REF}" in after and after.count(f"GET /api/ideas/{REF}") >= 1
    assert set(after) == {f"GET /ideas/{REF}", f"GET /api/ideas/{REF}"}
    # nothing but the fake app and its IdP was ever asked, and only the Share path's own routes
    assert {h for _, h, _ in app.calls} == {"web.test"}
    assert not any("/api/submissions" in p for p in seen)
    assert stats.ops["submission"] == {"attempted": 1, "failed": 0}
    assert stats.summary()["error_rate"] == 0.0


def test_a242_share_sends_what_the_browser_sends() -> None:
    app = FakeClub()
    _share(app)
    d = f"/api/drafts/{DRAFT}"
    made = app.body("POST", "/api/drafts")
    assert made["channel"] == "web" and made["via"] == "typed"
    assert made["text"].startswith("Load test (synthetic): ")  # the word list, never real words
    assert app.header("POST", "/api/drafts", "idempotency-key")
    assert app.header("POST", "/api/drafts", "x-device-id")
    stream = next(r for r in app.requests if r.url.path == f"{d}/stream")
    assert parse_qs(stream.url.query.decode())["run"] == [RUN]
    assert app.body("PATCH", f"{d}/sorting") == {"confirm": True}  # "Looks right"
    assert app.body("POST", f"{d}/submit") == {"declaration_version": VERSION}
    key = app.header("POST", f"{d}/submit", "idempotency-key") or ""
    assert key.startswith(f"s05:{DRAFT}:")
    # every call after sign-in carries the person's session, as the browser's cookie jar does
    assert all((r.headers.get("cookie") or "").startswith("kfin_session=") for r in app.requests)


def test_a242_send_to_sorted_is_timed_from_the_submit_request() -> None:
    app = FakeClub()
    app.sorted_after_s = 0.2
    stats = _share(app)
    (scan,) = stats.timings["scan"]
    assert 0.2 <= scan < 1.0
    assert app.polls >= 2  # read again while it said Checking
    assert stats.ops["submission"] == {"attempted": 1, "failed": 0}
    assert "draft" in stats.timings and stats.timings["draft"][0] < scan + 1.0


def test_a242_a_share_still_checking_at_the_timeout_fails_and_its_time_counts() -> None:
    app = FakeClub()
    app.sorted_after_s = 60.0
    stats = _share(app, lt.Waits(scan_timeout=0.15, draft_timeout=2.0, poll=0.01, recover=0.01))
    assert stats.timings["scan"] == [0.15]
    assert stats.ops["submission"] == {"attempted": 1, "failed": 1}
    assert stats.errors["scan_timeout"] == 1
    out = stats.summary()
    assert out["scan"]["p95_s"] == 0.15 and out["error_rate"] > 0


def test_a242_a_share_that_ends_in_another_state_fails_with_its_time() -> None:
    app = FakeClub()
    app.end_state = "withdrawn"
    stats = _share(app)
    assert len(stats.timings["scan"]) == 1
    assert stats.ops["submission"]["failed"] == 1 and stats.errors["scan_withdrawn"] == 1


def test_a242_needs_you_is_the_review_desk_too() -> None:
    app = FakeClub()
    app.end_state = "needs_you"
    assert _share(app).ops["submission"]["failed"] == 0


def test_a242_a_draft_that_never_builds_fails_before_submit_with_no_scan_time() -> None:
    app = FakeClub()
    app.hang_stream = True
    stats = _share(app, lt.Waits(scan_timeout=2.0, draft_timeout=0.1, poll=0.01, recover=0.01))
    assert stats.errors["draft_timeout"] == 1 and "scan" not in stats.timings
    assert stats.ops["submission"] == {"attempted": 1, "failed": 1}
    assert not any("/submit" in p for p in app.paths())


def test_a242_a_lost_stream_reads_the_draft_until_nothing_builds() -> None:
    app = FakeClub()
    app.stream = _sse("run", "part", "end")  # the server closed before `done`
    app.draft_reads_running = 2
    stats = _share(app)
    assert stats.errors["draft_stream_lost"] == 1
    assert app.paths().count(f"GET /api/drafts/{DRAFT}") >= 3 + 1  # three reads to settle, one on Check it
    assert stats.ops["submission"]["failed"] == 0


def test_a242_a_refused_stream_is_lost_too_and_the_draft_is_read() -> None:
    app = FakeClub()
    orig = app.api

    def busy(request: httpx.Request, method: str, path: str) -> httpx.Response:
        if path.endswith("/stream"):
            return httpx.Response(503, json={"error": "unavailable"})
        return orig(request, method, path)

    app.api = busy  # type: ignore[method-assign]
    stats = _share(app)
    assert stats.errors == {"stream": 1, "draft_stream_http_503": 1}
    assert stats.ops["submission"]["failed"] == 0


def test_a242_an_empty_sorting_field_takes_the_first_option_then_confirms() -> None:
    app = FakeClub()
    app.sorting_complete = False
    stats = _share(app)
    assert "GET /api/config" in app.paths()
    assert app.body("PATCH", f"/api/drafts/{DRAFT}/sorting") == {"area": "Investor service", "confirm": True}
    assert stats.notes == {"sorting_picked": 1} and stats.ops["submission"]["failed"] == 0


def test_a242_a_missing_title_is_typed_before_submit() -> None:
    app = FakeClub()
    app.problems = [{"code": "not_ready", "message": "x", "field": "title"}]
    stats = _share(app)
    d = f"/api/drafts/{DRAFT}"
    seen = app.paths()
    assert seen.index(f"PATCH {d}/parts/title") < seen.index(f"POST {d}/submit")
    assert isinstance(app.body("PATCH", f"{d}/parts/title")["value"], str)
    assert stats.notes == {"typed_title": 1} and stats.ops["submission"]["failed"] == 0


def test_a242_a_refused_submit_fails_with_its_code_and_no_scan_time() -> None:
    app = FakeClub()
    orig = app.api

    def refuse(request: httpx.Request, method: str, path: str) -> httpx.Response:
        if path.endswith("/submit"):
            return httpx.Response(422, json={"error": {"code": "sorting_unconfirmed", "message": "x"}})
        return orig(request, method, path)

    app.api = refuse  # type: ignore[method-assign]
    stats = _share(app)
    assert stats.errors == {"submit_422_sorting_unconfirmed": 1} and "scan" not in stats.timings


def test_a242_pages_are_the_1pc_clubs_own() -> None:
    assert lt.PAGES == ("/home", "/wall", "/inbox", "/my-ideas")


def test_a242_report_keeps_the_keys_gonogo_reads_and_carries_no_words(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = FakeClub()
    argv = ["--base-url", BASE, "--scale", "0.0003", "--submissions-per-hour", "36000", "--authors", "2",
            "--people", "3", "--poll", "0.01", "--scan-timeout", "2", "--draft-timeout", "2",
            "--out", str(tmp_path)]  # fmt: skip
    assert lt.main(argv, transport=app.transport) == 0
    (path,) = tmp_path.glob("report-*.json")  # the name gonogo looks for
    report = json.loads(path.read_text())
    # what gonogo's load_test row reads
    assert {"scale", "submissions_per_hour", "sign_ins", "base_url"} <= set(report["settings"])
    assert isinstance(report["scan"]["p95_s"], float) and isinstance(report["error_rate"], float)
    assert set(report["pass"]) == {"scan_p95", "page_p95", "error_rate", "launch_rate"}
    assert all(v is True for v in report["pass"].values())
    assert report["settings"]["flow"] == "share" and report["settings"]["scale"] == 0.0003
    assert {"requests", "errors", "operations", "notes", "targets", "page", "sign_in", "draft"} <= set(report)
    assert report["operations"]["submission"]["attempted"] == app.drafts >= 1
    # numbers, IDs and codes only: no synthetic words, no people, in the report or on screen
    printed = capsys.readouterr().out
    for text in (path.read_text(), printed):
        assert "synthetic" not in text and "SYN-" not in text and "Load test" not in text
        assert not any(w in text for w in lt.WORDS if len(w) > 3 and w != "report")  # report-*.json is a name


@pytest.mark.parametrize(
    "url",
    ["http://localhost:3000", "http://127.0.0.1:3000/", "http://[::1]:3000", "http://0.0.0.0:3000"],
)
def test_a242_never_the_demo_a_local_3000_is_refused_without_not_the_demo(
    url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """BLD-A242 (lane E's review): no default target, and this machine's :3000, the live demo on the developer Mac, is
    refused unless --not-the-demo says it is a throwaway stack (a CI runner)."""
    with pytest.raises(SystemExit) as no_url:
        lt.parse([])
    assert no_url.value.code == 2
    assert "--base-url" in capsys.readouterr().err
    with pytest.raises(SystemExit) as refused:
        lt.parse(["--base-url", url])
    assert refused.value.code == 2
    assert "never runs against the demo" in capsys.readouterr().err
    assert lt.parse(["--base-url", url, "--not-the-demo"]).base_url == url
    assert lt.parse(["--base-url", "http://loadtest-stack.internal:3000"]).not_the_demo is False
    assert lt.parse(["--base-url", "http://localhost:3001"]).base_url == "http://localhost:3001"
