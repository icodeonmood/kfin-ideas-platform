"""L-SUBMIT.edit: changing a shared idea in the edit window (S-06B).

1. Open until the review desk opens the idea, at the latest `edit_closes_at` (3 days after sharing), whichever comes
   first; a question set already sent closes it too (the desk has started on it). Save is refused once it closes:
   "The review desk has just opened it, so it can’t be changed now. …" with when it was opened (`/5`, V-FIELDS/15).
2. One page, nothing changes for anyone until Save (`/2`): `GET` gives the page, `PATCH` saves any of title,
   summary, how often, sorting, fix and who would help, and records the files the page added or removed. After Save: "Saved. The review desk will see the latest
   version."
3. Each save re-runs hidden-detail detection on the new text before it is stored (DEC-103: the masked copy is what
   is kept; the words as typed are sealed for the sharer alone), and similar-idea matching when the summary changed
   (`/3`). Text sent back exactly as its stored masked copy is unchanged: it is not masked again, so a repeat Save
   writes no hidden-detail or sealed rows (BLD-C141).
4. Each save is a version (`/4`): `idea_versions` holds the changed fields and, sealed, each one's value before and
   after, so the review desk can see what changed. The idea as shared is version 1; the first save is version 2.
   Files and links go in, or out, at once (each is checked as it lands), and the page tells Save which it added or
   removed since it was loaded, so the version records them as `files` (BLD-C161).
5. Empty optional parts carry a prompt with the closing date (`/6`).

A save is the sharer's action on their idea: `audit_log` gets it with the version and the field names only.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from core.crypto import CryptoError, decrypt_json, encrypt_json
from core.db import Conn
from hide.core import detail_view
from onepc.context import sealed_context
from similar.preview import DESK_ROLES
from submit import adapters, config, fix, helpers, own, ready, sorting
from submit.errors import NotFound, Refused
from submit.words import clock, countdown, day, join

TEXT_LIMITS = {"title": 70, "summary": 2000, "often": 200}
OPEN_SET_STATES = ("sent", "seen", "partly_answered", "answered", "closed")
SAVED = "Saved. The review desk will see the latest version."
FIELD_WORDS = {
    "title": "Title",
    "summary": "What happens",
    "often": "How often",
    "sorting": "Sorting",
    "fix": "Your fix",
    "helpers": "Who would help",
    "files": "Files",
}
ATT_ID = re.compile(r"^ATT-[0-9]{4}-[0-9]{6}$")
FILES_MAX = 100
# The review desk and the Ones Committee, as `similar.preview` and lane B's desk read them (DEC-104): E-ENUMS.roles
# `reviewer` and `committee`, and the committee's older `core_committee` and `core_chair` until lane E retires them.
STAFF_ROLES = DESK_ROLES


def window(conn: Conn, idea: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    """`Idea.edit_window`: open, when it closes, and when the desk opened it."""
    closes = idea.get("edit_closes_at")
    opened = idea.get("opened_at")
    asked = conn.execute(
        "SELECT 1 FROM question_sets WHERE idea_uuid = %s AND state = ANY(%s) LIMIT 1",
        (idea["id"], list(OPEN_SET_STATES)),
    ).fetchone()
    is_open = (
        idea["status"] in ("checking", "with_review_desk")
        and opened is None
        and asked is None
        and closes is not None
        and now < closes
    )
    out: dict[str, Any] = {"open": is_open}
    if closes is not None:
        out["closes_at"] = closes.isoformat()
    if opened is not None:
        out["opened_by_desk_at"] = opened.isoformat()
    if is_open and closes is not None:
        out["countdown"] = countdown(closes, now)
    elif opened is not None:
        out["line"] = (
            f"The review desk opened it on {day(opened, now)}, so the idea itself can’t be changed now. "
            "Write to them in the conversation."
        )
    elif not is_open:
        # NOT DRAWN: the window ran out, or questions came, before the desk opened it; or the idea has moved on
        # without the desk opening it (decided, withdrawn, merged, shipped) and was reached by its address. A closed
        # window always has a line, so the page never shows an empty status.
        out["line"] = (
            "The time for changes has ended, so the idea itself can’t be changed now. Write to the review desk in "
            "the conversation."
        )
    return out


def _closed(idea: dict[str, Any], w: dict[str, Any]) -> Refused:
    if idea.get("opened_at") is not None:
        return Refused(
            409,
            "edit_window_closed",
            "The review desk has just opened it, so it can’t be changed now. Your changes are kept below. Send them "
            "as a message instead.",
            opened_by_desk_at=w.get("opened_by_desk_at"),
            to=f"/ideas/{idea['idea_id']}/conversation",
        )
    return Refused(
        409,
        "edit_window_closed",
        "The time for changes has ended, so it can’t be changed now. Your changes are kept below. Send them as a "
        "message instead.",
        to=f"/ideas/{idea['idea_id']}/conversation",
    )


def _fix(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    """The included fix as E-ENTITIES `Fix` (`submit.fix.view`), or None."""
    return fix.view(conn, idea_uuid)


def _files(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, kind, name, file_state, state, hidden_note, link_scope FROM attachments WHERE idea_uuid = %s "
        "AND parent_id IS NULL AND answer_id IS NULL AND purpose = 'idea' AND conversation_entry_id IS NULL "
        "AND state <> 'rejected' ORDER BY created_at",
        (idea_uuid,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "name": r["name"],
            "state": r["file_state"] or ("checked" if r["state"] == "clean" else "checking"),
            **({"hidden_note": r["hidden_note"]} if r["hidden_note"] else {}),
            **({"link_scope": r["link_scope"]} if r["link_scope"] else {}),
        }
        for r in rows
    ]


def _times(n: int) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n} times")


def versions_summary(conn: Conn, idea: dict[str, Any]) -> dict[str, Any]:
    """`Idea.versions`: "3 versions. Title changed once, sorting confirmed." The idea as shared is the first."""
    row = conn.execute(
        "SELECT count(*) AS n, count(*) FILTER (WHERE 'title' = ANY(changed_fields)) AS titles FROM idea_versions "
        "WHERE idea_uuid = %s",
        (idea["id"],),
    ).fetchone()
    saves = int(row["n"]) if row else 0
    titles = int(row["titles"]) if row else 0
    count = saves + 1
    bits = [f"{count} version{'s' * (count != 1)}."]
    confirmed = idea.get("sorting_confirmed_at") is not None
    if titles:
        bits.append(f"Title changed {_times(titles)}" + (", sorting confirmed." if confirmed else "."))
    elif confirmed:
        bits.append("Sorting confirmed.")
    return {"count": count, "summary": " ".join(bits)}


def page(conn: Conn, key: str, user_id: str, *, now: dt.datetime) -> dict[str, Any]:
    """`GET /ideas/:id/edit`: everything S-06B shows, for the sharer only."""
    idea, _code = own.load_own(conn, key, user_id)
    if idea["status"] == "draft" or idea["idea_id"] is None:
        raise NotFound
    uid = str(idea["id"])
    ref = str(idea["idea_id"])
    w = window(conn, idea, now)
    closes = idea.get("edit_closes_at")
    decide = idea.get("decide_by")
    shared = idea["shared_at"]
    fix = _fix(conn, uid)
    files = _files(conn, uid)
    until = day(closes, now) if closes else None
    hidden = conn.execute(
        "SELECT id, kind, masked, state, reason, shown_at FROM hidden_details WHERE idea_uuid = %s "
        "AND source NOT IN ('file', 'teamup') ORDER BY created_at",
        (uid,),
    ).fetchall()
    return {
        "screen": "S-06B",
        "id": uid,
        "ref": ref,
        "status": idea["status"],
        "kind": sorting.kind_on_check_it(idea.get("kind")) or "problem",
        "bar": {
            "title": f"Edit {ref}",
            "line": (
                f"Shared {day(shared, now)}. You can edit until the review desk opens it, at the latest {until}."
                if until
                else f"Shared {day(shared, now)}."
            ),
            "back": {"label": "Back to your idea", "to": f"/ideas/{ref}"},
        },
        "window": w,
        "fields": {
            "title": idea.get("title") or "",
            "summary": idea.get("summary") or "",
            "often": idea.get("often"),
        },
        # E-ENTITIES HiddenDetail as "Show it" answers it (hide.core.detail_view): a shown row keeps its reason, so
        # C-HIDDEN.list/3's "Shown, because …" reads on S-06B as on S-05 (BLD-C189)
        "hidden": [detail_view(dict(h)) for h in hidden],
        "sorting": sorting.view(conn, idea, phase="edit"),
        "fix": fix,
        "helpers": helpers.view(idea),
        "files": files,
        "prompts": {
            **(
                {"fix": f"No fix added. Add one until {until}"} if fix is None and until and w["open"] else {}
            ),
            **(
                {"files": f"Nothing attached. Add one until {until}"}
                if not files and until and w["open"]
                else {}
            ),
        },
        "side": [
            {
                "when": "Straight away",
                "line": "The review desk sees the latest version. Earlier versions are kept on the timeline.",
            },
            *(
                [
                    {
                        "when": f"At the latest {until}",
                        "line": "Editing closes when the review desk opens it. After that, you can add a note for "
                        "them instead.",
                    }
                ]
                if until
                else []
            ),
            *(
                [{"when": f"By {day(decide, now)}", "line": "The review desk decides, and tells you why."}]
                if decide
                else []
            ),
        ],
        "declaration": {"version": config.DECLARATION_VERSION, "text": config.DECLARATION["save"]},
        "versions": versions_summary(conn, idea),
        **({"saved_label": f"Saved at {clock(idea['saved_at'])}"} if idea.get("saved_at") else {}),
    }


# --- Save --------------------------------------------------------------------------------------------------------


class _Save:
    """One save's working state: the masked values, what was hidden, and each changed field before and after."""

    def __init__(self, conn: Conn, idea: dict[str, Any], user_id: str, n: int) -> None:
        self.conn, self.idea, self.user_id, self.n = conn, idea, user_id, n
        self.uid = str(idea["id"])
        self.before: dict[str, Any] = {}
        self.after: dict[str, Any] = {}

    def mask(self, field: str, text: str, stored: str | None = None) -> str:
        """The masked copy of the person's new words for one field. Hide stores each value, its `hidden_details` row
        and the words as typed, sealed for the sharer alone (DEC-103, L-HIDE.rules/4); nothing more is written here.
        Words that are the stored masked copy, sent back unchanged, are that copy: hide already holds what it hid
        from them, so nothing runs and nothing is written (BLD-C141)."""
        if text == stored:
            return text
        source_id = f"{self.uid}:{self.n}:{field}"
        return adapters.mask_text(self.conn, self.uid, text, by=self.user_id, source_id=source_id).text

    def changed(self, field: str, before: Any, after: Any) -> None:
        self.before[field] = before
        self.after[field] = after


