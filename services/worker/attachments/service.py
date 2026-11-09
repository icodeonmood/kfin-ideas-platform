"""Research attachments, day one (§4.2 "Attachments", D3, AT-B3-06/07).

1. Accept: size, per-idea total and count limits; type by signature (`filetype.sniff`); store in quarantine.
2. Process (job `attachment.process`): virus scan → images held as `awaiting_check` → text-layer extraction
   → the level-1 personal-data patterns per location, plus the spreadsheet column check → `rejected` (with the
   data type and where; the quarantine copy is deleted at once) or `clean` (moved to the clean bucket).
3. Nobody can open a file that is not `clean`. File contents never go into Git.
Week 3, behind `attachments.deep_check` (attachments/deep.py): OCR for images and scanned pages, the gatekeeper
over file text, then `attachment-digest` and the file text in the search index once the idea is submitted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from attachments import clamav, sandbox, store
from attachments import deep as deep_checks
from attachments.filetype import sniff
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import scan
from rules import load_rule

log = get_logger("attachments")
OCR_TIMEOUT_S = 240.0

MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


class AttachmentRefused(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Limits:
    max_files: int
    max_bytes_each: int
    max_bytes_per_idea: int
    allowed: frozenset[str]
    held: frozenset[str]
    column_block_share: float


def limits() -> Limits:
    a = load_rule(store_repo(), "thresholds").data["attachments"]
    mb = 1024 * 1024
    return Limits(
        max_files=int(a["max_files"]),
        max_bytes_each=int(a["max_mb_each"]) * mb,
        max_bytes_per_idea=int(a["max_mb_per_idea"]) * mb,
        allowed=frozenset(a["allowed"]),
        held=frozenset(k for k in a["day_one_held"] if k in {"png", "jpg"}),
        column_block_share=float(a["column_block_share"]),
    )


def store_repo() -> Any:
    from pathlib import Path

    return Path(get_settings().company_repo_path)


def _key(att_id: str) -> str:
    return f"att/{att_id}"


def _screen(name: str, data: bytes, lim: Limits) -> str:
    """The checks before anything is stored: size, a name with no personal data, and a type by signature."""
    if not data:
        raise AttachmentRefused(400, "file_empty")
    if len(data) > lim.max_bytes_each:
        raise AttachmentRefused(413, "file_too_large")
    if any(m.action == "block" for m in scan(name, kfin_domains=get_settings().kfin_domains)):
        raise AttachmentRefused(422, "name_has_personal_data")  # the name is shown on screens; never stored
    kind = sniff(data)
    if kind is None or kind not in lim.allowed:
        raise AttachmentRefused(415, "type_not_allowed")
    return kind


def _store_and_queue(conn: Conn, owner: dict[str, Any], name: str, data: bytes, kind: str) -> str:
    """Inside the caller's transaction: next ATT number, the quarantine copy, the row and the check job."""
    s = get_settings()
    year = conn.execute("SELECT to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY') AS y").fetchone()["y"]  # type: ignore[index]
    n = conn.execute("SELECT next_number('ATT', %s) AS n", (year,)).fetchone()["n"]  # type: ignore[index]
    att_id = f"ATT-{year}-{n:06d}"
    store.put(s.s3_bucket_quarantine, _key(att_id), data)
    conn.execute(
        "INSERT INTO attachments (id, idea_uuid, delivery_id, uploaded_by_code, uploaded_by_user, name, mime, bytes, "
        "sha256, store_key, state) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'quarantine')",
        (
            att_id,
            owner.get("idea_uuid"),
            owner.get("delivery_id"),
            owner.get("uploaded_by_code"),
            owner.get("uploaded_by_user"),
            name[:200],
            MIME[kind],
            len(data),
            hashlib.sha256(data).hexdigest(),
            _key(att_id),
        ),
    )
    conn.execute(
        "INSERT INTO jobs (type, payload, dedupe_key) VALUES ('attachment.process', %s, %s)",
        (Jsonb({"attachment_id": att_id}), f"attachment:{att_id}"),
    )
    return att_id


