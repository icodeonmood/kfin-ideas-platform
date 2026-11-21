"""BLD-B274 (DEC-124, BLD-C216): a file added for the conversation, the "+" in S-08's box (`attachments.purpose =
'conversation'`), is never one of the idea's own files on the review side, sent on an entry or not. Each test pins one
reader against the database: the reviewer's page (the Attachments card, S-R2.left/2, and the Attached part,
S-R2.left/3), the committee's read of the same page, the Listen script (L-LISTEN/2), a merged contribution
(L-MERGE.effects/3), the suggestions' "Attached is filled" (L-QUESTIONS.ask/3), the files a sharer may put on an
answer (L-QUESTIONS.answer, `_link_files`), an answer's files for the desk and for the sharer, and the two pre-pack
readers lane E gave this branch (`review.view.item_view`, `committee.qualify._evidence`).

Every idea here carries three checked files: (a) its own (`purpose = 'idea'`); (b) one the review desk added for the
conversation and has not sent; (c) one the sharer added for the conversation and sent on a message through lane F's
composer (`convo.messages.send`), so it sits on a `conversation_entries` row. Synthetic people and files only
(non-negotiable 11); lane B's and lane F's fixtures, cleaned up after each test."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from attachments import files as F
from committee import qualify
from convo.messages import send
from core.db import Conn
from desk import asking, merging, reads
from desk import store as desk_store
from desk.store import Refused
from review.view import item_view
from tests import convo_fixtures as fx
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13)  # Monday 16 November 2026, 1 pm IST
OWN, DESK_NOTE, SENT_NOTE, ON_ENTRY = (
    "branch-call-log-nov.xlsx",
    "desk-notes-for-the-chat.xlsx",
    "sms-sent-in-the-chat.xlsx",
    "sms-moved-into-the-chat.xlsx",
)
QS: list[dict[str, Any]] = [
    {"part": "evidence", "text": "Can you add the call log for the whole of November?"}
]


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> f.FakeNotify:
    """Lane A's `notify` replaced: the desk's posts through the fake, the conversation's through a no-op (BLD-B270).
    `convo.adapters` was loaded with the real `notify` when this module imported `convo.messages`, so its name is
    patched rather than left to read the fake from sys.modules."""
    monkeypatch.setattr("convo.adapters.notify_post", lambda conn, kind, recipients, **kw: None)
    return f.install_fake_notify(monkeypatch)


@pytest.fixture
def cast(db: Conn, repo: Path, told: f.FakeNotify) -> dict[str, Any]:
    _ = told
    kavya = f.person(db, "Kavya Menon")
    return {
        "kavya": kavya, "ravi": f.person(db, "Ravi Nair"),
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya),
    }  # fmt: skip


def _for_the_conversation(db: Conn, att: str) -> str:
    db.execute("UPDATE attachments SET purpose = 'conversation' WHERE id = %s", (att,))
    return att


def three_files(
    db: Conn, idea: dict[str, Any], sharer: dict[str, str], desk: dict[str, str]
) -> dict[str, str]:
    """(a) the idea's own; (b) the desk's, for the conversation, not sent; (c) the sharer's, sent on a message."""
    own = fx.attachment(db, idea, sharer, name=OWN)
    unsent = _for_the_conversation(db, fx.attachment(db, idea, desk, name=DESK_NOTE))
    sent = _for_the_conversation(db, fx.attachment(db, idea, sharer, name=SENT_NOTE))
    send(db, idea["idea_id"], sharer["id"], {"file_ids": [sent]}, at=f.at(15, 10))
    on = db.execute("SELECT conversation_entry_id FROM attachments WHERE id = %s", (sent,)).fetchone()
    assert on is not None and on["conversation_entry_id"] is not None  # on lane F's entry
    return {"a": own, "b": unsent, "c": sent}


def _page_files(page: dict[str, Any]) -> list[str]:
    return [a["id"] for a in page["artefacts"] if a["kind"] == "file"]


