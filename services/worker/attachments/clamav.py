"""Virus scan through clamd's INSTREAM command (§4.2 attachments step 2). KFin's standard scanner in UAT/prod."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

from core.config import get_settings

CHUNK = 64 * 1024


class ScannerUnavailable(RuntimeError):
    """The scanner did not answer: the file stays in quarantine and the job retries."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str | None  # the virus name clamd reported, for the audit trail; never shown to people


def scan_bytes(data: bytes, timeout: float = 60.0) -> ScanResult:
    s = get_settings()
    try:
        with socket.create_connection((s.clamav_host, s.clamav_port), timeout=timeout) as sock:
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), CHUNK):
                part = data[i : i + CHUNK]
                sock.sendall(struct.pack("!I", len(part)) + part)
            sock.sendall(struct.pack("!I", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                reply += chunk
    except OSError as exc:
        raise ScannerUnavailable(type(exc).__name__) from None
    text = reply.rstrip(b"\0").decode("utf-8", "replace")
    if text.endswith("OK"):
        return ScanResult(clean=True, signature=None)
    if text.endswith("FOUND"):
        return ScanResult(clean=False, signature=text.split(":", 1)[-1].removesuffix("FOUND").strip())
    raise ScannerUnavailable("unexpected_reply")


def ping(timeout: float = 3.0) -> bool:
    """Whether the scanner answers (`zPING` → `PONG`). Used by the scanner watch (§7.6)."""
    s = get_settings()
    try:
        with socket.create_connection((s.clamav_host, s.clamav_port), timeout=timeout) as sock:
            sock.sendall(b"zPING\0")
            return sock.recv(16).startswith(b"PONG")
    except OSError:
        return False
