"""Files and links on the 1% Club (L-HIDE.files, A-API.files, C-FILE; lane C, BLD-C105 to BLD-C109) against a migrated
test database, the dev stack's store and its virus scanner: adding a file to a draft, a shared idea or an answer, the
check job (scan, text layer, hide), who sees and opens what (DEC-107), links that are never fetched, and Try again,
Remove and "Hide it for me". Synthetic people, files and values only (non-negotiable 11); everything made here is
removed afterwards except `audit_log`, which refuses DELETE, so audit reads are scoped to this test's own ideas."""

from __future__ import annotations

import io
import secrets
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from attachments import files as F
from attachments import store
from core.config import get_settings
from core.db import Conn
from hide.core import VAULT_TYPE, own_words, scope_for
from onepc.context import open_text
from pii import vault
from tests import desk_fixtures as f
from tests import files as make
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes the people and ideas)

pytestmark = pytest.mark.stack

ALL = F.Uploads(
    limit_mb=25, types=F.DEFAULT_TYPES, internal_domains=("sharepoint.com", "teams.microsoft.com")
)


def _pan() -> str:
    return f"ABCPK{secrets.randbelow(900) + 100}4F"


# ---- pure rules ---------------------------------------------------------------------------------------------------


def test_C_FILE_uploader_1_the_help_line_is_written_from_the_one_limit_and_type_list() -> None:
    assert (
        ALL.help_text
        == "PDF, Word, PowerPoint, Excel, Markdown, HTML, ZIP, images or a whole folder, up to 25 MB each."
    )
    assert ALL.as_json() == {"limit_mb": 25, "types": list(F.DEFAULT_TYPES), "help_text": ALL.help_text}
    few = F.Uploads(limit_mb=15, types=("pdf", "png", "jpg"), internal_domains=())
    assert few.help_text == "PDF, images or a whole folder, up to 15 MB each."


def test_L_HIDE_files_5_screen_refuses_empty_too_big_locked_and_other_types() -> None:
    one = F.Uploads(limit_mb=1, types=F.DEFAULT_TYPES, internal_domains=())
    with pytest.raises(F.FileRefused) as e:
        F.screen(b"", "a.pdf", one)
    assert e.value.code == "file_empty"
    with pytest.raises(F.FileRefused) as e:
        F.screen(b"%PDF-1.4\n" + b"0" * (1024 * 1024), "big.pdf", one)
    assert (e.value.status, e.value.code, e.value.extra) == (413, "too_big", {"limit_mb": 1})
    assert e.value.body()["error"]["message"] == "Too big. Files can be up to 1 MB."

    locked_office = (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64 + "EncryptedPackage".encode("utf-16-le")
    )
    with pytest.raises(F.FileRefused) as e:
        F.screen(locked_office, "notes.docx", ALL)
    assert e.value.code == "locked"
    assert e.value.message == "We can’t check a locked file. Remove the password and add it again."

    with pytest.raises(F.FileRefused) as e:
        F.screen(b"MZ\x90\x00" + b"\x00" * 200, "tool.exe", ALL)
    assert (e.value.status, e.value.code) == (415, "type_not_allowed")
    assert e.value.message == ALL.help_text

    assert F.screen(make.pdf(["Branch notes"]), "notes.pdf", ALL) == "pdf"
    assert F.screen(b"# Branch notes\n\nCalls double on Mondays.\n", "notes.md", ALL) == "md"
    assert F.screen(b"<!doctype html><html><body>Notes</body></html>", "notes.htm", ALL) == "html"
    assert F.screen(make.png(), "shot.png", ALL) == "png"
    pdf_only = F.Uploads(limit_mb=25, types=("pdf",), internal_domains=())
    with pytest.raises(F.FileRefused) as e:
        F.screen(make.png(), "shot.png", pdf_only)
    assert e.value.code == "type_not_allowed"


SEES = {"uploader", "sharer", "crew", "desk", "other"}


