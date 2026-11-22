"""Files and links on a draft, a shared idea or an answer (L-HIDE.files, A-API.files, C-FILE; lane C, BLD-C105
to BLD-C109). Lane B's answer screen (S-R3) and the desk (S-R2) read the same rows (`desk.asking._files`,
`desk.reads._checked_files`), so the columns and states here are theirs too.

A file's life (`attachments.file_state`, E-ENUMS.file):
1. `POST /files`: one configurable size limit and type list (BLD-E007; `rules/thresholds.md` `files`), a locked
   file refused, the name's details hidden, the bytes into the quarantine bucket, the row `checking`, and the
   `file.check` job queued. "Uploading" is the browser's own progress: a row exists once the bytes are stored.
2. The job (`check`): the virus scan first; then, in the sandbox, the file's structure (which Office type a ZIP
   is, a password, the types inside a ZIP) and its text layer (OCR for images and scanned pages, every cell of a
   spreadsheet, every file in a ZIP); then the gatekeeper on that text, piece by piece, and hide's detection
   (`hide.files`). Before the scan only the bytes' size and magic numbers are read: nothing is unpacked or parsed,
   and nobody opens the file before both checks finish (non-negotiable 8, L-HIDE.files/6).
3. The result: `checked`, or `personal_data_found` (DEC-107: it can still be sent, and opens only for the person
   who added it, the review desk and the Ones Committee), or `infected`, `locked`, `too_big`, `upload_failed`.
   A checked or found file moves to the clean bucket; the scan's verdict, not the bucket, decides who opens it.
   When the scanner, OCR, the store or the gatekeeper does not answer, the file stays `checking` and the job tries
   again; after its last try the file is `upload_failed`, with Try again. It is never `checked` without the
   gatekeeper (non-negotiable 4, DEC-103; BLD-C107). While `ai.all` or `agent.gatekeeper` is switched off, by a
   person or a process, or the day's budget is spent, the check waits without using a try (`JobWaits`, BLD-C225):
   before the virus scan, so no scan is repeated while it is off, the file stays `checking` with
   `checks.waiting_for` "gatekeeper", and its row reads `WAITING_LINE`. The ticker's watch runs waiting checks
   within a tick of the switches coming back on (`requeue_waiting`, BLD-C226); the 300-second step is only the
   fallback. Each other wait (`CheckWaits`: the scanner, the store, OCR, the gateway failing) is still a try, and
   its reason is kept in `checks.waiting_for`, so a file that gives up says which wait it died of.
   At worker start, files that an earlier build (r3) let die of those waits are put back to waiting
   (`start_sweep`, BLD-C227): nothing is checked or opened by it.
4. The old `state` column is kept in step only for the checked states, which are its `clean`; nothing else is ever
   marked clean, so the old `/api/attachments/:id` route never serves a file DEC-107 keeps from people.

A link (`POST /links`) is never fetched (non-negotiable 8, BLD-E001): it is classed internal or external by its
domain only, stored encrypted, and its details hidden like any text. Its row is named by its address, host and
path as the boards show it ("kfintech.sharepoint.com/ops/R07").

Who sees and opens what (DEC-107, P-PRODUCT.privacy; the coordinator's rule of 17 Nov), in `rights`:
- the person who added it: the row in every state; opens it once checked or found;
- checked, hidden_checked and ok: the idea's sharers, its crew, the review desk and the Ones Committee;
- personal_data_found: the review desk and the Ones Committee as well, never the crew or a co-sharer;
- a conversation file (`purpose = 'conversation'`, the "+" in S-08's box, DEC-124) with a customer detail found also
  opens for the idea's own sharer, so it opens for the sharer, the desk and the committee (DEC-107; BLD-C216);
- a draft's files, and a draft answer's: only the person who added them;
- everyone else: not found.

A file's `purpose` is `idea` (Proof, the edit page, an answer) or `conversation` (BLD-C216). Every reader of an idea's
own files reads `purpose = 'idea' AND conversation_entry_id IS NULL` (`IDEA_OWN`), so a conversation file never
shows among them. A conversation file still not on an entry a day after it was added is removed by the sweep.
Logs, errors and audit carry IDs, states and kinds only (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from botocore.exceptions import ClientError
from psycopg.types.json import Jsonb

from attachments import clamav, sandbox, store
from attachments.extract import Extracted
from attachments.filetype import CONTAINER, CONTAINER_TYPES, kind_before_scan, locked_before_scan
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from desk.store import CUSTOMER_DETAIL, DESK_SEES, FILES_CHECKED, READERS, code_of, has_role, own_codes
from hide import core as hide_core
from hide import files as hide_files
from jobs.runner import JobWaits
from jobs.runner import log as jobs_log
from onepc.context import open_text, seal_text

log = get_logger("files")

JOB = "file.check"
OCR_TIMEOUT_S = 240.0
CHECKING = "checking"
VIEWABLE: tuple[str, ...] = ("checked", "hidden_checked", CUSTOMER_DETAIL)  # a stored copy that can be opened
FINAL_FAILED = ("infected", "locked", "too_big", "upload_failed")
IDEA, CONVERSATION = "idea", "conversation"  # attachments.purpose (BLD-C216)
# The idea's own files: never one added for the conversation, sent or not (both conditions, so a row that is half
# one and half the other is never shown as the idea's). Callers prefix the columns when they join.
IDEA_OWN = "purpose = 'idea' AND conversation_entry_id IS NULL"
UNSENT_CONVERSATION_HOURS = 24  # a conversation file not on an entry after this long is removed (BLD-C216)
# Waiting for the gatekeeper (BLD-C225 to BLD-C227). The names are pinned by lane A's upgrade and its rehearsal.
GATEKEEPER = "gatekeeper"  # `checks.waiting_for` while the check waits for it
WAITING_GATEKEEPER = "waiting_gatekeeper"  # the job's `last_error` while it waits (a reason, not a failure)
WAIT_STEP_S = 300  # the fallback step: the watch runs waiting checks within a tick of the switch-on
# The gateway's codes for an assistant that is off (switched off, or the day's budget spent), not failing.
ASSISTANT_OFF = ("switched_off", "daily_budget")
NO_WAIT = "none"  # `checks.waiting_for` of a file that gave up on an error that was not a wait
BATCH = 50  # rows per commit in the switch-on re-queue and the start sweep
SYSTEM = "system:files"
# To confirm later (HR, DEC-123): the line a file's row shows while it waits for the gatekeeper.
WAITING_LINE = "Waiting for the personal details check. It runs when the assistant is back."

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "md": "text/markdown",
    "html": "text/html",
    "zip": "application/zip",
    "png": "image/png",
    "jpg": "image/jpeg",
}
# The help line's words for the types, in order (C-FILE.uploader/1): "PDF, Word, PowerPoint, Excel, Markdown,
# HTML, ZIP, images or a whole folder, up to 25 MB each."
TYPE_WORDS = {
    "pdf": "PDF", "docx": "Word", "pptx": "PowerPoint", "xlsx": "Excel", "csv": "Excel", "md": "Markdown",
    "html": "HTML", "zip": "ZIP", "png": "images", "jpg": "images",
}  # fmt: skip
DEFAULT_TYPES = ("pdf", "docx", "pptx", "xlsx", "csv", "md", "html", "zip", "png", "jpg")

# reference/copy/Edit.md, C-FILE.row, L-HIDE.files/5, V-FIELDS (curly apostrophes as the boards set them).
UPLOAD_FAILED = "Didn’t upload. Your other files are fine."
LOCKED = "We can’t check a locked file. Remove the password and add it again."
NOT_A_LINK = "That doesn’t look like a link. A link looks like intranet.kfintech.com/page."
NOT_FOUND = "We couldn't find that. It may have changed. Refresh and try again."  # as hide's routes say it
ONLY_YOURS = "Only the person who added this file can do that."


def too_big_line(limit_mb: int) -> str:
    return f"Too big. Files can be up to {limit_mb} MB."


class FileRefused(Exception):
    """A refusal in the pack's error shape (A-API.conventions/2). `code` is safe to log."""

    def __init__(self, status: int, code: str, message: str = "", **extra: Any) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def body(self) -> dict[str, Any]:
        return {"error": {**self.extra, "code": self.code, "message": self.message}}


