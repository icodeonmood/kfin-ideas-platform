"""The review side's `/internal/*` routes (A-API.desk, A-API.questions, A-API.committee), on their own router so
`api/app.py` takes one include line.

The web app has already checked who may call each route (RBAC) and passes the signed-in person as `user_id`.
The worker checks the role again for every desk route, because the web capabilities let admins reach the desk and
P-PRODUCT.privacy does not (DEC-104): a desk read needs the review desk or the Ones Committee (`store.READERS`), a desk
write the review desk (`store.REVIEWERS`), else `403 forbidden`. The services check what that person may do to
this idea (their own idea, a closed window). Errors follow A-API.conventions/2: `{error: {code, message, field?}}`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from core.db import connect
from desk.store import READERS, REVIEWERS, Refused, require_role


def _call(
    fn: Callable[..., Any],
    *args: Any,
    status: int = 200,
    need: tuple[frozenset[str], str] | None = None,
    **kwargs: Any,
) -> JSONResponse:
    """`need` is (roles, user_id): the role check runs first, on the same connection."""
    with connect(autocommit=True) as conn:
        try:
            if need is not None:
                require_role(conn, need[1], need[0])
            body = fn(conn, *args, **kwargs)
        except Refused as exc:
            return JSONResponse(exc.body(), status_code=exc.status)
    if body is None:
        return JSONResponse({"error": {"code": "not_found", "message": ""}}, status_code=404)
    return JSONResponse(jsonable_encoder(body), status_code=status, headers={"Cache-Control": "no-store"})


def build(require_token: Callable[..., None]) -> APIRouter:
    """The router, guarded by the app's internal-token check."""
    r = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])

    # --- the desk (S-R1, S-R2) ---------------------------------------------------------------------------
    @r.get("/desk")
    def desk_list(
        user_id: str, tab: str = "waiting", sort: str = "time_left", q: str | None = None
    ) -> JSONResponse:
        from desk import reads

        return _call(reads.desk, user_id, tab, sort, q, need=(READERS, user_id))

    @r.post("/desk/ideas/{ref}/open")
    def desk_open(ref: str, user_id: str) -> JSONResponse:
        from desk import review

        return _call(review.open_idea, ref, user_id, need=(REVIEWERS, user_id))

    @r.get("/desk/ideas/{ref}")
    def desk_idea(ref: str, user_id: str) -> JSONResponse:
        from desk import reads

        return _call(reads.reviewer_idea, ref, user_id, need=(READERS, user_id))

    @r.get("/desk/ideas/{ref}/listen")
    def desk_listen(ref: str, user_id: str) -> JSONResponse:
        from desk import reads

        return _call(reads.listen_script, ref, user_id, need=(READERS, user_id))

    @r.put("/desk/ideas/{ref}/worth")
    def desk_worth(ref: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from desk import revise

        return _call(revise.revise_worth, ref, user_id, body, need=(REVIEWERS, user_id))

    @r.post("/desk/ideas/{ref}/decision")
    def desk_decide(ref: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from desk import decide

        return _call(decide.send, ref, user_id, body, status=201, need=(REVIEWERS, user_id))

    @r.get("/desk/ideas/{ref}/merge-sheet")
    def desk_merge_sheet(ref: str, user_id: str, other: str) -> JSONResponse:
        from desk import merging

        return _call(merging.sheet_for, ref, other, user_id, need=(REVIEWERS, user_id))

    @r.post("/desk/ideas/{ref}/merge")
    def desk_merge(ref: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from desk import merging

        return _call(merging.desk_merge, ref, user_id, body, status=201, need=(REVIEWERS, user_id))

    # --- questions and answers (S-R2 Ask, S-R3) ----------------------------------------------------------
    @r.get("/desk/ideas/{ref}/suggested-questions")
    def desk_suggested(ref: str, user_id: str) -> JSONResponse:
        from desk import asking

        return _call(asking.suggested, ref, user_id, need=(REVIEWERS, user_id))

    @r.post("/desk/ideas/{ref}/question-sets")
    def desk_ask(ref: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from desk import asking

        return _call(asking.send_set, ref, user_id, body, status=201, need=(REVIEWERS, user_id))

    @r.post("/question-sets/{set_id}/extend")
    def set_extend(set_id: str, user_id: str) -> JSONResponse:
        from desk import asking

        return _call(asking.give_more_time, set_id, user_id, need=(REVIEWERS, user_id))

    @r.post("/question-sets/{set_id}/remind")
    def set_remind(set_id: str, user_id: str) -> JSONResponse:
        from desk import asking

        return _call(asking.remind, set_id, user_id, need=(REVIEWERS, user_id))

    @r.get("/ideas/{ref}/question-set")
    def sharer_set(ref: str, user_id: str, set_id: str | None = None) -> JSONResponse:
        from desk import asking

        return _call(asking.open_set_for_sharer, ref, user_id, set_id=set_id)

    @r.put("/questions/{question_id}/answer")
    def sharer_answer(question_id: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from desk import asking

        return _call(asking.save_answer, question_id, user_id, body.get("text"), body.get("file_ids"))

    @r.post("/question-sets/{set_id}/send")
    def sharer_send(set_id: str, user_id: str) -> JSONResponse:
        from desk import asking

        return _call(asking.send_answers, set_id, user_id)

    # --- the Ones Committee (S-R4) and the decision on an idea (S-06, S-R2) ------------------------------
    @r.get("/committee")
    def committee_list(user_id: str, tab: str = "window", sort: str = "closing") -> JSONResponse:
        from desk import committee

        return _call(committee.listing, user_id, tab, sort)

    @r.get("/committee/windows/{window_id}/reversing")
    def committee_reversing(window_id: str, user_id: str) -> JSONResponse:
        from desk import committee

        return _call(committee.reversing_words, window_id, user_id)

    @r.post("/committee/windows/{window_id}/extend")
    def committee_extend(window_id: str, user_id: str) -> JSONResponse:
        from desk import committee

        return _call(committee.extend_window, window_id, user_id)

    @r.post("/committee/windows/{window_id}/reverse")
    def committee_reverse(window_id: str, user_id: str, body: dict[str, Any]) -> JSONResponse:
        from desk import committee

        return _call(committee.reverse_window, window_id, user_id, body)

    @r.get("/ideas/{ref}/decision")
    def idea_decision(ref: str, user_id: str) -> JSONResponse:
        from desk import committee

        return _call(committee.decision_for_viewer, ref, user_id)

    return r
