"""L-CONVO writing: the box (L-CONVO/5), mentions (/6), masking before anyone sees it (/7), the desk-locked idea
(/9), removing one's own message (/10), the inbox kinds posted (L-INBOX Mention, Comment), files by ID only, and
logs with IDs only. Synthetic people only.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from psycopg.pq import TransactionStatus

from convo import post
from convo.messages import remove, send
from convo.reads import conversation
from convo.store import Refused, unseal
from tests import convo_fixtures as fx

NOW = fx.at(17, 10, 30)


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    """The shared `db` fixture, plus clean-up: the people and ideas these tests made are deleted when each test ends."""
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


def test_l_convo_5_nothing_typed_or_attached_is_refused_with_the_boards_words(
    db: Any, cast: dict[str, Any]
) -> None:
    idea = fx.idea(db, cast["kavya"])
    bodies: list[dict[str, Any]] = [{}, {"text": ""}, {"text": "   \n"}, {"text": None, "file_ids": []}]
    for body in bodies:
        err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], body)
        assert (err.status, err.code, err.message, err.field) == (
            422, "empty_message", "Write a message or attach a file first.", "text",
        )  # fmt: skip
    assert fx.entries(db, idea["id"]) == []


def test_l_convo_7_a_message_is_masked_then_sealed_before_anyone_else_sees_it(
    db: Any,
    cast: dict[str, Any],
    told: list[dict[str, Any]],
    captured_logs: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback while lane C's L-HIDE cannot be imported: the shared patterns (BLD-F054)."""
    monkeypatch.setattr("convo.adapters._hide_message", None)
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya)
    typed = "Folio 1234567890 was rejected twice, Kavya Menon says R07 again."
    out = send(db, idea["idea_id"], meera["id"], {"text": typed}, at=fx.at(17, 10))
    assert out["hidden"] == 1
    [row] = fx.entries(db, idea["id"])
    assert (
        row["type"] == "message" and str(row["author_user_id"]) == meera["id"] and row["author_code"] is None
    )
    blob = bytes(row["text_encrypted"])
    assert b"1234567890" not in blob and b"Folio" not in blob  # sealed, not plain
    assert unseal(blob, str(row["id"])) == "Folio ••••90 was rejected twice, Kavya Menon says R07 again."
    [m] = messages(conversation(db, idea["idea_id"], kavya["id"], at=NOW))
    assert m["text"] == "Folio ••••90 was rejected twice, Kavya Menon says R07 again."
    # DEC-111: the sharer reads the review desk, never the person at it; the desk reads the name (BLD-F082)
    assert m["from_label"] == "The review desk"
    assert m["from"] == {"id": "", "name": "The review desk", "first_name": "The review desk", "initials": ""}
    [d] = messages(conversation(db, idea["idea_id"], meera["id"], at=NOW))
    assert d["from_label"] == "You" and d["from"]["role_label"] == "from the review desk"
    assert "1234567890" not in captured_logs.getvalue() and "rejected twice" not in captured_logs.getvalue()