def _text(raw: Any, limit: int) -> str | None:
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split()) if "\n" not in raw else raw.strip()
    return text[:limit] if len(text) > limit else text


def _save_texts(s: _Save, body: dict[str, Any]) -> None:
    messages = {
        "title": "Give it a title of a few words.",
        "summary": "Say what happens, in a sentence or two.",
        "often": "Say how often it happens, or leave it empty.",
    }
    updates: dict[str, str | None] = {}
    for field, limit in TEXT_LIMITS.items():
        if field not in body:
            continue
        raw = body[field]
        if raw is None and field == "often":
            value: str | None = None
        else:
            text = _text(raw, 10_000)
            if text is None or (field != "often" and not text) or len(text) > limit:
                raise Refused(422, "field_needed", messages[field], field)
            value = s.mask(field, text, s.idea.get(field)) if text else None
        if value != s.idea.get(field):
            updates[field] = value
            s.changed(field, s.idea.get(field), value)
    for field, value in updates.items():
        s.conn.execute(f"UPDATE ideas SET {field} = %s WHERE id = %s", (value, s.uid))  # noqa: S608 - fixed names


def _save_helpers(s: _Save, body: dict[str, Any], li: config.Lists) -> None:
    if "helpers" not in body:
        return
    picks, words = helpers.read(body["helpers"], li, at="helpers.")
    text = s.mask("helpers", words, s.idea.get("helper_text")) if words else None
    before = {"picks": list(s.idea.get("helper_picks") or []), "text": s.idea.get("helper_text")}
    after = {"picks": picks, "text": text}
    if before != after:
        s.conn.execute(
            "UPDATE ideas SET helper_picks = %s, helper_text = %s WHERE id = %s", (picks, text, s.uid)
        )
        s.changed("helpers", before, after)