def _not_found() -> FileRefused:
    return FileRefused(404, "not_found", NOT_FOUND)


# ---- configuration (BLD-E007) ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Uploads:
    limit_mb: int
    types: tuple[str, ...]
    internal_domains: tuple[str, ...]

    @property
    def limit_bytes(self) -> int:
        return self.limit_mb * 1024 * 1024

    @property
    def help_text(self) -> str:
        words = list(dict.fromkeys(TYPE_WORDS[t] for t in self.types if t in TYPE_WORDS))
        return f"{', '.join(words)} or a whole folder, up to {self.limit_mb} MB each."

    def as_json(self) -> dict[str, Any]:
        """A-API.files `GET /config/uploads`: `{ limit_mb, types[], help_text }`."""
        return {"limit_mb": self.limit_mb, "types": list(self.types), "help_text": self.help_text}


def uploads() -> Uploads:
    """`rules/thresholds.md` `files` from the company repo; the defaults are the same values, for a repo seeded before
    the section existed. Internal link domains add KFintech's own domains and the 1% Club's host."""
    from rules import load_rule

    s = get_settings()
    try:
        f = load_rule(Path(s.company_repo_path), "thresholds").data.get("files") or {}
    except (
        Exception
    ):  # an unreadable rules file must not stop uploads; the defaults are the configured values
        f = {}
    host = (urlsplit(s.app_base_url).hostname or "").lower()
    domains = [*(f.get("internal_link_domains") or ()), *s.kfin_domains, *([host] if host else [])]
    return Uploads(
        limit_mb=int(f.get("limit_mb") or 25),
        types=tuple(f.get("types") or DEFAULT_TYPES),
        internal_domains=tuple(dict.fromkeys(d.lower() for d in domains if d)),
    )


# ---- who may see and open a file (DEC-107) ----------------------------------------------------------------------


@dataclass(frozen=True)
class Viewer:
    uploader: bool = False  # added this file (or link)
    sharer: bool = False  # a credited sharer of the idea (`own_codes`)
    crew: bool = False  # on the idea's crew
    desk: bool = False  # the review desk or the Ones Committee (`desk.store.READERS`)
    lead: bool = False  # the idea's own sharer (its contributor), not a co-sharer from a merge


def rights(
    state: str, kind: str, *, draft: bool, answer_unsent: bool, viewer: Viewer, conversation: bool = False
) -> tuple[bool, bool]:
    """(sees the row, opens the file). Pure, so every row of the rule has its own unit test. A conversation file
    with a customer detail found opens for the idea's own sharer as it does for the desk (DEC-107, BLD-C216)."""
    if viewer.uploader:
        see = True
    elif draft or answer_unsent:
        see = False  # a draft's files, and a draft answer's, stay with the person who added them
    elif viewer.desk or (conversation and viewer.lead):
        see = state in DESK_SEES
    elif viewer.sharer or viewer.crew:
        see = state in FILES_CHECKED
    else:
        see = False
    return see, see and kind == "file" and state in VIEWABLE


def effective_state(row: dict[str, Any]) -> str:
    """A file from before the cut-over has no `file_state`: the old pipeline's clean is checked, its waiting states
    are checking, and a refused file (its copy already deleted) failed."""
    if row.get("file_state"):
        return str(row["file_state"])
    old = row.get("state")
    if old == "clean":
        return "checked"
    return "upload_failed" if old == "rejected" else CHECKING


def old_state(state: str) -> str:
    """The old `state` column, in step only for the checked states (`clean`): nothing else is ever marked clean."""
    if state in ("checked", "hidden_checked"):
        return "clean"
    return "rejected" if state in FINAL_FAILED else "quarantine"


_ROW = (
    "SELECT a.*, i.status AS idea_status, i.contributor_code AS idea_code, "
    "(SELECT an.sent_at FROM answers an WHERE an.id = a.answer_id) AS answer_sent_at "
    "FROM attachments a JOIN ideas i ON i.id = a.idea_uuid WHERE a.id = %s"
)


def _load(conn: Conn, att_id: str, *, lock: bool = False) -> dict[str, Any]:
    if not re.fullmatch(r"ATT-[0-9]{4}-[0-9]{6}", att_id or ""):
        raise _not_found()
    row = conn.execute(_ROW + (" FOR UPDATE OF a" if lock else ""), (att_id,)).fetchone()
    if row is None:
        raise _not_found()
    return dict(row)


def _viewer(conn: Conn, row: dict[str, Any], user_id: str) -> Viewer:
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        return Viewer()
    code = code_of(conn, user_id)
    uploader = str(row.get("uploaded_by_user") or "") == str(user_id) or (
        code is not None and code == row.get("uploaded_by_code")
    )
    idea = {"id": row["idea_uuid"], "contributor_code": row["idea_code"]}
    sharer = code is not None and code in own_codes(conn, idea)
    crew = code is not None and (
        conn.execute(
            "SELECT 1 FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s AND left_at IS NULL LIMIT 1",
            (row["idea_uuid"], code),
        ).fetchone()
        is not None
    )
    lead = code is not None and code == row["idea_code"]
    return Viewer(
        uploader=uploader, sharer=sharer, crew=crew, desk=has_role(conn, user_id, READERS), lead=lead
    )


def _rights(conn: Conn, row: dict[str, Any], user_id: str) -> tuple[Viewer, bool, bool]:
    v = _viewer(conn, row, user_id)
    see, opens = rights(
        effective_state(row), str(row.get("kind") or "file"), draft=row["idea_status"] == "draft",
        answer_unsent=row.get("answer_id") is not None and row.get("answer_sent_at") is None, viewer=v,
        conversation=row.get("purpose") == CONVERSATION,
    )  # fmt: skip
    return v, see, opens


# ---- the FileItem (E-ENTITIES.files) ------------------------------------------------------------------------------


def _iso(t: dt.datetime | None) -> str | None:
    return t.isoformat() if t else None


def _url(row: dict[str, Any]) -> str | None:
    if row.get("url_encrypted") is None:
        return None
    return open_text("attachments", "url_encrypted", str(row["id"]), row["url_encrypted"])


def _shown_url(conn: Conn, row: dict[str, Any], raw: str | None) -> str:
    """A link's address for everyone but the person who added it: the whole address with its hidden details masked
    (the details `hide_name` stored for it), so the review desk can still try it."""
    from hide.core import details_for, layout

    if raw is None:
        return str(row["name"])
    details = details_for(conn, str(row["idea_uuid"]), "file", f"{row['id']}{hide_files.NAME_SUFFIX}")
    return layout(raw, details)[0]


