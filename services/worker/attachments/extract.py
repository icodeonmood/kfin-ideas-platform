"""Text extraction with locations (§4.2 attachments step 3, day-one scope).

Every piece of text keeps where it came from ("page 2", "slide 3 notes", "sheet 2, cell B4"), so a rejection
can tell the person exactly where to look. Locations never quote the file's own words (a sheet is named by its
position, not its title), because the location is stored and shown.

Coverage (BLD-065):
- Spreadsheets and CSV: every row, each value read together with its column header, so context-dependent
  patterns ("Folio No" above a column of numbers) still match. Past MAX_CELLS the file is too big to check.
- Office files: the structured pass gives precise locations; then a sweep over every XML part (text boxes,
  footnotes, comments, headers and footers of every kind, charts, masters, file properties) catches the rest.
- PDF: the text layer, comments and form-field values. Any page with no text layer marks the file as scanned.
Extraction runs in a separate process with memory and time limits (attachments/sandbox.py); ZIP-based files
are refused before parsing if they would unpack to more than MAX_UNPACKED_BYTES.
"""

from __future__ import annotations

import csv
import html
import io
import re
import zipfile
from dataclasses import dataclass, field

MAX_CELLS = 500_000
MAX_UNPACKED_BYTES = 250 * 1024 * 1024
MAX_ZIP_ENTRIES = 5_000
MAX_RATIO = 200  # uncompressed / compressed, for entries over 10 MB unpacked


class TooBigToCheck(Exception):
    """The file would take too much memory or time to check fully; it is refused rather than half-checked."""


class Locked(Exception):
    """The file is protected by a password, so its text cannot be read or checked (L-HIDE.files/5)."""


class NotCheckable(Exception):
    """A file inside a ZIP is of a type the checks cannot read (L-HIDE.files/5: each file is checked)."""


@dataclass
class Extracted:
    pieces: list[tuple[str, str]] = field(default_factory=list)  # (location, text)
    columns: list[tuple[str, list[str]]] = field(
        default_factory=list
    )  # (location, values) for the column check
    scanned: bool = False
    pages: int | None = None  # a PDF's page count, for the file row ("140 KB, 3 pages")


