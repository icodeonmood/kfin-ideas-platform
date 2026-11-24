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

    def __init__(self, *sends: httpx.Response | Exception, token: httpx.Response | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.sends = list(sends)
        self.token_answer = token
        self.tokens = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == LOGIN:
            if self.token_answer is not None:
                return self.token_answer
            self.tokens += 1
            return httpx.Response(200, json={"access_token": f"tok-{self.tokens}", "expires_in": 3599})
        assert request.url.host == GRAPH  # never any other host
        answer = self.sends.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def to(self, host: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, graph_mode: None) -> Callable[..., FakeGraph]:
    def install(*sends: httpx.Response | Exception, token: httpx.Response | None = None) -> FakeGraph:
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


def test_a243_a_second_401_is_final_and_never_a_third_try(fake: Callable[..., FakeGraph]) -> None:
    g = fake(httpx.Response(401), httpx.Response(401), ok())
    with pytest.raises(graph.EmailRefused) as refused:
        send.deliver(TO, MAIL)
    assert (refused.value.code, refused.value.status) == ("graph_4xx", 401)
    assert len(g.to(GRAPH)) == 2 and len(g.to(LOGIN)) == 2


@pytest.mark.parametrize(
    ("status", "error", "code"),
    [(400, graph.EmailRefused, "graph_token_4xx"), (401, graph.EmailRefused, "graph_token_4xx"),
     (503, graph.EmailRetry, "graph_token_5xx"), (429, graph.EmailRetry, "graph_token_429")],
)  # fmt: skip
def test_a243_a_refused_token_follows_the_same_rules_and_nothing_is_sent(
    fake: Callable[..., FakeGraph], status: int, error: type[Exception], code: str
) -> None:
    g = fake(
        ok(), token=httpx.Response(status, json={"error": "invalid_client", "error_description": SECRET})
    )
    with pytest.raises(error) as raised:
        send.deliver(TO, MAIL)
    assert getattr(raised.value, "code", None) == code and g.to(GRAPH) == []
    assert str(raised.value) == code  # never Graph's answer


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


# ---- Graph's answers: 202 sent; 429, 5xx and timeouts retried; any other 4xx final --------------------------------


@pytest.mark.parametrize(
    ("answer", "error", "code", "status", "retry_after"),
    [
        (httpx.Response(429, headers={"Retry-After": "120"}), graph.EmailRetry, "graph_429", 429, 120),
        (httpx.Response(429, headers={"Retry-After": "86400"}), graph.EmailRetry, "graph_429", 429, 900),
        (httpx.Response(429), graph.EmailRetry, "graph_429", 429, None),
        (httpx.Response(503, text=f"busy for {TO}"), graph.EmailRetry, "graph_5xx", 503, None),
        (httpx.Response(500), graph.EmailRetry, "graph_5xx", 500, None),
        (httpx.Response(400, text=f"bad message {SUBJECT}"), graph.EmailRefused, "graph_4xx", 400, None),
        (httpx.Response(403), graph.EmailRefused, "graph_4xx", 403, None),
        (httpx.Response(404), graph.EmailRefused, "graph_4xx", 404, None),
    ],
)
def test_a243_graphs_answer_decides_retry_or_final(
    fake: Callable[..., FakeGraph],
    answer: httpx.Response,
    error: type[Exception],
    code: str,
    status: int,
    retry_after: int | None,
) -> None:
    fake(answer)
    with pytest.raises(error) as raised:
        send.deliver(TO, MAIL)
    exc: Any = raised.value
    assert (exc.code, exc.status, getattr(exc, "retry_after_s", None)) == (code, status, retry_after)
    assert str(exc) == code and TO not in str(exc) and SUBJECT not in str(exc)


def test_a243_202_is_sent(fake: Callable[..., FakeGraph]) -> None:
    g = fake(ok())
    send.deliver(TO, MAIL)  # returns: Graph accepted it
    assert [r.url.path for r in g.to(GRAPH)] == [f"/v1.0/users/{MAILBOX}/sendMail"]


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
    assert retry.value.__suppress_context__ and retry.value.__cause__ is None  # httpx's error names the URL


def test_a243_retry_after_as_an_http_date() -> None:
    later = (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=10)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    seconds = graph._retry_after(httpx.Response(429, headers={"Retry-After": later}))
    assert seconds is not None and 590 <= seconds <= 600
    assert graph._retry_after(httpx.Response(429, headers={"Retry-After": "soon"})) is None


def test_a243_without_its_settings_graph_sends_nothing(
    fake: Callable[..., FakeGraph], monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, GRAPH_CLIENT_SECRET="")
    g = fake(ok())
    with pytest.raises(graph.EmailRetry) as retry:
        send.deliver(TO, MAIL)
    assert retry.value.code == "graph_not_configured" and g.requests == []


# ---- the send loop: how each answer lands on the notification ------------------------------------------------------


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None


class FakeConn:
    """Records every statement; the due-email select returns the given rows, the users lookup `users`."""

    def __init__(
        self, rows: list[dict[str, Any]] | None = None, users: list[dict[str, Any]] | None = None
    ) -> None:
        self.rows = rows or []
        self.users = users or []
        self.calls: list[tuple[str, Any]] = []

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    def execute(self, sql: str, params: Any = None) -> _Cursor:
        flat = " ".join(sql.split())
        self.calls.append((flat, params))
        if flat.startswith("SELECT n.id"):
            return _Cursor(self.rows)
        if flat.startswith("SELECT 1 FROM users"):
            return _Cursor(self.users)
        return _Cursor([])

    def updates(self) -> list[tuple[str, Any]]:
        return [(sql, p) for sql, p in self.calls if sql.startswith("UPDATE notifications SET attempts")]


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


@pytest.mark.parametrize(
    ("answer", "attempts", "state", "code", "wait"),
    [
        (httpx.Response(503), 0, "queued", "graph_5xx", FIVE),
        (
            httpx.Response(503, headers={"Retry-After": "600"}),
            0,
            "queued",
            "graph_5xx",
            dt.timedelta(seconds=600),
        ),
        (httpx.Response(429, headers={"Retry-After": "30"}), 0, "queued", "graph_429", FIVE),  # never sooner
        (httpx.Response(503), 2, "failed", "graph_5xx", FIVE),  # the third try was the last
        (httpx.Response(400), 0, "failed", "graph_4xx", FIVE),  # final at once
        (httpx.ReadTimeout("timed out"), 0, "queued", "graph_timeout", FIVE),
    ],
)
def test_a243_l_notify_the_loop_records_graphs_answer(
    fake: Callable[..., FakeGraph], loop: None, answer: Any, attempts: int, state: str, code: str, wait: Any
) -> None:
    fake(answer)
    conn = FakeConn([_row(1, attempts)])
    assert send.send_due(conn) == 0  # type: ignore[arg-type]
    [(_sql, params)] = conn.updates()
    assert params == (state, code, wait, 1)
    assert not any("state = 'sent'" in s for s, _ in conn.calls)


def test_a243_l_notify_a_202_marks_it_sent(fake: Callable[..., FakeGraph], loop: None) -> None:
    fake(ok())
    conn = FakeConn([_row(1)])
    assert send.send_due(conn) == 1  # type: ignore[arg-type]
    assert any(s.startswith("UPDATE notifications SET state = 'sent'") and p[1] == 1 for s, p in conn.calls)


def test_a243_l_notify_after_a_429_the_rest_of_the_batch_waits_untried(
    fake: Callable[..., FakeGraph], loop: None
) -> None:
    g = fake(httpx.Response(429, headers={"Retry-After": "600"}), ok(), ok())
    conn = FakeConn([_row(1), _row(2), _row(3)])
    assert send.send_due(conn) == 0  # type: ignore[arg-type]
    assert len(g.to(GRAPH)) == 1
    assert [p for _, p in conn.updates()] == [("queued", "graph_429", dt.timedelta(seconds=600), 1)]
    held = [
        p for s, p in conn.calls if s == "UPDATE notifications SET send_after = now() + %s WHERE id = ANY(%s)"
    ]
    assert held == [(dt.timedelta(seconds=600), [2, 3])]  # no try spent on them


def test_a243_nothing_logged_carries_the_address_the_subject_the_token_or_the_secret(
    fake: Callable[..., FakeGraph], loop: None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    fake(httpx.Response(401), httpx.Response(503, text=f"{TO} {SUBJECT}"), ok(), httpx.Response(400))
    conn = FakeConn([_row(1), _row(2), _row(3)])
    send.send_due(conn)  # type: ignore[arg-type]
    lines = [klog._JsonFormatter().format(r) for r in caplog.records]
    assert any('"event":"comms.send_failed"' in line for line in lines)
    failed = [line for line in lines if '"event":"comms.send_failed"' in line]
    assert (
        '"notification_id":1' in failed[0] and '"http_status":503' in failed[0] and '"attempt":1' in failed[0]
    )
    assert '"error_code":"graph_4xx"' in failed[1] and '"http_status":400' in failed[1]
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
    step3, step4 = rest.split("\n4. **Switch `comms.email` on.**", 1)
    assert "Do not go on to step 4 until the check passes." in step3
    assert "**Pass for this section:** `comms.email off` before the worker restarts" in step4


def test_a243_runbook_pastes_back_no_secret_no_address_and_no_staff_code() -> None:
    section = _graph_section()
    assert "SELECT id, at, after FROM audit_log WHERE action = 'comms.email_check'" in section
    assert "actor, after" not in section
    # Setting names only: nothing after the `=` of a Graph or email setting, and no address shape.
    assert not re.search(r"^\s*(GRAPH_[A-Z_]+|EMAIL_FROM|EMAIL_MODE)=(?!graph$)\S", section, re.M)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", section)
