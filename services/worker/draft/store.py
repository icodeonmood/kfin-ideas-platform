"""The draft API's worker side (A-API.drafts, L-DRAFT.autosave). BLD-C071.

A draft is an `ideas` row with status `draft` (never `ideas.stage`), its messages (`idea_messages`, the masked copy),
the person's own words sealed for them alone (`idea_words_sealed`, DEC-103), its six parts (`idea_parts`) and its
runs (`draft_runs`). Every call names the owner (user id and contributor code, from the signed-in session) and the
device (phone or laptop, and an opaque id for "this device"). Someone else's draft looks exactly like a missing one.

Saving: every change is written in the request, so the server holds it within the 2 seconds the person is promised
(the client debounces); `saved_at` and the device move with it. One active editor (L-DRAFT.autosave/5): opening a
draft (`open=True`) makes that device the editor; a change from another device is refused with `open_elsewhere`
until the person carries on there. A message sent again with the id its device gave it is kept once (offline,
L-DRAFT.autosave/7).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from core.logging import get_logger
from draft import adapters, labels, parts, runs
from draft.config import rules
from onepc import enums
from onepc.context import open_text, seal_text

log = get_logger("draft.store")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
CODE_RE = re.compile(r"^CTR-[0-9a-f]{6,8}$")
OFFLINE_DAYS = 30  # a message typed offline keeps its own time only within this window
CREATE_ROUTE = "POST /drafts"
LIST_LIMIT = 20


class DraftError(Exception):
    """A refusal the screen can explain. Carries a code, the field it is about and safe extras (never text)."""

    def __init__(self, status: int, code: str, *, field: str | None = None, **extra: Any):
        super().__init__(code)
        self.status, self.code, self.field, self.extra = status, code, field, extra

    def body(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.code, **self.extra}
        if self.field:
            out["field"] = self.field
        return out


@dataclass(frozen=True)
class Owner:
    user_id: str
    code: str

    def __post_init__(self) -> None:
        if not UUID_RE.match(self.user_id) or not CODE_RE.match(self.code):
            raise DraftError(403, "forbidden")


@dataclass(frozen=True)
class Device:
    kind: str | None = None  # phone | laptop
    id: str | None = None

    @classmethod
    def of(cls, kind: Any, ident: Any) -> Device:
        k = kind if kind in enums.values("device") else None
        i = ident if isinstance(ident, str) and DEVICE_ID_RE.match(ident) else None
        return cls(k, i)


def _now(conn: Conn) -> dt.datetime:
    row = conn.execute("SELECT now() AS now").fetchone()
    assert row is not None
    return row["now"]  # type: ignore[no-any-return]


def _lang(text: str) -> str:
    """The script the words are in (L-DRAFT.parts/9 records the language). Latin script, Hinglish included, is
    recorded as "en"; the draft itself is always written in English."""
    for code, lo, hi in (("hi", 0x0900, 0x097F), ("bn", 0x0980, 0x09FF), ("pa", 0x0A00, 0x0A7F),
                         ("gu", 0x0A80, 0x0AFF), ("ta", 0x0B80, 0x0BFF), ("te", 0x0C00, 0x0C7F),
                         ("kn", 0x0C80, 0x0CFF), ("ml", 0x0D00, 0x0D7F)):  # fmt: skip
        if sum(1 for ch in text if lo <= ord(ch) <= hi) >= 3:
            return code
    return "en"


# ---- loading and the checks every change passes ------------------------------------------------------------------

_DRAFT_SELECT = (
    "SELECT id, contributor_code, status, channel, origin_encrypted, step, saved_at, saved_device, saved_device_id, "
    "char_count, archived_at, editor_device_id, editor_device, editor_at, kind, affects, area, brings, "
    "sorting_sources, sorting_confirmed_at, helper_picks, helper_text, created_at FROM ideas WHERE id = %s"
)


def _load(conn: Conn, owner: Owner, idea_uuid: str, *, lock: bool = False) -> dict[str, Any]:
    if not UUID_RE.match(idea_uuid):
        raise DraftError(404, "not_found")
    row = conn.execute(_DRAFT_SELECT + " FOR UPDATE" if lock else _DRAFT_SELECT, (idea_uuid,)).fetchone()
    if row is None or row["contributor_code"] != owner.code or row["status"] != "draft":
        raise DraftError(404, "not_found")
    return row


def _writable(row: dict[str, Any], device: Device) -> None:
    if row["archived_at"] is not None:
        raise DraftError(409, "archived")
    if device.id and row["editor_device_id"] and row["editor_device_id"] != device.id:
        raise DraftError(409, "open_elsewhere", device=row["editor_device"])


def _touch(conn: Conn, idea_uuid: str, device: Device) -> None:
    """Saved now, on this device; the words' length follows the messages."""
    conn.execute(
        "UPDATE ideas SET saved_at = now(), saved_device = coalesce(%s, saved_device), "
        "saved_device_id = coalesce(%s, saved_device_id), "
        "char_count = (SELECT coalesce(sum(char_count), 0) FROM idea_messages WHERE idea_uuid = %s), "
        "editor_device_id = coalesce(editor_device_id, %s), editor_device = coalesce(editor_device, %s), "
        "editor_at = now() WHERE id = %s",
        (device.kind, device.id, idea_uuid, device.id, device.kind, idea_uuid),
    )


