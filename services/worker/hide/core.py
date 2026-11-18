"""Storing what was hidden, and every change to it (L-HIDE.rules, L-HIDE.audit; DEC-103).

Where things live (cut-over 20261121500100):
- the masked copy: the text's own column (`idea_messages.text_encrypted`, `answers.text_encrypted`,
  `conversation_entries.text_encrypted`, sealed with the data key; `ideas.title`, `idea_parts.value`), the only copy
  anyone else gets;
- the person's own words: `idea_words_sealed` (worker-only, vault key), keyed by (source, `sealed_key`): a row id as
  it is, any other id under the idea's uuid, so two ideas' "version 2" never meet (BLD-C066);
- each value: `pseudonym_vault` (worker-only, encrypted) under the idea's hide scope `DRAFT-<idea uuid>`, which
  never changes when the draft is shared;
- `hidden_details`: kind, span in the owner's text, the masked form, the vault tag, who found it and whether the
  owner chose "Show it" (with the reason). Never the value.

Every detect, show and hide is written to `audit_log` with IDs, kinds and reason codes only.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from core.logging import get_logger
from hide import detect
from onepc.context import open_text, seal_text
from pii import vault

log = get_logger("hide")

SEALED_SOURCES = (
    "message",
    "answer",
    "conversation",
    "edit",
)  # idea_words_sealed.source (E-ENUMS sealed_source)
DETAIL_SOURCES = (*SEALED_SOURCES, "file", "desk", "title", "part")  # what hide_into takes (BLD-C062)
SWEPT_SOURCES = ("fix", "version", "similar", "run")  # hidden_details.source for swept copies only (BLD-C066)
SHOW_REASONS = ("scheme_or_product_code", "internal_reference", "made_up_example")  # E-ENUMS show_reason
VAULT_TYPE = {
    "folio": "FOLIO_NUMBER",
    "pan": "PAN",
    "phone": "PHONE",
    "email": "EMAIL",
    "account": "ACCOUNT_NUMBER",
    "aadhaar": "AADHAAR",
    "name": "PERSON",
}


class HideError(Exception):
    """A refusal the API turns into `{error: {code, message}}`. The code is safe to log. `audit` (by, action,
    idea_uuid, after; IDs and codes only) is written by `hide/api.py` after the rollback, so a refused attempt that
    must leave a trace keeps it."""

    def __init__(
        self, status: int, code: str, *, audit: tuple[str, str, str, dict[str, Any]] | None = None
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.audit = audit


class GatekeeperUnavailable(Exception):
    """A re-check found the gateway still down: the job runner tries again later. Carries the gateway's code only."""


@dataclass
class Hidden:
    """What `hide_message` did to one text. `masked` is the only copy anyone else may get."""

    masked: str
    spans: list[dict[str, Any]] = field(default_factory=list)  # {start, end, kind, hid}: the owner's own text
    details: list[dict[str, Any]] = field(default_factory=list)  # E-ENTITIES HiddenDetail
    counts: dict[str, int] = field(default_factory=dict)  # hidden (not shown) details by kind
    receipt: str | None = None  # "Hid 3 personal details from everyone but you: …"
    kinds_line: str = ""  # "Folio number, PAN and phone number"

    @property
    def hidden_count(self) -> int:
        return sum(self.counts.values())


# ---- helpers -----------------------------------------------------------------------------------------------


def is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def scope_for(idea_uuid: str) -> str:
    """The vault scope for hidden values: one per idea, the same before and after it is shared."""
    return f"DRAFT-{uuid.UUID(idea_uuid)}"


def idea_row(conn: Conn, idea_uuid: str) -> dict[str, Any]:
    if not is_uuid(idea_uuid):
        raise HideError(404, "not_found")
    row = conn.execute(
        "SELECT i.id, i.idea_id, i.status, i.contributor_code, cm.user_id AS sharer_user_id FROM ideas i "
        "LEFT JOIN contributor_map cm ON cm.contributor_code = i.contributor_code WHERE i.id = %s",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        raise HideError(404, "not_found")
    return dict(row)


def lock(conn: Conn, idea_uuid: str) -> None:
    """One change at a time per idea (desk hide, an edit's re-run, Show it), inside the caller's transaction."""
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"hide:{idea_uuid}",))


