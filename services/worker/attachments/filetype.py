"""Decide a file's type from its bytes, never from its name (AT-B3-06)."""

from __future__ import annotations

import codecs
import io
import re
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


# ---- the 1% Club's files (BLD-E007's wider list; L-HIDE.files/5) ---------------------------------------------

CFB = (
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # an OLE container: old Office files, and password-protected new ones
)
_ENCRYPTED_PACKAGE = "EncryptedPackage".encode("utf-16-le")
_HTML = re.compile(rb"^\s*(?:<!--.*?-->\s*)*<(?:!doctype\s+html|html|head|body)[\s>]", re.I | re.S)
MARKDOWN = (".md", ".markdown")


def _is_text(data: bytes) -> bool:
    """UTF-8 text with no NUL bytes (the first 64 KB; a character cut at the end does not count against it)."""
    head = data[:65536]
    if not head or b"\x00" in head:
        return False
    try:
        codecs.getincrementaldecoder("utf-8-sig")().decode(head, final=False)
    except UnicodeDecodeError:
        return False
    return True


def kind_of(data: bytes, name: str = "") -> str | None:
    """The real type for the 1% Club's files: `sniff`'s types, plus HTML (by its opening tag), a plain ZIP (no
    Office parts), and Markdown. Markdown has no signature, so a UTF-8 text file is Markdown only when it is named
    .md or .markdown; it is read as text whatever it holds (BLD-C106)."""
    if _is_text(data):
        if _HTML.match(data[:4096]):
            return "html"
        if name.lower().endswith(MARKDOWN):
            return "md"
    kind = sniff(data)
    if kind is not None:
        return kind
    if data.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            return None
        return None if "[Content_Types].xml" in names else "zip"
    return None


def is_locked(data: bytes) -> bool:
    """A password-protected file, known from its structure alone before anything reads its contents: a new Office
    file saved with a password is an OLE container holding an `EncryptedPackage`; a ZIP marks encrypted entries in
    its directory. A PDF's password is found when its text is read, after the virus scan."""
    if data.startswith(CFB):
        return _ENCRYPTED_PACKAGE in data
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return any(i.flag_bits & 0x1 for i in z.infolist())
        except zipfile.BadZipFile:
            return False
    return False
