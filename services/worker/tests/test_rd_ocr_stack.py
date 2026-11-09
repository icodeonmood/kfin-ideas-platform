"""Real OCR in the worker image (§4.2 attachments, D3): with `attachments.deep_check` on, a photographed form with
a PAN is read by Tesseract and refused with where it was, and a photo of plain process notes becomes clean. Runs
against the running stack through the web API, because Tesseract lives in the worker container, not on the
host. The switch is put back the way it was."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest

from core import killswitch
from core.db import connect
from tests import files
from tests.test_b3_06_attachments import new_draft, settle, upload
from tests.web import people

pytestmark = pytest.mark.stack


@pytest.fixture
def deep_on() -> Iterator[Any]:
    with connect(autocommit=True) as conn, people(conn) as make:
        before = conn.execute(
            "SELECT state FROM kill_switches WHERE name = 'attachments.deep_check'"
        ).fetchone()
        killswitch.set_switch(
            conn, "attachments.deep_check", "on", reason="stack test: real OCR", actor="test"
        )
        time.sleep(
            killswitch.CACHE_SECONDS + 1
        )  # the worker reads switches through a 10-second cache (BLD-006)
        try:
            yield make, conn
        finally:
            killswitch.set_switch(
                conn, "attachments.deep_check", before["state"], reason="stack test: put back", actor="test"
            )


def test_tesseract_reads_a_photographed_pan_and_the_file_is_refused(deep_on: Any) -> None:
    make, _ = deep_on
    b = make().browser()
    draft = new_draft(b)
    pan = "QXRPK4821M"  # synthetic, PAN-shaped
    # ocr_text is deliberately empty: only real OCR can find the PAN.
    r = upload(b, draft, "form.png", files.png_with_text(f"Investor PAN {pan}", ocr_text=""), "png")
    assert r.status_code == 201, r.text
    body = settle(b, r.json()["id"], timeout=120)
    assert body["state"] == "rejected", body
    assert body["rejection"]["location"] == "the image" and pan not in str(body)


def test_a_photo_of_process_notes_becomes_clean(deep_on: Any) -> None:
    make, _ = deep_on
    b = make().browser()
    draft = new_draft(b)
    r = upload(
        b,
        draft,
        "board.png",
        files.png_with_text("Payout file re-keyed by hand twice a day", ocr_text=""),
        "png",
    )
    body = settle(b, r.json()["id"], timeout=120)
    assert body["state"] == "clean", body