@pytest.mark.parametrize(
    ("state", "who_sees", "who_opens"),
    [
        ("checked", {"uploader", "sharer", "crew", "desk"}, {"uploader", "sharer", "crew", "desk"}),
        ("hidden_checked", {"uploader", "sharer", "crew", "desk"}, {"uploader", "sharer", "crew", "desk"}),
        ("personal_data_found", {"uploader", "desk"}, {"uploader", "desk"}),
        ("checking", {"uploader"}, set()),
        ("uploading", {"uploader"}, set()),
        ("upload_failed", {"uploader"}, set()),
        ("infected", {"uploader"}, set()),
        ("locked", {"uploader"}, set()),
        ("too_big", {"uploader"}, set()),
    ],
)
def test_A_API_files_view_rule_who_sees_and_opens_a_file_by_state(
    state: str, who_sees: set[str], who_opens: set[str]
) -> None:
    viewers = {
        "uploader": F.Viewer(uploader=True, sharer=True, crew=True),
        "sharer": F.Viewer(sharer=True, crew=True),  # a co-sharer who did not add it
        "crew": F.Viewer(crew=True),
        "desk": F.Viewer(desk=True),
        "other": F.Viewer(),
    }
    for name, v in viewers.items():
        see, opens = F.rights(state, "file", draft=False, answer_unsent=False, viewer=v)
        assert see is (name in who_sees), (state, name)
        assert opens is (name in who_opens), (state, name)
        # A draft's files, and an unsent answer's, stay with the person who added them.
        for hidden in ({"draft": True, "answer_unsent": False}, {"draft": False, "answer_unsent": True}):
            see, opens = F.rights(state, "file", viewer=v, **hidden)
            assert see is (name == "uploader")
            assert opens is (name == "uploader" and state in F.VIEWABLE)


def test_A_API_files_links_are_parsed_and_classed_by_domain_only() -> None:
    assert F.parse_link("intranet.kfintech.com/page") == (
        "https://intranet.kfintech.com/page",
        "intranet.kfintech.com",
    )
    assert F.parse_link("https://kfintech.sharepoint.com/sites/ops/x.docx")[1] == "kfintech.sharepoint.com"
    for bad in ("", "not a link", "ftp://files.example.com/a", "javascript:alert(1)", "https://localhost/x",
                "https://user:pw@example.com/", "x" * 2001):  # fmt: skip
        with pytest.raises(F.FileRefused) as e:
            F.parse_link(bad)
        assert e.value.code == "not_a_link" and e.value.extra == {"field": "url"}
        assert (
            e.value.message == "That doesn’t look like a link. A link looks like intranet.kfintech.com/page."
        )
    assert F.link_scope("kfintech.sharepoint.com", ALL) == "internal"
    assert F.link_scope("teams.microsoft.com", ALL) == "internal"
    assert F.link_scope("notsharepoint.com", ALL) == "external"
    assert F.link_scope("example.org", ALL) == "external"


