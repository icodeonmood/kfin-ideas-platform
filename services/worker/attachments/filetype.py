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


# ---- the 1% Club's files (BLD-E007's wider list; L-HIDE.files/5, /6) ---------------------------------------------
#
# Before the virus scan only the bytes are looked at: the size, the magic numbers and, for text, its encoding
# (`kind_before_scan`, `locked_before_scan`). A file that starts as a ZIP is `CONTAINER` until then: its directory,
# which says whether it is Word, PowerPoint, Excel or a plain ZIP, is read after the scan in the sandbox
# (`container_kind`, from `extract.container`), as are a ZIP's passwords and the types inside it (non-negotiable 8).

CFB = (
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # an OLE container: old Office files, and password-protected new ones
)
_ENCRYPTED_PACKAGE = "EncryptedPackage".encode("utf-16-le")
_HTML = re.compile(rb"^\s*(?:<!--.*?-->\s*)*<(?:!doctype\s+html|html|head|body)[\s>]", re.I | re.S)
MARKDOWN = (".md", ".markdown")
ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
CONTAINER = "container"  # a ZIP-family file before the scan: one of CONTAINER_TYPES, read after it
CONTAINER_TYPES = ("docx", "pptx", "xlsx", "zip")


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


def kind_before_scan(data: bytes, name: str = "") -> str | None:
    """The type from the bytes alone, before the virus scan: PDF, PNG and JPEG by their magic numbers, HTML by its
    opening tag, Markdown (UTF-8 text named .md or .markdown, read as text whatever it holds, BLD-C106), CSV by its
    commas, and `CONTAINER` for anything that starts as a ZIP. Nothing is unpacked or parsed."""
    if _is_text(data):
        if _HTML.match(data[:4096]):
            return "html"
        if name.lower().endswith(MARKDOWN):
            return "md"
    for magic, kind in SIGNATURES.items():
        if data.startswith(magic):
            return kind
    if data.startswith(ZIP_MAGIC):
        return CONTAINER
    return "csv" if _looks_like_csv(data) else None


def locked_before_scan(data: bytes) -> bool:
    """A new Office file saved with a password, known from the bytes alone: an OLE container (its magic number)
    holding a stream named `EncryptedPackage` (a byte search, nothing parsed). A ZIP's password is read from its
    directory and a PDF's from its text, both after the scan."""
    return data.startswith(CFB) and _ENCRYPTED_PACKAGE in data


def container_kind(data: bytes) -> str | None:
    """After the scan, in the sandbox only: which ZIP-family type a file is, from its directory (Office files carry
    `[Content_Types].xml` and their own parts); None for an Office file of no known kind or a broken ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
    except zipfile.BadZipFile:
        return None
    if "[Content_Types].xml" not in names:
        return "zip"
    for prefix, kind in OFFICE_PARTS.items():
        if any(n.startswith(prefix) for n in names):
            return kind
    return None


def kind_of(data: bytes, name: str = "") -> str | None:
    """After the scan, in the sandbox only (a file inside a ZIP): the type from the bytes and, for a ZIP-family
    file, its directory."""
    kind = kind_before_scan(data, name)
    return container_kind(data) if kind == CONTAINER else kind
