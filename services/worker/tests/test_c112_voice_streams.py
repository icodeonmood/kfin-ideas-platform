"""BLD-C112 (DEC-108 (1), (2); L-DRAFT.voice; J-SHARE/3 "By voice"; J-RESUME/1): drafts by voice, streamed through
the worker. The logic runs against an in-memory store and the fake or a local fake Sarvam, so no stack is needed;
the SQL itself is covered by the stack tests at the end (marked stack)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any, ClassVar

import httpx
import pytest

from core.config import get_settings
from core.crypto import decrypt_bytes, decrypt_json
from gateway import sarvam, speech
from speech import drafts
from tests.sarvam_fakes import FakeSarvamWs, MeterConn, configure, ws_server
from voice.service import Limits

IDEA = "11111111-2222-4333-8444-555555555555"
ME = "CTR-a1b2c3"
PAN = "ABCPE1234F"  # synthetic
SECOND = bytes(drafts.BYTES_PER_SECOND)


class MemStore(drafts.Store):
    """The Store's contract, in memory."""

    rows: ClassVar[dict[str, dict[str, Any]]] = {}
    ideas: ClassVar[dict[str, tuple[str, str]]] = {}
    this_hour: int = 0

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def owned_draft(self, idea_uuid: str, by_code: str) -> str:
        found = self.ideas.get(idea_uuid)
        if found is None or found[1] != by_code:
            return "not_found"
        return "draft" if found[0] == "draft" else "not_a_draft"

    def begin(self, stream_id: str, idea_uuid: str, by_code: str, per_hour: int) -> bool:
        if MemStore.this_hour >= per_hour:
            return False
        MemStore.this_hour += 1
        self.rows[stream_id] = {
            "id": stream_id, "idea_uuid": idea_uuid, "by_code": by_code, "state": "live", "failure": None,
            "ended_by": None, "speech_seconds": 0, "chunk_count": 0, "lang": None, "own_words_sealed": None,
            "masked_encrypted": None, "text_en_encrypted": None, "translated": None, "spans": [],
            "hidden_count": 0, "handed_at": None,
        }  # fmt: skip
        return True

    def live_of(self, by_code: str) -> list[str]:
        return [k for k, r in self.rows.items() if r["by_code"] == by_code and r["state"] == "live"]

    def row(self, stream_id: str) -> dict[str, Any] | None:
        return dict(self.rows[stream_id]) if stream_id in self.rows else None

    def done(self, stream_id: str, v: dict[str, Any]) -> None:
        r = self.rows[stream_id]
        if r["state"] != "live":
            return
        r.update(
            state="done", ended_by=v["ended_by"], speech_seconds=v["seconds"], chunk_count=v["chunks"],
            lang=v["lang"], own_words_sealed=v["own_words_sealed"], masked_encrypted=v["masked_encrypted"],
            text_en_encrypted=v["text_en_encrypted"], translated=v["translated"], spans=v["spans"],
            hidden_count=v["hidden_count"], failure=v.get("failure"),
        )  # fmt: skip

    def failed(self, stream_id: str, code: str, ended_by: str | None, seconds: float, chunks: int) -> None:
        r = self.rows[stream_id]
        if r["state"] == "live":
            r.update(
                state="failed", failure=code, ended_by=ended_by, speech_seconds=seconds, chunk_count=chunks
            )

    def handed(self, stream_id: str) -> None:
        self.rows[stream_id].update(
            handed_at="now", own_words_sealed=None, masked_encrypted=None, text_en_encrypted=None
        )


class Clock:
    t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv("VAULT_ENCRYPTION_KEY", "t" * 40)  # synthetic, tests only
    configure(monkeypatch, SPEECH_MODE="fake")
    MemStore.rows, MemStore.ideas, MemStore.this_hour = {}, {IDEA: ("draft", ME)}, 0
    switches = {"capture.voice": True}
    refer: dict[str, str | None] = {"value": None}
    clock = Clock()
    monkeypatch.setattr(drafts, "_store", MemStore)
    monkeypatch.setattr(drafts, "_clock", clock)
    monkeypatch.setattr(drafts, "_ensure_reaper", lambda: None)
    monkeypatch.setattr(drafts.killswitch, "is_on", lambda name, conn=None: switches.get(name, False))
    monkeypatch.setattr(drafts.prefs, "refer_as", lambda conn, user_id: refer["value"])
    monkeypatch.setattr("voice.service.limits", lambda: Limits(max_waiting=3, max_per_hour=10))
    drafts._live.clear()
    yield {"switches": switches, "refer": refer, "clock": clock, "conn": MeterConn()}
    drafts._live.clear()
    monkeypatch.setattr(sarvam, "_transport", None)
    get_settings.cache_clear()


