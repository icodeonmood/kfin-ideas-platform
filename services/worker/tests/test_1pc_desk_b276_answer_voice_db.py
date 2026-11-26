"""BLD-B276 (DEC-108, DEC-120; L-QUESTIONS.answer/1, C-PROMPT.voice): S-R3's "Say your answer", lane C's stream for an
answer to the review desk (`desk.answer_voice`). Against the test database, with lane C's fake stream (`sarvam.FakeStream`,
heard as Hindi so a draft's note would be translated) in place of Sarvam's, and metering and the reaper switched off:

- who may open a stream, refused exactly as `asking.save_answer` refuses a save;
- chunk, end and status refuse anyone but the question's sharer, on every request;
- an answer's stream never makes an English copy: nothing goes to translation, `text_en_encrypted` is None and
  `translated` is False;
- the words a stream keeps are cleared by lane C's sweep 24 hours on, though the idea is not a draft;
- a saved, unsent answer is seen by its sharer alone (the desk's page, the idea page's answers, a co-sharer's read);
- lane C's `start` still answers 503 before 404 or 409, still refuses a shared idea, and `_open` refuses when
  `capture.voice` is off.

Synthetic people and words only (non-negotiable 11); lane B's fixtures remove every idea and person made, and the
streams go with their idea."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import answer_voice as av
from desk import asking, reads
from gateway import sarvam, speech
from speech import drafts
from speech.drafts import VoiceRefused
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)
from tests.sarvam_fakes import configure
from voice.service import Limits

NOW = f.at(16, 13)  # Monday 16 November 2026, 1 pm IST
QS: list[dict[str, Any]] = [
    {"part": "evidence", "text": "Can you add the call log for the whole of November?"},
    {"part": "often", "text": "Is it 40 calls a day at one branch, or across Hyderabad?"},
]
WORDS = "Only our Hyderabad branch, the other branches say the same"  # no spoken numbers to normalise


class HindiStream(sarvam.FakeStream):
    """Lane C's fake stream, heard as Hindi: a draft's note in Hindi is translated, so an answer's must not be."""

    def send(self, pcm: bytes) -> None:
        super().send(pcm)
        self._language = "hi-IN"


def say(words: str) -> bytes:
    pcm = speech.FAKE_MARKER + words.encode() + b"\0"
    return pcm + bytes(len(pcm) % 2)


@pytest.fixture
def env(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, bool]]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    configure(monkeypatch, SPEECH_MODE="fake")  # sets the env and clears the settings cache
    switches: dict[str, bool] = {}
    monkeypatch.setattr(drafts.killswitch, "is_on", lambda name, conn=None: switches.get(name, True))
    monkeypatch.setattr(sarvam, "stt_stream", lambda **k: HindiStream())
    monkeypatch.setattr(sarvam, "meter", lambda *a, **k: None)
    monkeypatch.setattr(drafts, "_ensure_reaper", lambda: None)
    monkeypatch.setattr("voice.service.limits", lambda: Limits(max_waiting=3, max_per_hour=10))
    f.install_fake_notify(monkeypatch)
    monkeypatch.setattr("convo.adapters.notify_post", lambda conn, kind, recipients, **kw: None)
    drafts._live.clear()
    yield switches
    drafts._live.clear()
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, env: dict[str, bool]) -> dict[str, Any]:
    _ = env
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    idea = f.idea(db, kavya)
    sent = asking.send_set(
        db, idea["idea_id"], meera["id"], {"questions": QS, "time_to_answer": "3d"}, f.at(16, 9)
    )
    return {
        "kavya": kavya, "ravi": f.person(db, "Ravi Nair"), "meera": meera, "idea": idea, "set": sent,
        "q1": sent["questions"][0]["id"], "q2": sent["questions"][1]["id"],
    }  # fmt: skip


def refused(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[int, str]:
    with pytest.raises(VoiceRefused) as exc:
        fn(*args, **kwargs)
    return exc.value.status, exc.value.code


def as_(who: dict[str, str]) -> dict[str, str]:
    return {"user_id": who["id"], "by_code": who["code"]}


def streams_of(db: Conn, code: str) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute("SELECT * FROM voice_streams WHERE by_code = %s", (code,)).fetchall()]