# ---- the database, the store and the scanner ----------------------------------------------------------------------


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core import killswitch
    from gateway import limits
    from gateway.routes import FAKE_SCRIPT

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    yield company_repo
    FAKE_SCRIPT.clear()
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path) -> Iterator[dict[str, Any]]:
    """Kavya shares an idea; Arjun is on its crew; Meera is the review desk; Rohan and Dev sit on the Ones
    Committee (the pack's role and the old one); Sam has nothing to do with it. Kavya also has a draft."""
    kavya = f.person(db, "Kavya Menon")
    arjun = f.person(db, "Arjun Nair")
    out = {
        "kavya": kavya, "arjun": arjun, "sam": f.person(db, "Sam Thomas"),
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "dev": f.person(db, "Dev Rao", roles=("core_committee",)),
        "idea": f.idea(db, kavya), "draft": f.idea(db, kavya, status="draft"),
    }  # fmt: skip
    f.crew(db, out["idea"], arjun)
    ideas = [str(out["idea"]["id"]), str(out["draft"]["id"])]
    started = db.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
    yield out
    s = get_settings()
    rows = db.execute(
        "SELECT id, store_key, masked_store_key FROM attachments WHERE idea_uuid = ANY(%s::uuid[])", (ideas,)
    ).fetchall()
    for r in rows:
        for key in (r["store_key"], r["masked_store_key"]):
            if key:
                store.delete(s.s3_bucket_quarantine, key)
                store.delete(s.s3_bucket_clean, key)
    ids = [str(r["id"]) for r in rows]
    # Every check job this test queued, its file removed or not: another module's `run_one` must never pick one up
    # (test_b3_04_drafts_purge runs the next due job of any type).
    db.execute(
        "DELETE FROM jobs WHERE type = %s AND (payload->>'attachment_id' = ANY(%s) OR (created_at >= %s AND NOT "
        "EXISTS (SELECT 1 FROM attachments a WHERE a.id = jobs.payload->>'attachment_id')))",
        (F.JOB, ids, started),
    )
    for i in ideas:
        vault.purge_scope(db, scope_for(i))
        db.execute("DELETE FROM vault_counters WHERE scope_id = %s", (scope_for(i),))
    db.execute("DELETE FROM llm_calls WHERE ref_id = ANY(%s::text[])", ([scope_for(i) for i in ideas],))


def _add(
    db: Conn, who: dict[str, str], data: bytes, name: str = "branch-notes.pdf", **target: Any
) -> dict[str, Any]:
    return F.accept(db, user_id=who["id"], name=name, data=data, **target)


def _row(db: Conn, att_id: str) -> dict[str, Any]:
    row = db.execute("SELECT * FROM attachments WHERE id = %s", (att_id,)).fetchone()
    assert row is not None
    return dict(row)


def _refused(fn: Any, *args: Any, **kwargs: Any) -> F.FileRefused:
    with pytest.raises(F.FileRefused) as e:
        fn(*args, **kwargs)
    return e.value


def _audits(db: Conn, idea_uuid: Any, action: str) -> list[dict[str, Any]]:
    return [
        dict(r["after"] or {})
        for r in db.execute(
            "SELECT after FROM audit_log WHERE entity = %s AND action = %s ORDER BY id",
            (f"idea:{idea_uuid}", action),
        ).fetchall()
    ]


def test_L_HIDE_files_1_2_a_clean_file_is_checking_then_checked_and_opens_for_crew_desk_and_committee(
    db: Conn, cast: dict[str, Any]
) -> None:
    from jobs import handlers  # noqa: F401 (registers the job types)
    from jobs.runner import DEAD_HANDLERS, HANDLERS

    assert F.JOB in HANDLERS and F.JOB in DEAD_HANDLERS
    idea, kavya = cast["idea"], cast["kavya"]
    data = make.pdf(["Calls double on Mondays at the branch.", "The SMS gives a code, not a reason."])
    item = _add(db, kavya, data, idea_id=idea["idea_id"])
    att = item["id"]
    assert item["state"] == "checking" and item["kind"] == "file" and item["type"] == "application/pdf"
    assert item["size"] == len(data) and item["name"] == "branch-notes.pdf" and "view_url" not in item
    assert item["added_by"]["name"] and item["customer_detail"] is False
    job = db.execute(
        "SELECT type, dedupe_key FROM jobs WHERE payload->>'attachment_id' = %s", (att,)
    ).fetchone()
    assert job is not None and job["dedupe_key"] == f"{F.JOB}:{att}"
    s = get_settings()
    key = _row(db, att)["store_key"]
    assert key.startswith(f"files/{att}-") and store.exists(s.s3_bucket_quarantine, key)

    # Until the checks finish, only Kavya sees it, and nobody opens it (non-negotiable 8).
    for who in ("arjun", "meera", "rohan", "sam"):
        assert _refused(F.get_item, db, att, cast[who]["id"]).code == "not_found"
    assert _refused(F.content, db, att, kavya["id"]).code == "not_available"

    assert F.check(db, att) == "checked"
    row = _row(db, att)
    assert (row["file_state"], row["state"], row["pages"]) == ("checked", "clean", 2)
    assert row["hidden_note"] is None and row["checks"]["result"] == "clean"
    assert store.exists(s.s3_bucket_clean, key) and not store.exists(s.s3_bucket_quarantine, key)
    assert F.check(db, att) == "checked"  # a second run of the job changes nothing

    for who in ("kavya", "arjun", "meera", "rohan", "dev"):
        got = F.get_item(db, att, cast[who]["id"])
        assert got["state"] == "checked" and got["view_url"] == f"/api/files/{att}/view" and got["pages"] == 2
        body, mime, _name = F.content(db, att, cast[who]["id"])
        assert body == data and mime == "application/pdf"
    assert _refused(F.get_item, db, att, cast["sam"]["id"]).code == "not_found"
    assert _refused(F.content, db, att, cast["sam"]["id"]).code == "not_found"
    assert _refused(F.get_item, db, att, "not-a-user").code == "not_found"
    assert _refused(F.get_item, db, "ATT-1999-000001", kavya["id"]).code == "not_found"
    assert _refused(F.get_item, db, "../etc", kavya["id"]).code == "not_found"
    assert [a["state"] for a in _audits(db, idea["id"], "file.checked")] == ["checked"]
    assert len(_audits(db, idea["id"], "file.opened")) == 5
    assert F.items_for(db, str(idea["id"]), cast["arjun"]["id"])[0]["id"] == att

    # A committee grant that has ended opens nothing.
    db.execute(
        "UPDATE role_grants SET valid_from = now() - interval '2 days', valid_to = now() - interval '1 minute' "
        "WHERE user_id = %s",
        (cast["rohan"]["id"],),
    )
    assert _refused(F.content, db, att, cast["rohan"]["id"]).code == "not_found"


