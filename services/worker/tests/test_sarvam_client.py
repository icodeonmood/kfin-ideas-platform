"""BLD-C110 (DEC-108): the Sarvam client in the gateway. REST speech to text, streaming speech to text, translation
and text to speech, each against a fake (httpx MockTransport or a local WebSocket server): exact models, modes and
fields from Sarvam's API reference, the key in a header only, retries, the approval and switch gate, masked text
only on the way out, metering by seconds and characters, and the automatic switch-off. No stack, no key."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from core.config import get_settings
from gateway import sarvam, speech
from tests.sarvam_fakes import KEY, FakeSarvamWs, MeterConn, configure, ws_server


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield
    monkeypatch.setattr(sarvam, "_transport", None)
    get_settings.cache_clear()


def transport(monkeypatch: pytest.MonkeyPatch, *answers: httpx.Response) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(sarvam, "_transport", httpx.MockTransport(handle))
    return seen


def form_fields(request: httpx.Request) -> str:
    return request.content.decode("latin-1")


# ---- REST speech to text ------------------------------------------------------------------------------------


def test_BLD_C110_rest_stt_sends_saaras_v4_in_codemix_with_the_key_in_a_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    seen = transport(
        monkeypatch,
        httpx.Response(
            200,
            json={
                "request_id": "r1",
                "transcript": " SIP form retyped twice ",
                "language_code": "hi-IN",
                "timestamps": {
                    "words": ["a", "b"],
                    "start_time_seconds": [0.0, 4.1],
                    "end_time_seconds": [4.0, 9.5],
                },
            },
        ),
    )
    conn = MeterConn()
    got = sarvam.stt_rest(b"RIFF....WAVE", "audio/wav", conn=conn, ref_id="voice-1")  # type: ignore[arg-type]
    assert got.text == "SIP form retyped twice" and got.language == "hi-IN" and got.seconds == 9.5
    req = seen[0]
    assert req.url.path == "/speech-to-text" and req.headers["api-subscription-key"] == KEY
    body = form_fields(req)
    for field, value in (("model", "saaras:v4"), ("mode", "codemix"), ("language_code", "unknown")):
        assert f'name="{field}"\r\n\r\n{value}\r\n' in body
    assert KEY not in str(req.url)  # the key travels in the header only
    assert conn.calls[0]["call"] == "stt_rest" and conn.calls[0]["outcome"] == "ok"
    assert conn.calls[0]["seconds"] == 9.5 and conn.calls[0]["cost"] > 0


def test_BLD_C110_transcribe_mode_is_a_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, SARVAM_STT_MODE="transcribe")
    seen = transport(monkeypatch, httpx.Response(200, json={"transcript": "x", "language_code": None}))
    sarvam.stt_rest(b"OggS", "audio/ogg")
    assert 'name="mode"\r\n\r\ntranscribe\r\n' in form_fields(seen[0])


def test_BLD_C110_retries_429_and_5xx_twice_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    seen = transport(
        monkeypatch,
        httpx.Response(429, json={}),
        httpx.Response(503, json={}),
        httpx.Response(200, json={"transcript": "ok", "language_code": "en-IN"}),
    )
    conn = MeterConn()
    assert sarvam.stt_rest(b"OggS", "audio/ogg", conn=conn).text == "ok"  # type: ignore[arg-type]
    assert len(seen) == 3 and conn.calls[-1]["outcome"] == "ok_after_retry"


@pytest.mark.parametrize(("status", "tries"), [(400, 1), (403, 1), (500, 3)])
def test_BLD_C110_a_failure_carries_a_code_only(
    monkeypatch: pytest.MonkeyPatch, status: int, tries: int
) -> None:
    configure(monkeypatch)
    seen = transport(
        monkeypatch, httpx.Response(status, json={"error": {"message": "Invalid PAN ABCDE1234F"}})
    )
    conn = MeterConn()
    with pytest.raises(sarvam.SarvamFailed) as exc:
        sarvam.stt_rest(b"OggS", "audio/ogg", conn=conn)  # type: ignore[arg-type]
    assert exc.value.code == f"hosted_{status}" and str(exc.value) == f"hosted_{status}"
    assert len(seen) == tries
    assert conn.calls[-1]["outcome"] == sarvam.failed_outcome(f"hosted_{status}")
    assert conn.calls[-1]["error_code"] == f"hosted_{status}"


@pytest.mark.parametrize(
    ("env", "hosted_on", "code"),
    [
        ({"SPEECH_HOSTED_APPROVAL": ""}, True, "hosted_not_approved"),
        ({}, False, "hosted_switched_off"),
        ({"SARVAM_API_KEY": ""}, True, "hosted_key_missing"),
    ],
)
def test_BLD_C110_nothing_goes_out_without_the_approval_the_switch_and_the_key(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], hosted_on: bool, code: str
) -> None:
    configure(monkeypatch, hosted_on=hosted_on, **env)
    seen = transport(monkeypatch, httpx.Response(200, json={"transcript": "x"}))
    with pytest.raises(speech.SpeechUnavailable) as exc:
        sarvam.stt_rest(b"OggS", "audio/ogg")
    assert exc.value.code == code and seen == []


def test_BLD_C110_fake_mode_never_runs_outside_dev_and_test(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, SPEECH_MODE="fake", APP_ENV="uat")
    with pytest.raises(sarvam.SarvamFailed) as exc:
        sarvam.stt_rest(b"OggS", "audio/ogg")
    assert exc.value.code == "fake_not_allowed"


def test_BLD_C110_the_base_url_override_is_ignored_outside_dev_and_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch, APP_ENV="uat", SARVAM_BASE_URL="http://127.0.0.1:9")
    assert sarvam._base() == sarvam.BASE and sarvam._ws_base() == "wss://api.sarvam.ai"


def test_BLD_C110_the_voice_note_route_uses_the_new_client(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    seen = transport(
        monkeypatch, httpx.Response(200, json={"transcript": "Typed twice", "language_code": "en-IN"})
    )
    assert speech.transcribe(b"OggS", "audio/ogg").text == "Typed twice"
    assert 'name="model"\r\n\r\nsaaras:v4\r\n' in form_fields(seen[0])


# ---- translation ------------------------------------------------------------------------------------------


def test_BLD_C110_translate_uses_mayura_code_mixed_into_english_and_omits_gender_unless_chosen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    seen = transport(
        monkeypatch,
        httpx.Response(
            200, json={"translated_text": "The form is typed twice.", "source_language_code": "hi-IN"}
        ),
    )
    got = sarvam.translate("Form do baar type hota hai.")
    assert got.text == "The form is typed twice." and got.translated and got.source_language == "hi-IN"
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/translate" and seen[0].headers["api-subscription-key"] == KEY
    assert body["model"] == "mayura:v1" and body["mode"] == "code-mixed"
    assert body["source_language_code"] == "auto" and body["target_language_code"] == "en-IN"
    assert "speaker_gender" not in body  # neutral unless the person chose (DEC-108 (3))
    sarvam.translate("Form do baar type hota hai.", gender="Female")
    assert json.loads(seen[1].content)["speaker_gender"] == "Female"
    sarvam.translate("Form do baar type hota hai.", gender="they")
    assert "speaker_gender" not in json.loads(seen[2].content)


def test_BLD_C110_translate_refuses_unmasked_text_before_anything_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    seen = transport(monkeypatch, httpx.Response(200, json={"translated_text": "x"}))
    with pytest.raises(sarvam.SarvamFailed) as exc:
        sarvam.translate("Investor PAN ABCPE1234F is stuck")  # synthetic
    assert exc.value.code == "unmasked_text" and seen == []
    sarvam.translate("Investor PAN ••••4F is stuck")  # masked: allowed
    assert len(seen) == 1


def test_BLD_C110_long_text_goes_in_pieces_of_at_most_1000_characters_at_sentence_ends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    seen = transport(
        monkeypatch, httpx.Response(200, json={"translated_text": "part", "source_language_code": "hi-IN"})
    )
    text = " ".join(f"Vaakya number {i} mein kuch shabd hain." for i in range(60))
    conn = MeterConn()
    got = sarvam.translate(text, conn=conn)  # type: ignore[arg-type]
    inputs = [json.loads(r.content)["input"] for r in seen]
    assert len(inputs) >= 2 and all(len(i) <= 1000 for i in inputs)
    assert all(i.endswith(".") for i in inputs)  # whole sentences
    assert got.text == " ".join(["part"] * len(inputs))
    assert sum(c["chars"] for c in conn.calls) == sum(len(i) for i in inputs)


def test_BLD_C110_english_is_not_sent_for_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    seen = transport(monkeypatch, httpx.Response(200, json={"translated_text": "x"}))
    got = sarvam.translate("Already in English.", source="en-IN")
    assert got.text == "Already in English." and not got.translated and seen == []


def test_BLD_C110_pieces_cut_a_long_sentence_at_spaces_and_a_long_word_where_it_must() -> None:
    text = ("word " * 300).strip() + ". " + "x" * 1200
    out = sarvam.pieces(text, 499)
    assert all(len(p) <= 499 for p in out) and "".join(out).replace(" ", "") == text.replace(" ", "")


# ---- metering and the automatic switch-off ---------------------------------------------------------------


def test_BLD_C110_a_sustained_error_rate_switches_hosted_speech_off(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    import gateway.core as core

    flips: list[tuple[str, str]] = []
    monkeypatch.setattr(core, "_maybe_switch_off", lambda conn, name, reason: flips.append((name, reason)))
    monkeypatch.setattr(core, "_thresholds", lambda: {})
    transport(monkeypatch, httpx.Response(503, json={}))
    with pytest.raises(sarvam.SarvamFailed):
        sarvam.stt_rest(b"OggS", "audio/ogg", conn=MeterConn(totals=(10, 2)))  # type: ignore[arg-type]
    assert flips == []  # 20% is not above 20%
    with pytest.raises(sarvam.SarvamFailed):
        sarvam.stt_rest(b"OggS", "audio/ogg", conn=MeterConn(totals=(10, 3)))  # type: ignore[arg-type]
    assert flips == [("speech.hosted", "Automatic: Sarvam error rate above 20% over 15 minutes (DEC-108)")]
    flips.clear()
    with pytest.raises(sarvam.SarvamFailed):
        sarvam.stt_rest(b"OggS", "audio/ogg", conn=MeterConn(totals=(9, 9)))  # type: ignore[arg-type]
    assert flips == []  # fewer than 10 calls: too few to judge


@pytest.mark.parametrize("status", [400, 413, 422])
def test_BLD_C117_bad_or_short_audio_is_not_counted_against_sarvam(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    configure(monkeypatch)
    import gateway.core as core

    flips: list[str] = []
    monkeypatch.setattr(core, "_maybe_switch_off", lambda conn, name, reason: flips.append(name))
    transport(monkeypatch, httpx.Response(status, json={}))
    conn = MeterConn(totals=(10, 10))
    with pytest.raises(sarvam.SarvamFailed):
        sarvam.stt_rest(b"OggS", "audio/ogg", conn=conn)  # type: ignore[arg-type]
    assert conn.calls[-1]["outcome"] == "bad_input" and flips == []


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_BLD_C117_service_side_failures_count(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    configure(monkeypatch)
    transport(monkeypatch, httpx.Response(status, json={}))
    conn = MeterConn()
    with pytest.raises(sarvam.SarvamFailed):
        sarvam.stt_rest(b"OggS", "audio/ogg", conn=conn)  # type: ignore[arg-type]
    assert conn.calls[-1]["outcome"] == "route_error"


def test_BLD_C117_the_leak_check_is_the_gateways_any_pattern_any_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    seen = transport(monkeypatch, httpx.Response(200, json={"translated_text": "x"}))
    for text in ("Distributor ARN-123456 asked", "Mail priya@kfintech.com about it"):  # synthetic
        with pytest.raises(sarvam.SarvamFailed) as exc:
            sarvam.translate(text)
        assert exc.value.code == "unmasked_text"
    assert seen == []


def test_BLD_C117_rest_speech_to_text_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    seen: list[httpx.Timeout] = []
    real = httpx.Client

    class Spy(real):  # type: ignore[misc, valid-type]
        def __init__(self, *a: Any, **k: Any) -> None:
            seen.append(k["timeout"])
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "Client", Spy)
    transport(monkeypatch, httpx.Response(200, json={"transcript": "ok"}))
    sarvam.stt_rest(b"OggS", "audio/ogg")
    assert seen[0].read == 20.0 and seen[0].connect == 5.0


# ---- streaming speech to text ---------------------------------------------------------------------------


def test_BLD_C110_the_stream_relays_pcm_and_returns_what_sarvam_heard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    with ws_server(monkeypatch, FakeSarvamWs(heard="Branch par form do baar type hota hai")) as fake:
        stream = sarvam.stt_stream(ref_id="s1")
        one_second = bytes(range(256)) * 125  # 32,000 bytes: one second of 16 kHz 16-bit mono
        stream.send(one_second)
        stream.send(one_second)
        heard = stream.finish()
    assert heard.text == "Branch par form do baar type hota hai" and heard.language == "hi-IN"
    assert heard.seconds == 2.0
    assert bytes(fake.audio) == one_second * 2  # relayed as is: never decoded
    path = fake.paths[0]
    assert path.startswith("/speech-to-text/ws?")
    for part in ("model=saaras%3Av4", "mode=codemix", "language-code=unknown", "sample_rate=16000",
                 "input_audio_codec=pcm_s16le", "flush_signal=true"):  # fmt: skip
        assert part in path
    assert fake.headers[0]["api-subscription-key"] == KEY and KEY not in path
    audio = [m for m in fake.received if "audio" in m]
    assert audio[0]["audio"]["sample_rate"] == "16000" and audio[0]["audio"]["encoding"] == "audio/wav"
    assert fake.received[-1] == {"type": "flush"}


def test_BLD_C117_a_stream_that_cannot_open_is_metered_as_a_route_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    configure(monkeypatch)
    with socket.socket() as sock:  # a port nobody listens on
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setenv("SARVAM_BASE_URL", f"http://127.0.0.1:{port}")
    get_settings.cache_clear()
    conn = MeterConn()
    with pytest.raises(sarvam.SarvamFailed) as exc:
        sarvam.stt_stream(conn=conn, ref_id="s1")  # type: ignore[arg-type]
    assert exc.value.code == "hosted_unreachable"
    assert conn.calls == [
        {"call": "stt_stream", "model": "saaras:v4", "ref_id": "s1", "outcome": "route_error",
         "error_code": "hosted_unreachable", "seconds": None, "chars": None,
         "latency_ms": conn.calls[0]["latency_ms"], "cost": 0.0},
    ]  # fmt: skip


def test_BLD_C110_the_stream_needs_the_gate_too(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, hosted_on=False)
    with pytest.raises(speech.HostedRefused):
        sarvam.stt_stream(ref_id="s1")


def test_BLD_C110_an_error_from_sarvam_mid_stream_fails_with_a_code(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    fake = FakeSarvamWs()

    def boom(ws: Any, msg: dict[str, Any]) -> None:
        if "audio" in msg:
            ws.send(
                json.dumps({"type": "error", "data": {"error": "bad audio for folio 12345678", "code": "x"}})
            )

    fake.on_stt = boom
    with ws_server(monkeypatch, fake):
        stream = sarvam.stt_stream(ref_id="s1")
        stream.send(bytes(3200))
        heard = stream.finish()
    assert stream.failure == "hosted_stream_error" and heard.text == ""


def test_BLD_C110_the_fake_stream_hears_a_synthetic_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, SPEECH_MODE="fake")
    stream = sarvam.stt_stream()
    stream.send(bytes(100) + speech.FAKE_MARKER + b"Forms typed twice\0")
    assert stream.finish().text == "Forms typed twice"


# ---- text to speech -------------------------------------------------------------------------------------


def test_BLD_C110_tts_streams_bulbul_v4_flash_a_sentence_a_message_under_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    script = "The problem. Investors call the branch. " + ("Long words here " * 50).strip() + "."
    conn = MeterConn()
    with ws_server(monkeypatch, FakeSarvamWs(tts_chunks=3)) as fake:
        audio = b"".join(sarvam.tts(script, conn=conn, ref_id="idea-1"))  # type: ignore[arg-type]
    assert audio == sarvam.fake_frames(10) * 3
    assert fake.paths[0].startswith("/text-to-speech/ws?") and "model=bulbul%3Av4-flash" in fake.paths[0]
    assert fake.headers[0]["api-subscription-key"] == KEY
    config, *texts, flush = fake.received
    assert config["type"] == "config" and config["data"]["model"] == "bulbul:v4-flash"
    assert config["data"]["language_code"] == "en-IN" and config["data"]["speaker"] == "simran_en_customer"
    assert config["data"]["output_audio_codec"] == "mp3"
    assert [t["type"] for t in texts] == ["text"] * len(texts) and len(texts) >= 3
    assert all(0 < len(t["data"]["text"]) < 500 for t in texts)
    assert flush == {"type": "flush"}
    assert conn.calls[-1]["call"] == "tts" and conn.calls[-1]["outcome"] == "ok"
    assert conn.calls[-1]["chars"] == sum(len(t["data"]["text"]) for t in texts)


def test_BLD_C117_audio_that_is_not_base64_is_a_bad_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    fake = FakeSarvamWs()

    def broken(ws: Any) -> None:
        for raw in ws:
            if json.loads(raw).get("type") == "flush":
                ws.send(json.dumps({"type": "audio", "data": {"audio": "not base64 at all!"}}))

    fake._tts = broken  # type: ignore[method-assign]
    conn = MeterConn()
    with ws_server(monkeypatch, fake), pytest.raises(sarvam.SarvamFailed) as exc:
        list(sarvam.tts("One sentence.", conn=conn))  # type: ignore[arg-type]
    assert exc.value.code == "hosted_bad_reply" and conn.calls[-1]["outcome"] == "route_error"


def test_BLD_C117_tts_has_a_deadline_for_the_whole_part(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(sarvam, "TTS_DEADLINE_S", 0.5)
    fake = FakeSarvamWs()

    def trickle(ws: Any) -> None:
        import time as t

        for raw in ws:
            if json.loads(raw).get("type") == "flush":
                for _ in range(20):  # audio keeps coming, never "final"
                    ws.send(json.dumps({"type": "audio", "data": {"audio": base64.b64encode(b"x").decode()}}))
                    t.sleep(0.1)

    fake._tts = trickle  # type: ignore[method-assign]
    with ws_server(monkeypatch, fake), pytest.raises(sarvam.SarvamFailed) as exc:
        list(sarvam.tts("One sentence."))
    assert exc.value.code == "hosted_timeout"


def test_BLD_C110_tts_reads_masked_text_only(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    with pytest.raises(sarvam.SarvamFailed) as exc:
        list(sarvam.tts("Call 9876543210 about it."))  # synthetic number
    assert exc.value.code == "unmasked_text"


def test_BLD_C110_a_listener_leaving_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    conn = MeterConn()
    with ws_server(monkeypatch, FakeSarvamWs(tts_chunks=3)):
        gen = sarvam.tts("One sentence. Two sentences.", conn=conn)  # type: ignore[arg-type]
        next(gen)
        gen.close()
    assert conn.calls[-1]["outcome"] == "cancelled"


def test_BLD_C110_nothing_in_the_metering_row_is_text(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    transport(
        monkeypatch,
        httpx.Response(200, json={"translated_text": "Secret words", "source_language_code": "hi-IN"}),
    )
    conn = MeterConn()
    sarvam.translate("Gupt shabd.", conn=conn, ref_id="stream-1")  # type: ignore[arg-type]
    row = conn.calls[0]
    assert set(row) == {
        "call",
        "model",
        "ref_id",
        "outcome",
        "error_code",
        "seconds",
        "chars",
        "latency_ms",
        "cost",
    }
    assert all(
        not isinstance(v, str) or v in {"translate", "mayura:v1", "stream-1", "ok"} for v in row.values()
    )
    assert base64.b64encode(b"Gupt").decode() not in json.dumps(row, default=str)
