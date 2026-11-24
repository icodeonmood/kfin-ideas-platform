"""Email through the KFin service mailbox with Microsoft Graph (BLD-A243, DEC-131): application permission, client
credentials, MIME send. `comms.send.deliver` calls it when `EMAIL_MODE=graph`; nothing else does.

Two hosts only, fixed here and never read from a setting: `login.microsoftonline.com` for the token and
`graph.microsoft.com` for the send. The token is kept in this process until 5 minutes before it expires; a 401 from
sendMail drops it and tries once more with a new one. The message goes exactly as `comms.send.build_message` built it
(plain text first, HTML second), base64 MIME with `Content-Type: text/plain`, so Graph keeps both parts and the From
line. A MIME send cannot turn off `saveToSentItems`: the service mailbox's Sent Items keeps a copy (IT's retention).

202 is sent. 429 and 5xx, a timeout or no connection raise `EmailRetry` (with Graph's Retry-After, capped at 15
minutes); any other answer raises `EmailRefused`, for good. Both carry a code (`graph_429`, `graph_5xx`, `graph_4xx`,
`graph_timeout`; `graph_token_…` for the token) and the HTTP status only: never the address, the subject, the body,
the token or Graph's answer (non-negotiable 3). httpx's own errors are dropped (`from None`): they name the URL,
which holds the mailbox.
"""

from __future__ import annotations

import base64
import datetime as dt
import threading
import time
from email import policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from core.config import Settings, get_settings
from core.logging import get_logger

log = get_logger("comms.graph")

LOGIN_HOST = "login.microsoftonline.com"
GRAPH_HOST = "graph.microsoft.com"
SCOPE = f"https://{GRAPH_HOST}/.default"
TIMEOUT_S = 10.0
REFRESH_EARLY_S = 300  # a token is used until 5 minutes before it expires
MAX_RETRY_AFTER_S = 900  # Graph's Retry-After is honoured up to 15 minutes

# Tests put an `httpx.MockTransport` here; None is httpx's own transport (the network).
transport: httpx.BaseTransport | None = None

_lock = threading.Lock()
# (tenant, client) -> (token, the monotonic time to stop using it)
_tokens: dict[tuple[str, str], tuple[str, float]] = {}


class EmailRetry(Exception):
    """Try this message again later: Graph is busy (429) or down (5xx), or did not answer in time."""

    def __init__(self, code: str, status: int | None = None, retry_after_s: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after_s = retry_after_s


class EmailRefused(Exception):
    """Graph refused this message for good (any answer but 202, 429 or 5xx): it is not tried again."""

    def __init__(self, code: str, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def reset() -> None:
    """Forget every cached token (tests, and a 401 from sendMail)."""
    with _lock:
        _tokens.clear()


def send(msg: EmailMessage) -> None:
    """Send one built message from the service mailbox. Returns only when Graph accepted it (202)."""
    s = get_settings()
    if not (s.graph_tenant_id and s.graph_client_id and s.graph_client_secret and s.graph_service_mailbox):
        raise EmailRetry("graph_not_configured")
    body = base64.b64encode(msg.as_bytes(policy=policy.SMTP))
    url = f"https://{GRAPH_HOST}/v1.0/users/{quote(s.graph_service_mailbox.strip(), safe='@')}/sendMail"
    with httpx.Client(timeout=TIMEOUT_S, transport=transport, follow_redirects=False) as client:
        for attempt in (1, 2):
            token = _token(client, s)
            resp = _post(
                client,
                url,
                "graph",
                content=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
            )
            if resp.status_code == 202:
                return
            # A 401 means the token went stale early: one new token, one more try.
            if resp.status_code == 401 and attempt == 1:
                with _lock:
                    _tokens.pop((s.graph_tenant_id, s.graph_client_id), None)
                log.info("comms.graph_token_dropped", http_status=401, attempt=attempt)
                continue
            raise _failure("graph", resp)


def _token(client: httpx.Client, s: Settings) -> str:
    key = (s.graph_tenant_id, s.graph_client_id)
    now = time.monotonic()
    with _lock:
        cached = _tokens.get(key)
        if cached and cached[1] > now:
            return cached[0]
    resp = _post(
        client,
        f"https://{LOGIN_HOST}/{quote(s.graph_tenant_id.strip(), safe='')}/oauth2/v2.0/token",
        "graph_token",
        data={
            "client_id": s.graph_client_id,
            "client_secret": s.graph_client_secret,
            "scope": SCOPE,
            "grant_type": "client_credentials",
        },
    )
    if resp.status_code != 200:
        raise _failure("graph_token", resp)
    try:
        payload: Any = resp.json()
        token = str(payload["access_token"])
        expires_in = int(payload.get("expires_in", 0))
    except (ValueError, KeyError, TypeError, AttributeError):
        raise EmailRetry("graph_token_unreadable", resp.status_code) from None
    if not token:
        raise EmailRetry("graph_token_unreadable", resp.status_code)
    if expires_in > REFRESH_EARLY_S:  # a token that lives 5 minutes or less is used once and not kept
        with _lock:
            _tokens[key] = (token, now + expires_in - REFRESH_EARLY_S)
    return token


def _post(client: httpx.Client, url: str, prefix: str, **kwargs: Any) -> httpx.Response:
    try:
        return client.post(url, **kwargs)
    except httpx.TimeoutException:
        raise EmailRetry(f"{prefix}_timeout") from None
    except httpx.HTTPError:
        raise EmailRetry(f"{prefix}_unreachable") from None


def _failure(prefix: str, resp: httpx.Response) -> EmailRetry | EmailRefused:
    """429 and 5xx are tried again; anything else is final. The code is the status family, never Graph's text."""
    status = resp.status_code
    if status == 429:
        return EmailRetry(f"{prefix}_429", status, _retry_after(resp))
    if status >= 500:
        return EmailRetry(f"{prefix}_5xx", status, _retry_after(resp))
    return EmailRefused(f"{prefix}_{status // 100}xx", status)


def _retry_after(resp: httpx.Response) -> int | None:
    """Graph's Retry-After in seconds (a number or an HTTP date), 0 to 15 minutes; None when absent or unreadable."""
    raw = resp.headers.get("Retry-After", "").strip()
    if not raw:
        return None
    if raw.isdigit():
        seconds = int(raw)
    else:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.UTC)
        seconds = int((when - dt.datetime.now(dt.UTC)).total_seconds())
    return max(0, min(seconds, MAX_RETRY_AFTER_S))
