"""The server half of the conversation's "+" (DEC-124, walk item WF-01; lane C, BLD-C216), against a migrated test
database with the object store faked (no stack): `POST /files` with `for: "conversation"` beside `idea_id`, stored
as `attachments.purpose`; who may add one (`convo.access.reader`'s `may_attach`: the sharer, the review desk and the
Ones Committee); 422 for any other `for` or one without an idea; the migration's backfill; every reader of an idea's
own files leaving conversation files out; the sweep of unsent conversation files after a day; an unsent
conversation file is its uploader's alone (BLD-C222); and DEC-127 for a conversation file with a customer detail
found (its uploader, the desk and the committee open it; never the idea's lead or sharer who did not upload it, nor
the crew), and for a file still checking (nobody but its uploader sees it, and nobody opens it).
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


# The viewer rows of DEC-127 and BLD-C222. `desk` stands for the review desk and the Ones Committee alike: both are
# `desk.store.READERS`, which the database tests below take one by one.
VIEWERS = {
    "uploader": F.Viewer(uploader=True),
    "lead_uploader": F.Viewer(uploader=True, sharer=True, crew=True, lead=True),  # the idea's sharer added it
    "lead": F.Viewer(
        sharer=True, crew=True, lead=True
    ),  # the idea's own sharer (its crew lead), did not add it
    "co_sharer": F.Viewer(sharer=True),  # credited through a merge
    "crew": F.Viewer(crew=True),
    "desk": F.Viewer(desk=True),
    "other": F.Viewer(),
}
UPLOADERS = {"uploader", "lead_uploader"}
CHECKED_READERS = {*UPLOADERS, "lead", "co_sharer", "crew", "desk"}  # P-PRODUCT.privacy, unchanged (BLD-F062)


@pytest.mark.parametrize(
    ("state", "sees", "opens_for"),
    [
        # DEC-127: a found conversation file opens for its uploader, the desk and the committee only.
        ("personal_data_found", {*UPLOADERS, "desk"}, {*UPLOADERS, "desk"}),
        # Checked conversation files on a sent entry: exactly as on main (lane F's question (a) stays open).
        ("checked", CHECKED_READERS, CHECKED_READERS),
        ("hidden_checked", CHECKED_READERS, CHECKED_READERS),
        ("checking", UPLOADERS, set()),
        ("upload_failed", UPLOADERS, set()),
        ("infected", UPLOADERS, set()),
    ],
)
def test_DEC_127_BLD_C222_every_viewer_row_on_a_sent_conversation_file(
    state: str, sees: set[str], opens_for: set[str]
) -> None:
    for name, v in VIEWERS.items():
        see, opens = F.rights(
            state, "file", draft=False, answer_unsent=False, viewer=v, conversation=True, unsent=False
        )
        assert see is (name in sees) and opens is (name in opens_for), (state, name)
    # The idea's own files keep their rule: a found file is never the sharer's unless they added it (DEC-107).
    assert F.rights(
        "personal_data_found", "file", draft=False, answer_unsent=False, viewer=VIEWERS["lead"]
    ) == (
        False,
        False,
    )


@pytest.mark.parametrize(
    "state", ["checked", "hidden_checked", "personal_data_found", "checking", "upload_failed", "too_big"]
)
def test_BLD_C222_an_unsent_conversation_file_is_its_uploaders_alone_in_every_state(state: str) -> None:
    """A conversation file on no entry yet is seen and opened by its uploader only, like a draft's file: not the
    idea's lead or a co-sharer, not the crew, not the desk or the committee (DEC-127's last line, BLD-C222)."""
    for name, v in VIEWERS.items():
        see, opens = F.rights(
            state, "file", draft=False, answer_unsent=False, viewer=v, conversation=True, unsent=True
        )
        assert see is (name in UPLOADERS), (state, name)
        assert opens is (name in UPLOADERS and state in F.VIEWABLE), (state, name)


def test_DEC_127_who_opens_a_found_conversation_file_is_one_rule_that_rights_follows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule lives in `opens_found_conversation_file` only: its uploader, the review desk and the Ones Committee.
    Changing that one function changes `rights` (and so every route), and nothing else needs an edit."""
    for name, v in VIEWERS.items():
        assert F.opens_found_conversation_file(v) is (name in {*UPLOADERS, "desk"}), name
    found = {"draft": False, "answer_unsent": False, "conversation": True, "unsent": False}
    assert F.rights("personal_data_found", "file", viewer=VIEWERS["lead"], **found) == (False, False)
    monkeypatch.setattr(F, "opens_found_conversation_file", lambda v: v.uploader or v.desk or v.lead)
    assert F.rights("personal_data_found", "file", viewer=VIEWERS["lead"], **found) == (True, True)
    assert F.rights("personal_data_found", "file", viewer=VIEWERS["crew"], **found) == (False, False)