def audit(
    conn: Conn, by: str, action: str, idea_uuid: str, after: dict[str, Any], reason: str | None = None
) -> None:
    actor = f"user:{by}" if is_uuid(by) else str(by)
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after, reason) VALUES (%s, %s, %s, %s, %s)",
        (actor, action, f"idea:{idea_uuid}", Jsonb(after), reason),
    )


def detail_view(row: dict[str, Any]) -> dict[str, Any]:
    """E-ENTITIES HiddenDetail."""
    out: dict[str, Any] = {
        "id": str(row["id"]),
        "kind": row["kind"],
        "masked": row["masked"],
        "state": row["state"],
    }
    if row.get("reason"):
        out["reason"] = row["reason"]
    if row.get("shown_at") is not None:
        out["shown_at"] = row["shown_at"].isoformat()
    return out


def details_for(conn: Conn, idea_uuid: str, source: str, source_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM hidden_details WHERE idea_uuid = %s AND source = %s AND source_id = %s "
        "ORDER BY span_start NULLS LAST, created_at",
        (idea_uuid, source, source_id),
    ).fetchall()
    return [dict(r) for r in rows]


def known_values(
    conn: Conn, idea_uuid: str, extra_tags: set[str] | None = None
) -> dict[str, tuple[str, str]]:
    """Values hidden on this idea by a reviewer or the gatekeeper (and `extra_tags`), to hide again wherever they
    appear: value -> (kind, found_by). Read from the vault; never leaves the worker."""
    rows = conn.execute(
        "SELECT DISTINCT vault_tag, kind, found_by FROM hidden_details WHERE idea_uuid = %s AND vault_tag IS NOT NULL "
        "AND state = 'hidden' AND (found_by IN ('reviewer', 'gatekeeper') OR vault_tag = ANY(%s::text[]))",
        (idea_uuid, sorted(extra_tags or set())),
    ).fetchall()
    if not rows:
        return {}
    mapping = vault.mapping(conn, scope_for(idea_uuid))
    out: dict[str, tuple[str, str]] = {}
    for r in rows:
        if r["vault_tag"] in mapping:
            value = mapping[r["vault_tag"]][1]
            found_by = "reviewer" if r["found_by"] == "reviewer" else str(r["found_by"])
            if value and (value not in out or found_by == "reviewer"):
                out[value] = (str(r["kind"]), found_by)
    return out


# ---- layout: the masked copy from the owner's words and the details -----------------------------------------


@dataclass(frozen=True)
class Seg:
    m_start: int
    m_end: int
    o_start: int
    o_end: int
    detail: dict[str, Any] | None


def layout(owner: str, details: list[dict[str, Any]]) -> tuple[str, list[Seg]]:
    """The masked copy: the owner's words with every hidden span replaced by its mask; shown ones stay as typed."""
    parts: list[str] = []
    segs: list[Seg] = []
    pos = mpos = 0
    for d in sorted(
        (d for d in details if d.get("span_start") is not None and d.get("span_end") is not None),
        key=lambda d: int(d["span_start"]),
    ):
        s, e = int(d["span_start"]), int(d["span_end"])
        if s < pos or e > len(owner) or e <= s:
            continue  # a stale or overlapping span never breaks the copy
        plain = owner[pos:s]
        segs.append(Seg(mpos, mpos + len(plain), pos, s, None))
        parts.append(plain)
        mpos += len(plain)
        rep = str(d["masked"]) if d["state"] == "hidden" else owner[s:e]
        segs.append(Seg(mpos, mpos + len(rep), s, e, d))
        parts.append(rep)
        mpos += len(rep)
        pos = e
    tail = owner[pos:]
    segs.append(Seg(mpos, mpos + len(tail), pos, len(owner), None))
    parts.append(tail)
    return "".join(parts), segs


