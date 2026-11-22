"""Research attachments over HTTP against the running stack.

AT-B3-06: a sixth file, a file over 20 MB and a disallowed type (by signature, not extension) are refused;
uploads land in quarantine; the EICAR test file is rejected and deleted.
AT-B3-07: a text-layer PDF with a generated PAN is rejected with the page number; a clean PDF becomes clean and
opens for a reviewer; a PNG becomes awaiting_check and returns 403 to everyone.
Plus: Word tables and spreadsheet columns are checked, files are only visible to the owner and review roles,
and every download is written to audit_log.
"""

from __future__ import annotations

import random
import time
from collections.abc import Iterator
from typing import Any

import generators as g
import pytest

from attachments import store
from core import killswitch
from core.config import get_settings
from core.db import connect
from tests import files
from tests.test_b3_submissions_api import full_canvas
from tests.web import Browser, people

pytestmark = pytest.mark.stack

MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "csv": "text/csv",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@pytest.fixture
def setup() -> Iterator[Any]:
    with connect(autocommit=True) as conn, people(conn) as make:
        yield make, conn


def new_draft(b: Browser) -> str:
    r = b.post("/api/submissions", json={"mode": "full", "canvas": full_canvas()})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def upload(b: Browser, draft: str, name: str, data: bytes, kind: str = "pdf") -> Any:
    return b.post(
        f"/api/submissions/{draft}/attachments",
        files={"file": (name, data, MIME.get(kind, "application/octet-stream"))},
    )


def settle(b: Browser, att_id: str, timeout: float = 90.0) -> dict[str, Any]:
    """Wait for the worker's checks to finish (ClamAV can be slow on a cold start)."""
    deadline = time.monotonic() + timeout
    while True:
        r = b.get(f"/api/attachments/{att_id}/status")
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        if body["state"] not in ("quarantine", "processing"):
            return body
        if time.monotonic() > deadline:
            raise AssertionError(f"{att_id} still {body['state']} after {timeout}s")
        time.sleep(0.5)


def in_bucket(conn: Any, att_id: str) -> tuple[bool, bool]:
    key = conn.execute("SELECT store_key FROM attachments WHERE id = %s", (att_id,)).fetchone()
    s = get_settings()
    k = key["store_key"] if key else f"att/{att_id}"
    return store.exists(s.s3_bucket_quarantine, k), store.exists(s.s3_bucket_clean, k)


