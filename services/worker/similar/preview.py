"""The idea preview (A-API.idea-preview, C-PREVIEW, L-SIMILAR.rules/10): a quick look at someone else's shared idea.

Who sees what (DEC-104, P-PRODUCT.privacy, non-negotiable 7):
- Everyone signed in: the masked title, status, area, city, when it was shared, the lead and crew, one masked
  sentence of the short summary ("The problem, in their words") and "They're looking for". Never the sharer's
  raw words, messages, answers or files.
- Names show unless that person hid theirs from the Wall in Profile; the review desk and the Ones Committee always
  see them.
- `compare` (How often, Who it affects, What it's worth) is for the review desk and the Ones Committee only; with
  `compare_with` it also carries the same three rows for the idea the reviewer is looking at ("Next to Kavya's").

Masking: text here is already the masked copy (L-HIDE.rules/3). It is masked again with the pattern rules
(`mask_text`, a thin adapter until L-HIDE's builder lands) and the summary sentence must then pass the tag, pattern
and name checks (`views.common.checked_summary`), or the placeholder is shown instead.

`idea_preview(conn, idea, viewer=..., compare_with=...)` is the one builder: lane F's crew cards and lane B's
reviewer pages reuse it. It returns None where the caller should answer 404.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from core.crypto import keyed_hash
from core.db import Conn
from pii.patterns import scan
from pii.tagger import TAG_RE

IDEA_REF = re.compile(r"^IDEA-[0-9]{4}-[0-9]{6}$")
# The review desk and the Ones Committee (E-ENUMS.roles; the old committee roles until the cleanup migration).
DESK_ROLES = ("reviewer", "committee", "core_committee", "core_chair")
SUMMARY_PENDING = "A short summary is on its way."
HIDDEN_NAME = "A colleague"
FACES = 3
SENTENCE_MAX = 240

# Pattern ID -> the masked label (L-HIDE kinds: "Folio ••••89"). Only `block` patterns are masked.
MASK_LABEL = {
    "pan": "PAN", "aadhaar": "Aadhaar", "mobile": "Phone", "email": "Email", "bank_account": "Account",
    "card": "Account", "folio": "Folio", "demat_in": "Account", "demat_16": "Account", "pran": "Account",
    "dob": "Date",
}  # fmt: skip
_PREFER = (
    "folio",
    "bank_account",
    "pan",
    "aadhaar",
    "card",
    "demat_in",
    "demat_16",
    "pran",
    "email",
    "dob",
    "mobile",
)


@dataclass(frozen=True)
class Viewer:
    """Who is looking, as the worker reads it from the database (the web app vouches only for the user ID)."""

    user_id: str | None
    codes: tuple[str, ...] = ()
    desk: bool = False

    @classmethod
    def of(cls, conn: Conn, user_id: str | None) -> Viewer:
        if not user_id or not _is_uuid(user_id):
            return cls(None)
        codes = tuple(
            str(r["contributor_code"])
            for r in conn.execute(
                "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
            ).fetchall()
        )
        desk = (
            conn.execute(
                "SELECT 1 FROM role_grants WHERE user_id = %s AND role = ANY(%s) AND valid_from <= now() "
                "AND (valid_to IS NULL OR valid_to > now()) LIMIT 1",
                (user_id, list(DESK_ROLES)),
            ).fetchone()
            is not None
        )
        return cls(user_id, codes, desk)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


# ---- masking (thin adapter until L-HIDE's builder lands) -----------------------------------------------------


def mask_text(text: str | None) -> str:
    """Every customer detail the pattern rules block becomes "<kind> ••••<last two>"; tags become "someone"."""
    if not text:
        return ""
    out, last = [], 0
    # One span can match two rules ("folio 7700012389" is also a phone shape): the rule with context wins.
    for m in sorted(
        scan(text, kfin_domains=[]),
        key=lambda m: (
            m.start,
            -m.end,
            _PREFER.index(m.pattern_id) if m.pattern_id in _PREFER else len(_PREFER),
        ),
    ):
        if m.action != "block" or m.start < last:
            continue
        value = text[m.start : m.end]
        label = MASK_LABEL.get(m.pattern_id, "Detail")
        before = text[last : m.start]
        # "folio 7700012389" -> "folio ••••89", not "folio Folio ••••89".
        said = before.rstrip().rsplit(" ", 1)[-1].casefold() == label.casefold()
        out.append(before)
        out.append(f"••••{value[-2:]}" if said else f"{label} ••••{value[-2:]}")
        last = m.end
    out.append(text[last:])
    return TAG_RE.sub("someone", "".join(out))


def first_sentence(text: str | None) -> str:
    """The first sentence, at most SENTENCE_MAX characters (cut at a word)."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    if len(sentence) > SENTENCE_MAX:
        sentence = sentence[:SENTENCE_MAX].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return sentence