def item_json(conn: Conn, row: dict[str, Any], *, uploader: bool, opens: bool) -> dict[str, Any]:
    """E-ENTITIES FileItem, plus `customer_detail` as lane B's rows carry it (DEC-107)."""
    from desk.store import person_by_code

    state = effective_state(row)
    kind = str(row.get("kind") or "file")
    out: dict[str, Any] = {
        "id": row["id"], "kind": kind, "name": row["name"],
        "type": "link" if kind == "link" else (row.get("mime") or "application/octet-stream"),
        "state": state, "added_by": person_by_code(conn, row.get("uploaded_by_code")).as_json(),
        "added_at": _iso(row.get("created_at")), "customer_detail": state == CUSTOMER_DETAIL,
    }  # fmt: skip
    if kind == "file":
        out["size"] = int(row["bytes"])
    if row.get("pages"):
        out["pages"] = int(row["pages"])
    if row.get("item_count") is not None:
        out["count"] = int(row["item_count"])
    if row.get("hidden_note"):
        out["hidden_note"] = row["hidden_note"]
    problem = problem_line(row, state, uploader=uploader)
    if problem:
        out["problem"] = problem
    if kind == "link":
        out["link_scope"] = row.get("link_scope")
        raw = _url(row)
        # the person who added it gets the address as typed; everyone else the same address with any customer's
        # detail in it masked. The row's name is its host and path (`link_name`).
        out["url"] = raw if uploader else _shown_url(conn, row, raw)
    if opens:
        out["view_url"] = f"/api/files/{row['id']}/view"
    return out


def problem_line(row: dict[str, Any], state: str, *, uploader: bool) -> str | None:
    """The FileItem's `problem` line; the draft read (`draft.store._files`) gives the same line (BLD-E076)."""
    if state == CUSTOMER_DETAIL:
        # C-FILE.row's found line is the uploader's, with Hide it for me and Remove file. The pack has no line for
        # the review desk's view of such a file: it reads `customer_detail` (a copy gap, not invented here).
        if not uploader:
            return None
        return hide_files.found_line(hide_files.FileFinds.from_codes((row.get("checks") or {}).get("found")))
    if state == CHECKING and (row.get("checks") or {}).get("waiting_for") == GATEKEEPER:
        return WAITING_LINE  # in place of an endless "Checking for personal details" (BLD-C225)
    if state == "upload_failed":
        return UPLOAD_FAILED
    if state == "too_big":
        return too_big_line(uploads().limit_mb)
    if state == "locked":
        return LOCKED
    return None


def get_item(conn: Conn, att_id: str, user_id: str) -> dict[str, Any]:
    """`GET /files/:id`: the FileItem, for the screens to follow the check. Anyone who may not see it: not found."""
    row = _load(conn, att_id)
    v, see, opens = _rights(conn, row, user_id)
    if not see:
        raise _not_found()
    return item_json(conn, row, uploader=v.uploader, opens=opens)


def items_for(
    conn: Conn, idea_uuid: str, user_id: str, *, answer_id: str | None = None
) -> list[dict[str, Any]]:
    """The files and links on an idea (or one answer) that this person may see, oldest first: for the draft and
    the edit page (S-05, S-06B), which list them in `Draft.files` and `Idea.files`."""
    sql = _ROW.replace(
        "WHERE a.id = %s",
        "WHERE a.idea_uuid = %s AND a.kind IN ('file', 'link') "
        "AND a.purpose = 'idea' AND a.conversation_entry_id IS NULL",  # never a conversation file (BLD-C216)
    )
    args: list[Any] = [idea_uuid]
    if answer_id is not None:
        sql += " AND a.answer_id = %s"
        args.append(answer_id)
    out = []
    for r in conn.execute(sql + " ORDER BY a.created_at, a.id", args).fetchall():
        row = dict(r)
        v, see, opens = _rights(conn, row, user_id)
        if see:
            out.append(item_json(conn, row, uploader=v.uploader, opens=opens))
    return out


# ---- adding a file or a link ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Owner:
    idea_uuid: str
    code: str
    user_id: str
    answer_id: str | None = None


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def purpose_of(given: str | None, *, idea_id: str | None) -> str:
    """`for` on `POST /files` (DEC-124, BLD-C216): absent, the file is the idea's own; "conversation" is the "+" in
    the conversation's box and needs `idea_id`. Any other value, or "conversation" without an idea: 422."""
    if given is None:
        return IDEA
    if given != CONVERSATION:
        raise FileRefused(422, "for_invalid", "", field="for")
    if not idea_id:
        raise FileRefused(422, "target_required", "", field="idea_id")
    return CONVERSATION


_IDEA_BY = {
    "id": "SELECT id AS idea_uuid FROM ideas WHERE id = %s",
    "idea_id": "SELECT id AS idea_uuid FROM ideas WHERE idea_id = %s",
    "answer": "SELECT s.idea_uuid FROM answers an JOIN questions q ON q.id = an.question_id "
    "JOIN question_sets s ON s.id = q.set_id WHERE an.id = %s",
}


def _hide_lock_first(conn: Conn, by: str, value: str) -> None:
    """L-HIDE's lock on the file's idea before any row lock (BLD-C067, BLD-C228): `accept` and `accept_link` reach
    hide (`hide_name`) after `_owner`'s row locks, and lane F's team-up and lane B's desk take hide's lock before the
    idea's or the answer's row. The idea's uuid is read with no lock; a row gone by the row lock answers as before."""
    row = conn.execute(_IDEA_BY[by], (value,)).fetchone()
    if row is not None:
        hide_core.lock(conn, str(row["idea_uuid"]))


def _conversation_owner(conn: Conn, user_id: str, code: str, idea_id: str) -> Owner:
    """A file for the conversation of a shared idea: only a reader lane F lets attach (`convo.access.reader`'s
    `may_attach`: the sharer, the review desk and the Ones Committee). Anyone who may not read the conversation, or
    may read it without attaching, finds nothing there (404, never 403), so the answer never says the idea exists;
    a withdrawn or merged idea, to someone who may attach, is closed (409)."""
    from convo import access
    from convo.store import Refused

    column = "idea_id" if str(idea_id).startswith("IDEA-") else "id"
    if column == "id" and not _is_uuid(idea_id):
        raise _not_found()
    _hide_lock_first(conn, column, idea_id)
    row = conn.execute(
        f"SELECT id, idea_id, contributor_code, status FROM ideas WHERE {column} = %s FOR UPDATE",  # noqa: S608 (fixed)
        (idea_id,),
    ).fetchone()
    if row is None or row["status"] == "draft":
        raise _not_found()  # a draft has no conversation
    idea = dict(row)
    try:
        reader = access.reader(conn, idea, user_id)
    except Refused:
        raise _not_found() from None
    if not reader.may_attach:
        raise _not_found()
    if idea["status"] in ("withdrawn", "merged"):
        raise FileRefused(409, "idea_closed", "")
    return Owner(str(idea["id"]), code, user_id)