# ---- create -------------------------------------------------------------------------------------------------------


def create(
    conn: Conn,
    owner: Owner,
    device: Device,
    *,
    channel: str = "web",
    text: str | None = None,
    text_en: str | None = None,
    via: str = "typed",
    idempotency_key: str | None = None,
    client_id: str | None = None,
) -> tuple[str, str | None]:
    """A new draft, with the first message when there are words (A-API.drafts `POST /drafts`). Returns the draft id
    and the run started, if any. The same Idempotency-Key returns the first draft (A-API.conventions/3)."""
    if channel not in enums.CHANNEL:
        raise DraftError(400, "channel_invalid", field="channel")
    if idempotency_key is not None and not 8 <= len(idempotency_key) <= 200:
        raise DraftError(400, "idempotency_key_invalid")
    idea_uuid = str(uuid.uuid4())
    with conn.transaction():
        if idempotency_key:
            got = conn.execute(
                "INSERT INTO idempotency_keys (key, user_id, route, request_hash, status, response_json) "
                "VALUES (%s, %s, %s, 'v1', 201, %s) ON CONFLICT (user_id, key) DO NOTHING RETURNING key",
                (idempotency_key, owner.user_id, CREATE_ROUTE, Jsonb({"id": idea_uuid})),
            ).fetchone()
            if got is None:
                first = conn.execute(
                    "SELECT route, response_json FROM idempotency_keys WHERE user_id = %s AND key = %s",
                    (owner.user_id, idempotency_key),
                ).fetchone()
                if first is None or first["route"] != CREATE_ROUTE:
                    raise DraftError(409, "idempotency_key_reused")
                return str(first["response_json"]["id"]), None
        conn.execute(
            "INSERT INTO ideas (id, contributor_code, status, channel, step, saved_at, saved_device, saved_device_id, "
            "editor_device_id, editor_device, editor_at, language) "
            "VALUES (%s, %s, 'draft', %s, 'tell', now(), %s, %s, %s, %s, now(), 'en')",
            (idea_uuid, owner.code, channel, device.kind, device.id, device.id, device.kind),
        )
        run_id = None
        if text is not None and text.strip():
            _, run_id = _add(conn, owner, idea_uuid, device, text=text, via=via, text_en=text_en,
                             client_id=client_id)  # fmt: skip
    log.info("draft.created", idea_uuid=idea_uuid, channel_code=channel)
    return idea_uuid, run_id


# ---- messages -----------------------------------------------------------------------------------------------------


def _check_text(text: Any, *, field: str = "text") -> str:
    if not isinstance(text, str) or not text.strip():
        raise DraftError(422, "empty_message", field=field)
    if len(text) > rules().max_message_chars:
        raise DraftError(422, "too_long", field=field, limit=rules().max_message_chars)
    return text.strip()


def _seal_words(conn: Conn, idea_uuid: str, owner: Owner, mid: str, text: str) -> None:
    conn.execute(
        "INSERT INTO idea_words_sealed (idea_uuid, source, source_id, owner_user_id, text_encrypted) "
        "VALUES (%s, 'message', %s, %s, %s) "
        "ON CONFLICT (source, source_id) DO UPDATE SET text_encrypted = EXCLUDED.text_encrypted",
        (idea_uuid, mid, owner.user_id,
         seal_text("idea_words_sealed", "text_encrypted", f"message:{mid}", text, vault=True)),
    )  # fmt: skip


