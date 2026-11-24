"""BLD-A243 (DEC-131, L-NOTIFY): email through the KFin service mailbox with Microsoft Graph, application permission,
client credentials, MIME send. One transport (`comms.send.deliver`) for every sender; `EMAIL_MODE=smtp` keeps the SMTP
path. No network: Graph is an `httpx.MockTransport`, the database a recording fake, SMTP a stub. Synthetic values
only: no tenant, client, secret or mailbox here is real. Safe under `-m "not stack"`."""

from __future__ import annotations

import base64
import datetime as dt
import email
import logging
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from email import policy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from bootstrap import preflight
from comms import email_check, email_html, graph, send
from core import logging as klog
from core.config import Settings, get_settings
from tests.test_b7_uat import GOOD
from tests.test_compose_speech import _compose

ROOT = Path(__file__).resolve().parents[3]
LOGIN, GRAPH = "login.microsoftonline.com", "graph.microsoft.com"
TENANT, CLIENT = "tenant-syn-0001", "client-syn-0001"
SECRET = "synthetic-graph-secret-never-real-0001"
MAILBOX = "onepercentclub@kfintech.example"
SENDER = f"1% Club <{MAILBOX}>"
TO = "kavya.syn@kfintech.example"
SUBJECT = "Your idea SYN-0001 has a reply"
MAIL = email_html.Email(
    subject=SUBJECT,
    text="Hi Kavya,\n\nThe review desk replied to your idea.\n",
    html="<p>Hi Kavya,</p><p>The review desk replied to your idea.</p>",
)


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()


@pytest.fixture
def graph_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _settings(
        monkeypatch,
        EMAIL_MODE="graph",
        EMAIL_FROM=SENDER,
        GRAPH_TENANT_ID=TENANT,
        GRAPH_CLIENT_ID=CLIENT,
        GRAPH_CLIENT_SECRET=SECRET,
        GRAPH_SERVICE_MAILBOX=MAILBOX,
    )
    graph.reset()
    yield
    graph.reset()
    get_settings.cache_clear()


class FakeGraph:
    """Answers the token endpoint with tok-1, tok-2, … and sendMail with the queued answers, in order."""

    def __init__(
        self, *sends: httpx.Response | BaseException, token: httpx.Response | BaseException | None = None
    ) -> None:
        self.requests: list[httpx.Request] = []
        self.sends = list(sends)
        self.token_answer = token
        self.tokens = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == LOGIN:
            if isinstance(self.token_answer, BaseException):
                raise self.token_answer
            if self.token_answer is not None:
                return self.token_answer
            self.tokens += 1
            return httpx.Response(200, json={"access_token": f"tok-{self.tokens}", "expires_in": 3599})
        assert request.url.host == GRAPH  # never any other host
        answer = self.sends.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def to(self, host: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, graph_mode: None) -> Callable[..., FakeGraph]:
    def install(
        *sends: httpx.Response | BaseException, token: httpx.Response | BaseException | None = None
    ) -> FakeGraph:
        g = FakeGraph(*sends, token=token)
        monkeypatch.setattr(graph, "transport", httpx.MockTransport(g))
        return g

    return install


def ok() -> httpx.Response:
    return httpx.Response(202)


# ---- the token: client credentials, kept until 5 minutes before it expires, one refresh on a 401 ------------------


def test_a243_the_token_request_is_client_credentials_for_graph(fake: Callable[..., FakeGraph]) -> None:
    g = fake(ok())
    send.deliver(TO, MAIL)
    [tok] = g.to(LOGIN)
    assert tok.method == "POST" and tok.url.scheme == "https"
    assert tok.url.path == f"/{TENANT}/oauth2/v2.0/token"
    assert tok.headers["content-type"] == "application/x-www-form-urlencoded"
    assert parse_qs(tok.content.decode()) == {
        "client_id": [CLIENT],
        "client_secret": [SECRET],
        "scope": ["https://graph.microsoft.com/.default"],
        "grant_type": ["client_credentials"],
    }


