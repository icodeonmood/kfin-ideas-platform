"""The admin path's `/internal/admin/*` routes, on their own router so `api/app.py` takes one include line.

The web app has already checked the capability (RBAC) and passes the signed-in person as `user_id` in the body (or
the path for reads); the services check the person's grants again. No kill switch pauses these: they are the
programme's own records, and an admin must be able to act while features are paused (reasoned exemptions in
`apps/web/src/lib/killswitch-routes.ts`). Errors follow A-API.conventions/2.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.db import connect
from programme.common import Refused, now_utc


def _call(fn: Callable[..., Any], *args: Any, status: int = 200) -> JSONResponse:
    with connect(autocommit=True) as conn:
        try:
            body = fn(conn, *args)
        except Refused as exc:
            return JSONResponse(exc.body(), status_code=exc.status)
    return JSONResponse(jsonable_encoder(body), status_code=status, headers={"Cache-Control": "no-store"})


def _who(body: dict[str, Any]) -> str:
    user_id = body.get("user_id")
    return user_id if isinstance(user_id, str) else ""


def build(require_token: Callable[..., None]) -> APIRouter:
    from programme import build as team
    from programme import impact, ones, view, wall

    r = APIRouter(prefix="/internal/admin", dependencies=[Depends(require_token)])

    @r.get("/view/{user_id}")
    def admin_view(user_id: str) -> JSONResponse:
        return _call(lambda c: view.admin_view(c, user_id, now_utc()))

    @r.post("/ideas/{ref}/build-team")
    def build_team(ref: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: team.choose_team(c, _who(body), ref, body), status=201)

    @r.post("/ideas/{ref}/shipped")
    def shipped(ref: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: team.mark_shipped(c, _who(body), ref))

    @r.put("/ideas/{ref}/measurements/{mark}")
    def measurement(ref: str, mark: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: impact.enter(c, _who(body), ref, mark, body))

    @r.post("/ideas/{ref}/measurements/{mark}/finance")
    def finance(ref: str, mark: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: impact.finance_confirm(c, _who(body), ref, mark))

    @r.post("/ideas/{ref}/wall-removal")
    def take_off(ref: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: wall.take_off(c, _who(body), ref, body), status=201)

    @r.post("/ideas/{ref}/wall-restore")
    def restore(ref: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: wall.restore(c, _who(body), ref, body))

    @r.post("/ones/founding")
    def founding(body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: ones.mark_founding(c, _who(body), body), status=201)

    @r.post("/ones/{one_id}/remove")
    def remove(one_id: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        return _call(lambda c: ones.remove_one(c, _who(body), one_id, body))

    return r