def _add(
    conn: Conn,
    owner: Owner,
    idea_uuid: str,
    device: Device,
    *,
    text: str,
    via: str,
    text_en: str | None = None,
    client_id: str | None = None,
    at: dt.datetime | None = None,
    defer_run: bool = False,
) -> tuple[str, str | None]:
    """Inside a transaction: mask, store the masked copy, seal the person's words, record what was hidden, save,
    then begin the run. Returns (message id, run id)."""
    text = _check_text(text)
    english = _check_text(text_en, field="text_en") if text_en else None
    if via not in enums.values("message_via"):
        raise DraftError(422, "via_invalid", field="via")
    if client_id is not None and not 8 <= len(client_id) <= 200:
        raise DraftError(400, "idempotency_key_invalid")
    if client_id:
        same = conn.execute(
            "SELECT id FROM idea_messages WHERE idea_uuid = %s AND client_id = %s", (idea_uuid, client_id)
        ).fetchone()
        if same:
            return str(same["id"]), None
    stats = conn.execute(
        "SELECT count(*) AS n, coalesce(max(seq), 0) AS last FROM idea_messages WHERE idea_uuid = %s",
        (idea_uuid,),
    ).fetchone()
    assert stats is not None
    if int(stats["n"]) >= rules().max_messages:
        raise DraftError(409, "too_many_messages", limit=rules().max_messages)
    hidden = adapters.hide_message(text)  # DEC-103: before anything else sees the words
    masked_en = adapters.hide_message(english).masked if english else None
    mid = str(uuid.uuid4())
    now = _now(conn)
    when = at if at is not None and now - dt.timedelta(days=OFFLINE_DAYS) <= at <= now else now
    conn.execute(
        "INSERT INTO idea_messages (id, idea_uuid, seq, via, device, lang, text_encrypted, spans, char_count, "
        "created_at, client_id, text_en_encrypted) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (mid, idea_uuid, int(stats["last"]) + 1, via, device.kind, _lang(text),
         seal_text("idea_messages", "text_encrypted", mid, hidden.masked), Jsonb(hidden.spans), len(text), when,
         client_id,
         seal_text("idea_messages", "text_en_encrypted", mid, masked_en) if masked_en else None),
    )  # fmt: skip
    _seal_words(conn, idea_uuid, owner, mid, text)
    adapters.record_hidden(conn, idea_uuid, runs.scope(idea_uuid), mid, hidden)
    _touch(conn, idea_uuid, device)
    run_id = (
        None
        if defer_run
        else runs.begin(conn, idea_uuid, trigger="message", message_id=mid, new_text=hidden.masked)
    )
    log.info("draft.message_added", idea_uuid=idea_uuid, message_id=mid, hidden_count=len(hidden.found),
             via_code=via, run_id=run_id)  # fmt: skip
    return mid, run_id


def add_message(
    conn: Conn,
    owner: Owner,
    idea_uuid: str,
    device: Device,
    *,
    text: Any,
    via: str = "typed",
    text_en: Any = None,
    client_id: str | None = None,
    at: dt.datetime | None = None,
    defer_run: bool = False,
) -> tuple[str, str | None]:
    """`POST /drafts/:id/messages`: one more message (typed, a voice note's words, an email or Teams arrival).
    `text` is the person's own words; `text_en`, for a voice note or another language, an English copy labelled as
    a translation (DEC-108): context for the parts, never quoted. `defer_run` keeps the words without building (the
    S1 interview's answers until the last, L-DRAFT.parts/10)."""
    with conn.transaction():
        row = _load(conn, owner, idea_uuid, lock=True)
        _writable(row, device)
        return _add(conn, owner, idea_uuid, device, text=text, via=via, text_en=text_en or None,
                    client_id=client_id, at=at, defer_run=defer_run)  # fmt: skip