def test_a243_one_token_serves_two_sends_until_five_minutes_before_it_expires(
    fake: Callable[..., FakeGraph], monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(graph, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    g = fake(ok(), ok(), ok())
    send.deliver(TO, MAIL)
    send.deliver(TO, MAIL)
    assert len(g.to(LOGIN)) == 1
    assert [r.headers["authorization"] for r in g.to(GRAPH)] == ["Bearer tok-1", "Bearer tok-1"]
    clock[0] += 3599 - 300  # 5 minutes before expires_in: a new token
    send.deliver(TO, MAIL)
    assert len(g.to(LOGIN)) == 2 and g.to(GRAPH)[-1].headers["authorization"] == "Bearer tok-2"


def test_a243_a_401_drops_the_token_and_tries_once_more(fake: Callable[..., FakeGraph]) -> None:
    g = fake(httpx.Response(401), ok())
    send.deliver(TO, MAIL)
    assert len(g.to(LOGIN)) == 2
    assert [r.headers["authorization"] for r in g.to(GRAPH)] == ["Bearer tok-1", "Bearer tok-2"]


def test_a243_a1_a_second_401_is_a_mailbox_fault_and_never_a_third_try(
    fake: Callable[..., FakeGraph],
) -> None:
    g = fake(httpx.Response(401), httpx.Response(401), ok())
    with pytest.raises(graph.MailboxFault) as fault:
        send.deliver(TO, MAIL)
    assert (fault.value.code, fault.value.status) == ("graph_4xx", 401)
    assert len(g.to(GRAPH)) == 2 and len(g.to(LOGIN)) == 2


@pytest.mark.parametrize(
    ("answer", "error", "code", "status"),
    [(httpx.Response(400), graph.MailboxFault, "graph_token_4xx", 400),
     (httpx.Response(401), graph.MailboxFault, "graph_token_4xx", 401),
     (httpx.Response(503), graph.MailboxFault, "graph_token_5xx", 503),
     (httpx.ReadTimeout("timed out"), graph.MailboxFault, "graph_token_timeout", None),
     (httpx.ConnectError("no route"), graph.MailboxFault, "graph_token_unreachable", None),
     (httpx.Response(429, headers={"Retry-After": "30"}), graph.EmailRetry, "graph_token_429", 429)],
)  # fmt: skip
def test_a243_a1_a_failed_token_stops_everything_but_a_429_waits(
    fake: Callable[..., FakeGraph], answer: Any, error: type[Exception], code: str, status: int | None
) -> None:
    if isinstance(answer, httpx.Response):
        answer = httpx.Response(
            answer.status_code,
            headers={k: v for k, v in answer.headers.items() if k.lower() == "retry-after"},
            json={"error": "invalid_client", "error_description": SECRET},
        )
    g = fake(ok(), token=answer)
    with pytest.raises(error) as raised:
        send.deliver(TO, MAIL)
    exc: Any = raised.value
    assert (exc.code, exc.status) == (code, status) and g.to(GRAPH) == []
    assert str(exc) == code  # never Graph's answer
    assert (graph.wait_left() > 0) is (error is graph.EmailRetry)
    if error is graph.EmailRetry:
        assert exc.spends_try is False and exc.wait_s == 30


@pytest.mark.parametrize(
    "payload",
    [{"access_token": "", "expires_in": 3599}, {"access_token": 1234, "expires_in": 3599}, {"expires_in": 3599},
     ["tok-1"], None],
)  # fmt: skip
def test_a243_a6_a_token_that_is_not_a_string_is_graph_token_bad_and_never_kept(
    fake: Callable[..., FakeGraph], payload: Any
) -> None:
    answer = httpx.Response(200, text="not json") if payload is None else httpx.Response(200, json=payload)
    g = fake(ok(), ok(), token=answer)
    for _ in range(2):
        with pytest.raises(graph.MailboxFault) as fault:
            send.deliver(TO, MAIL)
        assert fault.value.code == "graph_token_bad"
    assert len(g.to(LOGIN)) == 2 and g.to(GRAPH) == []  # asked again each time: nothing was cached


def test_a243_a6_one_client_for_the_whole_process(fake: Callable[..., FakeGraph]) -> None:
    import threading

    fake(ok(), ok())
    send.deliver(TO, MAIL)
    first = graph._client
    send.deliver(TO, MAIL)
    assert first is not None and graph._client is first
    assert first.timeout.read == graph.TIMEOUT_S and first.follow_redirects is False
    seen: list[Any] = []
    threads = [threading.Thread(target=lambda: seen.append(graph._http())) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(c is first for c in seen)


# ---- sendMail: the URL, the headers and the MIME body exactly as built ----------------------------------------------


def test_a243_sendmail_posts_the_built_message_as_base64_mime(fake: Callable[..., FakeGraph]) -> None:
    g = fake(ok())
    send.deliver(TO, MAIL)
    [req] = g.to(GRAPH)
    assert req.method == "POST" and str(req.url) == f"https://{GRAPH}/v1.0/users/{MAILBOX}/sendMail"
    assert req.headers["authorization"] == "Bearer tok-1" and req.headers["content-type"] == "text/plain"
    msg = email.message_from_bytes(base64.b64decode(req.content, validate=True), policy=policy.default)
    assert (msg["From"], msg["To"], msg["Subject"]) == (SENDER, TO, SUBJECT)
    assert msg.get_content_type() == "multipart/alternative"
    parts = list(msg.iter_parts())
    assert [p.get_content_type() for p in parts] == ["text/plain", "text/html"]
    assert (
        "The review desk replied" in parts[0].get_content() and "<p>Hi Kavya,</p>" in parts[1].get_content()
    )
    assert b"\r\n" in base64.b64decode(req.content)  # wire line endings


def test_a243_the_mailbox_is_quoted_in_the_path(
    fake: Callable[..., FakeGraph], monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, GRAPH_SERVICE_MAILBOX="ones+club/x?y#z@kfintech.example")
    g = fake(ok())
    send.deliver(TO, MAIL)
    [req] = g.to(GRAPH)
    assert req.url.raw_path == b"/v1.0/users/ones%2Bclub%2Fx%3Fy%23z@kfintech.example/sendMail"
    assert req.url.host == GRAPH and not req.url.query


# ---- Graph's answers: 202 sent; 429 waits; 5xx and timeouts retried; 401/403/404 stop; any other final ------------


@pytest.mark.parametrize(
    ("answer", "error", "code", "status", "wait", "spends"),
    [
        (httpx.Response(429, headers={"Retry-After": "120"}), graph.EmailRetry, "graph_429", 429, 120, False),
        (
            httpx.Response(429, headers={"Retry-After": "86400"}),
            graph.EmailRetry,
            "graph_429",
            429,
            900,
            False,
        ),
        (httpx.Response(429, headers={"Retry-After": "5"}), graph.EmailRetry, "graph_429", 429, 5, False),
        (httpx.Response(429), graph.EmailRetry, "graph_429", 429, 60, False),
        (httpx.Response(503, text=f"busy for {TO}"), graph.EmailRetry, "graph_5xx", 503, 300, True),
        (httpx.Response(503, headers={"Retry-After": "900"}), graph.EmailRetry, "graph_5xx", 503, 300, True),
        (httpx.Response(500), graph.EmailRetry, "graph_5xx", 500, 300, True),
        (
            httpx.Response(400, text=f"bad message {SUBJECT}"),
            graph.EmailRefused,
            "graph_4xx",
            400,
            None,
            None,
        ),
        (httpx.Response(413), graph.EmailRefused, "graph_4xx", 413, None, None),
        (httpx.Response(403), graph.MailboxFault, "graph_4xx", 403, None, None),
        (httpx.Response(404), graph.MailboxFault, "graph_4xx", 404, None, None),
    ],
)
def test_a243_graphs_answer_decides_wait_retry_stop_or_final(
    fake: Callable[..., FakeGraph],
    answer: httpx.Response,
    error: type[Exception],
    code: str,
    status: int,
    wait: int | None,
    spends: bool | None,
) -> None:
    fake(answer)
    with pytest.raises(error) as raised:
        send.deliver(TO, MAIL)
    exc: Any = raised.value
    assert (exc.code, exc.status) == (code, status)
    assert (getattr(exc, "wait_s", None), getattr(exc, "spends_try", None)) == (wait, spends)
    assert str(exc) == code and TO not in str(exc) and SUBJECT not in str(exc)
    assert (graph.wait_left() > 0) is (error is graph.EmailRetry and bool(wait))


def test_a243_202_is_sent(fake: Callable[..., FakeGraph]) -> None:
    g = fake(ok())
    send.deliver(TO, MAIL)  # returns: Graph accepted it
    assert [r.url.path for r in g.to(GRAPH)] == [f"/v1.0/users/{MAILBOX}/sendMail"]
    assert graph.wait_left() == 0


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (httpx.ReadTimeout("timed out"), "graph_timeout"),
        (httpx.ConnectError("no route"), "graph_unreachable"),
    ],
)
def test_a243_a_timeout_or_no_connection_is_retried_and_drops_httpxs_url(
    fake: Callable[..., FakeGraph], raised: Exception, code: str
) -> None:
    fake(raised)
    with pytest.raises(graph.EmailRetry) as retry:
        send.deliver(TO, MAIL)
    assert retry.value.code == code and retry.value.status is None
    assert (retry.value.wait_s, retry.value.spends_try) == (300, True)
    assert retry.value.__suppress_context__ or retry.value.__context__ is None  # httpx's error names the URL
    assert retry.value.__cause__ is None


def test_a243_a6_retry_after_as_an_http_date_or_ascii_digits_only() -> None:
    later = (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=10)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    seconds = graph._retry_after(httpx.Response(429, headers={"Retry-After": later}))
    assert seconds is not None and 590 <= seconds <= 600
    for raw in ("soon", "\uff11\uff12\uff10", "\u00b2", "-5", "1e3"):  # fullwidth and superscript digits too
        headers = [(b"Retry-After", raw.encode())]  # as bytes: what reaches the worker off the wire
        assert graph._retry_after(httpx.Response(429, headers=headers)) is None, raw
    assert graph._retry_after(httpx.Response(429, headers={"Retry-After": "120"})) == 120


def test_a243_a1_without_its_settings_graph_sends_nothing(
    fake: Callable[..., FakeGraph], monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, GRAPH_CLIENT_SECRET="")
    g = fake(ok())
    with pytest.raises(graph.MailboxFault) as fault:
        send.deliver(TO, MAIL)
    assert fault.value.code == "graph_not_configured" and g.requests == []


# ---- the send loop: how each answer lands on the notification ------------------------------------------------------


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


class FakeConn:
    """A recording connection. A statement counts as committed only when its transaction block ends without an
    exception (`committed`); every statement is in `calls`. The due-email pick returns the first given row not yet
    tried in this call; the users lookup returns `users`; a kill switch reads "on"."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        users: list[dict[str, Any]] | None = None,
        digest_people: list[dict[str, Any]] | None = None,
    ) -> None:
        self.rows = rows or []
        self.users = users or []
        self.digest_people = digest_people or []
        self.calls: list[tuple[str, Any]] = []
        self.committed: list[tuple[str, Any]] = []
        self._open: list[list[tuple[str, Any]]] = []

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._open.append([])
        try:
            yield
        except BaseException:
            self._open.pop()  # rolled back
            raise
        done = self._open.pop()
        (self._open[-1] if self._open else self.committed).extend(done)

    def execute(self, sql: str, params: Any = None) -> _Cursor:
        flat = " ".join(sql.split())
        self.calls.append((flat, params))
        (self._open[-1] if self._open else self.committed).append((flat, params))
        if flat.startswith("SELECT n.id"):
            return _Cursor([r for r in self.rows if r["id"] not in params[1]][:1])
        if flat.startswith("SELECT 1 FROM users"):
            return _Cursor(self.users)
        if flat.startswith("SELECT state FROM kill_switches"):
            return _Cursor([{"state": "on"}])
        if flat.startswith("SELECT DISTINCT n.user_id"):
            return _Cursor(self.digest_people)
        if flat.startswith("SELECT id, event, template, payload FROM notifications"):
            return _Cursor(
                [{"id": 900 + params[0], "event": "canvas.nudge", "template": "nudge", "payload": {}}]
            )
        return _Cursor([])

    def updates(self) -> list[tuple[str, Any]]:
        return [(sql, p) for sql, p in self.calls if sql.startswith("UPDATE notifications SET attempts")]

    def picks(self) -> int:
        return sum(1 for sql, _ in self.calls if sql.startswith("SELECT n.id"))

    def touching(self, row_id: int) -> list[tuple[str, Any]]:
        return [
            (sql, p)
            for sql, p in self.calls
            if sql.startswith("UPDATE notifications") and p and p[-1] == row_id
        ]


def _row(n: int, attempts: int = 0) -> dict[str, Any]:
    return {
        "id": n, "user_id": f"00000000-0000-4000-8000-00000000000{n}", "event": "idea.submitted",
        "template": "submitted", "payload": {}, "attempts": attempts, "urgency": "immediate",
        "email": f"syn.{n}@kfintech.example", "kind": None,
    }  # fmt: skip


@pytest.fixture
def loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(send.killswitch, "is_on", lambda name, conn: True)
    monkeypatch.setattr(send, "compose", lambda *a, **k: MAIL)


FIVE = dt.timedelta(minutes=5)
SENT = "UPDATE notifications SET state = 'sent', sent_at = %s WHERE id = %s"
WAIT_429 = "UPDATE notifications SET error_code = %s, send_after = clock_timestamp() + %s WHERE id = %s"
KEEP_TRY = "UPDATE notifications SET error_code = %s WHERE id = %s"


@pytest.mark.parametrize(
    ("answer", "attempts", "state", "code"),
    [
        (httpx.Response(503), 0, "queued", "graph_5xx"),
        (
            httpx.Response(503, headers={"Retry-After": "900"}),
            0,
            "queued",
            "graph_5xx",
        ),  # 5 minutes, whatever
        (httpx.Response(503), 2, "failed", "graph_5xx"),  # the third try was the last
        (httpx.ReadTimeout("timed out"), 0, "queued", "graph_timeout"),
        (httpx.ConnectError("no route"), 0, "queued", "graph_unreachable"),
    ],
)
def test_a243_a2_graph_down_spends_one_try_and_stops_the_loop_for_five_minutes(
    fake: Callable[..., FakeGraph], loop: None, answer: Any, attempts: int, state: str, code: str
) -> None:
    g = fake(answer, ok())
    conn = FakeConn([_row(1, attempts), _row(2)])
    assert send.send_due(conn) == 0  # type: ignore[arg-type]
    [(sql, params)] = conn.updates()
    assert "send_after = clock_timestamp() + %s" in sql and params == (state, code, FIVE, 1)
    assert len(g.to(GRAPH)) == 1 and conn.picks() == 1 and conn.touching(2) == []  # row 2 untouched
    assert 299 <= graph.wait_left() <= 300


def test_a243_a1_a_message_graph_refuses_fails_alone_and_the_loop_goes_on(
    fake: Callable[..., FakeGraph], loop: None
) -> None:
    g = fake(httpx.Response(400), ok())
    conn = FakeConn([_row(1), _row(2)])
    assert send.send_due(conn) == 1  # type: ignore[arg-type]
    assert [p for _, p in conn.updates()] == [("failed", "graph_4xx", FIVE, 1)]
    assert [sql for sql, _ in conn.touching(2)] == [SENT] and len(g.to(GRAPH)) == 2
    assert graph.wait_left() == 0


def test_a243_l_notify_a_202_marks_it_sent(fake: Callable[..., FakeGraph], loop: None) -> None:
    fake(ok())
    conn = FakeConn([_row(1)])
    assert send.send_due(conn) == 1  # type: ignore[arg-type]
    assert [p[1] for s, p in conn.committed if s == SENT] == [1]


@pytest.mark.parametrize(("retry_after", "wait"), [("120", 120), (None, 60), ("5", 5), ("86400", 900)])
def test_a243_a2_a_429_sets_the_wait_keeps_the_try_and_nothing_is_picked_until_it_passes(
    fake: Callable[..., FakeGraph],
    loop: None,
    monkeypatch: pytest.MonkeyPatch,
    retry_after: str | None,
    wait: int,
) -> None:
    clock = [5000.0]
    monkeypatch.setattr(graph, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    headers = {"Retry-After": retry_after} if retry_after else {}
    g = fake(httpx.Response(429, headers=headers), ok(), ok())
    conn = FakeConn([_row(1), _row(2)])
    assert send.send_due(conn) == 0  # type: ignore[arg-type]
    assert conn.updates() == []  # no try spent
    assert conn.touching(1) == [(WAIT_429, ("graph_429", dt.timedelta(seconds=wait), 1))]
    assert conn.touching(2) == [] and graph.wait_left() == wait and len(g.to(GRAPH)) == 1
    picks = conn.picks()
    clock[0] += wait - 1
    assert send.send_due(conn) == 0 and conn.picks() == picks  # type: ignore[arg-type]
    clock[0] += 1
    assert send.send_due(conn) == 2 and len(g.to(GRAPH)) == 3  # type: ignore[arg-type]


def test_a243_a2_a_token_429_waits_too_and_keeps_the_try(fake: Callable[..., FakeGraph], loop: None) -> None:
    g = fake(ok(), token=httpx.Response(429, headers={"Retry-After": "45"}))
    conn = FakeConn([_row(1), _row(2)])
    assert send.send_due(conn) == 0  # type: ignore[arg-type]
    assert conn.updates() == [] and conn.touching(1) == [
        (WAIT_429, ("graph_token_429", dt.timedelta(seconds=45), 1))
    ]
    assert g.to(GRAPH) == [] and 44 <= graph.wait_left() <= 45


@pytest.mark.parametrize(
    ("sends", "token", "code", "status"),
    [
        (
            (ok(),),
            httpx.Response(401, json={"error": "invalid_client"}),
            "graph_token_4xx",
            401,
        ),  # expired secret
        ((ok(),), httpx.Response(400), "graph_token_4xx", 400),
        ((ok(),), httpx.Response(503), "graph_token_5xx", 503),
        ((ok(),), httpx.ConnectError("no route"), "graph_token_unreachable", None),
        ((ok(),), httpx.Response(200, json={"access_token": ""}), "graph_token_bad", 200),
        ((httpx.Response(403), ok()), None, "graph_4xx", 403),
        ((httpx.Response(404), ok()), None, "graph_4xx", 404),
        ((httpx.Response(401), httpx.Response(401), ok()), None, "graph_4xx", 401),
    ],
)
def test_a243_a1_a_mailbox_fault_stops_the_loop_and_switches_email_off_audited(
    fake: Callable[..., FakeGraph],
    loop: None,
    sends: tuple[Any, ...],
    token: Any,
    code: str,
    status: int | None,
) -> None:
    g = fake(*sends, token=token)
    conn = FakeConn([_row(1), _row(2), _row(3)])
    assert send.send_due(conn) == 0  # type: ignore[arg-type]
    assert conn.picks() == 1 and conn.touching(2) == [] and conn.touching(3) == []
    assert conn.updates() == []  # no try spent, and (below) row 1 is not failed: only its code is noted
    assert conn.touching(1) == [(KEEP_TRY, (code, 1))]
    if token is not None:
        assert len(g.to(LOGIN)) == 1 and g.to(GRAPH) == []  # one token call, then nothing
    where = f"{code} (HTTP {status})" if status else code
    reason = f"Email through Graph stopped: {where} (automatic)"
    flips = [p for s, p in conn.committed if s.startswith("UPDATE kill_switches SET state")]
    assert flips == [("off", reason, "process:watch", "comms.email")]
    audits = [p for s, p in conn.committed if s.startswith("INSERT INTO audit_log")]
    assert [a[0] for a in audits] == ["process:watch", "process:watch"]
    assert [a[1] for a in audits] == ["kill_switch:comms.email", "kill_switch:comms.email"]
    assert any(isinstance(a, tuple) and reason in a for a in audits)  # kill_switch.set carries the reason
    assert graph.wait_left() == 0


def test_a243_a3_a_503_on_row_2_of_5_keeps_row_1_sent_and_leaves_3_to_5_untouched(
    fake: Callable[..., FakeGraph], loop: None
) -> None:
    g = fake(ok(), httpx.Response(503), ok(), ok(), ok())
    conn = FakeConn([_row(n) for n in range(1, 6)])
    assert send.send_due(conn) == 1  # type: ignore[arg-type]
    assert [p[1] for s, p in conn.committed if s == SENT] == [1]
    assert [p for _, p in conn.updates()] == [("queued", "graph_5xx", FIVE, 2)]
    assert all(conn.touching(n) == [] for n in (3, 4, 5)) and conn.picks() == 2 and len(g.to(GRAPH)) == 2


class Crash(BaseException):
    """The worker dies mid-send (a kill, an out-of-memory)."""


def test_a243_a3_a_crash_after_row_1s_202_leaves_row_1_sent(
    fake: Callable[..., FakeGraph], loop: None
) -> None:
    fake(ok(), Crash())
    conn = FakeConn([_row(1), _row(2)])
    with pytest.raises(Crash):
        send.send_due(conn)  # type: ignore[arg-type]
    assert [p[1] for s, p in conn.committed if s == SENT] == [1]  # committed before row 2 was picked
    assert conn.picks() == 2  # row 2 was picked, and its transaction rolled back:
    assert sum(1 for sql, _ in conn.committed if sql.startswith("SELECT n.id")) == 1


def test_a243_a4_comms_email_is_read_before_each_email(
    fake: Callable[..., FakeGraph], loop: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[str] = []
    answers = iter(
        [True, True, False]
    )  # on at the start and for row 1; an admin switches it off before row 2

    def is_on(name: str, conn: Any) -> bool:
        reads.append(name)
        return next(answers)

    monkeypatch.setattr(send.killswitch, "is_on", is_on)
    g = fake(ok(), ok(), ok())
    conn = FakeConn([_row(1), _row(2), _row(3)])
    assert send.send_due(conn) == 1  # type: ignore[arg-type]
    assert reads == ["comms.email"] * 3 and len(g.to(GRAPH)) == 1 and conn.touching(2) == []


@pytest.fixture
def digests(monkeypatch: pytest.MonkeyPatch, loop: None) -> None:
    monkeypatch.setattr(send, "next_send_time", lambda now, urgency: now)
    monkeypatch.setattr(send, "load", lambda template: template)
    monkeypatch.setattr(send, "variables", lambda *a, **k: {})
    monkeypatch.setattr(send.email_html, "digest", lambda sections, base: MAIL)


def _people(n: int) -> list[dict[str, Any]]:
    return [{"user_id": i, "email": f"syn.{i}@kfintech.example"} for i in range(1, n + 1)]


def test_a243_a5_a_429_stops_the_digests_with_the_same_wait_and_logs_code_and_status(
    fake: Callable[..., FakeGraph], digests: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    g = fake(ok(), httpx.Response(429, headers={"Retry-After": "90"}), ok())
    conn = FakeConn(digest_people=_people(3))
    assert send.send_digests(conn) == 1  # type: ignore[arg-type]
    assert len(g.to(GRAPH)) == 2 and 89 <= graph.wait_left() <= 90
    [line] = [
        klog._JsonFormatter().format(r) for r in caplog.records if r.getMessage() == "comms.batched_failed"
    ]
    assert '"error_code":"graph_429"' in line and '"http_status":429' in line and "syn." not in line
    calls = len(conn.calls)
    assert send.send_digests(conn) == 0 and len(conn.calls) == calls  # type: ignore[arg-type]


def test_a243_a5_a_mailbox_fault_stops_the_digests_and_switches_email_off(
    fake: Callable[..., FakeGraph], digests: None
) -> None:
    g = fake(httpx.Response(403), ok())
    conn = FakeConn(digest_people=_people(2))
    assert send.send_digests(conn) == 0  # type: ignore[arg-type]
    assert len(g.to(GRAPH)) == 1
    flips = [p for s, p in conn.committed if s.startswith("UPDATE kill_switches SET state")]
    assert flips == [
        (
            "off",
            "Email through Graph stopped: graph_4xx (HTTP 403) (automatic)",
            "process:watch",
            "comms.email",
        )
    ]
    assert not any(s.startswith("UPDATE notifications SET state = 'sent'") for s, _ in conn.committed)


def test_a243_nothing_logged_carries_the_address_the_subject_the_token_or_the_secret(
    fake: Callable[..., FakeGraph], loop: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fake(httpx.Response(401), ok(), httpx.Response(400), httpx.Response(503, text=f"{TO} {SUBJECT}"))
    conn = FakeConn([_row(1), _row(2), _row(3)])
    assert send.send_due(conn) == 1  # type: ignore[arg-type]
    lines = [klog._JsonFormatter().format(r) for r in caplog.records]
    assert any('"event":"comms.graph_token_dropped"' in line for line in lines)
    failed = [line for line in lines if '"event":"comms.send_failed"' in line]
    assert '"notification_id":2' in failed[0] and '"error_code":"graph_4xx"' in failed[0]
    assert '"http_status":400' in failed[0] and '"attempt":1' in failed[0] and '"try_spent":true' in failed[0]
    assert '"notification_id":3' in failed[1] and '"http_status":503' in failed[1]
    for line in lines:
        for secret in (TO, "syn.1@", "syn.2@", "syn.3@", SUBJECT, "tok-", SECRET, MAILBOX, "Kavya"):
            assert secret not in line, line


# ---- EMAIL_MODE=smtp: today's path, unchanged ----------------------------------------------------------------------


def test_a243_smtp_mode_calls_the_smtp_path_and_never_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, EMAIL_MODE="smtp", EMAIL_FROM=SENDER)
    seen: list[tuple[str, Any]] = []
    monkeypatch.setattr(send, "_smtp", lambda to, mail: seen.append((to, mail)))
    monkeypatch.setattr(graph, "send", lambda msg: pytest.fail("graph in smtp mode"))
    send.deliver(TO, MAIL)
    assert seen == [(TO, MAIL)]
    get_settings.cache_clear()


def test_a243_the_smtp_path_itself_is_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, EMAIL_MODE="smtp", SMTP_URL="smtp://mailpit:1025", EMAIL_FROM=SENDER)
    opened: list[tuple[str, int, float]] = []
    sent: list[Any] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            opened.append((host, port, timeout))

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def send_message(self, msg: Any) -> None:
            sent.append(msg)

    monkeypatch.setattr(send.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(
        graph, "transport", httpx.MockTransport(lambda r: pytest.fail("network in smtp mode"))
    )
    send.deliver(TO, MAIL)
    assert opened == [("mailpit", 1025, 10)]
    assert (sent[0]["From"], sent[0]["To"], sent[0]["Subject"]) == (SENDER, TO, SUBJECT)
    assert [p.get_content_type() for p in sent[0].iter_parts()] == ["text/plain", "text/html"]
    get_settings.cache_clear()


def test_a243_a_failed_smtp_send_is_recorded_as_before(monkeypatch: pytest.MonkeyPatch, loop: None) -> None:
    _settings(monkeypatch, EMAIL_MODE="smtp")

    def refuse(to: str, mail: Any) -> None:
        raise OSError("mailbox unavailable")

    monkeypatch.setattr(send, "_smtp", refuse)
    conn = FakeConn([_row(1)])
    send.send_due(conn)  # type: ignore[arg-type]
    assert conn.updates()[0][1] == ("queued", "oserror", FIVE, 1)
    get_settings.cache_clear()


def test_a243_an_unknown_email_mode_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, EMAIL_MODE="relay")
    monkeypatch.setattr(send, "_smtp", lambda to, mail: pytest.fail("smtp"))
    monkeypatch.setattr(graph, "send", lambda msg: pytest.fail("graph"))
    with pytest.raises(ValueError, match="EMAIL_MODE must be smtp or graph"):
        send.deliver(TO, MAIL)
    get_settings.cache_clear()


def test_a243_dev_defaults_keep_smtp_and_todays_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("EMAIL_MODE", "EMAIL_FROM", "GRAPH_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (s.email_mode, s.email_from) == ("smtp", "1% Club <onepercentclub@kfintech.example>")
    assert s.graph_client_secret == ""


def test_a243_every_sender_uses_the_one_transport() -> None:
    """send_due, send_digests and the sign-in code all call `deliver`; only `deliver` reaches SMTP or Graph, and only
    comms/graph.py names Graph's hosts."""
    worker = ROOT / "services" / "worker"
    sources = {
        p.relative_to(worker).as_posix(): p.read_text("utf-8")
        for p in worker.rglob("*.py")
        if ".venv" not in p.parts and "tests" not in p.parts
    }
    assert [n for n, t in sources.items() if re.search(r"^\s*(import smtplib|from smtplib)", t, re.M)] == [
        "comms/send.py"
    ]
    assert [n for n, t in sources.items() if "_smtp(" in t] == ["comms/send.py"]
    send_src = sources["comms/send.py"]
    assert send_src.count("_smtp(") == 2  # its definition and the one call, in deliver
    # deliver: its definition, send_due's call and _send_digest's call
    assert send_src.count("graph.send(") == 1 and send_src.count("deliver(") == 3
    assert "deliver(" in sources["comms/sign_in_code.py"] and "_smtp" not in sources["comms/sign_in_code.py"]
    assert [n for n, t in sources.items() if GRAPH in t or LOGIN in t] == ["comms/graph.py"]
    assert sorted(n for n, t in sources.items() if re.search(r"graph\.send\(|\bsendMail\b", t)) == [
        "comms/graph.py",
        "comms/send.py",
    ]


# ---- the preflight: every Graph name, and EMAIL_FROM is the service mailbox ----------------------------------------


@pytest.mark.parametrize("name", preflight.GRAPH_NAMES)
def test_a243_preflight_needs_every_graph_setting(name: str) -> None:
    problems, _ = preflight.check(GOOD | {name: ""})
    assert f"EMAIL_MODE=graph needs {name}" in problems


@pytest.mark.parametrize(
    ("sender", "ok_"),
    [
        ("1% Club <garage@kfintech.example>", True),
        ("1% Club <Garage@KFintech.example>", True),  # case does not matter
        ("garage@kfintech.example", True),
        ("1% Club <onepercentclub@kfintech.example>", False),  # today's dev sender is not the mailbox
        ("1% Club <garage@kfintech.example.evil>", False),
    ],
)
def test_a243_preflight_email_from_must_be_the_service_mailbox(sender: str, ok_: bool) -> None:
    problems, _ = preflight.check(GOOD | {"EMAIL_FROM": sender})
    mismatch = (
        "EMAIL_FROM must be the service mailbox's address (GRAPH_SERVICE_MAILBOX) with EMAIL_MODE=graph"
    )
    assert (mismatch not in problems) is ok_, problems


def test_a243_preflight_other_email_modes() -> None:
    problems, warnings = preflight.check(GOOD | {"EMAIL_MODE": "relay"})
    assert "EMAIL_MODE must be smtp or graph" in problems
    problems, warnings = preflight.check(
        GOOD | {"EMAIL_MODE": "smtp", "GRAPH_CLIENT_SECRET": "", "EMAIL_FROM": ""}
    )
    assert problems == [] and any(w.startswith("EMAIL_MODE=smtp") for w in warnings)
    problems, _ = preflight.check(GOOD | {"GRAPH_SERVICE_MAILBOX": "garage"})
    assert "GRAPH_SERVICE_MAILBOX must be the service mailbox's email address" in problems


def test_a243_preflight_never_prints_a_graph_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for k, v in (
        GOOD | {"GRAPH_CLIENT_SECRET": SECRET, "EMAIL_FROM": "1% Club <other@kfintech.example>"}
    ).items():
        monkeypatch.setenv(k, v)
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "EMAIL_FROM must be the service mailbox's address" in out
    for value in (SECRET, "other@kfintech.example", "garage@kfintech.example"):
        assert value not in out


# ---- the secret is the worker's alone ------------------------------------------------------------------------------


def test_a243_compose_gives_the_secret_to_the_worker_and_blanks_it_for_the_web_app() -> None:
    for name in ("docker-compose.yml", "uat/compose.uat.yml"):
        services = _compose(name)["services"]
        assert services["web"]["environment"]["GRAPH_CLIENT_SECRET"] == "", name
        assert services["worker"]["environment"]["GRAPH_CLIENT_SECRET"] == "${GRAPH_CLIENT_SECRET:-}", name
        assert "GRAPH_CLIENT_SECRET" not in (services.get("speech", {}).get("environment") or {}), name
    example = (ROOT / ".env.example").read_text("utf-8").splitlines()
    assert not any(line.startswith("GRAPH_CLIENT_SECRET=") for line in example)
    assert (
        "EMAIL_FROM=1% Club <onepercentclub@kfintech.example>" in example
        and "EMAIL_MODE=smtp" in " ".join(example)
    )


# ---- the check IT runs before `comms.email` goes on ---------------------------------------------------------------


def test_a243_email_check_sends_one_test_message_and_audits_the_result(
    fake: Callable[..., FakeGraph],
) -> None:
    g = fake(ok())
    conn = FakeConn()
    rc, line = email_check.check(conn, "it.mailcheck@kfintech.example", "ops:SYN-0001")  # type: ignore[arg-type]
    assert (rc, line) == (0, "email check: sent (Graph accepted it, HTTP 202)")
    [req] = g.to(GRAPH)
    msg = email.message_from_bytes(base64.b64decode(req.content), policy=policy.default)
    assert (msg["To"], msg["From"], msg["Subject"]) == (
        "it.mailcheck@kfintech.example",
        SENDER,
        email_check.SUBJECT,
    )
    [(_sql, params)] = [(s, p) for s, p in conn.calls if s.startswith("INSERT INTO audit_log")]
    assert params[0] == "ops:SYN-0001" and params[1].obj == {"result": "sent", "http_status": 202}


def test_a243_email_check_reports_graphs_refusal_without_the_address(fake: Callable[..., FakeGraph]) -> None:
    fake(httpx.Response(403, text="ErrorAccessDenied"))
    conn = FakeConn()
    rc, line = email_check.check(conn, "it.mailcheck@kfintech.example", "ops:SYN-0001")  # type: ignore[arg-type]
    assert (rc, line) == (1, "email check: failed graph_4xx (HTTP 403)")
    assert [p[1].obj for s, p in conn.calls if s.startswith("INSERT INTO audit_log")] == [
        {"result": "graph_4xx", "http_status": 403}
    ]


@pytest.mark.parametrize(
    ("to", "users", "expected"),
    [
        ("kavya.syn@kfintech.example", [{"?column?": 1}], "that address belongs to someone in 1% Club"),
        ("two@kfintech.example, three@kfintech.example", [], "--to must be one email address"),
        ("not-an-address", [], "--to must be one email address"),
    ],
)
def test_a243_email_check_never_mails_a_person_in_1pc_club(
    fake: Callable[..., FakeGraph], to: str, users: list[dict[str, Any]], expected: str
) -> None:
    g = fake(ok())
    conn = FakeConn(users=users)
    rc, line = email_check.check(conn, to, "ops:SYN-0001")  # type: ignore[arg-type]
    assert rc == 2 and expected in line and g.requests == [] and to not in line
    assert not any(s.startswith("INSERT INTO audit_log") for s, _ in conn.calls)


def test_a243_email_check_runs_only_with_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, EMAIL_MODE="smtp")
    monkeypatch.setattr(send, "_smtp", lambda to, mail: pytest.fail("smtp"))
    rc, line = email_check.check(FakeConn(), "it.mailcheck@kfintech.example", "ops:SYN-0001")  # type: ignore[arg-type]
    assert (rc, line) == (2, "email check: refused: EMAIL_MODE is not graph")
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("answer", "users", "rc", "last"),
    [
        (httpx.Response(202), [], 0, "email check: sent (Graph accepted it, HTTP 202)"),
        (httpx.Response(403), [], 1, "email check: failed graph_4xx (HTTP 403)"),
        (httpx.Response(202), [{"?column?": 1}], 2, "email check: refused: that address belongs to someone in "
         "1% Club; use IT's own test mailbox"),
    ],
)  # fmt: skip
def test_a243_b3_main_prints_the_result_as_its_last_line_and_exits_with_its_code(
    fake: Callable[..., FakeGraph],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    answer: httpx.Response,
    users: list[dict[str, Any]],
    rc: int,
    last: str,
) -> None:
    import contextlib

    fake(answer)
    conn = FakeConn(users=users)
    monkeypatch.setattr(email_check, "connect", lambda autocommit=False: contextlib.nullcontext(conn))
    assert email_check.main(["--to", "it.mailcheck@kfintech.example", "--actor", "ops:SYN-0001"]) == rc
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == last
    # Any other line on the terminal is the worker's JSON log, IDs and codes only, never the address.
    assert all(line.startswith("{") for line in out.splitlines()[:-1]) and "it.mailcheck@" not in out


