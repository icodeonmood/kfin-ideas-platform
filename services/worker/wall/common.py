"""What every reader in this package shares: the pack's error shape, the Wall's one filter hook, the name rule, the
public-text guard, and the labels the server writes so every screen agrees (A-API.conventions/2, /6).

Copy comes from the pack (`reference/copy/`, `V-FIELDS`); nothing here invents a sentence a person reads except
where a line says which pack line it follows.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from core.config import get_settings
from core.logging import get_logger
from onepc.enums import TIER_NAME, wall_labels
from pii.patterns import scan
from pii.tagger import TAG_RE

log = get_logger("wall")

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# V-FIELDS.one (S-ONE, S-H6). `{n}` and `{near}` are filled by the server.
MSG_OUT_OF_RANGE = "Pick a number from 1 to 999."
MSG_TAKEN = "No. {n} is taken. Free numbers near it: {near}."
MSG_YOURS = "No. {n} is yours for good."
MSG_BRIEF = "Keep it to one sentence, up to 140 characters."
MSG_SAVE_FAILED = "Couldn't save that. Try again."


class Refused(Exception):
    """A refusal in the pack's shape: `{error: {code, message, field?, …}}` (A-API.conventions/2). The code and
    any extra fields are IDs, numbers or the pack's own copy; a person's text never goes in one."""

    def __init__(
        self, status: int, code: str, message: str = "", *, field: str | None = None, **extra: Any
    ) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field, self.extra = status, code, message, field, extra

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field:
            err["field"] = self.field
        err.update(self.extra)
        return {"error": err}


# --- The Wall's one filter hook -----------------------------------------------------------------------------------


def on_wall_sql(alias: str = "i") -> str:
    """THE filter for "is this idea on the Wall at all". Every Wall query (Kindling, Just in, live fixes, the Ones'
    idea lines) goes through it, so lane A's audit-logged "Take off the Wall" (DEC-106, SHIP_PLAN §6.3) changes
    this one function and nothing else.

    It keeps out anything old code marked other than `org` (committee-only visibility is retired, DEC-106; keeping
    such rows off is the safe reading), anything merged into another idea (it shows as the survivor), and anything
    the review desk or an admin took off the Wall (`idea_off_wall`, 20261122100400; lane A, BLD-A212)."""
    return f"({alias}.visibility = 'org' AND {alias}.merged_into IS NULL AND NOT idea_off_wall({alias}.id))"


# --- Names (DEC-104) -------------------------------------------------------------------------------------------------

# Join a sharer from an idea's contributor code. Their name shows unless they hid it from the Wall in Profile.
SHARER_JOIN = (
    "LEFT JOIN contributor_map scm ON scm.contributor_code = {a}.contributor_code "
    "LEFT JOIN users su ON su.id = scm.user_id AND su.active "
    "LEFT JOIN person_settings sps ON sps.user_id = su.id"
)
SHARER_COLS = (
    "su.id AS sharer_id, su.name AS sharer_name, su.first_name AS sharer_first, su.area AS sharer_area, "
    "su.location AS sharer_city, coalesce(sps.show_name_on_wall, true) AS sharer_shown"
)


def initials(name: str) -> str:
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    if not words:
        return ""
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


def person_ref(
    user_id: Any, name: Any, first_name: Any = None, area: Any = None, city: Any = None
) -> dict[str, Any] | None:
    """E-ENTITIES PersonRef, or None when there is no one to name."""
    if user_id is None or not name:
        return None
    n = str(name)
    out: dict[str, Any] = {
        "id": str(user_id),
        "name": n,
        "first_name": str(first_name or n.split()[0]),
        "initials": initials(n),
    }
    if area:
        out["area"] = str(area)
    if city:
        out["city"] = str(city)
    return out


def sharer_ref(row: dict[str, Any]) -> dict[str, Any] | None:
    """The sharer as everyone may see them on the Wall: named, or None when they hid their name (DEC-104)."""
    if not row.get("sharer_shown"):
        return None
    return person_ref(
        row.get("sharer_id"), row.get("sharer_name"), row.get("sharer_first"), row.get("sharer_area"),
        row.get("sharer_city"),
    )  # fmt: skip


# --- Text everyone may read ---------------------------------------------------------------------------------------


def public_text(text: Any) -> str | None:
    """Text everyone sees (a title, a summary, a brief, a measured change) was masked before it was stored
    (L-HIDE.rules/3). Defence in depth: if it still holds a vault tag or anything the shared patterns would block,
    it is left out rather than shown (non-negotiables 4 and 7). Returns the text, or None."""
    if text is None:
        return None
    clean = str(text).strip()
    if not clean or TAG_RE.search(clean):
        return None
    if any(m.action == "block" for m in scan(clean, kfin_domains=get_settings().kfin_domains)):
        return None
    return clean


# --- Kinds on the Wall (E-ENUMS.kind OPEN default) ---------------------------------------------------------------


KIND_LABEL = wall_labels("kind")  # "Problem", "Fix", "Business idea" (S-WALL rows)


def plural(n: int, one: str, many: str | None = None) -> str:
    """ "1 colleague", "4 colleagues"; "1 One", "2 Ones"."""
    return f"{indian(n)} {one if n == 1 else (many or one + 's')}"


def wall_to(idea_id: str, back: str = "/wall") -> str:
    """Where a Wall row's title goes (S-WALL.rules/4): the idea's page, which shows "Back to the Wall" and returns
    to `back`, the Wall's own query (J-BROWSE/5). The idea page decides S-06 or S-09 by who opens it."""
    q = {"from": "wall"} | ({"back": back} if back != "/wall" else {})
    return f"/ideas/{idea_id}?{urlencode(q)}"