@pytest.mark.parametrize("state", ["checking", "uploading"])
def test_DEC_127_no_one_but_the_uploader_opens_a_file_before_both_checks_are_done(state: str) -> None:
    """DEC-127: a file opens for anyone but its uploader only once its checks are complete, the virus scan and the
    gatekeeper; never on the pattern check alone. Until then it is `checking` (BLD-C107), and the desk, the
    committee, the idea's lead or sharer and the crew neither see nor open it, an idea's own file or a conversation
    file, sent or not. The uploader sees the row and opens nothing, as before."""
    shapes = [
        {"conversation": False, "unsent": False},  # the idea's own file
        {"conversation": True, "unsent": False},  # a conversation file on an entry
        {"conversation": True, "unsent": True},  # a conversation file not yet sent
    ]
    for shape in shapes:
        for name, v in VIEWERS.items():
            got = F.rights(state, "file", draft=False, answer_unsent=False, viewer=v, **shape)
            assert got == ((name in UPLOADERS), False), (state, shape, name)


def test_DEC_127_BLD_C222_a_file_the_gatekeeper_never_read_is_its_uploaders_alone() -> None:
    """An old-pipeline row marked clean on the pattern check alone (`gatekeeper_ran` false): only its uploader sees
    and opens it; nobody else, an idea's own file or not. With the gatekeeper run, the rule is as before."""
    for name, v in VIEWERS.items():
        for conversation in (False, True):
            got = F.rights(
                "checked", "file", draft=False, answer_unsent=False, viewer=v, conversation=conversation,
                gatekeeper_ran=False,
            )  # fmt: skip
            assert got == ((name in UPLOADERS), (name in UPLOADERS)), (name, conversation)
    assert F.gatekeeper_ran({"file_state": "checked", "checks": {"type": "pdf"}}) is True  # the 1% Club's own
    assert F.gatekeeper_ran({"file_state": None, "state": "clean", "checks": {"gatekeeper": True}}) is True
    for checks in ({"patterns": True, "gatekeeper": False}, {"gatekeeper_skipped": True}, {}, None):
        assert F.gatekeeper_ran({"file_state": None, "state": "clean", "checks": checks}) is False, checks


# ---- the database, with the object store faked -------------------------------------------------------------------


@pytest.fixture
def objects(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], bytes]:
    """The object store as a dict: nothing here needs MinIO (no stack tests locally)."""
    kept: dict[tuple[str, str], bytes] = {}
    monkeypatch.setattr(store, "put", lambda bucket, key, data: kept.__setitem__((bucket, key), data))
    monkeypatch.setattr(store, "delete", lambda bucket, key: kept.pop((bucket, key), None))
    monkeypatch.setattr(store, "exists", lambda bucket, key: (bucket, key) in kept)
    monkeypatch.setattr(store, "get", lambda bucket, key: kept[(bucket, key)])
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
        unsent = _row(db, idea, cast["meera"], purpose="conversation", state="checking")
        for source_id in (unsent, f"{unsent}:name", own):
            _detail(db, idea, source_id, "Folio ••••41")
        db.execute(
            "INSERT INTO jobs (type, payload) VALUES (%s, %s)", (F.JOB, Jsonb({"attachment_id": unsent}))
        )
        db.execute(down)
        # BLD-C223: a down never turns an unsent conversation file into one of the idea's own files.
        assert db.execute("SELECT 1 FROM attachments WHERE id = %s", (unsent,)).fetchone() is None
        assert [r["source_id"] for r in db.execute(
            "SELECT source_id FROM hidden_details WHERE idea_uuid = %s AND source = 'file'", (idea["id"],))] == [own]  # fmt: skip
        assert (
            db.execute(
                "SELECT 1 FROM jobs WHERE type = %s AND payload->>'attachment_id' = %s", (F.JOB, unsent)
            ).fetchone()
            is None
        )
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
    from scan import pipeline
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
    # BLD-C223: canvas assist's research files (`scan.pipeline._attachments`) are the idea's own files only.
    assert [r["id"] for r in pipeline._attachments(db, uid)] == [own, waiting]


