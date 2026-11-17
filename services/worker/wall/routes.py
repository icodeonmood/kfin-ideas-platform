"""The Wall's, the Ones' and Profile's `/internal/*` routes (A-API.wall, A-API.ones, A-API.ones-posts, A-API.me),
on their own router so `api/app.py` takes one include line.

The web app has already checked who may call each route (RBAC) and passes the signed-in person as `user_id`; the
services check the rest (only a One reads and changes their dashboard; a profile is only ever the caller's own).
Kill switches are checked here on every request as well as in the web proxy (§7.6): `wall.public` for the Wall,
`ones.public` for the Ones. Errors follow A-API.conventions/2.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core import killswitch
from core.db import connect
from gateway import AgentFailed
from wall.common import MSG_SAVE_FAILED, Refused


def _paused(switch: str) -> JSONResponse:
    return JSONResponse({"error": {"code": "paused", "message": "", "switch": switch}}, status_code=503)


def _call(
    fn: Callable[..., Any], *args: Any, status: int = 200, switches: tuple[str, ...] = (), **kwargs: Any
) -> JSONResponse:
    with connect(autocommit=True) as conn:
        for name in switches:
            if not killswitch.is_on(name, conn):
                return _paused(name)
        try:
            body = fn(conn, *args, **kwargs)
        except Refused as exc:
            return JSONResponse(exc.body(), status_code=exc.status)
        except AgentFailed:  # the checks could not run: a clean answer the screen can show, never a 500
            return JSONResponse({"error": {"code": "try_again", "message": MSG_SAVE_FAILED}}, status_code=503)
    return JSONResponse(jsonable_encoder(body), status_code=status, headers={"Cache-Control": "no-store"})


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def build(require_token: Callable[..., None]) -> APIRouter:
    """The router, guarded by the app's internal-token check."""
    from wall import ember, impact, kindling, ones, profile

    r = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])
    wall_on = ("wall.public",)

    # --- The Wall (S-WALL, L-WALL): anyone signed in ---------------------------------------------------------------
    @r.get("/wall/kindling")
    def wall_kindling(kind: str | None = None) -> JSONResponse:
        return _call(kindling.kindling, kind, switches=wall_on)

    @r.get("/wall/just-in")
    def wall_just_in(
        kind: str | None = None, sort: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> JSONResponse:
        return _call(kindling.just_in, kind, sort, limit, offset, switches=wall_on)

    @r.get("/wall/ones")
    def wall_ones(order: str = "wall") -> JSONResponse:
        return _call(ones.one_cards, order, switches=("wall.public", "ones.public"))

    @r.get("/wall/impact")
    def wall_impact() -> JSONResponse:
        return _call(impact.wall_impact, _now(), switches=wall_on)

    @r.get("/wall/ember")
    def wall_ember() -> JSONResponse:
        return _call(ember.ember, _now(), switches=wall_on)

    # --- The Ones' posts (Home's fan, C-ONES-FAN): anyone signed in -----------------------------------------------
    @r.get("/ones/posts")
    def ones_posts(user_id: str) -> JSONResponse:
        return _call(ones.posts, user_id, _now(), switches=("ones.public",))

    @r.put("/ones/posts/{post_id}/like")
    def ones_post_like(post_id: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        return _call(ones.like, user_id, post_id, body.get("liked"), switches=("ones.public",))

    # --- A One's own dashboard (S-ONE): the One alone --------------------------------------------------------------
    @r.get("/one")
    def one_dashboard(user_id: str) -> JSONResponse:
        return _call(ones.dashboard, user_id, _now())

    @r.put("/one/number")
    def one_number(user_id: str, body: dict[str, Any]) -> JSONResponse:
        return _call(ones.set_number, user_id, body.get("number"), _now())

    @r.post("/one/brief")
    def one_brief(user_id: str, body: dict[str, Any]) -> JSONResponse:
        return _call(ones.propose_brief, user_id, body.get("text"), _now(), status=201)

    @r.post("/one/glow-up/{glow_id}/seen")
    def one_glow_up_seen(glow_id: str, user_id: str) -> JSONResponse:
        return _call(ones.glow_up_seen, user_id, glow_id, _now())

    # --- Profile (S-H6): the person alone --------------------------------------------------------------------------
    @r.get("/me/profile")
    def me_profile(user_id: str) -> JSONResponse:
        return _call(profile.profile, user_id)

    @r.patch("/me/settings")
    def me_settings(user_id: str, body: dict[str, Any]) -> JSONResponse:
        return _call(profile.save_settings, user_id, body)

    return r