def wall_kind_sql(alias: str = "i") -> str:
    """A problem shared with a fix shows as "Fix" (E-ENUMS.kind OPEN default); old rows' problem_with_solution too."""
    return (
        f"CASE WHEN {alias}.kind = 'business_idea' THEN 'business_idea' "  # noqa: S608 (fragments are this package's own)
        f"WHEN {alias}.kind IN ('fix', 'problem_with_solution') THEN 'fix' "
        f"WHEN EXISTS (SELECT 1 FROM idea_fix wf WHERE wf.idea_uuid = {alias}.id AND wf.included) THEN 'fix' "
        "ELSE 'problem' END"
    )


# --- Ones ---------------------------------------------------------------------------------------------------------


def tier_label(tier: int) -> str:
    """ "Tier 4, Blaze" (S-WALL.ones, S-H6, S-ONE)."""
    return f"Tier {tier}, {TIER_NAME[tier]}"


# --- Dates as the screens say them (A-API.conventions/6) -----------------------------------------------------------


def _ist(ts: dt.datetime) -> dt.datetime:
    return ts.astimezone(IST)


def ago_label(ts: dt.datetime, now: dt.datetime) -> str:
    """ "2h ago", "Yesterday", "2 days ago" (S-WALL.justin "Shared"); "Just now" under an hour."""
    seconds = (now - ts).total_seconds()
    if seconds < 3600:
        return "Just now"
    if seconds < 24 * 3600:
        return f"{int(seconds // 3600)}h ago"
    days = (_ist(now).date() - _ist(ts).date()).days
    if days <= 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return day_label(ts, year=_ist(ts).year != _ist(now).year)


def short_ago(ts: dt.datetime, now: dt.datetime) -> str:
    """ "2d", "5h", "now": how long ago a One posted (C-ONES-FAN.card)."""
    seconds = max(0.0, (now - ts).total_seconds())
    if seconds < 3600:
        return "now" if seconds < 60 else f"{int(seconds // 60)}m"
    if seconds < 24 * 3600:
        return f"{int(seconds // 3600)}h"
    days = int(seconds // (24 * 3600))
    return f"{days}d" if days < 7 else f"{days // 7}w"


def day_label(ts: dt.datetime, *, year: bool = True) -> str:
    """ "1 Dec 2026" (S-ONE: "Founding One since 1 Nov 2026", "until 1 Dec 2026"); "18 Nov" without the year."""
    d = _ist(ts)
    return f"{d.day} {d:%b}" + (f" {d.year}" if year else "")


def month_label(ts: dt.date | dt.datetime) -> str:
    """ "November 2026" (S-WALL.ember)."""
    return f"{ts:%B} {ts.year}"


# --- Numbers as the screens say them -------------------------------------------------------------------------------


def indian(n: float | int | Decimal) -> str:
    """Indian digit grouping: 58,600; 1,24,000. Whole numbers; one decimal only below ten when it matters."""
    value = float(n)
    if abs(value) < 10 and value != int(value):
        return f"{value:.1f}"
    whole = round(value)
    sign, s = ("-" if whole < 0 else ""), str(abs(whole))
    if len(s) <= 3:
        return sign + s
    head, tail = s[:-3], s[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join([*groups, tail])


def rupees(amount: float | int | Decimal) -> tuple[str, str]:
    """(number, suffix) for an amount in rupees: ("₹24", "lakh"), ("₹1.2", "crore"), ("₹45,000", "").
    S-WALL.impact keeps "lakh" as a small suffix because it is part of the amount."""
    a = float(amount)

    def short(x: float) -> str:
        return str(int(x)) if abs(x - round(x)) < 0.05 else f"{x:.1f}"

    if a >= 1e7:
        return f"₹{short(a / 1e7)}", "crore"
    if a >= 1e5:
        return f"₹{short(a / 1e5)}", "lakh"
    return f"₹{indian(a)}", ""


def rupees_text(amount: float | int | Decimal) -> str:
    value, suffix = rupees(amount)
    return f"{value} {suffix}".strip()


# --- Promises (BLD-A181) ------------------------------------------------------------------------------------------


def promise(section: str, key: str, default: int) -> int:
    """A number the product promises, from the company repo's rules/promises.md (BLD-A181); the pack's value if the
    file cannot be read (logged by name only)."""
    from rules import load_rule

    try:
        return int(load_rule(get_settings().company_repo_path, "promises").data[section][key])
    except Exception:  # an unreadable rule must not break the Wall; the pack's own value stands in
        log.warning("wall.promise_default", rule_section=section, rule_key=key)
        return default


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