def _detail(db: Conn, idea: dict[str, Any], source_id: str, masked: str, *, shown: bool = False) -> None:
    """A file's hidden detail as hide leaves it (`source` "file", the file's id or `<id>:name`), hidden or shown."""
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked, state, reason, shown_at) "
        "VALUES (%s, 'file', %s, 'folio', %s, %s, %s, CASE WHEN %s THEN now() END)",
        (idea["id"], source_id, masked, "shown" if shown else "hidden", "internal_reference" if shown else None,
         shown),
    )  # fmt: skip


def test_BLD_C223_the_idea_page_lists_no_hidden_detail_of_a_conversation_file(
    db: Conn, cast: dict[str, Any]
) -> None:
    """`ideapage.read.hidden`: the details of the idea's own files, and none of a file added for the conversation,
    sent or not, nor of its name (`<id>:name`); the other sources are as before (lane F's `teamup` stays out)."""
    from ideapage import read as ideapage

    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    entry = _entry(db, idea, meera)
    own = _row(db, idea, kavya)
    unsent = _row(db, idea, meera, purpose="conversation")
    sent = _row(db, idea, kavya, purpose="conversation", entry=entry)
    half = _row(db, idea, kavya, purpose="idea", entry=entry)  # half one, half the other: not the idea's
    shown = {"Folio ••••11", "Folio ••••12", "Folio ••••13"}
    _detail(db, idea, own, "Folio ••••11")
    _detail(db, idea, f"{own}:name", "Folio ••••12")
    _detail(db, idea, own, "Folio ••••13", shown=True)
    for n, att in enumerate((unsent, sent, half)):
        _detail(db, idea, att, f"Folio ••••2{n}")
        _detail(db, idea, f"{att}:name", f"Folio ••••3{n}")
        _detail(db, idea, att, f"Folio ••••4{n}", shown=True)
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) "
        "VALUES (%s, 'message', 'MSG-1', 'pan', 'PAN ••••4F'), (%s, 'teamup', 'REQ-1', 'phone', 'Phone ••••10')",
        (idea["id"], idea["id"]),
    )
    got = ideapage.hidden(db, str(idea["id"]))
    assert {r["masked"] for r in got} == {*shown, "PAN ••••4F"}
    assert {r["file_name"] for r in got if r["source"] == "file" and r["masked"] != "Folio ••••12"} == {
        "notes.pdf"
    }