def edit_message(
    conn: Conn,
    owner: Owner,
    idea_uuid: str,
    message_id: str,
    device: Device,
    *,
    text: Any,
    text_en: Any = None,
) -> tuple[str, str | None]:
    """`PATCH /drafts/:id/messages/:mid`: the person changes their words (the box autosaving, or "Edit" on a sent
    message). Masked again from scratch; the parts not pinned are built again."""
    if not UUID_RE.match(message_id):
        raise DraftError(404, "not_found")
    with conn.transaction():
        row = _load(conn, owner, idea_uuid, lock=True)
        _writable(row, device)
        found = conn.execute(
            "SELECT id FROM idea_messages WHERE id = %s AND idea_uuid = %s", (message_id, idea_uuid)
        ).fetchone()
        if found is None:
            raise DraftError(404, "not_found")
        words = _check_text(text)
        english = _check_text(text_en, field="text_en") if text_en else None
        hidden = adapters.hide_message(words)
        masked_en = adapters.hide_message(english).masked if english else None
        conn.execute(
            "UPDATE idea_messages SET text_encrypted = %s, spans = %s, char_count = %s, lang = %s, edited_at = now(), "
            "text_en_encrypted = %s WHERE id = %s",
            (seal_text("idea_messages", "text_encrypted", message_id, hidden.masked), Jsonb(hidden.spans), len(words),
             _lang(words),
             seal_text("idea_messages", "text_en_encrypted", message_id, masked_en) if masked_en else None,
             message_id),
        )  # fmt: skip
        _seal_words(conn, idea_uuid, owner, message_id, words)
        # The spans moved: what was hidden in this message is found again from scratch.
        conn.execute(
            "DELETE FROM hidden_details WHERE idea_uuid = %s AND source = 'message' AND source_id = %s",
            (idea_uuid, message_id),
        )
        adapters.record_hidden(conn, idea_uuid, runs.scope(idea_uuid), message_id, hidden)
        _touch(conn, idea_uuid, device)
        run_id = runs.begin(conn, idea_uuid, trigger="edit", message_id=message_id, new_text=hidden.masked)
    log.info("draft.message_edited", idea_uuid=idea_uuid, message_id=message_id, run_id=run_id)
    return message_id, run_id


# ---- parts the person changes (L-DRAFT.pins) ---------------------------------------------------------------------


def _mask_value(conn: Conn, idea_uuid: str, wire_key: str, value: Any) -> Any:
    """The person's own text in a part is masked like any message (DEC-103); what was hidden is recorded."""

    def one(text: str) -> str:
        hidden = adapters.hide_message(text)
        if hidden.found:
            adapters.record_hidden(conn, idea_uuid, runs.scope(idea_uuid), f"part:{wire_key}", hidden,
                                   source="edit")  # fmt: skip
        return hidden.masked

    if isinstance(value, str):
        return one(value)
    if isinstance(value, list) and wire_key != "value":
        return [one(v) for v in value]
    return value


def set_part(
    conn: Conn, owner: Owner, idea_uuid: str, wire_key: str, device: Device, body: dict[str, Any]
) -> str | None:
    """`PATCH /drafts/:id/parts/:part`: `{value}` sets and pins the part; `{pinned: false}` unpins it and asks the
    assistant again ("Suggest again"). Returns the run started, if any."""
    if wire_key not in parts.WIRE_KEYS:
        raise DraftError(404, "not_found")
    if wire_key not in parts.EDITABLE:
        raise DraftError(409, "not_editable", field="part")
    row_key = "title" if wire_key == "summary" else wire_key
    with conn.transaction():
        row = _load(conn, owner, idea_uuid, lock=True)
        _writable(row, device)
        got = conn.execute(
            "SELECT state, value FROM idea_parts WHERE idea_uuid = %s AND key = %s FOR UPDATE",
            (idea_uuid, row_key),
        ).fetchone()
        old = got["value"] if got else None
        run_id = None
        if "value" not in body and body.get("pinned") is False:
            if not runs.ai_on(conn):
                raise DraftError(409, "assistant_off")
            new: Any
            if row_key == "title":
                kept = parts.pinned_fields(old) - {wire_key}
                new = {**(old if isinstance(old, dict) else {}), "pinned": sorted(kept)}
                state = "filled"
            else:
                new, state = old, ("filled" if not parts.is_empty(row_key, old) else "waiting")
            conn.execute(
                "INSERT INTO idea_parts (idea_uuid, key, state, value) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (idea_uuid, key) DO UPDATE SET state = EXCLUDED.state, value = EXCLUDED.value",
                (idea_uuid, row_key, state, Jsonb(new) if new is not None else None),
            )
            _touch(conn, idea_uuid, device)
            run_id = runs.begin(conn, idea_uuid, trigger="unpin", only=[row_key])
        elif "value" in body:
            try:
                cleaned = parts.clean_value(wire_key, body["value"])
            except parts.PartValueError as exc:
                raise DraftError(422, exc.code, field="value") from None
            masked = _mask_value(conn, idea_uuid, wire_key, cleaned)
            if row_key == "title":
                base = old if isinstance(old, dict) else {}
                pinned = parts.pinned_fields(base) | {wire_key}
                new = {"title": base.get("title"), "summary": base.get("summary"), wire_key: masked,
                       "pinned": sorted(pinned)}  # fmt: skip
                state = "pinned" if pinned >= {"title", "summary"} else "filled"
            else:
                new, state = masked, "pinned"
            conn.execute(
                "INSERT INTO idea_parts (idea_uuid, key, state, value, why, source_quote, run_id) "
                "VALUES (%s, %s, %s, %s, NULL, NULL, NULL) ON CONFLICT (idea_uuid, key) DO UPDATE SET "
                "state = EXCLUDED.state, value = EXCLUDED.value, why = CASE WHEN EXCLUDED.state = 'pinned' THEN NULL "
                "ELSE idea_parts.why END, source_quote = CASE WHEN EXCLUDED.state = 'pinned' THEN NULL "
                "ELSE idea_parts.source_quote END, run_id = CASE WHEN EXCLUDED.state = 'pinned' THEN NULL "
                "ELSE idea_parts.run_id END",
                (idea_uuid, row_key, state, Jsonb(new) if new is not None else None),
            )
            _touch(conn, idea_uuid, device)
        else:
            raise DraftError(422, "value_required", field="value")
    log.info("draft.part_set", idea_uuid=idea_uuid, part=wire_key, run_id=run_id)
    return run_id