def say(words: str) -> bytes:
    pcm = speech.FAKE_MARKER + words.encode() + b"\0"
    return pcm + bytes(len(pcm) % 2)


def started(conn: Any) -> str:
    return str(drafts.start(conn, idea_uuid=IDEA, by_code=ME, user_id="u-1")["id"])


def test_BLD_C112_a_note_streams_and_ends_with_own_words_masked_copy_and_english(env: dict[str, Any]) -> None:
    conn = env["conn"]
    body = drafts.start(conn, idea_uuid=IDEA, by_code=ME, user_id="u-1")
    assert body["encoding"] == "pcm_s16le" and body["sample_rate"] == 16000 and body["max_seconds"] == 180
    sid = body["id"]
    first = drafts.chunk(
        conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say(f"Investor PAN {PAN} redemption stuck")
    )
    assert first["state"] == "live" and PAN in first["text"]  # the person's own words, to them alone
    assert first["spans"] == [{"start": 13, "end": 23, "kind": "pan"}]
    done = drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert done["state"] == "done" and done["text"] == f"Investor PAN {PAN} redemption stuck"
    assert done["text_en"] == "Investor PAN PAN ••••4F redemption stuck"  # masked again as it returns
    assert done["text_en_label"] == "Typed up in English" and done["hidden_count"] == 1
    row = MemStore.rows[sid]
    assert (
        decrypt_bytes(row["own_words_sealed"], f"voice_streams.own_words:{sid}", kind="vault").decode()
        == done["text"]
    )
    masked = decrypt_json(row["masked_encrypted"], f"voice_streams.masked:{sid}")["text"]
    assert PAN not in masked and "••••4F" in masked
    assert conn.calls[-1]["call"] == "stt_stream" and conn.calls[-1]["ref_id"] == sid


def test_BLD_C112_voice_to_message_hands_the_note_over_once(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say(f"Folio 12345678 PAN {PAN}"))
    drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert drafts.voice_to_message(conn, sid, idea_uuid=IDEA, by_code="CTR-other") is None
    msg = drafts.voice_to_message(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert msg is not None and msg.via == "voice" and msg.stream_id == sid
    assert (
        PAN in msg.text and PAN not in msg.text_masked and msg.text_en is not None and PAN not in msg.text_en
    )
    assert msg.text_en_label == "Typed up in English"
    assert MemStore.rows[sid]["own_words_sealed"] is None  # the held copies went with the hand-over
    assert drafts.voice_to_message(conn, sid, idea_uuid=IDEA, by_code=ME) is None
    assert drafts.status(conn, sid, idea_uuid=IDEA, by_code=ME)["state"] == "handed"


def test_BLD_C112_chunks_are_numbered_retries_are_not_sent_twice(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=SECOND)
    again = drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=SECOND)
    assert again["next_seq"] == 1 and again["seconds"] == 1.0  # counted once
    with pytest.raises(drafts.VoiceRefused) as exc:
        drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=3, data=SECOND)
    assert (exc.value.status, exc.value.code, exc.value.body) == (409, "chunk_out_of_order", {"next_seq": 1})


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        (b"", 400, "chunk_empty"),
        (bytes(3), 400, "not_pcm"),
        (bytes(drafts.MAX_CHUNK_BYTES + 2), 413, "chunk_too_large"),
    ],
)
def test_BLD_C112_a_chunk_must_be_pcm_and_about_a_second(
    env: dict[str, Any], data: bytes, status: int, code: str
) -> None:
    sid = started(env["conn"])
    with pytest.raises(drafts.VoiceRefused) as exc:
        drafts.chunk(env["conn"], sid, idea_uuid=IDEA, by_code=ME, seq=0, data=data)
    assert (exc.value.status, exc.value.code) == (status, code)


def test_BLD_C112_three_minutes_is_counted_from_the_bytes_and_ends_the_note(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    live = drafts._live[sid]
    two = SECOND * 2
    seq = 0
    body: dict[str, Any] = {}
    while body.get("state") != "failed" and body.get("state") != "done":
        body = drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=seq, data=two)
        seq += 1
    assert live.bytes == 180 * drafts.BYTES_PER_SECOND  # nothing past the cap was relayed
    assert body["ended_by"] == "limit" and sid not in drafts._live


