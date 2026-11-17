"""Thin adapters to modules other lanes own (BLD-C113). Each mirrors the real module's names and types, so moving to
it is a one-line change.

- `hide_text`: lane C's hiding (`L-HIDE`, DEC-103) on branch c/hide. Until it lands, this masks with the level-1
  patterns (`pii.patterns.scan`): every value the patterns block becomes kind + •••• + its last two characters
  ("Folio ••••89"), and its position in the person's own text is kept as a span.
- `listen_script`: lane B's masked Listen script (`desk.reads.script_for`, branch b/1pc-review-3). Until it lands,
  `ScriptUnavailable` is raised and Listen answers 503, so the player falls back to the on-device voice.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from core.db import Conn
from pii.patterns import scan

# ---- hiding customers' details (DEC-103) ------------------------------------------------------------------

# Pattern ids to E-ENUMS.hidden kinds, and the word shown before the dots.
_KIND = {
    "folio": "folio",
    "pan": "pan",
    "mobile": "phone",
    "email": "email",
    "aadhaar": "aadhaar",
    "bank_account": "account",
    "card": "account",
    "demat_in": "account",
    "demat_16": "account",
    "pran": "account",
    "dob": "account",
}
_SHOWN = {
    "folio": "Folio",
    "pan": "PAN",
    "phone": "Phone",
    "email": "Email",
    "aadhaar": "Aadhaar",
    "account": "Account",
}
DOTS = "••••"


@dataclass(frozen=True)
class Hidden:
    """`text` is the masked copy, the only one anything else may see. `spans` are positions in the person's own
    (unmasked) text with the kind only, never the value (E-ENTITIES HiddenSpan)."""

    text: str
    spans: list[dict[str, Any]]
    count: int


def hide_text(text: str) -> Hidden:
    # TODO(c/hide): replace with `from hide import hide_text` once branch c/hide lands (L-HIDE, DEC-103). This
    # stand-in uses the level-1 patterns only; c/hide adds names in the same sentence and the gatekeeper.
    matches = sorted(
        (m for m in scan(text, kfin_domains=get_settings().kfin_domains) if m.action == "block"),
        key=lambda m: (m.start, -m.end),
    )
    kept: list[Any] = []
    for m in matches:  # overlapping matches: the earliest, longest one wins
        if kept and m.start < kept[-1].end:
            continue
        kept.append(m)
    spans = [{"start": m.start, "end": m.end, "kind": _KIND.get(m.pattern_id, "account")} for m in kept]
    out = text
    for m, span in zip(reversed(kept), reversed(spans), strict=True):
        value = text[m.start : m.end]
        out = out[: m.start] + f"{_SHOWN[span['kind']]} {DOTS}{value[-2:]}" + out[m.end :]
    return Hidden(text=out, spans=spans, count=len(kept))


_SHOWN_OTHER = {"ifsc": "IFSC", "arn": "ARN", "euin": "EUIN"}


def mask_for_service(masked: str) -> str:
    """The copy that may leave KFin for Sarvam (BLD-C117): the masked text with every other pattern hit masked too
    (a distributor's ARN or EUIN, an IFSC, a KFin address), in the same form, so `gateway.sarvam.check_masked`, which
    is the gateway's leak check, finds nothing. Not part of DEC-103: those are not customers' details, so the copy
    people read keeps them."""
    matches = sorted(scan(masked, kfin_domains=[]), key=lambda m: (m.start, -m.end))
    kept: list[Any] = []
    for m in matches:
        if kept and m.start < kept[-1].end:
            continue
        kept.append(m)
    out = masked
    for m in reversed(kept):
        kind = _KIND.get(m.pattern_id)
        shown = _SHOWN[kind] if kind else _SHOWN_OTHER.get(m.pattern_id, "Detail")
        out = out[: m.start] + f"{shown} {DOTS}{masked[m.start : m.end][-2:]}" + out[m.end :]
    return out


# ---- lane B's Listen script ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScriptPart:
    """Mirrors lane B's `desk.listen.ScriptPart`: one E-ENUMS.part, its spoken title and its masked text."""

    part: str
    title: str
    text: str
    seconds: float | None = None


@dataclass(frozen=True)
class Script:
    """Mirrors lane B's `desk.listen.Script`: parts in E-ENUMS.part order and a 16-character hash of the spoken
    text, which changes with any edit, answer or worth revision."""

    parts: tuple[ScriptPart, ...]
    version: str


class ScriptUnavailable(Exception):
    """Lane B's script is not in this build yet."""


class ScriptRefused(Exception):
    """A draft or a missing idea (lane B raises `desk.store.Refused(404)`)."""

    def __init__(self, status: int = 404) -> None:
        super().__init__(status)
        self.status = status


def spoken(title: str, text: str) -> str:
    """How each part is read, exactly as lane B's `desk.listen.spoken`."""
    try:
        real = importlib.import_module("desk.listen")
    except ImportError:
        return f"{title}. {text}"
    return str(real.spoken(title, text))


def listen_script(conn: Conn, ref: str, at: Any = None) -> Script:
    """The masked script for one idea (`ref` is an IDEA- reference or the idea's uuid)."""
    # TODO(b/1pc-review-3): lane B's `from desk.reads import script_for` once it lands on main; until then this
    # raises ScriptUnavailable and Listen answers 503 (the player uses the on-device voice).
    try:
        reads = importlib.import_module("desk.reads")
    except ImportError:
        raise ScriptUnavailable("script_unavailable") from None
    try:
        script = reads.script_for(conn, ref, at)
    except Exception as exc:
        status = getattr(exc, "status", None) or (exc.args[0] if exc.args else None)
        if type(exc).__name__ == "Refused" and status == 404:
            raise ScriptRefused(404) from None
        raise
    return Script(
        parts=tuple(ScriptPart(p.part, p.title, p.text, getattr(p, "seconds", None)) for p in script.parts),
        version=str(script.version),
    )
