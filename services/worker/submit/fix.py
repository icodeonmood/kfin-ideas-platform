"""The fix sheet (S-05.fix, E-ENTITIES `Fix`, E-ENUMS.fix): `PUT /drafts/:id/fix` and `DELETE /drafts/:id/fix`
(A-API.drafts), and the same answers on the edit page's Save (`PATCH /ideas/:id`, `submit.edit`).

1. Six questions. Five count toward "2 of 5 ready for the review desk": how, what it would need, whether anyone has
   solved it already, what it's worth (any one measure) and what that is based on. The risks never count ("It never
   counts against the idea"). The most useful next answer is named in the order how, a rough size, solved already,
   what it is based on, what it would need: the board's "2 of 5" (how and solved already given) names the size.
2. Only how is needed to add a fix, at least 20 characters (V-FIELDS.checkit/8). "Close, and keep what you wrote" keeps
   a started fix with `included: false`: "You started a fix. It isn't included yet."
3. Amounts in any Indian form (2 lakh, 2L, 2,00,000, 25k, ranges) are read by the platform's one quantity reader,
   lane B's `desk.worth` (L-WORTH/1), and come back normalised in `Range.text` ("70 to 150 hours a month"). "About"
   before a single figure stays ("about ₹25,000 a month saved", as drawn): `idea_worth.<measure>_about` keeps it.
4. Every answer in words goes through hide like any part (`submit.adapters.mask_text`, DEC-103): only the masked
   copy is kept here; the words as typed are sealed for the sharer alone. One source id per answer, so saving the
   sheet again replaces what was hidden from that answer before. An answer sent back exactly as its stored masked
   copy is unchanged and is not masked again: no hidden-detail or sealed rows are written for it (BLD-C141).
5. A fix never holds Submit (L-SUBMIT.pre/6); with one included the button reads "Submit with my fix".

The sharer's figures are rows in `idea_worth` (by_side 'sharer'; the latest counts). On a draft they are replaced,
since nobody else has seen them; on a shared idea each change is a new row, so a reviewer's revision and every
earlier figure stay (L-WORTH/3, /7). Nothing here logs text or figures (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from core.db import Conn
from desk.worth import MEASURES, OUTSIDE_TOOLS, TOO_BIG, Range, Worth, WorthInvalid, parse
from onepc import enums
from submit import adapters, own
from submit.errors import Refused

READY_OF = 5
READY_KEYS = ("how", "needs", "solved_already", "worth", "basis")
NEXT_ORDER = ("how", "worth", "solved_already", "basis", "needs")
NEXT_LINE = {
    "worth": "Most useful next: a rough size. A range is fine.",  # drawn (Review.md, fix=Sheet open)
    # NOT DRAWN: the other four name the sheet's own question.
    "how": "Most useful next: how you’d solve it. One or two sentences is plenty.",
    "solved_already": "Most useful next: whether anyone has solved this already.",
    "basis": "Most useful next: what that is based on.",
    "needs": "Most useful next: what it would need.",
}
TEXT_LIMITS = {"how": 2000, "needs": 2000, "solved_note": 600, "risks": 2000}
HOW_MIN = 20  # V-FIELDS.checkit/8
FIGURE_MAX = 80  # characters typed into one figure field
HOW_NEEDED = "Say how you’d solve it, or close this to send without a fix."  # V-FIELDS.checkit/8
WORTH_UNCLEAR = "Write a rough figure or a range, like 70 to 150."  # V-FIELDS.checkit/9
STARTED = "You started a fix. It isn’t included yet."
CARRY_ON = "Carry on with your fix"
SOLVED_WORDS = {"yes": "yes", "partly": "partly", "no": "no"}  # "I don't know" adds nothing to the size line
WORTH_COLUMNS = {"hours_month": "hours", "cost_month": "cost", "revenue_month": "revenue"}
ENTITY_KEYS = (
    "how",
    "needs",
    "solved_already",
    "solved_note",
    "worth",
    "basis",
    "risks",
    "ready_count",
    "included",
)


@dataclass
class Answers:
    """The sheet as sent, read and checked; the words not yet masked."""

    words: dict[str, str | None] = field(default_factory=dict)  # how, needs, solved_note, risks
    solved_already: str | None = None
    basis: str | None = None
    worth: Worth = field(default_factory=Worth)


def _words(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split()) if "\n" not in raw else raw.strip()
    return text or None


def _plain(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _figure(measure: str, raw: Any, at: str) -> Range | None:
    """One measure as typed ("2 lakh", "70 to 150"), as a number, or as a `Range` sent back: read by `desk.worth`."""
    if raw is None or raw == "":
        return None
    typed: Any
    if isinstance(raw, bool):
        typed = None
    elif isinstance(raw, int | float):
        typed = _plain(raw) if raw >= 0 else None
    elif isinstance(raw, dict):
        text, low, high = raw.get("text"), raw.get("low"), raw.get("high")
        if isinstance(text, str) and text.strip():
            typed = text
        elif isinstance(low, int | float) and not isinstance(low, bool) and low >= 0:
            ok_high = isinstance(high, int | float) and not isinstance(high, bool)
            typed = _plain(low) if high is None else f"{_plain(low)} to {_plain(high)}" if ok_high else None
        else:
            typed = None
    else:
        typed = raw
    if not isinstance(typed, str) or len(typed) > FIGURE_MAX:
        raise Refused(422, "worth_unclear", WORTH_UNCLEAR, at)
    try:
        return parse(measure, typed)  # type: ignore[arg-type]
    except WorthInvalid as exc:
        message = TOO_BIG if exc.error.message == TOO_BIG else WORTH_UNCLEAR
        raise Refused(422, "worth_unclear", message, at) from None


def read_answers(raw: Any, *, need_how: bool, at: str = "") -> Answers:
    """The sheet's answers from a request body (`Fix` fields), or the field's message. `at` prefixes the field names
    ("fix." on the edit page). Values not on a list are dropped, as a chip the person never saw."""
    if not isinstance(raw, dict):
        raise Refused(422, "fix_how_needed", HOW_NEEDED, f"{at}how")
    out = Answers()
    for key, limit in TEXT_LIMITS.items():
        text = _words(raw.get(key))
        if text is not None and len(text) > limit:
            raise Refused(422, "field_needed", f"Keep it to {limit} characters.", f"{at}{key}")
        out.words[key] = text
    how = out.words["how"]
    if need_how and (how is None or len(how) < HOW_MIN):
        raise Refused(422, "fix_how_needed", HOW_NEEDED, f"{at}how")
    solved = raw.get("solved_already")
    out.solved_already = solved if solved in enums.values("solved_already") else None
    basis = raw.get("basis")
    out.basis = basis if basis in enums.values("basis") else None
    worth = raw.get("worth")
    if worth is not None and not isinstance(worth, dict):
        raise Refused(422, "worth_unclear", WORTH_UNCLEAR, f"{at}worth")
    worth = worth or {}
    ranges = {m: _figure(m, worth.get(m), f"{at}worth.{m}") for m in MEASURES}
    raw_tools = worth.get("outside_tools")
    tools: Any = raw_tools if isinstance(raw_tools, str) and raw_tools in OUTSIDE_TOOLS else None
    out.worth = Worth(**ranges, outside_tools=tools)
    return out


# --- Reading ------------------------------------------------------------------------------------------------------


def about(r: Range | None) -> bool | None:
    """Whether one figure was typed with "about" (`idea_worth.<measure>_about`): None when it is not given, and only a
    single figure keeps it, since `desk.worth` leaves it off a range."""
    if r is None:
        return None
    return r.high is None and r.text.startswith("about ")


def sharer_worth(conn: Conn, idea_uuid: str) -> Worth | None:
    """The sharer's latest figures, normalised again from the stored numbers (`desk.worth` writes the text), with
    "about" again before a single figure the sharer wrote it on (a row from before the flag reads as plain)."""
    row = conn.execute(
        "SELECT * FROM idea_worth WHERE idea_uuid = %s AND by_side = 'sharer' ORDER BY at DESC, id DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        return None
    ranges: dict[str, Range | None] = {}
    for measure, prefix in WORTH_COLUMNS.items():
        low, high = row[f"{prefix}_low"], row[f"{prefix}_high"]
        if low is None:
            ranges[measure] = None
            continue
        typed = _plain(float(low)) if high is None else f"{_plain(float(low))} to {_plain(float(high))}"
        if high is None and row.get(f"{prefix}_about"):
            typed = f"about {typed}"
        ranges[measure] = parse(measure, typed)  # type: ignore[arg-type]
    tools = row["outside_tools"] if row["outside_tools"] in OUTSIDE_TOOLS else None
    w = Worth(**ranges, outside_tools=tools)
    return w if w.as_json() else None


def ready_count(row: dict[str, Any] | None, worth: Worth | None) -> int:
    if row is None:
        return 0
    given = {k: bool(row.get(k)) for k in ("how", "needs", "solved_already", "basis")}
    given["worth"] = worth is not None and bool(worth.as_json())
    return sum(given[k] for k in READY_KEYS)


def next_up(row: dict[str, Any] | None, worth: Worth | None) -> dict[str, str] | None:
    given = {k: bool((row or {}).get(k)) for k in ("how", "needs", "solved_already", "basis")}
    given["worth"] = worth is not None and bool(worth.as_json())
    key = next((k for k in NEXT_ORDER if not given[k]), None)
    return {"key": key, "line": NEXT_LINE[key]} if key else None


def size_line(worth: Worth | None, solved_already: str | None) -> str:
    """'70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly' (Review.md, fix=Added)."""
    bits: list[str] = []
    if worth is not None:
        if worth.hours_month is not None:
            bits.append(worth.hours_month.text)
        if worth.cost_month is not None:
            bits.append(f"{worth.cost_month.text} saved")
        if worth.revenue_month is not None:
            bits.append(f"{worth.revenue_month.text} in new revenue")
        if worth.outside_tools in ("partly", "fully"):
            bits.append("less reliance on outside tools")
    if solved_already in SOLVED_WORDS:
        bits.append(f"solved elsewhere: {SOLVED_WORDS[solved_already]}")
    return ", ".join(bits)


def one_line(how: str | None) -> str | None:
    if not how:
        return None
    text = " ".join(how.split())
    return text if len(text) <= 140 else text[:139].rstrip() + "…"


def view(conn: Conn, idea_uuid: str, *, started_too: bool = False) -> dict[str, Any] | None:
    """E-ENTITIES `Fix` with `ready_count`, and the words S-05 shows: the readiness line, the most useful next answer,
    and on the part "Included, 5 of 5 ready", the one-line fix and its size line (or the started-fix line). None when
    there is no fix, or (unless `started_too`) when it is not included."""
    row = conn.execute("SELECT * FROM idea_fix WHERE idea_uuid = %s", (idea_uuid,)).fetchone()
    if row is None or not (started_too or (row["included"] and (row["how"] or "").strip())):
        return None
    worth = sharer_worth(conn, idea_uuid)
    included = bool(row["included"]) and bool((row["how"] or "").strip())
    n = ready_count(dict(row), worth)
    out: dict[str, Any] = {
        k: row[k]
        for k in ("how", "needs", "solved_already", "solved_note", "basis", "risks")
        if row[k] is not None
    }
    if worth is not None:  # E-ENTITIES `Range { low, high?, text }`: no `high` for a single figure
        out["worth"] = {
            m: {k: v for k, v in r.items() if v is not None} if isinstance(r, dict) else r
            for m, r in worth.as_json().items()
        }
    size = size_line(worth, row["solved_already"])
    out.update(
        ready_count=n,
        included=included,
        ready_of=READY_OF,
        readiness=f"{n} of {READY_OF} ready for the review desk",
        next=next_up(dict(row), worth),
        part=(
            {
                "rail": "Added",
                "line": f"Included, {n} of {READY_OF} ready",
                "fix_line": one_line(row["how"]),
                **({"size_line": size} if size else {}),
            }
            if included
            else {"rail": "Optional", "line": STARTED, "action": CARRY_ON}
        ),
    )
    return out


def entity(v: dict[str, Any] | None) -> dict[str, Any] | None:
    """Just the E-ENTITIES `Fix` fields of a `view`, for a version's before and after."""
    return None if v is None else {k: v[k] for k in ENTITY_KEYS if k in v}