def _graph_section() -> str:
    doc = (ROOT / "docs" / "UAT.md").read_text("utf-8")
    return doc.split("\n## Email through Graph (BLD-A243)\n", 1)[1].split("\n## ", 1)[0]


def test_a243_runbook_switches_comms_email_off_before_the_worker_restarts_in_graph_mode() -> None:
    """An install leaves `comms.email` on (the platform migration's default), so the section never assumes it is off:
    step 1 reads the switch list and has it switched off before step 2 restarts the worker with EMAIL_MODE=graph,
    and step 4 switches it on only after the test message has passed."""
    section = _graph_section()
    step1, rest = section.split("\n2. **Run the preflight, then restart the worker**", 1)
    assert "An install leaves `comms.email` on" in step1
    assert step1.index("python -m core.killswitch list") < step1.index("EMAIL_MODE=graph")
    assert "an admin switches it off now from the Admin page, with a reason" in step1
    assert "Pass: `comms.email off` on the last read" in step1
    step3, _step4 = rest.split("\n4. **Only on the product lead's word: switch `comms.email` on.**", 1)
    assert "Do not go on to step 4 until the check passes." in step3
    assert (
        "**Pass for steps 1 to 3 (email ready, `comms.email` off):** `comms.email off` before the worker restarts"
        in step3
    )