def _col(n: int) -> str:
    name = ""
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def check_zip(data: bytes) -> None:
    """Refuse ZIP bombs before any library unpacks the file."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise TooBigToCheck("too_many_parts")
    total = 0
    for info in infos:
        total += info.file_size
        if info.file_size > 10 * 1024 * 1024 and info.file_size > MAX_RATIO * max(info.compress_size, 1):
            raise TooBigToCheck("compression_ratio")
    if total > MAX_UNPACKED_BYTES:
        raise TooBigToCheck("unpacked_size")


# ---- Office XML sweep ---------------------------------------------------------------------------------------

_BREAKS = re.compile(
    r"</(?:w:p|a:p|si|c|row|w:tc|a:tc|vt:lpwstr|dc:title|dc:subject|dc:creator|cp:keywords)>|<w:br/>|<w:tab/>"
)
_TAGS = re.compile(r"<[^>]+>")
_PART_NAMES = (
    (re.compile(r"^word/document\.xml$"), "the main text (including text boxes)"),
    (re.compile(r"^word/(footnotes|endnotes)\.xml$"), "the footnotes"),
    (re.compile(r"^word/comments[^/]*\.xml$"), "the comments"),
    (re.compile(r"^word/header\d*\.xml$"), "a page header"),
    (re.compile(r"^word/footer\d*\.xml$"), "a page footer"),
    (re.compile(r"^ppt/slides/slide(\d+)\.xml$"), "slide {0}"),
    (re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$"), "slide notes"),
    (re.compile(r"^ppt/(slideMasters|slideLayouts)/"), "a slide master or layout"),
    (re.compile(r"^ppt/comments/"), "the comments"),
    (re.compile(r"^(word|ppt|xl)/charts/"), "a chart"),
    (re.compile(r"^xl/(comments|threadedComments)"), "the cell comments"),
    (re.compile(r"^xl/sharedStrings\.xml$"), "the sheet text"),
    (re.compile(r"^docProps/"), "the file properties"),
)
_SKIP_PARTS = re.compile(
    r"^(\[Content_Types\]\.xml|.*/_rels/.*|.*\.rels|.*/(styles|theme\d*|fontTable|settings|webSettings|numbering"
    r"|presProps|viewProps|tableStyles|calcChain)\.xml|xl/worksheets/.*)$"
)


def _part_location(name: str) -> str:
    for pattern, label in _PART_NAMES:
        m = pattern.match(name)
        if m:
            return label.format(*m.groups())
    return "another part of the file"


def office_sweep(data: bytes) -> list[tuple[str, str]]:
    """Plain text of every XML part an Office file carries, with a plain-words location."""
    pieces: list[tuple[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in sorted(z.namelist()):
            if not name.endswith(".xml") or _SKIP_PARTS.match(name):
                continue
            raw = z.read(name).decode("utf-8", "replace")
            text = html.unescape(_TAGS.sub("", _BREAKS.sub("\n", raw)))
            if text.strip():
                pieces.append((f"{_part_location(name)}", text))
    return pieces


# ---- formats ------------------------------------------------------------------------------------------------


def pdf(data: bytes) -> Extracted:
    from pypdf import PdfReader

    out = Extracted()
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:  # pypdf has tried the empty password; a user password means it cannot be read
        try:
            readable = bool(reader.decrypt(""))
        except Exception:
            readable = False
        if not readable:
            raise Locked("pdf_password")
    out.pages = len(reader.pages)
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            out.scanned = True  # no text layer on this page: hold the whole file until OCR
        else:
            out.pieces.append((f"page {i}", text))
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            for key in ("/Contents", "/T", "/V"):
                value = obj.get(key)
                if value:
                    out.pieces.append((f"page {i} comment", str(value)))
    for name, fld in (reader.get_fields() or {}).items():
        value = fld.get("/V")
        if value:
            out.pieces.append(("a form field", f"{name} {value}"))
    if not reader.pages:
        out.scanned = True
    return out


def docx(data: bytes) -> Extracted:
    from docx import Document

    check_zip(data)
    out = Extracted()
    doc = Document(io.BytesIO(data))
    for i, para in enumerate(doc.paragraphs, start=1):
        if para.text.strip():
            out.pieces.append((f"paragraph {i}", para.text))
    for t, table in enumerate(doc.tables, start=1):
        for r, row in enumerate(table.rows, start=1):
            for c, cell in enumerate(row.cells, start=1):
                if cell.text.strip():
                    out.pieces.append((f"table {t}, row {r}, column {c}", cell.text))
    out.pieces.extend(office_sweep(data))
    return out


def pptx(data: bytes) -> Extracted:
    from pptx import Presentation

    check_zip(data)
    out = Extracted()
    deck = Presentation(io.BytesIO(data))
    for i, slide in enumerate(deck.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                texts.extend(cell.text for row in shape.table.rows for cell in row.cells)
        if any(t.strip() for t in texts):
            out.pieces.append((f"slide {i}", "\n".join(texts)))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text
            if notes.strip():
                out.pieces.append((f"slide {i} notes", notes))
    out.pieces.extend(office_sweep(data))  # group shapes, charts, masters, comments, properties
    return out


class _Grid:
    """Collects a sheet's cells: each value is read with its column header; values also feed the column check."""

    def __init__(self, out: Extracted, prefix: str):
        self.out, self.prefix = out, prefix
        self.headers: dict[int, str] = {}
        self.columns: dict[int, list[str]] = {}
        self.cells = 0

    def add(self, r: int, c: int, text: str, where: str) -> None:
        self.cells += 1
        if self.cells > MAX_CELLS:
            raise TooBigToCheck("too_many_cells")
        if r == 1:
            self.headers[c] = text
            self.out.pieces.append((where, text))
            return
        header = self.headers.get(c, "")
        joined = f"{header} {text}" if header else text
        self.out.pieces.append((where, joined))
        self.columns.setdefault(c, []).append(joined)

    def finish(self) -> None:
        self.out.columns.extend((f"{self.prefix}column {_col(c)}", v) for c, v in self.columns.items())


def xlsx(data: bytes) -> Extracted:
    from openpyxl import load_workbook

    check_zip(data)
    out = Extracted()
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        for s, ws in enumerate(wb.worksheets, start=1):
            out.pieces.append((f"sheet {s} name", ws.title))
            grid = _Grid(out, f"sheet {s}, ")
            for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
                for c, value in enumerate(row, start=1):
                    if value is None or str(value).strip() == "":
                        continue
                    grid.add(r, c, str(value), f"sheet {s}, cell {_col(c)}{r}")
            grid.finish()
    finally:
        wb.close()
    out.pieces.extend(office_sweep(data))  # comments, charts, shared strings, file properties
    return out


def csv_text(data: bytes) -> Extracted:
    out = Extracted()
    grid = _Grid(out, "")
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
    for r, row in enumerate(reader, start=1):
        for c, value in enumerate(row, start=1):
            if value.strip():
                grid.add(r, c, value, f"row {r}, column {_col(c)}")
    grid.finish()
    return out


