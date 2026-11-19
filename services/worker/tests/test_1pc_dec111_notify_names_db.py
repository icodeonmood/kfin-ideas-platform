"""DEC-111 (BLD-B257), L-NOTIFY and L-INBOX: every kind the review desk sends a sharer is sent as the review desk as a
whole (`notify.AS_THE_DESK`), so neither the Inbox item, its JSON nor its email names the reviewer, and no sender is
stored. An item stored before the change, with the reviewer as its sender, reads as the desk too. A reversal is the
Ones Committee's: DEC-113 (BLD-A231) names its member only to the review desk and the committee, by live role grants;
a sharer and the crew read "The Ones Committee", and their rows store no sender."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import pytest

import notify
from notify import inbox
from notify import render as nrender
from tests import test_notify as l_notify

# L-NOTIFY's own people and ideas (fixture "cast"), shared with test_notify, and its working-day noon
cast = l_notify.cast
WORKDAY_NOON = l_notify.WORKDAY_NOON

DESK_KINDS: tuple[notify.InboxKind, ...] = (
    "questions",
    "answer_reminder",
    "decision",
    "desk_merge",
    "worth_revised",
)


def _refs(db: Any, kind: str, p: dict[str, Any], ideas: dict[str, str]) -> dict[str, Any]:
    if kind in ("questions", "answer_reminder"):
        s = db.execute(
            "INSERT INTO question_sets (idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at) "
            "VALUES (%s, %s, 'sent', '3d', %s, %s) RETURNING id",
            (ideas["mine"], p["meera"]["id"], WORKDAY_NOON, WORKDAY_NOON + dt.timedelta(days=3)),
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, 1, 'summary', '\\x00')",
            (s,),
        )
        return {"set_id": str(s)}
    if kind == "decision":
        return {"decision_id": str(uuid.uuid4()), "choice": "pick"}
    if kind == "desk_merge":
        return {"merge_id": str(uuid.uuid4())}
    return {"worth_id": str(uuid.uuid4())}


def test_DEC_111_L_NOTIFY_the_desks_kinds_are_sent_as_the_review_desk() -> None:
    assert set(DESK_KINDS) <= notify.AS_THE_DESK
    assert (
        "decision_reversed" not in notify.AS_THE_DESK
    )  # the Ones Committee's (DEC-113: notify.AS_THE_COMMITTEE)


@pytest.mark.parametrize("kind", DESK_KINDS)
def test_DEC_111_L_NOTIFY_L_INBOX_a_desk_item_and_its_email_never_name_the_reviewer(
    cast: Any, kind: notify.InboxKind
) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera = p["kavya"]["id"], p["meera"]["id"]
    try:
        notify.post(db, kind, [kavya], idea_id=ideas["mine"], sender=meera, refs=_refs(db, kind, p, ideas),
                    due_at=WORKDAY_NOON + dt.timedelta(days=3) if kind in ("questions", "answer_reminder") else None,
                    needs_you=kind in ("questions", "answer_reminder"))  # fmt: skip
        senders = db.execute(
            "SELECT channel, from_user_id FROM notifications WHERE user_id = %s AND kind = %s ORDER BY id",
            (kavya, kind),
        ).fetchall()
        assert senders and all(r["from_user_id"] is None for r in senders)  # not even stored
        item = inbox.items(db, kavya, now=WORKDAY_NOON)["items"][0]
        assert (
            item["kind"] == kind and item["body"]["sender"] == "The review desk" and item["from"] == "system"
        )
        row = db.execute(
            "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email' AND kind = %s",
            (kavya, kind),
        ).fetchone()
        mail = nrender.email(db, dict(row), WORKDAY_NOON) if row is not None else None
        seen = json.dumps(item, ensure_ascii=False) + (
            (mail.subject + mail.text + mail.html) if mail is not None else ""
        )
        assert "Meera" not in seen and "Iyer" not in seen and meera not in seen, seen
        if kind == "questions":
            assert (item["line"], mail and mail.subject) == (
                "asked you 1 question",
                "The review desk asked you 1 question",
            )
        if kind == "answer_reminder":
            assert item["line"].endswith("left to answer the review desk’s questions"), item["line"]
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = %s", (kavya,))


def test_DEC_111_L_INBOX_an_item_stored_with_the_reviewer_as_sender_reads_as_the_desk(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera = p["kavya"]["id"], p["meera"]["id"]
    try:
        notify.post(
            db, "decision", [kavya], idea_id=ideas["mine"], sender=meera, refs={"choice": "not_picked"}
        )
        # as an item posted before DEC-111 was stored: with the reviewer as its sender
        db.execute("UPDATE notifications SET from_user_id = %s WHERE user_id = %s", (meera, kavya))
        item = inbox.items(db, kavya, now=WORKDAY_NOON)["items"][0]
        assert (item["body"]["sender"], item["line"]) == (
            "The review desk",
            "didn’t pick your idea, with a reason",
        )
        row = db.execute(
            "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email'", (kavya,)
        ).fetchone()
        mail = nrender.email(db, dict(row), WORKDAY_NOON)
        seen = json.dumps(item, ensure_ascii=False) + mail.subject + mail.text + mail.html
        assert "Meera" not in seen and meera not in seen, seen
        # the committee's reversal names the committee as one to the sharer (DEC-113)
        notify.post(db, "decision_reversed", [kavya], idea_id=ideas["mine"], sender=p["rohan"]["id"],
                    refs={"window_id": str(uuid.uuid4()), "to": "pick"})  # fmt: skip
        rev = next(
            it
            for it in inbox.items(db, kavya, now=WORKDAY_NOON)["items"]
            if it["kind"] == "decision_reversed"
        )
        assert rev["body"]["sender"] == "The Ones Committee"
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = %s", (kavya,))


# ---------------------------------------------------------------------------------------------------------------
# DEC-113 (BLD-A231): the Ones Committee as one to the sharer and the crew; by name to the desk and the committee
# ---------------------------------------------------------------------------------------------------------------

AS_ONE = {"id": "", "name": "The Ones Committee", "first_name": "The Ones Committee", "initials": ""}


def _reversal(db: Any, kavya: str) -> dict[str, Any]:
    return next(
        it for it in inbox.items(db, kavya, now=WORKDAY_NOON)["items"] if it["kind"] == "decision_reversed"
    )


def test_l_inbox_kinds_dec113_committee_sender_for_sharer_crew_and_reviewer_db(cast: Any) -> None:
    """J-COMMITTEE: lane B tells the sharer, the crew and the reviewer. Only the reviewer's rows keep the member, and
    only the reviewer reads "Rohan Mehta from the Ones Committee"; the sharer and the crew (Ravi, no role) read "The
    Ones Committee" with no initials, in the Inbox and the email, and the member is in neither."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi, meera, rohan = (p[k]["id"] for k in ("kavya", "ravi", "meera", "rohan"))
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'core_committee')", (rohan,))
    try:
        notify.post(db, "decision_reversed", [kavya, ravi, meera], idea_id=ideas["mine"], sender=rohan,
                    refs={"window_id": str(uuid.uuid4()), "to": "pick"})  # fmt: skip
        stored = db.execute(
            "SELECT user_id::text AS u, channel, from_user_id::text AS f FROM notifications "
            "WHERE kind = 'decision_reversed' AND user_id = ANY(%s::uuid[]) ORDER BY user_id, channel",
            ([kavya, ravi, meera],),
        ).fetchall()
        assert {(r["u"], r["f"]) for r in stored} == {(kavya, None), (ravi, None), (meera, rohan)}
        assert {r["channel"] for r in stored if r["u"] == kavya} == {"in_app", "email"}
        for reader in (kavya, ravi):
            item = _reversal(db, reader)
            assert (item["from"], item["body"]["sender"]) == (AS_ONE, "The Ones Committee"), reader
            row = db.execute(
                "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email' AND kind = 'decision_reversed'",
                (reader,),
            ).fetchone()
            mail = nrender.email(db, dict(row), WORKDAY_NOON)
            seen = json.dumps(item, ensure_ascii=False) + mail.subject + mail.text + mail.html
            assert "Rohan" not in seen and "Mehta" not in seen and rohan not in seen, seen
            assert "The Ones Committee reversed a decision on your idea" in mail.text
        mine = _reversal(db, meera)
        assert mine["body"]["sender"] == "Rohan Mehta from the Ones Committee"
        assert mine["from"]["id"] == rohan and mine["from"]["initials"] == "RM"
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = ANY(%s::uuid[])", ([kavya, ravi, meera],))
        db.execute("DELETE FROM role_grants WHERE user_id = %s", (rohan,))