def spans_of(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"start": int(d["span_start"]), "end": int(d["span_end"]), "kind": d["kind"], "hid": str(d["id"])}
        for d in details
        if d.get("span_start") is not None
    ]


def summary(masked: str, details: list[dict[str, Any]]) -> Hidden:
    hidden = [d for d in details if d["state"] == "hidden"]
    counts = dict(Counter(str(d["kind"]) for d in hidden))
    return Hidden(
        masked=masked,
        spans=spans_of(details),
        details=[detail_view(d) for d in details],
        counts=counts,
        receipt=detect.receipt([str(d["masked"]) for d in hidden]),
        kinds_line=detect.kinds_line(str(d["kind"]) for d in hidden),
    )


# ---- hiding a text ---------------------------------------------------------------------------------------


def sealed_key(idea_uuid: str, source_id: str) -> str:
    """`idea_words_sealed.source_id` for one text. `UNIQUE (source, source_id)` spans every idea, so an id that is
    not a row id ("2" for an edit's version) is kept under the idea's uuid ("<uuid>:2"). Row ids, and ids that
    already start with the idea's uuid (lane C's drafts and edits), are kept as they are, so callers that remove
    their own rows by id still find them (BLD-C066)."""
    sid = str(source_id)
    if is_uuid(sid) or sid.startswith(f"{uuid.UUID(idea_uuid)}:"):
        return sid
    return f"{uuid.UUID(idea_uuid)}:{sid}"


def _seal_words(conn: Conn, idea_uuid: str, source: str, source_id: str, owner_user: str, text: str) -> None:
    """Seal the person's own words. A row under the same key for another idea or person is never overwritten."""
    key = sealed_key(idea_uuid, source_id)
    row = conn.execute(
        "INSERT INTO idea_words_sealed (idea_uuid, source, source_id, owner_user_id, text_encrypted) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (source, source_id) DO UPDATE SET text_encrypted = EXCLUDED.text_encrypted "
        "WHERE idea_words_sealed.idea_uuid = EXCLUDED.idea_uuid AND idea_words_sealed.owner_user_id = EXCLUDED.owner_user_id "
        "RETURNING id",
        (idea_uuid, source, key, owner_user,
         seal_text("idea_words_sealed", "text_encrypted", f"{source}:{key}", text, vault=True)),
    ).fetchone()  # fmt: skip
    if row is None:
        raise HideError(409, "conflict")


def own_words(conn: Conn, source: str, source_id: str, *, idea_uuid: str) -> str | None:
    """The person's own words for one text of this idea (worker only; the API hands them to their owner alone)."""
    key = sealed_key(idea_uuid, source_id)
    row = conn.execute(
        "SELECT text_encrypted FROM idea_words_sealed WHERE idea_uuid = %s AND source = %s AND source_id = %s",
        (idea_uuid, source, key),
    ).fetchone()
    if row is None:
        return None
    return open_text(
        "idea_words_sealed", "text_encrypted", f"{source}:{key}", row["text_encrypted"], vault=True
    )