def test_a243_runbook_pastes_back_no_secret_no_address_and_no_staff_code() -> None:
    section = _graph_section()
    assert "SELECT id, at, after FROM audit_log WHERE action = 'comms.email_check'" in section
    assert "actor, after" not in section
    # Setting names only: nothing after the `=` of a Graph or email setting, and no address shape.
    assert not re.search(r"^\s*(GRAPH_[A-Z_]+|EMAIL_FROM|EMAIL_MODE)=(?!graph$)\S", section, re.M)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", section)


def _full_mode_section() -> str:
    doc = (ROOT / "docs" / "UAT.md").read_text("utf-8")
    return doc.split("\n## Switching to full mode (mode A)\n", 1)[1].split("\n## ", 1)[0]


def test_a243_c6_email_goes_on_only_on_the_product_leads_word() -> None:
    """C6: whether `comms.email` goes on is the lead's call at the Full go/no-go. Steps 1 to 3 pass on their own with
    email off; step 4 and its pass line are only for the lead's go; nothing reads as if email will be on."""
    section = _graph_section()
    intro = section.split("\n1. **Switch `comms.email` off", 1)[0]
    assert (
        "Steps 1 to 3 get email ready and prove the mailbox with `comms.email` off; they pass on their own."
        in intro
    )
    assert "Step 4 runs only when the product lead says so" in intro
    assert "Until then email stays off and queued" in intro
    step4 = section.split("\n4. **Only on the product lead's word: switch `comms.email` on.**", 1)[1]
    assert step4.lstrip().startswith("Skip this step unless the product lead has said email goes on.")
    assert "**Pass for step 4 (only if the product lead switched email on):**" in step4
    assert "**Pass for this section:**" not in section  # two pass lines now, never one that needs email on
    full = _full_mode_section()
    assert "9. **Get email ready.**" in full and "Turn on email" not in full
    assert "its step 4 switches it on only if the product lead says so" in full
    assert "Full mode turns on the assistant and similar ideas, and gets email through Graph ready" in full
    assert "whether email goes on is the product lead's call at the go/no-go" in full