# --- Writing ------------------------------------------------------------------------------------------------------


def source_ids(idea_uuid: str, stem: str) -> dict[str, str]:
    return {k: f"{idea_uuid}:{stem}:fix.{k}" for k in TEXT_LIMITS}


def store(
    conn: Conn,
    idea_uuid: str,
    user_id: str,
    code: str,
    answers: Answers,
    *,
    included: bool,
    stem: str,
    replace_worth: bool,
) -> None:
    """Mask the words (hide, one source id per answer under `stem`), keep the masked copy in `idea_fix` and the
    figures in `idea_worth`. Inside the caller's transaction."""
    ids = source_ids(idea_uuid, stem)
    stored = conn.execute(
        "SELECT how, needs, solved_note, risks FROM idea_fix WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchone()
    masked: dict[str, str | None] = {}
    emptied: list[str] = []
    for key, text in answers.words.items():
        if text and stored is not None and text == stored[key]:
            masked[key] = text  # the stored masked copy sent back: hide already holds what it hid from it
        elif text:
            masked[key] = adapters.mask_text(conn, idea_uuid, text, by=user_id, source_id=ids[key]).text
        else:
            masked[key] = None
            emptied.append(ids[key])
    adapters.forget_words(conn, idea_uuid, emptied)
    conn.execute(
        "INSERT INTO idea_fix (idea_uuid, how, needs, solved_already, solved_note, basis, risks, included) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (idea_uuid) DO UPDATE SET how = EXCLUDED.how, "
        "needs = EXCLUDED.needs, solved_already = EXCLUDED.solved_already, solved_note = EXCLUDED.solved_note, "
        "basis = EXCLUDED.basis, risks = EXCLUDED.risks, included = EXCLUDED.included",
        (idea_uuid, masked["how"], masked["needs"], answers.solved_already, masked["solved_note"], answers.basis,
         masked["risks"], included),
    )  # fmt: skip
    before = sharer_worth(conn, idea_uuid)
    after = answers.worth if answers.worth.as_json() else None
    if replace_worth:
        conn.execute("DELETE FROM idea_worth WHERE idea_uuid = %s AND by_side = 'sharer'", (idea_uuid,))
    elif (before.as_json() if before else None) == (after.as_json() if after else None):
        return  # a shared idea: a new row only when the figures changed
    if after is None and replace_worth:
        return
    w = after or Worth()

    def lo(m: str) -> float | None:
        r = getattr(w, m)
        return r.low if r is not None else None

    def hi(m: str) -> float | None:
        r = getattr(w, m)
        return r.high if r is not None else None

    def ab(m: str) -> bool | None:
        return about(getattr(w, m))

    conn.execute(
        "INSERT INTO idea_worth (idea_uuid, by_side, by_code, hours_low, hours_high, hours_about, cost_low, "
        "cost_high, cost_about, revenue_low, revenue_high, revenue_about, outside_tools) "
        "VALUES (%s, 'sharer', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (idea_uuid, code, lo("hours_month"), hi("hours_month"), ab("hours_month"), lo("cost_month"),
         hi("cost_month"), ab("cost_month"), lo("revenue_month"), hi("revenue_month"), ab("revenue_month"),
         w.outside_tools),
    )  # fmt: skip


