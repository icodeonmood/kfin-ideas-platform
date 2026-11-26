"""Email through the KFin service mailbox with Microsoft Graph (BLD-A243, DEC-131): application permission, client
credentials, MIME send. `comms.send.deliver` calls it when `EMAIL_MODE=graph`; nothing else does.

Two hosts only, fixed here and never read from a setting: `login.microsoftonline.com` for the token and
`graph.microsoft.com` for the send. One httpx client serves the whole process (10-second timeout, no redirects). The
token is kept until 5 minutes before it expires; a 401 from sendMail drops it and tries once more with a new one. The
message goes exactly as `comms.send.build_message` built it (plain text first, HTML second), base64 MIME with
`Content-Type: text/plain`, so Graph keeps both parts and the From line. A MIME send cannot turn off
`saveToSentItems`: the service mailbox's Sent Items keeps a copy (IT's retention).

Every failure is one of three kinds, each with a code (the status family, never Graph's text) and the HTTP status:
- `EmailRetry`: Graph is busy or out of reach. A 429 (`graph_429`, `graph_token_429`) waits Graph's Retry-After (60 s
  without one, at most 15 minutes) and never spends a try; a 5xx, a timeout or no connection, from sendMail or the
  token call (`graph_5xx`, `graph_timeout`, `graph_unreachable`; `graph_token_5xx`, `graph_token_timeout`,
  `graph_token_unreachable`), waits 5 minutes and spends one. Either sets the process-wide wait (`wait_left`), which
  the send loops read before they pick anything. `comms.email` is left as it is.
- `MailboxFault`: nothing can go until a person fixes the mailbox, the app registration or the settings: the token
  refused (`graph_token_4xx`) or unreadable (`graph_token_bad`), no settings (`graph_not_configured`), and a sendMail
  401 after one fresh token, 403 or 404 (`graph_4xx`). The send loop stops and switches `comms.email` off
  (comms/send.py).
- `EmailRefused`: Graph refused this one message for good (any other answer but 202); the next one goes.

Never the address, the subject, the body, the token or Graph's answer (non-negotiable 3). httpx's own errors are
dropped (`from None`): they name the URL, which holds the mailbox.
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
THROTTLE_S = 60  # a 429 without a Retry-After
OUTAGE_S = 300  # a 5xx, a timeout or no connection
MAILBOX_STATUSES = (401, 403, 404)  # sendMail answers that mean the mailbox or the app, not the message

# Tests put an `httpx.MockTransport` here; None is httpx's own transport (the network).
transport: httpx.BaseTransport | None = None

_lock = threading.Lock()
# (tenant, client) -> (token, the monotonic time to stop using it)
_tokens: dict[tuple[str, str], tuple[str, float]] = {}
_not_before = 0.0  # monotonic: no send loop picks anything before it (A2)
_client: httpx.Client | None = None
_client_transport: httpx.BaseTransport | None = None


class GraphError(Exception):
    """A send through Graph that did not go: `code` is the status family, `status` the HTTP status (or None)."""

    def __init__(self, code: str, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


class EmailRetry(GraphError):
    """Graph is busy or out of reach: try again after `wait_s`. Only a 5xx, a timeout or no connection spends a try."""

    def __init__(self, code: str, status: int | None, wait_s: float, *, spends_try: bool) -> None:
        super().__init__(code, status)
        self.wait_s = wait_s
        self.spends_try = spends_try


class MailboxFault(GraphError):
    """Nothing can go until a person fixes the mailbox, the app registration or the settings."""


class EmailRefused(GraphError):
    """Graph refused this one message for good: it is not tried again."""


def wait_left() -> float:
    """Seconds until Graph may be asked again (0 when it may be asked now). Process-wide; read before any pick."""
    with _lock:
        return max(0.0, _not_before - time.monotonic())


def _hold(seconds: float) -> None:
    global _not_before
    with _lock:
        _not_before = max(_not_before, time.monotonic() + max(0.0, seconds))


def _retry(code: str, status: int | None, wait_s: float, *, spends_try: bool) -> EmailRetry:
    _hold(wait_s)
    return EmailRetry(code, status, wait_s, spends_try=spends_try)


def reset() -> None:
    """Forget the cached tokens, the wait and the client (tests)."""
    global _not_before, _client, _client_transport
    with _lock:
        _tokens.clear()
        _not_before = 0.0
        if _client is not None:
            _client.close()
        _client, _client_transport = None, None


def _http() -> httpx.Client:
    """The process's one client: its connection pool is safe to share between threads."""
    global _client, _client_transport
    with _lock:
        if _client is None or _client_transport is not transport:
            if _client is not None:
                _client.close()
            _client = httpx.Client(timeout=TIMEOUT_S, transport=transport, follow_redirects=False)
            _client_transport = transport
        return _client


def send(msg: EmailMessage) -> None:
    """Send one built message from the service mailbox. Returns only when Graph accepted it (202)."""
    s = get_settings()
    if not (s.graph_tenant_id and s.graph_client_id and s.graph_client_secret and s.graph_service_mailbox):
        raise MailboxFault("graph_not_configured")
    body = base64.b64encode(msg.as_bytes(policy=policy.SMTP))
    url = f"https://{GRAPH_HOST}/v1.0/users/{quote(s.graph_service_mailbox.strip(), safe='@')}/sendMail"
    client = _http()
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
    except ValueError:
        payload = None
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:  # never cached
        raise MailboxFault("graph_token_bad", resp.status_code)
    try:
        expires_in = int(payload.get("expires_in", 0))
    except (TypeError, ValueError, OverflowError):
        expires_in = 0
    if expires_in > REFRESH_EARLY_S:  # a token that lives 5 minutes or less is used once and not kept
        with _lock:
            _tokens[key] = (token, now + expires_in - REFRESH_EARLY_S)
    return token


def _post(client: httpx.Client, url: str, prefix: str, **kwargs: Any) -> httpx.Response:
    try:
        return client.post(url, **kwargs)
    except httpx.TimeoutException:
        kind = "timeout"
    except httpx.HTTPError:
        kind = "unreachable"
    raise _retry(
        f"{prefix}_{kind}", None, OUTAGE_S, spends_try=True
    ) from None  # an outage, token call or not


def _failure(prefix: str, resp: httpx.Response) -> GraphError:
    """What an answer other than the one wanted means. The code is the status family, never Graph's text."""
    status = resp.status_code
    family = f"{prefix}_{status // 100}xx"
    if status == 429:
        wait = _retry_after(resp)
        return _retry(f"{prefix}_429", status, THROTTLE_S if wait is None else wait, spends_try=False)
    if status >= 500:  # an outage, token call or not
        return _retry(family, status, OUTAGE_S, spends_try=True)
    if prefix == "graph_token":  # the token refused: the app registration or the secret
        return MailboxFault(family, status)
    if status in MAILBOX_STATUSES:
        return MailboxFault(family, status)
    return EmailRefused(family, status)


def _retry_after(resp: httpx.Response) -> int | None:
    """Graph's Retry-After in seconds (a number or an HTTP date), 0 to 15 minutes; None when absent or unreadable."""
    raw = resp.headers.get("Retry-After", "").strip()
    if not raw:
        return None
    try:
        if raw.isascii() and raw.isdigit():
            seconds = int(raw)
        else:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.UTC)
            seconds = int((when - dt.datetime.now(dt.UTC)).total_seconds())
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return max(0, min(seconds, MAX_RETRY_AFTER_S))
