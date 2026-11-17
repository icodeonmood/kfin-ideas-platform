"""Other lanes' modules, reached from lane C's sorting and sending through this one file (SHIP_PLAN §5a), so a change
on their side touches one place here.

- Withdraw and restore (`L-SUBMIT.withdraw`) have ONE implementation, lane E's `ideapage.withdraw` (branch
  `e/idea-page-my-ideas-2`, landing on `main` on Tue 17 Nov). Lane E's routes serve `POST /ideas/:id/withdraw` and
  `/restore`. Until that module is on `main`, `withdraw` and `restore` here raise `NotYetAvailable`.
  TODO(BLD-C086): drop the stub branch once `ideapage.withdraw` is on main.
- Lane C's part of a restore (`L-SUBMIT.withdraw/3`, `L-SUBMIT.send/3`): the review clock restarts from the restore
  with the boards' reading of decide-by, and "Checked and matched" runs again. `install_hooks` plugs `on_restored`
  into lane E's `ON_RESTORED_HOOK`.
- Hidden details (`L-HIDE`, lane C's `hide` package): an edit's new text is masked before it is stored. Until the
  package is on main, the shared patterns mask what they find (kind + •••• + last two characters, DEC-103).
- Similar ideas (`L-SIMILAR`, lane C's `similar` package): matching runs again when the summary changes, and in the
  check after sending. Until the package is on main this finds nothing.
- Amounts in any Indian form (`L-WORTH/1`, lane B's `desk.worth.parse`) for the fix's worth on the edit page.
"""

from __future__ import annotations

import datetime as dt
import importlib
import re
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import scan

log = get_logger("submit.adapters")


class NotYetAvailable(Exception):
    """The other lane's module is not on this branch yet."""


def _module(name: str) -> ModuleType | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


# --- Withdraw and restore: lane E ------------------------------------------------------------------------------


def withdraw(conn: Conn, key: str, user_id: str, reason: str | None = None) -> dict[str, Any]:
    mod = _module("ideapage.withdraw")
    if mod is None:
        raise NotYetAvailable("ideapage.withdraw")
    result: dict[str, Any] = mod.withdraw(conn, key, user_id, reason)
    return result


def restore(conn: Conn, key: str, user_id: str) -> dict[str, Any]:
    mod = _module("ideapage.withdraw")
    if mod is None:
        raise NotYetAvailable("ideapage.withdraw")
    result: dict[str, Any] = mod.restore(conn, key, user_id)
    return result


def on_restored(conn: Conn, idea_uuid: str) -> None:
    """Lane E's restore has set the idea back to `checking` (same reference, inside its transaction). The review
    clock restarts from now with the boards' decide-by, and the check runs again, which moves it to the desk."""
    from jobs.runner import enqueue
    from submit import clock, config

    row = conn.execute("SELECT id, idea_id FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
    if row is None or row["idea_id"] is None:
        return
    now = dt.datetime.now(dt.UTC)
    p = config.promises()
    due = clock.decide_by(now, p)
    conn.execute(
        "UPDATE ideas SET decide_by = %s, edit_closes_at = %s WHERE id = %s",
        (due, clock.edit_closes(now, p), idea_uuid),
    )
    clock.start_review_clock(conn, str(row["idea_id"]), now, due)
    enqueue(conn, "submit.check", {"idea_uuid": idea_uuid}, dedupe_key=f"submit.check:{idea_uuid}")


def install_hooks() -> bool:
    """Plug lane C's restore step into lane E's withdraw module, when it is there. True when installed."""
    mod = _module("ideapage.withdraw")
    if mod is None or not hasattr(mod, "ON_RESTORED_HOOK"):
        return False
    mod.ON_RESTORED_HOOK = on_restored  # type: ignore[attr-defined]
    return True


# --- Hidden details: lane C's hide -----------------------------------------------------------------------------

HIDDEN_KIND = {
    "folio": "folio",
    "pan": "pan",
    "mobile": "phone",
    "email": "email",
    "bank_account": "account",
    "card": "account",
    "demat_in": "account",
    "demat_16": "account",
    "pran": "account",
    "aadhaar": "aadhaar",
}
MASK_LABEL = {
    "folio": "Folio",
    "pan": "PAN",
    "phone": "Phone",
    "email": "Email",
    "account": "Account",
    "aadhaar": "Aadhaar",
}


@dataclass(frozen=True)
class Masked:
    text: str
    found: list[dict[str, Any]]  # [{kind, masked, start, end}] positions in the person's own text


def mask_text(conn: Conn, idea_uuid: str, text: str, *, source: str, source_id: str) -> Masked:
    """The person's new text with customers' details hidden (DEC-103). Lane C's `hide.mask_own_text` when it is on
    main; until then the shared patterns. Nothing here logs or returns the hidden values."""
    mod = _module("hide")
    if mod is not None and hasattr(mod, "mask_own_text"):
        masked, spans = mod.mask_own_text(conn, idea_uuid, text, source=source, source_id=source_id)
        return Masked(str(masked), list(spans))
    found: list[dict[str, Any]] = []
    out = text
    for m in sorted(
        scan(text, kfin_domains=get_settings().kfin_domains), key=lambda m: m.start, reverse=True
    ):
        if m.action != "block":
            continue
        kind = HIDDEN_KIND.get(m.pattern_id)
        if kind is None:
            continue
        value = text[m.start : m.end]
        tail = re.sub(r"\W", "", value)[-2:]
        masked = f"{MASK_LABEL[kind]} ••••{tail}"
        out = out[: m.start] + masked + out[m.end :]
        found.append({"kind": kind, "masked": masked, "start": m.start, "end": m.end})
    return Masked(out, list(reversed(found)))


# --- Similar ideas: lane C's similar ---------------------------------------------------------------------------


def find_similar(conn: Conn, idea_uuid: str, *, found_while: str) -> int | None:
    """Run matching for a shared idea; the number of similar ideas linked, or None while matching is not on main."""
    mod = _module("similar")
    if mod is None or not hasattr(mod, "match_shared"):
        return None
    return int(mod.match_shared(conn, idea_uuid, found_while=found_while))


# --- Amounts: lane B's worth -----------------------------------------------------------------------------------

_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|l|crores?|cr|k|thousand)?", re.IGNORECASE)
_SCALE = {
    "lakh": 1e5,
    "lakhs": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "l": 1e5,
    "crore": 1e7,
    "crores": 1e7,
    "cr": 1e7,
}
_SCALE.update({"k": 1e3, "thousand": 1e3})


def parse_range(measure: str, raw: object) -> tuple[float, float | None] | None:
    """'70 to 150', '2 lakh', '2L', '2,00,000' -> (low, high or None). Lane B's parser when it is on main."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return (float(raw), None) if raw >= 0 else None
    if isinstance(raw, dict):
        low, high = raw.get("low"), raw.get("high")
        if not isinstance(low, int | float) or low < 0:
            return None
        if high is not None and (not isinstance(high, int | float) or high < low):
            return None
        return float(low), float(high) if high is not None else None
    if not isinstance(raw, str) or len(raw) > 80:
        return None
    mod = _module("desk.worth")
    if mod is not None and hasattr(mod, "parse"):
        r = mod.parse(measure, raw)
        return (float(r.low), float(r.high) if r.high is not None else None) if r is not None else None
    found = [
        float(n) * _SCALE.get((unit or "").lower(), 1.0) for n, unit in _NUMBER.findall(raw.replace(",", ""))
    ]
    if not found or len(found) > 2:
        return None
    low = found[0]
    high = found[1] if len(found) == 2 else None
    if high is not None and high < low:
        return None
    return low, high