def accept(conn: Conn, *, idea_uuid: str, uploaded_by_code: str, name: str, data: bytes) -> dict[str, Any]:
    lim = limits()
    kind = _screen(name, data, lim)
    with conn.transaction():
        idea = conn.execute(
            "SELECT stage FROM ideas WHERE id = %s FOR UPDATE", (idea_uuid,)
        ).fetchone()  # serialise uploads per idea; files can only change while it is a draft
        if idea is None or idea["stage"] != "draft":
            raise AttachmentRefused(409, "not_a_draft")
        used = conn.execute(
            "SELECT count(*) AS n, coalesce(sum(bytes), 0) AS total FROM attachments "
            "WHERE idea_uuid = %s AND state <> 'rejected'",
            (idea_uuid,),
        ).fetchone()
        assert used is not None
        if used["n"] >= lim.max_files:
            raise AttachmentRefused(409, "too_many_files")
        if used["total"] + len(data) > lim.max_bytes_per_idea:
            raise AttachmentRefused(413, "idea_total_too_large")
        att_id = _store_and_queue(
            conn, {"idea_uuid": idea_uuid, "uploaded_by_code": uploaded_by_code}, name, data, kind
        )
    log.info("attachments.accepted", attachment_id=att_id, file_type=kind, byte_count=len(data))
    return {"id": att_id, "state": "quarantine", "name": name[:200], "bytes": len(data)}


EVIDENCE_MAX_FILES = 10  # per delivery (BLD-131); each file still obeys the per-file size and type rules
EVIDENCE_STATES = ("in_delivery", "shipped", "resolved")  # while work or results are being shown


def accept_evidence(conn: Conn, *, delivery_id: int, user_id: str, name: str, data: bytes) -> dict[str, Any]:
    """An evidence file for a delivery (BLD-131): the same checks as research files, then quarantine. The caller
    has checked that `user_id` may add evidence to this delivery."""
    lim = limits()
    kind = _screen(name, data, lim)
    with conn.transaction():
        d = conn.execute("SELECT state FROM deliveries WHERE id = %s FOR UPDATE", (delivery_id,)).fetchone()
        if d is None:
            raise AttachmentRefused(404, "not_found")
        if d["state"] not in EVIDENCE_STATES:
            raise AttachmentRefused(409, "not_open_for_evidence")
        used = conn.execute(
            "SELECT count(*) AS n, coalesce(sum(bytes), 0) AS total FROM attachments "
            "WHERE delivery_id = %s AND state <> 'rejected'",
            (delivery_id,),
        ).fetchone()
        assert used is not None
        if used["n"] >= EVIDENCE_MAX_FILES:
            raise AttachmentRefused(409, "too_many_files")
        if used["total"] + len(data) > lim.max_bytes_per_idea * 2:
            raise AttachmentRefused(413, "delivery_total_too_large")
        att_id = _store_and_queue(
            conn, {"delivery_id": delivery_id, "uploaded_by_user": user_id}, name, data, kind
        )
    log.info("attachments.evidence_accepted", attachment_id=att_id, delivery_id=delivery_id, file_type=kind)
    return {"id": att_id, "state": "quarantine", "name": name[:200], "bytes": len(data)}


def _personal_data(
    pieces: list[tuple[str, str]], columns: list[tuple[str, list[str]]], share: float
) -> dict[str, str] | None:
    """The first blocking finding as {type, location}; values are never recorded."""
    domains = get_settings().kfin_domains
    for location, text in pieces:
        for m in scan(text, kfin_domains=domains):
            if m.action == "block":
                return {"type": m.label, "code": m.pattern_id, "location": location}
    for location, values in columns:
        if not values:
            continue
        # Any pattern counts here, warn-level ones too: a column of work emails or ARNs is a list of people.
        hits = [v for v in values if scan(v, kfin_domains=domains)]
        if len(hits) / len(values) > share:
            return {"type": "personal data in a column", "code": "column", "location": location}
    return None