def forget(conn: Conn, idea_uuid: str, *, source: str, source_id: str) -> int:
    """Drop what hide kept for one text that is removed (lane F's L-CONVO/10: a conversation message removed within
    five minutes; lane C's own removals): its `hidden_details` rows, the person's sealed words, and each vault value
    of those rows that no other `hidden_details` row of the idea still holds. A value also hidden in another text of
    the idea stays. Returns how many `hidden_details` rows were removed (0 when nothing was kept).

    Takes the idea's advisory lock first (`lock`), so call it before any row lock of your own and in the same
    transaction as the removal of the text: the lock is held until that transaction ends. Logged and audited with
    IDs and counts only."""
    if source not in (*DETAIL_SOURCES, *SWEPT_SOURCES):
        raise ValueError("unknown hide source")
    if not is_uuid(idea_uuid):
        return 0
    sid = str(source_id)
    with conn.transaction():
        lock(conn, idea_uuid)
        tags = [
            str(r["vault_tag"])
            for r in conn.execute(
                "SELECT DISTINCT vault_tag FROM hidden_details WHERE idea_uuid = %s AND source = %s "
                "AND source_id = %s AND vault_tag IS NOT NULL",
                (idea_uuid, source, sid),
            ).fetchall()
        ]
        removed = conn.execute(
            "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = %s AND source_id = %s",
            (idea_uuid, source, sid),
        ).rowcount
        sealed = 0
        if source in SEALED_SOURCES:
            sealed = conn.execute(
                "DELETE FROM idea_words_sealed WHERE idea_uuid = %s AND source = %s AND source_id = %s",
                (idea_uuid, source, sealed_key(idea_uuid, sid)),
            ).rowcount
        values = 0
        if tags:
            values = conn.execute(
                "DELETE FROM pseudonym_vault v WHERE v.scope_id = %s AND v.tag = ANY(%s::text[]) AND NOT EXISTS "
                "(SELECT 1 FROM hidden_details d WHERE d.idea_uuid = %s AND d.vault_tag = v.tag)",
                (scope_for(idea_uuid), tags, idea_uuid),
            ).rowcount
        if removed or sealed or values:
            audit(
                conn,
                "system",
                "hide.forgotten",
                idea_uuid,
                {"source": source, "source_id": sid, "hidden": removed, "sealed": sealed, "vault": values},
            )
    log.info(
        "hide.forgotten",
        idea_id=idea_uuid,
        source_code=source,
        hidden_count=removed,
        sealed_count=sealed,
        vault_count=values,
    )
    return removed


def hide_into(
    conn: Conn,
    idea_uuid: str,
    text: str,
    *,
    by: str,
    source: str,
    source_id: str,
    gatekeeper: bool = True,
    seal: bool = True,
    gate: detect.Gate | None = None,
) -> Hidden:
    """Detect, store each value sealed, keep earlier "Show it" choices for the same values, and return the result.
    Re-running on an edited text keeps each detail's id where its value is still there. `gate`: the gatekeeper's
    finds the caller already has (a file's text, asked piece by piece, `hide/files.py`); then no model is called here.

    Call it inside the same transaction as the write that stores the masked copy (see `hide/__init__.py`): the
    idea's lock is held until that transaction ends, so a desk hide cannot land in between. Its own work runs in
    savepoints, so a failure here leaves the caller's transaction usable."""
    return _hide(
        conn, idea_uuid, text, by=by, source=source, source_id=source_id, gatekeeper=gatekeeper, seal=seal,
        gate=gate,
    )[0]  # fmt: skip


