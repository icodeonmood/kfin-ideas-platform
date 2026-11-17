"""L-CONVO writing: the box (L-CONVO/5), mentions (/6), masking before anyone sees it (/7), the desk-locked idea
(/9), removing one's own message (/10), the inbox kinds posted (L-INBOX Mention, Comment), files by ID only, and
logs with IDs only. Synthetic people only.
"""

from __future__ import annotations

from typing import Any

import pytest

from convo import post
from convo.messages import remove, send
from convo.reads import conversation
from convo.store import Refused, unseal
from tests import convo_fixtures as fx

NOW = fx.at(17, 10, 30)


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every inbox post, as lane A's `notify.post` receives it."""
    calls: list[dict[str, Any]] = []

    def fake(conn: Any, kind: str, recipients: list[str], **kw: Any) -> None:
        calls.append({"kind": kind, "to": list(recipients), **kw})

    monkeypatch.setattr("convo.adapters.notify_post", fake)
    return calls


@pytest.fixture
def cast(db: Any) -> dict[str, Any]:
    return {
        "kavya": fx.person(db, "Kavya Menon"),
        "meera": fx.person(db, "Meera Iyer", roles=(("reviewer", None),)),
        "sanjay": fx.person(db, "Sanjay Pillai", city="Mumbai", area="Operations"),
        "meghna": fx.person(db, "Meghna Das"),
        "colleague": fx.person(db, "Tara Joshi"),
    }


def refused(fn: Any, *args: Any, **kwargs: Any) -> Refused:
    with pytest.raises(Refused) as caught:
        fn(*args, **kwargs)
    return caught.value


def messages(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in view["entries"] if e["type"] == "message"]


def test_l_convo_5_nothing_typed_or_attached_is_refused_with_the_boards_words(db: Any, cast: dict) -> None:
    idea = fx.idea(db, cast["kavya"])
    for body in ({}, {"text": ""}, {"text": "   \n"}, {"text": None, "file_ids": []}):
        err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], body)
        assert (err.status, err.code, err.message, err.field) == (
            422, "empty_message", "Write a message or attach a file first.", "text",
        )  # fmt: skip
    assert fx.entries(db, idea["id"]) == []


def test_l_convo_7_a_message_is_masked_then_sealed_before_anyone_else_sees_it(
    db: Any, cast: dict, told: list, captured_logs: Any
) -> None:
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya)
    typed = "Folio 1234567890 was rejected twice, Kavya Menon says R07 again."
    out = send(db, idea["idea_id"], meera["id"], {"text": typed}, at=fx.at(17, 10))
    assert out["hidden"] == 1
    [row] = fx.entries(db, idea["id"])
    assert row["type"] == "message" and str(row["author_user_id"]) == meera["id"] and row["author_code"] is None
    blob = bytes(row["text_encrypted"])
    assert b"1234567890" not in blob and b"Folio" not in blob  # sealed, not plain
    assert unseal(blob, str(row["id"])) == "Folio ••••90 was rejected twice, Kavya Menon says R07 again."
    [m] = messages(conversation(db, idea["idea_id"], kavya["id"], at=NOW))
    assert m["text"] == "Folio ••••90 was rejected twice, Kavya Menon says R07 again."
    assert m["from_label"] == "Meera from the review desk" and m["from"]["role_label"] == "from the review desk"
    assert "1234567890" not in captured_logs.getvalue() and "rejected twice" not in captured_logs.getvalue()


def test_l_convo_9_l_inbox_comment_the_sharer_writes_to_the_desk_after_it_opened_and_hears_of_replies(
    db: Any, cast: dict, told: list
) -> None:
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya, opened_by=meera["id"], reviewer_id=meera["id"], opened_at=fx.at(16, 9, 50))
    mine = send(db, idea["idea_id"], kavya["id"], {"text": "Adding the Vizag numbers here."}, at=fx.at(17, 9))
    assert mine["entry"]["you"] and mine["entry"]["from_label"] == "You"
    [row] = fx.entries(db, idea["id"])
    assert row["author_code"] == kavya["code"] and row["author_user_id"] is None
    assert told == []  # the sharer writing tells nobody
    reply = send(db, idea["idea_id"], meera["id"], {"text": "Thanks, that helps."}, at=fx.at(17, 9, 5))
    send(db, idea["idea_id"], meera["id"], {"text": "One more thing on R03."}, at=fx.at(17, 9, 6))
    assert [c["kind"] for c in told] == ["comment", "comment"]
    first = told[0]
    assert first["to"] == [kavya["id"]] and first["sender"] == meera["id"] and first["idea_id"] == str(idea["id"])
    assert first["refs"] == {"entry_id": reply["entry"]["id"]}
    assert told[0]["dedupe_key"] == told[1]["dedupe_key"] == f"convo.comment:{idea['id']}:2026111709"  # a burst
    assert [a.to for a in first["actions"]] == [f"/ideas/{idea['idea_id']}/conversation"]


