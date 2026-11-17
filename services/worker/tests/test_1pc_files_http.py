"""A-API.files over HTTP against the running stack (lane C, BLD-C105 to BLD-C109): the web's routes pass the signed-in
person to the worker, a file goes from `checking` to `checked` through the stack's own job runner, the scanner and
hide, and `GET /api/files/:id/view` serves the checked copy only to the people DEC-107 allows. Synthetic people and
files; everything made is removed afterwards except `audit_log`."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest

from attachments import store
from core.config import get_settings
from core.db import connect
from hide.core import scope_for
from pii import vault
from tests import files as make
from tests.web import Browser, people

pytestmark = pytest.mark.stack


@pytest.fixture
def world() -> Iterator[dict[str, Any]]:
    with connect(autocommit=True) as conn, people(conn) as person:
        sharer, crew, other = person(), person(), person()
        reviewer = person((("reviewer", None),))
        row = conn.execute(
            "INSERT INTO ideas (contributor_code, status, kind, title, summary, idea_id) "
            "VALUES (%s, 'with_review_desk', 'problem', 'SMS gives a code, not a reason', 'Investors call', "
            "next_idea_ref()) RETURNING id, idea_id",
            (sharer.contributor_code,),
        ).fetchone()
        assert row is not None
        iid = str(row["id"])
        conn.execute(
            "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'crew', 'teamup')",
            (iid, crew.contributor_code),
        )
        try:
            yield {
                "conn": conn, "iid": iid, "ref": str(row["idea_id"]),
                "sharer": sharer.browser(), "crew": crew.browser(), "other": other.browser(),
                "reviewer": reviewer.browser(),
            }  # fmt: skip
        finally:  # the stored copies, the job rows and the vault scope; `people` removes the people and the idea
            s = get_settings()
            made = conn.execute(
                "SELECT id, store_key FROM attachments WHERE idea_uuid = %s", (iid,)
            ).fetchall()
            for r in made:
                if r["store_key"]:
                    store.delete(s.s3_bucket_quarantine, r["store_key"])
                    store.delete(s.s3_bucket_clean, r["store_key"])
            conn.execute(
                "DELETE FROM jobs WHERE type = 'file.check' AND payload->>'attachment_id' = ANY(%s)",
                ([str(r["id"]) for r in made],),
            )
            vault.purge_scope(conn, scope_for(iid))
            conn.execute("DELETE FROM vault_counters WHERE scope_id = %s", (scope_for(iid),))


def _settled(b: Browser, att_id: str, timeout: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        r = b.get(f"/api/files/{att_id}")
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        if body["state"] not in ("uploading", "checking"):
            return body
        if time.monotonic() > deadline:
            raise AssertionError(f"{att_id} still {body['state']} after {timeout}s")
        time.sleep(0.5)


def test_A_API_files_http_upload_check_and_view_through_the_web(world: dict[str, Any]) -> None:
    sharer, crew, other, reviewer = world["sharer"], world["crew"], world["other"], world["reviewer"]
    config = sharer.get("/api/config/uploads")
    assert config.status_code == 200 and config.json()["limit_mb"] == 25

    data = make.pdf(["Calls double on Mondays at the branch.", "The SMS gives a code, not a reason."])
    up = sharer.post(
        "/api/files",
        data={"idea_id": world["ref"]},
        files={"file": ("branch-notes.pdf", data, "application/pdf")},
    )
    assert up.status_code == 201, up.text
    item = up.json()
    assert item["state"] == "checking" and item["kind"] == "file" and item["name"] == "branch-notes.pdf"
    att = item["id"]
    # Until the checks finish, nobody but the sharer sees it, and nobody opens it (non-negotiable 8).
    assert crew.get(f"/api/files/{att}").status_code == 404
    early = sharer.get(f"/api/files/{att}/view")
    assert early.status_code in (403, 200)  # 200 only if the stack's runner has already checked it

    done = _settled(sharer, att)
    assert done["state"] == "checked" and done["view_url"] == f"/api/files/{att}/view" and done["pages"] == 2
    for b in (sharer, crew, reviewer):
        seen = b.get(f"/api/files/{att}/view")
        assert seen.status_code == 200 and seen.content == data
        assert seen.headers["content-type"] == "application/pdf"
        assert seen.headers["x-content-type-options"] == "nosniff"
        assert seen.headers["content-disposition"].startswith("inline;")
    assert other.get(f"/api/files/{att}").status_code == 404
    assert other.get(f"/api/files/{att}/view").status_code == 404
    opened = (
        world["conn"]
        .execute(
            "SELECT count(*) AS n FROM audit_log WHERE entity = %s AND action = 'file.opened'",
            (f"idea:{world['iid']}",),
        )
        .fetchone()
    )
    assert opened is not None and opened["n"] >= 3  # one more if the early view came after the check

    # `too_big` is refused from the Content-Length (web unit test) and by the worker (test_1pc_files_db), without
    # sending 25 MB through the stack here.
    wrong = sharer.post(
        "/api/files", data={"idea_id": world["ref"]}, files={"file": ("x.exe", b"MZ" + b"\0" * 64)}
    )
    assert wrong.status_code == 415 and wrong.json()["error"]["code"] == "type_not_allowed"
    assert (
        crew.post("/api/files", data={"idea_id": world["ref"]}, files={"file": ("a.pdf", data)}).status_code
        == 404
    )

    link = sharer.post(
        "/api/links", json={"url": "kfintech.sharepoint.com/sites/ops/x", "idea_id": world["ref"]}
    )
    assert (
        link.status_code == 201 and link.json()["link_scope"] == "internal" and link.json()["state"] == "ok"
    )
    bad = sharer.post("/api/links", json={"url": "not a link", "idea_id": world["ref"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "not_a_link"

    hide = sharer.post(f"/api/files/{att}/hide")
    assert hide.status_code == 503 and hide.json()["error"]["code"] == "not_available"
    assert reviewer.request("DELETE", f"/api/files/{att}").status_code == 403
    assert sharer.request("DELETE", f"/api/files/{att}").status_code == 204
    assert sharer.get(f"/api/files/{att}").status_code == 404
