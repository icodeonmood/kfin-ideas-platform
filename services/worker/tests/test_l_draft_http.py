"""L-DRAFT over HTTP against the running stack (BLD-C071, BLD-C075): J-SHARE steps 3 to 6 and J-RESUME steps 1 to 4
through the web app and the worker. A draft is started on a pause in typing, its parts arrive on the stream in the
contract's order, a part changed by hand is pinned, it resumes with "where and when", and it is archived and
restored. Owner only. Synthetic people and text."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from core.db import connect
from tests.web import WEB, people

pytestmark = pytest.mark.stack

LAPTOP = {"X-Device": "laptop", "X-Device-Id": "laptop-http-0001"}
PHONE = {"X-Device": "phone", "X-Device-Id": "phone-http-0002"}
WORDS = (
    'When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, '
    "so they call the branch. Our branch takes about 40 calls a day like this."
)


@pytest.fixture
def me() -> Iterator[Any]:
    """Synthetic people of their own; their drafts and the drafts' vault entries go with them afterwards."""
    with connect(autocommit=True) as conn, people(conn) as make:
        codes: list[str] = []

        def person(*args: Any, **kw: Any) -> Any:
            made = make(*args, **kw)
            codes.append(made.contributor_code)
            return made

        try:
            yield person(), person
        finally:
            gone = [
                f"DRAFT-{r['id']}"
                for r in conn.execute(
                    "DELETE FROM ideas WHERE contributor_code = ANY(%s) RETURNING id", (codes,)
                ).fetchall()
            ]
            for table in ("pseudonym_vault", "vault_counters", "llm_calls"):
                column = "ref_id" if table == "llm_calls" else "scope_id"
                conn.execute(f"DELETE FROM {table} WHERE {column} = ANY(%s)", (gone,))  # noqa: S608


def _settled(b: Any, draft_id: str, timeout: float = 45.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        r = b.get(f"/api/drafts/{draft_id}", headers=LAPTOP)
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        if not body["run"] or body["run"]["state"] != "running":
            return body
        assert time.monotonic() < deadline, body["run"]
        time.sleep(0.3)


def _events(b: Any, draft_id: str, run_id: str) -> list[tuple[str, str]]:
    """The stream for one run, read until `done` (A-API.draft-stream)."""
    out: list[tuple[str, str]] = []
    cookie = "; ".join(f"{k}={v}" for k, v in b.cookies.items())
    with httpx.stream(
        "GET",
        f"{WEB}/api/drafts/{draft_id}/stream?run={run_id}",
        headers={"Cookie": cookie, **LAPTOP},
        timeout=60,
    ) as r:
        assert r.status_code == 200
        event = ""
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                out.append((event, line[len("data: ") :]))
                if event == "done":
                    break
    return out


def test_j_share_3_to_6_a_draft_starts_streams_and_pins(me: Any) -> None:
    person, make = me
    b = person.browser()
    created = b.post("/api/drafts", json={"channel": "web", "text": WORDS},
                     headers={**LAPTOP, "Idempotency-Key": "http-create-0001"})  # fmt: skip
    assert created.status_code == 201, created.text
    draft = created.json()["draft"]
    run_id = created.json()["run_id"]
    again = b.post("/api/drafts", json={"channel": "web", "text": WORDS},
                   headers={**LAPTOP, "Idempotency-Key": "http-create-0001"})  # fmt: skip
    assert again.json()["draft"]["id"] == draft["id"]  # A-API.conventions/3
    assert draft["messages"][0]["text"] == WORDS and draft["min_chars"] == 30
    assert run_id

    events = _events(b, draft["id"], run_id)
    names = [e for e, _ in events]
    assert names[:2] == ["run", "hidden"] and names[-2:] == ["receipt", "done"]
    assert names.count("part") == len(names) - 4 >= 1

    settled = _settled(b, draft["id"])
    assert settled["char_count"] == len(WORDS)
    pin = b.request("PATCH", f"/api/drafts/{draft['id']}/parts/title", headers=LAPTOP,
                    json={"value": "Rejection SMS codes confuse investors"})  # fmt: skip
    assert pin.status_code == 200, pin.text
    assert pin.json()["draft"]["parts"]["title"]["state"] == "pinned"
    bad = b.request(
        "PATCH", f"/api/drafts/{draft['id']}/parts/title", headers=LAPTOP, json={"value": "x" * 71}
    )
    assert bad.status_code == 422
    assert bad.json()["error"] == {"code": "too_long", "message": "That's too long. Please make it shorter.",
                                   "field": "value"}  # fmt: skip
    sent = b.post(f"/api/drafts/{draft['id']}/messages", headers={**LAPTOP, "Idempotency-Key": "http-msg-0001"},
                  json={"text": "Distributors ask the same thing every week.", "via": "typed"})  # fmt: skip
    assert sent.status_code == 202, sent.text
    assert sent.json()["message"]["text"] == "Distributors ask the same thing every week."
    step = b.request("PATCH", f"/api/drafts/{draft['id']}", headers=LAPTOP, json={"step": "check:1"})
    assert step.status_code == 200 and step.json()["saved_labels"]["status"].startswith("Saved at ")

    # Someone else's draft looks exactly like a missing one.
    other = make().browser().get(f"/api/drafts/{draft['id']}", headers=LAPTOP)
    assert other.status_code == 404 and other.json()["error"]["code"] == "not_found"


def test_j_resume_1_to_4_resume_on_another_device_then_archive_and_restore(me: Any) -> None:
    person, _ = me
    b = person.browser()
    created = b.post("/api/drafts", json={"channel": "web", "text": WORDS}, headers=PHONE)
    draft_id = created.json()["draft"]["id"]
    _settled(b, draft_id)
    listed = b.get("/api/drafts?recent=1", headers=LAPTOP).json()
    row = next(i for i in listed["items"] if i["id"] == draft_id)
    assert row["saved_labels"]["sidebar"].endswith("on your phone")  # "Friday, on your phone"
    resumed = b.get(f"/api/drafts/{draft_id}?open=1", headers=LAPTOP).json()
    assert resumed["saved_labels"]["resume"].startswith("Last saved on your phone, ")
    assert resumed["editor"] == {"device": "laptop", "this_device": True}
    late = b.post(
        f"/api/drafts/{draft_id}/messages", headers=PHONE, json={"text": "One more detail.", "via": "typed"}
    )
    assert late.status_code == 409
    assert late.json()["error"]["message"] == "This draft is open on your laptop. Carry on here?"

    assert b.request("DELETE", f"/api/drafts/{draft_id}", headers=LAPTOP).status_code == 204
    assert b.get(f"/api/drafts/{draft_id}", headers=LAPTOP).json()["archived"] is True
    archived = b.get("/api/drafts?recent=1&archived=1", headers=LAPTOP).json()["items"]
    assert draft_id in [i["id"] for i in archived]
    restored = b.post(f"/api/drafts/{draft_id}/restore", headers=LAPTOP)
    assert restored.status_code == 200 and restored.json()["archived"] is False