def test_l_convo_9_l_inbox_comment_the_sharer_writes_to_the_desk_after_it_opened_and_hears_of_replies(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
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
    assert (
        first["to"] == [kavya["id"]]
        and first["sender"] == meera["id"]
        and first["idea_id"] == str(idea["id"])
    )
    # Meera speaks as the review desk: lane A names the desk, not her (DEC-111, BLD-F084)
    assert first["refs"] == {"entry_id": reply["entry"]["id"], "as_desk": True}
    assert (
        told[0]["dedupe_key"] == told[1]["dedupe_key"] == f"convo.comment:{idea['id']}:2026111709:desk"
    )  # a burst
    assert [a.to for a in first["actions"]] == [f"/ideas/{idea['idea_id']}/conversation"]


def test_l_convo_6_a_mention_tells_the_person_and_opens_that_message_only(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    sanjay, meghna, kavya, meera = cast["sanjay"], cast["meghna"], cast["kavya"], cast["meera"]
    idea = fx.idea(db, sanjay, title="No script for calls about rejections", status="picked")
    fx.join_crew(db, idea, meghna)
    post(db, str(idea["id"]), "desk.decided", author_user_id=meera["id"], payload={"choice": "pick"},
         at=fx.at(12, 11, 30))  # fmt: skip
    send(db, idea["idea_id"], meghna["id"], {"text": "The first draft of the script covers R03 and R12."},
         at=fx.at(12, 15, 2))  # fmt: skip
    assert refused(conversation, db, idea["idea_id"], kavya["id"]).status == 404  # not in it yet
    told.clear()
    sent = send(db, idea["idea_id"], sanjay["id"],
                {"text": "@Kavya Menon your R07 call examples would help us write the script.",
                 "mentions": [kavya["id"], "not-a-uuid", sanjay["id"]]}, at=fx.at(12, 15, 15))  # fmt: skip
    mention = next(c for c in told if c["kind"] == "mention")
    assert mention["to"] == [kavya["id"]] and mention["refs"] == {"entry_id": sent["entry"]["id"]}  # IDs only
    assert mention["dedupe_key"] == f"convo.mention:{sent['entry']['id']}"
    assert mention["actions"][0].to == f"/ideas/{idea['idea_id']}/conversation#entry-{sent['entry']['id']}"
    assert not any(c["kind"] == "comment" for c in told)  # the sharer wrote it
    assert (
        db.execute(
            "SELECT count(*) AS n FROM audit_log WHERE action = 'convo.mention_access' AND after->>'user_id' = %s",
            (kavya["id"],),
        ).fetchone()["n"]
        == 1
    )

    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert [m["id"] for m in view["entries"]] == [sent["entry"]["id"]]  # that message, nothing else
    assert view["entries"][0]["mentions_you"] and view["entries"][0]["mentions"][0]["name"] == "Kavya Menon"
    assert view["composer"]["placeholder"] == "Reply to Sanjay"
    assert (
        view["composer"]["visibility"]
        == "The crew, the review desk and anyone they mention see this conversation."
    )
    assert ("You", "Mentioned") in [(p["label"], p["doing"]) for p in view["participants"]]

    reply = send(
        db, idea["idea_id"], kavya["id"], {"text": "Two calls from last week, coming up."}, at=fx.at(13, 9)
    )
    send(db, idea["idea_id"], meghna["id"], {"text": "Crew only: draft two is ready."}, at=fx.at(13, 10))
    seen = [m["id"] for m in conversation(db, idea["idea_id"], kavya["id"], at=NOW)["entries"]]
    assert seen == [sent["entry"]["id"], reply["entry"]["id"]]  # own replies too, nothing else
    crew_view = conversation(db, idea["idea_id"], meghna["id"], at=NOW)
    assert reply["entry"]["id"] in [m["id"] for m in messages(crew_view)]


def test_l_convo_6_mentioning_someone_already_in_the_conversation_adds_no_access(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    idea = fx.idea(db, cast["kavya"])
    sent = send(
        db,
        idea["idea_id"],
        cast["kavya"]["id"],
        {"text": "Over to the desk.", "mentions": [cast["meera"]["id"]]},
    )
    [m] = [c for c in told if c["kind"] == "mention"]
    assert m["to"] == [cast["meera"]["id"]] and m["refs"] == {"entry_id": sent["entry"]["id"]}
    granted = db.execute(
        "SELECT count(*) AS n FROM audit_log WHERE action = 'convo.mention_access' AND entity = %s",
        (f"idea:{idea['idea_id']}",),
    ).fetchone()["n"]
    assert granted == 0  # Meera reads it already: the mention adds no access


def test_l_convo_7_files_only_by_id_and_only_once_checked(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya, colleague = cast["kavya"], cast["colleague"]
    idea = fx.idea(db, kavya)
    ok = fx.attachment(db, idea, kavya)
    checking = fx.attachment(db, idea, kavya, file_state="checking")
    detail = fx.attachment(db, idea, kavya, file_state="personal_data_found")
    other_idea = fx.idea(db, colleague)
    theirs = fx.attachment(db, other_idea, colleague)
    for fid, code in (
        (checking, "file_not_checked"),
        (detail, "file_has_detail"),
        (theirs, "file_unavailable"),
    ):
        err = refused(send, db, idea["idea_id"], kavya["id"], {"file_ids": [fid]})
        assert (err.status, err.code, err.field) == (422, code, "file_ids")
    out = send(db, idea["idea_id"], kavya["id"], {"file_ids": [ok]})  # a file alone is a message
    [f] = out["entry"]["files"]
    assert (f["id"], f["name"], f["type"], f["state"]) == (
        ok,
        "plain-rejection-reasons.xlsx",
        "XLSX",
        "checked",
    )
    assert f["view_url"] == f"/api/attachments/{ok}" and f["added_by"]["name"] == "Kavya Menon"
    assert (
        db.execute("SELECT conversation_entry_id FROM attachments WHERE id = %s", (ok,)).fetchone()[
            "conversation_entry_id"
        ]
        is not None
    )
    assert (
        refused(send, db, idea["idea_id"], kavya["id"], {"file_ids": [ok]}).code == "file_unavailable"
    )  # used


def test_l_convo_10_the_sender_removes_their_own_message_within_5_minutes(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya, meera, colleague = cast["kavya"], cast["meera"], cast["colleague"]
    idea = fx.idea(db, kavya)
    att = fx.attachment(db, idea, kavya)
    sent = send(
        db, idea["idea_id"], kavya["id"], {"text": "Wrong idea, sorry.", "file_ids": [att]}, at=fx.at(17, 10)
    )
    eid = sent["entry"]["id"]
    assert sent["entry"]["can_remove_until"] == fx.at(17, 10, 5)
    assert refused(remove, db, idea["idea_id"], meera["id"], eid).code == "not_yours"
    assert refused(remove, db, idea["idea_id"], colleague["id"], eid).status == 404
    out = remove(db, idea["idea_id"], kavya["id"], eid, at=fx.at(17, 10, 4))
    assert (
        out["entry"]["removed"] and out["entry"]["text"] == "Message removed" and out["entry"]["files"] == []
    )
    row = fx.entries(db, idea["id"])[0]
    assert row["deleted_at"] is not None and row["text_encrypted"] is None  # the words are gone, not hidden
    assert (
        db.execute("SELECT conversation_entry_id FROM attachments WHERE id = %s", (att,)).fetchone()[
            "conversation_entry_id"
        ]
        is None
    )
    [m] = messages(conversation(db, idea["idea_id"], meera["id"], at=NOW))
    assert (m["text"], m["removed"], m["files"]) == ("Message removed", True, [])
    assert remove(db, idea["idea_id"], kavya["id"], eid, at=fx.at(17, 11))["entry"]["removed"]  # idempotent
    late = send(db, idea["idea_id"], kavya["id"], {"text": "Second thoughts."}, at=fx.at(17, 10))
    err = refused(remove, db, idea["idea_id"], kavya["id"], late["entry"]["id"], at=fx.at(17, 10, 6))
    assert (err.status, err.code) == (409, "too_late")
    assert "can_remove_until" not in messages(conversation(db, idea["idea_id"], kavya["id"], at=NOW))[-1]
    actions = [
        r["action"]
        for r in db.execute("SELECT action FROM audit_log WHERE entity = %s", (f"idea:{idea['idea_id']}",))
    ]
    assert actions == ["convo.message_removed"]


def test_l_convo_9_a_merged_ideas_conversation_takes_no_new_messages(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    idea = fx.idea(db, cast["kavya"], status="merged")
    err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], {"text": "Hello?"})
    assert (err.status, err.code) == (409, "conversation_closed")


def test_a_api_conventions_3_a_repeated_idempotency_key_returns_the_first_message(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    idea = fx.idea(db, cast["kavya"])
    body = {"text": "Say hello once."}
    first = send(db, idea["idea_id"], cast["kavya"]["id"], body, idempotency_key="key-say-hello-0001")
    again = send(db, idea["idea_id"], cast["kavya"]["id"], body, idempotency_key="key-say-hello-0001")
    assert first["entry"]["id"] == again["entry"]["id"] and len(fx.entries(db, idea["id"])) == 1
    err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], {"text": "Different."},
                  idempotency_key="key-say-hello-0001")  # fmt: skip
    assert (err.status, err.code) == (409, "idempotency_key_reused")
    stored = db.execute(
        "SELECT response_json FROM idempotency_keys WHERE key = 'key-say-hello-0001'"
    ).fetchone()
    assert stored["response_json"] == {"entry_id": first["entry"]["id"]}  # IDs only


def test_l_convo_2_an_outsider_can_neither_write_nor_remove(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    idea = fx.idea(db, cast["kavya"])
    assert refused(send, db, idea["idea_id"], cast["colleague"]["id"], {"text": "Hi"}).status == 404
    assert fx.entries(db, idea["id"]) == []


def test_l_convo_routes_are_mounted_on_the_worker_behind_the_internal_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each route answers, and refuses a caller without the token (401, not 404: it is mounted). FastAPI keeps an
    included router as one entry in `app.routes`, so the routes are called rather than listed."""
    from fastapi.testclient import TestClient

    from core.config import get_settings

    monkeypatch.setenv("INTERNAL_API_TOKEN", "t" * 40)
    get_settings.cache_clear()
    try:
        from api.app import app

        with TestClient(app, raise_server_exceptions=False) as c:
            base = "/internal/ideas/IDEA-2026-003401/conversation"
            for method, path in (("GET", base), ("POST", f"{base}/messages"),
                                 ("DELETE", f"{base}/messages/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10")):  # fmt: skip
                assert c.request(method, path, params={"user_id": "x"}).status_code == 401, (method, path)
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------------------------------------------
# Review fixes (f/convo-5 review, 17 Nov): BLD-F062, BLD-F054, BLD-F055, BLD-F057 and the gaps it listed
# ---------------------------------------------------------------------------------------------------------------
def test_bld_f062_j_teamup_5_6_files_go_only_to_readers_the_attachment_route_lets_open_them(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    """The sharer, the desk and the core committee get the file with its link; the crew, a plain committee holder,
    the build team and a mentioned person get the message without it (DEC-107)."""
    kavya, meera, meghna, tara = cast["kavya"], cast["meera"], cast["meghna"], cast["colleague"]
    core = fx.person(db, "Rohan Mehta", roles=(("core_committee", None),))
    plain = fx.person(db, "Nisha Rao", roles=(("committee", None),))
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, kavya, status="being_built")
    fx.join_crew(db, idea, meghna)
    fx.build_team(db, idea, arjun)
    att = fx.attachment(db, idea, kavya)
    sent = send(db, idea["idea_id"], kavya["id"],
                {"text": "The rejection list, for Tara too.", "file_ids": [att], "mentions": [tara["id"]]},
                at=fx.at(17, 10))  # fmt: skip
    assert [f["view_url"] for f in sent["entry"]["files"]] == [f"/api/attachments/{att}"]  # the sharer's own
    for who in (kavya, meera, core):
        [m] = messages(conversation(db, idea["idea_id"], who["id"], at=NOW))
        assert [f["id"] for f in m["files"]] == [att], who["name"]
    for who in (meghna, plain, arjun, tara):
        [m] = messages(conversation(db, idea["idea_id"], who["id"], at=NOW))
        assert m["files"] == [] and m["text"] == "The rejection list, for Tara too.", who["name"]


def test_bld_f062_l_convo_6_a_mention_only_reader_sees_neither_files_nor_the_crews_messages(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    sanjay, meghna, kavya = cast["sanjay"], cast["meghna"], cast["kavya"]
    idea = fx.idea(db, sanjay, status="picked")
    fx.join_crew(db, idea, meghna)
    crew_only = send(db, idea["idea_id"], meghna["id"], {"text": "Crew only: draft one."}, at=fx.at(17, 9))
    att = fx.attachment(db, idea, sanjay)
    asked = send(db, idea["idea_id"], sanjay["id"],
                 {"text": "@Kavya Menon does this match your R07 calls?", "file_ids": [att],
                  "mentions": [kavya["id"]]}, at=fx.at(17, 9, 5))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert [e["id"] for e in view["entries"]] == [asked["entry"]["id"]]
    assert crew_only["entry"]["id"] not in [e["id"] for e in view["entries"]]
    assert view["entries"][0]["files"] == []


def test_bld_f054_l_convo_7_a_message_is_hidden_through_lane_cs_hide_message_when_it_is_importable(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stand-in for lane C's `hide.hide_message`: called once, with source "conversation", the entry's id and
    the author's users.id, inside the transaction that inserts the entry; its masked copy is what is sealed."""

    @dataclass
    class Hidden:
        masked: str
        hidden_count: int

    calls: list[dict[str, Any]] = []

    def stand_in(conn: Any, idea_uuid: str, text: str, **kw: Any) -> Hidden:
        calls.append(
            {
                "idea": idea_uuid,
                "text": text,
                "in_tx": conn.info.transaction_status == TransactionStatus.INTRANS,
                **kw,
            }
        )
        return Hidden(masked="Folio ••••90 was rejected, Ravi ••••ir says.", hidden_count=2)

    monkeypatch.setattr("convo.adapters._hide_message", stand_in)
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya)
    typed = "Folio 1234567890 was rejected, Ravi Nair says."
    out = send(db, idea["idea_id"], meera["id"], {"text": typed}, at=fx.at(17, 10))
    [row] = fx.entries(db, idea["id"])
    [call] = calls
    assert call == {"idea": str(idea["id"]), "text": typed, "in_tx": True, "by": meera["id"],
                    "source": "conversation", "source_id": str(row["id"]), "gatekeeper": True}  # fmt: skip
    assert (
        unseal(bytes(row["text_encrypted"]), str(row["id"])) == "Folio ••••90 was rejected, Ravi ••••ir says."
    )
    assert out["hidden"] == 2 and out["entry"]["id"] == str(row["id"])
    assert refused(send, db, idea["idea_id"], meera["id"], {"text": "   "}).code == "empty_message"
    assert len(calls) == 1  # nothing to hide, nothing called


def test_a_api_conventions_3_one_idempotency_key_on_two_ideas_is_refused_not_read_as_a_repeat(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya = cast["kavya"]
    first_idea, second_idea = fx.idea(db, kavya), fx.idea(db, kavya)
    body = {"text": "Same words on both."}
    send(db, first_idea["idea_id"], kavya["id"], body, idempotency_key="key-two-ideas-0001")
    err = refused(send, db, second_idea["idea_id"], kavya["id"], body, idempotency_key="key-two-ideas-0001")
    assert (err.status, err.code) == (409, "idempotency_key_reused")
    assert len(fx.entries(db, first_idea["id"])) == 1 and fx.entries(db, second_idea["id"]) == []
    stored = db.execute("SELECT route FROM idempotency_keys WHERE key = 'key-two-ideas-0001'").fetchone()
    assert stored["route"] == f"POST /ideas/{first_idea['idea_id']}/conversation/messages"


def test_l_convo_6_a_removed_message_no_longer_lets_a_mentioned_person_read(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    sanjay, kavya = cast["sanjay"], cast["kavya"]
    idea = fx.idea(db, sanjay)
    sent = send(db, idea["idea_id"], sanjay["id"], {"text": "@Kavya Menon a quick look?", "mentions": [kavya["id"]]},
                at=fx.at(17, 10))  # fmt: skip
    assert len(conversation(db, idea["idea_id"], kavya["id"], at=NOW)["entries"]) == 1
    remove(db, idea["idea_id"], sanjay["id"], sent["entry"]["id"], at=fx.at(17, 10, 1))
    assert refused(conversation, db, idea["idea_id"], kavya["id"], at=NOW).status == 404
    assert refused(send, db, idea["idea_id"], kavya["id"], {"text": "Here."}).status == 404


def test_bld_f055_a_sixth_file_or_an_eleventh_mention_is_refused_not_dropped(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya, colleague = cast["kavya"], cast["colleague"]
    idea = fx.idea(db, kavya)
    files = [fx.attachment(db, idea, kavya) for _ in range(6)]
    people = [fx.person(db, f"Crew Member{n}")["id"] for n in range(11)]
    err = refused(send, db, idea["idea_id"], kavya["id"], {"text": "All six.", "file_ids": files})
    assert (err.status, err.code, err.message, err.field) == (
        422, "too_many_files", "Attach up to 5 files to a message.", "file_ids",
    )  # fmt: skip
    err = refused(send, db, idea["idea_id"], kavya["id"], {"text": "All of you.", "mentions": people})
    assert (err.status, err.code, err.message, err.field) == (
        422, "too_many_mentions", "Mention up to 10 people in a message.", "mentions",
    )  # fmt: skip
    assert fx.entries(db, idea["id"]) == [] and told == []
    assert (
        refused(send, db, idea["idea_id"], colleague["id"], {"file_ids": files}).status == 404
    )  # access first
    ok = send(
        db, idea["idea_id"], kavya["id"], {"text": "Five.", "file_ids": files[:5], "mentions": people[:10]}
    )
    assert len(ok["entry"]["files"]) == 5 and len(ok["entry"]["mentions"]) == 10


def test_s_08_layout_1_the_header_reads_the_shared_day_against_the_time_asked_not_the_clock(
    db: Any, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    kavya = cast["kavya"]
    idea = fx.idea(db, kavya)
    monkeypatch.setattr("convo.reads.now", lambda: dt.datetime(2027, 1, 5, 10, tzinfo=dt.UTC))  # after 31 Dec
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    assert view["header"]["line"] == "Your idea, shared Saturday 14 November"


def test_l_convo_5_a_committee_member_and_a_build_team_member_write_and_read_as_themselves(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya = cast["kavya"]
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, kavya, status="being_built")
    fx.build_team(db, idea, arjun)
    send(db, idea["idea_id"], rohan["id"], {"text": "The committee is watching this one."}, at=fx.at(17, 9))
    built = send(db, idea["idea_id"], arjun["id"], {"text": "First screens are up."}, at=fx.at(17, 9, 10))
    rows = fx.entries(db, idea["id"])
    assert [str(r["author_user_id"]) for r in rows] == [rohan["id"], arjun["id"]]
    assert all(r["author_code"] is None for r in rows)
    assert built["entry"]["you"] and built["entry"]["from_label"] == "You"
    labels = [m["from_label"] for m in messages(conversation(db, idea["idea_id"], kavya["id"], at=NOW))]
    assert labels == ["The Ones Committee", "Arjun Rao"]  # the committee, not Rohan, for the sharer (DEC-113)
    assert [c["to"] for c in told if c["kind"] == "comment"] == [[kavya["id"]], [kavya["id"]]]


def test_l_convo_10_a_message_can_be_removed_at_exactly_5_minutes_and_not_a_moment_after(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya = cast["kavya"]
    idea = fx.idea(db, kavya)
    sent = send(db, idea["idea_id"], kavya["id"], {"text": "Typo."}, at=fx.at(17, 10))
    late = send(db, idea["idea_id"], kavya["id"], {"text": "Another typo."}, at=fx.at(17, 10))
    late_at = late["entry"]["at"]  # a microsecond after the first (BLD-F057)
    over = late_at + dt.timedelta(minutes=5, microseconds=1)
    assert refused(remove, db, idea["idea_id"], kavya["id"], late["entry"]["id"], at=over).code == "too_late"
    out = remove(
        db,
        idea["idea_id"],
        kavya["id"],
        sent["entry"]["id"],
        at=sent["entry"]["at"] + dt.timedelta(minutes=5),
    )
    assert out["entry"]["removed"]


def test_bld_f056_l_inbox_comment_a_new_hour_starts_a_new_comment_item(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya)
    send(db, idea["idea_id"], meera["id"], {"text": "Before ten."}, at=fx.at(17, 9, 59))
    send(db, idea["idea_id"], meera["id"], {"text": "After ten."}, at=fx.at(17, 10, 0))
    keys = [c["dedupe_key"] for c in told if c["kind"] == "comment"]
    # the review desk's own hourly item (DEC-111, BLD-F084)
    assert keys == [
        f"convo.comment:{idea['id']}:2026111709:desk",
        f"convo.comment:{idea['id']}:2026111710:desk",
    ]


def test_bld_f063_l_convo_7_only_the_sharer_the_desk_and_the_core_committee_add_files(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    """The crew, the build team and a mentioned person write without files: a file from them is refused, and the
    box tells S-08 not to show the attach control. The readers who add files are the readers who can open them."""
    kavya, meera, meghna, tara = cast["kavya"], cast["meera"], cast["meghna"], cast["colleague"]
    core = fx.person(db, "Rohan Mehta", roles=(("core_committee", None),))
    arjun = fx.person(db, "Arjun Rao")
    idea = fx.idea(db, kavya, status="being_built")
    fx.join_crew(db, idea, meghna)
    fx.build_team(db, idea, arjun)
    send(db, idea["idea_id"], kavya["id"], {"text": "@Tara Joshi have a look.", "mentions": [tara["id"]]})
    for who in (meghna, arjun, tara):
        own = fx.attachment(db, idea, who)
        err = refused(send, db, idea["idea_id"], who["id"], {"text": "With my file.", "file_ids": [own]})
        assert (err.status, err.code, err.field) == (422, "files_not_allowed", "file_ids"), who["name"]
        assert err.message == (
            "You can’t add files here. The person who shared this idea or the review desk can add them."
        )
        assert conversation(db, idea["idea_id"], who["id"], at=NOW)["composer"]["can_attach"] is False
        assert send(db, idea["idea_id"], who["id"], {"text": "Words only."})["entry"]["files"] == []
    for who in (kavya, meera, core):
        own = fx.attachment(db, idea, who)
        assert conversation(db, idea["idea_id"], who["id"], at=NOW)["composer"]["can_attach"] is True
        sent = send(db, idea["idea_id"], who["id"], {"file_ids": [own]})
        assert [f["id"] for f in sent["entry"]["files"]] == [own], who["name"]


def test_bld_f067_l_convo_10_removing_a_message_drops_what_l_hide_kept_and_keeps_a_value_another_message_uses(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    """Lane C's real `hide_message` through `send` (one connection), then removal in lane C's order: the removed
    message's hidden details and the writer's sealed words go, and so does a vault value only it used; a value the
    second message also holds stays (review of f/convo-7, items 3 and 8)."""
    from hide.core import scope_for

    kavya, meera = cast["kavya"], cast["meera"]
    idea = fx.idea(db, kavya)
    first = send(db, idea["idea_id"], kavya["id"],
                 {"text": "Folio 1234567890 failed, and Folio 9876543210 too."}, at=fx.at(17, 10))  # fmt: skip
    second = send(
        db, idea["idea_id"], kavya["id"], {"text": "Folio 9876543210 failed again."}, at=fx.at(17, 10, 1)
    )
    one, two = first["entry"]["id"], second["entry"]["id"]
    assert first["hidden"] >= 2 and "1234567890" not in first["entry"]["text"]

    def rows(table: str, source_id: str) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM {table} WHERE idea_uuid = %s AND source = 'conversation' AND source_id = %s",  # noqa: S608
                (idea["id"], source_id),
            ).fetchall()
        ]

    def tags(source_id: str) -> set[str]:
        return {str(r["vault_tag"]) for r in rows("hidden_details", source_id) if r["vault_tag"]}

    def in_vault(tag: str) -> bool:
        n = db.execute(
            "SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id = %s AND tag = %s",
            (scope_for(str(idea["id"])), tag),
        ).fetchone()["n"]
        return int(n) == 1

    assert len(rows("idea_words_sealed", one)) == 1 and len(rows("idea_words_sealed", two)) == 1
    only_first, shared = tags(one) - tags(two), tags(one) & tags(two)
    assert only_first and shared  # 1234567890 is the first's alone; 9876543210 is in both
    assert all(in_vault(t) for t in tags(one) | tags(two))

    remove(db, idea["idea_id"], kavya["id"], one, at=fx.at(17, 10, 2))
    assert (
        rows("hidden_details", one) == [] and rows("idea_words_sealed", one) == []
    )  # no sealed words remain
    assert not any(in_vault(t) for t in only_first)
    assert all(in_vault(t) for t in shared)  # the second message still holds it
    assert len(rows("idea_words_sealed", two)) == 1 and shared and shared <= tags(two)
    [gone] = [m for m in messages(conversation(db, idea["idea_id"], meera["id"], at=NOW)) if m["id"] == one]
    assert gone["removed"] and gone["text"] == "Message removed"


def test_bld_f093_l_convo_10_removing_a_message_leaves_another_ideas_and_another_sources_details(
    db: Any, cast: dict[str, Any], told: list[dict[str, Any]]
) -> None:
    """Removal forgets only what L-HIDE kept for that message (source "conversation", its entry id): the same folio
    hidden on another idea, and in another text of the same idea (source "message"), keeps its hidden detail, its
    vault value and its sealed words (f-convo-7 review, after launch)."""
    import uuid

    from hide import hide_message
    from hide.core import scope_for

    kavya = cast["kavya"]
    idea = fx.idea(db, kavya)
    other = fx.idea(db, kavya, title="Branch staff cannot read the rejection code")
    gone = send(db, idea["idea_id"], kavya["id"], {"text": "Folio 1234567890 failed."}, at=fx.at(17, 10))
    there = send(db, other["idea_id"], kavya["id"], {"text": "Folio 1234567890 failed here too."},
                 at=fx.at(17, 10, 1))  # fmt: skip
    draft_text = str(uuid.uuid4())
    with db.transaction():
        hide_message(db, str(idea["id"]), "Folio 1234567890 is in my notes.", by=kavya["id"], source="message",
                     source_id=draft_text)  # fmt: skip

    def tags(i: dict[str, Any], source: str, sid: str) -> set[str]:
        return {
            str(r["vault_tag"])
            for r in db.execute(
                "SELECT vault_tag FROM hidden_details WHERE idea_uuid = %s AND source = %s AND source_id = %s "
                "AND vault_tag IS NOT NULL",
                (i["id"], source, sid),
            ).fetchall()
        }

    def in_vault(i: dict[str, Any], found: set[str]) -> bool:
        n = db.execute(
            "SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id = %s AND tag = ANY(%s::text[])",
            (scope_for(str(i["id"])), sorted(found)),
        ).fetchone()["n"]
        return bool(found) and int(n) == len(found)

    def sealed(i: dict[str, Any], source: str) -> int:
        return int(
            db.execute(
                "SELECT count(*) AS n FROM idea_words_sealed WHERE idea_uuid = %s AND source = %s",
                (i["id"], source),
            ).fetchone()["n"]
        )

    elsewhere = tags(other, "conversation", there["entry"]["id"])
    in_notes = tags(idea, "message", draft_text)
    assert elsewhere and in_notes and tags(idea, "conversation", gone["entry"]["id"])
    before = (sealed(other, "conversation"), sealed(idea, "message"))
    assert before == (1, 1)

    remove(db, idea["idea_id"], kavya["id"], gone["entry"]["id"], at=fx.at(17, 10, 2))
    assert tags(idea, "conversation", gone["entry"]["id"]) == set()
    assert tags(other, "conversation", there["entry"]["id"]) == elsewhere and in_vault(other, elsewhere)
    assert tags(idea, "message", draft_text) == in_notes and in_vault(idea, in_notes)
    assert (sealed(other, "conversation"), sealed(idea, "message")) == before


@pytest.mark.parametrize(("hide_status", "status"), [(503, 503), (409, 422), (404, 422)])
def test_bld_f054_a_refusal_from_l_hide_is_a_ready_503_or_422_and_nothing_is_written(
    db: Any,
    cast: dict[str, Any],
    told: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    hide_status: int,
    status: int,
) -> None:
    """Lane C's HideError never reaches the person as a 500: a 5xx is a 503, any 4xx a 422, both with the same ready
    message (f-convo-7 review, after launch: the 4xx case pinned by BLD-F093)."""
    from hide.core import HideError

    def refuses(*a: Any, **k: Any) -> Any:
        raise HideError(hide_status, "gatekeeper_down" if hide_status >= 500 else "conflict")

    monkeypatch.setattr("convo.adapters._hide_message", refuses)
    idea = fx.idea(db, cast["kavya"])
    err = refused(send, db, idea["idea_id"], cast["kavya"]["id"], {"text": "Folio 1234567890 failed."})
    assert (err.status, err.code, err.field) == (status, "hide_unavailable", "text")
    assert (
        err.message
        == "We couldn’t check this message for customers’ details just now. Try again in a minute."
    )
    assert fx.entries(db, idea["id"]) == [] and told == []
