"""BLD-C228, L-HIDE (BLD-C067's lock order): lane C's own callers take hide's lock on the idea before any row lock in
the same transaction, as lane F's team-up and lane B's desk do, so the two kinds of lock always queue in one order
and a team-up answer never deadlocks against a draft message, an edit, a file or the check.

A spy records, in order, each call of `hide.core.lock` as ("hide", uuid) and each statement with FOR UPDATE as
("row", sql). Each path is one transaction: its first lock is hide's on its idea, before its first row lock, and
hide's own call comes after the row lock (re-entrant, held already), so the path did reach hide. The assistant is
off, so no model is called; the file store, the virus scanner, the sandbox and the file gatekeeper are stood in for.
Synthetic people and values only (non-negotiable 11). Everything made is removed afterwards except `audit_log`,
whose trigger refuses DELETE."""

from __future__ import annotations

import datetime as dt
import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from attachments import clamav
from attachments import files as F
from attachments.extract import Extracted
from core.config import get_settings
from core.db import Conn
from draft import adapters as draft_adapters
from draft import store
from draft.store import Device, Owner
from hide import detect
from hide.core import scope_for
from submit import check
from submit import edit as submit_edit
from submit.config import DECLARATION_VERSION
from tests import f_teamup_fixtures as f
from tests import files as make

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
LAPTOP = Device("laptop", "laptop-c228-0001")
WORDS = "Investors call the branch about 40 times a day because the SMS only says R07."
Calls = list[tuple[str, str]]


def _pan() -> str:
    """A made-up PAN in the pattern's shape, new for each test."""
    return f"ABCPK{secrets.randbelow(900) + 100}4F"


