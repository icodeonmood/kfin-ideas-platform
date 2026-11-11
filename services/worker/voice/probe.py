"""How long a recording is, and what it is, without decoding it (DEC-096, BLD-C005). Standard library only.

Runs as a child process (`core.isolated.run`: cleared environment, closed descriptors, resource limits, a timeout;
same user, filesystem and network as the worker, which is acceptable for this stdlib-only parser, BLD-C012), after
the virus scan and before any decoder sees the file:
`python -I voice/probe.py --memory-mb 256 --cpu-s 5 <max_seconds>` with the recording on stdin, one JSON line out.
It walks the container's own structure and reads timestamps, never audio samples, so a small file that claims
hours of sound costs a few milliseconds here instead of minutes of decoding in the worker.

Allowed, and nothing else (what browsers' MediaRecorder writes, plus WAV):
- WebM (EBML DocType "webm") with Opus audio tracks only (CodecID "A_OPUS"); duration from cluster and block
  timestamps;
- Ogg with Opus streams only ("OpusHead"); duration from the last granule position, less the pre-skip;
- MP4 with AAC ("mp4a") or Opus ("Opus") audio only; duration from mvhd/mdhd, or the fragments' sample
  durations when the file is fragmented;
- WAV with PCM or float samples; duration from the data size and byte rate.

Answers: {"ok": true, "container", "codec", "seconds"} or {"ok": false, "code"} with code `type_not_allowed`,
`codec_not_allowed`, `too_long` (stops reading as soon as the limit is passed) or `unreadable`.
"""

from __future__ import annotations

import contextlib
import json
import struct
import sys
from dataclasses import dataclass


class Refused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Probe:
    container: str
    codec: str
    seconds: float


def probe(data: bytes, max_seconds: float) -> Probe:
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return _webm(data, max_seconds)
    if data[:4] == b"OggS":
        return _ogg(data, max_seconds)
    if data[4:8] == b"ftyp":
        return _mp4(data, max_seconds)
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return _wav(data, max_seconds)
    raise Refused("type_not_allowed")


def _check(seconds: float, max_seconds: float) -> None:
    if seconds != seconds or seconds < 0:  # NaN or negative: a broken file
        raise Refused("unreadable")
    if seconds > max_seconds:
        raise Refused("too_long")


# ---- WebM (Matroska/EBML) ----------------------------------------------------------------------------------

SEGMENT, CLUSTER = 0x18538067, 0x1F43B675
INFO, TIMECODE_SCALE, DURATION = 0x1549A966, 0x2AD7B1, 0x4489
TRACKS, TRACK_ENTRY, TRACK_TYPE, CODEC_ID = 0x1654AE6B, 0xAE, 0x83, 0x86
CLUSTER_TIMECODE, SIMPLE_BLOCK, BLOCK_GROUP, BLOCK = 0xE7, 0xA3, 0xA0, 0xA1
TOP_LEVEL = {SEGMENT, CLUSTER, INFO, TRACKS, 0x114D9B74, 0x1C53BB6B, 0x1254C367, 0x1941A469, 0x1043A770}
UNKNOWN = -1
SEGMENT_ID = b"\x18\x53\x80\x67"
TRAILING_PADDING = 16  # bytes allowed after a sized Segment


def _vint(data: bytes, pos: int, keep_marker: bool) -> tuple[int, int]:
    if pos >= len(data):
        raise Refused("unreadable")
    first = data[pos]
    length = 1
    mask = 0x80
    while length <= 8 and not first & mask:
        mask >>= 1
        length += 1
    if length > 8 or pos + length > len(data):
        raise Refused("unreadable")
    value = first if keep_marker else first & (mask - 1)
    all_ones = (first & (mask - 1)) == mask - 1
    for b in data[pos + 1 : pos + length]:
        value = (value << 8) | b
        all_ones = all_ones and b == 0xFF
    if not keep_marker and all_ones:
        return UNKNOWN, pos + length
    return value, pos + length


def _element(data: bytes, pos: int) -> tuple[int, int, int]:
    """(id, size or UNKNOWN, start of the payload)."""
    eid, pos = _vint(data, pos, keep_marker=True)
    size, pos = _vint(data, pos, keep_marker=False)
    return eid, size, pos


def _uint(raw: bytes) -> int:
    return int.from_bytes(raw, "big") if raw else 0