def checked_sentence(conn: Conn, text: str | None) -> str | None:
    """One masked sentence that passes the tag, pattern and name checks, or None."""
    from views.common import checked_summary  # the shared check, cached for ten minutes

    sentence = first_sentence(mask_text(text))
    return checked_summary(conn, sentence) if sentence else None


# ---- people ----------------------------------------------------------------------------------------------------


def initials(name: str) -> str:
    words = [w for w in name.split() if w[:1].isalpha()]
    if not words:
        return ""
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


def hidden_person(code: str) -> dict[str, Any]:
    """Someone who hid their name from the Wall (or has left): no name, no user ID, a stable opaque ID."""
    return {
        "id": "p" + keyed_hash("person-ref", code).hex()[:12],
        "name": HIDDEN_NAME,
        "first_name": HIDDEN_NAME,
        "initials": "",
    }


def person_refs(conn: Conn, codes: list[str], *, names_always: bool) -> dict[str, dict[str, Any]]:
    """PersonRef per contributor code. `names_always` for the review desk and the committee (DEC-104)."""
    if not codes:
        return {}
    rows = conn.execute(
        "SELECT m.contributor_code, u.id, u.name, u.first_name, u.area, u.location, u.active, "
        "coalesce(ps.show_name_on_wall, true) AS show_name FROM contributor_map m JOIN users u ON u.id = m.user_id "
        "LEFT JOIN person_settings ps ON ps.user_id = u.id WHERE m.contributor_code = ANY(%s)",
        (codes,),
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not names_always and not (r["show_name"] and r["active"]):
            continue
        name = str(r["name"] or "").strip()
        if not name:
            continue
        ref: dict[str, Any] = {
            "id": str(r["id"]),
            "name": name,
            "first_name": str(r["first_name"] or name.split()[0]),
            "initials": initials(name),
        }
        if r["area"]:
            ref["area"] = str(r["area"])
        if r["location"]:
            ref["city"] = str(r["location"])
        out[str(r["contributor_code"])] = ref
    return {c: out.get(c) or hidden_person(c) for c in codes}


def crew_codes(conn: Conn, idea_uuid: str, sharer_code: str) -> tuple[str, list[str]]:
    """(lead, active crew with the lead first). An idea with no crew rows yet is led by its sharer alone."""
    rows = conn.execute(
        "SELECT contributor_code, role FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL "
        "ORDER BY (role = 'lead') DESC, joined_at, id",
        (idea_uuid,),
    ).fetchall()
    codes = [str(r["contributor_code"]) for r in rows]
    lead = next((str(r["contributor_code"]) for r in rows if r["role"] == "lead"), sharer_code)
    if lead not in codes:
        codes.insert(0, lead)
    return lead, codes


# ---- the comparison (reviewers only) -----------------------------------------------------------------------------


def rupees(amount: Decimal | float | int) -> str:
    """₹ with Indian digit grouping: 2500000 -> "₹25,00,000"."""
    whole = int(Decimal(str(amount)).quantize(Decimal(1)))
    digits = str(abs(whole))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    return ("-" if whole < 0 else "") + "₹" + digits


def _number(value: Decimal | float | int) -> str:
    d = Decimal(str(value))
    return str(int(d)) if d == d.to_integral_value() else f"{d.normalize():f}"


def _range(low: Any, high: Any, unit: str, money: bool) -> str | None:
    if low is None and high is None:
        return None
    fmt = rupees if money else _number
    if low is not None and high is not None and Decimal(str(high)) != Decimal(str(low)):
        return f"{fmt(low)} to {fmt(high)} {unit}"
    return f"about {fmt(low if low is not None else high)} {unit}"


def worth_line(row: dict[str, Any] | None) -> str:
    """One line for "What it's worth": "Saves 70 to 150 hours a month and about ₹40,000 a month"."""
    if not row:
        return "Not given"
    saves = [
        x
        for x in (
            _range(row.get("hours_low"), row.get("hours_high"), "hours a month", False),
            _range(row.get("cost_low"), row.get("cost_high"), "a month", True),
        )
        if x
    ]
    earns = _range(row.get("revenue_low"), row.get("revenue_high"), "a month", True)
    parts = []
    if saves:
        parts.append("Saves " + " and ".join(saves))
    if earns:
        parts.append(("earns " if parts else "Earns ") + earns)
    return "; ".join(parts) or "Not given"


def compare_rows(conn: Conn, idea: dict[str, Any]) -> dict[str, str]:
    worth = conn.execute(
        "SELECT hours_low, hours_high, cost_low, cost_high, revenue_low, revenue_high FROM idea_worth "
        "WHERE idea_uuid = %s ORDER BY at DESC, id DESC LIMIT 1",
        (idea["id"],),
    ).fetchone()
    out = {"worth": worth_line(dict(worth) if worth else None)}
    often = mask_text(idea.get("often")).strip()
    if often:
        out["often"] = often
    affects = [str(a) for a in idea.get("affects") or [] if str(a).strip()]
    if affects:
        out["who"] = ", ".join(affects)
    return out


# ---- the preview ---------------------------------------------------------------------------------------------------

_IDEA_COLUMNS = (
    "id, idea_id, contributor_code, status, kind, title, summary, often, city, area, affects, helper_picks, "
    "helper_text, shared_at, canvas"
)


def find_idea(conn: Conn, key: str) -> dict[str, Any] | None:
    """An idea by its IDEA- reference or its row ID."""
    if IDEA_REF.match(key):
        row = conn.execute(f"SELECT {_IDEA_COLUMNS} FROM ideas WHERE idea_id = %s", (key,)).fetchone()  # noqa: S608
    elif _is_uuid(key):
        row = conn.execute(f"SELECT {_IDEA_COLUMNS} FROM ideas WHERE id = %s", (key,)).fetchone()  # noqa: S608
    else:
        return None
    return dict(row) if row else None


def can_preview(idea: dict[str, Any], viewer: Viewer) -> bool:
    """Shared ideas only. A withdrawn one stays visible to its sharer, the review desk and the committee."""
    if not idea.get("idea_id") or idea.get("shared_at") is None or idea["status"] == "draft":
        return False
    if idea["status"] == "withdrawn":
        return viewer.desk or idea["contributor_code"] in viewer.codes
    return True


def _iso(value: dt.datetime | None) -> str | None:
    return value.astimezone(dt.UTC).isoformat().replace("+00:00", "Z") if value else None


def looking_for(conn: Conn, idea: dict[str, Any]) -> str | None:
    """ "They're looking for": the sharer's own line if it passes the checks, else the picks they chose."""
    text = checked_sentence(conn, idea.get("helper_text"))
    if text:
        return text
    picks = [str(p) for p in idea.get("helper_picks") or [] if str(p).strip()]
    return ", ".join(picks) if picks else None


def in_their_words(conn: Conn, idea: dict[str, Any]) -> str:
    """One masked sentence of the short summary (DEC-104: never the sharer's raw words)."""
    summary = idea.get("summary") or (idea.get("canvas") or {}).get("neutral_summary")
    return checked_sentence(conn, summary) or SUMMARY_PENDING


def idea_preview(
    conn: Conn, idea_key: str, *, viewer: Viewer, compare_with: str | None = None
) -> dict[str, Any] | None:
    """IdeaPreview (E-ENTITIES) of `idea_key` (IDEA- reference or row ID) for `viewer`, or None (answer 404)."""
    idea = find_idea(conn, idea_key)
    if idea is None or not can_preview(idea, viewer):
        return None
    ref = str(idea["idea_id"])
    lead_code, codes = crew_codes(conn, str(idea["id"]), str(idea["contributor_code"]))
    people = person_refs(conn, codes, names_always=viewer.desk)
    out: dict[str, Any] = {
        "id": ref,
        "title": mask_text(idea.get("title")).strip() or ref,
        "status": idea["status"],
        "area": str(idea.get("area") or ""),
        "city": str(idea.get("city") or ""),
        "shared_at": _iso(idea.get("shared_at")),
        "lead": people[lead_code],
        "crew_faces": [people[c] for c in codes[:FACES]],
        "crew_count": len(codes),
        "in_their_words": in_their_words(conn, idea),
        "hue": int(ref[-6:]) % 2 + 1,
    }
    wanted = looking_for(conn, idea)
    if wanted:
        out["looking_for"] = wanted
    if viewer.desk:
        out["compare"] = compare_rows(conn, idea)
        other = find_idea(conn, compare_with) if compare_with else None
        if other is not None and other["id"] != idea["id"] and other.get("idea_id"):
            owner = person_refs(conn, [str(other["contributor_code"])], names_always=True)
            out["compare_with"] = {
                "id": str(other["idea_id"]),
                "title": mask_text(other.get("title")).strip() or str(other["idea_id"]),
                "owner": owner[str(other["contributor_code"])],
                **compare_rows(conn, other),
            }
    return out
