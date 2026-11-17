"""A reviewer's "Hide this" (L-HIDE.rules/7, S-R2) and the sharer's "Show it" / "Hide it" (L-HIDE.rules/6, C-HIDDEN.list).

"Hide this": the reviewer selects text in what they read (offsets in the masked copy, in code points, or in UTF-16
units when the browser sends them). It is masked at once in that text and, as whole words in any case, in every
other copy of the idea (`_sweep`): messages (and their English copy), answers, conversation messages, the title,
summary, how-often line and helper line, the parts, the fix, the desk's questions, the saved versions, the
similar-idea reasons and the draft's receipts. Each changed copy gets a `hidden_details` row, the value is stored
sealed, the action is audited and the sharer is told (`detail_hidden_by_desk`). A selection must be at least three
characters with a letter or digit in it, and at most 300 (`selection_too_long` above that). When the page sends the
words it selected (`selected`, the masked words as the desk sees them) and the stored text no longer has them at
those offsets, the hide is refused with `stale` (409), so a range never lands on words the reviewer did not select.
A reviewer never hides on their own idea or on one their contribution was merged into (`forbidden`, as lane B's
`refuse_own`; the attempt is audited).

"Show it" needs one of the three reasons and puts the value back in the copy others read; "Hide it" masks it again.
Both are the owner's alone and are audited; the desk reads "Shown, because …" from `hidden_details`. A detail the
review desk hid, or any detail holding a value the desk hid, cannot be shown: the desk's hide wins (BLD-C066).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.crypto import CryptoError, decrypt_json, encrypt_json
from core.db import Conn
from core.logging import get_logger
from hide import detect
from hide.core import (
    SHOW_REASONS,
    VAULT_TYPE,
    HideError,
    _seal_words,
    audit,
    detail_view,
    details_for,
    idea_row,
    is_uuid,
    layout,
    lock,
    own_words,
    scope_for,
    spans_of,
)
from onepc.context import open_text, seal_text, sealed_context
from pii import vault

log = get_logger("hide")

DESK_SOURCES = ("part", "message", "answer", "title", "conversation", "fix")
NOTIFY_KIND = "detail_hidden_by_desk"
MAX_SELECTION = 300  # code points; a longer selection is `selection_too_long` (422)
SELECTED_MAX = 10_000  # UTF-16 units of `selected`: twice the longest text (a 5,000-character message, V-FIELDS.submit/2)
MIN_SELECTION = 3  # shorter selections ("a", "5") would mask pieces of other words (BLD-C066)
PART_KEYS = ("title", "often", "who", "value", "area", "similar")
TITLE_FIELDS = ("title", "summary", "often", "helper_text")  # ideas columns the desk reads
FIX_FIELDS = ("how", "needs", "solved_note", "risks")  # idea_fix columns the desk reads
UNITS = ("cp", "utf16")


# ---- texts with a sealed owner's copy: messages, answers, conversation messages --------------------------------


@dataclass
class Sealed:
    source: str  # message | answer | conversation
    id: str
    table: str
    owner_user: str | None
    masked_now: str
    owner_text: str
    has_words: bool

    @property
    def in_place(self) -> bool:
        """No owner's words and no owner to seal them for (an author no longer mapped): the masked copy is the only
        copy, so it is masked in place and its details carry no span. Spans would point into a copy that changes
        with each hide, and a second hide would garble it (BLD-C066)."""
        return not self.has_words and not self.owner_user


_SEALED_SQL = {
    "message": (
        "idea_messages",
        "SELECT m.id, m.text_encrypted, cm.user_id AS owner FROM idea_messages m JOIN ideas i ON i.id = m.idea_uuid "
        "LEFT JOIN contributor_map cm ON cm.contributor_code = i.contributor_code "
        "WHERE m.idea_uuid = %s {where} ORDER BY m.seq",
    ),
    "answer": (
        "answers",
        "SELECT a.id, a.text_encrypted, cm.user_id AS owner FROM answers a JOIN questions q ON q.id = a.question_id "
        "JOIN question_sets s ON s.id = q.set_id LEFT JOIN contributor_map cm ON cm.contributor_code = a.by_code "
        "WHERE s.idea_uuid = %s AND a.text_encrypted IS NOT NULL {where} ORDER BY a.saved_at",
    ),
    "conversation": (
        "conversation_entries",
        "SELECT e.id, e.text_encrypted, coalesce(e.author_user_id, cm.user_id) AS owner FROM conversation_entries e "
        "LEFT JOIN contributor_map cm ON cm.contributor_code = e.author_code "
        "WHERE e.idea_uuid = %s AND e.type = 'message' AND e.text_encrypted IS NOT NULL {where} ORDER BY e.at",
    ),
}
_WHERE_ID = {"message": "AND m.id = %s", "answer": "AND a.id = %s", "conversation": "AND e.id = %s"}


def load_sealed(conn: Conn, idea_uuid: str, source: str, source_id: str | None = None) -> list[Sealed]:
    table, sql = _SEALED_SQL[source]
    params: tuple[Any, ...] = (idea_uuid,)
    where = ""
    if source_id is not None:
        if not is_uuid(source_id):
            return []
        where, params = _WHERE_ID[source], (idea_uuid, source_id)
    out: list[Sealed] = []
    for r in conn.execute(sql.format(where=where), params).fetchall():
        sid = str(r["id"])
        masked = open_text(table, "text_encrypted", sid, r["text_encrypted"])
        if masked is None:
            continue
        words = own_words(conn, source, sid, idea_uuid=idea_uuid)
        out.append(
            Sealed(
                source,
                sid,
                table,
                str(r["owner"]) if r["owner"] else None,
                masked,
                words or masked,
                words is not None,
            )
        )
    return out


def _write_in_place(conn: Conn, src: Sealed, new: str) -> None:
    """Store a new masked copy for a text masked in place (`Sealed.in_place`)."""
    conn.execute(
        f"UPDATE {src.table} SET text_encrypted = %s WHERE id = %s",  # noqa: S608 (one of three fixed names)
        (seal_text(src.table, "text_encrypted", src.id, new), src.id),
    )
    src.masked_now = src.owner_text = new


def _write_sealed(conn: Conn, idea_uuid: str, src: Sealed, details: list[dict[str, Any]]) -> str:
    if src.in_place:
        return src.masked_now  # never rebuilt from spans: its callers mask it in place (`_write_in_place`)
    masked, _ = layout(src.owner_text, details)
    conn.execute(
        f"UPDATE {src.table} SET text_encrypted = %s WHERE id = %s",  # noqa: S608 (one of three fixed names)
        (seal_text(src.table, "text_encrypted", src.id, masked), src.id),
    )
    if src.source == "message":
        conn.execute(
            "UPDATE idea_messages SET spans = %s WHERE id = %s",
            (_jsonb([{k: v for k, v in s.items() if k != "hid"} for s in spans_of(details)]), src.id),
        )
    if not src.has_words and src.owner_user:
        _seal_words(conn, idea_uuid, src.source, src.id, src.owner_user, src.owner_text)
        src.has_words = True
    src.masked_now = masked
    return masked


def _jsonb(value: Any) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def _owner_range(
    src: Sealed, details: list[dict[str, Any]], start: int, end: int
) -> tuple[int, int, dict[str, Any] | None]:
    """The reviewer's range in the masked copy -> the same range in the owner's words. A range on a shown detail
    returns that detail (the reviewer masks it again)."""
    rebuilt, segs = layout(src.owner_text, details)
    if rebuilt == src.masked_now:
        hit = [s for s in segs if s.m_end > s.m_start and s.m_start < end and start < s.m_end]
        for s in hit:
            if s.detail is not None and s.detail["state"] == "hidden":
                inside = s.m_start <= start and end <= s.m_end
                raise HideError(409, "already_hidden") if inside else HideError(400, "range_invalid")
        shown = [s for s in hit if s.detail is not None]
        if shown:
            s = shown[0]
            if len(shown) == 1 and s.m_start == start and s.m_end == end:
                return s.o_start, s.o_end, s.detail
            raise HideError(400, "range_invalid")
        first, last = hit[0], hit[-1]
        return first.o_start + (start - first.m_start), last.o_start + (end - last.m_start), None
    # The stored copy and the details disagree (written by another path): match by occurrence instead.
    selected = src.masked_now[start:end]
    k = len(detect.occurrences(src.masked_now[:start], selected))
    taken = [(int(d["span_start"]), int(d["span_end"])) for d in details if d.get("span_start") is not None]
    free = [
        (s, e)
        for s, e in detect.occurrences(src.owner_text, selected)
        if all(e <= a or s >= b for a, b in taken)
    ]
    if len(free) <= k:
        raise HideError(400, "range_invalid")
    return free[k][0], free[k][1], None


def _new_detail(
    conn: Conn,
    idea_uuid: str,
    source: str,
    source_id: str,
    start: int | None,
    end: int | None,
    kind: str,
    value: str,
    found_by: str = "reviewer",
) -> dict[str, Any]:
    tag = vault.assign(conn, scope_for(idea_uuid), VAULT_TYPE[kind], value)
    row = conn.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, vault_tag, "
        "found_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (idea_uuid, source, source_id, start, end, kind, detect.mask(kind, value), tag, found_by),
    ).fetchone()
    assert row is not None
    return dict(row)


def _copy_detail(
    conn: Conn, idea_uuid: str, source: str, source_id: str, kind: str, value: str, found_by: str
) -> None:
    """A copy with no owner's words (a title, a part, a saved version…) that the sweep masked: one row per copy and
    value, with no span, so it can be traced and listed (BLD-C066)."""
    tag = vault.assign(conn, scope_for(idea_uuid), VAULT_TYPE[kind], value)
    conn.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked, vault_tag, found_by) "
        "SELECT %s, %s, %s, %s, %s, %s, %s WHERE NOT EXISTS (SELECT 1 FROM hidden_details WHERE idea_uuid = %s "
        "AND source = %s AND source_id = %s AND vault_tag = %s AND span_start IS NULL)",
        (idea_uuid, source, source_id, kind, detect.mask(kind, value), tag, found_by,
         idea_uuid, source, source_id, tag),
    )  # fmt: skip


def _rehide(conn: Conn, detail: dict[str, Any], *, by_desk: bool = False) -> dict[str, Any]:
    """Hide a shown detail again. `by_desk`: the review desk hid it, so it becomes the desk's (the owner cannot show
    it again, BLD-C066)."""
    row = conn.execute(
        "UPDATE hidden_details SET state = 'hidden', reason = NULL, shown_by = NULL, shown_at = NULL, "
        "found_by = CASE WHEN %s THEN 'reviewer' ELSE found_by END WHERE id = %s RETURNING *",
        (by_desk, detail["id"]),
    ).fetchone()
    assert row is not None
    return dict(row)


# ---- texts with no owner's copy: title, summary, often, parts ---------------------------------------------------


def _walk(node: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(node, str):
        return fn(node)
    if isinstance(node, list):
        return [_walk(x, fn) for x in node]
    if isinstance(node, dict):
        return {k: _walk(v, fn) for k, v in node.items()}
    return node


def _part_path(source_id: str) -> tuple[str, list[str]]:
    key, *path = source_id.split(".")
    if key not in PART_KEYS:
        raise HideError(404, "not_found")
    return key, path


def _get_path(node: Any, path: list[str]) -> Any:
    for p in path:
        if isinstance(node, list) and p.isdigit() and int(p) < len(node):
            node = node[int(p)]
        elif isinstance(node, dict) and p in node:
            node = node[p]
        else:
            raise HideError(404, "not_found")
    return node


def _set_path(node: Any, path: list[str], value: str) -> Any:
    if not path:
        return value
    head, rest = path[0], path[1:]
    if isinstance(node, list):
        out = list(node)
        out[int(head)] = _set_path(node[int(head)], rest, value)
        return out
    out_d = dict(node)
    out_d[head] = _set_path(node[head], rest, value)
    return out_d


def _plain_text(conn: Conn, idea_uuid: str, kind: str, source_id: str) -> tuple[str, Callable[[str], None]]:
    """The text a reviewer sees for a title, a fix field or a part, and how to write it back."""
    if kind in ("title", "fix"):
        fields, table, key = (
            (TITLE_FIELDS, "ideas", "id") if kind == "title" else (FIX_FIELDS, "idea_fix", "idea_uuid")
        )
        if kind == "fix" and source_id not in fields:
            raise HideError(404, "not_found")
        column = source_id if source_id in fields else "title"
        row = conn.execute(
            f"SELECT {column} AS t FROM {table} WHERE {key} = %s",  # noqa: S608 (fixed names only)
            (idea_uuid,),
        ).fetchone()
        if row is None or not isinstance(row["t"], str):
            raise HideError(404, "not_found")

        def write_plain(new: str) -> None:
            conn.execute(f"UPDATE {table} SET {column} = %s WHERE {key} = %s", (new, idea_uuid))  # noqa: S608

        return row["t"], write_plain
    key, path = _part_path(source_id)
    row = conn.execute(
        "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = %s", (idea_uuid, key)
    ).fetchone()
    if row is None or row["value"] is None:
        raise HideError(404, "not_found")
    whole = row["value"]
    text = _get_path(whole, path)
    if not isinstance(text, str):
        raise HideError(400, "range_invalid")

    def write_part(new: str) -> None:
        conn.execute(
            "UPDATE idea_parts SET value = %s WHERE idea_uuid = %s AND key = %s",
            (_jsonb(_set_path(whole, path, new)), idea_uuid, key),
        )

    return text, write_part


def _has_column(conn: Conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s "
            "AND column_name = %s",
            (table, column),
        ).fetchone()
        is not None
    )


@dataclass
class Swept:
    copies: int = 0  # texts changed
    rehidden: int = 0  # the owner's "Show it" undone because the desk hid the same value


def _sweep_sealed(
    conn: Conn, idea_uuid: str, src: Sealed, value: str, kind: str, found_by: str, out: Swept
) -> int:
    """One text with the owner's words: a detail per new place, rebuilt from the words. Returns 1 when it changed."""
    details = details_for(conn, idea_uuid, src.source, src.id)
    flipped = False
    if found_by == "reviewer":
        for i, d in enumerate(details):
            s, e = d.get("span_start"), d.get("span_end")
            if d["state"] == "shown" and s is not None and detect.same_value(value, src.owner_text[s:e]):
                details[i] = _rehide(conn, d, by_desk=True)
                flipped = True
                out.rehidden += 1
    taken = [(int(d["span_start"]), int(d["span_end"])) for d in details if d.get("span_start") is not None]
    new = [
        (s, e)
        for s, e in detect.value_places(src.owner_text, value)
        if all(e <= a or s >= b for a, b in taken)
    ]
    for s, e in new:
        details.append(
            _new_detail(conn, idea_uuid, src.source, src.id, s, e, kind, src.owner_text[s:e], found_by)
        )
    if new or flipped:
        _write_sealed(conn, idea_uuid, src, details)
        return 1
    return 0