def _webm(data: bytes, max_seconds: float) -> Probe:
    _eid, size, pos = _element(data, 0)
    end = len(data) if size == UNKNOWN else pos + size
    doctype = b""
    while pos < end:
        cid, csize, cpos = _element(data, pos)
        if csize == UNKNOWN:
            raise Refused("unreadable")
        if cid == 0x4282:
            doctype = data[cpos : cpos + csize]
        pos = cpos + csize
    if doctype != b"webm":
        raise Refused("type_not_allowed")
    sid, ssize, spos = _element(data, pos)
    if sid != SEGMENT:
        raise Refused("unreadable")
    send = len(data) if ssize == UNKNOWN else min(len(data), spos + ssize)
    scale = 1_000_000  # nanoseconds per timecode unit (the default)
    codecs: list[str] = []
    latest = 0.0
    pos = spos
    while pos < send:
        cid, csize, cpos = _element(data, pos)
        if cid == SEGMENT:
            raise Refused("unreadable")  # a second Segment (BLD-C013)
        if cid == CLUSTER:
            pos, latest = _cluster(data, cpos, csize, send, scale, latest, max_seconds)
            continue
        if csize == UNKNOWN:
            raise Refused("unreadable")
        cend = min(send, cpos + csize)
        if cid == INFO:
            for iid, ipos, iend in _children(data, cpos, cend):
                if iid == TIMECODE_SCALE:
                    scale = _uint(data[ipos:iend]) or scale
                elif iid == DURATION and iend - ipos in (4, 8):
                    declared = struct.unpack(">f" if iend - ipos == 4 else ">d", data[ipos:iend])[0]
                    _check(declared * scale / 1e9, max_seconds)
        elif cid == TRACKS:
            for tid, tpos, tend in _children(data, cpos, cend):
                if tid != TRACK_ENTRY:
                    continue
                kind, codec = 0, ""
                for fid, fpos, fend in _children(data, tpos, tend):
                    if fid == TRACK_TYPE:
                        kind = _uint(data[fpos:fend])
                    elif fid == CODEC_ID:
                        codec = data[fpos:fend].rstrip(b"\0").decode("ascii", "replace")
                if kind != 2 or codec != "A_OPUS":  # audio (2) in Opus, nothing else
                    raise Refused("codec_not_allowed")
                codecs.append("opus")
        pos = cpos + csize
    if not codecs:
        raise Refused("unreadable")
    # Nothing may follow a sized Segment but a little padding, and never a second Segment (BLD-C013): bytes there
    # would be data no check above has read.
    trailing = data[send:]
    if len(trailing) > TRAILING_PADDING or SEGMENT_ID in trailing:
        raise Refused("unreadable")
    return Probe("webm", "opus", latest)


def _children(data: bytes, pos: int, end: int) -> list[tuple[int, int, int]]:
    out = []
    while pos < end:
        cid, csize, cpos = _element(data, pos)
        if csize == UNKNOWN or cpos + csize > end:
            raise Refused("unreadable")
        out.append((cid, cpos, cpos + csize))
        pos = cpos + csize
    return out


def _cluster(
    data: bytes, pos: int, size: int, send: int, scale: int, latest: float, max_seconds: float
) -> tuple[int, float]:
    """Read one cluster (its size may be unknown, as MediaRecorder writes it). Returns where it ends and the
    latest timestamp seen so far, in seconds."""
    end = send if size == UNKNOWN else min(send, pos + size)
    base = 0
    while pos < end:
        cid, csize, cpos = _element(data, pos)
        if size == UNKNOWN and cid in TOP_LEVEL:
            return pos, latest  # the next cluster (or other top-level element) ends an unknown-size cluster
        if csize == UNKNOWN or cpos + csize > len(data):
            raise Refused("unreadable")
        if cid == CLUSTER_TIMECODE:
            base = _uint(data[cpos : cpos + csize])
        elif cid in (SIMPLE_BLOCK, BLOCK_GROUP):
            block = cpos
            if cid == BLOCK_GROUP:
                inner = [(bid, bpos) for bid, bpos, _ in _children(data, cpos, cpos + csize) if bid == BLOCK]
                if not inner:
                    pos = cpos + csize
                    continue
                block = inner[0][1]
            _track, after = _vint(data, block, keep_marker=False)
            if after + 2 > len(data):
                raise Refused("unreadable")
            relative = struct.unpack(">h", data[after : after + 2])[0]
            latest = max(latest, (base + relative) * scale / 1e9)
            _check(latest, max_seconds)
        pos = cpos + csize
    return end, latest


