"""The reviewer revises what an idea is worth, and recategorises it (L-WORTH/2–7, C-WORTH.edit).

A revision is a new `idea_worth` row on the reviewer's side; the sharer's row is never changed (L-WORTH/3). The
latest revision is what counts (L-WORTH/5), and every one is kept with who, when and the note (L-WORTH/7).
The rules that need no database (reading figures, the tiles) are in `desk.worth`.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

from core.db import Conn
from desk import adapters, promises, worth
from desk.review import ensure_on_desk
from desk.store import (
    Refused,
    actor,
    audit,
    audited,
    load_idea,
    now,
    own_codes,
    person_by_user,
    refuse_own,
    seal,
    unseal,
    user_of,
)
from desk.worth import KIND_LABELS, MEASURES, Range, Worth


def _range(measure: worth.Measure, low: Any, high: Any) -> Range | None:
    """A stored measure, its words rebuilt the way `worth.parse` writes them."""
    if low is None:
        return None
    lo = float(low)
    hi = None if high is None or float(high) == lo else float(high)
    return Range(lo, hi, worth._text(measure, lo, hi, False))


def _worth(row: dict[str, Any]) -> Worth:
    tools = row["outside_tools"]
    return Worth(
        hours_month=_range("hours_month", row["hours_low"], row["hours_high"]),
        cost_month=_range("cost_month", row["cost_low"], row["cost_high"]),
        revenue_month=_range("revenue_month", row["revenue_low"], row["revenue_high"]),
        outside_tools=tools if tools in worth.OUTSIDE_TOOLS else None,
    )


def _latest(conn: Conn, idea_uuid: Any, side: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM idea_worth WHERE idea_uuid = %s AND by_side = %s ORDER BY at DESC, id DESC LIMIT 1",
        (idea_uuid, side),
    ).fetchone()
    return dict(row) if row else None


def current(conn: Conn, idea_uuid: Any) -> tuple[Worth, Worth | None, dict[str, Any] | None]:
    """The sharer's latest figures (empty when they gave none) and the latest revision with its note, who and when
    (E-ENTITIES.idea `worth`). The note is the masked copy."""
    sharer = _latest(conn, idea_uuid, "sharer")
    reviewer = _latest(conn, idea_uuid, "reviewer")
    if reviewer is None:
        return (_worth(sharer) if sharer else Worth()), None, None
    meta = {
        "id": reviewer["id"],
        "note": unseal(reviewer["note_encrypted"], "idea_worth", "note_encrypted", reviewer["id"]),
        "by": person_by_user(conn, str(reviewer["by_user_id"]) if reviewer["by_user_id"] else None).as_json(),
        "at": reviewer["at"].isoformat(),
        "kind": reviewer["kind"],
        "area": reviewer["area"],
    }
    return (_worth(sharer) if sharer else Worth()), _worth(reviewer), meta


def _merged(fields: dict[str, Any], typed: Worth, base: Worth) -> Worth:
    """What was sent replaces what counts now; a measure left out of the body keeps its current figure, so a
    revision of the hours alone does not blank the cost (an empty value does clear it)."""
    ranges = {m: getattr(typed if m in fields else base, m) for m in MEASURES}
    tools = typed.outside_tools if "outside_tools" in fields else base.outside_tools
    return Worth(**ranges, outside_tools=tools)


def revise_worth(
    conn: Conn, ref: str, user_id: str, body: dict[str, Any], at: dt.datetime | None = None
) -> dict[str, Any]:
    """L-WORTH/2–4, /7: the reviewer's revision of the four measures, the kind and the area, with an optional note
    the sharer reads at once. Allowed while the idea is on the desk. Body: hours_month, cost_month and
    revenue_month as typed, outside_tools, kind, area, note (all optional; the figures may also come under
    `worth`, as A-API.desk writes it). Errors: own_idea (403), already_decided (409), worth_invalid,
    outside_tools_invalid, note_invalid, note_too_long, kind_invalid, area_invalid (422)."""
    t = at or now()
    p = promises.get()
    fields: dict[str, Any] = body["worth"] if isinstance(body.get("worth"), dict) else body
    note = body.get("note")
    kind, area = body.get("kind"), body.get("area")
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        refuse_own(conn, user_id, idea, "revise_worth")
        ensure_on_desk(idea)
        if note is not None and not isinstance(note, str):  # a list or object is never stored as its repr
            raise Refused(422, "note_invalid", "Write the note as text.", "note")
        typed, errors = worth.read_revision(fields, note, p.worth_note_max)
        if errors:
            e = errors[0]
            raise Refused(422, e.code, e.message, e.field)
        if kind is not None and (not isinstance(kind, str) or kind not in KIND_LABELS):
            raise Refused(422, "kind_invalid", "Choose what kind it is.", "kind")
        if area is not None and (not isinstance(area, str) or not area.strip()):
            raise Refused(422, "area_invalid", "Choose an area.", "area")
        area = area.strip() if area is not None else None
        sharer, reviewer, _ = current(conn, idea["id"])
        base = worth.counted(sharer, reviewer)
        revised = _merged(fields, typed, base)
        values: list[Any] = []
        for m in MEASURES:
            r = getattr(revised, m)
            values += [r.low, r.high] if r else [None, None]
        row = conn.execute(
            "INSERT INTO idea_worth (idea_uuid, by_side, by_user_id, hours_low, hours_high, cost_low, cost_high, "
            "revenue_low, revenue_high, outside_tools, kind, area, at) "
            "VALUES (%s, 'reviewer', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (idea["id"], user_id, *values, revised.outside_tools, kind, area, t),
        ).fetchone()
        assert row is not None
        worth_id = int(row["id"])
        masked = None
        if note is not None and note.strip():
            masked, _ = adapters.hide(conn, str(idea["id"]), note.strip(), by=user_id)
            conn.execute(
                "UPDATE idea_worth SET note_encrypted = %s WHERE id = %s",
                (seal(masked, "idea_worth", "note_encrypted", worth_id), worth_id),
            )
        # recategorise (L-WORTH/2): the idea itself takes the new kind and area; the audit keeps the old ones
        before: dict[str, Any] = {}
        changes: dict[str, Any] = {}
        if kind is not None and kind != idea["kind"]:
            before["kind"], changes["kind"] = idea["kind"], kind
        if area is not None and area != idea["area"]:
            before["area"], changes["area"] = idea["area"], area
        if changes:
            sets = ", ".join(f"{c} = %s" for c in changes)  # fixed column names only
            conn.execute(f"UPDATE ideas SET {sets} WHERE id = %s", (*changes.values(), idea["id"]))  # noqa: S608
        sharer, reviewer, meta = current(conn, idea["id"])
        shown = worth.tiles(sharer, reviewer)
        adapters.say(conn, str(idea["id"]), "desk.worth_revised", author_user_id=user_id,
                     payload={"worth_id": worth_id}, at=t)  # fmt: skip
        adapters.tell(
            conn, "worth_revised", [u for c in sorted(own_codes(conn, idea)) if (u := user_of(conn, c))],
            idea_uuid=str(idea["id"]), sender=user_id,
            actions=[("Open the idea", f"/ideas/{idea['idea_id']}", "primary")], refs={"worth_id": worth_id},
        )  # fmt: skip
        audit(conn, actor(user_id), "desk.revise_worth", f"idea:{idea['idea_id']}", before=before or None,
              after={"worth_id": worth_id, "changed": [t_.measure for t_ in shown if t_.changed], **changes})  # fmt: skip
        assert reviewer is not None and meta is not None
        return {
            "idea_id": idea["idea_id"], "worth_id": worth_id,
            "tiles": [dataclasses.asdict(t_) for t_ in shown],
            "sharer": sharer.as_json(),
            "reviewer": {**reviewer.as_json(), "note": masked, "by": meta["by"], "at": meta["at"]},
            "kind": changes.get("kind", idea["kind"]), "area": changes.get("area", idea["area"]),
        }  # fmt: skip