def process(conn: Conn, att_id: str) -> str:
    """Run the day-one checks. Returns the final state. Raises ScannerUnavailable to retry later."""
    s = get_settings()
    row = conn.execute(
        "SELECT id, mime, store_key, state, idea_uuid FROM attachments WHERE id = %s", (att_id,)
    ).fetchone()
    if row is None or row["state"] not in ("quarantine", "processing"):
        return row["state"] if row else "missing"
    conn.execute("UPDATE attachments SET state = 'processing' WHERE id = %s", (att_id,))
    data = store.get(s.s3_bucket_quarantine, row["store_key"])
    lim = limits()

    def reject(reason: dict[str, str]) -> str:
        store.delete(s.s3_bucket_quarantine, row["store_key"])  # well inside the 24-hour rule
        conn.execute(
            "UPDATE attachments SET state = 'rejected', rejection = %s WHERE id = %s", (Jsonb(reason), att_id)
        )
        log.info("attachments.rejected", attachment_id=att_id, reason_code=reason.get("code", reason["type"]))
        return "rejected"

    try:
        result = clamav.scan_bytes(data)
    except clamav.ScannerUnavailable:
        conn.execute("UPDATE attachments SET state = 'quarantine' WHERE id = %s", (att_id,))
        raise
    if not result.clean:
        return reject({"type": "virus", "code": "virus", "location": "the whole file"})

    kind = sniff(data)
    deep = killswitch.is_on("attachments.deep_check", conn)  # week 3: OCR, gatekeeper, digest, index (D3)

    def hold(code: str) -> str:
        conn.execute(
            "UPDATE attachments SET state = 'awaiting_check', checks = %s WHERE id = %s",
            (Jsonb({"waiting_for": code}), att_id),
        )
        return "awaiting_check"

    extractor = f"{kind}_ocr" if kind in lim.held else (kind or "")
    if kind in lim.held and not deep:
        return hold("ocr")
    try:
        extracted = sandbox.extract(
            extractor, data, timeout_s=OCR_TIMEOUT_S if extractor.endswith("_ocr") else 90.0
        )
        if extracted.scanned:
            if not deep:
                return hold("ocr")
            extractor = "pdf_ocr"
            extracted = sandbox.extract(extractor, data, timeout_s=OCR_TIMEOUT_S)
    except sandbox.ExtractionFailed as exc:
        if exc.code == "ocr_unavailable":
            log.error("attachments.ocr_unavailable", attachment_id=att_id)
            return hold("ocr")
        log.warning("attachments.unreadable", attachment_id=att_id, reason_code=exc.code)
        code = "too_big" if exc.code == "too_big" else "unreadable"
        return reject({"type": code, "code": code, "location": "the whole file"})
    finding = _personal_data(extracted.pieces, extracted.columns, lim.column_block_share)
    if finding:
        return reject(finding)
    checks: dict[str, Any] = {"patterns": True, "ocr": extractor.endswith("_ocr"), "gatekeeper": False}
    if deep:
        try:
            finding = deep_checks.gatekeeper_verdict(conn, att_id, extracted)
        except deep_checks.Unavailable:
            if checks["ocr"]:
                return hold("gatekeeper")  # text read from an image has had no model check yet: keep it held
            finding = None  # a text-layer file falls back to the day-one check (patterns), and says so
            checks["gatekeeper_skipped"] = True
        else:
            checks["gatekeeper"] = True
        if finding:
            return reject(finding)

    # Commit under the row lock: a file removed (or its draft purged) during the checks is never copied to clean.
    with conn.transaction():
        live = conn.execute("SELECT state FROM attachments WHERE id = %s FOR UPDATE", (att_id,)).fetchone()
        if live is None or live["state"] != "processing":
            return live["state"] if live else "missing"
        store.put(s.s3_bucket_clean, row["store_key"], data)
        store.delete(s.s3_bucket_quarantine, row["store_key"])
        conn.execute(
            "UPDATE attachments SET state = 'clean', rejection = NULL, checks = %s WHERE id = %s",
            (Jsonb(checks), att_id),
        )
        if deep and row["idea_uuid"] is not None:  # delivery evidence is checked, never digested or indexed
            conn.execute(
                "INSERT INTO jobs (type, payload, dedupe_key) VALUES ('attachment.digest', %s, %s) "
                "ON CONFLICT DO NOTHING",
                (Jsonb({"attachment_id": att_id}), f"attachment.digest:{att_id}"),
            )
    log.info("attachments.clean", attachment_id=att_id, file_type=kind)
    return "clean"


