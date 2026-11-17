"""The conversation's `/internal/*` routes (A-API.inbox: the idea's conversation), on their own router so
`api/app.py` takes one include line.

The web app has checked the session and passes the signed-in person as `user_id`; this side decides what that
person may read or write on this idea (L-CONVO/2) and answers anyone else 404. Errors follow A-API.conventions/2:
`{error: {code, message, field?}}`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, Header
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from convo.store import Refused
from core.db import connect


def _call(fn: Callable[..., Any], *args: Any, status: int = 200, **kwargs: Any) -> JSONResponse:
    with connect(autocommit=True) as conn:
        try:
            body = fn(conn, *args, **kwargs)
        except Refused as exc:
            return JSONResponse(exc.body(), status_code=exc.status, headers={"Cache-Control": "no-store"})
    return JSONResponse(jsonable_encoder(body), status_code=status, headers={"Cache-Control": "no-store"})


def build(require_token: Callable[..., None]) -> APIRouter:
    """The router, guarded by the app's internal-token check."""
    r = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])

    @r.get("/ideas/{ref}/conversation")
    def conversation(ref: str, user_id: str) -> JSONResponse:
        from convo import reads

        return _call(reads.conversation, ref, user_id)

    @r.post("/ideas/{ref}/conversation/messages")
    def send(
        ref: str,
        user_id: str,
        body: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 (FastAPI's way)
        idempotency_key: str | None = Header(default=None),
    ) -> JSONResponse:
        from convo import messages

        return _call(messages.send, ref, user_id, body, idempotency_key=idempotency_key, status=201)

    @r.delete("/ideas/{ref}/conversation/messages/{entry_id}")
    def remove(ref: str, entry_id: str, user_id: str) -> JSONResponse:
        from convo import messages

        return _call(messages.remove, ref, user_id, entry_id)

    return r
