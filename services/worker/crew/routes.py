"""Lane F's `/internal/*` routes: Find your crew (A-API.team-up `GET /crew`, the passes), on their own router so
`api/app.py` takes one include line.

The web app has already checked that the caller is signed in and passes them as `user_id`; the services decide what
that person may see. Errors follow A-API.conventions/2: `{error: {code, message, field?}}`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.db import connect
from crew.store import Refused


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

    # --- Find your crew (S-H2, and Home's top three, S-03) ------------------------------------------------
    @r.get("/crew")
    def crew_deck(
        user_id: str,
        location: list[str] = Query(default=[]),  # noqa: B008 (FastAPI's way to read a repeated parameter)
        category: list[str] = Query(default=[]),  # noqa: B008
        status: list[str] = Query(default=[]),  # noqa: B008
        team_size: list[str] = Query(default=[]),  # noqa: B008
        looking_for: list[str] = Query(default=[]),  # noqa: B008
        limit: int | None = Query(default=None, ge=1, le=50),
    ) -> JSONResponse:
        from crew import deck

        filters = {"location": location, "category": category, "status": status, "team_size": team_size,
                   "looking_for": looking_for}  # fmt: skip
        return _call(deck.deck, user_id, filters, limit=limit)

    @r.post("/crew/pass")
    def crew_pass(user_id: str, body: dict[str, Any]) -> JSONResponse:
        from crew import deck

        return _call(deck.pass_idea, user_id, body.get("idea_id"))

    @r.post("/crew/pass/undo")
    def crew_pass_undo(user_id: str) -> JSONResponse:
        from crew import deck

        return _call(deck.undo_last, user_id)

    @r.post("/crew/pass/reset")
    def crew_pass_reset(user_id: str) -> JSONResponse:
        from crew import deck

        return _call(deck.reset, user_id)

    return r
