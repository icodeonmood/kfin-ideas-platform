"""The server half of the conversation's "+" (DEC-124, walk item WF-01; lane C, BLD-C216), against a migrated test
database with the object store faked (no stack): `POST /files` with `for: "conversation"` beside `idea_id`, stored
as `attachments.purpose`; who may add one (`convo.access.reader`'s `may_attach`: the sharer, the review desk and the
Ones Committee); 422 for any other `for` or one without an idea; the migration's backfill; every reader of an idea's
own files leaving conversation files out; the sweep of unsent conversation files after a day; and DEC-107 for a
conversation file with a customer detail found (the sharer, the desk and the committee open it, never the crew).
Synthetic people, files and values only (non-negotiable 11)."""

from __future__ import annotations

import types
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from attachments import files as F
from attachments import store
from core.config import REPO_ROOT, get_settings
from core.db import Conn
from tests import desk_fixtures as f
from tests import files as make
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes the people and ideas)

assert REPO_ROOT is not None
MIGRATION = REPO_ROOT / "db" / "migrations" / "20261122301000_attachment_purpose.sql"
TOKEN = "lane-c-convo-files-test-token-0123456789ab"


# ---- pure rules ---------------------------------------------------------------------------------------------------


def test_A_API_files_for_conversation_needs_an_idea_and_nothing_else_is_taken() -> None:
    assert F.purpose_of(None, idea_id=None) == "idea"
    assert F.purpose_of(None, idea_id="IDEA-2026-001481") == "idea"
    assert F.purpose_of("conversation", idea_id="IDEA-2026-001481") == "conversation"
    for bad in ("idea", "Conversation", "convo", "", "message"):
        with pytest.raises(F.FileRefused) as e:
            F.purpose_of(bad, idea_id="IDEA-2026-001481")
        assert (e.value.status, e.value.code, e.value.extra) == (422, "for_invalid", {"field": "for"})
    with pytest.raises(F.FileRefused) as e:
        F.purpose_of("conversation", idea_id=None)
    assert (e.value.status, e.value.code) == (422, "target_required")


@pytest.mark.parametrize(
    ("state", "sees", "opens_for"),
    [
        ("personal_data_found", {"uploader", "lead", "desk"}, {"uploader", "lead", "desk"}),
        (
            "checked",
            {"uploader", "lead", "co_sharer", "crew", "desk"},
            {"uploader", "lead", "co_sharer", "crew", "desk"},
        ),
        ("checking", {"uploader"}, set()),
    ],
)
def test_DEC_107_a_conversation_file_with_a_detail_opens_for_the_sharer_desk_and_committee_only(
    state: str, sees: set[str], opens_for: set[str]
) -> None:
    viewers = {
        "uploader": F.Viewer(uploader=True),
        "lead": F.Viewer(sharer=True, crew=True, lead=True),  # the idea's own sharer (its crew lead)
        "co_sharer": F.Viewer(sharer=True),  # credited through a merge
        "crew": F.Viewer(crew=True),
        "desk": F.Viewer(desk=True),  # the review desk and the Ones Committee (READERS)
        "other": F.Viewer(),
    }
    for name, v in viewers.items():
        see, opens = F.rights(state, "file", draft=False, answer_unsent=False, viewer=v, conversation=True)
        assert see is (name in sees) and opens is (name in opens_for), (state, name)
    # The idea's own files keep their rule: a found file is never the sharer's unless they added it (DEC-107).
    lead = viewers["lead"]
    assert F.rights("personal_data_found", "file", draft=False, answer_unsent=False, viewer=lead) == (
        False,
        False,
    )


# ---- the database, with the object store faked -------------------------------------------------------------------


@pytest.fixture
def objects(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], bytes]:
    """The object store as a dict: nothing here needs MinIO (no stack tests locally)."""
    kept: dict[tuple[str, str], bytes] = {}
    monkeypatch.setattr(store, "put", lambda bucket, key, data: kept.__setitem__((bucket, key), data))
    monkeypatch.setattr(store, "delete", lambda bucket, key: kept.pop((bucket, key), None))
    monkeypatch.setattr(store, "exists", lambda bucket, key: (bucket, key) in kept)
    return kept