def test_L_HIDE_files_3_DEC_107_a_customer_detail_marks_the_file_and_keeps_it_from_the_crew(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, kavya = cast["idea"], cast["kavya"]
    pan = _pan()
    data = make.pdf(["Calls double on Mondays.", f"The investor with PAN {pan} called twice."])
    att = _add(db, kavya, data, idea_id=str(idea["id"]))["id"]
    assert F.check(db, att) == "personal_data_found"

    row = _row(db, att)
    assert row["file_state"] == "personal_data_found" and row["state"] != "clean"  # never marked clean
    assert row["hidden_note"] == "A PAN on page 2 is hidden."
    assert row["checks"]["found"] == [{"kind": "pan", "page": 2}]
    details = db.execute(
        "SELECT source, source_id, kind, masked FROM hidden_details WHERE idea_uuid = %s", (idea["id"],)
    ).fetchall()
    assert [(d["source"], d["source_id"], d["kind"]) for d in details] == [("file", att, "pan")]
    assert pan not in str(details[0]["masked"])
    assert (
        own_words(db, "file", att, idea_uuid=str(idea["id"])) is None
    )  # a file has no sealed own-words copy
    assert pan in {value for _type, value in vault.mapping(db, scope_for(str(idea["id"]))).values()}

    mine = F.get_item(db, att, kavya["id"])
    assert mine["state"] == "personal_data_found" and mine["customer_detail"] is True
    assert mine["problem"] == "Found a PAN on page 2. Nobody can open it until it’s hidden."
    assert mine["hidden_note"] == "A PAN on page 2 is hidden." and mine["view_url"]
    for who in ("kavya", "meera", "rohan", "dev"):
        assert F.content(db, att, cast[who]["id"])[0] == data
        assert F.get_item(db, att, cast[who]["id"])["customer_detail"] is True
    for who in ("arjun", "sam"):  # never the crew, never anyone else
        assert _refused(F.get_item, db, att, cast[who]["id"]).code == "not_found"
        assert _refused(F.content, db, att, cast[who]["id"]).code == "not_found"
    assert F.items_for(db, str(idea["id"]), cast["arjun"]["id"]) == []

    # Lane B's desk and answer rows read the same columns (desk.asking._files): the state and the note.
    from desk.store import CUSTOMER_DETAIL

    assert row["file_state"] == CUSTOMER_DETAIL
    for audit in _audits(db, idea["id"], "file.checked") + _audits(db, idea["id"], "file.opened"):
        assert pan not in str(audit) and "branch-notes" not in str(audit)


def test_L_HIDE_files_values_the_desk_hid_on_the_idea_are_hidden_in_a_file_too(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The desk's "Hide this" marked a name the patterns do not know; the same name in a file is hidden again."""
    idea, kavya = cast["idea"], cast["kavya"]
    name = "Kiran Ra" + "".join(secrets.choice("bcdfghjklmnpqrstvwxz") for _ in range(4))
    tag = vault.assign(db, scope_for(str(idea["id"])), VAULT_TYPE["name"], name)
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, vault_tag, "
        "found_by) VALUES (%s, 'desk', %s, 0, %s, 'name', 'Name ••••', %s, 'reviewer')",
        (idea["id"], str(uuid.uuid4()), len(name), tag),
    )
    att = _add(
        db,
        kavya,
        f"# Notes\n\nThe agent {name} keeps calling.\n".encode(),
        "notes.md",
        idea_id=idea["idea_id"],
    )["id"]
    assert F.check(db, att) == "personal_data_found"
    assert _row(db, att)["hidden_note"] == "Name hidden"  # not a page: the label, as the answer rows have it


def test_L_HIDE_files_6_an_infected_file_is_deleted_and_never_opens(db: Conn, cast: dict[str, Any]) -> None:
    att = _add(db, cast["kavya"], make.eicar_docx(), "notes.docx", idea_id=cast["idea"]["idea_id"])["id"]
    assert F.check(db, att) == "infected"
    row = _row(db, att)
    assert (row["file_state"], row["state"]) == ("infected", "rejected")
    assert not store.exists(get_settings().s3_bucket_quarantine, row["store_key"])
    assert not store.exists(get_settings().s3_bucket_clean, row["store_key"])
    assert F.get_item(db, att, cast["kavya"]["id"])["state"] == "infected"
    assert _refused(F.content, db, att, cast["kavya"]["id"]).code == "not_available"
    assert _refused(F.get_item, db, att, cast["meera"]["id"]).code == "not_found"


def test_L_HIDE_files_5_a_pdf_with_a_password_is_locked_after_the_scan(
    db: Conn, cast: dict[str, Any]
) -> None:
    from pypdf import PdfReader, PdfWriter

    w = PdfWriter()
    for page in PdfReader(io.BytesIO(make.pdf(["Synthetic notes"]))).pages:
        w.add_page(page)
    w.encrypt(user_password="kfin-test", owner_password="kfin-test-owner")
    out = io.BytesIO()
    w.write(out)
    att = _add(db, cast["kavya"], out.getvalue(), idea_id=cast["idea"]["idea_id"])["id"]
    assert F.check(db, att) == "locked"
    item = F.get_item(db, att, cast["kavya"]["id"])
    assert item["state"] == "locked"
    assert item["problem"] == "We can’t check a locked file. Remove the password and add it again."


def test_L_HIDE_files_5_a_zip_is_unpacked_and_each_file_checked(db: Conn, cast: dict[str, Any]) -> None:
    pan = _pan()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.md", "# Clean notes\n")
        z.writestr("b.csv", f"Investor,PAN\nSomeone,{pan}\n")
    att = _add(db, cast["kavya"], buf.getvalue(), "pack.zip", idea_id=cast["idea"]["idea_id"])["id"]
    assert _row(db, att)["mime"] == "application/zip"
    assert F.check(db, att) == "personal_data_found"
    assert _row(db, att)["hidden_note"] == "PAN hidden"


def test_A_API_files_one_target_a_draft_is_its_owners_alone(db: Conn, cast: dict[str, Any]) -> None:
    kavya, draft = cast["kavya"], cast["draft"]
    data = make.pdf(["Synthetic"])
    assert _refused(_add, db, kavya, data).code == "target_required"
    two = _refused(_add, db, kavya, data, draft_id=str(draft["id"]), idea_id=cast["idea"]["idea_id"])
    assert (two.status, two.code) == (422, "target_required")
    assert _refused(_add, db, cast["sam"], data, draft_id=str(draft["id"])).code == "not_found"
    assert (
        _refused(_add, db, cast["arjun"], data, idea_id=cast["idea"]["idea_id"]).code == "not_found"
    )  # crew
    assert _refused(_add, db, kavya, data, draft_id="IDEA-2026-000001").code == "not_found"
    assert (
        _refused(_add, db, kavya, data, draft_id=str(cast["idea"]["id"])).code == "not_found"
    )  # not a draft

    att = _add(db, kavya, data, draft_id=str(draft["id"]))["id"]
    assert F.check(db, att) == "checked"
    assert F.get_item(db, att, kavya["id"])["view_url"]
    for who in ("meera", "rohan", "arjun"):
        assert _refused(F.get_item, db, att, cast[who]["id"]).code == "not_found"
    assert [i["id"] for i in F.items_for(db, str(draft["id"]), kavya["id"])] == [att]

    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (cast["idea"]["id"],))
    assert _refused(_add, db, kavya, data, idea_id=cast["idea"]["idea_id"]).code == "idea_closed"