def test_limits_type_by_signature_and_quarantine(setup: Any) -> None:
    make, conn = setup
    b = make().browser()
    draft = new_draft(b)

    # A disallowed type is refused by its bytes, whatever its name says; an allowed type with an odd name is fine.
    exe = b"MZ\x90\x00" + bytes(200)
    assert upload(b, draft, "budget.pdf", exe).json() == {"error": "type_not_allowed"}
    assert upload(b, draft, "budget.pdf", exe).status_code == 415
    renamed = upload(b, draft, "notes.txt", files.pdf(["Synthetic notes about SIP forms"]))
    assert renamed.status_code == 201, renamed.text

    # Uploads land in quarantine first: the response says so and the check job is queued.
    body = renamed.json()
    assert body["state"] == "quarantine" and body["id"].startswith("ATT-")
    job = conn.execute(
        "SELECT type FROM jobs WHERE dedupe_key = %s", (f"attachment:{body['id']}",)
    ).fetchone()
    assert job is not None and job["type"] == "attachment.process"
    row = conn.execute("SELECT mime, sha256 FROM attachments WHERE id = %s", (body["id"],)).fetchone()
    assert row["mime"] == "application/pdf" and len(row["sha256"]) == 64

    # Five files is the limit; the sixth is refused.
    for i in range(4):
        r = upload(b, draft, f"table-{i}.csv", files.csv([["step", "minutes"], ["check", str(i + 3)]]), "csv")
        assert r.status_code == 201, r.text
    sixth = upload(b, draft, "sixth.csv", files.csv([["a", "b"], ["1", "2"]]), "csv")
    assert sixth.status_code == 409 and sixth.json()["error"] == "too_many_files"

    # Over 20 MB is refused before it is stored (on a fresh draft so the count is not what stops it).
    other = new_draft(b)
    big = b"%PDF-1.4\n" + bytes(20 * 1024 * 1024 + 10)
    r = upload(b, other, "big.pdf", big)
    assert r.status_code == 413 and r.json()["error"] == "file_too_large"
    assert (
        conn.execute("SELECT count(*) AS n FROM attachments WHERE idea_uuid = %s", (other,)).fetchone()["n"]
        == 0
    )

    # Empty files and personal data in the file name are refused too.
    assert upload(b, other, "empty.pdf", b"").json()["error"] in ("file_empty", "file_required")
    rng = random.Random(61)
    named = upload(b, other, f"{g.pan(rng)}.pdf", files.pdf(["Synthetic"]))
    assert named.status_code == 422 and named.json()["error"] == "name_has_personal_data"

    # Someone else cannot attach to my draft (it looks missing).
    stranger = make().browser()
    assert upload(stranger, other, "x.pdf", files.pdf(["Synthetic"])).status_code == 404

    # Every file settles; then removing a file deletes it from the store and the list.
    for att in conn.execute("SELECT id FROM attachments WHERE idea_uuid = %s", (draft,)).fetchall():
        settle(b, att["id"])
    gone = b.request("DELETE", f"/api/submissions/{draft}/attachments/{body['id']}")
    assert gone.status_code == 204
    assert in_bucket(conn, body["id"]) == (False, False)
    assert conn.execute("SELECT 1 FROM attachments WHERE id = %s", (body["id"],)).fetchone() is None


def test_eicar_is_rejected_and_deleted(setup: Any) -> None:
    make, conn = setup
    b = make().browser()
    draft = new_draft(b)
    r = upload(b, draft, "harmless-test.docx", files.eicar_docx(), "docx")
    assert r.status_code == 201, r.text
    att = r.json()["id"]
    done = settle(b, att)
    assert done["state"] == "rejected"
    assert done["rejection"]["type"] == "virus"
    assert in_bucket(conn, att) == (False, False)  # deleted from quarantine, never reached clean
    assert b.get(f"/api/attachments/{att}").status_code == 403


@pytest.fixture
def deep_off(setup: Any) -> Iterator[Any]:
    """The day-one behaviour without the deep check: images and scanned pages wait for it (`awaiting_check`).
    The switch is on from launch (DEC-088), so this test turns it off and puts it back as it found it."""
    _, conn = setup
    before = conn.execute("SELECT state FROM kill_switches WHERE name = 'attachments.deep_check'").fetchone()
    killswitch.set_switch(conn, "attachments.deep_check", "off", reason="test: deep check off", actor="test")
    time.sleep(killswitch.CACHE_SECONDS + 1)  # the worker reads switches through a 10-second cache (BLD-006)
    try:
        yield setup
    finally:
        killswitch.set_switch(
            conn, "attachments.deep_check", before["state"], reason="test: put back", actor="test"
        )