def _save_fix(s: _Save, body: dict[str, Any], code: str) -> None:
    """The fix sheet's answers (`submit.fix`), or `fix: null` for "Remove". Figures that changed are a new
    `idea_worth` row; the earlier ones stay (L-WORTH/7)."""
    if "fix" not in body:
        return
    before = fix.entity(_fix(s.conn, s.uid))
    raw = body["fix"]
    if raw is None:  # "Remove"
        if before is not None:
            s.conn.execute("UPDATE idea_fix SET included = false WHERE idea_uuid = %s", (s.uid,))
            s.changed("fix", before, None)
        return
    answers = fix.read_answers(raw, need_how=True, at="fix.")
    fix.store(s.conn, s.uid, s.user_id, code, answers, included=True, stem=str(s.n), replace_worth=False)
    after = fix.entity(_fix(s.conn, s.uid))
    if after != before:
        s.changed("fix", before, after)


def _file_ids(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key, [])
    if (
        not isinstance(value, list)
        or len(value) > FILES_MAX
        or not all(isinstance(x, str) and ATT_ID.match(x) for x in value)
    ):
        raise Refused(400, "body_required", "Something went wrong. Try again.", "files")
    return list(dict.fromkeys(value))


def _save_files(s: _Save, body: dict[str, Any]) -> None:
    """`files: {added, removed}`: the files and links the edit page added or removed since it was loaded or last
    saved. They acted at once (BLD-C161); this save records them in the version, so the review desk's history shows
    them and a save that changed only files is not "Nothing has changed.". Only IDs that hold up count: an added one
    is on this idea now, a removed one is gone and its removal from this idea is in `audit_log` (`file.removed`).
    The version keeps IDs only, never a name."""
    raw = body.get("files")
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise Refused(400, "body_required", "Something went wrong. Try again.", "files")
    asked_added, asked_removed = _file_ids(raw, "added"), _file_ids(raw, "removed")
    added: list[str] = []
    if asked_added:
        rows = s.conn.execute(
            "SELECT id FROM attachments WHERE idea_uuid = %s AND id = ANY(%s) AND parent_id IS NULL "
            "AND answer_id IS NULL AND purpose = 'idea' AND conversation_entry_id IS NULL AND state <> 'rejected'",
            (s.uid, asked_added),
        ).fetchall()
        here = {str(r["id"]) for r in rows}
        added = [x for x in asked_added if x in here]
    removed: list[str] = []
    if asked_removed:
        rows = s.conn.execute(
            "SELECT DISTINCT after->>'file_id' AS id FROM audit_log WHERE entity = %s AND action = 'file.removed' "
            "AND after->>'file_id' = ANY(%s)",
            (f"idea:{s.uid}", asked_removed),
        ).fetchall()
        gone = {str(r["id"]) for r in rows}
        still = {
            str(r["id"])
            for r in s.conn.execute(
                "SELECT id FROM attachments WHERE id = ANY(%s)", (asked_removed,)
            ).fetchall()
        }
        removed = [x for x in asked_removed if x in gone and x not in still]
    if added or removed:
        s.changed("files", {"removed": removed}, {"added": added})