def test_A_API_files_answer_files_sit_on_the_answer_and_the_answers_idea(
    db: Conn, cast: dict[str, Any]
) -> None:
    from desk import asking

    idea, kavya = cast["idea"], cast["kavya"]
    sent = asking.send_set(
        db, idea["idea_id"], cast["meera"]["id"],
        {"questions": [{"part": "evidence", "text": "Can you add a screenshot of the SMS?"}], "time_to_answer": "3d"},
    )  # fmt: skip
    qid = sent["questions"][0]["id"]
    answer = asking.save_answer(db, qid, kavya["id"], "Here is the SMS.")
    pan = _pan()
    att = _add(db, kavya, make.png_with_text(f"SMS for PAN {pan}"), "sms.png", answer_id=answer["id"])["id"]
    row = _row(db, att)
    assert str(row["answer_id"]) == answer["id"] and row["idea_uuid"] == idea["id"]
    assert row["mime"] == "image/png"
    assert _refused(_add, db, cast["arjun"], make.png(), answer_id=answer["id"]).code == "not_found"
    assert _refused(_add, db, kavya, make.png(), answer_id=str(uuid.uuid4())).code == "not_found"

    assert F.check(db, att) == "personal_data_found"
    # Unsent: the review desk does not see it yet; Kavya does.
    assert _refused(F.get_item, db, att, cast["meera"]["id"]).code == "not_found"
    assert F.items_for(db, str(idea["id"]), kavya["id"], answer_id=answer["id"])[0]["id"] == att
    shown = asking._files(db, [answer["id"]])[answer["id"]]
    assert [(x["id"], x["state"], x["customer_detail"]) for x in shown] == [
        (att, "personal_data_found", True)
    ]
    assert (
        shown[0]["hidden_note"] == "PAN hidden"
    )  # an image has no pages: the label, as the answer rows have it

    asking.send_answers(db, sent["id"], kavya["id"])
    assert F.get_item(db, att, cast["meera"]["id"])["customer_detail"] is True
    assert F.content(db, att, cast["rohan"]["id"])[1] == "image/png"
    assert _refused(F.content, db, att, cast["arjun"]["id"]).code == "not_found"
    late = _refused(_add, db, kavya, make.png(), answer_id=answer["id"])
    assert (late.status, late.code) == (409, "answer_sent")