# ---- the draft itself ---------------------------------------------------------------------------------------------


def save_step(conn: Conn, owner: Owner, idea_uuid: str, device: Device, step: Any) -> dict[str, Any]:
    """`PATCH /drafts/:id`: where the person is (Tell it, Check it step n, Send it)."""
    if step not in enums.DRAFT_STEP:
        raise DraftError(422, "step_invalid", field="step")
    with conn.transaction():
        row = _load(conn, owner, idea_uuid, lock=True)
        _writable(row, device)
        conn.execute("UPDATE ideas SET step = %s WHERE id = %s", (step, idea_uuid))
        _touch(conn, idea_uuid, device)
        saved = _load(conn, owner, idea_uuid)
    return _saved(saved, device, _now(conn))


def build(conn: Conn, owner: Owner, idea_uuid: str, device: Device) -> str | None:
    """`POST /drafts/:id/runs`: "Try again" after a failed run, or the one build after the S1 interview."""
    with conn.transaction():
        row = _load(conn, owner, idea_uuid, lock=True)
        _writable(row, device)
        if not runs.ai_on(conn):
            raise DraftError(409, "assistant_off")
        return runs.begin(conn, idea_uuid, trigger="retry")


def archive(conn: Conn, owner: Owner, idea_uuid: str) -> None:
    """`DELETE /drafts/:id`: archived, never deleted (L-DRAFT.autosave/8)."""
    with conn.transaction():
        _load(conn, owner, idea_uuid, lock=True)
        conn.execute(
            "UPDATE ideas SET archived_at = coalesce(archived_at, now()) WHERE id = %s", (idea_uuid,)
        )
    log.info("draft.archived", idea_uuid=idea_uuid, by_code="owner")


def restore_draft(conn: Conn, owner: Owner, idea_uuid: str, device: Device) -> None:
    """From My ideas → Drafts: back to the person's drafts, saved now."""
    with conn.transaction():
        _load(conn, owner, idea_uuid, lock=True)
        conn.execute("UPDATE ideas SET archived_at = NULL WHERE id = %s", (idea_uuid,))
        _touch(conn, idea_uuid, device)
    log.info("draft.restored", idea_uuid=idea_uuid)


def take_over(conn: Conn, owner: Owner, idea_uuid: str, device: Device) -> None:
    """Opening the draft here: this device becomes the one editor (L-DRAFT.autosave/5)."""
    if not device.id:
        return
    _load(conn, owner, idea_uuid)
    conn.execute(
        "UPDATE ideas SET editor_device_id = %s, editor_device = coalesce(%s, editor_device), editor_at = now() "
        "WHERE id = %s",
        (device.id, device.kind, idea_uuid),
    )


# ---- reading ------------------------------------------------------------------------------------------------------


def _saved(row: dict[str, Any], device: Device, now: dt.datetime) -> dict[str, Any]:
    this = bool(device.id and row["saved_device_id"] == device.id)
    return {
        "saved_at": row["saved_at"].isoformat() if row["saved_at"] else None,
        "saved_on": {"device": row["saved_device"], "this_device": this},
        "saved_labels": labels.saved_labels(row["saved_at"], row["saved_device"], this, now),
    }


def _title_text(value: Any) -> str:
    return str(value.get("title") or "") if isinstance(value, dict) else ""