def test_l_inbox_kinds_dec113_a_row_stored_with_the_member_reads_the_committee_to_a_sharer_db(
    cast: Any,
) -> None:
    """An item stored before DEC-113, or by the club seed, with the member as its sender: the role check at reading
    time makes it read "The Ones Committee" to the sharer."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, rohan = p["kavya"]["id"], p["rohan"]["id"]
    try:
        notify.post(db, "decision_reversed", [kavya], idea_id=ideas["mine"], sender=rohan,
                    refs={"window_id": str(uuid.uuid4()), "to": "pick"})  # fmt: skip
        db.execute("UPDATE notifications SET from_user_id = %s WHERE user_id = %s", (rohan, kavya))
        item = _reversal(db, kavya)
        assert (item["from"], item["body"]["sender"]) == (AS_ONE, "The Ones Committee")
        assert rohan not in json.dumps(item) and "Rohan" not in json.dumps(item, ensure_ascii=False)
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = %s", (kavya,))


@pytest.mark.parametrize("kind", ("comment", "mention"))
def test_l_inbox_kinds_dec113_as_committee_stores_no_sender_db(cast: Any, kind: notify.InboxKind) -> None:
    """Lane F's seam (S-08): `as_committee: true` stores no sender and reads "The Ones Committee"."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, rohan = p["kavya"]["id"], p["rohan"]["id"]
    try:
        notify.post(db, kind, [kavya], idea_id=ideas["mine"], sender=rohan,
                    refs={"entry_id": str(uuid.uuid4()), "as_committee": True})  # fmt: skip
        senders = db.execute(
            "SELECT from_user_id FROM notifications WHERE user_id = %s AND kind = %s", (kavya, kind)
        ).fetchall()
        assert senders and all(r["from_user_id"] is None for r in senders)
        item = inbox.items(db, kavya, now=WORKDAY_NOON)["items"][0]
        assert (item["kind"], item["from"], item["body"]["sender"]) == (kind, AS_ONE, "The Ones Committee")
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = %s", (kavya,))
