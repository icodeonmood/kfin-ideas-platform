"""BLD-C114 (DEC-108 (4), L-LISTEN, C-LISTEN, J-REVIEW/2): Listen in Sarvam's voice from lane B's masked script.
Part by part in E-ENUMS.part order; chapters from each part's real audio length; cached per (script version,
voice); masked text only. No stack: the database and the store are faked; the SQL is a stack test at the end."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core.config import get_settings
from gateway import sarvam
from speech import adapters, listen
from tests.sarvam_fakes import FakeSarvamWs, MeterConn, configure, ws_server

IDEA = "11111111-2222-4333-8444-555555555555"
FRAME_S = 576 / 24000  # one silent MPEG-2 Layer III frame at 24 kHz


def script(version: str = "a1b2c3d4e5f60718", **texts: str) -> adapters.Script:
    titles = {"summary": "The problem", "often": "How often", "who": "Who it affects", "cost": "What it's worth",
              "evidence": "Attached", "fix": "Fix"}  # fmt: skip
    order = ("fix", "who", "summary", "evidence", "cost", "often")  # deliberately out of order
    return adapters.Script(
        parts=tuple(adapters.ScriptPart(p, titles[p], texts.get(p, f"Text for {p}."), None) for p in order),
        version=version,
    )


class Conn(MeterConn):
    """Metering rows plus the listen_cache and jobs statements."""

    def __init__(self) -> None:
        super().__init__()
        self.cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.jobs: list[tuple[Any, ...]] = []
        self.failures: dict[tuple[str, str, str], str] = {}
        self.locks: list[str] = []
        self.status = "with_review_desk"

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        from tests.sarvam_fakes import Result

        if sql.startswith("SELECT store_key, chapters"):
            row = self.cache.get(params)
            return Result(row)
        if sql.startswith("DELETE FROM listen_cache WHERE idea_uuid"):
            gone = [k for k in self.cache if k[0] == params[0] and k[1:] != params[1:]]
            rows = [{"store_key": self.cache.pop(k)["store_key"]} for k in gone]
            return _Rows(rows)
        if sql.startswith("INSERT INTO listen_cache"):
            idea, version, voice, _lang, key, chapters, duration, size = params
            self.cache[(idea, version, voice)] = {
                "store_key": key, "chapters": chapters.obj, "duration_s": duration, "byte_count": size,
            }  # fmt: skip
            return Result(None)
        if sql.startswith("INSERT INTO jobs"):
            self.jobs.append(params)
            return Result(None)
        if sql.startswith("SELECT id, status FROM ideas"):
            return Result({"id": IDEA, "status": self.status})
        if sql.startswith("SELECT pg_advisory_lock"):
            self.locks.append(f"lock {params[0]}")
            return Result(None)
        if sql.startswith("SELECT pg_advisory_unlock"):
            self.locks.append(f"unlock {params[0]}")
            return Result(None)
        if sql.startswith("SELECT 1 FROM listen_failures"):
            return Result({"x": 1} if tuple(params[:3]) in self.failures else None)
        if sql.startswith("INSERT INTO listen_failures"):
            self.failures[tuple(params[:3])] = params[3]
            return Result(None)
        return super().execute(sql, params)


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    configure(monkeypatch, SPEECH_MODE="fake")
    objects: dict[str, bytes] = {}
    monkeypatch.setattr(listen.store, "put", lambda b, k, d: objects.__setitem__(k, d))
    monkeypatch.setattr(listen.store, "get", lambda b, k: objects[k])
    monkeypatch.setattr(listen.store, "delete", lambda b, k: objects.pop(k, None))
    switches = {"desk.listen": True, "speech.hosted": True}
    monkeypatch.setattr(listen.killswitch, "is_on", lambda name, conn=None: switches.get(name, False))
    current = {"script": script()}
    monkeypatch.setattr(listen, "listen_script", lambda conn, ref, at=None: current["script"])
    yield {"objects": objects, "switches": switches, "current": current, "conn": Conn()}
    get_settings.cache_clear()


def test_BLD_C114_mp3_length_is_counted_from_frame_headers() -> None:
    assert listen.mp3_seconds(sarvam.fake_frames(10)) == pytest.approx(10 * FRAME_S)
    tag = b"ID3\x04\x00\x00\x00\x00\x00\x05" + b"x" * 5
    assert listen.mp3_seconds(tag + sarvam.fake_frames(3) + tag + sarvam.fake_frames(2)) == pytest.approx(
        5 * FRAME_S
    )
    with pytest.raises(ValueError):
        listen.mp3_seconds(b"not audio at all")


def test_BLD_C114_each_parts_tag_and_vbr_header_are_dropped() -> None:
    frames = sarvam.fake_frames(3)
    header = bytearray(sarvam.fake_frames(1))
    header[4 + 13 : 4 + 17] = b"Xing"  # where an encoder writes it, inside the first frame
    tag = b"ID3\x04\x00\x00\x00\x00\x00\x05" + b"x" * 5
    assert listen.strip_leading(tag + bytes(header) + frames) == frames
    assert listen.strip_leading(frames) == frames  # a plain first frame is audio and stays
    assert listen.strip_leading(tag[:8]) is None  # not enough yet to decide
    assert listen.strip_leading(tag[:8], final=True) == tag[:8]


def test_BLD_C114_parts_in_order_chapters_from_real_lengths_then_cached(env: dict[str, Any]) -> None:
    conn = env["conn"]
    s = env["current"]["script"]
    audio = b"".join(listen.speak(conn, IDEA, s))
    hit = listen.cached(conn, IDEA, s.version, "simran_en_customer")
    assert hit is not None and hit.byte_count == len(audio) == len(env["objects"][hit.store_key])
    parts = [c["part"] for c in hit.chapters]
    assert parts == ["summary", "often", "who", "cost", "evidence", "fix"]  # E-ENUMS.part order
    # Each part's length is what came back: the fake gives one frame per 4 characters of each sentence sent.
    lengths = [
        sum(max(1, len(m) // 4) for m in sarvam.sentences(adapters.spoken(p.title, p.text))) * FRAME_S
        for p in listen._ordered(s)
    ]
    starts = [round(sum(lengths[:i]), 2) for i in range(len(lengths))]
    assert [c["start_s"] for c in hit.chapters] == starts
    assert hit.duration_s == round(sum(lengths), 2)
    assert hit.view() == {"parts": hit.chapters, "duration_s": hit.duration_s}
    assert hit.store_key == f"listen/{IDEA}/{s.version}-simran_en_customer.mp3"
    # The second listen comes from the cache: no new synthesis.
    calls = len(conn.calls)
    assert b"".join(listen.speak(conn, IDEA, s)) == audio and len(conn.calls) == calls


def test_BLD_C114_a_new_script_version_replaces_the_old_audio(env: dict[str, Any]) -> None:
    conn = env["conn"]
    b"".join(listen.speak(conn, IDEA, script("1111111111111111")))
    old_key = next(iter(env["objects"]))
    b"".join(listen.speak(conn, IDEA, script("2222222222222222", summary="An answer was added.")))
    assert old_key not in env["objects"] and len(env["objects"]) == 1  # L-LISTEN/3
    assert list(conn.cache) == [(IDEA, "2222222222222222", "simran_en_customer")]


def test_BLD_C114_chapters_are_pending_until_cached_and_queue_a_prefetch(env: dict[str, Any]) -> None:
    conn = env["conn"]
    assert listen.chapters(conn, IDEA) is None
    assert conn.jobs and conn.jobs[0][1] == f"listen:{IDEA}"
    assert listen.prefetch(conn, IDEA) is True
    got = listen.chapters(conn, IDEA)
    assert got is not None and next(p["part"] for p in got["parts"]) == "summary" and got["duration_s"] > 0
    assert listen.prefetch(conn, IDEA) is False  # already cached


def test_BLD_C114_desk_listen_off_or_no_script_refuses(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    env["switches"]["desk.listen"] = False
    with pytest.raises(listen.ListenRefused) as exc:
        listen.prepare(env["conn"], IDEA)
    assert (exc.value.status, exc.value.code) == (503, "paused")
    env["switches"]["desk.listen"] = True

    def unavailable(conn: Any, ref: str, at: Any = None) -> Any:
        raise adapters.ScriptUnavailable("script_unavailable")

    monkeypatch.setattr(listen, "listen_script", unavailable)
    with pytest.raises(listen.ListenRefused) as exc:
        listen.prepare(env["conn"], IDEA)
    assert (exc.value.status, exc.value.code) == (503, "script_unavailable")
    assert listen.prefetch(env["conn"], IDEA) is False


def test_BLD_C114_a_bad_reference_is_not_found(env: dict[str, Any]) -> None:
    with pytest.raises(listen.ListenRefused) as exc:
        listen.prepare(env["conn"], "../etc")
    assert (exc.value.status, exc.value.code) == (404, "not_found")


@pytest.mark.parametrize("status", ["draft", "checking", "withdrawn", "merged"])
def test_BLD_C117_nobody_listens_to_a_draft_one_being_checked_withdrawn_or_merged(
    env: dict[str, Any], status: str
) -> None:
    env["conn"].status = status
    with pytest.raises(listen.ListenRefused) as exc:
        listen.prepare(env["conn"], IDEA)
    assert (exc.value.status, exc.value.code) == (404, "not_found")
    assert "checking" not in listen.DESK_STATUSES and set(listen.DESK_STATUSES) == {
        "with_review_desk",
        "needs_you",
    }


def test_BLD_C114_only_masked_text_is_read(env: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []

    def record(text: str, **k: Any) -> Iterator[bytes]:
        sent.append(text)
        yield sarvam.fake_frames(1)

    monkeypatch.setattr(sarvam, "tts", record)
    env["current"]["script"] = script(summary="Call the investor on 9876543210.")  # synthetic, unmasked
    b"".join(listen.speak(env["conn"], IDEA, env["current"]["script"]))
    assert not any("9876543210" in t for t in sent) and any("Phone ••••10" in t for t in sent)


def test_BLD_C114_through_sarvam_each_part_is_its_own_stream(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch, SPEECH_MODE="sarvam")
    conn = env["conn"]
    with ws_server(monkeypatch, FakeSarvamWs(tts_chunks=2)) as fake:
        audio = b"".join(listen.speak(conn, IDEA, script()))
    assert len(fake.paths) == 6 and audio == sarvam.fake_frames(10) * 12
    texts = [m["data"]["text"] for m in fake.received if m.get("type") == "text"]
    assert texts[0] == "The problem." and texts[1] == "Text for summary."
    hit = listen.cached(conn, IDEA, "a1b2c3d4e5f60718", "simran_en_customer")
    assert hit is not None and [c["start_s"] for c in hit.chapters] == [
        round(i * 20 * FRAME_S, 2) for i in range(6)
    ]
    assert [c["call"] for c in conn.calls] == ["tts"] * 6


@pytest.mark.parametrize(
    ("header", "size", "span"),
    [("bytes=0-99", 1000, (0, 99)), ("bytes=900-", 1000, (900, 999)), ("bytes=-100", 1000, (900, 999)),
     ("bytes=0-5000", 1000, (0, 999)), ("bytes=1000-", 1000, None), ("bytes=a-b", 1000, None)],
)  # fmt: skip
def test_BLD_C114_cached_audio_serves_byte_ranges(
    header: str, size: int, span: tuple[int, int] | None
) -> None:
    assert listen.byte_range(header, size) == span


def test_BLD_C114_the_adapter_mirrors_lane_bs_names(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    real = importlib.import_module

    def missing(name: str, *a: Any) -> Any:
        if name.startswith("desk."):  # as if lane B's module were not in the build, whether or not it is
            raise ImportError(name)
        return real(name, *a)

    monkeypatch.setattr(adapters.importlib, "import_module", missing)
    assert adapters.spoken("The problem", "Text.") == "The problem. Text."
    with pytest.raises(adapters.ScriptUnavailable):
        adapters.listen_script(object(), IDEA)  # type: ignore[arg-type]


def test_BLD_C113_hide_text_masks_kind_dots_last_two_and_keeps_spans() -> None:
    got = adapters.hide_text("Folio 12345678 and PAN ABCPE1234F, call 9876543210.")  # synthetic
    assert got.text == "Folio Folio ••••78 and PAN PAN ••••4F, call Phone ••••10."
    assert [s["kind"] for s in got.spans] == ["folio", "pan", "phone"] and got.count == 3
    assert "12345678" not in str(got.spans)


# ---- the SQL, against the running stack ---------------------------------------------------------------------


@pytest.mark.stack
def test_BLD_C114_the_cache_against_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.db import connect
    from tests.web import people

    configure(monkeypatch, SPEECH_MODE="fake")
    monkeypatch.setattr(listen.killswitch, "is_on", lambda name, conn=None: True)
    monkeypatch.setattr(listen, "listen_script", lambda conn, ref, at=None: script())
    with connect(autocommit=True) as db, people(db) as make:
        person = make()
        idea = db.execute(
            "INSERT INTO ideas (contributor_code, status) VALUES (%s, 'with_review_desk') RETURNING id",
            (person.contributor_code,),
        ).fetchone()
        idea_uuid = str(idea["id"])
        assert listen.chapters(db, idea_uuid) is None
        assert listen.prefetch(db, idea_uuid) is True
        got = listen.chapters(db, idea_uuid)
        assert got is not None and got["parts"][0] == {"part": "summary", "start_s": 0.0}


def test_BLD_C117_one_synthesis_per_script_and_voice_under_a_lock(env: dict[str, Any]) -> None:
    conn = env["conn"]
    s = env["current"]["script"]
    b"".join(listen.speak(conn, IDEA, s))
    key = f"listen:{IDEA}:{s.version}:simran_en_customer"
    assert conn.locks == [f"lock {key}", f"unlock {key}"]
    b"".join(listen.speak(conn, IDEA, s))  # cached: no lock, no synthesis
    assert len(conn.locks) == 2


def test_BLD_C117_every_part_is_checked_before_any_is_sent(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    def record(text: str, **k: Any) -> Iterator[bytes]:
        sent.append(text)
        yield sarvam.fake_frames(1)

    monkeypatch.setattr(sarvam, "tts", record)
    monkeypatch.setattr(listen, "mask_for_service", lambda text: text)  # as if masking missed one
    env["current"]["script"] = script(
        fix="Call 9876543210 after the fix."
    )  # synthetic, the last part, unmasked
    with pytest.raises(sarvam.SarvamFailed):
        b"".join(listen.speak(env["conn"], IDEA, env["current"]["script"]))
    assert sent == []  # nothing billed for parts 1 to 5


def test_BLD_C117_a_distributors_arn_is_masked_on_the_way_out_not_refused(env: dict[str, Any]) -> None:
    env["current"]["script"] = script(who="Distributors such as ARN-123456 call daily.")  # synthetic
    texts = dict(listen.outgoing(env["current"]["script"]))
    assert "ARN-123456" not in texts["who"] and "ARN ••••56" in texts["who"]


def test_BLD_C117_a_failed_prefetch_is_remembered_and_not_paid_for_again(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def failing(text: str, **k: Any) -> Any:
        calls.append(text)
        raise sarvam.SarvamFailed("hosted_503")

    monkeypatch.setattr(sarvam, "tts", failing)
    conn = env["conn"]
    assert listen.prefetch(conn, IDEA) is False
    assert list(conn.failures.values()) == ["hosted_503"] and len(calls) == 1
    assert listen.prefetch(conn, IDEA) is False and len(calls) == 1  # backed off: nothing sent again


def test_BLD_C117_prefetch_asks_the_gate_on_the_sarvam_route(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch, SPEECH_MODE="sarvam", SARVAM_API_KEY="")
    assert listen.prefetch(env["conn"], IDEA) is False and env["conn"].cache == {}


def test_BLD_C117_listen_in_fake_mode_needs_no_key(
    env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The uncached path asks the Sarvam gate only on the Sarvam route, like drafts (dev has no key)."""
    from contextlib import contextmanager

    from fastapi.testclient import TestClient

    import api.app as app_module

    configure(monkeypatch, SPEECH_MODE="fake", SARVAM_API_KEY="", INTERNAL_API_TOKEN="t" * 32)

    @contextmanager
    def fake_connect(**k: Any) -> Iterator[Any]:
        yield env["conn"]

    monkeypatch.setattr(app_module, "connect", fake_connect)
    client = TestClient(app_module.app)
    r = client.get(f"/internal/listen/{IDEA}", headers={"X-Internal-Token": "t" * 32})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert listen.mp3_seconds(r.content) > 0
