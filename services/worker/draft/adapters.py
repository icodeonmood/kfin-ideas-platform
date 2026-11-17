"""Thin adapters to the other lane C modules L-DRAFT depends on, so a change touches one file (SHIP_PLAN §5a).

- L-HIDE (branch c/hide): `hide_message` calls c/hide's `hide.hide_message(conn, idea_uuid, text, *, by, source,
  source_id=None, gatekeeper=True) -> Hidden` (.masked, .spans, .details, .hidden_count, .kinds_line, .receipt) as
  soon as the `hide` package is on main (a guarded import, BLD-C038). Until then it masks the customer details of
  DEC-103 with the level-1 patterns alone; L-HIDE adds the gatekeeper's pass and names next to a detail, and keeps
  each detail's id across edits. `hide_text` and `preview` go through the same masking.
- Voice (DEC-108, branch c/sarvam): `voice_message` has the signature of `speech.drafts.voice_to_message`: a
  finished voice note handed to the draft as one message, the person's words plus an English copy. Until c/sarvam is
  on main it returns None, and the words the client sends are kept as they are.
  TODO(c/sarvam): replace with `from speech.drafts import voice_to_message` once c/sarvam lands.
- L-SIMILAR (branch c/similar): `similar_for` calls c/similar's `similar.similar_for(conn, idea_uuid, title,
  summary) -> list[dict] | None` (None: couldn't check) as soon as it is on main (a guarded import, BLD-C038). Until
  then similar ideas are not looked for here and the part says so ("Couldn't check for similar ideas. The review
  desk will.", `L-SIMILAR.failure`), never "none found".

Nothing here logs a value: only kinds, counts and IDs.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.config import get_settings
from core.db import Conn
from onepc.context import seal_text
from pii import vault
from pii.patterns import scan

# Level-1 pattern -> the hidden kind it is (E-ENUMS.hidden). DEC-103 hides folio, PAN, phone, customer email, account
# and Aadhaar numbers; demat accounts, cards and PRANs are account numbers to the person. Patterns that only warn
# (IFSC, ARN, EUIN, a KFin email address) are not customer details and stay as written; the gateway still tags
# anything sensitive before a model sees it (non-negotiable 2).
KIND_OF = {
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
}
LABEL = {"folio": "Folio", "pan": "PAN", "phone": "Phone", "email": "Email", "account": "Account",
         "aadhaar": "Aadhaar", "name": "Name"}  # fmt: skip
VAULT_TYPE = {"folio": "FOLIO_NUMBER", "pan": "PAN", "phone": "PHONE", "email": "EMAIL",
              "account": "ACCOUNT_NUMBER", "aadhaar": "AADHAAR"}  # fmt: skip
SEALED_SOURCES = ("message", "answer", "conversation", "edit")


@dataclass(frozen=True)
class Found:
    kind: str
    start: int  # in the person's own text
    end: int
    value: str  # the real value: goes to the vault only, never to a log, a model or another person
    masked: str  # "Folio ••••89"


@dataclass
class Hidden:
    """What hiding did to one text (c/hide's `Hidden`). `masked` is the only copy anyone else may get."""

    masked: str
    spans: list[dict[str, Any]] = field(
        default_factory=list
    )  # {start, end, kind, hid?}: the owner's own text
    details: list[dict[str, Any]] = field(default_factory=list)  # E-ENTITIES HiddenDetail
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def hidden_count(self) -> int:
        return sum(self.counts.values())


def landed(module: str, name: str) -> Callable[..., Any] | None:
    """Another lane's entry point once its package is on main, else None. A package that is there but breaks on
    import is an error, never a quiet fall-back."""
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise
        return None
    fn = getattr(mod, name, None)
    return fn if callable(fn) else None


def masked_form(kind: str, value: str) -> str:
    """Kind + •••• + the last two characters (DEC-103): "PAN ••••4F"."""
    tail = "".join(ch for ch in value if ch.isalnum())[-2:]
    return f"{LABEL[kind]} ••••{tail}"


def find(text: str) -> tuple[Found, ...]:
    """Every customer detail in the text, in order, none inside another."""
    hits = sorted(
        (m for m in scan(text, kfin_domains=get_settings().kfin_domains) if m.action == "block"),
        key=lambda m: (m.start, -(m.end - m.start)),
    )
    found: list[Found] = []
    for m in hits:
        kind = KIND_OF.get(m.pattern_id)
        if kind is None or (found and m.start < found[-1].end):
            continue  # not a hidden kind (a date of birth stays; the gateway tags it), or inside one already found
        value = text[m.start : m.end]
        found.append(Found(kind, m.start, m.end, value, masked_form(kind, value)))
    return tuple(found)


def _masked(text: str, found: tuple[Found, ...]) -> str:
    out, last = [], 0
    for f in found:
        out.append(text[last : f.start])
        out.append(f.masked)
        last = f.end
    out.append(text[last:])
    return "".join(out)


def _counts(found: tuple[Found, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in found:
        out[f.kind] = out.get(f.kind, 0) + 1
    return out


def preview(conn: Conn | None, text: str, *, idea_uuid: str | None = None) -> Hidden:
    """The masked copy and spans, nothing stored: for text that is not the person's own message (an English copy,
    an email's subject or thread)."""
    found = find(text)
    spans = [{"start": f.start, "end": f.end, "kind": f.kind} for f in found]
    return Hidden(_masked(text, found), spans, [], _counts(found))


def hide_message(
    conn: Conn, idea_uuid: str, text: str, *, by: str, source: str = "message", source_id: str
) -> Hidden:
    """Mask a message (or an edit), record each detail (kind, span, mask, vault tag; never the value) and seal the
    person's own words for them alone (`idea_words_sealed`, context "<source>:<source_id>"). Running it again for
    the same source finds every detail afresh. Inside the caller's transaction."""
    if source not in SEALED_SOURCES:
        raise ValueError("hide_message takes a message, answer, conversation or edit")
    hide = landed("hide", "hide_message")
    if hide is not None:  # c/hide: patterns, then the gatekeeper (non-negotiable 4)
        hidden: Hidden = hide(
            conn, idea_uuid, text, by=by, source=source, source_id=source_id, gatekeeper=True
        )
        return hidden
    found = find(text)
    scope = f"DRAFT-{idea_uuid}"
    with conn.transaction():
        before = [
            r["vault_tag"]
            for r in conn.execute(
                "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = %s AND source_id = %s "
                "RETURNING vault_tag",
                (idea_uuid, source, source_id),
            ).fetchall()
        ]
        spans, details = [], []
        for f in found:
            tag = vault.assign(conn, scope, VAULT_TYPE[f.kind], f.value, subject_user_id=None)
            row = conn.execute(
                "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, "
                "vault_tag, found_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'patterns') RETURNING id",
                (idea_uuid, source, source_id, f.start, f.end, f.kind, f.masked, tag),
            ).fetchone()
            assert row is not None
            hid = str(row["id"])
            spans.append({"start": f.start, "end": f.end, "kind": f.kind, "hid": hid})
            details.append({"id": hid, "kind": f.kind, "masked": f.masked, "state": "hidden"})
        conn.execute(
            "INSERT INTO idea_words_sealed (idea_uuid, source, source_id, owner_user_id, text_encrypted) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (source, source_id) DO UPDATE SET text_encrypted = EXCLUDED.text_encrypted",
            (idea_uuid, source, source_id, by,
             seal_text("idea_words_sealed", "text_encrypted", f"{source}:{source_id}", text, vault=True)),
        )  # fmt: skip
        _drop_unreferenced(conn, idea_uuid, before)  # a value the edit took out leaves the vault with it
    return Hidden(_masked(text, found), spans, details, _counts(found))


def forget(conn: Conn, idea_uuid: str, source: str, source_ids: list[str]) -> None:
    """Texts that are gone (a list part cut shorter): their hidden details and sealed words, and the vault tags no
    other hidden detail of the draft references (BLD-C038). Inside the caller's transaction."""
    if not source_ids:
        return
    tags = [
        r["vault_tag"]
        for r in conn.execute(
            "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = %s AND source_id = ANY(%s) "
            "RETURNING vault_tag",
            (idea_uuid, source, source_ids),
        ).fetchall()
    ]
    conn.execute(
        "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = %s AND source_id = ANY(%s)",
        (idea_uuid, source, source_ids),
    )
    _drop_unreferenced(conn, idea_uuid, tags)


def _drop_unreferenced(conn: Conn, idea_uuid: str, tags: list[Any]) -> None:
    """Only tags these hidden details held (customer values the gateway never sees, so never one of its own tags),
    and only when no hidden detail of the draft still holds them. The vault's counters stay: a tag number is never
    given out again."""
    held = sorted({str(t) for t in tags if t})
    if held:
        conn.execute(
            "DELETE FROM pseudonym_vault v WHERE v.scope_id = %s AND v.tag = ANY(%s) AND NOT EXISTS "
            "(SELECT 1 FROM hidden_details h WHERE h.idea_uuid = %s AND h.vault_tag = v.tag)",
            (f"DRAFT-{idea_uuid}", held, idea_uuid),
        )


def hide_text(
    conn: Conn, idea_uuid: str, text: str, *, by: str, source: str = "edit", source_id: str | None = None
) -> tuple[str, int]:
    """Any other text the person writes on the draft (a part they change by hand): (masked text, hidden count)."""
    if source_id is None:
        found = find(text)
        return _masked(text, found), len(found)
    done = hide_message(conn, idea_uuid, text, by=by, source=source, source_id=source_id)
    return done.masked, done.hidden_count


def similar_for(conn: Conn, idea_uuid: str, title: str, summary: str) -> list[dict[str, Any]] | None:
    """Up to 8 similar ideas (`SimilarMatch[]`), or None when they could not be looked for (the part then fails and
    the review desk checks instead). L-SIMILAR owns the matching; until c/similar lands this is None."""
    look = landed("similar", "similar_for")
    if look is None:
        return None
    found: list[dict[str, Any]] | None = look(conn, idea_uuid, title, summary)
    return found


def voice_message(
    conn: Conn, stream_id: str, *, idea_uuid: str, by_code: str, consume: bool = True
) -> Any | None:
    """A finished voice note for this draft (`text`, `text_en`, `lang`, …), handed over once, or None when there is
    none to hand over. c/sarvam's `voice_to_message`; until it lands, None."""
    return None
