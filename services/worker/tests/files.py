"""Synthetic test files built in memory at run time (AT-B3-06/07). Nothing here is a real document."""

from __future__ import annotations

import io
import struct
import zlib


def pdf(pages: list[str]) -> bytes:
    """A small valid PDF with one text line per page (a real text layer). An empty string makes a page with no
    text layer, which the checks treat as scanned."""
    objects: list[bytes] = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    for i, text in enumerate(pages):
        content_obj = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_obj} 0 R "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode()
        )
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode() if text else b"0 0 1 rg 72 72 100 100 re f"
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


def png() -> bytes:
    """A 1×1 white PNG."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    ihdr = struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table:
        t = doc.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                t.cell(r, c).text = value
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def xlsx(rows: list[list[str]], sheet: str = "Data") -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def csv(rows: list[list[str]]) -> bytes:
    return ("\n".join(",".join(r) for r in rows) + "\n").encode()


def eicar_docx() -> bytes:
    """A Word file carrying the industry-standard antivirus test string (harmless) as an embedded part. The
    string is assembled at run time so the repo never holds it. ClamAV only flags the string on its own (the
    EICAR rule), so it sits in its own part inside an otherwise ordinary .docx that passes the type check."""
    import zipfile

    parts = ["X5O!P%@AP[4\\PZX54(P^)7CC)7}$", "EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*"]
    src = zipfile.ZipFile(io.BytesIO(docx(["Synthetic notes"])))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            z.writestr(item, src.read(item.filename))
        z.writestr("word/embeddings/test.bin", "".join(parts).encode())
    return out.getvalue()
