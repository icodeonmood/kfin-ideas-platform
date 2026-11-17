"""Other lanes' modules, reached from lane C's sorting and sending through this one file (SHIP_PLAN §5a), so a change
on their side touches one place here. Each is a guarded import: the real entry point when its package is on main,
a stated fallback until then (BLD-C038, BLD-C087).

- Restore (`L-SUBMIT.withdraw/3`, `L-SUBMIT.send/3`): withdraw and restore are lane E's (`ideapage.withdraw`, which
  serves `POST /ideas/:id/withdraw` and `/restore`). Lane C's part of a restore is `on_restored`: the review clock
  restarts from the restore with the boards' reading of decide-by, and "Checked and matched" runs again.
  `install_hooks` plugs it into lane E's `ON_RESTORED_HOOK`.
- Hidden details (`L-HIDE`, branch c/hide): `mask_text` calls `hide.hide_message(conn, idea_uuid, text, *, by,
  source="edit", source_id, gatekeeper=True)` for an edit's new words, and `hide.hide_text(conn, idea_uuid, text, *,
  by, source="edit")` for the final pass over stored text. Hide stores each value in the vault under the idea's hide
  scope `DRAFT-<idea uuid>`, writes `hidden_details` and seals the person's own words, so callers write nothing
  else. Until the package is on main the shared patterns do the same here (kind + •••• + last two characters,
  DEC-103). Nothing in lane C's sorting and sending purges or re-keys that scope: it outlives the send.
- Similar ideas (`L-SIMILAR`, branch c/similar): `find_similar` calls `similar.match_shared(conn, idea_uuid, *,
  found_while) -> int`, where -1 means matching failed (recorded and retried there). Both that and "not on main" come
  back as None, "couldn't check", never as zero matches (`L-SIMILAR.failure`).
- Listen (`L-LISTEN`, branch c/sarvam): `prefetch_listen` calls `speech.listen.enqueue_prefetch(conn, idea_uuid)`
  after a send, a deduped `listen.prefetch` job inside the send's transaction. Until then nothing is queued.

Amounts in any Indian form (`L-WORTH/1`) are not an adapter: lane B's `desk.worth` is on main, and `submit.fix`
imports its one quantity reader directly.

Nothing here logs or returns a hidden value: only kinds, counts, spans and IDs.
"""

from __future__ import annotations

import datetime as dt
import importlib
import re
import uuid
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from onepc.context import seal_text
from pii import vault
from pii.patterns import scan

log = get_logger("submit.adapters")


def _module(name: str) -> ModuleType | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


# --- Restore: lane E -------------------------------------------------------------------------------------------


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
VAULT_TYPE = {
    "folio": "FOLIO_NUMBER",
    "pan": "PAN",
    "phone": "PHONE",
    "email": "EMAIL",
    "account": "ACCOUNT_NUMBER",
    "aadhaar": "AADHAAR",
}  # as c/hide's hide.core.VAULT_TYPE
# One span can match two rules ("folio 9876543210" is also a phone shape, "a/c 4111…" also a card): the longer span
# wins, then the rule with context, in `similar.preview`'s order.
PREFER = (
    "folio",
    "bank_account",
    "pan",
    "aadhaar",
    "card",
    "demat_in",
    "demat_16",
    "pran",
    "email",
    "mobile",
)


@dataclass(frozen=True)
class Found:
    kind: str
    start: int
    end: int
    masked: str


@dataclass(frozen=True)
class Masked:
    text: str  # the masked copy: the only one anyone else gets
    found: list[dict[str, Any]]  # [{start, end, kind, ...}] in the person's own text; never a value
    hidden_count: int


def pattern_find(text: str) -> list[Found]:
    """Every customer detail the shared patterns block, in order, none overlapping another kept before it."""
    hits = sorted(
        (m for m in scan(text, kfin_domains=get_settings().kfin_domains) if m.action == "block"),
        key=lambda m: (
            m.start,
            -m.end,
            PREFER.index(m.pattern_id) if m.pattern_id in PREFER else len(PREFER),
        ),
    )
    found: list[Found] = []
    for m in hits:
        kind = HIDDEN_KIND.get(m.pattern_id)
        if kind is None or (found and m.start < found[-1].end):
            continue  # not a hidden kind (a date of birth stays; the gateway tags it), or overlapping one kept
        tail = re.sub(r"\W", "", text[m.start : m.end])[-2:]
        found.append(Found(kind, m.start, m.end, f"{MASK_LABEL[kind]} ••••{tail}"))
    return found