def _owner(
    conn: Conn,
    user_id: str,
    *,
    draft_id: str | None,
    idea_id: str | None,
    answer_id: str | None,
    purpose: str = IDEA,
) -> Owner:
    """Where the file goes, and that this person may add it there (A-API.files: exactly one of the three).
    - a draft: its owner only;
    - a shared idea: a credited sharer (`own_codes`), while it is not withdrawn or merged;
    - a shared idea's conversation (`purpose` "conversation"): `_conversation_owner`;
    - an answer: the sharer whose draft answer it is, while the set is open and the answer not yet sent, as lane
      B's answer rules allow (`desk.asking.save_answer`); never wider. The idea is the answer's idea.
    Anyone else finds nothing there."""
    given = [x for x in (draft_id, idea_id, answer_id) if x]
    if len(given) != 1:
        raise FileRefused(422, "target_required", "", field="draft_id")
    if purpose == CONVERSATION and not idea_id:
        raise FileRefused(422, "target_required", "", field="idea_id")
    code = code_of(conn, user_id) if _is_uuid(user_id) else None
    if code is None:
        raise _not_found()
    if purpose == CONVERSATION:
        return _conversation_owner(conn, user_id, code, str(idea_id))
    if draft_id:
        if not _is_uuid(draft_id):
            raise _not_found()
        # Hide's lock first, keyed by the lower-case uuid as hide's own lock is (BLD-C228).
        hide_core.lock(conn, str(uuid.UUID(str(draft_id))))
        row = conn.execute(
            "SELECT id, contributor_code, status FROM ideas WHERE id = %s FOR UPDATE", (draft_id,)
        ).fetchone()
        if row is None or row["status"] != "draft" or row["contributor_code"] != code:
            raise _not_found()
        return Owner(str(row["id"]), code, user_id)
    if idea_id:
        column = "idea_id" if str(idea_id).startswith("IDEA-") else "id"
        if column == "id" and not _is_uuid(idea_id):
            raise _not_found()
        _hide_lock_first(conn, column, idea_id)
        row = conn.execute(
            f"SELECT id, contributor_code, status FROM ideas WHERE {column} = %s FOR UPDATE",  # noqa: S608 (fixed)
            (idea_id,),
        ).fetchone()
        if row is None:
            raise _not_found()
        idea = dict(row)
        mine = (
            code == idea["contributor_code"] if idea["status"] == "draft" else code in own_codes(conn, idea)
        )
        if not mine:
            raise _not_found()
        if idea["status"] in ("withdrawn", "merged"):
            raise FileRefused(409, "idea_closed", "")
        return Owner(str(idea["id"]), code, user_id)
    from desk.asking import ANSWER_IN_PROGRESS, CLOSED

    if not _is_uuid(answer_id):
        raise _not_found()
    _hide_lock_first(conn, "answer", str(answer_id))
    row = conn.execute(
        "SELECT an.id, an.by_code, an.sent_at, s.idea_uuid, s.state, i.contributor_code, i.status "
        "FROM answers an JOIN questions q ON q.id = an.question_id JOIN question_sets s ON s.id = q.set_id "
        "JOIN ideas i ON i.id = s.idea_uuid WHERE an.id = %s FOR UPDATE OF an",
        (answer_id,),
    ).fetchone()
    if row is None or row["state"] == "queued" or row["status"] == "draft":
        raise _not_found()
    if code not in own_codes(conn, {"id": row["idea_uuid"], "contributor_code": row["contributor_code"]}):
        raise _not_found()
    if row["state"] == "closed":
        raise FileRefused(409, "set_closed", CLOSED)
    if row["sent_at"] is not None:
        raise FileRefused(409, "answer_sent", "This answer is already with the review desk.")
    if row["by_code"] != code:
        raise FileRefused(409, "answer_in_progress", ANSWER_IN_PROGRESS)
    return Owner(str(row["idea_uuid"]), code, user_id, str(row["id"]))


def _clean_name(name: str) -> str:
    """The last part of the name the browser sent, without control characters, at most 200 characters."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = unicodedata.normalize("NFC", "".join(ch for ch in base if unicodedata.category(ch)[0] != "C"))
    base = re.sub(r"\s+", " ", base).strip()
    return base[:200] or "file"


def _next_id(conn: Conn) -> str:
    year = conn.execute("SELECT to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY') AS y").fetchone()["y"]  # type: ignore[index]
    n = conn.execute("SELECT next_number('ATT', %s) AS n", (year,)).fetchone()["n"]  # type: ignore[index]
    return f"ATT-{year}-{n:06d}"


def _key(att_id: str) -> str:
    """The object's key: the id and a random part, so a key never names an object an earlier database left in a
    shared store (dev and test stacks share one), and nothing can be guessed from it. Flat, under its own prefix:
    MinIO cannot put `att/<id>/…` while the old pipeline's `att/<id>` object exists."""
    return f"files/{att_id}-{uuid.uuid4().hex}"


def _audit(conn: Conn, user_id: str, action: str, idea_uuid: str, after: dict[str, Any]) -> None:
    """Every add, check, open, retry and removal (non-negotiable 9): IDs, states and kinds, never a name or value."""
    actor = f"user:{user_id}" if _is_uuid(user_id) else str(user_id)
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (actor, action, f"idea:{idea_uuid}", Jsonb(after)),
    )


def screen(data: bytes, name: str, cfg: Uploads) -> str:
    """The checks before anything is stored, from the bytes alone: the size, the magic numbers, and a locked Office
    file's marker. Nothing is unpacked or parsed before the virus scan (non-negotiable 8, L-HIDE.files/6). Returns
    the type, or `CONTAINER` for a file that starts as a ZIP: whether it is Word, PowerPoint, Excel or a plain ZIP,
    whether it has a password and what is inside are read after the scan. Pure, so each refusal has its own test."""
    if not data:
        raise FileRefused(400, "file_empty", UPLOAD_FAILED)
    if len(data) > cfg.limit_bytes:
        raise FileRefused(413, "too_big", too_big_line(cfg.limit_mb), limit_mb=cfg.limit_mb)
    if locked_before_scan(data):
        raise FileRefused(422, "locked", LOCKED)
    kind = kind_before_scan(data, name)
    allowed = any(t in cfg.types for t in CONTAINER_TYPES) if kind == CONTAINER else kind in cfg.types
    if kind is None or not allowed:
        raise FileRefused(415, "type_not_allowed", cfg.help_text)
    return kind


def _shown_mime(kind: str, name: str) -> str:
    """The type the row shows while the file is checked. A ZIP-family file's type is read from its directory after
    the scan, which replaces this; until then the name's extension picks among Word, PowerPoint, Excel and ZIP, for
    the row's badge only (nothing is opened or served by it)."""
    if kind != CONTAINER:
        return MIME[kind]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return MIME[ext if ext in CONTAINER_TYPES else "zip"]


def accept(
    conn: Conn,
    *,
    user_id: str,
    name: str,
    data: bytes,
    draft_id: str | None = None,
    idea_id: str | None = None,
    answer_id: str | None = None,
    purpose: str = IDEA,
) -> dict[str, Any]:
    """`POST /files`: store the bytes in quarantine and queue the checks. Returns the FileItem, `checking`. If the
    row cannot be written after the bytes are stored, the stored copy is deleted again (no orphan in the store).
    `purpose` "conversation" is a file for the idea's conversation (BLD-C216); its checks are the same (DEC-107)."""
    if purpose not in (IDEA, CONVERSATION):
        raise FileRefused(422, "for_invalid", "", field="for")
    cfg = uploads()
    kind = screen(data, name, cfg)
    s = get_settings()
    stored: str | None = None
    try:
        with conn.transaction():
            owner = _owner(
                conn, user_id, draft_id=draft_id, idea_id=idea_id, answer_id=answer_id, purpose=purpose
            )
            att_id = _next_id(conn)
            key = _key(att_id)
            clean_name = _clean_name(name)
            shown = hide_files.hide_name(conn, owner.idea_uuid, clean_name, by=user_id, att_id=att_id)
            try:
                store.put(s.s3_bucket_quarantine, key, data)
            except Exception:
                log.error("files.store_failed", attachment_id=att_id)
                raise FileRefused(502, "upload_failed", UPLOAD_FAILED) from None
            stored = key
            conn.execute(
                "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, uploaded_by_user, name, mime, bytes, "
                "sha256, store_key, state, kind, file_state, answer_id, checks, purpose) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'quarantine', 'file', %s, %s, %s, %s)",
                (att_id, owner.idea_uuid, owner.code, user_id, shown[:200], _shown_mime(kind, clean_name),
                 len(data), hashlib.sha256(data).hexdigest(), key, CHECKING, owner.answer_id,
                 Jsonb({"type": kind}), purpose),
            )  # fmt: skip
            conn.execute(
                "INSERT INTO jobs (type, payload, dedupe_key) VALUES (%s, %s, %s)",
                (JOB, Jsonb({"attachment_id": att_id}), f"{JOB}:{att_id}"),
            )
            _audit(conn, user_id, "file.added", owner.idea_uuid,
                   {"file_id": att_id, "type": kind, "answer_id": owner.answer_id, "purpose": purpose})  # fmt: skip
            row = _load(conn, att_id)
    except BaseException:
        if stored is not None:
            _delete_quietly(s.s3_bucket_quarantine, stored)
        raise
    log.info("files.added", attachment_id=att_id, file_type=kind, byte_count=len(data), purpose_code=purpose)
    return item_json(conn, row, uploader=True, opens=False)