def test_a243_c1_email_mode_stays_smtp_until_the_graph_section_step_1() -> None:
    doc = (ROOT / "docs" / "UAT.md").read_text("utf-8")
    row = next(line for line in doc.splitlines() if line.startswith("| Email through Graph (BLD-A243"))
    assert (
        "The values go in only at step 1 of **Email through Graph (BLD-A243)**: until then `EMAIL_MODE` stays `smtp`"
        in row
    )
    full = _full_mode_section()
    step1 = full.split("\n1. **Check the build.**", 1)[1].split("\n2. **", 1)[0]
    step5 = full.split("\n5. **Set the route and restart the worker and the web app.**", 1)[1].split(
        "\n6. **", 1
    )[0]
    assert "`EMAIL_MODE` stays `smtp` through that upgrade and every step before 9" in step1
    assert "`EMAIL_MODE` stays `smtp` at this restart" in step5
    graph_step1 = _graph_section().split("\n2. **Run the preflight", 1)[0]
    off = graph_step1.index("an admin switches it off now from the Admin page")
    assert off < graph_step1.index("Only now do the Graph values go in")
    assert graph_step1.index("Only now do the Graph values go in") < graph_step1.index("EMAIL_MODE=graph")


def test_a243_c2_the_step_3_list_has_a_catch_all_and_the_tls_proxy() -> None:
    step3 = _graph_section().split("\n3. **Send one test message.**", 1)[1].split("\n4. **", 1)[0]
    assert (
        "- any other line (for example `graph_not_configured`, `graph_4xx (HTTP 400)` or `(HTTP 401)`, or the preflight's mailbox line): send it to lane A."
        in step3
    )
    assert "a TLS-inspecting proxy presents a certificate the worker does not trust" in step3
    # B1 and B2: what IT sees, and what the guard can and cannot tell.
    assert "The first command's last line is the result, `email check: …`." in step3
    assert "never the address or the token" in step3
    assert "not an alias, a distribution list or anyone's address" in step3
    assert "it can never reach an employee" not in step3


