"""The engine on KFin's own server as a child process of the worker, for dev and test only (DEC-096, BLD-C005,
BLD-C012). Standalone: no worker imports.

`python -I gateway/speech_child.py --memory-mb N --cpu-s N <model_path> <max_seconds> <threads>`, the recording on
stdin, one JSON line out: {"text", "language", "seconds"} or {"error": code}. It sets its own limits before it
reads anything and decodes and transcribes here (faster-whisper, CPU, int8). Its environment is cleared and its
file descriptors closed, so it is not handed the database URL, keys or tokens; but it runs as the worker's user,
with the worker's filesystem and network, so it is not a security boundary against a decoder exploit
(`core/isolated.py`). Outside dev and test the worker refuses this route and uses the isolated speech service.
The model files are read from disk only; nothing is downloaded. The probe has already checked the container, the
codec and the length; the length is checked again after decoding.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys


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


def transcribe(data: bytes, model_path: str, max_seconds: float, threads: int) -> dict[str, object]:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    except ImportError:
        return {"error": "engine_not_installed"}  # the image needs WITH_SPEECH=1
    try:
        model = WhisperModel(
            model_path, device="cpu", compute_type="int8", cpu_threads=threads, local_files_only=True
        )
    except Exception:  # a missing or broken model folder: keep only a code
        return {"error": "model_unavailable"}
    try:
        segments, info = model.transcribe(io.BytesIO(data), beam_size=1, vad_filter=True)
        if info.duration and info.duration > max_seconds:
            return {"error": "too_long"}
        text = " ".join(s.text.strip() for s in segments).strip()
    except MemoryError:
        return {"error": "too_big"}
    except Exception:  # decoder errors can carry pieces of the input: keep only a code
        return {"error": "unreadable"}
    return {"text": text, "language": info.language, "seconds": float(info.duration or 0.0)}


def main(argv: list[str]) -> int:
    memory_mb, cpu_s = int(argv[2]), int(argv[4])
    model_path, max_seconds, threads = argv[5], float(argv[6]), int(argv[7])
    _limits(memory_mb, cpu_s)
    data = sys.stdin.buffer.read(8 * 1024 * 1024)
    print(json.dumps(transcribe(data, model_path, max_seconds, threads)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