@pytest.fixture
def cast(db: Conn, company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Kavya shares an idea (and has a draft); Arjun is on its crew; Meera is the review desk; Rohan sits on the
    Ones Committee and Dev on it under the old role; Sam has nothing to do with it."""
    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    kavya, arjun = f.person(db, "Kavya Menon"), f.person(db, "Arjun Nair")
    out = {
        "kavya": kavya, "arjun": arjun, "sam": f.person(db, "Sam Thomas"),
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "dev": f.person(db, "Dev Rao", roles=("core_committee",)),
        "idea": f.idea(db, kavya), "draft": f.idea(db, kavya, status="draft"),
    }  # fmt: skip
    f.crew(db, out["idea"], arjun)
    yield out
    db.execute(
        "DELETE FROM jobs WHERE type = %s AND payload->>'attachment_id' IN (SELECT id FROM attachments "
        "WHERE idea_uuid = ANY(%s::uuid[]))",
        (F.JOB, [str(out["idea"]["id"]), str(out["draft"]["id"])]),
    )
    get_settings.cache_clear()


def _upload(
    db: Conn, who: dict[str, str], idea: dict[str, Any], *, purpose: str = "conversation"
) -> dict[str, Any]:
    return F.accept(
        db, user_id=who["id"], name="branch-notes.pdf", data=make.pdf(["Calls double on Mondays."]),
        idea_id=idea["idea_id"], purpose=purpose,
    )  # fmt: skip


def cast_owner(who: dict[str, str]) -> Any:
    """The draft store's owner, as `draft.store._files` reads it (only the user id)."""
    return types.SimpleNamespace(user_id=who["id"])


def _one(db: Conn, sql: str, *args: Any) -> dict[str, Any]:
    row = db.execute(sql, args).fetchone()
    assert row is not None
    return dict(row)


def _refused(fn: Any, *args: Any, **kwargs: Any) -> F.FileRefused:
    with pytest.raises(F.FileRefused) as e:
        fn(*args, **kwargs)
    return e.value


def _entry(db: Conn, idea: dict[str, Any], by: dict[str, str]) -> str:
    row = db.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, author_code) VALUES (%s, 'message', %s) RETURNING id",
        (idea["id"], by["code"]),
    ).fetchone()
    assert row is not None
    return str(row["id"])


def _row(
    db: Conn, idea: dict[str, Any], by: dict[str, str], *, purpose: str = "idea", entry: str | None = None,
    state: str = "checked", kind: str = "file", hours_ago: float = 0,
) -> str:  # fmt: skip
    """An attachments row as the routes leave it, written directly (its copy is a key in the faked store)."""
    att = F._next_id(db)
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, uploaded_by_user, name, mime, bytes, store_key, "
        "state, kind, file_state, checks, purpose, conversation_entry_id, created_at) "
        "VALUES (%s, %s, %s, %s, 'notes.pdf', 'application/pdf', 1200, %s, %s, %s, %s, %s, %s, %s, "
        "now() - make_interval(secs => %s))",
        (att, idea["id"], by["code"], by["id"], f"files/{att}-{uuid.uuid4().hex}",
         "clean" if state == "checked" else "quarantine", kind, state, Jsonb({"type": "pdf"}), purpose, entry,
         hours_ago * 3600),
    )  # fmt: skip
    return att


