"""Internal routes for L-HIDE (lane C). Included by `api/app.py` behind the internal token. The web app has checked
the person's role or ownership; the worker checks again who owns a detail. Errors are A-API.conventions/2's shape,
`{error: {code, message}}`, with a fixed code and an empty message (the web app has the words); IDs only.

Each call runs in one transaction, so the idea's lock is held until its writes are done (BLD-C067)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.db import connect
from core.logging import get_logger
from hide import core, desk

router = APIRouter()
log = get_logger("hide")
NO_STORE = {"Cache-Control": "no-store"}


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": ""}}, status_code=status, headers=NO_STORE)


def _call(fn: Any, *args: Any, **kwargs: Any) -> JSONResponse:
    try:
        with connect(autocommit=True) as conn, conn.transaction():
            body = fn(conn, *args, **kwargs)
    except core.HideError as exc:
        return _error(exc.code, exc.status)
    except Exception as exc:  # never the text: a fixed code, and the error's type in the log
        log.error("hide.route_failed", error_type=type(exc).__name__)
        return _error("hide_failed", 500)
    return JSONResponse(body, headers=NO_STORE)


@router.post("/internal/hide/desk/{idea_uuid}")
def desk_hide(idea_uuid: str, body: dict[str, Any]) -> JSONResponse:
    """S-R2 "Hide this" (L-HIDE.rules/7). Body: {source: {kind, id}, start, end, by (users.id), units?}. `units`
    "utf16" when the offsets are the browser's (the web app sends them so); "cp" (code points) otherwise."""
    raw = body.get("source")
    source: dict[str, Any] = raw if isinstance(raw, dict) else {}
    return _call(
        desk.desk_hide,
        idea_uuid,
        source_kind=str(source.get("kind") or ""),
        source_id=str(source.get("id") or ""),
        start=body.get("start"),
        end=body.get("end"),
        by=str(body.get("by") or ""),
        units=str(body.get("units") or "cp"),
    )


@router.post("/internal/hide/{idea_uuid}/details/{hid}/show")
def show(idea_uuid: str, hid: str, body: dict[str, Any]) -> JSONResponse:
    """C-HIDDEN "Show it" with a reason (L-HIDE.rules/6). Body: {reason, by}. `forbidden` when the review desk hid
    it (the desk's hide wins)."""
    return _call(desk.show, idea_uuid, hid, reason=body.get("reason"), by=str(body.get("by") or ""))


@router.post("/internal/hide/{idea_uuid}/details/{hid}/hide")
def hide_again(idea_uuid: str, hid: str, body: dict[str, Any]) -> JSONResponse:
    """C-HIDDEN "Hide it". Body: {by}."""
    return _call(desk.hide_again, idea_uuid, hid, by=str(body.get("by") or ""))
