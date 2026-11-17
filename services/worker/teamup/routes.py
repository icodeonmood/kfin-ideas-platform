"""Lane F's `/internal/*` routes for team-up, draft merge requests and crews (A-API.team-up, A-API.drafts
merge-request), on their own router so `api/app.py` takes one include line.

The web app has already checked the session and passes the signed-in person as `user_id`; the services check what
that person may do here (their own request, the idea's lead). Errors follow A-API.conventions/2:
`{error: {code, message, field?}}`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.db import connect
from teamup.store import Refused


def _call(fn: Callable[..., Any], *args: Any, status: int = 200, **kwargs: Any) -> JSONResponse:
    with connect(autocommit=True) as conn:
        try:
            body = fn(conn, *args, **kwargs)
        except Refused as exc:
            return JSONResponse(exc.body(), status_code=exc.status)
    return JSONResponse(jsonable_encoder(body), status_code=status, headers={"Cache-Control": "no-store"})


def build(require_token: Callable[..., None]) -> APIRouter:
    """The router, guarded by the app's internal-token check."""
    r = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])

    # --- asking to team up on a shared idea (C-SHEET-TEAMUP) ---------------------------------------------
    @r.get("/ideas/{ref}/team-up/draft-note")
    def teamup_draft_note(ref: str, user_id: str) -> JSONResponse:
        from teamup import requests

        return _call(requests.draft_note, ref, user_id)

    @r.get("/ideas/{ref}/team-up")
    def teamup_mine(ref: str, user_id: str) -> JSONResponse:
        from teamup import requests

        return _call(requests.my_state, ref, user_id)

    @r.post("/ideas/{ref}/team-up")
    def teamup_send(
        ref: str, user_id: str, body: dict[str, Any], idempotency_key: str | None = Header(default=None)
    ) -> JSONResponse:
        from teamup import requests

        return _call(requests.send, ref, user_id, body, idempotency_key, status=201)

    # --- one request, either kind (BLD-F010) ---------------------------------------------------------------
    @r.get("/team-up/{request_id}")
    def teamup_read(request_id: str, user_id: str) -> JSONResponse:
        from teamup import requests

        return _call(requests.read, request_id, user_id)

    @r.delete("/team-up/{request_id}")
    def teamup_withdraw(request_id: str, user_id: str) -> JSONResponse:
        from teamup import requests

        return _call(requests.withdraw, request_id, user_id)

    @r.post("/team-up/{request_id}/answer")
    def teamup_answer(request_id: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from teamup import requests

        return _call(requests.answer, request_id, user_id, body)

    # --- a draft's merge request (L-MERGE.request) -----------------------------------------------------------
    @r.get("/drafts/{draft_id}/merge-request")
    def merge_request_state(draft_id: str, user_id: str) -> JSONResponse:
        from teamup import drafts

        return _call(drafts.state, draft_id, user_id)

    @r.post("/drafts/{draft_id}/merge-request")
    def merge_request_ask(
        draft_id: str, user_id: str, body: dict[str, Any], idempotency_key: str | None = Header(default=None)
    ) -> JSONResponse:
        from teamup import drafts

        return _call(drafts.ask, draft_id, user_id, body, idempotency_key, status=201)

    @r.delete("/drafts/{draft_id}/merge-request")
    def merge_request_withdraw(draft_id: str, user_id: str) -> JSONResponse:
        from teamup import drafts

        return _call(drafts.withdraw, draft_id, user_id)

    # --- leaving and removal (L-TEAMUP.rules/11) -------------------------------------------------------------
    @r.post("/ideas/{ref}/crew/leave")
    def crew_leave(ref: str, user_id: str) -> JSONResponse:
        from teamup import crew

        return _call(crew.leave, ref, user_id)

    @r.delete("/ideas/{ref}/crew/{member}")
    def crew_remove(ref: str, member: str, user_id: str) -> JSONResponse:
        from teamup import crew

        return _call(crew.remove, ref, member, user_id)

    return r
