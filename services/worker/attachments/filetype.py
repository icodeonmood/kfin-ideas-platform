"""Decide a file's type from its bytes, never from its name (AT-B3-06)."""

from __future__ import annotations

import io
import zipfile

SIGNATURES = {
    b"%PDF-": "pdf",
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
}
OFFICE_PARTS = {"word/": "docx", "ppt/": "pptx", "xl/": "xlsx"}


def sniff(data: bytes) -> str | None:
    """The real type (pdf, png, jpg, docx, pptx, xlsx, csv) or None for anything else."""
    for magic, kind in SIGNATURES.items():
        if data.startswith(magic):
            return kind
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" not in names:
            return None
        for prefix, kind in OFFICE_PARTS.items():
            if any(n.startswith(prefix) for n in names):
                return kind
        return None
    return "csv" if _looks_like_csv(data) else None


def _looks_like_csv(data: bytes) -> bool:
    """CSV has no signature: accept UTF-8 text with no NUL bytes and a consistent comma structure."""
    if not data or b"\x00" in data[:65536]:
        return False
    try:
        text = data[:65536].decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    lines = [ln for ln in text.splitlines() if ln.strip()][:20]
    if len(lines) < 2:
        return False
    counts = {ln.count(",") for ln in lines[:-1]}  # the last line may be cut off
    return len(counts) == 1 and next(iter(counts)) >= 1
