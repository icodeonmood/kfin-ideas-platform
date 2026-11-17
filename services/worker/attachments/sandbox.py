"""Run a file extractor in a separate process with a memory cap and a time limit.

Parsers for PDF and Office files are large and see hostile input. A file that would exhaust memory or hang
must cost one child process, never the worker that also runs scans and the repo writer.
"""

from __future__ import annotations

import multiprocessing
import sys
from multiprocessing.connection import Connection
from typing import Any

from attachments.extract import EXTRACTORS, Extracted, Locked, NotCheckable, TooBigToCheck
from attachments.ocr import OcrFailed

TIMEOUT_S = 90.0
MEMORY_MB = 768


class ExtractionFailed(Exception):
    """The file could not be read within the limits. `code` is safe to log and store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _child(kind: str, data: bytes, memory_mb: int, conn: Connection) -> None:
    if sys.platform.startswith("linux"):
        import resource

        limit = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    try:
        result: Any = ("ok", EXTRACTORS[kind](data))
    except TooBigToCheck as exc:
        result = ("too_big", str(exc))
    except Locked as exc:
        result = ("locked", str(exc))
    except NotCheckable as exc:
        result = ("not_checkable", str(exc))
    except MemoryError:
        result = ("too_big", "memory")
    except OcrFailed as exc:
        # OCR that is not installed is our problem, not the file's: the file waits, it is not refused.
        result = ("unavailable" if exc.code == "ocr_not_installed" else "error", exc.code)
    except Exception as exc:  # hostile or broken files: report the type only, never the message
        result = ("error", type(exc).__name__)
    try:
        conn.send(result)
    except Exception:
        conn.send(("too_big", "result_size"))
    finally:
        conn.close()


def extract(kind: str, data: bytes, *, timeout_s: float = TIMEOUT_S, memory_mb: int = MEMORY_MB) -> Extracted:
    if kind not in EXTRACTORS:
        raise ExtractionFailed("no_extractor")
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(kind, data, memory_mb, child), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout_s):
            raise ExtractionFailed("timeout")
        try:
            status, value = parent.recv()
        except EOFError:
            raise ExtractionFailed("crashed") from None
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        parent.close()
    if status == "ok":
        assert isinstance(value, Extracted)
        return value
    if status == "unavailable":
        raise ExtractionFailed("ocr_unavailable")
    if status in ("locked", "not_checkable"):  # the old pipeline treats both as unreadable, as before
        raise ExtractionFailed(status)
    raise ExtractionFailed("too_big" if status == "too_big" else "unreadable")