def test_l_convo_6_a_mention_tells_the_person_and_opens_that_message_only(
    db: Any, cast: dict, told: list
) -> None:
    sanjay, meghna, kavya, meera = cast["sanjay"], cast["meghna"], cast["kavya"], cast["meera"]
    idea = fx.idea(db, sanjay, title="No script for calls about rejections", status="picked")
    fx.join_crew(db, idea, meghna)
    post(db, str(idea["id"]), "desk.decided", author_user_id=meera["id"], payload={"choice": "pick"},
         at=fx.at(12, 11, 30))  # fmt: skip
    send(db, idea["idea_id"], meghna["id"], {"text": "The first draft of the script covers R03 and R12."},
         at=fx.at(12, 15, 2))  # fmt: skip
    assert pytest.raises(Refused, conversation, db, idea["idea_id"], kavya["id"]).value.status == 404
    told.clear()
    sent = send(db, idea["idea_id"], sanjay["id"],
                {"text": "@Kavya Menon your R07 call examples would help us write the script.",
                 "mentions": [kavya["id"], "not-a-uuid", sanjay["id"]]}, at=fx.at(12, 15, 15))  # fmt: skip
    mention = next(c for c in told if c["kind"] == "mention")
    assert mention["to"] == [kavya["id"]] and mention["refs"] == {"entry_id": sent["entry"]["id"], "outside": True}
    assert mention["actions"][0].to == f"/ideas/{idea['idea_id']}/conversation#entry-{sent['entry']['id']}"
    assert not any(c["kind"] == "comment" for c in told)  # the sharer wrote it
    assert db.execute(
        "SELECT count(*) AS n FROM audit_log WHERE action = 'convo.mention_access' AND after->>'user_id' = %s",
        (kavya["id"],),
    ).fetchone()["n"] == 1

    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert [m["id"] for m in view["entries"]] == [sent["entry"]["id"]]  # that message, nothing else
    assert view["entries"][0]["mentions_you"] and view["entries"][0]["mentions"][0]["name"] == "Kavya Menon"
    assert view["composer"]["placeholder"] == "Reply to Sanjay"
    assert view["composer"]["visibility"] == "The crew, the review desk and anyone they mention see this conversation."
    assert ("You", "Mentioned") in [(p["label"], p["doing"]) for p in view["participants"]]

    reply = send(db, idea["idea_id"], kavya["id"], {"text": "Two calls from last week, coming up."}, at=fx.at(13, 9))
    send(db, idea["idea_id"], meghna["id"], {"text": "Crew only: draft two is ready."}, at=fx.at(13, 10))
    seen = [m["id"] for m in conversation(db, idea["idea_id"], kavya["id"], at=NOW)["entries"]]
    assert seen == [sent["entry"]["id"], reply["entry"]["id"]]  # own replies too, nothing else
    crew_view = conversation(db, idea["idea_id"], meghna["id"], at=NOW)
    assert reply["entry"]["id"] in [m["id"] for m in messages(crew_view)]


def test_l_convo_6_mentioning_someone_already_in_the_conversation_adds_no_access(
    db: Any, cast: dict, told: list
) -> None:
    idea = fx.idea(db, cast["kavya"])
    send(db, idea["idea_id"], cast["kavya"]["id"], {"text": "Over to the desk.", "mentions": [cast["meera"]["id"]]})
    [m] = [c for c in told if c["kind"] == "mention"]
    assert m["refs"]["outside"] is False
    assert db.execute("SELECT count(*) AS n FROM audit_log WHERE action = 'convo.mention_access'").fetchone()["n"] == 0


def test_l_convo_7_files_only_by_id_and_only_once_checked(db: Any, cast: dict, told: list) -> None:
    kavya, colleague = cast["kavya"], cast["colleague"]
    idea = fx.idea(db, kavya)
    ok = fx.attachment(db, idea, kavya)
    checking = fx.attachment(db, idea, kavya, file_state="checking")
    detail = fx.attachment(db, idea, kavya, file_state="personal_data_found")
    other_idea = fx.idea(db, colleague)
    theirs = fx.attachment(db, other_idea, colleague)
    for fid, code in ((checking, "file_not_checked"), (detail, "file_has_detail"), (theirs, "file_unavailable")):
        err = refused(send, db, idea["idea_id"], kavya["id"], {"file_ids": [fid]})
        assert (err.status, err.code, err.field) == (422, code, "file_ids")
    out = send(db, idea["idea_id"], kavya["id"], {"file_ids": [ok]})  # a file alone is a message
    [f] = out["entry"]["files"]
    assert (f["id"], f["name"], f["type"], f["state"]) == (ok, "plain-rejection-reasons.xlsx", "XLSX", "checked")
    assert f["view_url"] == f"/api/attachments/{ok}" and f["added_by"]["name"] == "Kavya Menon"
    assert db.execute("SELECT conversation_entry_id FROM attachments WHERE id = %s", (ok,)).fetchone()[
        "conversation_entry_id"
    ] is not None
    assert refused(send, db, idea["idea_id"], kavya["id"], {"file_ids": [ok]}).code == "file_unavailable"  # used


