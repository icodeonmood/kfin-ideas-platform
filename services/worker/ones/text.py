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


def _verdict(gk_data: dict[str, Any]) -> None:
    """The gatekeeper's reading, as a refusal: personal data is blocked, and text it would hold for a person (abuse
    or spam, BLD-074) is refused too, so the writer can change it (Ones review, BLD-111)."""
    from scan.pipeline import decide, thresholds  # the scan's own reading of the gatekeeper's output

    verdict = decide(gk_data, thresholds())
    if verdict == "blocked":
        raise OnesRefused(422, "personal_data")
    if verdict == "held":
        raise OnesRefused(422, "text_needs_review")


def no_names(conn: Conn, text: str) -> None:
    """Text that will be shown to everyone (a One's title or impact brief) may not name a colleague or a client:
    the same detector the wall's summaries pass (BLD-111)."""
    from pii.detect import detect, directory

    if detect(text, directory(conn)):
        raise OnesRefused(422, "names_not_allowed")


def checked(
    conn: Conn,
    text: Any,
    *,
    min_chars: int = 10,
    max_chars: int = 400,
    max_words: int | None = None,
    public: bool = False,
) -> str:
    """The text, whitespace tidied, if it passes the length rules, the patterns and the gatekeeper (and, for text
    everyone will see, the colleague and client detector). Run it before any transaction opens: the gatekeeper is
    a model call."""
    clean = " ".join(str(text or "").split())
    if len(clean) < min_chars:
        raise OnesRefused(422, "text_too_short")
    if len(clean) > max_chars or (max_words is not None and len(clean.split()) > max_words):
        raise OnesRefused(422, "text_too_long")
    if any(m.action == "block" for m in scan(clean, kfin_domains=get_settings().kfin_domains)):
        raise OnesRefused(422, "personal_data")
    if public:
        no_names(conn, clean)
    # A fresh draft scope: any tags the gateway makes for this check never mix with an idea's own tags.
    gk = run_agent(
        "gatekeeper",
        {"mode": "submission", "submission": {"choice_text": clean}},
        _draft_scope(),
        conn=conn,
    )
    _verdict(gk.data)
    return clean


def checked_parts(
    conn: Conn, parts: dict[str, Any], keys: tuple[str, ...], *, max_chars: int = 600
) -> dict[str, str]:
    """Several short texts at once (the Showcase brief): patterns on each, then one gatekeeper call for all of
    them. Empty parts are allowed and stay empty."""
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
        _verdict(gk.data)
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