def _wire_parts(rows: list[dict[str, Any]], means: dict[str, int]) -> dict[str, Any]:
    by = {str(r["key"]): r for r in rows}
    out: dict[str, Any] = {}
    defaults: dict[str, Any] = {"often": None, "who": [], "value": [], "area": "", "similar": []}
    title = by.get("title")
    tv = title["value"] if title and isinstance(title["value"], dict) else {}
    pinned = parts.pinned_fields(tv)
    for sub in ("title", "summary"):
        if sub in pinned or (title and title["state"] == "pinned"):
            state = "pinned"
        elif title and title["state"] in ("updating", "failed"):
            state = str(title["state"])
        else:
            state = "filled" if tv.get(sub) else "waiting"
        part: dict[str, Any] = {"state": state, "value": tv.get(sub) or "", "mean_ms": means.get("title")}
        if sub == "title" and state == "filled" and title and title["why"]:
            part.update(why=title["why"], source_quote=title["source_quote"])
        out[sub] = part
    for key in ("often", "who", "value", "area", "similar"):
        r = by.get(key)
        value = r["value"] if r and r["value"] is not None else defaults[key]
        state = str(r["state"]) if r else "waiting"
        if state == "filled" and parts.is_empty(key, value):
            state = "waiting"
        part = {"state": state, "value": value, "mean_ms": means.get(key)}
        if state == "filled" and r and r["why"]:
            part["why"] = r["why"]
        if state == "filled" and r and r["source_quote"]:
            part["source_quote"] = r["source_quote"]
        out[key] = part
    return out


def _sorting(row: dict[str, Any], wire: dict[str, Any]) -> dict[str, Any]:
    """E-ENTITIES Sorting: what the person confirmed or changed (L-SORT) wins; until then the parts suggest."""
    sources = row["sorting_sources"] or {}

    def choice(field: str, own: Any, part: str) -> dict[str, Any]:
        src = (sources.get(field) or {}).get("source")
        if src in ("confirmed", "changed"):
            out = {"value": own, "source": src}
            why = (sources.get(field) or {}).get("why")
            return {**out, "why": why} if why else out
        p = wire[part]
        out = {"value": p["value"], "source": "suggested"}
        return {**out, "why": p["why"]} if p.get("why") else out

    kind_src = (sources.get("kind") or {}).get("source")
    return {
        "affects": choice("affects", list(row["affects"] or []), "who"),
        "kind": {"value": row["kind"] or "problem", "source": kind_src or "suggested"},
        "area": choice("area", row["area"] or "", "area"),
        "brings": choice("brings", list(row["brings"] or []), "value"),
        "confirmed": row["sorting_confirmed_at"] is not None,
    }


def _messages(conn: Conn, idea_uuid: str, device: Device, now: dt.datetime) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT m.id, m.via, m.device, m.lang, m.text_encrypted, m.text_en_encrypted, m.spans, m.created_at, "
        "m.edited_at, s.text_encrypted AS sealed "
        "FROM idea_messages m LEFT JOIN idea_words_sealed s ON s.source = 'message' AND s.source_id = m.id::text "
        "WHERE m.idea_uuid = %s ORDER BY m.created_at, m.seq",
        (idea_uuid,),
    ).fetchall()
    out = []
    for r in rows:
        mid = str(r["id"])
        own = open_text("idea_words_sealed", "text_encrypted", f"message:{mid}", r["sealed"], vault=True)
        text = (
            own if own is not None else open_text("idea_messages", "text_encrypted", mid, r["text_encrypted"])
        )
        english = open_text("idea_messages", "text_en_encrypted", mid, r["text_en_encrypted"])
        msg: dict[str, Any] = {
            "id": mid,
            "text": text or "",
            "lang": r["lang"],
            "at": r["created_at"].isoformat(),
            "at_label": labels.message_label(r["created_at"], r["device"], False, now),
            "device": r["device"],
            "via": r["via"],
            "files": [],
            "spans": r["spans"] if own is not None else [],
        }
        if english:
            msg["text_en"] = english
        if r["edited_at"]:
            msg["edited_at"] = r["edited_at"].isoformat()
        out.append(msg)
    return out


def _files(conn: Conn, idea_uuid: str, owner: Owner) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, kind, name, mime, bytes, pages, item_count, file_state, state, hidden_note, link_scope, "
        "message_id, created_at FROM attachments WHERE idea_uuid = %s AND parent_id IS NULL ORDER BY created_at",
        (idea_uuid,),
    ).fetchall()
    out = []
    for r in rows:
        item: dict[str, Any] = {
            "id": r["id"], "kind": r["kind"], "name": r["name"], "type": r["mime"] or "", "size": int(r["bytes"]),
            "state": r["file_state"] or r["state"], "added_by": {"id": owner.user_id},
            "added_at": r["created_at"].isoformat(),
        }  # fmt: skip
        for key, col in (("pages", "pages"), ("count", "item_count"), ("hidden_note", "hidden_note"),
                         ("link_scope", "link_scope"), ("message_id", "message_id")):  # fmt: skip
            if r[col] is not None:
                item[key] = str(r[col]) if key == "message_id" else r[col]
        out.append(item)
    return out


