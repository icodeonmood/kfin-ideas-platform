"""A reviewer's "Hide this" (L-HIDE.rules/7, S-R2) and the sharer's "Show it" / "Hide it" (L-HIDE.rules/6, C-HIDDEN.list).

"Hide this": the reviewer selects text in what they read (offsets in the masked copy). It is masked at once in
that text and wherever the same value appears in the idea's other copies (messages, answers, conversation, title,
summary, parts, receipts), the value is stored sealed, the action is audited and the sharer is told
(`detail_hidden_by_desk`).

"Show it" needs one of the three reasons and puts the value back in the copy others read; "Hide it" masks it again.
Both are the owner's alone and are audited; the desk reads "Shown, because …" from `hidden_details`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
from onepc.context import open_text, seal_text
from pii import vault

log = get_logger("hide")

DESK_SOURCES = ("part", "message", "answer", "title", "conversation")
NOTIFY_KIND = "detail_hidden_by_desk"
MAX_SELECTION = 300
PART_KEYS = ("title", "often", "who", "value", "area", "similar")
TITLE_FIELDS = ("title", "summary", "often")


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
        words = own_words(conn, source, sid)
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


def _write_sealed(conn: Conn, idea_uuid: str, src: Sealed, details: list[dict[str, Any]]) -> str:
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
        hit = [s for s in segs if s.m_start < end and start < s.m_end]
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
) -> dict[str, Any]:
    tag = vault.assign(conn, scope_for(idea_uuid), VAULT_TYPE[kind], value)
    row = conn.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, vault_tag, "
        "found_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'reviewer') RETURNING *",
        (idea_uuid, source, source_id, start, end, kind, detect.mask(kind, value), tag),
    ).fetchone()
    assert row is not None
    return dict(row)


def _rehide(conn: Conn, detail: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute(
        "UPDATE hidden_details SET state = 'hidden', reason = NULL, shown_by = NULL, shown_at = NULL "
        "WHERE id = %s RETURNING *",
        (detail["id"],),
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
    """The text a reviewer sees for a title or part, and how to write it back."""
    if kind == "title":
        column = source_id if source_id in TITLE_FIELDS else "title"
        row = conn.execute(
            f"SELECT {column} AS t FROM ideas WHERE id = %s",  # noqa: S608 (one of three fixed names)
            (idea_uuid,),
        ).fetchone()
        if row is None or not isinstance(row["t"], str):
            raise HideError(404, "not_found")

        def write_title(new: str) -> None:
            conn.execute(f"UPDATE ideas SET {column} = %s WHERE id = %s", (new, idea_uuid))  # noqa: S608 (fixed names)

        return row["t"], write_title
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


def _sweep(conn: Conn, idea_uuid: str, value: str, kind: str, skip: tuple[str, str]) -> int:
    """Mask `value` in every other copy of this idea. Returns how many texts changed."""
    changed = 0
    mask_text = detect.mask(kind, value)
    for source in ("message", "answer", "conversation"):
        for src in load_sealed(conn, idea_uuid, source):
            if (source, src.id) == skip:
                continue
            details = details_for(conn, idea_uuid, source, src.id)
            taken = [
                (int(d["span_start"]), int(d["span_end"])) for d in details if d.get("span_start") is not None
            ]
            new = [
                (s, e)
                for s, e in detect.occurrences(src.owner_text, value)
                if all(e <= a or s >= b for a, b in taken)
            ]
            if not new:
                continue
            for s, e in new:
                details.append(_new_detail(conn, idea_uuid, source, src.id, s, e, kind, value))
            _write_sealed(conn, idea_uuid, src, details)
            changed += 1

    def replace(t: str) -> str:
        return t.replace(value, mask_text)

    row = conn.execute(
        "UPDATE ideas SET title = replace(title, %s, %s), summary = replace(summary, %s, %s), "
        "often = replace(often, %s, %s) WHERE id = %s AND (strpos(title, %s) > 0 OR strpos(summary, %s) > 0 "
        "OR strpos(often, %s) > 0) RETURNING id",
        (value, mask_text, value, mask_text, value, mask_text, idea_uuid, value, value, value),
    ).fetchone()
    changed += 1 if row else 0
    for part in conn.execute(
        "SELECT key, value, why, source_quote FROM idea_parts WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchall():
        new_value = _walk(part["value"], replace) if part["value"] is not None else None
        new_why = replace(part["why"]) if part["why"] else part["why"]
        new_quote = replace(part["source_quote"]) if part["source_quote"] else part["source_quote"]
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
            changed += 1
    for run in conn.execute(
        "SELECT id, receipt, suggestions FROM draft_runs WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchall():
        receipt, suggestions = _walk(run["receipt"], replace), _walk(run["suggestions"], replace)
        if (receipt, suggestions) != (run["receipt"], run["suggestions"]):
            conn.execute(
                "UPDATE draft_runs SET receipt = %s, suggestions = %s WHERE id = %s",
                (_jsonb(receipt), _jsonb(suggestions), run["id"]),
            )
            changed += 1
    return changed


def _notify_sharer(conn: Conn, idea: dict[str, Any], by: str, hid: str, kind: str) -> None:
    from notify import INBOX_KINDS, post

    sharer = idea.get("sharer_user_id")
    if not sharer or str(sharer) == by:
        return
    if (
        NOTIFY_KIND not in INBOX_KINDS
    ):  # lane A adds the kind to E-ENUMS.inbox (BLD-C063); the audit row stands
        log.info("hide.notify_kind_pending", idea_id=str(idea["id"]), hidden_id=hid)
        return
    post(
        conn,
        NOTIFY_KIND,  # type: ignore[arg-type]
        [str(sharer)],
        idea_id=str(idea["id"]),
        sender=by,
        refs={"hidden_id": hid, "kind": kind},
        dedupe_key=f"{NOTIFY_KIND}:{hid}",
    )


def desk_hide(
    conn: Conn, idea_uuid: str, *, source_kind: str, source_id: str, start: int, end: int, by: str
) -> dict[str, Any]:
    """A reviewer's "Hide this". Returns the HiddenDetail. Errors: not_found, range_invalid, already_hidden."""
    if source_kind not in DESK_SOURCES:
        raise HideError(400, "range_invalid")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or isinstance(start, bool)
        or isinstance(end, bool)
    ):
        raise HideError(400, "range_invalid")
    if start < 0 or end <= start or end - start > MAX_SELECTION:
        raise HideError(400, "range_invalid")
    with conn.transaction():
        idea = idea_row(conn, idea_uuid)
        if idea["status"] == "draft":
            raise HideError(404, "not_found")  # the desk never sees a draft
        lock(conn, idea_uuid)
        if source_kind in ("message", "answer", "conversation"):
            found = load_sealed(conn, idea_uuid, source_kind, source_id)
            if not found:
                raise HideError(404, "not_found")
            src = found[0]
            if end > len(src.masked_now) or not src.masked_now[start:end].strip():
                raise HideError(400, "range_invalid")
            details = details_for(conn, idea_uuid, source_kind, src.id)
            o_start, o_end, shown = _owner_range(src, details, start, end)
            if shown is not None:
                row = _rehide(conn, shown)
                details = [row if str(d["id"]) == str(row["id"]) else d for d in details]
                _write_sealed(conn, idea_uuid, src, details)
                value = src.owner_text[o_start:o_end]
            else:
                raw = src.owner_text[o_start:o_end]
                lead = len(raw) - len(raw.lstrip())
                value = raw.strip()
                o_start += lead
                o_end = o_start + len(value)
                kind = detect.classify(value, src.owner_text, o_start)
                row = _new_detail(conn, idea_uuid, source_kind, src.id, o_start, o_end, kind, value)
                details.append(row)
                _write_sealed(conn, idea_uuid, src, details)
            skip = (source_kind, src.id)
        else:
            text, write = _plain_text(conn, idea_uuid, source_kind, source_id)
            if end > len(text) or not text[start:end].strip():
                raise HideError(400, "range_invalid")
            for a, b in detect.mask_tokens(text):
                if a < end and start < b:
                    raise (
                        HideError(409, "already_hidden")
                        if a <= start and end <= b
                        else HideError(400, "range_invalid")
                    )
            raw = text[start:end]
            lead = len(raw) - len(raw.lstrip())
            value = raw.strip()
            s = start + lead
            kind = detect.classify(value, text, s)
            row = _new_detail(conn, idea_uuid, source_kind, source_id, s, s + len(value), kind, value)
            write(text[:s] + str(row["masked"]) + text[s + len(value) :])
            skip = (source_kind, source_id)
        changed = _sweep(conn, idea_uuid, value, str(row["kind"]), skip)
        hid = str(row["id"])
        audit(
            conn,
            by,
            "hide.desk_hidden",
            idea_uuid,
            {"hidden_id": hid, "kind": row["kind"], "source": source_kind, "source_id": source_id,
             "other_copies": changed},
        )  # fmt: skip
        _notify_sharer(conn, idea, by, hid, str(row["kind"]))
    log.info("hide.desk_hidden", idea_id=idea_uuid, hidden_id=hid, other_copies=changed)
    return detail_view(row)


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


def show(conn: Conn, idea_uuid: str, hid: str, *, reason: object, by: str) -> dict[str, Any]:
    """ "Show it" with one of the three reasons (L-HIDE.rules/6). Returns the HiddenDetail."""
    if reason not in SHOW_REASONS:
        raise HideError(400, "reason_required")
    with conn.transaction():
        _, detail = _owned_detail(conn, idea_uuid, hid, by)
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
