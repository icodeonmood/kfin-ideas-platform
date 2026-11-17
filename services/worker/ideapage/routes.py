"""Lane E's `/internal/*` routes for an idea's own pages (A-API.ideas, A-API.my-ideas), on their own router so
`api/app.py` takes one include line.

The web app has checked the session and the endpoint's capability (policy/rbac.yaml) and passes the signed-in
person as `user_id`; the services here decide what that person may see of this idea. Errors follow
A-API.conventions/2: `{error: {code, message, …}}`. Responses never carry text in logs (non-negotiable 3).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.db import connect

NOT_FOUND = {"error": {"code": "not_found", "message": "We can’t find that idea."}}


def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> JSONResponse:
    from ideapage import colleague, read, withdraw

    with connect(autocommit=True) as conn:
        try:
            body = fn(conn, *args, **kwargs)
        except read.NotFound:
            return JSONResponse(NOT_FOUND, status_code=404)
        except colleague.Paused:
            return JSONResponse(
                {"error": {"code": "wall_paused", "message": "The Wall is paused for a short while."}},
                status_code=503,
            )
        except withdraw.Refused as exc:
            return JSONResponse(exc.body(), status_code=exc.status)
    return JSONResponse(jsonable_encoder(body), headers={"Cache-Control": "no-store"})


def build(require_token: Callable[..., None]) -> APIRouter:
    r = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])

    @r.get("/ideas/{key}/view")
    def idea_view(
        key: str, user_id: str, came_from: str | None = None, back: str | None = None
    ) -> JSONResponse:
        """`/ideas/:id`: S-06 for the sharer, a pointer to S-R2 for a reviewer, S-09 for anyone else."""
        from ideapage.route import idea_view as view

        return _call(view, key, user_id, came_from=came_from, back=back)

    @r.get("/me/{user_id}/my-ideas")
    def my_ideas(
        user_id: str,
        list_: str | None = Query(None, alias="list"),
        filter_: str | None = Query(None, alias="filter"),
        sort: str | None = None,
        q: str | None = None,
        row: str | None = None,
        device: str | None = None,
    ) -> JSONResponse:
        """S-07: the person's list in the state the URL names (P-ROUTES.state)."""
        from ideapage.mine import my_ideas as mine

        params = {"list": list_, "filter": filter_, "sort": sort, "q": q, "row": row}
        return _call(mine, user_id, params, device=device)

    @r.get("/me/{user_id}/shell-lists")
    def shell_lists(user_id: str, device_id: str | None = None) -> JSONResponse:
        """C-SIDEBAR.anatomy/4 (A-API.me `drafts`, `ideas`): the sidebar's two drafts and three ideas, as S-07
        lists them first. `device_id` is the browser's device cookie, for "on this laptop"."""
        from ideapage.mine import shell_lists as lists

        return _call(lists, user_id, device_id)

    @r.post("/ideas/{key}/withdraw")
    def idea_withdraw(key: str, user_id: str, body: dict[str, Any] | None = None) -> JSONResponse:
        from ideapage.withdraw import withdraw

        reason = (body or {}).get("reason")
        return _call(withdraw, key, user_id, reason if isinstance(reason, str) else None)

    @r.post("/ideas/{key}/restore")
    def idea_restore(key: str, user_id: str) -> JSONResponse:
        from ideapage.withdraw import restore

        return _call(restore, key, user_id)

    return r