def save(conn: Conn, key: str, user_id: str, body: Any, *, now: dt.datetime) -> dict[str, Any]:
    """`PATCH /ideas/:id` (the edit page's Save) → the new version and the words S-06B shows after Save."""
    if not isinstance(body, dict):
        raise Refused(400, "body_required", "Something went wrong. Try again.")
    if body.get("declaration_version") != config.DECLARATION_VERSION:
        raise Refused(
            409,
            "declaration_changed",
            "The declaration beside Save has changed. Read it again, then save.",
            "declaration",
            version=config.DECLARATION_VERSION,
            text=config.DECLARATION["save"],
        )
    li = config.lists()
    with conn.transaction():
        idea, code = own.load_own(conn, key, user_id, lock=True)
        if idea["status"] == "draft" or idea["idea_id"] is None:
            raise NotFound
        w = window(conn, idea, now)
        if not w["open"]:
            raise _closed(idea, w)
        last = conn.execute(
            "SELECT coalesce(max(n), 0) AS n FROM idea_versions WHERE idea_uuid = %s", (idea["id"],)
        ).fetchone()
        n = (int(last["n"]) if last else 0) + 1
        s = _Save(conn, idea, user_id, n)
        _save_texts(s, body)
        _save_helpers(s, body, li)
        _save_fix(s, body, code)
        _save_files(s, body)
        if isinstance(body.get("sorting"), dict):
            before = sorting.current(conn, idea, li)
            sorting.apply(conn, idea, dict(body["sorting"]), phase="edit", now=now, li=li)
            after = sorting.current(conn, idea, li)
            if any(not sorting._same(f, before[f].value, after[f].value) for f in sorting.FIELDS):
                s.changed(
                    "sorting",
                    {f: before[f].value for f in sorting.FIELDS},
                    {f: after[f].value for f in sorting.FIELDS},
                )
        fresh = own.find(conn, str(idea["id"]))
        assert fresh is not None
        if (
            "fix" in s.after or "sorting" in s.after
        ):  # a problem shared with a fix shows as a Fix (E-ENUMS.kind)
            kind = sorting.kind_on_check_it(fresh.get("kind")) or "problem"
            stored = sorting.stored_kind(kind, ready.fix_line(conn, str(idea["id"])) is not None)
            if stored != fresh.get("kind"):
                conn.execute("UPDATE ideas SET kind = %s WHERE id = %s", (stored, idea["id"]))
        changed = [f for f in FIELD_WORDS if f in s.after]
        if not changed:
            return {
                "version": None,
                "changed_fields": [],
                "message": "Nothing has changed.",
                "next": {"to": f"/ideas/{idea['idea_id']}", "replace": True},
            }
        context = sealed_context("idea_versions", "snapshot_encrypted", f"{idea['id']}:{n}")
        conn.execute(
            "INSERT INTO idea_versions (idea_uuid, n, changed_fields, by_code, snapshot_encrypted, at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                idea["id"],
                n,
                changed,
                code,
                encrypt_json({"n": n, "before": s.before, "after": s.after}, context),
                now,
            ),
        )
        conn.execute("UPDATE ideas SET saved_at = %s WHERE id = %s", (now, idea["id"]))
        own.audit(conn, user_id, "idea.edit", idea, {"version": n + 1, "fields": changed})
        if "summary" in s.after:
            found = adapters.find_similar(conn, str(idea["id"]), found_while="later")
            conn.execute(
                "UPDATE ideas SET similar_check = %s WHERE id = %s",
                ("failed" if found is None else "done", idea["id"]),
            )
        return {
            "version": {"n": n + 1, "changed_fields": changed, "at": now.isoformat()},
            "changed_fields": changed,
            "saved_label": f"Saved at {clock(now)}",
            "message": SAVED,
            "next": {"to": f"/ideas/{idea['idea_id']}", "replace": True},
        }