def test_a243_c3_c4_stopping_email_the_automatic_switch_off_and_a_rollback() -> None:
    section = _graph_section()
    stop = section.split("**To stop email at any time:**", 1)[1].split("\n\n", 1)[0]
    assert "an email already being sent finishes first, and that one email goes" in stop
    auto = section.split("**If email switches itself off:**", 1)[1].split(
        "**To stop email at any time:**", 1
    )[0]
    assert "switches `comms.email` off by itself, audited, with the code in the reason" in auto
    assert "No email spends a try; they all stay queued." in auto
    assert (
        "SELECT at, reason FROM audit_log WHERE action = 'kill_switch.set' AND entity = 'kill_switch:comms.email'"
        in auto
    )
    assert "runs the step 3 check until it passes; then an admin switches `comms.email` back on" in auto
    assert "Nothing switches it back on by itself." in auto
    rollback = section.split("**Before a rollback:**", 1)[1]
    assert "a rollback to a build without BLD-A243 would send by SMTP to nothing" in rollback
    assert "before such a rollback an admin switches `comms.email` off, with a reason" in rollback
    doc = (ROOT / "docs" / "UAT.md").read_text("utf-8")
    assert (
        "With `EMAIL_MODE=graph` in the app env file, read **Before a rollback** under **Email through Graph (BLD-A243)** first:"
        in doc
    )