# ---- links (BLD-E001) ---------------------------------------------------------------------------------------------

_HOST = re.compile(
    r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)
URL_MAX = 2000


def parse_link(text: str) -> tuple[str, str]:
    """(the address as stored, its host) or `not_a_link`. A link may be typed without https:// (V-FIELDS link/10:
    "intranet.kfintech.com/page"). Only http and https, a host with a dot, no spaces. Nothing is fetched."""
    raw = (text or "").strip()
    if not raw or len(raw) > URL_MAX or re.search(r"\s", raw):
        raise FileRefused(422, "not_a_link", NOT_A_LINK, field="url")
    url = raw if re.match(r"(?i)^[a-z][a-z0-9+.-]*://", raw) else f"https://{raw}"
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        parts.port  # noqa: B018 (a bad port raises here)
    except ValueError:
        raise FileRefused(422, "not_a_link", NOT_A_LINK, field="url") from None
    if (
        parts.scheme.lower() not in ("http", "https")
        or not _HOST.match(host)
        or parts.username
        or parts.password
    ):
        raise FileRefused(422, "not_a_link", NOT_A_LINK, field="url")
    return url, host


def link_name(shown: str, host: str) -> str:
    """The row's name for a link: its host and path, as the boards show it ("kfintech.sharepoint.com/ops/R07"), from
    the masked address. No scheme, query or fragment; the host in lower case; a bare "/" path left off."""
    rest = re.sub(r"(?i)^[a-z][a-z0-9+.-]*://", "", shown)
    rest = re.split(r"[?#]", rest, maxsplit=1)[0]
    head, slash, path = rest.partition("/")
    if head.lower().rstrip(".").split(":")[0] == host:
        head = head.lower()
    return head + (slash + path if path else "")


def link_scope(host: str, cfg: Uploads) -> str:
    """Internal when the host is one of the internal domains or under one (SharePoint, Teams, KFintech's own
    domains, the 1% Club); external otherwise. By the domain only (BLD-E001)."""
    host = host.lower().rstrip(".")
    for d in cfg.internal_domains:
        if host == d or host.endswith("." + d):
            return "internal"
    return "external"


def accept_link(
    conn: Conn,
    *,
    user_id: str,
    url: str,
    draft_id: str | None = None,
    idea_id: str | None = None,
    answer_id: str | None = None,
) -> dict[str, Any]:
    """`POST /links`: the address kept as typed (encrypted), never opened. Its row shows the masked copy."""
    cfg = uploads()
    address, host = parse_link(url)
    scope = link_scope(host, cfg)
    with conn.transaction():
        owner = _owner(conn, user_id, draft_id=draft_id, idea_id=idea_id, answer_id=answer_id)
        att_id = _next_id(conn)
        shown = hide_files.hide_name(conn, owner.idea_uuid, address, by=user_id, att_id=att_id)
        conn.execute(
            "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, uploaded_by_user, name, bytes, state, kind, "
            "file_state, link_scope, url_encrypted, answer_id) "
            "VALUES (%s, %s, %s, %s, %s, 0, 'quarantine', 'link', 'ok', %s, %s, %s)",
            (att_id, owner.idea_uuid, owner.code, user_id, link_name(shown, host)[:URL_MAX], scope,
             seal_text("attachments", "url_encrypted", att_id, address), owner.answer_id),
        )  # fmt: skip
        _audit(conn, user_id, "file.link_added", owner.idea_uuid,
               {"file_id": att_id, "link_scope": scope, "answer_id": owner.answer_id})  # fmt: skip
        row = _load(conn, att_id)
    log.info("files.link_added", attachment_id=att_id, link_scope=scope)
    return item_json(conn, row, uploader=True, opens=False)


# ---- the check (job `file.check`) -------------------------------------------------------------------------------


class CheckWaits(Exception):
    """The check cannot run yet (the scanner, OCR, the store or the gatekeeper is not answering): the job retries;
    after its last try the file is `upload_failed`, with Try again. The message is a reason code only, and `check`
    keeps it in `checks.waiting_for`. A gatekeeper that is switched off is not this: it is `JobWaits` (BLD-C225)."""


ENDS_COPY = ("not_checkable",)  # a failure Try again cannot change: the quarantine copy goes at once


def _delete_quietly(bucket: str, key: str | None) -> None:
    """Delete a stored object, never failing the caller: a link has no key, and a copy already gone is fine."""
    if not key:
        return
    try:
        store.delete(bucket, key)
    except Exception:
        log.warning("files.store_delete_failed")


def _finish(conn: Conn, row: dict[str, Any], state: str, code: str) -> str:
    """A check that ended without a stored copy to open. An infected, locked or too-big file's quarantine copy is
    deleted at once; a failed one is kept so Try again can run the checks again, unless nothing could change."""
    s = get_settings()
    with conn.transaction():
        live = conn.execute(
            "SELECT file_state FROM attachments WHERE id = %s FOR UPDATE", (row["id"],)
        ).fetchone()
        if live is None or live["file_state"] != CHECKING:
            return str(live["file_state"]) if live else "missing"
        if (state != "upload_failed" or code in ENDS_COPY) and row.get("store_key"):
            store.delete(s.s3_bucket_quarantine, row["store_key"])
        # A file that gave up (`check_failed`) keeps the wait it died of, or "none": so every such row from this
        # build has `waiting_for`, and only r3's rows lack it (`start_sweep`, BLD-C227). Any other end drops it.
        conn.execute(
            "UPDATE attachments SET file_state = %s, state = %s, updated_at = now(), "
            "checks = (CASE WHEN %s THEN coalesce(checks, '{}'::jsonb) || jsonb_build_object('waiting_for', "
            "coalesce(checks->>'waiting_for', %s::text)) ELSE coalesce(checks, '{}'::jsonb) - 'waiting_for' END) "
            "|| jsonb_build_object('result', %s::text, 'ended_at', now()) WHERE id = %s",
            (state, old_state(state), code == "check_failed", NO_WAIT, code, row["id"]),
        )
        _audit(conn, "system:files", "file.checked", str(row["idea_uuid"]),
               {"file_id": row["id"], "state": state, "result": code})  # fmt: skip
    log.info("files.checked", attachment_id=row["id"], file_state=state, reason_code=code)
    return state