def _part(parts: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(p for p in parts if p["part"] == name)


# ---- desk.store.IDEA_OWN is lane C's text ----------------------------------------------------------------------
def test_BLD_B274_desk_idea_own_is_lane_c_text_in_both_forms() -> None:
    """The desk's copy of the condition (desk.store cannot import `attachments.files`, which imports it) is lane C's,
    word for word, and the `a.` form is the same condition on a table named `a`."""
    on_a = F.IDEA_OWN.replace("purpose", "a.purpose").replace(
        "conversation_entry_id", "a.conversation_entry_id"
    )
    assert desk_store.IDEA_OWN == F.IDEA_OWN
    assert on_a == desk_store.IDEA_OWN_A


# ---- step 2: the one reader of the idea's checked files --------------------------------------------------------
def test_S_R2_left_2_S_R2_left_3_BLD_B274_desk_page_leaves_out_conversation_files(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The Attachments card and the Attached part list only the idea's own file, for the review desk and for the
    Ones Committee reading the same page."""
    files = three_files(db, cast["idea"], cast["kavya"], cast["meera"])
    for who in ("meera", "rohan"):
        page = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast[who]["id"], NOW)
        assert _page_files(page) == [files["a"]], who
        assert _part(page["parts"], "evidence")["text"] == f"One file: {OWN}.", who


def test_L_LISTEN_2_BLD_B274_listen_script_names_only_the_ideas_own_file(
    db: Conn, cast: dict[str, Any]
) -> None:
    three_files(db, cast["idea"], cast["kavya"], cast["meera"])
    script = reads.listen_script(db, cast["idea"]["idea_id"], cast["meera"]["id"])
    said = " ".join(p["text"] for p in script["parts"])
    assert _part(script["parts"], "evidence")["text"] == f"One file: {OWN}."
    assert DESK_NOTE not in said and SENT_NOTE not in said


def test_L_MERGE_effects_3_BLD_B274_a_merged_contribution_lists_only_its_own_file(
    db: Conn, cast: dict[str, Any]
) -> None:
    ravis = f.idea(db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9))
    files = three_files(db, ravis, cast["ravi"], cast["meera"])
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": ravis["idea_id"], "lead": "this",
                        "note": "You both found the same R07 calls."}, f.at(16, 12))  # fmt: skip
    page = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    [ravi] = page["contributions"]
    assert [x["id"] for x in ravi["files"]] == [files["a"]]
    assert _part(ravi["parts"], "evidence")["text"] == f"One file: {OWN}."
    assert _page_files(page) == []  # the lead has no file of its own


# ---- step 5: the suggestions' "Attached is filled" ---------------------------------------------------------------
def test_L_QUESTIONS_ask_3_BLD_B274_a_conversation_file_alone_leaves_attached_empty(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea = cast["idea"]
    _for_the_conversation(db, fx.attachment(db, idea, cast["meera"], name=DESK_NOTE))
    assert asking._filled(db, idea)["evidence"] is False
    fx.attachment(db, idea, cast["kavya"], name=OWN)
    assert asking._filled(db, idea)["evidence"] is True


# ---- step 6: only the idea's own files go on an answer -----------------------------------------------------------
def test_L_QUESTIONS_answer_BLD_B274_a_conversation_file_cannot_be_put_on_an_answer(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The desk's unsent conversation file (b) and the sharer's sent one (c) are refused like a file that isn't the
    idea's: 422 `file_not_found`, and neither is moved; the idea's own file (a) is still kept."""
    files = three_files(db, cast["idea"], cast["kavya"], cast["meera"])
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"questions": QS, "time_to_answer": "3d"}, f.at(16, 9))  # fmt: skip
    q, kavya = sent["questions"][0]["id"], cast["kavya"]["id"]
    for which in ("b", "c"):
        with pytest.raises(Refused) as refused:
            asking.save_answer(db, q, kavya, "The log is attached.", [files[which]], f.at(16, 10))
        got = refused.value
        assert (got.status, got.code, got.field) == (422, "file_not_found", "file_ids"), which
        assert got.message == asking.FILE_CANT_BE_ADDED, which
    on_answers = db.execute(
        "SELECT id FROM attachments WHERE id = ANY(%s) AND answer_id IS NOT NULL", ([files["b"], files["c"]],)
    ).fetchall()
    assert on_answers == []
    saved = asking.save_answer(db, q, kavya, "The log is attached.", [files["a"]], f.at(16, 10))
    assert [x["id"] for x in saved["files"]] == [files["a"]]


# ---- steps 3 and 4: an answer's files, for the desk and for the sharer ---------------------------------------------
def test_S_R2_left_3_S_R3_BLD_B274_a_conversation_file_on_an_answer_row_stays_out_for_desk_and_sharer(
    db: Conn, cast: dict[str, Any]
) -> None:
    """A conversation file put on an answer row in SQL (a row the routes never write once `_link_files` holds) is
    still left out of the answer's files: the desk's (`reads._questions`) and the sharer's (`asking._files`)."""
    files = three_files(db, cast["idea"], cast["kavya"], cast["meera"])
    idea, kavya = cast["idea"], cast["kavya"]["id"]
    sent = asking.send_set(db, idea["idea_id"], cast["meera"]["id"], {"questions": QS, "time_to_answer": "3d"},
                           f.at(16, 9))  # fmt: skip
    q = sent["questions"][0]["id"]
    saved = asking.save_answer(db, q, kavya, "The log is attached.", [files["a"]], f.at(16, 10))
    db.execute(
        "UPDATE attachments SET answer_id = %s WHERE id = ANY(%s)", (saved["id"], [files["b"], files["c"]])
    )
    asking.send_answers(db, sent["id"], kavya, f.at(16, 11))
    # the desk: the answer's files under its question, and the Attachments card (step 2)
    page = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], NOW)
    [question] = _part(page["parts"], "evidence")["questions"]
    assert [x["id"] for x in question["answer"]["files"]] == [files["a"]]
    assert _page_files(page) == [files["a"]]
    # the sharer: S-R3's set and the idea page's answers
    mine = asking.open_set_for_sharer(db, idea["idea_id"], kavya, NOW)
    assert mine is not None
    assert [x["id"] for x in mine["questions"][0]["answer"]["files"]] == [files["a"]]
    assert [x["id"] for x in asking.answers_by_part(db, idea["id"])["evidence"][0]["files"]] == [files["a"]]


