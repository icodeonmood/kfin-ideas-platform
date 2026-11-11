"""Synthetic recordings for the voice tests (DEC-096): valid containers built byte by byte, plus a real 2-second
clip of Chromium's fake microphone (a beep) recorded with MediaRecorder (`fixtures/voice/chrome-opus-2s.webm`).
`FAKE-TRANSCRIPT:` markers make SPEECH_MODE=fake return a chosen sentence; real engines ignore them."""

from __future__ import annotations

import struct
from pathlib import Path

from gateway.speech import FAKE_MARKER

CHROME_WEBM = (Path(__file__).parent / "fixtures" / "voice" / "chrome-opus-2s.webm").read_bytes()


def wav(seconds: float, *, rate: int = 8000, bits: int = 16, fmt: int = 1, words: str = "") -> bytes:
    """Mono silence of `seconds`, plus an extra chunk carrying the fake transcript (WAV readers skip it)."""
    block = bits // 8
    data = bytes(int(seconds * rate) * block)
    fmt_chunk = struct.pack("<HHIIHH", fmt, 1, rate, rate * block, block, bits)
    chunks = b"fmt " + struct.pack("<I", len(fmt_chunk)) + fmt_chunk
    chunks += b"data" + struct.pack("<I", len(data)) + data
    if words:
        extra = FAKE_MARKER + words.encode() + b"\0"
        extra += b"\0" * (len(extra) & 1)
        chunks += b"fake" + struct.pack("<I", len(extra)) + extra
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def long_low_bitrate_wav(seconds: int = 4000) -> bytes:
    """Hours of sound in a few MB: 8-bit samples at 1,000 a second (1 kB a second)."""
    return wav(seconds, rate=1000, bits=8)


def ogg_opus(seconds: float, *, codec_head: bytes = b"OpusHead") -> bytes:
    """Two Ogg pages: the stream's head, then one page whose granule position says `seconds` of Opus."""

    def page(header_type: int, granule: int, seq: int, body: bytes) -> bytes:
        lacing = bytes([255] * (len(body) // 255) + [len(body) % 255])
        head = b"OggS" + bytes([0, header_type]) + struct.pack("<qIII", granule, 0x1234, seq, 0)
        return head + bytes([len(lacing)]) + lacing + body

    opus_head = codec_head + bytes([1, 1]) + struct.pack("<HIhB", 312, 48000, 0, 0)
    return page(0x02, 0, 0, opus_head) + page(0x04, int(312 + seconds * 48000), 1, b"\x00" * 40)


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def mp4(
    seconds: float,
    *,
    handler: bytes = b"soun",
    entry: bytes = b"mp4a",
    fragments: tuple[int, int] | None = None,
) -> bytes:
    """ftyp + moov (mvhd, one track: mdhd, hdlr, stsd). With `fragments` = (samples, sample duration) the header
    durations are 0 and the length comes from a movie fragment instead, as Safari's MediaRecorder writes it."""
    scale = 48000
    header_len = 0 if fragments else int(seconds * scale)
    mvhd = _box(b"mvhd", bytes(4) + struct.pack(">IIII", 0, 0, scale, header_len) + bytes(80))
    mdhd = _box(b"mdhd", bytes(4) + struct.pack(">IIII", 0, 0, scale, header_len) + bytes(4))
    hdlr = _box(b"hdlr", bytes(4) + bytes(4) + handler + bytes(12) + b"\0")
    stsd = _box(b"stsd", bytes(4) + struct.pack(">I", 1) + _box(entry, bytes(28)))
    stbl = _box(b"stbl", stsd)
    minf = _box(b"minf", stbl)
    mdia = _box(b"mdia", mdhd + hdlr + minf)
    trak = _box(b"trak", mdia)
    moov_parts = mvhd + trak
    tail = b""
    if fragments:
        count, duration = fragments
        trex = _box(b"trex", bytes(4) + struct.pack(">IIIII", 1, 1, duration, 0, 0))
        moov_parts += _box(b"mvex", trex)
        tfhd = _box(b"tfhd", bytes([0, 0, 0, 0]) + struct.pack(">I", 1))
        trun = _box(b"trun", bytes([0, 0, 0, 0]) + struct.pack(">I", count))
        tail = _box(b"moof", _box(b"traf", tfhd + trun)) + _box(b"mdat", bytes(16))
    return _box(b"ftyp", b"M4A " + bytes(4) + b"isom") + _box(b"moov", moov_parts) + tail


def webm_lasting(seconds: int) -> bytes:
    """The real Chrome clip with its first cluster moved `seconds` later: a few kB that claim hours."""
    cluster = b"\x1f\x43\xb6\x75\x01\xff\xff\xff\xff\xff\xff\xff\xe7\x81\x00"
    assert cluster in CHROME_WEBM
    moved = cluster[:-3] + b"\xe7\x84" + (seconds * 1000).to_bytes(4, "big")
    return CHROME_WEBM.replace(cluster, moved, 1)
