"""Structured JSON logging that carries IDs only (non-negotiable 3).

Usage:  log = get_logger(__name__);  log.info("repo_writer.committed", outbox_id=12, commit_sha="ab12…")

There is no free-text message: the first argument is an event name (`a.b_c`). Field names that look like
text or personal data, and string values that match a personal-data pattern, are refused. In dev and test
that raises `LogPolicyError` so the mistake is found at once; in UAT and prod the field is dropped and the
line records which field names were dropped (names only).

A value that is exactly one of our identifier shapes (a UUID, `DRAFT-<uuid>`, `IDEA-<uuid>`, `user:<uuid>`, a
hash or a coded ID such as `IDEA-2026-000142`) is kept without the value scan: `value_patterns` checks the shared
`log_rules.safe_value_regex` first (BLD-087, BLD-A183, BLD-A189). Anything else, an ID with text beside it
included, is scanned.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from datetime import UTC, datetime
from typing import Any

from pii.log_rules import event_name_ok, field_is_forbidden, value_patterns

_SAFE_SCALARS = (int, float, bool, type(None))
_EXTERNAL = re.compile(r"[^a-z0-9_.]")


class LogPolicyError(ValueError):
    """A log call tried to write free text or personal data."""


def _strict() -> bool:
    return os.environ.get("APP_ENV", "dev") not in {"uat", "prod"}


def _clean(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    out: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in fields.items():
        if field_is_forbidden(key):
            dropped.append(key)
            continue
        if isinstance(value, _SAFE_SCALARS):
            out[key] = value
        elif isinstance(value, str):
            if value_patterns(value):
                dropped.append(key)
            else:
                out[key] = value
        elif isinstance(value, list | tuple) and all(isinstance(v, str | int) for v in value):
            if any(isinstance(v, str) and value_patterns(v) for v in value):
                dropped.append(key)
            else:
                out[key] = list(value)
        else:
            dropped.append(key)  # nested structures could hide text; log their IDs instead
    return out, dropped


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ours = hasattr(record, "fields")
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            # Libraries write free text (and sometimes request data). Keep that they logged, not what.
            "event": record.getMessage() if ours else "external." + _EXTERNAL.sub("_", record.name.lower()),
        }
        line.update(getattr(record, "fields", {}))
        if record.exc_info and record.exc_info[0] is not None:
            # Exception type only: messages and tracebacks can carry idea text.
            line["error_type"] = record.exc_info[0].__name__
        return json.dumps(line, ensure_ascii=False, separators=(",", ":"))


class Log:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _emit(self, level: int, event: str, fields: dict[str, Any], exc: bool = False) -> None:
        if not event_name_ok(event):
            if _strict():
                raise LogPolicyError("log event must be a dotted snake_case name")
            fields = {"original_event_dropped": True}
            event = "log.event_dropped"
        clean, dropped = _clean(fields)
        if dropped:
            if _strict():
                raise LogPolicyError(f"log fields refused: {sorted(dropped)}")
            clean["dropped_fields"] = sorted(dropped)
        self._logger.log(level, event, extra={"fields": clean}, exc_info=exc)

    def debug(self, event: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, fields)

    def exception(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, fields, exc=True)


_configured = False


def configure(level: str = "INFO", stream: Any = None) -> None:
    global _configured
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_kfin", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler._kfin = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Third-party loggers can echo request bodies; keep them quiet.
    for noisy in ("uvicorn.access", "botocore", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _install_excepthooks()
    _configured = True


def _install_excepthooks() -> None:
    """Uncaught exceptions would print their message and traceback to stderr, and a database error message
    can quote a failing row (idea text). Log the exception type only."""

    def report(exc_type: type[BaseException], where: str) -> None:
        logging.getLogger("uncaught").error(
            "process.uncaught_exception", extra={"fields": {"error_type": exc_type.__name__, "where": where}}
        )

    def sys_hook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        report(exc_type, "main")

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        report(args.exc_type, "thread")

    sys.excepthook = sys_hook
    threading.excepthook = thread_hook


def get_logger(name: str) -> Log:
    if not _configured:
        configure(os.environ.get("LOG_LEVEL", "INFO"))
    return Log(name)