@pytest.mark.parametrize(
    ("idea", "by", "status", "code"),
    [(IDEA, "CTR-other", 404, "not_found"), ("99999999-2222-4333-8444-555555555555", ME, 404, "not_found")],
)
def test_BLD_C112_only_the_sharer_on_their_own_draft(
    env: dict[str, Any], idea: str, by: str, status: int, code: str
) -> None:
    with pytest.raises(drafts.VoiceRefused) as exc:
        drafts.start(env["conn"], idea_uuid=idea, by_code=by)
    assert (exc.value.status, exc.value.code) == (status, code)


def test_BLD_C112_a_sent_idea_is_not_a_draft(env: dict[str, Any]) -> None:
    MemStore.ideas[IDEA] = ("with_review_desk", ME)
    with pytest.raises(drafts.VoiceRefused) as exc:
        drafts.start(env["conn"], idea_uuid=IDEA, by_code=ME)
    assert (exc.value.status, exc.value.code) == (409, "not_a_draft")


def test_BLD_C112_capture_voice_off_and_the_hourly_limit_refuse_a_start(env: dict[str, Any]) -> None:
    env["switches"]["capture.voice"] = False
    with pytest.raises(drafts.VoiceRefused) as exc:
        started(env["conn"])
    assert (exc.value.status, exc.value.code) == (503, "voice_paused")
    env["switches"]["capture.voice"] = True
    MemStore.this_hour = 10
    with pytest.raises(drafts.VoiceRefused) as exc:
        started(env["conn"])
    assert (exc.value.status, exc.value.code) == (429, "too_many_this_hour")


def test_BLD_C112_switched_off_mid_note_ends_it_and_keeps_the_words(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say("Forms typed twice"))
    env["switches"]["capture.voice"] = False
    with pytest.raises(drafts.VoiceRefused) as exc:
        drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=1, data=SECOND)
    assert exc.value.status == 503 and exc.value.code == "voice_paused"
    assert exc.value.body["state"] == "done" and exc.value.body["ended_by"] == "paused"
    assert exc.value.body["text"] == "Forms typed twice"


def test_BLD_C112_a_person_who_leaves_keeps_what_was_heard(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say("Started on the phone"))
    env["clock"].t += drafts.IDLE_S - 1
    assert drafts.reap(conn) == 0
    env["clock"].t += 1
    assert drafts.reap(conn) == 1  # J-RESUME/1: the tab closed or the signal dropped
    view = drafts.status(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert view["state"] == "done" and view["ended_by"] == "idle" and view["text"] == "Started on the phone"


def test_BLD_C112_a_new_start_ends_the_persons_other_live_note(env: dict[str, Any]) -> None:
    conn = env["conn"]
    first = started(conn)
    drafts.chunk(conn, first, idea_uuid=IDEA, by_code=ME, seq=0, data=say("On the laptop"))
    second = started(conn)
    assert first not in drafts._live and second in drafts._live
    assert MemStore.rows[first]["ended_by"] == "replaced" and MemStore.rows[first]["state"] == "done"


def test_BLD_C112_ending_twice_gives_the_same_answer_and_nothing_heard_fails(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=SECOND)
    first = drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert first == {"id": sid, "state": "failed", "failure": "nothing_heard", "ended_by": "person"}
    assert drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME) == first


def test_BLD_C112_a_stream_lost_to_a_restart_says_so(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts._live.clear()  # the worker restarted
    with pytest.raises(drafts.VoiceRefused) as exc:
        drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=SECOND)
    assert (exc.value.status, exc.value.code) == (410, "stream_lost")


@pytest.mark.parametrize(
    ("choice", "gender"), [("she", "Female"), ("he", "Male"), ("they", None), (None, None)]
)
def test_BLD_C112_through_sarvam_the_translation_follows_the_persons_choice(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch, choice: str | None, gender: str | None
) -> None:
    configure(monkeypatch, SPEECH_MODE="sarvam")
    env["refer"]["value"] = choice
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(
            200, json={"translated_text": "The SIP form is typed twice.", "source_language_code": "hi-IN"}
        )

    monkeypatch.setattr(sarvam, "_transport", httpx.MockTransport(handle))
    conn = env["conn"]
    with ws_server(monkeypatch, FakeSarvamWs(heard="SIP form do baar type hota hai")) as fake:
        sid = started(conn)
        drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=SECOND)
        drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=1, data=SECOND)
        done = drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert bytes(fake.audio) == SECOND * 2  # relayed as is
    assert (
        done["text"] == "SIP form do baar type hota hai"
        and done["lang"] == "hi-IN"
        and done["language"] == "Hindi"
    )
    assert done["text_en"] == "The SIP form is typed twice." and done["translated"] is True
    body = httpx.Request("POST", "/", content=sent[0].content).read()
    import json

    sent_body = json.loads(body)
    assert sent_body["source_language_code"] == "hi-IN" and sent_body["mode"] == "code-mixed"
    assert sent_body.get("speaker_gender") == gender
    assert done["summary"] == "Voice message, 2 seconds, in Hindi"
    assert [c["call"] for c in conn.calls] == ["stt_stream", "translate"]
    assert conn.calls[0]["seconds"] == 2.0