@pytest.fixture
def db(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Iterator[Conn]:
    """The shared `db` with `ai.all` off (no model call; hide runs its patterns and names) and the seeded company
    repo; afterwards this test's jobs, the vault values under its ideas' scopes, its ideas and its people go."""
    from core import killswitch

    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    yield db
    scopes = [scope_for(i) for i in f._made["ideas"]]
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
    f.clean(db)
    db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'ai.all'")
    killswitch.clear_cache()
    get_settings.cache_clear()


@pytest.fixture
def locks(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Every lock asked for on `db`, in order: ("hide", uuid) for each `hide.core.lock` (lane C's callers and hide's
    own entry points reach it through the module), ("row", sql) for each statement with FOR UPDATE."""
    import hide.core

    calls: Calls = []
    real_lock, real_execute = hide.core.lock, db.execute

    def hide_lock(conn: Conn, idea_uuid: str) -> None:
        calls.append(("hide", str(idea_uuid)))
        real_lock(conn, idea_uuid)

    def execute(query: Any, params: Any = None, **kw: Any) -> Any:
        text = query if isinstance(query, str) else str(query)
        if "FOR UPDATE" in text.upper():
            calls.append(("row", " ".join(text.split())[:80]))
        return real_execute(query, params, **kw)

    monkeypatch.setattr(hide.core, "lock", hide_lock)
    monkeypatch.setattr(db, "execute", execute)
    return calls


@pytest.fixture
def stood_in(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """The file store (a dict), a clean scan, the sandbox's text layer and the file gatekeeper with nothing found:
    the check's own steps, without the stack's services."""
    kept: dict[str, bytes] = {}
    monkeypatch.setattr(F.store, "put", lambda bucket, key, data: kept.__setitem__(key, data))
    monkeypatch.setattr(F.store, "get", lambda bucket, key: kept[key])
    monkeypatch.setattr(F.store, "delete", lambda bucket, key: None)
    monkeypatch.setattr(F.clamav, "scan_bytes", lambda data, timeout=60.0: clamav.ScanResult(True, None))
    monkeypatch.setattr(
        F, "_extract", lambda kind, data, types: Extracted(pieces=[("page 1", WORDS)], pages=1, kind="pdf")
    )
    monkeypatch.setattr(F.hide_files, "gate_for", lambda conn, idea_uuid, text: detect.Gate([]))
    return kept


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    """Kavya (a draft, and an idea with the review desk whose edit window is open) and Meera at the review desk."""
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    closes = dt.datetime.now(dt.UTC) + dt.timedelta(days=2)
    return {
        "kavya": kavya,
        "meera": meera,
        "owner": Owner(kavya["id"], kavya["code"]),
        "draft": f.draft(db, kavya),
        "idea": f.idea(db, kavya, edit_closes_at=closes),
    }


def _hide_first(calls: Calls, idea_uuid: Any) -> None:
    """One transaction's locks: hide's on the idea first, before the first row lock, and hide's own call after it."""
    key = ("hide", str(idea_uuid))
    rows = [i for i, c in enumerate(calls) if c[0] == "row"]
    assert rows, calls  # the path locked a row
    assert calls[0] == key, calls
    assert key in calls[rows[0] + 1 :], calls  # hide itself, later: the lock is held already


# ---- draft/store.py (L-DRAFT) -------------------------------------------------------------------------------------


def test_l_hide_bld_c228_l_draft_add_and_edit_message_take_hides_lock_before_the_drafts_row(
    db: Conn, cast: dict[str, Any], locks: Calls
) -> None:
    """L-DRAFT.autosave, L-HIDE: `add_message` and `edit_message` lock hide first (`_load(lock=True)`), then the
    draft's row, then hide the words (`hide_message`)."""
    draft_id, owner = str(cast["draft"]["id"]), cast["owner"]
    mid, _ = store.add_message(db, owner, draft_id, LAPTOP, text=WORDS, defer_run=True)
    _hide_first(list(locks), draft_id)

    locks.clear()
    store.edit_message(db, owner, draft_id, mid, LAPTOP, text=f"{WORDS} Each call takes 5 to 10 minutes.")
    _hide_first(list(locks), draft_id)


def test_l_hide_bld_c228_l_draft_pins_a_parts_save_and_its_forget_take_hides_lock_before_the_drafts_row(
    db: Conn, cast: dict[str, Any], locks: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-DRAFT.pins: a part's words saved by hand (`set_part` with a value, masked through `hide_text`) and a list
    cut shorter (its lost item's hidden details go through `forget`) both lock hide first, then the draft's row."""
    draft_id, owner = str(cast["draft"]["id"]), cast["owner"]
    store.set_part(db, owner, draft_id, "often", LAPTOP, {"value": "About 40 calls a day at our branch"})
    _hide_first(list(locks), draft_id)

    store.set_part(
        db, owner, draft_id, "who", LAPTOP, {"value": ["Investors", f"Investors with PAN {_pan()}"]}
    )
    forgot: list[list[str]] = []
    real_forget = draft_adapters.forget

    def forget(conn: Conn, idea_uuid: str, source: str, source_ids: list[str]) -> None:
        forgot.append(list(source_ids))
        real_forget(conn, idea_uuid, source, source_ids)

    monkeypatch.setattr(draft_adapters, "forget", forget)
    locks.clear()
    store.set_part(db, owner, draft_id, "who", LAPTOP, {"value": ["Investors"]})
    _hide_first(list(locks), draft_id)
    # The cut item's details went, in the same transaction, under hide's lock.
    assert forgot and f"{draft_id}:part:who:1" in forgot[-1]


# ---- submit/ (L-SUBMIT) -------------------------------------------------------------------------------------------


def test_l_hide_bld_c228_l_submit_edit_save_takes_hides_lock_before_the_ideas_row(
    db: Conn, cast: dict[str, Any], locks: Calls
) -> None:
    """L-SUBMIT.edit: Save on the edit page, by the idea's reference, reads its uuid with no lock, locks hide, then
    the idea's row (`own.load_own(lock=True)`), then hides the new words (`mask_text`)."""
    idea = cast["idea"]
    out = submit_edit.save(
        db,
        str(idea["idea_id"]),
        cast["kavya"]["id"],
        {
            "declaration_version": DECLARATION_VERSION,
            "title": "SMS rejection codes confuse investors at branches",
        },
        now=dt.datetime.now(dt.UTC),
    )
    assert out["changed_fields"] == ["title"]
    _hide_first(list(locks), idea["id"])


def test_l_hide_bld_c228_l_submit_the_checks_final_pass_takes_hides_lock_before_the_ideas_row(
    db: Conn, cast: dict[str, Any], locks: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-SUBMIT.check: the check's last step locks hide, then the idea's row, then masks the shared text again
    (`_final_pass`, `mask_text`). Lane F's review had it as no mixed order; it was hide after the row."""
    monkeypatch.setattr(check.notify, "post", lambda *a, **k: None)  # lane A's Inbox is not what this checks
    idea = f.idea(db, cast["kavya"], status="checking")
    locks.clear()
    check.run(db, str(idea["id"]), gave_up=True)
    _hide_first(list(locks), idea["id"])
    row = db.execute("SELECT status FROM ideas WHERE id = %s", (idea["id"],)).fetchone()
    assert row is not None and row["status"] == "with_review_desk"


# ---- attachments/files.py (L-HIDE.files, A-API.files) -------------------------------------------------------------


def _answer(db: Conn, cast: dict[str, Any]) -> str:
    """A question Meera sent on Kavya's idea and Kavya's answer to it, not sent yet."""
    s = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at) "
        "VALUES (%s, %s, 'sent', '3d', now(), now() + interval '3 days') RETURNING id",
        (cast["idea"]["id"], cast["meera"]["id"]),
    ).fetchone()
    assert s is not None
    q = db.execute(
        "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, 1, 'evidence', %s) RETURNING id",
        (s["id"], b"synthetic"),
    ).fetchone()
    assert q is not None
    a = db.execute(
        "INSERT INTO answers (question_id, by_code) VALUES (%s, %s) RETURNING id",
        (q["id"], cast["kavya"]["code"]),
    ).fetchone()
    assert a is not None
    return str(a["id"])


def test_l_hide_bld_c228_a_api_files_adding_a_file_or_a_link_takes_hides_lock_before_any_row(
    db: Conn, cast: dict[str, Any], locks: Calls, stood_in: dict[str, bytes]
) -> None:
    """A-API.files: `accept` on a draft, on a shared idea by its reference, on its conversation and on an answer,
    and `accept_link` on the idea, each lock hide on the idea first (the uuid read with no lock), then the idea's or
    the answer's row, then hide the name (`hide_name`)."""
    kavya, draft, idea = cast["kavya"], cast["draft"], cast["idea"]
    answer_id = _answer(db, cast)
    data = make.pdf(["Calls double on Mondays."])
    for target, idea_uuid in (
        ({"draft_id": str(draft["id"])}, draft["id"]),
        ({"idea_id": str(idea["idea_id"])}, idea["id"]),
        ({"idea_id": str(idea["idea_id"]), "purpose": F.CONVERSATION}, idea["id"]),
        ({"answer_id": answer_id}, idea["id"]),
    ):
        locks.clear()
        item = F.accept(db, user_id=kavya["id"], name="branch-notes.pdf", data=data, **target)
        assert item["id"], target
        _hide_first(list(locks), idea_uuid)

    locks.clear()
    F.accept_link(db, user_id=kavya["id"], url="kfintech.sharepoint.com/ops/R07", idea_id=str(idea["id"]))
    _hide_first(list(locks), idea["id"])


def test_l_hide_bld_c228_l_hide_files_the_file_checks_finish_takes_hides_lock_before_the_files_row(
    db: Conn, cast: dict[str, Any], locks: Calls, stood_in: dict[str, bytes]
) -> None:
    """L-HIDE.files/1: the check's last transaction locks hide on the file's idea, then the file's row, then
    stores what hide found (`hide_file`); the gatekeeper ran before either lock."""
    idea = cast["idea"]
    att = F.accept(
        db,
        user_id=cast["kavya"]["id"],
        name="branch-notes.pdf",
        data=make.pdf([WORDS]),
        idea_id=str(idea["idea_id"]),
    )["id"]
    # BLD-C225: with the assistant off the check waits before the scan, so it is on here (the gatekeeper is stood in).
    from core import killswitch

    db.execute("UPDATE kill_switches SET state = 'on' WHERE name IN ('ai.all', 'agent.gatekeeper')")
    killswitch.clear_cache()
    locks.clear()
    assert F.check(db, att) == "checked"
    _hide_first(list(locks), idea["id"])