# ---- Ogg ---------------------------------------------------------------------------------------------------


def _ogg(data: bytes, max_seconds: float) -> Probe:
    pos = 0
    preskip: dict[int, int] = {}
    latest = 0.0
    while pos + 27 <= len(data):
        if data[pos : pos + 4] != b"OggS" or data[pos + 4] != 0:
            raise Refused("unreadable")
        header_type = data[pos + 5]
        granule = struct.unpack("<q", data[pos + 6 : pos + 14])[0]
        serial = struct.unpack("<I", data[pos + 14 : pos + 18])[0]
        segments = data[pos + 26]
        lacing = data[pos + 27 : pos + 27 + segments]
        if len(lacing) != segments:
            raise Refused("unreadable")
        body = pos + 27 + segments
        length = sum(lacing)
        if body + length > len(data):
            raise Refused("unreadable")
        if header_type & 0x02:  # beginning of a stream: it must be Opus
            if data[body : body + 8] != b"OpusHead" or length < 19:
                raise Refused("codec_not_allowed")
            preskip[serial] = struct.unpack("<H", data[body + 10 : body + 12])[0]
        elif serial not in preskip:
            raise Refused("unreadable")
        if granule >= 0:
            latest = max(latest, max(0, granule - preskip[serial]) / 48_000)
            _check(latest, max_seconds)
        pos = body + length
    if not preskip:
        raise Refused("unreadable")
    return Probe("ogg", "opus", latest)


# ---- MP4 ---------------------------------------------------------------------------------------------------

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"moof", b"traf", b"mvex"}


def _boxes(data: bytes, pos: int, end: int) -> list[tuple[bytes, int, int]]:
    out = []
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        head = 8
        if size == 1:
            if pos + 16 > end:
                raise Refused("unreadable")
            size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
            head = 16
        elif size == 0:
            size = end - pos
        if size < head or pos + size > end:
            raise Refused("unreadable")
        out.append((kind, pos + head, pos + size))
        pos += size
    return out


def _walk(data: bytes, pos: int, end: int, depth: int = 0) -> list[tuple[bytes, int, int]]:
    if depth > 8:
        raise Refused("unreadable")
    found = []
    for kind, start, stop in _boxes(data, pos, end):
        found.append((kind, start, stop))
        if kind in CONTAINERS:
            found.extend(_walk(data, start, stop, depth + 1))
    return found


def _header_duration(data: bytes, start: int, stop: int, *, offset: int) -> tuple[int, int]:
    """(timescale, duration) from an mvhd or mdhd box payload."""
    version = data[start] if start < stop else 0
    if version == 1:
        at = start + 4 + 16 + offset
        if at + 12 > stop:
            raise Refused("unreadable")
        return struct.unpack(">IQ", data[at : at + 12])
    at = start + 4 + 8 + offset
    if at + 8 > stop:
        raise Refused("unreadable")
    return struct.unpack(">II", data[at : at + 8])


def _mp4(data: bytes, max_seconds: float) -> Probe:
    boxes = _walk(data, 0, len(data))
    kinds = [k for k, _, _ in boxes]
    if b"moov" not in kinds:
        raise Refused("unreadable")
    codec = ""
    timescale = 0
    longest = 0.0
    for kind, start, stop in boxes:
        if kind == b"hdlr" and stop - start >= 12:
            handler = data[start + 8 : start + 12]
            if handler not in (b"soun", b"meta", b"mdir"):
                raise Refused("codec_not_allowed")
        elif kind == b"stsd" and stop - start >= 16:
            entry = data[start + 12 : start + 16]
            if entry not in (b"mp4a", b"Opus"):
                raise Refused("codec_not_allowed")
            codec = "aac" if entry == b"mp4a" else "opus"
        elif kind in (b"mvhd", b"mdhd"):
            scale, duration = _header_duration(data, start, stop, offset=0)
            if kind == b"mdhd":
                timescale = scale
            if scale:
                longest = max(longest, duration / scale)
                _check(longest, max_seconds)
    if not codec:
        raise Refused("unreadable")
    longest = max(longest, _fragments(data, boxes, timescale, max_seconds))
    return Probe("mp4", codec, longest)