def digest(conn: Conn, att_id: str) -> str:
    """Digest and index one clean file once its idea is submitted (job `attachment.digest`). Before that it waits:
    the digest is tagged under the idea's scope, which starts at submit."""
    if not killswitch.is_on("attachments.deep_check", conn):
        return "switched_off"
    att = conn.execute(
        "SELECT a.id, a.store_key, a.state, a.mime, a.idea_uuid, a.checks FROM attachments a WHERE a.id = %s",
        (att_id,),
    ).fetchone()
    if att is None or att["state"] != "clean":
        return "not_clean"
    if att["idea_uuid"] is None:
        return "not_an_idea_file"
    idea = conn.execute(
        "SELECT idea_id, stage, visibility, lobs, area_ids, category, canvas FROM ideas WHERE id = %s",
        (att["idea_uuid"],),
    ).fetchone()
    if idea is None:
        return "missing"
    if idea["idea_id"] is None or idea["stage"] in ("draft", "scanning", "blocked"):
        conn.execute(  # no dedupe key: this job still holds it while it runs
            "INSERT INTO jobs (type, payload, run_at) VALUES ('attachment.digest', %s, now() + interval '10 minutes')",
            (Jsonb({"attachment_id": att_id}),),
        )
        return "waiting_for_submit"
    data = store.get(get_settings().s3_bucket_clean, att["store_key"])
    kind = sniff(data) or ""
    extractor = f"{kind}_ocr" if (att["checks"] or {}).get("ocr") else kind
    try:
        extracted = sandbox.extract(
            extractor, data, timeout_s=OCR_TIMEOUT_S if extractor.endswith("_ocr") else 90.0
        )
    except sandbox.ExtractionFailed as exc:
        log.warning("attachments.digest_unreadable", attachment_id=att_id, reason_code=exc.code)
        return "unreadable"
    with conn.transaction():
        out = deep_checks.digest_and_index(conn, dict(att), dict(idea), extracted, extractor)
    log.info("attachments.digested", attachment_id=att_id, agent_ok=out["digest"], chunk_count=out["indexed"])
    return "done"


def recheck(conn: Conn) -> int:
    """Files held for OCR or the gatekeeper go back through the checks while the deep check is on (every 15 min)."""
    if not killswitch.is_on("attachments.deep_check", conn):
        return 0
    # Only files whose blocker is gone: OCR is back with the switch; the gatekeeper needs the assistant.
    waiting = ["ocr"]
    if killswitch.is_on("ai.all", conn) and killswitch.is_on("agent.gatekeeper", conn):
        waiting.append("gatekeeper")
    rows = conn.execute(
        "UPDATE attachments SET state = 'quarantine' WHERE state = 'awaiting_check' "
        "AND coalesce(checks->>'waiting_for', 'ocr') = ANY(%s) RETURNING id",
        (waiting,),
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO jobs (type, payload, dedupe_key) VALUES ('attachment.process', %s, %s) ON CONFLICT DO NOTHING",
            (Jsonb({"attachment_id": r["id"]}), f"attachment:{r['id']}:recheck"),
        )
    return len(rows)


def content(conn: Conn, att_id: str) -> tuple[bytes, str, str]:
    """A clean file's bytes, MIME type and name. Anything not clean is refused."""
    row = conn.execute(
        "SELECT mime, name, store_key, state FROM attachments WHERE id = %s", (att_id,)
    ).fetchone()
    if row is None or row["state"] != "clean":
        raise AttachmentRefused(403, "not_available")
    return store.get(get_settings().s3_bucket_clean, row["store_key"]), row["mime"], row["name"]


def remove(conn: Conn, att_id: str) -> None:
    s = get_settings()
    with conn.transaction():  # waits for a check that is committing this file, then removes every copy
        row = conn.execute("SELECT store_key FROM attachments WHERE id = %s FOR UPDATE", (att_id,)).fetchone()
        if row is None:
            return
        for bucket in (s.s3_bucket_quarantine, s.s3_bucket_clean):
            store.delete(bucket, row["store_key"])
        conn.execute("DELETE FROM attachments WHERE id = %s", (att_id,))


def give_up(conn: Conn, att_id: str) -> None:
    """The checks could not finish after every retry (for example the scanner stayed down): reject the file
    so the person is told, and delete the quarantine copy."""
    s = get_settings()
    row = conn.execute("SELECT store_key, state FROM attachments WHERE id = %s", (att_id,)).fetchone()
    if row is None or row["state"] not in ("quarantine", "processing"):
        return
    store.delete(s.s3_bucket_quarantine, row["store_key"])
    reason = {"type": "check_failed", "code": "check_failed", "location": "the whole file"}
    conn.execute(
        "UPDATE attachments SET state = 'rejected', rejection = %s WHERE id = %s", (Jsonb(reason), att_id)
    )
    log.warning("attachments.check_failed", attachment_id=att_id)