def _sweep(conn: Conn, idea_uuid: str, value: str, kind: str, *, found_by: str = "reviewer") -> Swept:
    """Mask `value`, as whole words in any case, in every copy of this idea (L-HIDE.rules/7). Texts with the owner's
    words get a detail per place (their masked copy is rebuilt from them); the other copies are masked in place and
    get one row each. When the desk hid it, a detail the owner chose to show with the same value is hidden again."""
    out = Swept()
    masked = detect.mask(kind, value)

    def masker(t: str) -> str:
        return detect.mask_in(t, value, masked)[0]

    # 1. Messages, answers and conversation messages: rebuilt from the owner's words.
    english = _has_column(conn, "idea_messages", "text_en_encrypted")  # lane C's drafts add an English copy
    for source in ("message", "answer", "conversation"):
        for src in load_sealed(conn, idea_uuid, source):
            if src.in_place:
                in_place, n = detect.mask_in(src.masked_now, value, masked)
                if n:
                    _write_in_place(conn, src, in_place)
                    _copy_detail(conn, idea_uuid, source, src.id, kind, value, found_by)
                    out.copies += 1
            else:
                out.copies += _sweep_sealed(conn, idea_uuid, src, value, kind, found_by, out)
            if source == "message" and english:
                row = conn.execute(
                    "SELECT text_en_encrypted FROM idea_messages WHERE id = %s", (src.id,)
                ).fetchone()
                text_en = (
                    open_text("idea_messages", "text_en_encrypted", src.id, row["text_en_encrypted"])
                    if row
                    else None
                )
                if text_en:
                    new_en, n = detect.mask_in(text_en, value, masked)
                    if n:
                        conn.execute(
                            "UPDATE idea_messages SET text_en_encrypted = %s WHERE id = %s",
                            (seal_text("idea_messages", "text_en_encrypted", src.id, new_en), src.id),
                        )
                        out.copies += 1

    def plain(source: str, source_id: str) -> None:
        _copy_detail(conn, idea_uuid, source, source_id, kind, value, found_by)
        out.copies += 1

    # 2. The idea's own lines: title, summary, how often, the helper line.
    idea = conn.execute(
        "SELECT title, summary, often, helper_text FROM ideas WHERE id = %s", (idea_uuid,)
    ).fetchone()
    for column in TITLE_FIELDS:
        old = idea[column] if idea else None
        if isinstance(old, str) and detect.value_places(old, value):
            conn.execute(f"UPDATE ideas SET {column} = %s WHERE id = %s", (masker(old), idea_uuid))  # noqa: S608
            plain("title", column)

    # 3. The fix (masked copies; the person's own words for them are sealed as edits).
    fix = conn.execute(
        "SELECT how, needs, solved_note, risks FROM idea_fix WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchone()
    for column in FIX_FIELDS:
        old = fix[column] if fix else None
        if isinstance(old, str) and detect.value_places(old, value):
            conn.execute(f"UPDATE idea_fix SET {column} = %s WHERE idea_uuid = %s", (masker(old), idea_uuid))  # noqa: S608
            plain("fix", column)

    # 4. The parts: value, why and the quote.
    for part in conn.execute(
        "SELECT key, value, why, source_quote FROM idea_parts WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchall():
        new_value = _walk(part["value"], masker) if part["value"] is not None else None
        new_why = masker(part["why"]) if part["why"] else part["why"]
        new_quote = masker(part["source_quote"]) if part["source_quote"] else part["source_quote"]
        if (new_value, new_why, new_quote) != (part["value"], part["why"], part["source_quote"]):
            conn.execute(
                "UPDATE idea_parts SET value = %s, why = %s, source_quote = %s WHERE idea_uuid = %s AND key = %s",
                (
                    _jsonb(new_value) if new_value is not None else None,
                    new_why,
                    new_quote,
                    idea_uuid,
                    part["key"],
                ),
            )
            plain("part", str(part["key"]))

    # 5. The desk's questions (masked when written, `hide_text`), sealed per row.
    for q in conn.execute(
        "SELECT q.id, q.text_encrypted FROM questions q JOIN question_sets s ON s.id = q.set_id "
        "WHERE s.idea_uuid = %s",
        (idea_uuid,),
    ).fetchall():
        qid = str(q["id"])
        text = open_text("questions", "text_encrypted", qid, q["text_encrypted"])
        if text and detect.value_places(text, value):
            conn.execute(
                "UPDATE questions SET text_encrypted = %s WHERE id = %s",
                (seal_text("questions", "text_encrypted", qid, masker(text)), qid),
            )
            plain("desk", qid)

    # 6. Saved versions of the idea (the masked idea as saved, sealed as JSON).
    for v in conn.execute(
        "SELECT id, n, snapshot_encrypted FROM idea_versions WHERE idea_uuid = %s AND snapshot_encrypted IS NOT NULL",
        (idea_uuid,),
    ).fetchall():
        context = sealed_context("idea_versions", "snapshot_encrypted", f"{idea_uuid}:{v['n']}")
        try:
            snap = decrypt_json(bytes(v["snapshot_encrypted"]), context)
        except CryptoError:
            continue  # sealed another way: left as it is, never opened by the desk
        new_snap = _walk(snap, masker)
        if new_snap != snap:
            conn.execute(
                "UPDATE idea_versions SET snapshot_encrypted = %s WHERE id = %s",
                (encrypt_json(new_snap, context), v["id"]),
            )
            plain("version", str(v["n"]))

    # 7. Why another idea looks similar, in either direction.
    for link in conn.execute(
        "SELECT idea_uuid, other_idea_uuid, reason FROM similar_links WHERE idea_uuid = %s OR other_idea_uuid = %s",
        (idea_uuid, idea_uuid),
    ).fetchall():
        if detect.value_places(link["reason"], value):
            conn.execute(
                "UPDATE similar_links SET reason = %s WHERE idea_uuid = %s AND other_idea_uuid = %s",
                (masker(link["reason"]), link["idea_uuid"], link["other_idea_uuid"]),
            )
            other = link["other_idea_uuid"] if str(link["idea_uuid"]) == idea_uuid else link["idea_uuid"]
            plain("similar", str(other))

    # 8. The draft's receipts and suggestions.
    for run in conn.execute(
        "SELECT id, receipt, suggestions FROM draft_runs WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchall():
        receipt, suggestions = _walk(run["receipt"], masker), _walk(run["suggestions"], masker)
        if (receipt, suggestions) != (run["receipt"], run["suggestions"]):
            conn.execute(
                "UPDATE draft_runs SET receipt = %s, suggestions = %s WHERE id = %s",
                (_jsonb(receipt), _jsonb(suggestions), run["id"]),
            )
            plain("run", str(run["id"]))
    return out


def _notify_sharer(conn: Conn, idea: dict[str, Any], by: str) -> bool:
    """Tell the sharer the review desk hid a detail (Inbox kind `detail_hidden_by_desk`, BLD-C063). IDs only: no refs,
    so the notice never carries the hidden value (L-HIDE.rules/8). Until lane A's notify knows the kind, the audit
    row is the record and nothing is posted. Returns whether a notice was posted."""
    import notify

    sharer = idea.get("sharer_user_id")
    if not sharer or str(sharer) == by:
        return False
    if NOTIFY_KIND not in notify.INBOX_KINDS:
        log.info("hide.notify_kind_pending", idea_id=str(idea["id"]))
        return False
    notify.post(conn, NOTIFY_KIND, [str(sharer)], idea_id=str(idea["id"]), sender=by)  # type: ignore[arg-type]
    return True


def _selection(text: str, start: int, end: int) -> tuple[int, str]:
    """The selected words without the spaces around them, and where they start. Refuses a selection shorter than
    three characters or with no letter or digit in it (BLD-C066)."""
    raw = text[start:end]
    value = raw.strip()
    if len(value) < MIN_SELECTION or not any(ch.isalnum() for ch in value):
        raise HideError(400, "range_invalid")
    return start + len(raw) - len(raw.lstrip()), value


def _code_points(text: str, start: int, end: int, units: str) -> tuple[int, int]:
    if units == "cp":
        return start, end
    s, e = detect.from_utf16(text, start), detect.from_utf16(text, end)
    if s is None or e is None or e <= s:
        raise HideError(400, "range_invalid")
    return s, e


def _range(text: str, start: int, end: int, units: str, selected: str | None) -> tuple[int, int]:
    """The reviewer's range in `text` (the masked copy they read), in code points. With `selected`, the words must
    still be there: `text[start:end]` and `selected`, each without the spaces at its ends, compared after the UTF-16
    conversion (the same words in either count); a range that no longer fits the text is the same case. Errors:
    `stale` (409) with `selected`, else `range_invalid`; `selection_too_long` (422) above MAX_SELECTION."""
    try:
        s, e = _code_points(text, start, end, units)
        if e > len(text):
            raise HideError(400, "range_invalid")
    except HideError:
        if selected is not None:
            raise HideError(409, "stale") from None
        raise
    if selected is not None and text[s:e].strip() != selected.strip():
        raise HideError(409, "stale")
    if e - s > MAX_SELECTION:
        raise HideError(422, "selection_too_long")
    return s, e


def _refuse_own(conn: Conn, by: str, idea: dict[str, Any]) -> None:
    """A reviewer never hides on their own idea, nor on one their contribution was merged into: lane B's rule for the
    desk page's `own` (`desk.store.is_own`, P-PRODUCT.roles/3). 403 `forbidden`; the attempt is audited after the
    rollback (`hide/api.py`)."""
    from desk.store import is_own

    if is_uuid(by) and is_own(conn, by, idea):
        raise HideError(
            403,
            "forbidden",
            audit=(by, "hide.own_idea_refused", str(idea["id"]), {"action": "desk_hide"}),
        )


def desk_hide(
    conn: Conn,
    idea_uuid: str,
    *,
    source_kind: str,
    source_id: str,
    start: int,
    end: int,
    by: str,
    units: str = "cp",
    selected: object = None,
) -> dict[str, Any]:
    """A reviewer's "Hide this". `units`: "cp" (code points, Python callers) or "utf16" (the browser's offsets, which
    the web passes on as they are). `selected`: optional, the masked words the reviewer selected; when the stored text
    no longer has them at those offsets the hide is refused with `stale` (`_range`). Returns the HiddenDetail.
    Errors: not_found, range_invalid, already_hidden, stale (409), selection_too_long (422), forbidden (403: the
    reviewer's own idea, `_refuse_own`)."""
    if source_kind not in DESK_SOURCES or units not in UNITS:
        raise HideError(400, "range_invalid")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or isinstance(start, bool)
        or isinstance(end, bool)
    ):
        raise HideError(400, "range_invalid")
    if selected is not None and not isinstance(selected, str):
        raise HideError(400, "range_invalid")
    if selected is not None and detect.to_utf16(selected, len(selected)) > SELECTED_MAX:
        raise HideError(422, "selection_too_long")
    if start < 0 or end <= start:
        raise HideError(400, "range_invalid")
    with conn.transaction():
        idea = idea_row(conn, idea_uuid)
        if idea["status"] == "draft":
            raise HideError(404, "not_found")  # the desk never sees a draft
        _refuse_own(conn, by, idea)
        lock(conn, idea_uuid)
        if source_kind in ("message", "answer", "conversation"):
            found = load_sealed(conn, idea_uuid, source_kind, source_id)
            if not found:
                raise HideError(404, "not_found")
            src = found[0]
            start, end = _range(src.masked_now, start, end, units, selected)
            _selection(src.masked_now, start, end)
            row, value = _hide_sealed(conn, idea_uuid, src, start, end)
        else:
            text, write = _plain_text(conn, idea_uuid, source_kind, source_id)
            start, end = _range(text, start, end, units, selected)
            row, value = _hide_plain(conn, idea_uuid, source_kind, source_id, text, start, end, write)
        swept = _sweep(conn, idea_uuid, value, str(row["kind"]))
        hid = str(row["id"])
        notified = _notify_sharer(conn, idea, by)
        audit(
            conn,
            by,
            "hide.desk_hidden",
            idea_uuid,
            {"hidden_id": hid, "kind": row["kind"], "source": source_kind, "source_id": source_id,
             "other_copies": swept.copies, "rehidden": swept.rehidden, "sharer_notified": notified},
        )  # fmt: skip
    log.info("hide.desk_hidden", idea_id=idea_uuid, hidden_id=hid, other_copies=swept.copies)
    return detail_view(row)


def _hide_sealed(conn: Conn, idea_uuid: str, src: Sealed, start: int, end: int) -> tuple[dict[str, Any], str]:
    """The selection in a message, answer or conversation message: mapped to the owner's words and rebuilt from them,
    or masked in place when there are none and no owner (`Sealed.in_place`). Returns the detail and the value."""
    if src.in_place:
        return _hide_plain(
            conn, idea_uuid, src.source, src.id, src.masked_now, start, end,
            lambda new: _write_in_place(conn, src, new), spans=False,
        )  # fmt: skip
    details = details_for(conn, idea_uuid, src.source, src.id)
    o_start, o_end, shown = _owner_range(src, details, start, end)
    if shown is not None:
        row = _rehide(conn, shown, by_desk=True)  # the desk's hide now: the owner cannot show it again
        details = [row if str(d["id"]) == str(row["id"]) else d for d in details]
        _write_sealed(conn, idea_uuid, src, details)
        return row, src.owner_text[o_start:o_end]
    o_start, value = _selection(src.owner_text, o_start, o_end)
    kind = detect.classify(value, src.owner_text, o_start)
    row = _new_detail(conn, idea_uuid, src.source, src.id, o_start, o_start + len(value), kind, value)
    details.append(row)
    _write_sealed(conn, idea_uuid, src, details)
    return row, value


def _hide_plain(
    conn: Conn,
    idea_uuid: str,
    source: str,
    source_id: str,
    text: str,
    start: int,
    end: int,
    write: Callable[[str], None],
    *,
    spans: bool = True,
) -> tuple[dict[str, Any], str]:
    """Mask the selection in a text that is its only copy (a title, a part, the fix, or a text masked in place) and
    store its detail; `spans`: whether the detail keeps where it sits. Returns the detail and the value."""
    for a, b in detect.mask_tokens(text):
        if a < end and start < b:
            raise (
                HideError(409, "already_hidden")
                if a <= start and end <= b
                else HideError(400, "range_invalid")
            )
    s, value = _selection(text, start, end)
    kind = detect.classify(value, text, s)
    at = (s, s + len(value)) if spans else (None, None)
    row = _new_detail(conn, idea_uuid, source, source_id, at[0], at[1], kind, value)
    write(text[:s] + str(row["masked"]) + text[s + len(value) :])
    return row, value


# ---- the owner's "Show it" and "Hide it" ------------------------------------------------------------------


def _owner_of(conn: Conn, idea: dict[str, Any], detail: dict[str, Any]) -> str | None:
    source = str(detail["source"])
    if source in ("answer", "conversation"):
        found = load_sealed(conn, str(idea["id"]), source, str(detail["source_id"]))
        return found[0].owner_user if found else None
    return str(idea["sharer_user_id"]) if idea.get("sharer_user_id") else None


def _value_of(conn: Conn, idea_uuid: str, detail: dict[str, Any]) -> str | None:
    tag = detail.get("vault_tag")
    if not tag:
        return None
    hit = vault.mapping(conn, scope_for(idea_uuid)).get(str(tag))
    return hit[1] if hit else None


def _rewrite(
    conn: Conn, idea_uuid: str, detail: dict[str, Any], details_after: Callable[[], list[dict[str, Any]]]
) -> None:
    """Put the copy others read in line with the detail's new state."""
    source, sid = str(detail["source"]), str(detail["source_id"])
    if source in ("message", "answer", "conversation"):
        found = load_sealed(conn, idea_uuid, source, sid)
        if found:
            _write_sealed(conn, idea_uuid, found[0], details_after())
        return
    if source in ("title", "part"):
        value = _value_of(conn, idea_uuid, detail)
        if value is None:
            return
        text, write = _plain_text(conn, idea_uuid, source, sid)
        masked_form = str(detail["masked"])
        if detail["state"] == "shown":
            write(text.replace(masked_form, value, 1))
        else:
            at = text.find(value)
            if at != -1:
                write(text[:at] + masked_form + text[at + len(value) :])


def _owned_detail(conn: Conn, idea_uuid: str, hid: str, by: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not is_uuid(hid):
        raise HideError(404, "not_found")
    idea = idea_row(conn, idea_uuid)
    lock(conn, idea_uuid)
    row = conn.execute(
        "SELECT * FROM hidden_details WHERE id = %s AND idea_uuid = %s FOR UPDATE",
        (hid, idea_uuid),
    ).fetchone()
    if row is None or _owner_of(conn, idea, dict(row)) != by:
        raise HideError(404, "not_found")  # someone else's detail looks exactly like a missing one
    return idea, dict(row)


def _desk_hid(conn: Conn, idea_uuid: str, detail: dict[str, Any]) -> bool:
    """The review desk hid this detail, or the same value elsewhere on the idea: the desk's hide wins (BLD-C066)."""
    if detail["found_by"] == "reviewer":
        return True
    if not detail.get("vault_tag"):
        return False
    return (
        conn.execute(
            "SELECT 1 FROM hidden_details WHERE idea_uuid = %s AND vault_tag = %s AND found_by = 'reviewer' LIMIT 1",
            (idea_uuid, detail["vault_tag"]),
        ).fetchone()
        is not None
    )


def show(conn: Conn, idea_uuid: str, hid: str, *, reason: object, by: str) -> dict[str, Any]:
    """ "Show it" with one of the three reasons (L-HIDE.rules/6). Returns the HiddenDetail."""
    if reason not in SHOW_REASONS:
        raise HideError(400, "reason_required")
    with conn.transaction():
        _, detail = _owned_detail(conn, idea_uuid, hid, by)
        if _desk_hid(conn, idea_uuid, detail):
            raise HideError(403, "forbidden")
        if detail["state"] == "shown":
            return detail_view(detail)
        row = conn.execute(
            "UPDATE hidden_details SET state = 'shown', reason = %s, shown_by = %s, shown_at = %s "
            "WHERE id = %s RETURNING *",
            (reason, by, dt.datetime.now(dt.UTC), hid),
        ).fetchone()
        assert row is not None
        updated = dict(row)
        _rewrite(
            conn,
            idea_uuid,
            updated,
            lambda: details_for(conn, idea_uuid, str(updated["source"]), str(updated["source_id"])),
        )
        audit(conn, by, "hide.shown", idea_uuid, {"hidden_id": hid, "kind": updated["kind"], "reason_code": reason},
              reason=str(reason))  # fmt: skip
    log.info("hide.shown", idea_id=idea_uuid, hidden_id=hid, reason_code=str(reason))
    return detail_view(updated)


def hide_again(conn: Conn, idea_uuid: str, hid: str, *, by: str) -> dict[str, Any]:
    """ "Hide it": reverses "Show it". Returns the HiddenDetail."""
    with conn.transaction():
        _, detail = _owned_detail(conn, idea_uuid, hid, by)
        if detail["found_by"] == "reviewer":
            raise HideError(403, "forbidden")  # the desk's own hide: not the owner's to change
        if detail["state"] == "hidden":
            return detail_view(detail)
        updated = _rehide(conn, detail)
        _rewrite(
            conn,
            idea_uuid,
            updated,
            lambda: details_for(conn, idea_uuid, str(updated["source"]), str(updated["source_id"])),
        )
        audit(conn, by, "hide.rehidden", idea_uuid, {"hidden_id": hid, "kind": updated["kind"]})
    log.info("hide.rehidden", idea_id=idea_uuid, hidden_id=hid)
    return detail_view(updated)