def _own_draft(conn: Conn, key: str, user_id: str) -> tuple[dict[str, Any], str]:
    idea, code = own.load_own(conn, key, user_id, lock=True)
    if idea["status"] == "merged":
        raise Refused(409, "merged", "This draft was merged into another idea. Nothing else to send.")
    if idea["status"] != "draft":
        raise Refused(
            409,
            "not_a_draft",
            "This idea has been sent. Change it from its page while it’s open to changes.",
        )
    return idea, code


def put_draft(conn: Conn, key: str, user_id: str, body: Any, *, now: dt.datetime) -> dict[str, Any]:
    """`PUT /drafts/:id/fix` with the `Fix` fields → `Fix` with `ready_count`. "Add my fix" sends `included: true`
    (the default) and needs how; "Close, and keep what you wrote" sends `included: false` and needs nothing."""
    if not isinstance(body, dict):
        raise Refused(400, "body_required", "Something went wrong. Try again.")
    included = body.get("included", True) is not False
    answers = read_answers(body, need_how=included)
    with conn.transaction():
        idea, code = _own_draft(conn, key, user_id)
        uid = str(idea["id"])
        store(conn, uid, user_id, code, answers, included=included, stem="draft", replace_worth=True)
        conn.execute("UPDATE ideas SET saved_at = %s WHERE id = %s", (now, uid))
        out = view(conn, uid, started_too=True)
        assert out is not None
        own.audit(
            conn,
            user_id,
            "idea.fix",
            idea,
            {"included": out["included"], "ready_count": out["ready_count"]},
        )
        return out


def delete_draft(conn: Conn, key: str, user_id: str, *, now: dt.datetime) -> dict[str, Any]:
    """`DELETE /drafts/:id/fix` ("Remove"): the fix, its figures, and what was hidden from its words go."""
    with conn.transaction():
        idea, _code = _own_draft(conn, key, user_id)
        uid = str(idea["id"])
        gone = conn.execute(
            "DELETE FROM idea_fix WHERE idea_uuid = %s RETURNING idea_uuid", (uid,)
        ).fetchone()
        conn.execute("DELETE FROM idea_worth WHERE idea_uuid = %s AND by_side = 'sharer'", (uid,))
        adapters.forget_words(conn, uid, list(source_ids(uid, "draft").values()))
        if gone is not None:
            conn.execute("UPDATE ideas SET saved_at = %s WHERE id = %s", (now, uid))
            own.audit(conn, user_id, "idea.fix_removed", idea, {})
        return {"fix": None, "part": {"rail": "Optional"}}