def _extract(kind: str, data: bytes, types: tuple[str, ...]) -> Extracted:
    """The file's structure and text, in the sandbox, after the scan. A ZIP-family file (`CONTAINER`) is read there
    as what its directory says it is, within the configured types; `got.kind` is that type."""
    if kind == CONTAINER:
        return sandbox.extract("container", data, options={"types": list(types)})
    ocr = kind in ("png", "jpg")
    extractor = f"{kind}_ocr" if ocr else kind
    got = sandbox.extract(extractor, data, timeout_s=OCR_TIMEOUT_S if ocr else 90.0)
    if got.scanned:  # a PDF with a page that has no text layer: read those pages by OCR
        pages = got.pages
        got = sandbox.extract("pdf_ocr", data, timeout_s=OCR_TIMEOUT_S)
        got.pages = got.pages or pages
    got.kind = kind
    return got


def gatekeeper_on(conn: Conn) -> bool:
    """`ai.all` and `agent.gatekeeper` both on, read from the table past the 10-second cache, so a switch-on is
    seen at once here and by the gateway after it (the cache is refilled from this read)."""
    from core import killswitch

    killswitch.clear_cache()
    return all(killswitch.is_on(name, conn) for name in hide_files.GATEKEEPER_SWITCHES)


def _note_wait(conn: Conn, att_id: str, reason: str) -> None:
    """Keep why the check waits (`checks.waiting_for`) on a file still checking. Its own statement on the runner's
    autocommit connection: no transaction here reaches hide, so hide's lock order is untouched (BLD-C228)."""
    conn.execute(
        "UPDATE attachments SET checks = coalesce(checks, '{}'::jsonb) || jsonb_build_object('waiting_for', %s::text) "
        "WHERE id = %s AND file_state = %s",
        (reason, att_id, CHECKING),
    )


def _gatekeeper_wait(conn: Conn, att_id: str) -> JobWaits:
    """The file waits for the gatekeeper (BLD-C225): it stays checking, its row reads `WAITING_LINE`, and the job
    runs again after the step without using a try. Never a skip of the gatekeeper (non-negotiable 4)."""
    _note_wait(conn, att_id, GATEKEEPER)
    return JobWaits(WAIT_STEP_S, WAITING_GATEKEEPER)


def check(conn: Conn, att_id: str) -> str:
    """Virus scan, then the file's structure and text layer in the sandbox, then the gatekeeper and hide's
    detection (L-HIDE.files/1, /6). Returns the new state. Raises `JobWaits` while the gatekeeper is switched off
    (BLD-C225) and `CheckWaits` while a service it needs is down, its reason kept in `checks.waiting_for`.
    A job for a file that is gone, or no longer checking, changes nothing."""
    try:
        return _check(conn, att_id)
    except CheckWaits as wait:
        _note_wait(conn, att_id, str(wait))
        raise


def _check(conn: Conn, att_id: str) -> str:
    s = get_settings()
    found = conn.execute(
        "SELECT id, idea_uuid, store_key, file_state, uploaded_by_user, uploaded_by_code, checks "
        "FROM attachments WHERE id = %s AND kind = 'file'",
        (att_id,),
    ).fetchone()
    if found is None or found["file_state"] != CHECKING:
        return str(found["file_state"]) if found else "missing"
    row = dict(found)
    # First, before the virus scan: while the gatekeeper is switched off the file waits, and no scan is repeated.
    if not gatekeeper_on(conn):
        raise _gatekeeper_wait(conn, att_id)
    if (row.get("checks") or {}).get("waiting_for"):  # it runs now: the row no longer says it waits
        conn.execute(
            "UPDATE attachments SET checks = checks - 'waiting_for' WHERE id = %s AND file_state = %s",
            (att_id, CHECKING),
        )
    if not row.get("store_key"):
        return _finish(conn, row, "upload_failed", "no_copy")
    try:
        data = store.get(s.s3_bucket_quarantine, row["store_key"])
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return _finish(conn, row, "upload_failed", "no_copy")
        raise CheckWaits("store") from None
    try:
        verdict = clamav.scan_bytes(data)
    except clamav.ScannerUnavailable:
        raise CheckWaits("scanner") from None
    if not verdict.clean:
        return _finish(conn, row, "infected", "virus")
    kind = str((row.get("checks") or {}).get("type") or kind_before_scan(data) or "")
    try:
        got = _extract(kind, data, uploads().types)
    except sandbox.ExtractionFailed as exc:
        if exc.code == "ocr_unavailable":
            raise CheckWaits("ocr") from None
        state = {"locked": "locked", "too_big": "too_big"}.get(exc.code, "upload_failed")
        return _finish(conn, row, state, exc.code)
    real = got.kind if got.kind in MIME else kind
    by = str(row["uploaded_by_user"] or "") or None
    if by is None:
        from desk.store import user_of

        by = user_of(conn, row["uploaded_by_code"]) or "system:files"
    # The gatekeeper reads the text before the file's row is locked, so Remove and Try again never wait on a model
    # (BLD-C107). It cannot run: the file stays checking (non-negotiable 4, DEC-103). Switched off meanwhile, or the
    # day's budget spent: it waits without using a try (BLD-C225). The gateway failing: a try, as before.
    try:
        gate = hide_files.gate_for(conn, str(row["idea_uuid"]), hide_files.text_of(got.pieces))
    except hide_files.GatekeeperWaits as exc:
        if str(exc) in ASSISTANT_OFF:
            raise _gatekeeper_wait(conn, att_id) from None
        raise CheckWaits(GATEKEEPER) from None
    with conn.transaction():
        # L-HIDE's lock before the file's row (BLD-C067, BLD-C228): `hide_file` takes it next. The gatekeeper has
        # already run above, so nothing waits on a model under it.
        hide_core.lock(conn, str(row["idea_uuid"]))
        live = conn.execute(
            "SELECT file_state FROM attachments WHERE id = %s FOR UPDATE", (att_id,)
        ).fetchone()
        if live is None or live["file_state"] != CHECKING:  # removed, or checked by another run, meanwhile
            return str(live["file_state"]) if live else "missing"
        finds = hide_files.hide_file(conn, str(row["idea_uuid"]), got.pieces, by=by, att_id=att_id, gate=gate)
        state = CUSTOMER_DETAIL if finds.count else "checked"
        store.put(s.s3_bucket_clean, row["store_key"], data)
        store.delete(s.s3_bucket_quarantine, row["store_key"])
        # No hidden note: nothing is blacked out until "Hide it for me" (DEC-107); the found line is the problem.
        conn.execute(
            "UPDATE attachments SET file_state = %s, state = %s, pages = %s, mime = %s, hidden_note = NULL, "
            "checks = (coalesce(checks, '{}'::jsonb) - 'waiting_for') || %s, updated_at = now() WHERE id = %s",
            (state, old_state(state), got.pages, MIME.get(real, "application/octet-stream"),
             Jsonb({"type": real, "result": "found" if finds.count else "clean", "found": finds.codes(),
                    "gatekeeper": "ran",  # always: a file never skips it (BLD-C107)
                    "ocr": real in ("png", "jpg") or any("(scanned)" in w for w, _ in got.pieces)}),
             att_id),
        )  # fmt: skip
        _audit(conn, "system:files", "file.checked", str(row["idea_uuid"]),
               {"file_id": att_id, "state": state, "kinds": finds.kinds, "count": finds.count,
                "gatekeeper": "ran"})  # fmt: skip
    log.info("files.checked", attachment_id=att_id, file_state=state, hidden_count=finds.count)
    return state


def gave_up(conn: Conn, att_id: str) -> None:
    """The checks could not finish after every retry: the file is `upload_failed`, with Try again."""
    row = conn.execute(
        "SELECT id, idea_uuid, store_key, file_state FROM attachments WHERE id = %s", (att_id,)
    ).fetchone()
    if row is not None and row["file_state"] == CHECKING:
        _finish(conn, dict(row), "upload_failed", "check_failed")


