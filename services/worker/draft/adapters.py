"""Thin adapters to the other lane C modules L-DRAFT depends on, so a change touches one file (SHIP_PLAN §5a).

- `hide_message`: L-HIDE (branch c/hide). Until it is on main, the customer details of DEC-103 are masked with the
  level-1 patterns alone (`pii.patterns.scan`); L-HIDE adds the gatekeeper's second pass.
  TODO(c/hide): switch to `from hide import …` once c/hide lands on main.
- `similar_for`: L-SIMILAR (branch c/similar). Until it is on main, similar ideas are not looked for here and the part
  says so ("Couldn't check for similar ideas. The review desk will.", `L-SIMILAR.failure`), never "none found".
  TODO(c/similar): switch to `from similar import …` once c/similar lands on main.

Nothing here logs a value: only kinds, counts and IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from core.db import Conn
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


@dataclass(frozen=True)
class Found:
    kind: str
    start: int  # in the person's own text
    end: int
    value: str  # the real value: goes to the vault only, never to a log, a model or another person
    masked: str  # "Folio ••••89"


@dataclass(frozen=True)
class Hidden:
    masked: str  # the copy every other person, service and model receives
    found: tuple[Found, ...]

    @property
    def spans(self) -> list[dict[str, Any]]:
        return [{"start": f.start, "end": f.end, "kind": f.kind} for f in self.found]


def masked_form(kind: str, value: str) -> str:
    """Kind + •••• + the last two characters (DEC-103): "PAN ••••4F"."""
    tail = "".join(ch for ch in value if ch.isalnum())[-2:]
    return f"{LABEL[kind]} ••••{tail}"


def hide_message(text: str) -> Hidden:
    """The person's words with every customer detail masked, and what was found (positions in their own text)."""
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
    out, last = [], 0
    for f in found:
        out.append(text[last : f.start])
        out.append(f.masked)
        last = f.end
    out.append(text[last:])
    return Hidden("".join(out), tuple(found))


def record_hidden(
    conn: Conn, idea_uuid: str, scope: str, source_id: str, hidden: Hidden, *, source: str = "message"
) -> list[str]:
    """One `hidden_details` row per detail found (kind, span, masked form, vault tag; never the value). Returns their
    ids. The value itself goes into the pseudonym vault under the draft's scope. `source` is `message`, or `edit`
    for a part the person typed themselves."""
    ids = []
    for f in hidden.found:
        tag = vault.assign(conn, scope, VAULT_TYPE[f.kind], f.value, subject_user_id=None)
        row = conn.execute(
            "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, vault_tag, "
            "found_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'patterns') RETURNING id",
            (idea_uuid, source, source_id, f.start, f.end, f.kind, f.masked, tag),
        ).fetchone()
        assert row is not None
        ids.append(str(row["id"]))
    return ids


def similar_for(conn: Conn, idea_uuid: str, title: str, summary: str) -> list[dict[str, Any]] | None:
    """Up to 8 similar ideas (`SimilarMatch[]`), or None when they could not be looked for (the part then fails and
    the review desk checks instead). L-SIMILAR owns the matching; until it lands this is None."""
    return None
