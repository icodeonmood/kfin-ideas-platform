"""Week-3 file checks (§4.2 attachments, D3), behind `attachments.deep_check`: OCR for images and scanned pages,
the gatekeeper over file text, attachment-digest and the file text in the search index. Host-side, with
OCR_MODE=fake (a synthetic image carries its text in metadata); the real Tesseract in the worker image is covered
by `test_rd_ocr_stack.py`."""

from __future__ import annotations

import secrets
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from attachments import deep, service, store
from attachments.extract import Extracted
from core import killswitch
from core.config import get_settings
from gateway.routes import FAKE_SCRIPT
from index.indexer import Indexer
from tests import files, helpers

pytestmark = pytest.mark.stack


@pytest.fixture
def draft(db: Any, company_repo: Any, test_database: str) -> Any:
    killswitch.clear_cache()
    FAKE_SCRIPT.clear()
    db.execute("TRUNCATE attachments, jobs CASCADE")
    code = f"CTR-{secrets.token_hex(3)}"
    row = db.execute(
        "INSERT INTO ideas (contributor_code, stage, canvas) VALUES (%s, 'draft', %s) RETURNING id",
        (code, Jsonb(helpers.synthetic_canvas())),
    ).fetchone()
    killswitch.set_switch(db, "attachments.deep_check", "on", reason="test: deep checks on", actor="test")
    killswitch.clear_cache()
    yield {"db": db, "idea": str(row["id"]), "code": code, "repo": company_repo, "database": test_database}
    killswitch.clear_cache()


def _process(d: Any, name: str, data: bytes) -> dict[str, Any]:
    att = service.accept(d["db"], idea_uuid=d["idea"], uploaded_by_code=d["code"], name=name, data=data)
    service.process(d["db"], att["id"])
    return dict(d["db"].execute("SELECT * FROM attachments WHERE id = %s", (att["id"],)).fetchone())


def _submit(d: Any) -> str:
    """Give the draft an IDEA- ID and move it on, as submit and the scan would."""
    db = d["db"]
    n = db.execute("SELECT next_number('IDEA', '2026') AS n").fetchone()["n"]
    idea_id = f"IDEA-2026-{n:06d}"
    db.execute(
        "UPDATE ideas SET idea_id = %s, submission_id = %s, stage = 'scanned', submitted_at = now() WHERE id = %s",
        (idea_id, f"SUB-2026-{n:06d}", d["idea"]),
    )
    return idea_id


def test_switched_off_images_wait_as_on_day_one(draft: Any) -> None:
    killswitch.set_switch(
        draft["db"], "attachments.deep_check", "off", reason="test: deep checks off", actor="test"
    )
    killswitch.clear_cache()
    row = _process(draft, "photo.png", files.png_with_text("Courier slips signed twice"))
    assert row["state"] == "awaiting_check" and row["checks"] == {"waiting_for": "ocr"}


def test_ocr_text_with_a_pan_is_refused_with_where_not_what(draft: Any) -> None:
    pan = "QXRPK4821M"  # synthetic, PAN-shaped (fourth letter P)
    row = _process(draft, "form.png", files.png_with_text(f"Investor PAN {pan} on the form"))
    assert row["state"] == "rejected"
    assert row["rejection"]["location"] == "the image" and pan not in str(row["rejection"])
    assert store.exists(get_settings().s3_bucket_quarantine, row["store_key"]) is False


def test_a_clean_image_is_checked_by_the_gatekeeper_then_opens(draft: Any) -> None:
    row = _process(draft, "board.png", files.png_with_text("Payout file re-keyed by hand twice a day"))
    assert row["state"] == "clean"
    assert row["checks"] == {"patterns": True, "ocr": True, "gatekeeper": True}
    calls = draft["db"].execute("SELECT agent, ref_id FROM llm_calls ORDER BY id").fetchall()
    assert [c["agent"] for c in calls] == ["gatekeeper"] and calls[0]["ref_id"].startswith("ATTCHK-")
    # Only the verdict is kept: the throwaway scope's tags are gone.
    assert (
        draft["db"]
        .execute("SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id LIKE 'ATTCHK-%%'")
        .fetchone()["n"]
        == 0
    )
    job = draft["db"].execute("SELECT type FROM jobs WHERE type = 'attachment.digest'").fetchone()
    assert job is not None