def no_english(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("an answer's stream made an English copy")


# ---- who may speak an answer ---------------------------------------------------------------------------------------
def test_BLD_B276_start_for_answer_refuses_as_save_answer_does(db: Conn, cast: dict[str, Any]) -> None:
    kavya, ravi, q1, q2 = cast["kavya"], cast["ravi"], cast["q1"], cast["q2"]
    idea, set_id = cast["idea"], cast["set"]["id"]
    start = av.start_for_answer
    assert refused(start, db, "not-a-question", **as_(kavya)) == (404, "not_found")
    assert refused(start, db, str(uuid.uuid4()), **as_(kavya)) == (404, "not_found")
    assert refused(start, db, q1, user_id="", by_code=kavya["code"]) == (404, "not_found")
    assert refused(start, db, q1, **as_(ravi)) == (404, "not_found")  # not a sharer of the idea
    assert refused(start, db, q1, user_id=kavya["id"], by_code=ravi["code"]) == (
        404,
        "not_found",
    )  # not her code
    db.execute("UPDATE question_sets SET state = 'queued' WHERE id = %s", (set_id,))
    assert refused(start, db, q1, **as_(kavya)) == (404, "not_found")
    db.execute("UPDATE question_sets SET state = 'closed' WHERE id = %s", (set_id,))
    assert refused(start, db, q1, **as_(kavya)) == (409, "set_closed")
    db.execute("UPDATE question_sets SET state = 'sent' WHERE id = %s", (set_id,))
    was = db.execute("SELECT status FROM ideas WHERE id = %s", (idea["id"],)).fetchone()
    assert was is not None
    db.execute("UPDATE ideas SET status = 'draft' WHERE id = %s", (idea["id"],))
    assert refused(start, db, q1, **as_(kavya)) == (404, "not_found")
    db.execute("UPDATE ideas SET status = %s WHERE id = %s", (was["status"], idea["id"]))
    # a co-sharer's draft with words in it holds question 2
    db.execute(
        "INSERT INTO answers (id, question_id, by_code, text_encrypted, added_to, saved_at) "
        "VALUES (%s, %s, %s, %s, 'often', now())",
        (str(uuid.uuid4()), q2, ravi["code"], b"sealed-synthetic"),
    )
    assert refused(start, db, q2, **as_(kavya)) == (409, "answer_in_progress")
    db.execute("DELETE FROM answers WHERE question_id = %s", (q2,))
    # question 1 answered and sent
    asking.save_answer(db, q1, kavya["id"], "Our Hyderabad branch alone.", [], f.at(16, 10))
    asking.send_answers(db, set_id, kavya["id"], f.at(16, 11))
    assert refused(start, db, q1, **as_(kavya)) == (409, "answer_sent")
    assert streams_of(db, kavya["code"]) == [] and drafts._live == {}  # nothing was opened
    # question 2 is still hers to answer
    opened = start(db, q2, **as_(kavya))
    assert opened["state"] == "live" and opened["encoding"] == "pcm_s16le"
    [row] = streams_of(db, kavya["code"])
    assert str(row["id"]) == opened["id"] and str(row["idea_uuid"]) == str(idea["id"])


# ---- the stream: the person's own words, and no English copy -------------------------------------------------------
def test_BLD_B276_an_answer_stream_gives_the_words_and_never_calls_translation(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drafts, "_english", no_english)
    monkeypatch.setattr(sarvam, "translate", no_english)
    monkeypatch.setattr(sarvam, "tag_for_service", no_english)
    kavya, q1 = cast["kavya"], cast["q1"]
    sid = av.start_for_answer(db, q1, **as_(kavya))["id"]
    heard = av.chunk_for_answer(db, sid, q1, **as_(kavya), seq=0, data=say(WORDS))
    assert heard["state"] == "live" and heard["text"] == WORDS
    assert av.status_for_answer(db, sid, q1, **as_(kavya))["text"] == WORDS
    done = av.end_for_answer(db, sid, q1, **as_(kavya))
    assert done["state"] == "done" and done["text"] == WORDS and done["lang"] == "hi-IN"
    assert done["text_en"] is None and done["translated"] is False and done["translation_failure"] is None
    row = db.execute("SELECT * FROM voice_streams WHERE id = %s", (sid,)).fetchone()
    assert row is not None
    assert row["text_en_encrypted"] is None and row["translated"] is False and row["failure"] is None
    assert row["own_words_sealed"] is not None  # theirs, until the sweep
    again = av.status_for_answer(db, sid, q1, **as_(kavya))
    assert again["state"] == "done" and again["text"] == WORDS and again["text_en"] is None


def test_BLD_B276_chunk_end_and_status_refuse_anyone_but_the_questions_sharer(
    db: Conn, cast: dict[str, Any]
) -> None:
    kavya, ravi, q1 = cast["kavya"], cast["ravi"], cast["q1"]
    # Ravi shares an idea of his own, with a question of his own, and tries Kavya's stream through it
    his = f.idea(db, ravi, title="Courier slips are signed twice")
    his_q = asking.send_set(
        db, his["idea_id"], cast["meera"]["id"], {"questions": QS[:1], "time_to_answer": "3d"}, f.at(16, 9)
    )["questions"][0]["id"]
    sid = av.start_for_answer(db, q1, **as_(kavya))["id"]
    for who, q in ((ravi, q1), ({"id": ravi["id"], "code": kavya["code"]}, q1), (ravi, his_q)):
        assert refused(av.chunk_for_answer, db, sid, q, **as_(who), seq=0, data=say(WORDS)) == (
            404,
            "not_found",
        )
        assert refused(av.status_for_answer, db, sid, q, **as_(who)) == (404, "not_found")
        assert refused(av.end_for_answer, db, sid, q, **as_(who)) == (404, "not_found")
    assert av.chunk_for_answer(db, sid, q1, **as_(kavya), seq=0, data=say(WORDS))["text"] == WORDS
    assert av.end_for_answer(db, sid, q1, **as_(kavya))["state"] == "done"


# ---- the words the stream keeps -------------------------------------------------------------------------------------
def test_BLD_B276_lane_c_sweep_clears_an_answer_streams_words(db: Conn, cast: dict[str, Any]) -> None:
    """`Store.sweep` reads `delete_after` only: an answer's stream (its idea is shared, not a draft) is cleared too."""
    kavya, q1 = cast["kavya"], cast["q1"]
    sid = av.start_for_answer(db, q1, **as_(kavya))["id"]
    av.chunk_for_answer(db, sid, q1, **as_(kavya), seq=0, data=say(WORDS))
    av.end_for_answer(db, sid, q1, **as_(kavya))
    db.execute("UPDATE voice_streams SET delete_after = now() - interval '1 minute' WHERE id = %s", (sid,))
    assert drafts.sweep(db) >= 1
    row = db.execute("SELECT * FROM voice_streams WHERE id = %s", (sid,)).fetchone()
    assert row is not None
    assert (row["own_words_sealed"], row["masked_encrypted"], row["text_en_encrypted"]) == (None, None, None)
    assert av.status_for_answer(db, sid, q1, **as_(kavya))["state"] == "expired"


# ---- before the gatekeeper: a saved answer is its sharer's alone until sent ----------------------------------------
def test_BLD_B276_a_saved_unsent_answer_is_seen_by_its_sharer_alone(db: Conn, cast: dict[str, Any]) -> None:
    """The box's words are saved as typed (patterns only; the gatekeeper runs on send), so nobody else reads them
    before then: not the review desk's page (S-R2), not the idea page's answers, not a co-sharer's read of the set."""
    kavya, idea, q1 = cast["kavya"], cast["idea"], cast["q1"]
    asking.save_answer(db, q1, kavya["id"], WORDS, [], f.at(16, 10))
    page = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], NOW)
    assert WORDS not in json.dumps(page, default=str)
    assert WORDS not in json.dumps(asking.answers_by_part(db, idea["id"]), default=str)
    s = db.execute("SELECT * FROM question_sets WHERE id = %s", (cast["set"]["id"],)).fetchone()
    assert s is not None
    for viewer in (None, cast["ravi"]["code"]):  # the desk, and anyone credited but not its writer
        read = asking._set_json(db, dict(s), idea, NOW, viewer_code=viewer)
        assert read["questions"][0]["answer"] is None, viewer
    mine = asking.open_set_for_sharer(db, idea["idea_id"], kavya["id"], NOW)
    assert mine is not None and mine["questions"][0]["answer"]["text"] == WORDS