# ---- waiting for the gatekeeper: the switch-on re-queue and the worker-start sweep (BLD-C226, BLD-C227) ----------


def requeue_waiting(conn: Conn, batch: int = BATCH) -> int:
    """On every tick of the ticker's watch (about every 60 s) while `ai.all` and `agent.gatekeeper` are both on:
    the file checks waiting for the gatekeeper are made due now, `batch` jobs per commit, the switches read again
    before each batch, stopping if they go off (BLD-C226). It covers a switch-on from the Admin page, which the
    worker's own set path never sees, and a worker started with the assistant on. Nothing is checked here: the job
    runner runs each check, from the virus scan. Logs carry a count only. Returns how many."""
    moved = 0
    while gatekeeper_on(conn):
        with conn.transaction():
            # The batch is picked once (a MATERIALIZED CTE), so a commit moves at most `batch` jobs. An
            # `IN (SELECT … LIMIT n FOR UPDATE SKIP LOCKED)` can be rescanned per row, and a rescan skips the rows this
            # same UPDATE has just changed and takes the next ones (BLD-C238).
            n = conn.execute(
                "WITH due AS MATERIALIZED (SELECT id FROM jobs WHERE type = %s AND state = 'queued' "
                "AND last_error = %s AND run_at > now() ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED) "
                "UPDATE jobs SET run_at = now() FROM due WHERE jobs.id = due.id",
                (JOB, WAITING_GATEKEEPER, batch),
            ).rowcount
        moved += n
        if n < batch:
            break
    if moved:
        log.info("files.waiting_requeued", job_count=moved)
    return moved


def reset_r3_waits(conn: Conn) -> int:
    """r3 counted each wait as a try: its file checks still queued after a wait (`last_error` "CheckWaits") get
    their tries back and wait for the gatekeeper (BLD-C227). Run by `start_sweep`, not in its count. Returns how
    many; logs `jobs.waits_reset` with the count only."""
    n = 0
    while True:
        with conn.transaction():
            done = conn.execute(  # the batch picked once, as `requeue_waiting` does (BLD-C238)
                "WITH due AS MATERIALIZED (SELECT id FROM jobs WHERE type = %s AND state = 'queued' "
                "AND last_error = 'CheckWaits' ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED) "
                "UPDATE jobs SET attempts = 0, last_error = %s FROM due WHERE jobs.id = due.id",
                (JOB, BATCH, WAITING_GATEKEEPER),
            ).rowcount
        n += done
        if done < BATCH:
            break
    jobs_log.info("jobs.waits_reset", job_count=n)
    return n


# THE EXACT RULE (lane A, from r3's `check`, `gave_up` and `_finish`): a row r3 let die of its waits. r3 never kept
# the scan's verdict on a waiting row, so none is asked for: the whole check runs again, from the virus scan, and
# nothing opens until it passes (non-negotiable 8). A row from this build always has `waiting_for` once it gave up,
# so it is never moved: real failures are not retried on every restart.
_R3_DEAD = (
    "SELECT a.id, a.idea_uuid, a.store_key FROM attachments a JOIN ideas i ON i.id = a.idea_uuid "
    "WHERE a.kind = 'file' AND a.id > %s "
    "AND i.status NOT IN ('withdrawn', 'merged') AND i.merged_into IS NULL "  # a
    "AND a.file_state = 'upload_failed' "  # b
    "AND a.checks->>'result' = 'check_failed' AND NOT a.checks ? 'gatekeeper' "  # c
    "AND NOT a.checks ? 'waiting_for' "  # c: never a row from this build
    "AND a.masked_store_key IS NULL "  # d
    "AND NOT EXISTS (SELECT 1 FROM hidden_details h WHERE h.source = 'file' AND h.source_id = a.id) "  # d
    "AND a.store_key IS NOT NULL AND coalesce(a.checks->>'copy', '') <> 'gone' "  # e
    "ORDER BY a.id LIMIT %s FOR UPDATE OF a SKIP LOCKED"
)


def _in_store(s3: Any, bucket: str, key: str) -> bool:
    """Whether the object is there. Only a clear "not there" is False; any other error stops the sweep."""
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
            return False
        raise


def _bring_back(conn: Conn, s3: Any, after_id: str) -> tuple[int, str | None]:
    """One batch of `_R3_DEAD`, in one transaction: each row whose quarantine copy is there (e) and that was never
    moved to the clean bucket (d) goes back to checking, waiting for the gatekeeper, with its result cleared, a
    fresh check job at 0 tries and one `file.check_requeued` audit row. Returns (moved, the last id read)."""
    s = get_settings()
    moved, last = 0, None
    with conn.transaction():
        rows = conn.execute(_R3_DEAD, (after_id, BATCH)).fetchall()
        for r in rows:
            last = str(r["id"])
            key = str(r["store_key"])
            if not _in_store(s3, s.s3_bucket_quarantine, key) or _in_store(s3, s.s3_bucket_clean, key):
                continue
            conn.execute(
                "UPDATE attachments SET file_state = %s, state = %s, updated_at = now(), "
                "checks = (checks - 'result' - 'ended_at') || jsonb_build_object('waiting_for', %s::text) "
                "WHERE id = %s",
                (CHECKING, old_state(CHECKING), GATEKEEPER, last),
            )
            conn.execute(
                "INSERT INTO jobs (type, payload, attempts, run_at, last_error) "
                "SELECT %s, %s, 0, now() + make_interval(secs => %s), %s WHERE NOT EXISTS (SELECT 1 FROM jobs "
                "WHERE type = %s AND state IN ('queued', 'running') AND payload->>'attachment_id' = %s)",
                (JOB, Jsonb({"attachment_id": last}), WAIT_STEP_S, WAITING_GATEKEEPER, JOB, last),
            )
            _audit(conn, SYSTEM, "file.check_requeued", str(r["idea_uuid"]),
                   {"file_id": last, "from": "upload_failed", "to": CHECKING})  # fmt: skip
            moved += 1
    return moved, last


def start_sweep(conn: Conn) -> int:
    """At worker start, whatever the switches say, before any job is taken (BLD-C227): r3's file checks still
    queued get their tries back (`reset_r3_waits`), and every row that fits THE EXACT RULE goes back to waiting for
    the gatekeeper, `BATCH` rows per commit. It checks nothing and opens nothing to anyone, so non-negotiable 4 is
    unchanged, and it is idempotent: a row moved is checking, so it is never read again. Then one `files.start_sweep`
    line (its only field `count`) and one `file.start_sweep` audit row, `after` {"count", "complete"}, which lane A's
    upgrade reads to print "file checks: N files back to waiting for the personal-data check (none opened)". A
    failure part-way logs `files.start_sweep_failed` (`count`, `error_type`) and still writes the audit row, with
    `complete` false. Returns the count. A separate step: if the lead picks "leave them failed", only this goes."""
    count, complete = 0, True
    try:
        reset_r3_waits(conn)
        s3 = store.client()
        after = ""
        while True:
            moved, last = _bring_back(conn, s3, after)
            count += moved
            if last is None:
                break
            after = last
    except Exception as exc:
        complete = False
        log.error("files.start_sweep_failed", count=count, error_type=type(exc).__name__)
    try:
        with conn.transaction():
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'file.start_sweep', %s, %s)",
                (SYSTEM, "files:start_sweep", Jsonb({"count": count, "complete": complete})),
            )
    except Exception as exc:
        complete = False
        log.error("files.start_sweep_failed", count=count, error_type=type(exc).__name__)
    if complete:
        log.info("files.start_sweep", count=count)
    return count


