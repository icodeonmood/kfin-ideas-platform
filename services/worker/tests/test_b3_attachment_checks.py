"""Regression tests from the B3 review (BLD-065): what the attachment checks read, and the limits that keep a
hostile file from hurting the worker. Pure functions plus the sandbox; no stack needed."""

from __future__ import annotations

import io
import random
import zipfile
from typing import Any

import generators as g
import pytest

from attachments import extract, sandbox
from attachments.service import _personal_data
from tests import files

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def finding(kind: str, data: bytes) -> dict[str, str] | None:
    e = extract.EXTRACTORS[kind](data)
    return _personal_data(e.pieces, e.columns, 0.2)


def test_spreadsheet_values_are_read_with_their_column_header() -> None:
    rng = random.Random(71)
    folios = [str(rng.randint(10_000_000, 99_999_999)) for _ in range(5)]
    csv = files.csv([["Folio No", "Units"]] + [[f, "10"] for f in folios])
    assert finding("csv", csv) == {"type": "Folio number", "code": "folio", "location": "row 2, column A"}
    accounts = [str(rng.randint(10**11, 10**12 - 1)) for _ in range(5)]
    sheet = files.xlsx([["Bank A/c", "Branch"]] + [[a, "Pune"] for a in accounts])
    hit = finding("xlsx", sheet)
    assert hit is not None and hit["code"] == "bank_account" and hit["location"] == "sheet 1, cell A2"


def test_every_row_is_checked_not_only_the_first_200() -> None:
    rng = random.Random(72)
    rows = [["step", "minutes"]] + [[f"s{i}", str(i)] for i in range(300)] + [["note", g.pan(rng)]]
    hit = finding("csv", files.csv(rows))
    assert hit is not None and hit["location"] == "row 302, column B"


def test_sheet_titles_are_checked_but_never_quoted_in_the_location() -> None:
    rng = random.Random(73)
    title = g.pan(rng)
    hit = finding("xlsx", files.xlsx([["Week", "Forms"], ["W1", "12"]], sheet=title))
    assert hit is not None and hit["location"] == "sheet 1 name"
    assert title not in str(hit)


@pytest.mark.parametrize(
    ("part", "where"),
    [
        ("word/footnotes.xml", "the footnotes"),
        ("word/comments.xml", "the comments"),
        ("word/header3.xml", "a page header"),
        ("docProps/core.xml", "the file properties"),
    ],
)
def test_word_parts_outside_the_body_are_checked(part: str, where: str) -> None:
    rng = random.Random(74)
    xml = f'<w:root xmlns:w="{W}"><w:p><w:r><w:t>Investor PAN {g.pan(rng)}</w:t></w:r></w:p></w:root>'
    doc = files.with_part(files.docx(["Synthetic notes"]), part, xml)
    assert finding("docx", doc) == {"type": "PAN", "code": "pan", "location": where}


def test_text_split_across_runs_is_joined() -> None:
    rng = random.Random(75)
    pan = g.pan(rng)
    body = (
        f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>PAN {pan[:5]}</w:t></w:r>'
        f"<w:r><w:t>{pan[5:]}</w:t></w:r></w:p></w:body></w:document>"
    )
    doc = files.with_part(files.docx(["x"]), "word/document.xml", body)
    hit = finding("docx", doc)
    assert hit is not None and hit["code"] == "pan"


def test_pdf_comments_are_checked() -> None:
    rng = random.Random(76)
    data = files.pdf(["Synthetic survey summary"], comment=f"Investor PAN {g.pan(rng)}")
    assert finding("pdf", data) == {"type": "PAN", "code": "pan", "location": "page 1 comment"}


def test_zip_bombs_are_refused_before_parsing(monkeypatch: Any) -> None:
    monkeypatch.setattr(extract, "MAX_UNPACKED_BYTES", 1024 * 1024)
    big = files.with_part(files.docx(["x"]), "word/media/blob.xml", "<a>" + "0" * (2 * 1024 * 1024) + "</a>")
    with pytest.raises(extract.TooBigToCheck):
        extract.docx(big)
    monkeypatch.setattr(extract, "MAX_UNPACKED_BYTES", 250 * 1024 * 1024)
    ratio = io.BytesIO()
    with zipfile.ZipFile(ratio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", b"\0" * (11 * 1024 * 1024))
    with pytest.raises(extract.TooBigToCheck):
        extract.check_zip(ratio.getvalue())


def test_cell_cap(monkeypatch: Any) -> None:
    monkeypatch.setattr(extract, "MAX_CELLS", 50)
    with pytest.raises(extract.TooBigToCheck):
        extract.csv_text(files.csv([[str(i), str(i)] for i in range(40)]))


def test_sandbox_runs_extractors_in_a_child_process() -> None:
    out = sandbox.extract("pdf", files.pdf(["Synthetic page"]))
    assert out.pieces == [("page 1", "Synthetic page")]
    with pytest.raises(sandbox.ExtractionFailed) as broken:
        sandbox.extract("pdf", b"%PDF-1.4\n garbage")
    assert broken.value.code in ("unreadable", "crashed")
    with pytest.raises(sandbox.ExtractionFailed) as slow:
        sandbox.extract("pdf", files.pdf(["x"]), timeout_s=0.001)
    assert slow.value.code == "timeout"
