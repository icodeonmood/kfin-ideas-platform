"""Free text in the Ones module (citations, reasons, titles, impact briefs) is checked like any other text people
type: the shared pattern rules first, then the gatekeeper through the gateway (which tags before it sends), and
only then stored, encrypted. Personal data is refused with a code; the text is never logged (non-negotiables 2, 3).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from core.config import get_settings
from core.crypto import CryptoError, decrypt_json, encrypt_json
from core.db import Conn
from gateway import run_agent
from pii.patterns import scan

_DIGIT_RUN = re.compile(r"[0-9]{6}")


def _draft_scope() -> str:
    """A fresh draft scope for one check. Its ID is logged by the gateway, so it must never look like a number a
    person has (a phone or account number hiding in a random UUID would trip the log policy)."""
    while True:
        u = str(uuid.uuid4())
        if not _DIGIT_RUN.search(u.replace("-", "")):
            return f"DRAFT-{u}"


class OnesRefused(Exception):
    """A refused Ones action. `code` is safe to show and log; the request's text never is."""

    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def checked(
    conn: Conn, text: Any, *, min_chars: int = 10, max_chars: int = 400, max_words: int | None = None
) -> str:
    """The text, whitespace tidied, if it passes the length rules, the patterns and the gatekeeper. Run it before
    any transaction opens: the gatekeeper is a model call."""
    from scan.pipeline import decide, thresholds  # the scan's own reading of the gatekeeper's output

    clean = " ".join(str(text or "").split())
    if len(clean) < min_chars:
        raise OnesRefused(422, "text_too_short")
    if len(clean) > max_chars or (max_words is not None and len(clean.split()) > max_words):
        raise OnesRefused(422, "text_too_long")
    if any(m.action == "block" for m in scan(clean, kfin_domains=get_settings().kfin_domains)):
        raise OnesRefused(422, "personal_data")
    # A fresh draft scope: any tags the gateway makes for this check never mix with an idea's own tags.
    gk = run_agent(
        "gatekeeper",
        {"mode": "submission", "submission": {"choice_text": clean}},
        _draft_scope(),
        conn=conn,
    )
    if decide(gk.data, thresholds()) == "blocked":
        raise OnesRefused(422, "personal_data")
    return clean


def checked_parts(
    conn: Conn, parts: dict[str, Any], keys: tuple[str, ...], *, max_chars: int = 600
) -> dict[str, str]:
    """Several short texts at once (the Showcase brief): patterns on each, then one gatekeeper call for all of
    them. Empty parts are allowed and stay empty."""
    from scan.pipeline import decide, thresholds

    clean: dict[str, str] = {}
    for key in keys:
        text = " ".join(str(parts.get(key) or "").split())
        if len(text) > max_chars:
            raise OnesRefused(422, "text_too_long")
        if text and any(m.action == "block" for m in scan(text, kfin_domains=get_settings().kfin_domains)):
            raise OnesRefused(422, "personal_data")
        clean[key] = text
    filled = {k: v for k, v in clean.items() if v}
    if filled:
        gk = run_agent("gatekeeper", {"mode": "submission", "submission": filled}, _draft_scope(), conn=conn)
        if decide(gk.data, thresholds()) == "blocked":
            raise OnesRefused(422, "personal_data")
    return clean


def seal_json(value: Any, context: str) -> bytes:
    return encrypt_json(value, context)


def unseal_json(blob: Any, context: str) -> Any:
    if blob is None:
        return None
    try:
        return decrypt_json(bytes(blob), context)
    except CryptoError:
        return None


def seal(text: str | None, context: str) -> bytes | None:
    return None if text is None else encrypt_json({"text": text}, context)


def unseal(blob: Any, context: str) -> str | None:
    if blob is None:
        return None
    try:
        return str(decrypt_json(bytes(blob), context).get("text") or "") or None
    except CryptoError:
        return None