# ---- opening, retrying, removing --------------------------------------------------------------------------------


def content(conn: Conn, att_id: str, user_id: str) -> tuple[bytes, str, str]:
    """`GET /files/:id/view`: the stored copy, to the people `rights` allows, once the checks have passed: the
    blacked-out copy when there is one. Every opening is audited."""
    row = _load(conn, att_id)
    _, see, opens = _rights(conn, row, user_id)
    if not see:
        raise _not_found()
    if not opens:
        raise FileRefused(403, "not_available", "")
    key = row.get("masked_store_key") or row["store_key"]
    data = store.get(get_settings().s3_bucket_clean, key)
    _audit(conn, user_id, "file.opened", str(row["idea_uuid"]),
           {"file_id": att_id, "state": effective_state(row)})  # fmt: skip
    return data, str(row.get("mime") or "application/octet-stream"), str(row["name"])


def _own_row(conn: Conn, att_id: str, user_id: str) -> dict[str, Any]:
    row = _load(conn, att_id, lock=True)
    v, see, _ = _rights(conn, row, user_id)
    if not see:
        raise _not_found()
    if not v.uploader:
        raise FileRefused(403, "forbidden", ONLY_YOURS)
    return row


def retry(conn: Conn, att_id: str, user_id: str) -> dict[str, Any]:
    """`POST /files/:id/retry` ("Try again" on a failed upload): the checks run again on the kept copy."""
    s = get_settings()
    with conn.transaction():
        row = _own_row(conn, att_id, user_id)
        if row["kind"] != "file" or effective_state(row) != "upload_failed":
            raise FileRefused(409, "not_failed", "")
        if not store.exists(s.s3_bucket_quarantine, row["store_key"]):
            raise FileRefused(409, "upload_again", UPLOAD_FAILED)
        conn.execute(
            "UPDATE attachments SET file_state = %s, state = 'quarantine', updated_at = now() WHERE id = %s",
            (CHECKING, att_id),
        )
        conn.execute(
            "INSERT INTO jobs (type, payload) VALUES (%s, %s)", (JOB, Jsonb({"attachment_id": att_id}))
        )
        _audit(conn, user_id, "file.retried", str(row["idea_uuid"]), {"file_id": att_id})
        row = _load(conn, att_id)
    log.info("files.retried", attachment_id=att_id)
    return item_json(conn, row, uploader=True, opens=False)


def remove(conn: Conn, att_id: str, user_id: str) -> None:
    """`DELETE /files/:id` ("Remove", "Remove file"): every stored copy, the row and its hidden details go. Only the
    person who added it; it works in any state, after an answer is sent too (DEC-107: the desk may ask for it)."""
    with conn.transaction():
        row = _own_row(conn, att_id, user_id)
        drop(conn, row)
        _audit(conn, user_id, "file.removed", str(row["idea_uuid"]),
               {"file_id": att_id, "state": effective_state(row), "kind": row["kind"]})  # fmt: skip
    log.info("files.removed", attachment_id=att_id)


def drop(conn: Conn, row: dict[str, Any]) -> None:
    """Every stored copy of a file, its hidden details, its queued checks and its row, in the caller's transaction
    holding the row's lock. A link has no stored copy. Used by Remove, the old remove route and the draft purge."""
    s = get_settings()
    for bucket, key in (
        (s.s3_bucket_quarantine, row.get("store_key")),
        (s.s3_bucket_clean, row.get("store_key")),
        (s.s3_bucket_quarantine, row.get("masked_store_key")),
        (s.s3_bucket_clean, row.get("masked_store_key")),
    ):
        if key:
            store.delete(bucket, key)
    hide_files.forget(conn, str(row["id"]))
    # Its checks still waiting go too, so a job runner never picks up work for a file that is gone.
    conn.execute(
        "DELETE FROM jobs WHERE type = %s AND state = 'queued' AND payload->>'attachment_id' = %s",
        (JOB, str(row["id"])),
    )
    conn.execute("DELETE FROM attachments WHERE id = %s", (row["id"],))


def sweep_failed_copies(conn: Conn) -> int:
    """The attachments sweep (run with the draft purge, `jobs.handlers.purge_drafts`). The quarantine copy of a file
    that stayed `upload_failed` past the retention period (`rules/thresholds.md`
    `attachments.rejected_retention_hours`) is deleted; Try again then asks for the file again. And a file added for
    the conversation that never went on an entry is removed, every stored copy and its row, a day after it was added
    (`sweep_unsent_conversation`, BLD-C216). Returns how many of both."""
    return _sweep_failed(conn) + sweep_unsent_conversation(conn)


def sweep_unsent_conversation(conn: Conn, hours: int = UNSENT_CONVERSATION_HOURS) -> int:
    """Conversation files (`purpose` "conversation") still not on an entry `hours` after they were added: each is
    locked, checked again and dropped (`drop`: every stored copy, its hidden details, its queued checks, its row).
    Logs and the audit carry IDs only. Returns how many."""
    due = conn.execute(
        "SELECT id FROM attachments WHERE purpose = 'conversation' AND conversation_entry_id IS NULL "
        "AND created_at < now() - make_interval(hours => %s) ORDER BY created_at",
        (hours,),
    ).fetchall()
    removed = 0
    for d in due:
        with conn.transaction():
            row = conn.execute(
                "SELECT * FROM attachments WHERE id = %s AND purpose = 'conversation' "
                "AND conversation_entry_id IS NULL AND created_at < now() - make_interval(hours => %s) "
                "FOR UPDATE SKIP LOCKED",
                (d["id"], hours),
            ).fetchone()
            if row is None:
                continue  # sent on an entry meanwhile, or another sweep has it
            drop(conn, dict(row))
            _audit(conn, "system:files", "file.swept", str(row["idea_uuid"]),
                   {"file_id": str(row["id"]), "purpose": CONVERSATION})  # fmt: skip
            removed += 1
        log.info("files.swept_unsent", attachment_id=str(d["id"]))
    return removed


def _sweep_failed(conn: Conn) -> int:
    """The failed uploads' quarantine copies past their retention period (see `sweep_failed_copies`)."""
    from rules import load_rule

    try:
        hours = int(
            load_rule(Path(get_settings().company_repo_path), "thresholds").data["attachments"][
                "rejected_retention_hours"
            ]
        )
    except Exception:  # an unreadable rules file keeps the configured default
        hours = 24
    s = get_settings()
    rows = conn.execute(
        "SELECT id, store_key FROM attachments WHERE kind = 'file' AND file_state = 'upload_failed' "
        "AND store_key IS NOT NULL AND (checks->>'ended_at')::timestamptz < now() - make_interval(hours => %s) "
        "AND coalesce(checks->>'copy', '') <> 'gone'",
        (hours,),
    ).fetchall()
    for r in rows:
        _delete_quietly(s.s3_bucket_quarantine, r["store_key"])
        conn.execute(
            "UPDATE attachments SET checks = coalesce(checks, '{}'::jsonb) || '{\"copy\": \"gone\"}'::jsonb "
            "WHERE id = %s",
            (r["id"],),
        )
    return len(rows)


def hide_for_me(conn: Conn, att_id: str, user_id: str) -> dict[str, Any]:
    """`POST /files/:id/hide` ("Hide it for me", L-HIDE.files/3). Black-out is not built (DEC-107, BLD-C064): the
    web route answers `not_available` while `files.blackout` is off, and this answers the same while it is on."""
    with conn.transaction():
        _own_row(conn, att_id, user_id)
    raise FileRefused(503, "not_available", "")
