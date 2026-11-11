"""DEC-096 review (BLD-C005): before anything decodes a recording, an isolated child reads its container: allowed
containers and codecs only, and the length from timestamps, so a few MB that claim hours are refused in
milliseconds. Synthetic files only (tests/voice_files.py), plus a real 2-second Chromium recording."""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from core import isolated
from tests import voice_files as f
from voice.probe import Refused, probe
from voice.service import PROBE

LIMIT = 190.0


@pytest.mark.parametrize(
    ("data", "container", "codec", "seconds"),
    [
        (f.CHROME_WEBM, "webm", "opus", 2.1),
        (f.wav(2, words="Forms are typed twice."), "wav", "pcm", 2.0),
        (f.ogg_opus(2), "ogg", "opus", 2.0),
        (f.mp4(2), "mp4", "aac", 2.0),
        (f.mp4(0, fragments=(100, 1024)), "mp4", "aac", 100 * 1024 / 48000),
    ],
)
def test_allowed_recordings_are_measured_without_decoding(
    data: bytes, container: str, codec: str, seconds: float
) -> None:
    got = probe(data, LIMIT)
    assert (got.container, got.codec) == (container, codec)
    assert got.seconds == pytest.approx(seconds, abs=0.2)


@pytest.mark.parametrize(
    "data",
    [
        f.long_low_bitrate_wav(4000),  # about 4 MB, over an hour
        f.webm_lasting(10 * 3600),  # a few kB that claim 10 hours
        f.ogg_opus(5 * 3600),
        f.mp4(3600),
        f.mp4(0, fragments=(200_000, 1024)),
    ],
)
def test_a_small_file_that_claims_hours_is_refused_as_too_long(data: bytes) -> None:
    assert len(data) < 5 * 1024 * 1024
    started = time.monotonic()
    with pytest.raises(Refused) as exc:
        probe(data, LIMIT)
    assert exc.value.code == "too_long"
    assert time.monotonic() - started < 2.0


@pytest.mark.parametrize(
    "data",
    [
        f.ogg_opus(2, codec_head=b"\x01vorbis"),  # Ogg, but not Opus
        f.mp4(2, handler=b"vide"),  # a video track
        f.mp4(2, entry=b"avc1"),
        f.CHROME_WEBM.replace(b"A_OPUS", b"A_VORB", 1),
        f.CHROME_WEBM.replace(b"\x83\x81\x02", b"\x83\x81\x01", 1),  # the track says video
        f.wav(2, fmt=0x55),  # MP3 inside WAV
    ],
)
def test_other_codecs_and_video_are_refused(data: bytes) -> None:
    with pytest.raises(Refused) as exc:
        probe(data, LIMIT)
    assert exc.value.code == "codec_not_allowed"


def test_other_files_and_broken_ones_are_refused() -> None:
    for data, code in ((b"%PDF-1.7" + bytes(64), "type_not_allowed"), (f.CHROME_WEBM[:100], "unreadable")):
        with pytest.raises(Refused) as exc:
            probe(data, LIMIT)
        assert exc.value.code == code


def test_the_probe_runs_as_an_isolated_child() -> None:
    def run(data: bytes) -> dict[str, object]:
        return isolated.run(PROBE, [str(LIMIT)], data, timeout_s=15, memory_mb=256, cpu_s=5)

    assert run(f.CHROME_WEBM)["ok"] is True
    assert run(f.long_low_bitrate_wav(4000)) == {"ok": False, "code": "too_long"}
    assert run(os.urandom(4096)) == {"ok": False, "code": "type_not_allowed"}


def test_the_child_never_sees_the_workers_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("DATABASE_URL", "VAULT_ENCRYPTION_KEY", "INTERNAL_API_TOKEN", "PSEUDONYM_VAULT_KEY"):
        monkeypatch.setenv(name, "synthetic-secret-for-the-test")
    script = tmp_path / "env_child.py"
    script.write_text(
        textwrap.dedent(
            """
            import json, os, sys
            sys.stdin.buffer.read()
            print(json.dumps({"keys": sorted(os.environ), "flags": sys.flags.isolated}))
            """
        )
    )
    got = isolated.run(script, [], b"", timeout_s=15, memory_mb=256, cpu_s=5)
    assert got["flags"] == 1
    assert not [k for k in got["keys"] if any(w in k for w in ("DATABASE", "KEY", "TOKEN", "SECRET"))]
    with pytest.raises(ValueError):
        isolated.minimal_env({"DATABASE_URL": "x"}, home="/tmp")


def test_a_child_that_hangs_is_stopped(tmp_path: Path) -> None:
    script = tmp_path / "hang.py"
    script.write_text("import time\ntime.sleep(30)\n")
    with pytest.raises(isolated.IsolatedFailed) as exc:
        isolated.run(script, [], b"", timeout_s=1, memory_mb=256, cpu_s=5)
    assert exc.value.code == "timeout"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="RLIMIT_AS is enforced on Linux, where the worker runs"
)
def test_a_child_that_eats_memory_is_stopped(tmp_path: Path) -> None:
    script = tmp_path / "eat.py"
    script.write_text(
        "import resource, sys\nresource.setrlimit(resource.RLIMIT_AS, (int(sys.argv[2]) << 20,) * 2)\n"
        "x = bytearray(1 << 30)\nprint('{}')\n"
    )
    with pytest.raises(isolated.IsolatedFailed):
        isolated.run(script, [], b"", timeout_s=15, memory_mb=128, cpu_s=5)


def _sized_segment(extra: bytes = b"") -> bytes:
    """The Chrome clip with its unknown Segment size replaced by the real one, then `extra` after it."""
    unknown = b"\x18\x53\x80\x67\x01\xff\xff\xff\xff\xff\xff\xff"
    at = f.CHROME_WEBM.index(unknown)
    body = f.CHROME_WEBM[at + len(unknown) :]
    sized = b"\x18\x53\x80\x67\x01" + len(body).to_bytes(7, "big")
    return f.CHROME_WEBM[:at] + sized + body + extra


def test_nothing_may_follow_a_webm_segment_but_padding() -> None:
    """BLD-C013: bytes after a sized Segment are data no check has read; a second Segment is refused."""
    assert probe(_sized_segment(), LIMIT).seconds == pytest.approx(2.1, abs=0.2)
    assert probe(_sized_segment(bytes(8)), LIMIT).container == "webm"
    for extra in (bytes(200), b"\x18\x53\x80\x67\x01\xff\xff\xff\xff\xff\xff\xff" + bytes(4)):
        with pytest.raises(Refused) as exc:
            probe(_sized_segment(extra), LIMIT)
        assert exc.value.code == "unreadable"
    with pytest.raises(Refused):  # a second Segment inside an unknown-size first one
        probe(f.CHROME_WEBM + b"\x18\x53\x80\x67\x01\xff\xff\xff\xff\xff\xff\xff", LIMIT)


def test_a_wav_header_that_disagrees_with_itself_or_the_file_is_refused() -> None:
    """BLD-C013: the byte rate must be rate × channels × bytes per sample, and the data must all be there."""
    import struct

    good = f.wav(2)
    at = good.index(b"fmt ") + 8
    lying_rate = good[: at + 8] + struct.pack("<I", 10) + good[at + 12 :]  # claims 10 bytes a second
    data_at = good.index(b"data") + 4
    lying_size = good[:data_at] + struct.pack("<I", 10 * 1024 * 1024) + good[data_at + 4 :]
    for data in (lying_rate, lying_size):
        with pytest.raises(Refused) as exc:
            probe(data, LIMIT)
        assert exc.value.code == "unreadable"