def _fragments(data: bytes, boxes: list[tuple[bytes, int, int]], timescale: int, max_seconds: float) -> float:
    """Total sample duration across movie fragments (MediaRecorder in Safari writes fragmented MP4)."""
    default = 0
    for kind, start, stop in boxes:
        if kind == b"trex" and stop - start >= 24:  # version/flags, track, sample description, duration…
            default = struct.unpack(">I", data[start + 12 : start + 16])[0]
    total = 0
    frag_default = default
    for kind, start, stop in boxes:
        if kind == b"tfhd" and stop - start >= 8:
            flags = int.from_bytes(data[start + 1 : start + 4], "big")
            at = start + 8 + (8 if flags & 0x01 else 0) + (4 if flags & 0x02 else 0)
            frag_default = default
            if flags & 0x08 and at + 4 <= stop:
                frag_default = struct.unpack(">I", data[at : at + 4])[0]
        elif kind == b"trun" and stop - start >= 8:
            flags = int.from_bytes(data[start + 1 : start + 4], "big")
            count = struct.unpack(">I", data[start + 4 : start + 8])[0]
            at = start + 8 + (4 if flags & 0x01 else 0) + (4 if flags & 0x04 else 0)
            per = sum(4 for bit in (0x100, 0x200, 0x400, 0x800) if flags & bit)
            if flags & 0x100:
                if at + per * count > stop:
                    raise Refused("unreadable")
                for i in range(count):
                    total += struct.unpack(">I", data[at + i * per : at + i * per + 4])[0]
            else:
                total += frag_default * count
            if timescale:
                _check(total / timescale, max_seconds)
    return total / timescale if timescale else 0.0


# ---- WAV ---------------------------------------------------------------------------------------------------


def _wav(data: bytes, max_seconds: float) -> Probe:
    """PCM or float only. The header must agree with itself (byte rate = sample rate × channels × bytes per
    sample) and with the file (the data chunk is all there): a header that lies is refused, not trusted (BLD-C013)."""
    pos = 12
    byte_rate = 0
    fmt = 0
    seconds = None
    while pos + 8 <= len(data):
        kind = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        body = pos + 8
        if kind == b"fmt " and size >= 16:
            fmt, channels, rate, byte_rate, align, bits = struct.unpack("<HHIIHH", data[body : body + 16])
            if (
                fmt == 0xFFFE and size >= 26
            ):  # extensible: the real format is the sub-format's first two bytes
                fmt = struct.unpack("<H", data[body + 24 : body + 26])[0]
            if fmt not in (1, 3):  # PCM or float
                raise Refused("codec_not_allowed")
            if not channels or not rate or bits % 8 or not bits:
                raise Refused("unreadable")
            if byte_rate != rate * channels * bits // 8 or align != channels * bits // 8:
                raise Refused("unreadable")
        elif kind == b"data":
            if not byte_rate:
                raise Refused("unreadable")
            if size > len(data) - body:  # the header claims more sound than the file holds
                raise Refused("unreadable")
            seconds = size / byte_rate
            _check(seconds, max_seconds)
        pos = body + size + (size & 1)
    if seconds is None or not fmt:
        raise Refused("unreadable")
    return Probe("wav", "pcm", seconds)


# ---- run as an isolated child ------------------------------------------------------------------------------


def _limits(memory_mb: int, cpu_s: int) -> None:
    import resource

    for limit, value in (
        (resource.RLIMIT_CPU, cpu_s),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_AS, memory_mb * 1024 * 1024),
    ):
        with contextlib.suppress(ValueError, OSError):  # macOS may refuse RLIMIT_AS; the timeout still holds
            resource.setrlimit(limit, (value, value))


def main(argv: list[str]) -> int:
    memory_mb, cpu_s, max_seconds = int(argv[2]), int(argv[4]), float(argv[5])
    _limits(memory_mb, cpu_s)
    data = sys.stdin.buffer.read(8 * 1024 * 1024)
    try:
        p = probe(data, max_seconds)
        answer: dict[str, object] = {
            "ok": True,
            "container": p.container,
            "codec": p.codec,
            "seconds": p.seconds,
        }
    except Refused as exc:
        answer = {"ok": False, "code": exc.code}
    except (struct.error, IndexError, ValueError, OverflowError, RecursionError):
        answer = {"ok": False, "code": "unreadable"}
    print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