def test_l_convo_10_the_sender_removes_their_own_message_within_5_minutes(db: Any, cast: dict, told: list) -> None:
    kavya, meera, colleague = cast["kavya"], cast["meera"], cast["colleague"]
    idea = fx.idea(db, kavya)
    att = fx.attachment(db, idea, kavya)
    sent = send(db, idea["idea_id"], kavya["id"], {"text": "Wrong idea, sorry.", "file_ids": [att]}, at=fx.at(17, 10))
    eid = sent["entry"]["id"]
    assert sent["entry"]["can_remove_until"] == fx.at(17, 10, 5)
    assert refused(remove, db, idea["idea_id"], meera["id"], eid).code == "not_yours"
    assert refused(remove, db, idea["idea_id"], colleague["id"], eid).status == 404
    out = remove(db, idea["idea_id"], kavya["id"], eid, at=fx.at(17, 10, 4))
    assert out["entry"]["removed"] and out["entry"]["text"] == "Message removed" and out["entry"]["files"] == []
    row = fx.entries(db, idea["id"])[0]
    assert row["deleted_at"] is not None and row["text_encrypted"] is None  # the words are gone, not hidden
    assert db.execute("SELECT conversation_entry_id FROM attachments WHERE id = %s", (att,)).fetchone()[
        "conversation_entry_id"
    ] is None
    [m] = messages(conversation(db, idea["idea_id"], meera["id"], at=NOW))
    assert (m["text"], m["removed"], m["files"]) == ("Message removed", True, [])
    assert remove(db, idea["idea_id"], kavya["id"], eid, at=fx.at(17, 11))["entry"]["removed"]  # idempotent
    late = send(db, idea["idea_id"], kavya["id"], {"text": "Second thoughts."}, at=fx.at(17, 10))
    err = refused(remove, db, idea["idea_id"], kavya["id"], late["entry"]["id"], at=fx.at(17, 10, 6))
    assert (err.status, err.code) == (409, "too_late")
    assert "can_remove_until" not in messages(conversation(db, idea["idea_id"], kavya["id"], at=NOW))[-1]
    actions = [r["action"] for r in db.execute("SELECT action FROM audit_log WHERE entity = %s", (f"idea:{idea['idea_id']}",))]
    assert actions == ["convo.message_removed"]


def test_l_convo_9_a_merged_ideas_conversation_takes_no_new_messages(db: Any, cast: dict, told: list) -> None:
    idea = fx.idea(db, cast["kavya"], status="merged")
    err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], {"text": "Hello?"})
    assert (err.status, err.code) == (409, "conversation_closed")


def test_a_api_conventions_3_a_repeated_idempotency_key_returns_the_first_message(
    db: Any, cast: dict, told: list
) -> None:
    idea = fx.idea(db, cast["kavya"])
    body = {"text": "Say hello once."}
    first = send(db, idea["idea_id"], cast["kavya"]["id"], body, idempotency_key="key-say-hello-0001")
    again = send(db, idea["idea_id"], cast["kavya"]["id"], body, idempotency_key="key-say-hello-0001")
    assert first["entry"]["id"] == again["entry"]["id"] and len(fx.entries(db, idea["id"])) == 1
    err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], {"text": "Different."},
                  idempotency_key="key-say-hello-0001")  # fmt: skip
    assert (err.status, err.code) == (409, "idempotency_key_reused")
    stored = db.execute("SELECT response_json FROM idempotency_keys WHERE key = 'key-say-hello-0001'").fetchone()
    assert stored["response_json"] == {"entry_id": first["entry"]["id"]}  # IDs only


def test_l_convo_2_an_outsider_can_neither_write_nor_remove(db: Any, cast: dict, told: list) -> None:
    idea = fx.idea(db, cast["kavya"])
    assert refused(send, db, idea["idea_id"], cast["colleague"]["id"], {"text": "Hi"}).status == 404
    assert fx.entries(db, idea["id"]) == []


def test_l_convo_routes_are_mounted_on_the_worker() -> None:
    from api.app import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert {
        "/internal/ideas/{ref}/conversation",
        "/internal/ideas/{ref}/conversation/messages",
        "/internal/ideas/{ref}/conversation/messages/{entry_id}",
    } <= paths