def pattern_mask(text: str) -> tuple[str, list[Found]]:
    """The masked copy by the shared patterns alone, substituted from the end so earlier spans stay put."""
    found = pattern_find(text)
    out = text
    for f in reversed(found):
        out = out[: f.start] + f.masked + out[f.end :]
    return out, found


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def mask_text(conn: Conn, idea_uuid: str, text: str, *, by: str, source_id: str | None) -> Masked:
    """Hide customers' details in a text written on a shared idea (DEC-103), inside the caller's transaction.

    `by` is the users.id of the person whose words these are. With a `source_id` (an edit's new words) the person's
    own words are sealed for them alone; without one (the check's final pass over text already stored) nothing is
    sealed. Either way each value goes to the vault under `DRAFT-<idea uuid>` with a `hidden_details` row, and the
    caller stores only the masked copy it gets back."""
    mod = _module("hide")
    if mod is not None and source_id is not None and hasattr(mod, "hide_message"):
        done = mod.hide_message(
            conn, idea_uuid, text, by=by, source="edit", source_id=source_id, gatekeeper=True
        )
        return Masked(str(done.masked), list(done.spans), int(done.hidden_count))
    if mod is not None and source_id is None and hasattr(mod, "hide_text"):
        masked, count = mod.hide_text(conn, idea_uuid, text, by=by, source="edit")
        return Masked(str(masked), [], int(count))
    out, found = pattern_mask(text)
    if source_id is not None:
        # The same words saved again (a draft's fix or helpers keep one source id per field) replace what was hidden
        # from them before, as hide's own re-run does; an edit's ids are new on every save, so nothing goes there.
        conn.execute(
            "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = 'edit' AND source_id = %s",
            (idea_uuid, source_id),
        )
    if not found:
        # Nothing hidden now: the masked copy is the words, so no sealed copy is kept.
        if source_id is not None:
            conn.execute(
                "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'edit' AND source_id = %s",
                (idea_uuid, source_id),
            )
        return Masked(out, [], 0)
    sid = source_id or str(uuid.uuid4())
    scope = f"DRAFT-{uuid.UUID(idea_uuid)}"
    spans: list[dict[str, Any]] = []
    for f in found:
        tag = vault.assign(conn, scope, VAULT_TYPE[f.kind], text[f.start : f.end])
        row = conn.execute(
            "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, "
            "vault_tag, found_by) VALUES (%s, 'edit', %s, %s, %s, %s, %s, %s, 'patterns') RETURNING id",
            (idea_uuid, sid, f.start, f.end, f.kind, f.masked, tag),
        ).fetchone()
        spans.append({"start": f.start, "end": f.end, "kind": f.kind, "hid": str(row["id"]) if row else None})
    if source_id is not None and _is_uuid(by):
        # The words as typed stay readable by the person alone (DEC-103, L-HIDE.rules/4); the context is c/hide's
        # ("<source>:<source_id>"), so its `own_words` opens them once it lands.
        conn.execute(
            "INSERT INTO idea_words_sealed (idea_uuid, source, source_id, owner_user_id, text_encrypted) "
            "VALUES (%s, 'edit', %s, %s, %s) ON CONFLICT (source, source_id) DO UPDATE SET "
            "text_encrypted = EXCLUDED.text_encrypted",
            (idea_uuid, source_id, by,
             seal_text("idea_words_sealed", "text_encrypted", f"edit:{source_id}", text, vault=True)),
        )  # fmt: skip
    return Masked(out, spans, len(found))


def forget_words(conn: Conn, idea_uuid: str, source_ids: list[str]) -> None:
    """A draft's fix removed, or one of its answers emptied: what was hidden from those words, and the words as typed,
    go with them (the vault keeps its values under the idea's scope, which nothing reads without a detail row)."""
    if not source_ids:
        return
    conn.execute(
        "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = 'edit' AND source_id = ANY(%s)",
        (idea_uuid, source_ids),
    )
    conn.execute(
        "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'edit' AND source_id = ANY(%s)",
        (idea_uuid, source_ids),
    )


# --- Similar ideas: lane C's similar ---------------------------------------------------------------------------


def find_similar(conn: Conn, idea_uuid: str, *, found_while: str) -> int | None:
    """Run matching for a shared idea (`found_while` "checking" at send, "later" after an edit): how many similar
    ideas are linked, or None for "couldn't check". c/similar's `match_shared` returns -1 when matching failed (it
    records the run and retries it, in a savepoint, never raising); that is not zero matches. None too while
    matching is not on main."""
    mod = _module("similar")
    if mod is None or not hasattr(mod, "match_shared"):
        return None
    n = int(mod.match_shared(conn, idea_uuid, found_while=found_while))
    return None if n < 0 else n


# --- Listen: c/sarvam ------------------------------------------------------------------------------------------


def prefetch_listen(conn: Conn, idea_uuid: str) -> bool:
    """After a send, queue the idea's Listen audio before anyone asks (c/sarvam's `speech.listen.enqueue_prefetch`,
    a deduped `listen.prefetch` job, inside the send's transaction). False while it is not on main."""
    mod = _module("speech.listen")
    if mod is None or not hasattr(mod, "enqueue_prefetch"):
        return False
    mod.enqueue_prefetch(conn, idea_uuid)
    return True