def test_the_gatekeeper_refuses_an_investor_named_in_the_file(draft: Any) -> None:
    row = _process(
        draft, "letter.pdf", files.pdf(["The investor Shri Ramesh Iyer called about his redemption delay."])
    )
    assert row["state"] == "rejected" and row["rejection"]["code"] == "gatekeeper"
    assert row["rejection"]["location"] == "page 1" and "Ramesh" not in str(row["rejection"])


def test_a_scanned_pdf_is_read_by_ocr(draft: Any) -> None:
    row = _process(draft, "scan.pdf", files.scanned_pdf("Branch register"))
    assert row["state"] == "clean" and row["checks"]["ocr"] is True


def test_with_the_assistant_off_text_files_fall_back_and_images_wait(draft: Any) -> None:
    db = draft["db"]
    killswitch.set_switch(db, "ai.all", "off", reason="test: assistant off", actor="test")
    killswitch.clear_cache()
    text = _process(draft, "note.pdf", files.pdf(["Exceptions are cleared by the next business day."]))
    assert text["state"] == "clean" and text["checks"]["gatekeeper_skipped"] is True
    image = _process(draft, "note.png", files.png_with_text("Exceptions cleared next day"))
    assert image["state"] == "awaiting_check" and image["checks"] == {"waiting_for": "gatekeeper"}
    assert service.recheck(db) == 0  # still no assistant: nothing to gain from another pass
    # Back on: the recheck sends held files through again.
    killswitch.set_switch(db, "ai.all", "on", reason="test: assistant on", actor="test")
    killswitch.clear_cache()
    assert service.recheck(db) == 1
    service.process(db, image["id"])
    assert (
        db.execute("SELECT state FROM attachments WHERE id = %s", (image["id"],)).fetchone()["state"]
        == "clean"
    )


def test_the_digest_waits_for_submit_then_reaches_the_canvas_and_the_index(draft: Any) -> None:
    db = draft["db"]
    row = _process(draft, "volumes.png", files.png_with_text("Hyderabad NIGO forms 812 in Sep 2026"))
    assert service.digest(db, row["id"]) == "waiting_for_submit"
    idea_id = _submit(draft)
    assert service.digest(db, row["id"]) == "done"
    att = db.execute(
        "SELECT digest, digest_meta, indexed_at FROM attachments WHERE id = %s", (row["id"],)
    ).fetchone()
    assert att["digest"] and att["digest_meta"]["generated_by"].startswith("attachment-digest/")
    assert att["digest_meta"]["claims"][0]["figure"] == "812" and att["indexed_at"] is not None
    chunks = db.execute(
        "SELECT file_type, trust, visibility FROM chunks WHERE attachment_id = %s", (row["id"],)
    ).fetchall()
    assert [(c["file_type"], c["trust"], c["visibility"]) for c in chunks] == [
        ("attachment", "unverified", "org")
    ]
    canvas = db.execute("SELECT canvas FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone()["canvas"]
    assert any(a["id"] == row["id"] and a["digest"] for a in canvas["attachments"])
    event = db.execute(
        "SELECT payload FROM outbox WHERE event_type = 'idea.updated' AND aggregate_id = %s", (idea_id,)
    ).fetchone()
    assert event["payload"]["history"][0]["event"] == "research_digest"
    # A full index rebuild keeps research-file text: it comes from the file store, not the repo.
    Indexer(helpers.settings_for(draft["repo"], draft["database"])).run_once(rebuild=True)
    assert (
        db.execute("SELECT count(*) AS n FROM chunks WHERE attachment_id = %s", (row["id"],)).fetchone()["n"]
        == 1
    )


def test_long_text_is_split_into_gatekeeper_pieces_and_sheets_stop_at_200_rows() -> None:
    pieces = [(f"sheet 1, row {r}, column A", "x" * 100) for r in range(1, 400)]
    kept = [p for p in pieces if deep._within_rows(p[0])]
    assert len(kept) == 200
    groups = deep.batches([("page 1", "a" * 20_000)], deep.GATEKEEPER_PIECE_CHARS)
    assert [len(g[0][1]) for g in groups] == [8_000, 8_000, 4_000]
    assert deep.batches([("p1", "a"), ("p2", "b")], 10) == [[("p1", "a"), ("p2", "b")]]
    assert Extracted().pieces == []
