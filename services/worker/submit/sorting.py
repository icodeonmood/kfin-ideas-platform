"""L-SORT: sorting is suggested from the draft, then confirmed or changed by the sharer (DEC-102; supersedes DEC-004
and DEC-094).

- Each field arrives pre-filled from the draft's parts with its reason (`L-SORT.rules/1`): who it affects from the
  `who` part, the area from `area`, what it would bring from `value`; what kind it is from the draft's kind, a
  problem to fix unless the draft says otherwise. A suggestion is never stored: while a field is untouched it follows
  the draft, so a later message that changes a part changes the suggestion too.
- Confirmation is explicit (`/2`). `{confirm: true}` ("Confirm sorting", "Looks right") confirms every untouched
  field at its current suggestion; changing a value confirms that field. Each field records its source,
  `suggested`, `confirmed` or `changed` (`/3`), in `ideas.sorting_sources`; a changed value is the person's call
  and nothing overwrites it. A value equal to the current suggestion counts as confirmed, not changed.
- Required (V-FIELDS.sorting): who it affects, at least one; what kind, one; area, one; what it would bring, at least
  one, "Not sure yet" on its own.
- After sharing, the same changes are made from the edit page (`/5`, `submit.edit`).

How often people change each suggested field is a launch metric (`/8`): the `sorting_trust` view counts it from
`ideas.sorting_sources` of shared ideas.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal

from psycopg.types.json import Jsonb

from core.db import Conn
from onepc import enums
from submit import config, own
from submit.errors import Refused
from submit.words import in_sentence, join

Field = Literal["affects", "kind", "area", "brings"]
FIELDS: tuple[Field, ...] = ("affects", "kind", "area", "brings")
Phase = Literal["draft", "edit"]

INCOMPLETE = "Confirm these, or change any of them, before you send."
UNCONFIRMED = "Confirm the sorting first, or change any of it."
NOTE_SUGGESTED = "These are suggestions from your words. Not confirmed yet."
NOTE_EDIT = "Confirmed when you shared it. You can still change any of these."
KIND_WHY = {
    "problem": "because you described something that goes wrong today.",
    "business_idea": "because you described something new KFintech could offer.",  # NOT DRAWN: default
}
MAX_PICKS = 20


@dataclass(frozen=True)
class Choice:
    value: Any
    source: str  # suggested | confirmed | changed
    why: str | None

    def filled(self) -> bool:
        return bool(self.value)


def kind_on_check_it(kind: object) -> str | None:
    """E-ENUMS.kind: a problem shared with a fix is stored as `fix` (the Wall's label) and sorted as a problem."""
    if kind in ("problem", "fix", "problem_with_solution"):
        return "problem"
    if kind == "business_idea":
        return "business_idea"
    return None


def stored_kind(kind: str, fix_included: bool) -> str:
    return "fix" if kind == "problem" and fix_included else kind


def _parts(conn: Conn, idea_uuid: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT key, state, value, why FROM idea_parts WHERE idea_uuid = %s AND key IN ('who', 'value', 'area') "
        "AND state IN ('filled', 'pinned') AND value IS NOT NULL",
        (idea_uuid,),
    ).fetchall()
    return {str(r["key"]): dict(r) for r in rows}


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for i in items:
        if i not in seen:
            seen.append(i)
    return seen


def suggestions(conn: Conn, idea: dict[str, Any], li: config.Lists) -> dict[Field, Choice]:
    """What the draft suggests for each field, with its reason (L-DRAFT.parts). A part with no value suggests
    nothing; the columns are the fallback for a draft written before its parts were."""
    parts = _parts(conn, str(idea["id"]))

    def why(key: str) -> str | None:
        w = parts.get(key, {}).get("why")
        return str(w) if w else None

    who = parts.get("who", {}).get("value")
    who_list = who if isinstance(who, list) else list(idea.get("affects") or [])
    affects = _dedupe([x for x in (li.affects_label(v) for v in who_list) if x])
    area_raw = parts.get("area", {}).get("value", idea.get("area"))
    area = li.area_label(area_raw) if area_raw else None
    value = parts.get("value", {}).get("value")
    value_list = value if isinstance(value, list) else list(idea.get("brings") or [])
    brings = _dedupe([b for b in value_list if b in config.BRINGS])
    if config.NOT_SURE in brings and len(brings) > 1:
        brings = [b for b in brings if b != config.NOT_SURE]
    kind = kind_on_check_it(idea.get("kind")) or "problem"
    return {
        "affects": Choice(affects, "suggested", why("who") if affects else None),
        "kind": Choice(kind, "suggested", KIND_WHY[kind]),
        "area": Choice(area, "suggested", why("area") if area else None),
        "brings": Choice(brings, "suggested", why("value") if brings else None),
    }


def current(conn: Conn, idea: dict[str, Any], li: config.Lists | None = None) -> dict[Field, Choice]:
    """Each field as it stands: the person's confirmed or changed value, else the draft's suggestion."""
    li = li or config.lists()
    suggested = suggestions(conn, idea, li)
    sources = idea.get("sorting_sources") or {}
    out: dict[Field, Choice] = {}
    for f in FIELDS:
        rec = sources.get(f) or {}
        source = rec.get("source")
        if source not in ("confirmed", "changed"):
            out[f] = suggested[f]
            continue
        stored: Any = {
            "affects": list(idea.get("affects") or []),
            "kind": kind_on_check_it(idea.get("kind")),
            "area": idea.get("area"),
            "brings": list(idea.get("brings") or []),
        }[f]
        out[f] = Choice(stored, str(source), rec.get("why") if source == "confirmed" else None)
    return out


def is_confirmed(choices: dict[Field, Choice]) -> bool:
    return all(c.source in ("confirmed", "changed") for c in choices.values())


def is_complete(choices: dict[Field, Choice]) -> bool:
    return all(c.filled() for c in choices.values())


def why_line(c: Choice) -> str | None:
    """'Suggested because you mentioned investors and the branch.' Shown while the value is the draft's, before
    and after confirming (S-05 part 2, S-06B section 4); none for the person's own change."""
    if c.source == "changed" or not c.why:
        return None
    w = " ".join(c.why.split())
    if w.lower().startswith("suggested"):
        line = w
    elif w.lower().startswith("because"):
        line = "Suggested " + w[0].lower() + w[1:]
    else:
        line = "Suggested: " + w[0].lower() + w[1:]
    return line if line.endswith((".", "!", "?")) else line + "."


def _brings_words(brings: list[str]) -> list[str]:
    labels = enums.labels("brings")
    return [labels.get(b, b).lower() for b in brings]


def rail_line(choices: dict[Field, Choice]) -> str:
    """The rail's status for part 2: 'Suggested, not confirmed yet', then 'Investor service, saves time, saves cost'."""
    if not is_confirmed(choices):
        return "Suggested, not confirmed yet"
    return ", ".join([str(choices["area"].value or ""), *_brings_words(list(choices["brings"].value or []))])


def summary_line(choices: dict[Field, Choice]) -> str:
    """The Send part's sorting row: 'Investor service, affecting investors and KFin teams, saves time, saves cost',
    or 'Not confirmed yet'."""
    if not is_confirmed(choices):
        return "Not confirmed yet"
    affecting = join([in_sentence(a) for a in choices["affects"].value or []])
    bits = [str(choices["area"].value or ""), f"affecting {affecting}" if affecting else ""]
    return ", ".join(b for b in [*bits, *_brings_words(list(choices["brings"].value or []))] if b)


def view(conn: Conn, idea: dict[str, Any], *, phase: Phase, li: config.Lists | None = None) -> dict[str, Any]:
    """E-ENTITIES `Sorting`, with the words the screen shows beside it."""
    choices = current(conn, idea, li)
    confirmed = is_confirmed(choices)
    complete = is_complete(choices)
    out: dict[str, Any] = {
        f: {"value": c.value, "source": c.source, "why": c.why, "why_line": why_line(c)}
        for f, c in choices.items()
    }
    if phase == "edit":
        note: str | None = NOTE_EDIT
    else:
        note = None if confirmed else NOTE_SUGGESTED
    out.update(
        confirmed=confirmed,
        complete=complete,
        confirmed_at=idea["sorting_confirmed_at"].isoformat() if idea.get("sorting_confirmed_at") else None,
        rail=rail_line(choices),
        summary=summary_line(choices),
        note=note,
        problem=None
        if complete
        else {"code": "sorting_incomplete", "message": INCOMPLETE, "field": "sorting"},
    )
    return out


def _incomplete() -> Refused:
    return Refused(422, "sorting_incomplete", INCOMPLETE, "sorting")


def _read_value(f: Field, raw: Any, li: config.Lists) -> Any:
    """A value from the request, in the configured spelling; Refused when it is empty or not on the list."""
    if f == "kind":
        kind = kind_on_check_it(raw)
        if kind is None:
            raise _incomplete()
        return kind
    if f == "area":
        area = li.area_label(raw)
        if area is None:
            raise _incomplete()
        return area
    if not isinstance(raw, list) or not raw or len(raw) > MAX_PICKS:
        raise _incomplete()
    if f == "affects":
        picked = [li.affects_label(v) for v in raw]
        if any(p is None for p in picked):
            raise _incomplete()
        return _dedupe([p for p in picked if p])
    if any(not isinstance(b, str) or b not in config.BRINGS for b in raw):
        raise _incomplete()
    picks = _dedupe(list(raw))
    if config.NOT_SURE in picks and len(picks) > 1:  # "Not sure yet" clears the others (V-FIELDS.checkit/3)
        raise _incomplete()
    return picks


def _same(f: Field, a: Any, b: Any) -> bool:
    if f in ("affects", "brings"):
        return set(a or []) == set(b or [])
    return bool(a == b)


def apply(
    conn: Conn,
    idea: dict[str, Any],
    body: dict[str, Any],
    *,
    phase: Phase,
    now: dt.datetime,
    li: config.Lists | None = None,
) -> list[Field]:
    """Apply changes and/or `confirm` to a locked idea row; returns the fields whose value or source changed. The
    caller holds the transaction and the row lock, and decides whether the idea may be changed now."""
    li = li or config.lists()
    before = current(conn, idea, li)
    suggested = suggestions(conn, idea, li)
    after = dict(before)
    touched: list[Field] = []
    for f in FIELDS:
        if f not in body:
            continue
        value = _read_value(f, body[f], li)
        source = "confirmed" if _same(f, value, suggested[f].value) else "changed"
        if before[f].source == "changed" and _same(f, value, before[f].value):
            source = "changed"  # the person's call stays theirs
        after[f] = Choice(value, source, suggested[f].why if source == "confirmed" else None)
        if not _same(f, value, before[f].value) or source != before[f].source:
            touched.append(f)
    if body.get("confirm") is True:
        for f in FIELDS:
            if after[f].source == "suggested":
                if not after[f].filled():
                    raise _incomplete()
                after[f] = Choice(after[f].value, "confirmed", after[f].why)
                touched.append(f)
    if not touched:
        return []
    if phase == "edit" and not is_complete(after):
        raise _incomplete()

    sources = dict(idea.get("sorting_sources") or {})
    for f in FIELDS:
        if after[f].source != "suggested":
            sources[f] = {"source": after[f].source, **({"why": after[f].why} if after[f].why else {})}
    fix_included = bool(
        conn.execute(
            "SELECT 1 FROM idea_fix WHERE idea_uuid = %s AND included AND coalesce(how, '') <> ''",
            (idea["id"],),
        ).fetchone()
    )
    kind = after["kind"].value if after["kind"].source != "suggested" else kind_on_check_it(idea.get("kind"))
    confirmed_now = is_confirmed(after)
    row = conn.execute(
        "UPDATE ideas SET affects = %s, kind = %s, area = %s, brings = %s, sorting_sources = %s, "
        "sorting_confirmed_at = CASE WHEN %s THEN coalesce(sorting_confirmed_at, %s) ELSE sorting_confirmed_at END "
        "WHERE id = %s RETURNING *",
        (
            list(after["affects"].value or [])
            if after["affects"].source != "suggested"
            else idea.get("affects") or [],
            stored_kind(kind, fix_included) if kind else idea.get("kind"),
            after["area"].value if after["area"].source != "suggested" else idea.get("area"),
            list(after["brings"].value or [])
            if after["brings"].source != "suggested"
            else idea.get("brings") or [],
            Jsonb(sources),
            confirmed_now,
            now,
            idea["id"],
        ),
    ).fetchone()
    assert row is not None
    idea.clear()
    idea.update(dict(row))
    return [f for f in FIELDS if f in touched]


def update_draft(conn: Conn, key: str, user_id: str, body: Any, *, now: dt.datetime) -> dict[str, Any]:
    """`PATCH /drafts/:id/sorting` → `Sorting`. Only a draft; a shared idea is changed from its edit page."""
    if not isinstance(body, dict):
        raise Refused(400, "body_required", "Something went wrong. Try again.")
    li = config.lists()
    with conn.transaction():
        idea, _code = own.load_own(conn, key, user_id, lock=True)
        if idea["status"] != "draft":
            raise Refused(
                409,
                "not_a_draft",
                "This idea has been sent. Change it from its page while it’s open to changes.",
            )
        touched = apply(conn, idea, body, phase="draft", now=now, li=li)
        if touched:
            conn.execute("UPDATE ideas SET saved_at = %s WHERE id = %s", (now, idea["id"]))
            sources = idea.get("sorting_sources") or {}
            own.audit(
                conn,
                user_id,
                "idea.sorting",
                idea,
                {
                    "fields": list(touched),
                    "sources": {f: (sources.get(f) or {}).get("source") for f in FIELDS},
                },
            )
        return view(conn, idea, phase="draft", li=li)


def read_draft(conn: Conn, key: str, user_id: str) -> dict[str, Any]:
    """`GET /drafts/:id/sorting` → `Sorting`: the suggestions, or what the person confirmed or changed."""
    idea, _code = own.load_own(conn, key, user_id)
    return view(conn, idea, phase="draft" if idea["status"] == "draft" else "edit")