# ---- OCR (week 3): images and scanned PDF pages ------------------------------------------------------------


def image_ocr(data: bytes) -> Extracted:
    from attachments.ocr import read_text

    out = Extracted()
    text = read_text(data)
    if text:
        out.pieces.append(("the image", text))
    return out


def pdf_ocr(data: bytes) -> Extracted:
    """The text layer, then OCR of the images on every page that has no text layer."""
    from pypdf import PdfReader

    from attachments.ocr import MAX_IMAGES_PER_PAGE, MAX_SCANNED_PAGES, read_text

    out = pdf(data)
    out.scanned = False
    reader = PdfReader(io.BytesIO(data))
    scanned = 0
    for i, page in enumerate(reader.pages, start=1):
        if (page.extract_text() or "").strip():
            continue
        scanned += 1
        if scanned > MAX_SCANNED_PAGES:
            raise TooBigToCheck("too_many_scanned_pages")
        for n, image in enumerate(page.images, start=1):
            if n > MAX_IMAGES_PER_PAGE:
                raise TooBigToCheck("too_many_images")
            text = read_text(image.data)
            if text:
                out.pieces.append((f"page {i} (scanned)", text))
    return out


# ---- the 1% Club's wider type list (BLD-E007, L-HIDE.files/5): Markdown, HTML and ZIP -------------------------

MAX_ZIP_FILES = 100
_SCRIPT = re.compile(r"(?is)<(script|style)\b.*?</\1\s*>")
_BREAKS_HTML = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|tr|h[1-6]|td|th|title)>")
_JUNK = re.compile(r"(^|/)(__MACOSX/|\.DS_Store$)")


def _lines(text: str) -> Extracted:
    out = Extracted()
    for i, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            out.pieces.append((f"line {i}", line))
    return out


def text_file(data: bytes) -> Extracted:
    """Markdown or plain text: every line, by number."""
    return _lines(data.decode("utf-8-sig", errors="replace"))


def html_text(data: bytes) -> Extracted:
    """HTML: the text a reader sees, scripts and styles left out (comments and attributes are swept too)."""
    raw = data.decode("utf-8-sig", errors="replace")
    attrs = " ".join(re.findall(r"""(?:alt|title|content|value|href)\s*=\s*["']([^"']*)["']""", raw, re.I))
    text = html.unescape(_TAGS.sub(" ", _BREAKS_HTML.sub("\n", _SCRIPT.sub(" ", raw))))
    out = _lines(text)
    if attrs.strip():
        out.pieces.append(("the page's hidden text", html.unescape(attrs)))
    return out



def _inner(kind: str, data: bytes) -> Extracted:
    """One file inside a ZIP, read the way it would be read on its own (images and scanned pages by OCR)."""
    if kind in ("png", "jpg"):
        return image_ocr(data)
    if kind == "pdf":
        got = pdf(data)
        return pdf_ocr(data) if got.scanned else got
    return EXTRACTORS[kind](data)


def zip_files(data: bytes) -> Extracted:
    """A ZIP is unpacked and every file in it checked (L-HIDE.files/5). Locations name a file by its position, never
    by its name. A file the checks cannot read, a ZIP inside the ZIP or a locked file stops the whole ZIP."""
    from attachments.filetype import kind_of

    check_zip(data)
    out = Extracted()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        members = [i for i in z.infolist() if not i.is_dir() and not _JUNK.search(i.filename)]
        if len(members) > MAX_ZIP_FILES:
            raise TooBigToCheck("too_many_files")
        for n, info in enumerate(members, start=1):
            if info.flag_bits & 0x1:
                raise Locked("zip_password")
            inner = z.read(info)
            kind = kind_of(inner, info.filename)
            if kind is None or kind == "zip" or kind not in INNER_KINDS:
                raise NotCheckable("zip_member_type")
            got = _inner(kind, inner)
            out.pieces.extend((f"file {n} in the ZIP, {where}", text) for where, text in got.pieces)
            out.columns.extend((f"file {n} in the ZIP, {where}", values) for where, values in got.columns)
    return out


EXTRACTORS = {
    "pdf": pdf,
    "docx": docx,
    "pptx": pptx,
    "xlsx": xlsx,
    "csv": csv_text,
    "png_ocr": image_ocr,
    "jpg_ocr": image_ocr,
    "pdf_ocr": pdf_ocr,
    "md": text_file,
    "html": html_text,
    "zip": zip_files,
}
INNER_KINDS = frozenset({"pdf", "docx", "pptx", "xlsx", "csv", "png", "jpg", "md", "html"})