def test_A_API_files_links_are_classed_stored_sealed_and_never_opened(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    def no_network(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a link was fetched")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    idea, kavya = cast["idea"], cast["kavya"]
    inside = F.accept_link(db, user_id=kavya["id"], url="kfintech.sharepoint.com/sites/ops/sms.docx",
                           idea_id=idea["idea_id"])  # fmt: skip
    outside = F.accept_link(
        db, user_id=kavya["id"], url="https://example.org/report", idea_id=idea["idea_id"]
    )
    monkeypatch.undo()
    assert (inside["kind"], inside["state"], inside["link_scope"], inside["type"]) == (
        "link",
        "ok",
        "internal",
        "link",
    )
    assert inside["url"] == "https://kfintech.sharepoint.com/sites/ops/sms.docx"
    assert outside["link_scope"] == "external" and "size" not in outside and "view_url" not in outside
    row = _row(db, inside["id"])
    assert b"sharepoint" not in bytes(row["url_encrypted"])
    assert open_text("attachments", "url_encrypted", inside["id"], row["url_encrypted"]) == inside["url"]
    crew = F.get_item(db, inside["id"], cast["arjun"]["id"])
    assert crew["url"] == row["name"] and "view_url" not in crew
    assert _refused(F.content, db, inside["id"], kavya["id"]).code == "not_available"
    bad = _refused(F.accept_link, db, user_id=kavya["id"], url="not a link", idea_id=idea["idea_id"])
    assert (bad.status, bad.code) == (422, "not_a_link")

    pan = _pan()
    masked = F.accept_link(
        db, user_id=kavya["id"], url=f"https://example.org/lookup?pan={pan}", idea_id=idea["idea_id"]
    )
    assert pan in masked["url"]  # the person who added it gets the address as typed
    assert pan not in F.get_item(db, masked["id"], cast["meera"]["id"])["url"]
    assert pan not in _row(db, masked["id"])["name"]


def test_A_API_files_part_2_try_again_remove_and_hide_it_for_me(db: Conn, cast: dict[str, Any]) -> None:
    idea, kavya = cast["idea"], cast["kavya"]
    pan = _pan()
    att = _add(db, kavya, make.pdf([f"PAN {pan}"]), idea_id=idea["idea_id"])["id"]
    F.gave_up(db, att)  # the checks could not finish after every retry
    failed = F.get_item(db, att, kavya["id"])
    assert (
        failed["state"] == "upload_failed"
        and failed["problem"] == "Didn’t upload. Your other files are fine."
    )
    key = _row(db, att)["store_key"]
    assert store.exists(get_settings().s3_bucket_quarantine, key)  # kept for Try again

    assert _refused(F.retry, db, att, cast["meera"]["id"]).code == "not_found"
    again = F.retry(db, att, kavya["id"])
    assert again["state"] == "checking"
    assert _refused(F.retry, db, att, kavya["id"]).code == "not_failed"
    assert F.check(db, att) == "personal_data_found"

    blackout = _refused(F.hide_for_me, db, att, kavya["id"])
    assert (blackout.status, blackout.code) == (503, "not_available")
    assert _refused(F.remove, db, att, cast["meera"]["id"]).code == "forbidden"
    assert _refused(F.remove, db, att, cast["arjun"]["id"]).code == "not_found"
    F.remove(db, att, kavya["id"])
    assert db.execute("SELECT 1 FROM attachments WHERE id = %s", (att,)).fetchone() is None
    assert db.execute("SELECT 1 FROM hidden_details WHERE source_id = %s", (att,)).fetchone() is None
    assert (
        db.execute(
            "SELECT 1 FROM jobs WHERE type = %s AND payload->>'attachment_id' = %s", (F.JOB, att)
        ).fetchone()
        is None
    )
    assert not store.exists(get_settings().s3_bucket_clean, key)
    assert [a["file_id"] for a in _audits(db, idea["id"], "file.removed")] == [att]
    assert _refused(F.get_item, db, att, kavya["id"]).code == "not_found"


# ---- the worker's routes (A-API.files behind the internal token) ----------------------------------------------------

TOKEN = "lane-c-files-test-token-0123456789abcdef"


@pytest.fixture
def client(cast: dict[str, Any], test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from tests import helpers

    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    from api.app import app

    yield TestClient(app, headers={"X-Internal-Token": TOKEN})
    get_settings.cache_clear()


def test_A_API_files_worker_routes_upload_poll_view_and_refuse_in_the_packs_shape(
    db: Conn, cast: dict[str, Any], client: Any
) -> None:
    from fastapi.testclient import TestClient

    kavya, ref = cast["kavya"], cast["idea"]["idea_id"]
    assert TestClient(client.app).get("/internal/files/config").status_code == 401
    config = client.get("/internal/files/config").json()
    assert (
        config["limit_mb"] == 25
        and "md" in config["types"]
        and config["help_text"].endswith("up to 25 MB each.")
    )

    data = make.pdf(["Calls double on Mondays."])
    up = client.post(
        "/internal/files",
        data={"user_id": kavya["id"], "idea_id": ref},
        files={"file": ("C:\\Users\\kavya\\branch notes.pdf", data, "application/pdf")},
    )
    assert up.status_code == 201, up.text
    item = up.json()
    assert (
        item["state"] == "checking"
        and item["name"] == "branch notes.pdf"
        and up.headers["cache-control"] == "no-store"
    )
    att = item["id"]
    assert client.get(f"/internal/files/{att}", params={"user_id": cast["sam"]["id"]}).status_code == 404
    early = client.get(f"/internal/files/{att}/content", params={"user_id": kavya["id"]})
    assert early.status_code == 403 and early.json()["error"]["code"] == "not_available"

    assert F.check(db, att) == "checked"
    polled = client.get(f"/internal/files/{att}", params={"user_id": cast["arjun"]["id"]}).json()
    assert polled["state"] == "checked" and polled["view_url"] == f"/api/files/{att}/view"
    seen = client.get(f"/internal/files/{att}/content", params={"user_id": cast["rohan"]["id"]})
    assert seen.status_code == 200 and seen.content == data
    assert (
        seen.headers["content-type"] == "application/pdf"
        and seen.headers["x-file-name"] == "branch%20notes.pdf"
    )

    big = client.post(
        "/internal/files", data={"user_id": kavya["id"], "idea_id": ref},
        files={"file": ("big.pdf", b"%PDF-1.4\n" + b"0" * (25 * 1024 * 1024), "application/pdf")},
    )  # fmt: skip
    assert big.status_code == 413
    assert big.json() == {
        "error": {"limit_mb": 25, "code": "too_big", "message": "Too big. Files can be up to 25 MB."}
    }
    exe = client.post(
        "/internal/files", data={"user_id": kavya["id"], "idea_id": ref},
        files={"file": ("tool.exe", b"MZ" + b"\x00" * 100, "application/octet-stream")},
    )  # fmt: skip
    assert exe.status_code == 415 and exe.json()["error"]["code"] == "type_not_allowed"
    none = client.post(
        "/internal/files", data={"user_id": kavya["id"]}, files={"file": ("a.pdf", data, "application/pdf")}
    )
    assert none.status_code == 422 and none.json()["error"]["code"] == "target_required"

    link = client.post(
        "/internal/links", json={"user_id": kavya["id"], "idea_id": ref, "url": "example.org/x"}
    )
    assert link.status_code == 201 and link.json()["link_scope"] == "external"
    bad = client.post("/internal/links", json={"user_id": kavya["id"], "idea_id": ref, "url": "no link here"})
    assert bad.status_code == 422 and bad.json()["error"]["field"] == "url"
    assert client.post(f"/internal/files/{att}/hide", params={"user_id": kavya["id"]}).json()["error"][
        "code"
    ] == ("not_available")
    assert client.post(f"/internal/files/{att}/retry", params={"user_id": kavya["id"]}).status_code == 409
    assert client.delete(f"/internal/files/{att}", params={"user_id": cast["sam"]["id"]}).status_code == 404
    assert client.delete(f"/internal/files/{att}", params={"user_id": kavya["id"]}).status_code == 204
    for refused in (early, big, exe, none, bad):  # errors never echo a file name or a link (non-negotiable 3)
        assert (
            "tool.exe" not in refused.text and "branch" not in refused.text and "no link" not in refused.text
        )
