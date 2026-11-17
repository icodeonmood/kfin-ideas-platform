"""Other ways in: a forwarded email or a Teams message lands as a draft (L-DRAFT.channels). BLD-C077.

Built and switched off (DEC-105): `intake.email` and `intake.teams` start off and stay off until IT gives the 1% Club
mailbox and the Teams app. The mailbox reader and the bot are IT's; they hand each arrival to `intake` (worker
route `POST /internal/drafts/intake`).

The sender is matched to an employee by their work address (a Teams identity is its sign-in address); anyone else
gets a polite bounce, which comms sends from the code returned here. The person's note on top is their words: it is
masked before anything is stored (DEC-103) and becomes the draft's first message. A forwarded thread is context
only: it is kept masked with the draft's origin for the person to read, and never quoted by the parts. Nothing that
arrives this way is shared until the person goes through Check it; their Inbox says the draft was kept
(`draft_kept`, "Check and send").
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any

from core import killswitch
from core.db import Conn
from core.logging import get_logger
from draft import adapters, labels
from draft.store import Device, DraftError, Owner, _add
from onepc.context import seal_text

log = get_logger("draft.channels")
SWITCH = {"email": "intake.email", "teams": "intake.teams"}
SUBJECT_MAX = 200
THREAD_MAX = 20_000


class ChannelOff(Exception):
    """The channel's switch is off: the arrival is not taken (the caller keeps or bounces it)."""


@dataclass(frozen=True)
class Arrival:
    channel: str  # email | teams
    sender: str  # the work address (a Teams identity's sign-in address)
    note: str  # the person's own words: the note on top, the Teams message, or a voice note's words
    received_at: dt.datetime
    subject: str | None = None
    thread: str | None = None  # the forwarded thread: context only
    note_en: str | None = None  # a voice note's English copy (DEC-108)


def _sender(conn: Conn, address: str) -> Owner | None:
    row = conn.execute(
        "SELECT u.id, m.contributor_code FROM users u JOIN contributor_map m ON m.user_id = u.id "
        "WHERE lower(u.email) = lower(%s) AND u.active",
        (address.strip(),),
    ).fetchone()
    return Owner(str(row["id"]), str(row["contributor_code"])) if row else None


def origin_label(channel: str, origin: dict[str, Any], now: dt.datetime) -> str | None:
    """ "From your email, today at 9:14 am: “Fwd: R07 rejections again”" and "From Teams, yesterday 7:02 pm"
    (reference/copy/Compose.md, L-DRAFT.channels)."""
    try:
        at = dt.datetime.fromisoformat(str(origin.get("received_at")))
    except ValueError:
        return None
    day, clock = labels.day(at, now), labels.clock(at)
    if channel == "email":
        subject = origin.get("subject")
        head = f"From your email, {day} at {clock}"
        return f"{head}: “{subject}”" if subject else head
    if channel == "teams":
        return f"From Teams, {day} {clock}"
    return None


def intake(conn: Conn, arrival: Arrival) -> dict[str, Any]:
    """One arrival: a draft (`{"draft_id", "run_id"}`), or `{"bounced": true, "reason_code": …}` for a sender who
    is not an employee. Raises ChannelOff while the channel is off."""
    switch = SWITCH.get(arrival.channel)
    if switch is None:
        raise DraftError(400, "channel_invalid", field="channel")
    if not killswitch.is_on(switch, conn):
        raise ChannelOff(switch)
    owner = _sender(conn, arrival.sender)
    if owner is None:
        log.info("intake.bounced", channel_code=arrival.channel, reason_code="unknown_sender")
        return {"bounced": True, "reason_code": "unknown_sender"}
    if arrival.received_at.tzinfo is None:
        raise DraftError(400, "received_at_invalid")
    from draft import store

    origin: dict[str, Any] = {"received_at": arrival.received_at.isoformat()}
    if arrival.subject:
        origin["subject"] = adapters.hide_message(arrival.subject[:SUBJECT_MAX]).masked
        origin["note"] = origin["subject"]
    if arrival.thread:
        origin["thread"] = adapters.hide_message(arrival.thread[:THREAD_MAX]).masked
    device = Device(None, None)
    with conn.transaction():  # one draft, its origin, its first message and the Inbox item, or nothing
        idea_uuid, _ = store.create(conn, owner, device, channel=arrival.channel)
        conn.execute(
            "UPDATE ideas SET origin_encrypted = %s WHERE id = %s",
            (
                seal_text("ideas", "origin_encrypted", idea_uuid, json.dumps(origin, ensure_ascii=False)),
                idea_uuid,
            ),
        )
        _, run_id = _add(conn, owner, idea_uuid, device, text=arrival.note, via=arrival.channel,
                         text_en=arrival.note_en)  # fmt: skip
        _kept(conn, owner, idea_uuid, arrival.channel)
    log.info("intake.kept", channel_code=arrival.channel, idea_uuid=idea_uuid, run_id=run_id)
    return {"draft_id": idea_uuid, "run_id": run_id}


def _kept(conn: Conn, owner: Owner, idea_uuid: str, channel: str) -> None:
    """The Inbox item "kept your draft from your email" with "Check and send" (L-DRAFT.channels, L-NOTIFY)."""
    from notify import Action, post

    post(
        conn,
        "draft_kept",
        [owner.user_id],
        idea_id=idea_uuid,
        actions=(Action("Check and send", style="primary", to=f"/share/{idea_uuid}"),),
        refs={"channel": channel},
        dedupe_key=f"draft_kept:{idea_uuid}",
    )