def test_BLD_C223_the_idea_page_lists_no_hidden_detail_of_a_file_on_an_answer_to_the_desk(
    db: Conn, cast: dict[str, Any]
) -> None:
    """`ideapage.read.hidden`: a file on an answer to the review desk is not one of the idea's own files (`files`
    leaves it out too), so neither its details nor its name's are listed, as lane F's `checked()` (BLD-F103)."""
    from ideapage import read as ideapage

    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    s = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at) "
        "VALUES (%s, %s, 'sent', '3d', now(), now() + interval '3 days') RETURNING id",
        (idea["id"], meera["id"]),
    ).fetchone()
    assert s is not None
    q = db.execute(
        "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, 1, 'evidence', %s) RETURNING id",
        (s["id"], b"synthetic"),
    ).fetchone()
    assert q is not None
    a = db.execute(
        "INSERT INTO answers (question_id, by_code) VALUES (%s, %s) RETURNING id", (q["id"], kavya["code"])
    ).fetchone()
    assert a is not None
    own, on_answer = _row(db, idea, kavya), _row(db, idea, kavya)
    db.execute("UPDATE attachments SET answer_id = %s WHERE id = %s", (a["id"], on_answer))
    _detail(db, idea, own, "Folio ••••51")
    _detail(db, idea, on_answer, "Folio ••••52")
    _detail(db, idea, f"{on_answer}:name", "Folio ••••53")
    assert {r["masked"] for r in ideapage.hidden(db, str(idea["id"]))} == {"Folio ••••51"}
    assert [r["id"] for r in ideapage.files(db, str(idea["id"]))] == [own]  # the same line `files` draws


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
    db.execute(  # a worker start sweep that finished: the attachments sweep waits for one (BLD-C242)
        "INSERT INTO audit_log (actor, action, entity, after) VALUES "
        "('system:files', 'file.start_sweep', 'files:start_sweep', '{\"count\": 0, \"complete\": true}'::jsonb)"
    )
    assert F.sweep_failed_copies(db) == 1  # the one sweep, run every hour by files.sweep
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