def _hide(
    conn: Conn,
    idea_uuid: str,
    text: str,
    *,
    by: str,
    source: str,
    source_id: str,
    gatekeeper: bool = True,
    seal: bool = True,
    recheck: bool = False,
    gate: detect.Gate | None = None,
) -> tuple[Hidden, list[dict[str, Any]]]:
    """`hide_into`, also returning the stored rows. `recheck`: a queued re-check, which raises
    `GatekeeperUnavailable` instead of going on without the gatekeeper."""
    if source not in DETAIL_SOURCES:
        raise ValueError("unknown hide source")
    idea_row(conn, idea_uuid)
    scope = scope_for(idea_uuid)
    if gate is None:
        gate = detect.Gate([])
        if gatekeeper:
            with conn.transaction():  # the model call comes before the idea's lock (BLD-C067)
                gate = detect.gatekeeper_finds(conn, text, scope)
    if recheck and gate.skipped:
        raise GatekeeperUnavailable(gate.skipped)
    with conn.transaction():
        lock(conn, idea_uuid)
        before = details_for(conn, idea_uuid, source, source_id)
        known = known_values(conn, idea_uuid, {str(d["vault_tag"]) for d in before if d["vault_tag"]})
        found = detect.find(conn, text, scope=scope, known=known, gatekeeper=False, gate=gate.finds)
        by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for d in before:
            by_tag[str(d["vault_tag"])].append(d)
        kept: list[dict[str, Any]] = []
        for f in found:
            tag = vault.assign(conn, scope, VAULT_TYPE[f.kind], f.value)
            masked_form = detect.mask(f.kind, f.value)
            prior = by_tag[tag].pop(0) if by_tag.get(tag) else None
            if prior is not None:
                row = conn.execute(
                    "UPDATE hidden_details SET span_start = %s, span_end = %s, kind = %s, masked = %s "
                    "WHERE id = %s RETURNING *",
                    (f.start, f.end, f.kind, masked_form, prior["id"]),
                ).fetchone()
            else:
                row = conn.execute(
                    "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, "
                    "vault_tag, found_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                    (idea_uuid, source, source_id, f.start, f.end, f.kind, masked_form, tag,
                     "reviewer" if f.found_by == "reviewer" else f.found_by),
                ).fetchone()  # fmt: skip
            assert row is not None
            kept.append(dict(row))
        gone = [str(d["id"]) for rows in by_tag.values() for d in rows]
        if gone:
            conn.execute("DELETE FROM hidden_details WHERE id = ANY(%s::uuid[])", (gone,))
        masked, _ = layout(text, kept)
        sealed = seal and source in SEALED_SOURCES and is_uuid(by)
        if sealed:
            _seal_words(conn, idea_uuid, source, source_id, by, text)
        if kept or gone:
            audit(
                conn,
                by,
                "hide.detected",
                idea_uuid,
                {
                    "source": source,
                    "source_id": source_id,
                    "kinds": dict(Counter(str(d["kind"]) for d in kept)),
                    "found_by": dict(Counter(str(d["found_by"]) for d in kept)),
                    "removed": len(gone),
                },
            )
        if gate.skipped:
            _gatekeeper_skipped(conn, idea_uuid, by, source, source_id, gate, recheck=sealed)
    log.info("hide.text_hidden", idea_id=idea_uuid, source_code=source, hidden_count=len(kept))
    return summary(masked, kept), kept


RECHECK_JOB = "hide.recheck"


def _gatekeeper_skipped(
    conn: Conn, idea_uuid: str, by: str, source: str, source_id: str, gate: detect.Gate, *, recheck: bool
) -> None:
    """The gatekeeper could not run on this text: it went on with the patterns and names. Audited with IDs and the
    gateway's code only, and, when the person's words are sealed and the gatekeeper was not switched off on
    purpose, a re-check is queued that runs it again once the gateway is back (`hide/recheck.py`, BLD-C067)."""
    queued = None
    if recheck and not gate.switched_off:
        from jobs.runner import enqueue

        queued = enqueue(
            conn,
            RECHECK_JOB,
            {"idea_uuid": idea_uuid, "source": source, "source_id": source_id, "by": by},
            dedupe_key=f"{RECHECK_JOB}:{idea_uuid}:{source}:{sealed_key(idea_uuid, source_id)}",
        )
    audit(
        conn,
        by,
        "hide.gatekeeper_skipped",
        idea_uuid,
        {"source": source, "source_id": source_id, "code": gate.skipped, "recheck_job": queued},
    )


def preview(conn: Conn | None, text: str, *, idea_uuid: str | None = None) -> Hidden:
    """Spans and the masked copy while the person types, with nothing stored and no model call (patterns, the
    idea's already-hidden values and names). Send the text through `hide_message` before anyone else sees it."""
    known = known_values(conn, idea_uuid) if conn is not None and idea_uuid and is_uuid(idea_uuid) else {}
    found = detect.find(conn, text, known=known, gatekeeper=False)
    rows = [
        {"id": f"preview-{i}", "span_start": f.start, "span_end": f.end, "kind": f.kind,
         "masked": detect.mask(f.kind, f.value), "state": "hidden"}
        for i, f in enumerate(found)
    ]  # fmt: skip
    masked, _ = layout(text, rows)
    return summary(masked, rows)
