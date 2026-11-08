"""FastAPI app for `/internal/*` (§8). Only the web app calls it, with the shared INTERNAL_API_TOKEN.

Health stays open for the container healthcheck; everything else needs the token (BLD-048).
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from api.canvas_config import canvas_config
from attachments import service as attachments
from core.config import get_settings
from core.db import connect
from core.logging import get_logger
from index.indexer import Indexer

log = get_logger("api")
app = FastAPI(title="kfin-ideas worker", docs_url=None, redoc_url=None, openapi_url=None)


def require_token(x_internal_token: str = Header(default="")) -> None:
    expected = get_settings().internal_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="internal token not configured")
    if get_settings().is_production_like and len(expected) < 32:
        raise HTTPException(status_code=503, detail="internal token too short for this environment")
    if not hmac.compare_digest(x_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="internal token required")


@app.get("/internal/health")
def health() -> dict[str, Any]:
    try:
        with connect(autocommit=True) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        log.error("health.db_unreachable", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="database unreachable") from None
    return {"status": "ok", "roles": sorted(get_settings().roles)}


@app.get("/internal/token-check", dependencies=[Depends(require_token)])
def token_check() -> dict[str, bool]:
    """For the web app's deep health check: the caller's internal token is the right one."""
    return {"ok": True}


@app.post("/internal/index", dependencies=[Depends(require_token)])
def index_now() -> dict[str, Any]:
    result = Indexer().run_once()
    return {"commit": result.to_commit, "upserted": len(result.upserted), "deleted": len(result.deleted)}


@app.get("/internal/canvas-config", dependencies=[Depends(require_token)])
def get_canvas_config() -> dict[str, Any]:
    return canvas_config()


@app.post("/internal/scan", dependencies=[Depends(require_token)])
def scan() -> JSONResponse:
    return JSONResponse({"error": "not_built", "block": "B4"}, status_code=501)


@app.post("/hooks/git-post-commit", dependencies=[Depends(require_token)])
def post_commit() -> dict[str, Any]:
    return index_now()


@app.post("/internal/attachments", dependencies=[Depends(require_token)])
def upload_attachment(
    file: UploadFile, idea_uuid: str = Form(...), uploaded_by_code: str = Form(...)
) -> JSONResponse:
    # A plain def: FastAPI runs it in a thread, so the store and database calls never block the event loop.
    limit = attachments.limits().max_bytes_each
    data = file.file.read(limit + 1)
    try:
        with connect(autocommit=True) as conn:
            body = attachments.accept(
                conn,
                idea_uuid=idea_uuid,
                uploaded_by_code=uploaded_by_code,
                name=file.filename or "file",
                data=data,
            )
    except attachments.AttachmentRefused as exc:
        return JSONResponse({"error": exc.code}, status_code=exc.status)
    return JSONResponse(body, status_code=201)


@app.get("/internal/attachments/{att_id}/content", dependencies=[Depends(require_token)])
def attachment_content(att_id: str) -> Response:
    try:
        with connect(autocommit=True) as conn:
            data, mime, _name = attachments.content(conn, att_id)
    except attachments.AttachmentRefused as exc:
        return JSONResponse({"error": exc.code}, status_code=exc.status)
    return Response(content=data, media_type=mime)


@app.delete("/internal/attachments/{att_id}", dependencies=[Depends(require_token)])
def delete_attachment(att_id: str) -> Response:
    with connect(autocommit=True) as conn:
        attachments.remove(conn, att_id)
    return Response(status_code=204)


@app.get("/internal/scans/{idea_uuid}/view", dependencies=[Depends(require_token)])
def scan_view(idea_uuid: str, mode: str = "neutral") -> JSONResponse:
    """The scan as one viewer may see it. The web app decides `mode` from §3.1 (owner: real)."""
    from scan.view import view

    if mode not in ("real", "neutral"):
        return JSONResponse({"error": "bad_mode"}, status_code=400)
    with connect(autocommit=True) as conn:
        body = view(conn, idea_uuid, "real" if mode == "real" else "neutral")
    if body is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@app.post("/internal/scans/{idea_uuid}/confirm", dependencies=[Depends(require_token)])
def scan_confirm(idea_uuid: str, body: dict[str, Any]) -> JSONResponse:
    """The owner keeps or clears suggestions and may edit the one line and details (the web app checked
    ownership). Re-runs the match when the text changed by more than the rule's share (AT-B5-07)."""
    from gateway import AgentFailed
    from scan.confirm import ConfirmRefused, confirm
    from scan.view import view

    with connect(autocommit=True) as conn:
        idea = conn.execute("SELECT idea_id FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
        if idea is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        try:
            out = confirm(conn, idea_uuid, idea["idea_id"], body)
        except ConfirmRefused as exc:
            return JSONResponse({"error": exc.code, "details": exc.details}, status_code=exc.status)
        except AgentFailed as exc:  # switched off, leak check, route down: a clean answer, never a 500
            return JSONResponse({"error": "checks_unavailable", "code": exc.code}, status_code=503)
        return JSONResponse(
            {**out, "view": view(conn, idea_uuid, "real")}, headers={"Cache-Control": "no-store"}
        )


@app.post("/internal/scans/{idea_uuid}/save", dependencies=[Depends(require_token)])
def scan_save(idea_uuid: str, body: dict[str, Any]) -> JSONResponse:
    """The person's choice and the one-transaction save (§4.2 step 8)."""
    from gateway import AgentFailed
    from scan.save import SaveRefused, save

    code = str(body.get("contributor_code") or "")
    with connect(autocommit=True) as conn:
        try:
            out = save(conn, idea_uuid, code, body)
        except SaveRefused as exc:
            return JSONResponse({"error": exc.code}, status_code=exc.status)
        except AgentFailed as exc:
            return JSONResponse({"error": "checks_unavailable", "code": exc.code}, status_code=503)
    return JSONResponse(out)


@app.get("/internal/inbox/{user_id}", dependencies=[Depends(require_token)])
def inbox_list(user_id: str) -> JSONResponse:
    """The person's in-app messages, rendered for them (the web app vouches for who they are)."""
    from comms.inbox import inbox

    with connect(autocommit=True) as conn:
        return JSONResponse({"messages": inbox(conn, user_id)}, headers={"Cache-Control": "no-store"})


@app.post("/internal/inbox/{user_id}/{notification_id}/read", dependencies=[Depends(require_token)])
def inbox_read(user_id: str, notification_id: int) -> JSONResponse:
    from comms.inbox import mark_read

    with connect(autocommit=True) as conn:
        ok = mark_read(conn, user_id, notification_id)
    return JSONResponse({"ok": ok}, status_code=200 if ok else 404)


def _review_call(fn: Any, *args: Any) -> JSONResponse:
    from review.service import ActionRefused

    with connect(autocommit=True) as conn:
        try:
            return JSONResponse(fn(conn, *args))
        except ActionRefused as exc:
            return JSONResponse({"error": exc.code}, status_code=exc.status)


@app.post("/internal/review/items/{item_id}/action", dependencies=[Depends(require_token)])
def review_action(item_id: int, body: dict[str, Any]) -> JSONResponse:
    """A review desk action; the web app has checked `work_review_queue` and passes who is acting."""
    from review.service import act

    return _review_call(act, item_id, str(body.get("reviewer_user_id") or ""), body)


@app.post("/internal/review/items/{item_id}/confirm-hold", dependencies=[Depends(require_token)])
def review_confirm_hold(item_id: int, body: dict[str, Any]) -> JSONResponse:
    from review.service import confirm_hold

    return _review_call(confirm_hold, item_id, str(body.get("reviewer_user_id") or ""))


@app.post("/internal/ideas/{idea_uuid}/answer", dependencies=[Depends(require_token)])
def idea_answer(idea_uuid: str, body: dict[str, Any]) -> JSONResponse:
    from review.service import answer

    return _review_call(
        answer, idea_uuid, str(body.get("contributor_code") or ""), str(body.get("text") or "")
    )


@app.post("/internal/ideas/{idea_uuid}/disagree", dependencies=[Depends(require_token)])
def idea_disagree(idea_uuid: str, body: dict[str, Any]) -> JSONResponse:
    from review.service import disagree

    return _review_call(
        disagree, idea_uuid, str(body.get("contributor_code") or ""), str(body.get("text") or "")
    )


@app.get("/internal/review/items/{item_id}/view", dependencies=[Depends(require_token)])
def review_item_view(item_id: int, mode: str = "neutral") -> JSONResponse:
    """The item screen as one viewer may see it; the web app decides `mode` from the restore policy."""
    from review.view import item_view

    if mode not in ("real", "neutral"):
        return JSONResponse({"error": "bad_mode"}, status_code=400)
    with connect(autocommit=True) as conn:
        body = item_view(conn, item_id, "real" if mode == "real" else "neutral")
    if body is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@app.get("/internal/review/desk-decisions", dependencies=[Depends(require_token)])
def review_desk_decisions() -> JSONResponse:
    from review.veto import desk_decisions

    with connect(autocommit=True) as conn:
        return JSONResponse(desk_decisions(conn), headers={"Cache-Control": "no-store"})


@app.post("/internal/review/items/{item_id}/veto", dependencies=[Depends(require_token)])
def review_veto(item_id: int, body: dict[str, Any]) -> JSONResponse:
    """A core committee member's veto (the web app checked `veto_desk_decision`)."""
    from review.veto import veto

    return _review_call(veto, item_id, str(body.get("member_user_id") or ""), str(body.get("reason") or ""))


@app.get("/internal/wall", dependencies=[Depends(require_token)])
def wall_view() -> JSONResponse:
    """The public wall (§4.13). Everything on it has passed review and its summary check."""
    from views.wall import wall

    with connect(autocommit=True) as conn:
        return JSONResponse(wall(conn), headers={"Cache-Control": "no-store"})


@app.get("/internal/me/{user_id}/ideas", dependencies=[Depends(require_token)])
def my_ideas_view(user_id: str) -> JSONResponse:
    """My ideas (AT-B7-02); the web app vouches for who the person is."""
    from views.mine import my_ideas

    with connect(autocommit=True) as conn:
        return JSONResponse(my_ideas(conn, user_id), headers={"Cache-Control": "no-store"})


@app.put("/internal/me/{user_id}/name-on-wall", dependencies=[Depends(require_token)])
def name_on_wall(user_id: str, body: dict[str, Any]) -> JSONResponse:
    from views.mine import set_name_on_wall

    if not isinstance(body.get("on"), bool):
        return JSONResponse({"error": "bad_request"}, status_code=400)
    with connect(autocommit=True) as conn:
        return JSONResponse(set_name_on_wall(conn, user_id, body["on"]))


@app.get("/internal/ideas/{idea_id}/page", dependencies=[Depends(require_token)])
def idea_page_view(idea_id: str, view: str, mode: str, user_id: str) -> JSONResponse:
    """The idea page in the view and restore mode the web app chose from §3.1 (AT-B7-03)."""
    from views.idea_page import page
    from views.mine import viewer_codes

    if view not in ("full", "public") or mode not in ("real", "neutral"):
        return JSONResponse({"error": "bad_request"}, status_code=400)
    with connect(autocommit=True) as conn:
        out = page(conn, idea_id, view, mode, viewer_codes(conn, user_id))  # type: ignore[arg-type]
    if out is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(out, headers={"Cache-Control": "no-store"})