def test_A_API_files_the_desk_and_the_committee_add_files_for_the_conversation_and_404_without_for(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    idea = cast["idea"]
    for who in ("meera", "rohan", "dev", "kavya"):
        item = _upload(db, cast[who], idea)
        assert item["state"] == "checking" and item["id"].startswith("ATT-")
        row = db.execute(
            "SELECT purpose, conversation_entry_id FROM attachments WHERE id = %s", (item["id"],)
        )
        assert row.fetchone() == {"purpose": "conversation", "conversation_entry_id": None}, who
    # Without `for` the file is the idea's own, and only its sharer adds those, as before.
    for who in ("meera", "rohan", "dev"):
        assert _refused(_upload, db, cast[who], idea, purpose="idea").status == 404, who
    assert db.execute("SELECT purpose FROM attachments WHERE id = %s", (_upload(db, cast["kavya"], idea,
               purpose="idea")["id"],)).fetchone() == {"purpose": "idea"}  # fmt: skip
    added = db.execute(
        "SELECT after FROM audit_log WHERE entity = %s AND action = 'file.added' ORDER BY id",
        (f"idea:{idea['id']}",),
    ).fetchall()
    assert [a["after"]["purpose"] for a in added] == ["conversation"] * 4 + ["idea"]


def test_A_API_files_the_crew_and_anyone_else_get_404_for_the_conversation_and_a_closed_idea_409(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    idea = cast["idea"]
    for who in ("arjun", "sam"):  # the crew writes without files (BLD-F063); Sam cannot read it at all
        e = _refused(_upload, db, cast[who], idea)
        assert (e.status, e.code) == (404, "not_found"), who
    # A draft has no conversation; an unknown idea is not found either.
    assert _refused(_upload, db, cast["kavya"], cast["draft"]).status == 404
    assert _refused(_upload, db, cast["meera"], {"idea_id": "IDEA-2026-999999"}).status == 404
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (idea["id"],))
    e = _refused(_upload, db, cast["meera"], idea)
    assert (e.status, e.code) == (409, "idea_closed")
    assert _refused(_upload, db, cast["sam"], idea).status == 404  # never says that the idea exists
    assert objects == {}  # nothing refused left a copy behind


def test_A_API_files_for_on_the_worker_route_unknown_or_without_an_idea_is_422(
    cast: dict[str, Any], test_database: str, monkeypatch: pytest.MonkeyPatch, objects: dict[Any, bytes]
) -> None:
    from fastapi.testclient import TestClient

    from tests import helpers

    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    from api.app import app

    client = TestClient(app, headers={"X-Internal-Token": TOKEN})
    pdf = ("notes.pdf", make.pdf(["Calls double on Mondays."]), "application/pdf")
    meera, idea = cast["meera"], cast["idea"]
    cases = [
        ({"idea_id": idea["idea_id"], "for": "idea"}, "for_invalid"),
        ({"idea_id": idea["idea_id"], "for": "chat"}, "for_invalid"),
        ({"draft_id": str(cast["draft"]["id"]), "for": "conversation"}, "target_required"),
        ({"for": "conversation"}, "target_required"),
    ]
    for target, code in cases:
        r = client.post("/internal/files", data={"user_id": meera["id"], **target}, files={"file": pdf})
        assert r.status_code == 422 and r.json()["error"]["code"] == code, (target, r.text)
    ok = client.post(
        "/internal/files", data={"user_id": meera["id"], "idea_id": idea["idea_id"], "for": "conversation"},
        files={"file": pdf},
    )  # fmt: skip
    assert ok.status_code == 201, ok.text
    assert client.post(
        "/internal/files", data={"user_id": cast["arjun"]["id"], "idea_id": idea["idea_id"], "for": "conversation"},
        files={"file": pdf},
    ).status_code == 404  # fmt: skip
    get_settings.cache_clear()


def test_attachment_purpose_migration_backfills_conversation_for_files_already_on_an_entry(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The migration's own text, run inside a transaction that is rolled back: the column gone, rows as they were
    before it, then its `migrate:up` (DDL is transactional in Postgres)."""
    up = MIGRATION.read_text().split("-- migrate:up", 1)[1].split("-- migrate:down", 1)[0]
    down = MIGRATION.read_text().split("-- migrate:down", 1)[1]
    idea, kavya = cast["idea"], cast["kavya"]
    with db.transaction(force_rollback=True):
        on_entry = _row(db, idea, kavya, purpose="conversation", entry=_entry(db, idea, kavya))
        own = _row(db, idea, kavya)
        db.execute(down)
        assert (
            db.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = 'attachments' AND column_name = 'purpose'"
            ).fetchone()
            is None
        )
        db.execute(up)
        got = {r["id"]: r["purpose"] for r in db.execute(
            "SELECT id, purpose FROM attachments WHERE id = ANY(%s)", ([on_entry, own],)).fetchall()}  # fmt: skip
        assert got == {on_entry: "conversation", own: "idea"}
        with pytest.raises(Exception, match="check"), db.transaction():
            db.execute("UPDATE attachments SET purpose = 'chat' WHERE id = %s", (own,))


def test_every_reader_of_an_ideas_own_files_leaves_conversation_files_out(
    db: Conn, cast: dict[str, Any]
) -> None:
    from draft import store as draft_store
    from ideapage import read as ideapage
    from submit import edit, ready

    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    entry = _entry(db, idea, meera)
    own = _row(db, idea, kavya)
    waiting = _row(db, idea, kavya, state="checking")
    for state in ("checked", "checking"):
        _row(db, idea, meera, purpose="conversation", state=state)  # unsent
        _row(db, idea, meera, purpose="conversation", entry=entry, state=state)  # on an entry
        _row(db, idea, kavya, purpose="idea", entry=entry, state=state)  # half one, half the other
    uid = str(idea["id"])
    assert [r["id"] for r in ideapage.files(db, uid)] == [own, waiting]
    assert [r["id"] for r in edit._files(db, uid)] == [own, waiting]
    assert ready.waiting_files(db, uid) == [waiting]
    assert ready._proof(db, uid) == (2, 0)
    assert [i["id"] for i in F.items_for(db, uid, kavya["id"])] == [own, waiting]
    owner = cast_owner(kavya)
    assert [i["id"] for i in draft_store._files(db, uid, owner)] == [own, waiting]


def test_the_sweep_removes_only_unsent_conversation_files_older_than_a_day(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    s = get_settings()
    entry = _entry(db, idea, meera)
    old = _row(db, idea, meera, purpose="conversation", hours_ago=25)
    new = _row(db, idea, meera, purpose="conversation", hours_ago=23)
    sent = _row(db, idea, meera, purpose="conversation", entry=entry, hours_ago=48)
    mine = _row(db, idea, kavya, hours_ago=72)
    key = str(_one(db, "SELECT store_key FROM attachments WHERE id = %s", old)["store_key"])
    objects[(s.s3_bucket_clean, key)] = b"%PDF-1.4"
    assert F.sweep_failed_copies(db) == 1  # the one sweep, run with the draft purge
    left = {r["id"] for r in db.execute("SELECT id FROM attachments WHERE idea_uuid = %s", (idea["id"],))}
    assert left == {new, sent, mine}
    assert (s.s3_bucket_clean, key) not in objects
    swept = db.execute(
        "SELECT actor, after FROM audit_log WHERE entity = %s AND action = 'file.swept'",
        (f"idea:{idea['id']}",),
    ).fetchall()
    assert [(a["actor"], a["after"]) for a in swept] == [
        ("system:files", {"file_id": old, "purpose": "conversation"})
    ]
    assert F.sweep_unsent_conversation(db) == 0


def test_DEC_107_a_detail_found_conversation_file_opens_for_the_sharer_desk_and_committee_never_the_crew(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea = cast["idea"]
    att = _row(db, idea, cast["meera"], purpose="conversation", state="personal_data_found")
    for who in ("meera", "kavya", "rohan", "dev"):
        item = F.get_item(db, att, cast[who]["id"])
        assert item["customer_detail"] is True and item["view_url"] == f"/api/files/{att}/view", who
    for who in ("arjun", "sam"):
        assert _refused(F.get_item, db, att, cast[who]["id"]).status == 404, who
    # A checked conversation file is the crew's to open, as checked files are (P-PRODUCT.privacy).
    checked = _row(db, idea, cast["meera"], purpose="conversation")
    assert F.get_item(db, checked, cast["arjun"]["id"])["view_url"] == f"/api/files/{checked}/view"
    assert _refused(F.get_item, db, checked, cast["sam"]["id"]).status == 404


def test_attachment_purpose_the_new_column_defaults_to_idea_for_every_existing_writer(
    db: Conn, cast: dict[str, Any]
) -> None:
    att = F._next_id(db)
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, bytes, store_key) "
        "VALUES (%s, %s, %s, 'notes.pdf', 10, 'files/x')",
        (att, cast["idea"]["id"], cast["kavya"]["code"]),
    )
    assert db.execute("SELECT purpose FROM attachments WHERE id = %s", (att,)).fetchone() == {
        "purpose": "idea"
    }
