"""Internal routes for L-HIDE (lane C). Included by `api/app.py` behind the internal token. The web app has checked
the person's role or ownership; the worker checks again who owns a detail. Errors are `{error: code}`; IDs only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.db import connect
from hide import core, desk

router = APIRouter()
NO_STORE = {"Cache-Control": "no-store"}


def _call(fn: Any, *args: Any, **kwargs: Any) -> JSONResponse:
    try:
        with connect(autocommit=True) as conn:
            body = fn(conn, *args, **kwargs)
    except core.HideError as exc:
        return JSONResponse({"error": exc.code}, status_code=exc.status)
    return JSONResponse(body, headers=NO_STORE)


@router.post("/internal/hide/desk/{idea_uuid}")
def desk_hide(idea_uuid: str, body: dict[str, Any]) -> JSONResponse:
    """S-R2 "Hide this" (L-HIDE.rules/7). Body: {source: {kind, id}, start, end, by (users.id)}."""
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
    )


@router.post("/internal/hide/{idea_uuid}/details/{hid}/show")
def show(idea_uuid: str, hid: str, body: dict[str, Any]) -> JSONResponse:
    """C-HIDDEN "Show it" with a reason (L-HIDE.rules/6). Body: {reason, by}."""
    return _call(desk.show, idea_uuid, hid, reason=body.get("reason"), by=str(body.get("by") or ""))


@router.post("/internal/hide/{idea_uuid}/details/{hid}/hide")
def hide_again(idea_uuid: str, hid: str, body: dict[str, Any]) -> JSONResponse:
    """C-HIDDEN "Hide it". Body: {by}."""
    return _call(desk.hide_again, idea_uuid, hid, by=str(body.get("by") or ""))
