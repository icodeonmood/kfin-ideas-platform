"""S-R3's "Say your answer" (BLD-B276; DEC-108, DEC-120; L-QUESTIONS.answer/1, C-PROMPT.voice): the sharer speaks an
answer to the review desk, and their own words go into the answer box, where they read, edit and save them like
typed text (the box's autosave, `asking.save_answer`, masks them as it masks typing).

Lane C's stream does the work (`speech.drafts`): `_open` after this module's own check, then lane C's `chunk`, `end`
and `status` with the idea's uuid and the person's code. Only two things differ from a draft's note:

- **Who may speak** is checked on every request, as `save_answer` checks a save: the question's set is sent and not
  closed, the idea is shared, the caller is one of its sharers (`_sharer_code`, so a credited co-sharer too) and the
  code they speak as is their own; the answer is not sent, and no co-sharer's draft with words in it holds it.
  Anything else is lane C's `VoiceRefused`: 404 `not_found` (a bad id, a queued set, a draft idea, not a sharer) or
  409 `set_closed`, `answer_sent`, `answer_in_progress`. A read: no row is locked.
- **No English copy** (`english=False`): the words go only into the person's own box, so nothing goes to translation
  and no vault tags are made (data minimisation, agreed with lane C on 21 Nov).

What the stream row keeps (the person's own words, sealed, and the masked copy) is cleared by lane C's sweep 24 hours
on, as for a draft's note: `Store.sweep` reads `delete_after` only, whatever the idea's status. One live stream per
person: an answer's stream ends that person's live draft stream ("replaced").

Nothing here logs text or audio: lane C's module logs the stream's id, counts and codes only (non-negotiable 3).
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from desk.asking import _empty_draft, _sharer_code, _uuid
from desk.store import Refused, load_idea
from speech import drafts
from speech.drafts import VoiceRefused


def _not_found() -> VoiceRefused:
    return VoiceRefused(404, "not_found")


def _check(conn: Conn, question_id: str, user_id: str, by_code: str) -> str:
    """The idea's uuid when `user_id`, speaking as `by_code`, may answer this question now; refused as
    `asking.save_answer` refuses a save, in lane C's `VoiceRefused`."""
    try:
        qid = _uuid(question_id)
        _uuid(user_id)  # someone with no account id is nobody's sharer
    except Refused:
        raise _not_found() from None
    q = conn.execute(
        "SELECT q.id, s.idea_uuid, s.state FROM questions q JOIN question_sets s ON s.id = q.set_id WHERE q.id = %s",
        (qid,),
    ).fetchone()
    if q is None or q["state"] == "queued":
        raise _not_found()
    try:
        idea = load_idea(conn, str(q["idea_uuid"]))  # a draft idea is not found
        code = _sharer_code(conn, idea, user_id)
    except Refused:
        raise _not_found() from None
    if code != by_code:
        raise _not_found()
    if q["state"] == "closed":
        raise VoiceRefused(409, "set_closed")
    answer = conn.execute(
        "SELECT id, by_code, sent_at, text_encrypted FROM answers WHERE question_id = %s", (qid,)
    ).fetchone()
    if answer is not None and answer["sent_at"] is not None:
        raise VoiceRefused(409, "answer_sent")
    if answer is not None and answer["by_code"] != code and not _empty_draft(conn, dict(answer)):
        raise VoiceRefused(409, "answer_in_progress")
    return str(idea["id"])


def start_for_answer(conn: Conn, question_id: str, *, user_id: str, by_code: str) -> dict[str, Any]:
    """`POST /internal/answer-voice-streams`: open a stream for the person's answer, with no English copy."""
    idea_uuid = _check(conn, question_id, user_id, by_code)
    return drafts._open(conn, idea_uuid=idea_uuid, by_code=by_code, user_id=user_id, english=False)


def chunk_for_answer(
    conn: Conn, stream_id: str, question_id: str, *, user_id: str, by_code: str, seq: int, data: bytes
) -> dict[str, Any]:
    idea_uuid = _check(conn, question_id, user_id, by_code)
    return drafts.chunk(conn, stream_id, idea_uuid=idea_uuid, by_code=by_code, seq=seq, data=data)


def end_for_answer(
    conn: Conn, stream_id: str, question_id: str, *, user_id: str, by_code: str
) -> dict[str, Any]:
    idea_uuid = _check(conn, question_id, user_id, by_code)
    return drafts.end(conn, stream_id, idea_uuid=idea_uuid, by_code=by_code)


def status_for_answer(
    conn: Conn, stream_id: str, question_id: str, *, user_id: str, by_code: str
) -> dict[str, Any]:
    idea_uuid = _check(conn, question_id, user_id, by_code)
    return drafts.status(conn, stream_id, idea_uuid=idea_uuid, by_code=by_code)