# ---- step 9: the two pre-pack readers ------------------------------------------------------------------------------
def test_BLD_B274_review_item_view_lists_only_the_ideas_own_files(db: Conn, cast: dict[str, Any]) -> None:
    """`GET /api/review/items/[id]` → `/internal/review/items/{id}/view`: the review item's idea's files."""
    files = three_files(db, cast["idea"], cast["kavya"], cast["meera"])
    row = db.execute(
        "INSERT INTO review_items (item_type, ref_id) VALUES ('idea', %s) RETURNING id",
        (cast["idea"]["idea_id"],),
    ).fetchone()
    assert row is not None
    try:
        view = item_view(db, int(row["id"]), "neutral")
        assert view is not None
        assert [a["id"] for a in view["idea"]["attachments"]] == [files["a"]]
    finally:
        db.execute("DELETE FROM review_items WHERE id = %s", (row["id"],))


def _free_cluster(db: Conn) -> str:
    """A cluster ID no idea or link in the shared test database uses."""
    for _ in range(50):
        cid = f"CL-{9000 + secrets.randbelow(1000)}"
        if (
            db.execute(
                "SELECT 1 FROM ideas WHERE cluster_id = %(c)s UNION ALL SELECT 1 FROM idea_links "
                "WHERE cluster_id = %(c)s",
                {"c": cid},
            ).fetchone()
            is None
        ):
            return cid
    raise AssertionError("no free cluster ID")


def test_BLD_B274_committee_qualify_evidence_counts_only_the_members_own_files(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The evidence gate counts the members' clean files: only their own, never a conversation file."""
    three_files(db, cast["idea"], cast["kavya"], cast["meera"])
    cluster = _free_cluster(db)
    db.execute("UPDATE ideas SET cluster_id = %s WHERE id = %s", (cluster, cast["idea"]["id"]))
    _gate, found = qualify._evidence(db, cluster, qualify._members(db, cluster))
    assert found["clean_files"] == 1


# ---- both halves of IDEA_OWN -----------------------------------------------------------------------------------------
def test_S_R2_left_2_L_QUESTIONS_BLD_B274_a_file_on_an_entry_is_never_the_ideas_own_whatever_its_purpose(
    db: Conn, cast: dict[str, Any]
) -> None:
    """Lane C's condition has two halves. A file on a conversation entry whose `purpose` still says 'idea' (set in
    SQL; the composer never writes one) is not one of the idea's files either: the desk's page leaves it out, it
    leaves Attached empty, and it cannot go on an answer. The other tests pin the `purpose` half; this one pins
    `conversation_entry_id IS NULL`."""
    idea, kavya = cast["idea"], cast["kavya"]["id"]
    on_entry = _for_the_conversation(db, fx.attachment(db, idea, cast["kavya"], name=ON_ENTRY))
    send(db, idea["idea_id"], kavya, {"file_ids": [on_entry]}, at=f.at(15, 11))
    db.execute("UPDATE attachments SET purpose = 'idea' WHERE id = %s", (on_entry,))
    row = db.execute(
        "SELECT purpose, conversation_entry_id FROM attachments WHERE id = %s", (on_entry,)
    ).fetchone()
    assert row is not None and row["purpose"] == "idea" and row["conversation_entry_id"] is not None
    assert asking._filled(db, idea)["evidence"] is False
    assert _page_files(reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], NOW)) == []
    sent = asking.send_set(db, idea["idea_id"], cast["meera"]["id"],
                           {"questions": QS, "time_to_answer": "3d"}, f.at(16, 9))  # fmt: skip
    with pytest.raises(Refused) as refused:
        asking.save_answer(
            db, sent["questions"][0]["id"], kavya, "The log is attached.", [on_entry], f.at(16, 10)
        )
    assert (refused.value.status, refused.value.code) == (422, "file_not_found")
