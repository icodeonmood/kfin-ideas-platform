"""Who would help (S-05 part 6, E-ENTITIES Draft `helpers?: { picks, text? }`, E-ENUMS.sorting `helper`):
`PUT /drafts/:id/helpers` (A-API.drafts) and the same answer on the edit page's Save (`submit.edit`).

The picks come from the configured list (`rules/sorting.md` `helpers`: "Someone at a branch", "Someone in
operations", "Someone from tech", "Someone who knows the rules", "Data or reports"), matched without regard to case
and kept in the list's spelling, each once. A pick not on the list is refused: the chips are the list. The person's
own words ("Who would help, in your own words") are up to 140 characters (V-FIELDS.checkit/10) and go through hide
like any part (DEC-103): only the masked copy is kept. It shows on Find your crew as "They're looking for", so it is
optional and never holds Submit (L-SUBMIT.pre/6).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from submit import adapters, config, own
from submit.errors import Refused
from submit.words import join

TEXT_MAX = 140  # V-FIELDS.checkit/10
NOT_SAID = "Not said"
WRONG = "Something went wrong. Try again."  # only a client off the list sends this


def read(raw: Any, li: config.Lists, *, at: str = "") -> tuple[list[str], str | None]:
    """`{picks, text?}` → (the picks in the list's spelling, the words as typed or None)."""
    if not isinstance(raw, dict):
        raise Refused(400, "body_required", "Something went wrong. Try again.")
    picks_raw = raw.get("picks", [])
    if picks_raw is None:
        picks_raw = []
    if not isinstance(picks_raw, list):
        raise Refused(422, "field_needed", WRONG, f"{at}picks")
    picks: list[str] = []
    for p in picks_raw:
        label = config._match(p, li.helpers)
        if label is None:
            raise Refused(422, "field_needed", WRONG, f"{at}picks")
        if label not in picks:
            picks.append(label)
    text = raw.get("text")
    if text is not None and not isinstance(text, str):
        raise Refused(422, "field_needed", WRONG, f"{at}text")
    words = " ".join((text or "").split()) or None
    if words is not None and len(words) > TEXT_MAX:
        raise Refused(422, "field_needed", f"Keep it to {TEXT_MAX} characters.", f"{at}text")
    return picks, words


def mask(
    conn: Conn, idea_uuid: str, user_id: str, words: str | None, *, source_id: str, stored: str | None = None
) -> str | None:
    """The masked copy of the person's own words; emptied words take what was hidden from them along. Words sent
    back exactly as the stored masked copy are that copy, and nothing is masked or written again (BLD-C141)."""
    if not words:
        adapters.forget_words(conn, idea_uuid, [source_id])
        return None
    if words == stored:
        return words
    return adapters.mask_text(conn, idea_uuid, words, by=user_id, source_id=source_id).text


def line(picks: list[str], text: str | None) -> str:
    """The Send part's row (S-05 part 7): "Not said", or the picks and the person's own words."""
    words = " ".join((text or "").split())
    return join([*picks, words] if words else picks) or NOT_SAID


def view(idea: dict[str, Any]) -> dict[str, Any]:
    picks = list(idea.get("helper_picks") or [])
    text = idea.get("helper_text")
    return {
        "picks": picks,
        "text": text,
        "line": line(picks, text),
        "part": {"rail": "Added" if picks or text else "Optional"},
    }


def put_draft(conn: Conn, key: str, user_id: str, body: Any, *, now: dt.datetime) -> dict[str, Any]:
    """`PUT /drafts/:id/helpers` `{picks, text?}` → `{picks, text, line, part}`."""
    li = config.lists()
    picks, words = read(body, li)
    with conn.transaction():
        idea, _code = own.load_own(conn, key, user_id, lock=True)
        if idea["status"] == "merged":
            raise Refused(409, "merged", "This draft was merged into another idea. Nothing else to send.")
        if idea["status"] != "draft":
            raise Refused(
                409,
                "not_a_draft",
                "This idea has been sent. Change it from its page while it’s open to changes.",
            )
        uid = str(idea["id"])
        text = mask(
            conn, uid, user_id, words, source_id=f"{uid}:draft:helpers", stored=idea.get("helper_text")
        )
        if picks != list(idea.get("helper_picks") or []) or text != idea.get("helper_text"):
            conn.execute(
                "UPDATE ideas SET helper_picks = %s, helper_text = %s, saved_at = %s WHERE id = %s",
                (picks, text, now, uid),
            )
            own.audit(
                conn, user_id, "idea.helpers", idea, {"picks": len(picks), "own_words": text is not None}
            )
        return view({"helper_picks": picks, "helper_text": text})
