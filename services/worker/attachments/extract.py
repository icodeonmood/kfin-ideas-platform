"""Text-layer extraction with locations (§4.2 attachments step 3, day-one scope).

Every piece of text keeps where it came from ("page 2", "slide 3 notes", "sheet Data, cell B4"), so a rejection
can tell the person exactly where to look. Spreadsheets and CSV: sheet names, headers and the first 200 rows.
A PDF with any page that has no text layer is treated as scanned and held for OCR (week 3).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

MAX_ROWS = 200


@dataclass
class Extracted:
    pieces: list[tuple[str, str]] = field(default_factory=list)  # (location, text)
    columns: list[tuple[str, list[str]]] = field(
        default_factory=list
    )  # (location, values) for the column check
    scanned: bool = False


def _col(n: int) -> str:
    name = ""
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def pdf(data: bytes) -> Extracted:
    from pypdf import PdfReader

    out = Extracted()
    reader = PdfReader(io.BytesIO(data))
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            out.scanned = True  # no text layer on this page: hold the whole file until OCR
        else:
            out.pieces.append((f"page {i}", text))
    if not reader.pages:
        out.scanned = True
    return out


def docx(data: bytes) -> Extracted:
    from docx import Document

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
    for s, section in enumerate(doc.sections, start=1):
        for part, name in ((section.header, "header"), (section.footer, "footer")):
            text = "\n".join(p.text for p in part.paragraphs if p.text.strip())
            if text:
                out.pieces.append((f"section {s} {name}", text))
    return out


def pptx(data: bytes) -> Extracted:
    from pptx import Presentation

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
    return out


def xlsx(data: bytes) -> Extracted:
    from openpyxl import load_workbook

    out = Extracted()
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    for ws in wb.worksheets:
        out.pieces.append((f"sheet {ws.title}", ws.title))
        columns: dict[int, list[str]] = {}
        for r, row in enumerate(ws.iter_rows(max_row=MAX_ROWS + 1, values_only=True), start=1):
            for c, value in enumerate(row, start=1):
                if value is None or str(value).strip() == "":
                    continue
                text = str(value)
                out.pieces.append((f"sheet {ws.title}, cell {_col(c)}{r}", text))
                if r > 1:  # row 1 is usually headers
                    columns.setdefault(c, []).append(text)
        out.columns.extend((f"sheet {ws.title}, column {_col(c)}", vals) for c, vals in columns.items())
    wb.close()
    return out


def csv_text(data: bytes) -> Extracted:
    out = Extracted()
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
    columns: dict[int, list[str]] = {}
    for r, row in enumerate(reader, start=1):
        if r > MAX_ROWS + 1:
            break
        for c, value in enumerate(row, start=1):
            if value.strip():
                out.pieces.append((f"row {r}, column {_col(c)}", value))
                if r > 1:
                    columns.setdefault(c, []).append(value)
    out.columns.extend((f"column {_col(c)}", vals) for c, vals in columns.items())
    return out


EXTRACTORS = {"pdf": pdf, "docx": docx, "pptx": pptx, "xlsx": xlsx, "csv": csv_text}