def test_BLD_C112_a_failed_translation_keeps_the_persons_words(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*a: Any, **k: Any) -> Any:
        raise sarvam.SarvamFailed("hosted_503")

    monkeypatch.setattr(sarvam, "translate", broken)
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say("Form do baar"))
    drafts._live[sid].stream._language = "hi-IN"  # heard as Hindi: translated
    done = drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert done["state"] == "done" and done["text"] == "Form do baar" and done["text_en"] is None
    assert done["translation_failure"] == "translation_hosted_503"


def test_BLD_C112_english_is_its_own_english_copy(env: dict[str, Any]) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say(f"PAN {PAN} again"))
    done = drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    assert (
        done["lang"] == "en-IN" and done["translated"] is False and done["text_en"] == "PAN PAN ••••4F again"
    )


def test_BLD_C112_summary_reads_like_the_ways_copy() -> None:
    assert drafts.summary(72, "te-IN") == "Voice message, 1 minute 12 seconds, in Telugu"
    assert drafts.summary(120, None) == "Voice message, 2 minutes"
    assert drafts.summary(1, "hi-IN") == "Voice message, 1 second, in Hindi"


def test_BLD_C116_the_notice_names_no_vendor_and_the_contract_is_pcm() -> None:
    assert drafts.NOTICE == (
        "Your voice note goes to an Indian speech service to turn it into text. You can check the text before you send it."
    )
    assert "sarvam" not in drafts.NOTICE.lower()
    c = drafts.chunk_contract()
    assert (c["encoding"], c["sample_rate"], c["channels"], c["max_chunk_bytes"]) == (
        "pcm_s16le",
        16000,
        1,
        64000,
    )


def test_BLD_C112_no_words_in_the_logs(env: dict[str, Any], captured_logs: io.StringIO) -> None:
    conn = env["conn"]
    sid = started(conn)
    drafts.chunk(conn, sid, idea_uuid=IDEA, by_code=ME, seq=0, data=say(f"Secret PAN {PAN} words"))
    drafts.end(conn, sid, idea_uuid=IDEA, by_code=ME)
    logged = captured_logs.getvalue()
    assert sid in logged and PAN not in logged and "Secret" not in logged


# ---- the SQL, against the running stack ---------------------------------------------------------------------


@pytest.mark.stack
def test_BLD_C112_the_store_against_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.db import connect
    from tests.web import people

    configure(monkeypatch, SPEECH_MODE="fake")
    monkeypatch.setattr(drafts.killswitch, "is_on", lambda name, conn=None: True)
    with connect(autocommit=True) as db, people(db) as make:
        person = make()
        idea = db.execute(
            "INSERT INTO ideas (contributor_code, status) VALUES (%s, 'draft') RETURNING id",
            (person.contributor_code,),
        ).fetchone()
        idea_uuid = str(idea["id"])
        sid = str(
            drafts.start(db, idea_uuid=idea_uuid, by_code=person.contributor_code, user_id=person.user_id)[
                "id"
            ]
        )
        drafts.chunk(
            db, sid, idea_uuid=idea_uuid, by_code=person.contributor_code, seq=0, data=say(f"PAN {PAN}")
        )
        done = drafts.end(db, sid, idea_uuid=idea_uuid, by_code=person.contributor_code)
        assert done["state"] == "done" and PAN in done["text"]
        row = db.execute(
            "SELECT state, spans, hidden_count FROM voice_streams WHERE id = %s", (sid,)
        ).fetchone()
        assert row["state"] == "done" and row["hidden_count"] == 1
        msg = drafts.voice_to_message(db, sid, idea_uuid=idea_uuid, by_code=person.contributor_code)
        assert msg is not None and PAN not in msg.text_masked
        held = db.execute("SELECT own_words_sealed FROM voice_streams WHERE id = %s", (sid,)).fetchone()
        assert held["own_words_sealed"] is None