def view(conn: Conn, owner: Owner, idea_uuid: str, device: Device, *, open_: bool = False) -> dict[str, Any]:
    """`GET /drafts/:id` (owner only): everything to pick up exactly where the person left off, on any device."""
    if UUID_RE.match(idea_uuid):
        runs.settle_stale(conn, idea_uuid)
    if open_:
        take_over(conn, owner, idea_uuid, device)
    row = _load(conn, owner, idea_uuid)
    now = _now(conn)
    means = runs.means(conn)
    part_rows = conn.execute(
        "SELECT key, state, value, why, source_quote FROM idea_parts WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchall()
    wire = _wire_parts(part_rows, means)
    hidden = [
        {"id": str(h["id"]), "kind": h["kind"], "masked": h["masked"], "state": h["state"],
         **({"reason": h["reason"]} if h["reason"] else {}),
         **({"shown_at": h["shown_at"].isoformat()} if h["shown_at"] else {})}
        for h in conn.execute(
            "SELECT id, kind, masked, state, reason, shown_at FROM hidden_details WHERE idea_uuid = %s "
            "ORDER BY created_at, span_start",
            (idea_uuid,),
        ).fetchall()
    ]  # fmt: skip
    last = conn.execute(
        "SELECT id, state, receipt, suggestions FROM draft_runs WHERE idea_uuid = %s ORDER BY started_at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    done = conn.execute(
        "SELECT receipt, suggestions FROM draft_runs WHERE idea_uuid = %s AND state = 'done' "
        "ORDER BY started_at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    r = rules()
    out: dict[str, Any] = {
        "id": idea_uuid,
        "owner_id": owner.user_id,
        "channel": row["channel"],
        "messages": _messages(conn, idea_uuid, device, now),
        "parts": wire,
        "hidden": hidden,
        "sorting": _sorting(row, wire),
        "files": _files(conn, idea_uuid, owner),
        "step": row["step"] or "tell",
        **_saved(row, device, now),
        "ready": runs.ready(conn, idea_uuid),
        "min_chars": r.min_chars_to_check,
        "parts_from_chars": r.parts_from_chars,
        "char_count": int(row["char_count"]),
        "archived": row["archived_at"] is not None,
        "assistant": runs.ai_on(conn),
        "run": {"id": str(last["id"]), "state": last["state"]} if last else None,
        "editor": {
            "device": row["editor_device"],
            "this_device": bool(device.id and row["editor_device_id"] == device.id),
        }
        if row["editor_device_id"]
        else None,
    }
    if done:
        out["receipt"] = list(done["receipt"] or [])
        out["suggestions"] = list(done["suggestions"] or [])
    origin = open_text("ideas", "origin_encrypted", idea_uuid, row["origin_encrypted"])
    if origin:
        from draft.channels import origin_label

        o = json.loads(origin)
        o["label"] = origin_label(row["channel"], o, now)
        out["origin"] = o
    fix = conn.execute(
        "SELECT how, needs, solved_already, solved_note, basis, risks, included FROM idea_fix WHERE idea_uuid = %s",
        (idea_uuid,),
    ).fetchone()
    if fix:
        filled = {k: v for k, v in fix.items() if k != "included" and v not in (None, "")}
        out["fix"] = {
            **filled,
            "how": fix["how"] or "",
            "ready_count": len(filled),
            "included": fix["included"],
        }
    if row["helper_picks"] or row["helper_text"]:
        out["helpers"] = {"picks": list(row["helper_picks"] or []),
                          **({"text": row["helper_text"]} if row["helper_text"] else {})}  # fmt: skip
    return out


def recent(conn: Conn, owner: Owner, device: Device, *, archived: bool = False) -> dict[str, Any]:
    """`GET /drafts?recent=1`: the person's drafts, newest first, for the "existing draft" prompt, the side bar and
    My ideas → Drafts (`archived=True` lists the archived ones, to restore)."""
    rows = conn.execute(
        "SELECT i.id, i.saved_at, i.saved_device, i.saved_device_id, i.step, i.char_count, i.channel, i.archived_at, "
        "p.value AS title_value, "
        "(SELECT m.id FROM idea_messages m WHERE m.idea_uuid = i.id ORDER BY m.created_at, m.seq LIMIT 1) AS first_id, "
        "(SELECT m.text_encrypted FROM idea_messages m WHERE m.idea_uuid = i.id ORDER BY m.created_at, m.seq LIMIT 1) "
        "AS first_text FROM ideas i LEFT JOIN idea_parts p ON p.idea_uuid = i.id AND p.key = 'title' "
        "WHERE i.contributor_code = %s AND i.status = 'draft' AND (i.archived_at IS NOT NULL) = %s "
        "ORDER BY i.saved_at DESC NULLS LAST LIMIT %s",
        (owner.code, archived, LIST_LIMIT),
    ).fetchall()
    total = conn.execute(
        "SELECT count(*) AS n FROM ideas WHERE contributor_code = %s AND status = 'draft' "
        "AND (archived_at IS NOT NULL) = %s",
        (owner.code, archived),
    ).fetchone()
    now = _now(conn)
    items = []
    for r in rows:
        title = _title_text(r["title_value"])
        if not title and r["first_id"]:
            first = open_text("idea_messages", "text_encrypted", str(r["first_id"]), r["first_text"]) or ""
            title = first if len(first) <= 70 else first[:69].rsplit(" ", 1)[0] + "…"
        items.append({
            "id": str(r["id"]), "title": title, **_saved(r, device, now), "step": r["step"] or "tell",
            "char_count": int(r["char_count"]), "channel": r["channel"], "archived": r["archived_at"] is not None,
        })  # fmt: skip
    return {"items": items, "total": int(total["n"]) if total else len(items)}


def live(conn: Conn, owner: Owner, idea_uuid: str, run_id: str | None = None) -> dict[str, Any]:
    """What the draft stream needs for one run (A-API.draft-stream): the run, the loader's means, what was hidden in
    its message, and the parts as they stand. `run_id` None means the newest run."""
    if UUID_RE.match(idea_uuid):
        runs.settle_stale(conn, idea_uuid)
    _load(conn, owner, idea_uuid)
    latest = conn.execute(
        "SELECT id, state FROM draft_runs WHERE idea_uuid = %s ORDER BY started_at DESC LIMIT 1", (idea_uuid,)
    ).fetchone()
    want = run_id if run_id and UUID_RE.match(run_id) else (str(latest["id"]) if latest else None)
    run = (
        conn.execute(
            "SELECT id, message_id, state, parts, part_ms, receipt, suggestions, ready FROM draft_runs "
            "WHERE id = %s AND idea_uuid = %s",
            (want, idea_uuid),
        ).fetchone()
        if want
        else None
    )
    out: dict[str, Any] = {
        "latest": {"id": str(latest["id"]), "state": latest["state"]} if latest else None,
        "run": None,
    }
    if run is None:
        return out
    means = runs.means(conn)
    hidden_rows = (
        conn.execute(
            "SELECT id, kind, masked, state, span_start, span_end FROM hidden_details WHERE idea_uuid = %s "
            "AND source = 'message' AND source_id = %s ORDER BY span_start",
            (idea_uuid, str(run["message_id"])),
        ).fetchall()
        if run["message_id"]
        else []
    )
    part_rows = conn.execute(
        "SELECT key, state, value, why, source_quote, took_ms, run_id FROM idea_parts WHERE idea_uuid = %s",
        (idea_uuid,),
    ).fetchall()
    out["run"] = {
        "id": str(run["id"]),
        "state": run["state"],
        "parts": [{"key": k, "mean_ms": means.get(k)} for k in run["parts"]],
        "part_ms": dict(run["part_ms"] or {}),
        "receipt": list(run["receipt"] or []),
        "suggestions": list(run["suggestions"] or []),
        "ready": bool(run["ready"]),
        "hidden": {
            "spans": [
                {"start": h["span_start"], "end": h["span_end"], "kind": h["kind"]}
                for h in hidden_rows
                if h["span_start"] is not None
            ],
            "details": [
                {"id": str(h["id"]), "kind": h["kind"], "masked": h["masked"], "state": h["state"]}
                for h in hidden_rows
            ],
        },
    }
    out["parts"] = {
        str(p["key"]): {
            "state": p["state"],
            "value": p["value"],
            "why": p["why"],
            "source_quote": p["source_quote"],
            "took_ms": p["took_ms"],
            "run_id": str(p["run_id"]) if p["run_id"] else None,
        }
        for p in part_rows
    }
    return out
