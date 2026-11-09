"""OCR for images and scanned PDF pages (§4.2 attachments step 3, D3 week 3): Tesseract, English and Hindi.

It runs inside the extraction sandbox (attachments/sandbox.py), so a hostile image costs one child process.
Tesseract reads the image from stdin and writes text to stdout; nothing is written to disk and nothing it reads
is logged. `OCR_MODE=fake` is for host-side tests only: a synthetic test image carries the text it shows in a
metadata field (`ocr-text`), so tests can say exactly what the "photo" contains without Tesseract installed.
"""

from __future__ import annotations

import io
import subprocess

from core.config import get_settings

TESSERACT_TIMEOUT_S = 60.0
MAX_SCANNED_PAGES = 50
MAX_IMAGES_PER_PAGE = 10


class OcrFailed(Exception):
    """OCR could not read the image. `code` is safe to log and store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fake(image: bytes) -> str:
    from PIL import Image

    try:
        with Image.open(io.BytesIO(image)) as img:
            return str(img.info.get("ocr-text") or "")
    except Exception as exc:
        raise OcrFailed("unreadable_image") from exc


def _tesseract(image: bytes) -> str:
    s = get_settings()
    try:
        proc = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", s.ocr_languages, "--psm", "3"],
            input=image,
            capture_output=True,
            timeout=TESSERACT_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError:
        raise OcrFailed("ocr_not_installed") from None
    except subprocess.TimeoutExpired:
        raise OcrFailed("ocr_timeout") from None
    if proc.returncode != 0:
        raise OcrFailed("ocr_failed")
    return proc.stdout.decode("utf-8", errors="replace")


def read_text(image: bytes) -> str:
    """The text in one image, as plain lines."""
    text = _fake(image) if get_settings().ocr_mode == "fake" else _tesseract(image)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