# --- Draft history -----------------------------------------------------------------------------------------------


def _may_see_versions(conn: Conn, idea: dict[str, Any], user_id: str) -> bool:
    """The sharer, the review desk and the Ones Committee (DEC-104, P-PRODUCT.privacy), on a grant live now. A
    withdrawn idea is found by its sharer alone (L-SUBMIT.withdraw/2, BLD-E011): it has left every queue."""
    code = own.code_of(conn, user_id)
    if code is not None and code == idea["contributor_code"]:
        return True
    if idea["status"] == "withdrawn" or not own.UUID.match(user_id or ""):
        return False
    row = conn.execute(
        "SELECT 1 FROM role_grants WHERE user_id = %s AND role = ANY(%s) AND valid_from <= now() "
        "AND (valid_to IS NULL OR valid_to > now()) LIMIT 1",
        (user_id, list(STAFF_ROLES)),
    ).fetchone()
    return row is not None


def versions(conn: Conn, key: str, user_id: str, *, now: dt.datetime) -> dict[str, Any]:
    """`GET /ideas/:id/versions` for "Draft history": the idea as shared, then each save with what it changed."""
    idea = own.find(conn, key)
    if idea is None or idea["idea_id"] is None or not _may_see_versions(conn, idea, user_id):
        raise NotFound
    rows = conn.execute(
        "SELECT n, changed_fields, snapshot_encrypted, at FROM idea_versions WHERE idea_uuid = %s ORDER BY n",
        (idea["id"],),
    ).fetchall()
    items: list[dict[str, Any]] = [
        {
            "n": 1,
            "label": "As shared",
            "at": idea["shared_at"].isoformat(),
            "at_label": day(idea["shared_at"], now),
            "changed_fields": [],
        }
    ]
    for r in rows:
        snap: dict[str, Any] = {}
        if r["snapshot_encrypted"] is not None:
            try:
                snap = dict(
                    decrypt_json(
                        bytes(r["snapshot_encrypted"]),
                        sealed_context("idea_versions", "snapshot_encrypted", f"{idea['id']}:{r['n']}"),
                    )
                )
            except (CryptoError, ValueError, TypeError):
                snap = {}
        fields = list(r["changed_fields"] or [])
        items.append(
            {
                "n": int(r["n"]) + 1,
                "label": f"Changed: {join([FIELD_WORDS.get(f, f).lower() for f in fields])}"
                if fields
                else "Saved",
                "at": r["at"].isoformat(),
                "at_label": f"{day(r['at'], now)}, {clock(r['at'])}",
                "changed_fields": fields,
                **({"before": snap.get("before"), "after": snap.get("after")} if snap else {}),
            }
        )
    return {**versions_summary(conn, idea), "items": items}
