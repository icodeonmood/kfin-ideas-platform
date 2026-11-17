"""Lane C's `/internal/*` routes for sorting and sending (A-API.drafts sorting and submit, A-API.ideas edit and
versions, A-API.config), on their own router so `api/app.py` takes one include line.

The web app has checked the session and the capability (policy/rbac.yaml) and the kill switches, and passes the
signed-in person as `user_id`; the services decide what that person may do with this draft or idea. Errors follow
A-API.conventions/2. Nothing here logs text (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.db import connect


def _json(body: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(jsonable_encoder(body), status_code=status, headers={"Cache-Control": "no-store"})


def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> JSONResponse:
    from submit.errors import Refused

    with connect(autocommit=True) as conn:
        try:
            result = fn(conn, *args, **kwargs)
        except Refused as exc:
            return _json(exc.body(), exc.status)
    if isinstance(result, tuple):
        status, body = result
        return _json(body, int(status))
    return _json(result)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def build(require_token: Callable[..., None]) -> APIRouter:
    from submit import adapters

    adapters.install_hooks()  # lane C's part of a restore, when lane E's withdraw module is here
    r = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])

    @r.get("/config/sorting")
    def config_sorting() -> JSONResponse:
        """A-API.config, lane C's values: the sorting lists, the declaration, the review days and the edit window."""
        from submit.config import public_config

        return _json(public_config())

    @r.get("/drafts/{key}/sorting")
    def draft_sorting(key: str, user_id: str) -> JSONResponse:
        from submit.sorting import read_draft

        return _call(read_draft, key, user_id)

    @r.patch("/drafts/{key}/sorting")
    def draft_sorting_update(key: str, user_id: str, body: Any = Body(default=None)) -> JSONResponse:  # noqa: B008
        from submit.sorting import update_draft

        return _call(update_draft, key, user_id, body, now=_now())

    @r.get("/drafts/{key}/send")
    def draft_send(key: str, user_id: str) -> JSONResponse:
        from submit.ready import send_view

        return _call(send_view, key, user_id, now=_now())

    @r.post("/drafts/{key}/submit")
    def draft_submit(
        key: str,
        user_id: str,
        idempotency_key: str | None = None,
        body: Any = Body(default=None),  # noqa: B008
    ) -> JSONResponse:
        from submit.send import submit

        return _call(submit, key, user_id, body, idempotency_key=idempotency_key or None, now=_now())

    @r.get("/ideas/{key}/edit")
    def idea_edit_page(key: str, user_id: str) -> JSONResponse:
        from submit.edit import page

        return _call(page, key, user_id, now=_now())

    @r.patch("/ideas/{key}/edit")
    def idea_edit_save(key: str, user_id: str, body: Any = Body(default=None)) -> JSONResponse:  # noqa: B008
        from submit.edit import save

        return _call(save, key, user_id, body, now=_now())

    @r.get("/ideas/{key}/versions")
    def idea_versions(key: str, user_id: str) -> JSONResponse:
        from submit.edit import versions

        return _call(versions, key, user_id, now=_now())

    return r
