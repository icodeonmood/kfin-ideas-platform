"""BLD-B270, DEC-107: `convo.access.FILE_ROLES` follows `view_review_queue`, so a member who holds only the Ones
Committee role gets the conversation's files on S-08 and adds files (BLD-F062, BLD-F063). The crew still gets no
files there, and never opens a file holding a customer detail. Lane F's fixtures; synthetic people only.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from attachments import files as F
from convo.messages import send
from convo.reads import conversation
from tests import convo_fixtures as fx

NOW = fx.at(20, 10, 30)  # Friday 20 November 2026, IST


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    """The shared `db` fixture, plus clean-up: the people and ideas made here are deleted when the test ends."""
    yield db
    fx.clean(db)


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every inbox post, as lane A's `notify.post` receives it."""
    calls: list[dict[str, Any]] = []

    def fake(conn: Any, kind: str, recipients: list[str], **kw: Any) -> None:
        calls.append({"kind": kind, "to": list(recipients), **kw})

    monkeypatch.setattr("convo.adapters.notify_post", fake)
    return calls


def messages(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in view["entries"] if e["type"] == "message"]


def test_bld_b270_dec_107_a_committee_only_reader_sees_and_adds_the_conversations_files(
    db: Any, told: list[dict[str, Any]]
) -> None:
    """BLD-B270, DEC-107: a committee-only reader sees and adds the conversation's files."""
    kavya = fx.person(db, "Kavya Menon")
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))  # no core_committee
    meghna = fx.person(db, "Meghna Das")
    idea = fx.idea(db, kavya, status="being_built")
    fx.join_crew(db, idea, meghna)
    att = fx.attachment(db, idea, kavya)
    send(
        db, idea["idea_id"], kavya["id"], {"text": "The rejection list.", "file_ids": [att]}, at=fx.at(20, 9)
    )

    # The committee-only member gets the sharer's file on S-08, and the attach control.
    view = conversation(db, idea["idea_id"], rohan["id"], at=NOW)
    [m] = messages(view)
    assert [f["id"] for f in m["files"]] == [att]
    assert view["composer"]["can_attach"] is True
    own = fx.attachment(db, idea, rohan, name="committee-notes.xlsx")
    sent = send(db, idea["idea_id"], rohan["id"], {"file_ids": [own]}, at=fx.at(20, 9, 5))
    assert [f["id"] for f in sent["entry"]["files"]] == [own]

    # The crew reads both messages without their files and cannot attach (BLD-F062, BLD-F063, unchanged).
    crew = conversation(db, idea["idea_id"], meghna["id"], at=NOW)
    assert len(messages(crew)) == 2 and all(e["files"] == [] for e in messages(crew))
    assert crew["composer"]["can_attach"] is False

    # DEC-107, the files route: a file holding a customer detail opens for the Ones Committee, never for the crew.
    # This half pins `attachments.files.get_item` (`GET /api/files/:id`), which decides on `desk.store.READERS`, so
    # it holds with or without BLD-B270's FILE_ROLES; the halves above (the message's files, `can_attach`) pin those.
    detail = fx.attachment(db, idea, kavya, file_state="personal_data_found", name="calls-with-a-name.xlsx")
    db.execute("UPDATE attachments SET state = 'quarantine' WHERE id = %s", (detail,))  # never marked clean
    seen = F.get_item(db, detail, rohan["id"])
    assert seen["customer_detail"] is True and seen["view_url"] == f"/api/files/{detail}/view"
    with pytest.raises(F.FileRefused) as caught:
        F.get_item(db, detail, meghna["id"])
    assert (caught.value.status, caught.value.code) == (404, "not_found")