# ---- lane C's start and _open, unchanged in what they refuse ---------------------------------------------------------
def test_BLD_B276_lane_c_start_still_answers_503_first_and_refuses_a_shared_idea(
    db: Conn, cast: dict[str, Any], env: dict[str, bool]
) -> None:
    kavya, idea = cast["kavya"], cast["idea"]
    env["capture.voice"] = False
    for target in (str(uuid.uuid4()), str(idea["id"])):  # 503 before 404 and before 409
        assert refused(drafts.start, db, idea_uuid=target, by_code=kavya["code"]) == (503, "voice_paused")
    env["capture.voice"] = True
    assert refused(drafts.start, db, idea_uuid=str(idea["id"]), by_code=kavya["code"]) == (409, "not_a_draft")
    assert refused(drafts.start, db, idea_uuid=str(uuid.uuid4()), by_code=kavya["code"]) == (404, "not_found")
    assert streams_of(db, kavya["code"]) == []


def test_BLD_B276_open_refuses_when_capture_voice_is_off(
    db: Conn, cast: dict[str, Any], env: dict[str, bool]
) -> None:
    kavya, idea = cast["kavya"], cast["idea"]
    env["capture.voice"] = False
    assert refused(
        drafts._open, db, idea_uuid=str(idea["id"]), by_code=kavya["code"], user_id=kavya["id"], english=False
    ) == (503, "voice_paused")
    assert refused(av.start_for_answer, db, cast["q1"], **as_(kavya)) == (503, "voice_paused")
    assert streams_of(db, kavya["code"]) == [] and drafts._live == {}