def test_BLD_C223_the_sweep_goes_on_when_the_store_fails_for_one_file(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The object store failing for one unsent conversation file rolls back that file only: its row stays for the
    next sweep, the sweep removes the others, and the draft purge that runs it does not fail (BLD-C223)."""
    idea, meera = cast["idea"], cast["meera"]
    s = get_settings()
    stuck = _row(db, idea, meera, purpose="conversation", hours_ago=30)
    gone = _row(db, idea, meera, purpose="conversation", hours_ago=26)
    stuck_key = str(_one(db, "SELECT store_key FROM attachments WHERE id = %s", stuck)["store_key"])
    for att in (stuck, gone):
        _copy(db, objects, att)

    def delete(bucket: str, key: str) -> None:
        if key == stuck_key:
            raise OSError("the store is not answering")
        objects.pop((bucket, key), None)

    monkeypatch.setattr(store, "delete", delete)
    assert F.sweep_unsent_conversation(db) == 1
    left = {r["id"] for r in db.execute("SELECT id FROM attachments WHERE idea_uuid = %s", (idea["id"],))}
    assert stuck in left and gone not in left
    assert (s.s3_bucket_clean, stuck_key) in objects
    monkeypatch.setattr(store, "delete", lambda bucket, key: objects.pop((bucket, key), None))
    assert F.sweep_unsent_conversation(db) == 1  # the next sweep takes it
    assert db.execute("SELECT 1 FROM attachments WHERE id = %s", (stuck,)).fetchone() is None


def _co_sharer(db: Conn, idea: dict[str, Any]) -> dict[str, str]:
    """Nisha, credited on the idea through a merge (`own_codes`): a sharer of it, not its lead, not on its crew."""
    nisha = f.person(db, "Nisha Rao")
    joined = f.idea(db, nisha, status="merged", title="The R07 SMS gives a code, not a reason")
    db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_code) VALUES (%s, %s, 'lead_accepted', %s)",
        (idea["id"], joined["id"], idea["contributor_code"]),
    )
    return nisha


def _copy(db: Conn, objects: dict[Any, bytes], att: str) -> None:
    """The file's copy in the faked clean bucket, so that whoever may open it gets bytes back."""
    key = str(_one(db, "SELECT store_key FROM attachments WHERE id = %s", att)["store_key"])
    objects[(get_settings().s3_bucket_clean, key)] = b"%PDF-1.4 synthetic"


def _not_found_anywhere(db: Conn, att: str, who: dict[str, str]) -> None:
    """The row and the copy (`GET /files/:id`, `GET /files/:id/view`) are both not found, in the very words an id
    that does not exist gets, so nothing says that the file is there."""
    missing = _refused(F.get_item, db, "ATT-2099-999999", who["id"]).body()
    for fn in (F.get_item, F.content):
        e = _refused(fn, db, att, who["id"])
        assert (e.status, e.body()) == (404, missing), (fn.__name__, who["name"])


def test_BLD_C222_DEC_127_an_unsent_conversation_file_is_404_for_everyone_but_its_uploader(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """Item 1 of the walk's privacy fixes: Meera at the review desk adds a file in the conversation's box and has
    not sent it. Whoever asks for the ids after their own gets nothing: the idea's lead, a co-sharer, the crew,
    the Ones Committee, anyone else. Meera alone sees the row and opens the copy, checked or found."""
    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    nisha = _co_sharer(db, idea)
    mine = _upload(db, kavya, idea)["id"]  # Kavya knows her own file's id
    theirs = _upload(db, meera, idea)["id"]
    guesses = [f"{mine[:-6]}{int(mine[-6:]) + n:06d}" for n in (1, 2, 3)]
    assert theirs in guesses  # ids are sequential: the next one is Meera's
    for state in ("checking", "checked", "personal_data_found"):
        db.execute(
            "UPDATE attachments SET file_state = %s, state = %s WHERE id = %s",
            (state, "clean" if state == "checked" else "quarantine", theirs),
        )
        _copy(db, objects, theirs)
        for who in ("kavya", "arjun", "sam", "rohan", "dev"):
            for guess in guesses:
                _not_found_anywhere(db, guess, cast[who])
        _not_found_anywhere(db, theirs, nisha)
        item = F.get_item(db, theirs, meera["id"])
        assert item["state"] == state, state
        if state == "checking":
            assert "view_url" not in item
            assert _refused(F.content, db, theirs, meera["id"]).status == 403  # as before: not yet checked
        else:
            assert item["view_url"] == f"/api/files/{theirs}/view"
            assert F.content(db, theirs, meera["id"])[0] == b"%PDF-1.4 synthetic"
    # Sent on an entry, a checked conversation file is read as on main: the crew and the sharers open it.
    db.execute(
        "UPDATE attachments SET file_state = 'checked', state = 'clean', conversation_entry_id = %s WHERE id = %s",
        (_entry(db, idea, meera), theirs),
    )
    for reader in (kavya, cast["arjun"], nisha, cast["rohan"]):
        assert F.get_item(db, theirs, reader["id"])["view_url"] == f"/api/files/{theirs}/view", reader["name"]
    _not_found_anywhere(db, theirs, cast["sam"])


def test_BLD_C222_the_worker_routes_answer_an_unsent_conversation_file_as_an_id_that_does_not_exist(
    db: Conn,
    cast: dict[str, Any],
    test_database: str,
    monkeypatch: pytest.MonkeyPatch,
    objects: dict[Any, bytes],
) -> None:
    """The same, through the routes behind `GET /api/files/:id` and `GET /api/files/:id/view`: the status, the
    body and the content type are those of an id that does not exist."""
    from fastapi.testclient import TestClient

    from tests import helpers

    att = _upload(db, cast["meera"], cast["idea"])["id"]
    db.execute("UPDATE attachments SET file_state = 'checked', state = 'clean' WHERE id = %s", (att,))
    _copy(db, objects, att)
    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    from api.app import app

    client = TestClient(app, headers={"X-Internal-Token": TOKEN})
    for who in ("kavya", "arjun", "rohan", "sam"):
        uid = cast[who]["id"]
        for path in ("/internal/files/{}", "/internal/files/{}/content"):
            got = client.get(path.format(att), params={"user_id": uid})
            missing = client.get(path.format("ATT-2099-999999"), params={"user_id": uid})
            assert got.status_code == missing.status_code == 404, (who, path)
            assert got.json() == missing.json(), (who, path)
            assert got.headers["content-type"] == missing.headers["content-type"], (who, path)
    own = client.get(f"/internal/files/{att}/content", params={"user_id": cast["meera"]["id"]})
    assert own.status_code == 200 and own.content == b"%PDF-1.4 synthetic"
    get_settings.cache_clear()


def test_DEC_127_a_found_conversation_file_opens_for_its_uploader_the_desk_and_the_committee_only(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """Item 2, every viewer row on a conversation file in which our checks found a customer detail, put on an entry
    here as a belt (lane F's send refuses one, BLD-F095): its uploader, the review desk and the Ones Committee open
    it; the idea's lead or sharer who did not upload it, a co-sharer, the crew and anyone else get not found."""
    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    nisha = _co_sharer(db, idea)
    entry = _entry(db, idea, meera)
    by_desk = _row(db, idea, meera, purpose="conversation", entry=entry, state="personal_data_found")
    by_lead = _row(db, idea, kavya, purpose="conversation", entry=entry, state="personal_data_found")
    rows = {
        by_desk: ({"meera", "rohan", "dev"}, {"kavya", "nisha", "arjun", "sam"}),
        by_lead: ({"kavya", "meera", "rohan", "dev"}, {"nisha", "arjun", "sam"}),
    }
    people = {**cast, "nisha": nisha}
    for att, (opens, never) in rows.items():
        _copy(db, objects, att)
        for who in sorted(opens):
            item = F.get_item(db, att, people[who]["id"])
            assert item["customer_detail"] is True and item["view_url"] == f"/api/files/{att}/view", who
            assert F.content(db, att, people[who]["id"])[0] == b"%PDF-1.4 synthetic", who
        for who in sorted(never):
            _not_found_anywhere(db, att, people[who])
    # The found line is the uploader's only, as before (C-FILE.row); the desk reads `customer_detail`.
    assert "problem" not in F.get_item(db, by_desk, cast["rohan"]["id"])


def test_DEC_127_a_file_still_checking_opens_for_no_one_and_shows_only_to_its_uploader(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """DEC-127's last sentence: until the virus scan and the gatekeeper have both run the file is `checking`, so
    the desk, the committee, the idea's lead and the crew neither see nor open it, even with the pattern check
    done (`checks.patterns`). The uploader's own access is as before: the row, and no copy."""
    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    entry = _entry(db, idea, meera)
    waiting = [
        _row(db, idea, meera, purpose="conversation", entry=entry, state="checking"),  # sent, still checking
        _row(db, idea, kavya, state="checking"),  # the idea's own file
    ]
    for att in waiting:
        db.execute(
            "UPDATE attachments SET checks = checks || '{\"patterns\": true}'::jsonb WHERE id = %s", (att,)
        )
        _copy(db, objects, att)
    for att, uploader in zip(waiting, (meera, kavya), strict=True):
        for who in ("meera", "rohan", "dev", "kavya", "arjun", "sam"):
            if cast[who] is uploader:
                continue
            _not_found_anywhere(db, att, cast[who])
        item = F.get_item(db, att, uploader["id"])
        assert item["state"] == "checking" and "view_url" not in item
        assert _refused(F.content, db, att, uploader["id"]).status == 403


def test_DEC_127_BLD_C222_an_old_pipeline_file_clean_on_patterns_alone_opens_for_its_uploader_only(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """A file from before the cut-over (no `file_state`) that the old pipeline marked clean on the pattern check
    alone (`checks.gatekeeper` false): the routes treat it as never checked by the gatekeeper, so the desk, the
    committee, the idea's lead and the crew get not found; its uploader sees and opens it as before. Once
    `checks.gatekeeper` is true it is read as a checked file again."""
    idea, arjun = cast["idea"], cast["arjun"]
    old = _row(db, idea, arjun)  # Arjun added it to the idea's files under the old pipeline
    db.execute(
        "UPDATE attachments SET file_state = NULL, state = 'clean', "
        'checks = \'{"patterns": true, "ocr": false, "gatekeeper": false}\'::jsonb WHERE id = %s',
        (old,),
    )
    _copy(db, objects, old)
    for who in ("meera", "rohan", "dev", "kavya", "sam"):
        _not_found_anywhere(db, old, cast[who])
    assert F.get_item(db, old, arjun["id"])["view_url"] == f"/api/files/{old}/view"
    assert F.content(db, old, arjun["id"])[0] == b"%PDF-1.4 synthetic"
    db.execute(
        "UPDATE attachments SET checks = checks || '{\"gatekeeper\": true}'::jsonb WHERE id = %s", (old,)
    )
    for who in ("meera", "rohan", "kavya"):
        assert F.get_item(db, old, cast[who]["id"])["view_url"] == f"/api/files/{old}/view", who
    _not_found_anywhere(db, old, cast["sam"])


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