def test_pdf_pan_rejected_with_page_and_clean_pdf_opens_for_reviewer(deep_off: Any) -> None:
    make, conn = deep_off
    owner = make()
    b = owner.browser()
    draft = new_draft(b)
    rng = random.Random(62)

    bad = upload(
        b, draft, "survey.pdf", files.pdf(["Survey of SIP form errors", f"Investor PAN {g.pan(rng)} noted"])
    )
    bad_done = settle(b, bad.json()["id"])
    assert bad_done["state"] == "rejected"
    assert bad_done["rejection"] == {"type": "PAN", "code": "pan", "location": "page 2"}
    assert in_bucket(conn, bad.json()["id"]) == (False, False)

    clean_bytes = files.pdf(["Synthetic time study: 14 minutes per SIP form", "Totals by week"])
    good = upload(b, draft, "time-study.pdf", clean_bytes)
    good_id = good.json()["id"]
    assert settle(b, good_id)["state"] == "clean"
    assert in_bucket(conn, good_id) == (False, True)

    png = upload(b, draft, "whiteboard.png", files.png(), "png")
    png_id = png.json()["id"]
    assert settle(b, png_id)["state"] == "awaiting_check"
    scanned = upload(b, draft, "scan.pdf", files.pdf(["", ""]))
    assert settle(b, scanned.json()["id"])["state"] == "awaiting_check"

    # The owner can open the clean file while drafting; a reviewer cannot see a draft's files.
    reviewer = make(roles=(("reviewer", None),)).browser()
    assert b.get(f"/api/attachments/{good_id}").status_code == 200
    assert reviewer.get(f"/api/attachments/{good_id}").status_code == 404

    sent = b.post(f"/api/submissions/{draft}/submit", json={"canvas": full_canvas()})
    assert sent.status_code == 202, sent.text

    # DEC-127 (3), BLD-C222: with the deep check off this file passed on the patterns alone (`checks.gatekeeper`
    # false), so after submit it still opens for no one but its owner: never on the pattern check alone.
    assert reviewer.get(f"/api/attachments/{good_id}").status_code == 404
    # Once the gatekeeper has checked it (`checks.gatekeeper` true, as the deep check records), the clean PDF opens
    # for a reviewer as a safe download, and the download is logged.
    conn.execute(
        "UPDATE attachments SET checks = checks || jsonb_build_object('gatekeeper', true) WHERE id = %s",
        (good_id,),
    )
    opened = reviewer.get(f"/api/attachments/{good_id}")
    assert opened.status_code == 200
    assert opened.content == clean_bytes
    assert opened.headers["content-type"] == "application/pdf"
    assert opened.headers["content-disposition"].startswith("attachment;")
    assert opened.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in opened.headers["content-security-policy"]
    logged = conn.execute(
        "SELECT count(*) AS n FROM audit_log WHERE action = 'attachment.download' AND entity = %s",
        (f"attachment:{good_id}",),
    ).fetchone()["n"]
    assert logged == 2  # owner once, reviewer once

    # The PNG (awaiting_check) and the rejected PDF answer 403 to everyone, owner and reviewer alike.
    for viewer in (b, reviewer):
        assert viewer.get(f"/api/attachments/{png_id}").status_code == 403
        assert viewer.get(f"/api/attachments/{bad.json()['id']}").status_code == 403

    # Another contributor never sees the file or its status.
    stranger = make().browser()
    assert stranger.get(f"/api/attachments/{good_id}").status_code == 404
    assert stranger.get(f"/api/attachments/{good_id}/status").status_code == 404
    # Files cannot change once the idea is submitted.
    assert upload(b, draft, "late.pdf", files.pdf(["Late"])).status_code == 409


def test_word_tables_and_spreadsheet_columns_are_checked(setup: Any) -> None:
    make, _conn = setup
    b = make().browser()
    draft = new_draft(b)
    rng = random.Random(63)

    doc = files.docx(["Synthetic process notes"], [["Step", "Example"], ["Verify", g.pan(rng)]])
    r = settle(b, upload(b, draft, "notes.docx", doc, "docx").json()["id"])
    assert r["state"] == "rejected" and r["rejection"]["location"] == "table 1, row 2, column 2"

    # Work emails alone only warn, but a column of them is a list of people: blocked by the column check.
    sheet = files.xlsx(
        [["Owner", "Forms"]] + [[g.kfin_email(rng, ["kfintech.com"]), str(i)] for i in range(10)]
    )
    r = settle(b, upload(b, draft, "owners.xlsx", sheet, "xlsx").json()["id"])
    assert r["state"] == "rejected"
    assert r["rejection"]["code"] == "column" and r["rejection"]["location"] == "sheet 1, column A"

    ok = files.xlsx(
        [["Week", "Forms", "Minutes"]] + [[f"W{i}", str(100 + i), str(14 * (100 + i))] for i in range(8)]
    )
    assert settle(b, upload(b, draft, "volumes.xlsx", ok, "xlsx").json()["id"])["state"] == "clean"
