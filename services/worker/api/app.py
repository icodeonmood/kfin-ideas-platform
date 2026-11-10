"""FastAPI app for `/internal/*` (§8). Only the web app calls it, with the shared INTERNAL_API_TOKEN.

Health stays open for the container healthcheck; everything else needs the token (BLD-048).
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from psycopg.types.json import Jsonb

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


@app.post("/internal/voice", dependencies=[Depends(require_token)])
def upload_voice(
    file: UploadFile, idea_uuid: str = Form(...), uploaded_by_code: str = Form(...)
) -> JSONResponse:
    """A voice note for a draft's quick capture (DEC-096). The web app checked the person owns the draft."""
    from voice import service as voice

    data = file.file.read(voice.MAX_BYTES + 1)
    try:
        with connect(autocommit=True) as conn:
            body = voice.accept(conn, idea_uuid=idea_uuid, uploaded_by_code=uploaded_by_code, data=data)
    except voice.VoiceRefused as exc:
        return JSONResponse({"error": exc.code}, status_code=exc.status)
    return JSONResponse(body, status_code=201)


@app.get("/internal/voice/{voice_id}", dependencies=[Depends(require_token)])
def voice_status(voice_id: str, idea_uuid: str) -> JSONResponse:
    """The owner's view of one voice note: its state, and its text once ready (the web app checked ownership)."""
    from voice import service as voice

    with connect(autocommit=True) as conn:
        body = voice.status(conn, voice_id, idea_uuid)
    if body is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@app.delete("/internal/voice/{voice_id}", dependencies=[Depends(require_token)])
def delete_voice(voice_id: str, idea_uuid: str) -> Response:
    """The person took the text, or threw the note away: the recording and the held text go."""
    from voice import service as voice

    with connect(autocommit=True) as conn:
        voice.remove_for(conn, voice_id, idea_uuid)
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


# --- The Ones (DEC-034 to DEC-087). The web app checks the capability and passes who is acting; the worker checks
# the person's grants again. Refusals answer with a code; text is never echoed or logged.


def _ones_call(fn: Any, *args: Any, status: int = 200) -> JSONResponse:
    from gateway import AgentFailed
    from ones.text import OnesRefused

    with connect(autocommit=True) as conn:
        try:
            return JSONResponse(fn(conn, *args), status_code=status, headers={"Cache-Control": "no-store"})
        except OnesRefused as exc:
            return JSONResponse({"error": exc.code}, status_code=exc.status)
        except AgentFailed as exc:  # the checks could not run: a clean answer, never a 500
            return JSONResponse({"error": "checks_unavailable", "code": exc.code}, status_code=503)


def _actor(body: dict[str, Any]) -> str:
    return str(body.get("actor_user_id") or "")


@app.get("/internal/ones/console", dependencies=[Depends(require_token)])
def ones_console() -> JSONResponse:
    from ones.views import console

    return _ones_call(console)


@app.post("/internal/ones/proposals", dependencies=[Depends(require_token)])
def ones_propose(body: dict[str, Any]) -> JSONResponse:
    from ones.service import propose

    return _ones_call(propose, _actor(body), body, status=201)


@app.post("/internal/ones/proposals/{proposal_id}/decide", dependencies=[Depends(require_token)])
def ones_decide(proposal_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import decide

    return _ones_call(decide, _actor(body), proposal_id, body)


@app.post("/internal/ones/proposals/{proposal_id}/carry-out", dependencies=[Depends(require_token)])
def ones_carry_out(proposal_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import carry_out

    return _ones_call(carry_out, _actor(body), proposal_id)


@app.post("/internal/ones/proposals/{proposal_id}/withdraw", dependencies=[Depends(require_token)])
def ones_withdraw(proposal_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import withdraw

    return _ones_call(withdraw, _actor(body), proposal_id)


@app.get("/internal/ones/proposals/{proposal_id}/invite/{user_id}", dependencies=[Depends(require_token)])
def ones_invite_view(proposal_id: int, user_id: str) -> JSONResponse:
    from ones.views import invite_view

    with connect(autocommit=True) as conn:
        out = invite_view(conn, proposal_id, user_id)
    if out is None:
        return JSONResponse({"error": "not_invited"}, status_code=403)
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@app.post("/internal/ones/proposals/{proposal_id}/messages", dependencies=[Depends(require_token)])
def ones_message(proposal_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import add_message

    return _ones_call(add_message, _actor(body), proposal_id, body, status=201)


@app.post("/internal/ones/proposals/{proposal_id}/invites", dependencies=[Depends(require_token)])
def ones_invite(proposal_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import invite_peer

    return _ones_call(invite_peer, _actor(body), proposal_id, str(body.get("email") or ""))


@app.put("/internal/ones/{one_id}/measures", dependencies=[Depends(require_token)])
def ones_measures(one_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import set_measures

    return _ones_call(set_measures, _actor(body), one_id, body.get("measures") or {})


@app.post("/internal/ones/{one_id}/awards", dependencies=[Depends(require_token)])
def ones_award(one_id: int, body: dict[str, Any]) -> JSONResponse:
    from ones.service import award

    return _ones_call(award, _actor(body), one_id, body, status=201)


@app.get("/internal/ones/{one_id}/showcase", dependencies=[Depends(require_token)])
def ones_showcase(one_id: int) -> JSONResponse:
    from ones.views import showcase

    with connect(autocommit=True) as conn:
        out = showcase(conn, one_id)
    if out is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@app.put("/internal/ones/screen-mode", dependencies=[Depends(require_token)])
def ones_screen_mode(body: dict[str, Any]) -> JSONResponse:
    from ones.service import set_screen_mode

    return _ones_call(set_screen_mode, _actor(body), body.get("mode"))


@app.post("/internal/ones/announce", dependencies=[Depends(require_token)])
def ones_announce(body: dict[str, Any]) -> JSONResponse:
    from ones.service import announce

    return _ones_call(announce, _actor(body))


# --- The Ember (DEC-062, DEC-070, BLD-128): drafts and the note for the chair and admins; sending for admins; the
# archive for everyone. Same refusal handling as the Ones.


@app.get("/internal/me/{user_id}/points", dependencies=[Depends(require_token)])
def my_points(user_id: str) -> JSONResponse:
    """A person's own points (DEC-078): the web app passes the signed-in person; nobody reads anyone else's."""
    from points.ledger import mine

    return _ones_call(mine, user_id)


@app.get("/internal/me/{user_id}/lens", dependencies=[Depends(require_token)])
def my_lens(user_id: str) -> JSONResponse:
    """A person's own lens (BLD-135): their ideas and groups, counts only. The web app passes the signed-in person."""
    from lenses import mine

    return _ones_call(mine, user_id)


@app.get("/internal/ember", dependencies=[Depends(require_token)])
def ember_archive() -> JSONResponse:
    from ember.service import archive

    return _ones_call(archive)


@app.get("/internal/ember/current/{viewer_id}", dependencies=[Depends(require_token)])
def ember_current(viewer_id: str) -> JSONResponse:
    from ember.service import current_draft

    return _ones_call(current_draft, viewer_id)


@app.get("/internal/ember/{issue_id}/{viewer_id}", dependencies=[Depends(require_token)])
def ember_view(issue_id: str, viewer_id: str) -> JSONResponse:
    from ember.service import view

    return _ones_call(view, viewer_id, issue_id)


@app.post("/internal/ember/drafts", dependencies=[Depends(require_token)])
def ember_draft(body: dict[str, Any]) -> JSONResponse:
    from ember.service import draft

    return _ones_call(draft, _actor(body), body, status=201)


@app.put("/internal/ember/{issue_id}/note", dependencies=[Depends(require_token)])
def ember_note(issue_id: str, body: dict[str, Any]) -> JSONResponse:
    from ember.service import set_note

    return _ones_call(set_note, _actor(body), issue_id, body)


@app.post("/internal/ember/{issue_id}/send", dependencies=[Depends(require_token)])
def ember_send(issue_id: str, body: dict[str, Any]) -> JSONResponse:
    from ember.service import send

    return _ones_call(send, _actor(body), issue_id, body)


@app.post("/internal/ember/{issue_id}/ready", dependencies=[Depends(require_token)])
def ember_ready(issue_id: str, body: dict[str, Any]) -> JSONResponse:
    """The core committee chair approves the note; the issue becomes ready to send (Ember review)."""
    from ember.service import approve_note

    return _ones_call(approve_note, _actor(body), issue_id)


@app.get("/internal/ones/public", dependencies=[Depends(require_token)])
def ones_public() -> JSONResponse:
    from ones.views import public

    return _ones_call(public)


@app.get("/internal/ones/constellation", dependencies=[Depends(require_token)])
def ones_constellation() -> JSONResponse:
    from ones.views import constellation

    return _ones_call(constellation)


@app.get("/internal/ones/leaderboard/{user_id}", dependencies=[Depends(require_token)])
def ones_leaderboard(user_id: str) -> JSONResponse:
    from ones.views import leaderboard

    with connect(autocommit=True) as conn:
        out = leaderboard(conn, user_id)
    if out is None:
        return JSONResponse({"error": "ones_only"}, status_code=403)
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@app.get("/internal/me/{user_id}/one", dependencies=[Depends(require_token)])
def me_one(user_id: str) -> JSONResponse:
    from ones.views import my_one

    with connect(autocommit=True) as conn:
        return JSONResponse({"one": my_one(conn, user_id)}, headers={"Cache-Control": "no-store"})


@app.post("/internal/me/{user_id}/one/number", dependencies=[Depends(require_token)])
def me_one_number(user_id: str, body: dict[str, Any]) -> JSONResponse:
    from ones.service import swap_number

    return _ones_call(swap_number, user_id, body.get("number"))


@app.post("/internal/me/{user_id}/one/brief", dependencies=[Depends(require_token)])
def me_one_brief(user_id: str, body: dict[str, Any]) -> JSONResponse:
    from ones.service import propose_brief

    return _ones_call(propose_brief, user_id, body.get("text"), status=201)


@app.post("/internal/me/{user_id}/one/glow-up/{glow_id}/seen", dependencies=[Depends(require_token)])
def me_one_glow_seen(user_id: str, glow_id: int) -> JSONResponse:
    from ones.service import glow_up_seen

    with connect(autocommit=True) as conn:
        return JSONResponse({"ok": glow_up_seen(conn, user_id, glow_id)})


@app.get("/internal/me/{user_id}/one/showcase", dependencies=[Depends(require_token)])
def me_one_showcase(user_id: str) -> JSONResponse:
    from ones.views import showcase_for_user

    with connect(autocommit=True) as conn:
        out = showcase_for_user(conn, user_id)
    if out is None:
        return JSONResponse({"error": "not_a_one"}, status_code=403)
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@app.put("/internal/me/{user_id}/one/showcase", dependencies=[Depends(require_token)])
def me_one_showcase_save(user_id: str, body: dict[str, Any]) -> JSONResponse:
    from ones.service import save_showcase

    return _ones_call(save_showcase, user_id, body)


@app.get("/internal/me/{user_id}/team", dependencies=[Depends(require_token)])
def me_team(user_id: str) -> JSONResponse:
    from ones.views import team

    return _ones_call(team, user_id)


# ---- weekly clustering (§4.4 B) -------------------------------------------------------------------------------


@app.post("/internal/cluster-runs", dependencies=[Depends(require_token)])
def cluster_run_now(body: dict[str, Any]) -> JSONResponse:
    """The desk asks for a run now (the web app checked `approve_cluster_proposals` and the `clusters.batch`
    switch). The run itself is a job, so the request returns at once."""
    from core import killswitch

    user = str(body.get("user_id") or "")
    with connect(autocommit=True) as conn:
        if not killswitch.is_on("clusters.batch", conn):
            return JSONResponse({"error": "switched_off"}, status_code=503)
        busy = conn.execute(
            "SELECT 1 FROM jobs WHERE type = 'cluster.batch' AND state IN ('queued', 'running') LIMIT 1"
        ).fetchone()
        if busy:
            return JSONResponse({"error": "run_in_progress"}, status_code=409)
        row = conn.execute(
            "INSERT INTO jobs (type, payload, dedupe_key) VALUES ('cluster.batch', %s, 'cluster.batch:manual') "
            "ON CONFLICT DO NOTHING RETURNING id",
            (Jsonb({"manual_by": user}),),
        ).fetchone()
        if row is None:
            return JSONResponse({"error": "run_in_progress"}, status_code=409)
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity) VALUES (%s, 'cluster.run_requested', 'cluster_runs')",
            (f"user:{user}",),
        )
    return JSONResponse({"job_id": row["id"] if row else None}, status_code=202)


@app.get("/internal/cluster-runs", dependencies=[Depends(require_token)])
def cluster_runs_list() -> JSONResponse:
    from cluster.view import runs

    with connect(autocommit=True) as conn:
        return JSONResponse(runs(conn), headers={"Cache-Control": "no-store"})


@app.get("/internal/cluster-proposals/{item_id}/view", dependencies=[Depends(require_token)])
def cluster_proposal_view(item_id: int, mode: str = "neutral") -> JSONResponse:
    from cluster.view import proposal_view

    if mode not in ("real", "neutral"):
        return JSONResponse({"error": "bad_mode"}, status_code=400)
    with connect(autocommit=True) as conn:
        body = proposal_view(conn, item_id, "real" if mode == "real" else "neutral")
    if body is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@app.post("/internal/cluster-proposals/{item_id}/action", dependencies=[Depends(require_token)])
def cluster_proposal_action(item_id: int, body: dict[str, Any]) -> JSONResponse:
    """Approve, remove a member or reject (the web app checked `approve_cluster_proposals`)."""
    from cluster.proposals import act

    return _review_call(act, item_id, str(body.get("reviewer_user_id") or ""), body)


# --- Delivery (§4.8 to §4.11), lenses (§4.14) and learning (§5). The web checks the capability and passes who is
# acting; the worker checks each person's part in the delivery again. Refusals answer with a code only.


def _delivery_call(fn: Any, *args: Any, status: int = 200) -> JSONResponse:
    from gateway import AgentFailed
    from ones.text import OnesRefused

    with connect(autocommit=True) as conn:
        try:
            return JSONResponse(fn(conn, *args), status_code=status, headers={"Cache-Control": "no-store"})
        except OnesRefused as exc:
            code, _, rest = exc.code.partition(":")
            body: dict[str, Any] = {"error": code}
            if rest:
                body["missing"] = rest.split(",")
            return JSONResponse(body, status_code=exc.status)
        except AgentFailed as exc:
            return JSONResponse({"error": "checks_unavailable", "code": exc.code}, status_code=503)


@app.get("/internal/delivery/console/{user_id}", dependencies=[Depends(require_token)])
def delivery_console(user_id: str) -> JSONResponse:
    from delivery.views import console

    return _delivery_call(console, user_id)


@app.post("/internal/delivery", dependencies=[Depends(require_token)])
def delivery_start(body: dict[str, Any]) -> JSONResponse:
    from delivery.service import start

    return _delivery_call(start, _actor(body), body, status=201)


@app.get("/internal/delivery/{delivery_id}/view/{user_id}", dependencies=[Depends(require_token)])
def delivery_view(delivery_id: str, user_id: str) -> JSONResponse:
    from delivery.views import detail

    with connect(autocommit=True) as conn:
        out = detail(conn, user_id, delivery_id)
    if out is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@app.put("/internal/delivery/{delivery_id}/pack", dependencies=[Depends(require_token)])
def delivery_pack(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import save_pack

    return _delivery_call(save_pack, _actor(body), delivery_id, body)


@app.post("/internal/delivery/{delivery_id}/submit", dependencies=[Depends(require_token)])
def delivery_submit(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import submit

    return _delivery_call(submit, _actor(body), delivery_id)


@app.post("/internal/delivery/{delivery_id}/approve", dependencies=[Depends(require_token)])
def delivery_approve(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import approve

    return _delivery_call(approve, _actor(body), delivery_id)


@app.post("/internal/delivery/{delivery_id}/send-back", dependencies=[Depends(require_token)])
def delivery_send_back(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import send_back

    return _delivery_call(send_back, _actor(body), delivery_id)


@app.post("/internal/delivery/{delivery_id}/link", dependencies=[Depends(require_token)])
def delivery_link(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import link_page

    return _delivery_call(link_page, _actor(body), delivery_id, body)


@app.post("/internal/delivery/{delivery_id}/phase", dependencies=[Depends(require_token)])
def delivery_phase(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import set_phase

    return _delivery_call(set_phase, _actor(body), delivery_id, body)


@app.post("/internal/delivery/{delivery_id}/milestones", dependencies=[Depends(require_token)])
def delivery_milestone_add(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import add_milestone

    return _delivery_call(add_milestone, _actor(body), delivery_id, body, status=201)


@app.post("/internal/delivery/{delivery_id}/milestones/{milestone_id}", dependencies=[Depends(require_token)])
def delivery_milestone_set(delivery_id: str, milestone_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import set_milestone

    return _delivery_call(set_milestone, _actor(body), delivery_id, milestone_id, body)


@app.post("/internal/delivery/{delivery_id}/complete", dependencies=[Depends(require_token)])
def delivery_complete(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import complete_fix

    return _delivery_call(complete_fix, _actor(body), delivery_id, body)


@app.post("/internal/delivery/{delivery_id}/approve-completion", dependencies=[Depends(require_token)])
def delivery_approve_completion(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import approve_completion

    return _delivery_call(approve_completion, _actor(body), delivery_id)


@app.put("/internal/delivery/{delivery_id}/measurements/{mark}", dependencies=[Depends(require_token)])
def delivery_measure_fill(delivery_id: str, mark: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import fill

    return _delivery_call(fill, _actor(body), delivery_id, mark, body)


@app.post(
    "/internal/delivery/{delivery_id}/measurements/{mark}/confirm", dependencies=[Depends(require_token)]
)
def delivery_measure_confirm(delivery_id: str, mark: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import confirm

    return _delivery_call(confirm, _actor(body), delivery_id, mark)


@app.post(
    "/internal/delivery/{delivery_id}/measurements/{mark}/finance", dependencies=[Depends(require_token)]
)
def delivery_measure_finance(delivery_id: str, mark: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.service import finance_confirm

    return _delivery_call(finance_confirm, _actor(body), delivery_id, mark)


@app.post("/internal/delivery/{delivery_id}/evidence", dependencies=[Depends(require_token)])
def delivery_evidence_add(delivery_id: str, file: UploadFile, actor_user_id: str = Form(...)) -> JSONResponse:
    """An evidence file (BLD-131): the owner or an admin; the same checks as research files, then quarantine."""
    from delivery.extras import add_evidence

    limit = attachments.limits().max_bytes_each
    data = file.file.read(limit + 1)
    return _delivery_call(add_evidence, actor_user_id, delivery_id, file.filename or "file", data, status=201)


@app.get(
    "/internal/delivery/{delivery_id}/evidence/{att_id}/content/{user_id}",
    dependencies=[Depends(require_token)],
)
def delivery_evidence_content(delivery_id: str, att_id: str, user_id: str) -> Response:
    """A clean evidence file for someone who can see the delivery; anything not clean is refused."""
    from delivery.extras import evidence_content
    from ones.text import OnesRefused

    try:
        with connect(autocommit=True) as conn:
            data, mime, _name = evidence_content(conn, user_id, delivery_id, att_id)
    except OnesRefused as exc:
        return JSONResponse({"error": exc.code}, status_code=exc.status)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "no-store"})


@app.post("/internal/delivery/{delivery_id}/evidence/{att_id}/remove", dependencies=[Depends(require_token)])
def delivery_evidence_remove(delivery_id: str, att_id: str, body: dict[str, Any]) -> JSONResponse:
    from delivery.extras import remove_evidence

    return _delivery_call(remove_evidence, _actor(body), delivery_id, att_id)


@app.post("/internal/delivery/{delivery_id}/checkin", dependencies=[Depends(require_token)])
def delivery_checkin(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    """The fix track's Friday check-in, answered on the page (BLD-132)."""
    from delivery.extras import check_in

    return _delivery_call(check_in, _actor(body), delivery_id, body)


@app.post("/internal/delivery/{delivery_id}/pack-draft", dependencies=[Depends(require_token)])
def delivery_pack_draft(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    """The handover-draft agent proposes the pack's fields; nothing is saved (BLD-138)."""
    from delivery.pack_draft import draft

    return _delivery_call(draft, _actor(body), delivery_id)


@app.put("/internal/delivery/{delivery_id}/writeup", dependencies=[Depends(require_token)])
def delivery_writeup_save(delivery_id: str, body: dict[str, Any]) -> JSONResponse:
    """The owner drafts the write-up other teams can adopt (BLD-133); every part is checked before it is kept."""
    from delivery.writeups import save

    return _delivery_call(save, _actor(body), delivery_id, body)


@app.post("/internal/delivery/{delivery_id}/writeup/{step}", dependencies=[Depends(require_token)])
def delivery_writeup_step(delivery_id: str, step: str, body: dict[str, Any]) -> JSONResponse:
    """Submit (owner), approve or send back (the named sponsor, never the submitter) (BLD-133)."""
    from delivery import writeups

    steps = {"submit": writeups.submit, "approve": writeups.approve, "send-back": writeups.send_back}
    if step not in steps:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _delivery_call(steps[step], _actor(body), delivery_id)


@app.get("/internal/lenses/{user_id}", dependencies=[Depends(require_token)])
def lenses_view(user_id: str) -> JSONResponse:
    from lenses import view

    return _delivery_call(view, user_id)


@app.post("/internal/lenses/rebuild", dependencies=[Depends(require_token)])
def lenses_rebuild(body: dict[str, Any]) -> JSONResponse:
    from lenses import rebuild

    return _delivery_call(rebuild, _actor(body))


@app.get("/internal/learning/{user_id}", dependencies=[Depends(require_token)])
def learning_view(user_id: str) -> JSONResponse:
    from learning.run import view

    return _delivery_call(view, user_id)


@app.get("/internal/learning/committee/{user_id}", dependencies=[Depends(require_token)])
def learning_committee_view(user_id: str) -> JSONResponse:
    """The core committee's learning page: agreement, what it rewards, scoring bands (§5.9, BLD-149, BLD-150)."""
    from learning.decisions import view

    return _delivery_call(view, user_id)


@app.post("/internal/learning/proposals/{proposal_id}/decide", dependencies=[Depends(require_token)])
def learning_decide(proposal_id: str, body: dict[str, Any]) -> JSONResponse:
    """The product team decides terms and tags; the chair or the core committee decides committee proposals."""
    from learning.proposals import decide

    return _delivery_call(decide, _actor(body), proposal_id, body)


@app.post("/internal/learning/proposals/{proposal_id}/publish", dependencies=[Depends(require_token)])
def learning_publish(proposal_id: str, body: dict[str, Any]) -> JSONResponse:
    """An admin writes an approved term or tag into the company repo, through the outbox (BLD-136)."""
    from learning.proposals import publish

    return _delivery_call(publish, _actor(body), proposal_id, body)


@app.post("/internal/learning/role-themes/{theme_id}/decide", dependencies=[Depends(require_token)])
def learning_role_themes_decide(theme_id: str, body: dict[str, Any]) -> JSONResponse:
    """The product team approves or declines a role's friction themes (BLD-139)."""
    from learning.role_themes import decide

    return _delivery_call(decide, _actor(body), theme_id, body)


@app.post("/internal/learning/run", dependencies=[Depends(require_token)])
def learning_run(body: dict[str, Any]) -> JSONResponse:
    from learning.run import run_now

    return _delivery_call(run_now, _actor(body), body)


# ---- committee flow (§4.5–§4.7) -----------------------------------------------------------------------------------
# The web app has checked the capability for the route; these handlers check the chair, the roster, the
# cluster's contributors and conflicts of interest, and keep sealed scores and assessments sealed.


def _json(body: Any) -> JSONResponse:
    if body is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@app.get("/internal/qualify/{item_id}", dependencies=[Depends(require_token)])
def qualify_view_route(item_id: int, user_id: str = "", mode: str = "real") -> JSONResponse:
    from committee.views import qualify_view

    with connect(autocommit=True) as conn:
        return _json(qualify_view(conn, item_id, "real" if mode == "real" else "neutral"))


@app.post("/internal/qualify/{item_id}/action", dependencies=[Depends(require_token)])
def qualify_action(item_id: int, body: dict[str, Any]) -> JSONResponse:
    from committee.qualify import act

    return _review_call(act, item_id, str(body.get("reviewer_user_id") or ""), body)


@app.get("/internal/committee/rounds", dependencies=[Depends(require_token)])
def committee_rounds(user_id: str) -> JSONResponse:
    from committee.rounds import is_chair, presentations_for, rounds_for

    with connect(autocommit=True) as conn:
        return _json({"rounds": rounds_for(conn, user_id), "chair": is_chair(conn, user_id),
                      "presentations": presentations_for(conn, user_id)})  # fmt: skip


@app.get("/internal/committee/rounds/{round_id}", dependencies=[Depends(require_token)])
def committee_round(round_id: str, user_id: str) -> JSONResponse:
    from committee.rounds import round_view

    with connect(autocommit=True) as conn:
        return _json(round_view(conn, round_id, user_id))


@app.post("/internal/committee/rounds/{round_id}/action", dependencies=[Depends(require_token)])
def committee_round_action(round_id: str, body: dict[str, Any]) -> JSONResponse:
    from committee.rounds import act

    return _review_call(act, round_id, str(body.get("user_id") or ""), body)


@app.get("/internal/committee/conflicts", dependencies=[Depends(require_token)])
def committee_conflicts(user_id: str) -> JSONResponse:
    """Manager flags waiting for an admin (BLD-221); the round action `clear_conflict` clears one."""
    from committee.rounds import open_flags

    with connect(autocommit=True) as conn:
        flags = open_flags(conn, user_id)
    if flags is None:
        return JSONResponse({"error": "admin_only"}, status_code=403)
    return _json({"flags": flags})


@app.post("/internal/committee/cycles", dependencies=[Depends(require_token)])
def committee_cycle(body: dict[str, Any]) -> JSONResponse:
    from committee.rounds import open_cycle

    return _review_call(open_cycle, str(body.get("user_id") or ""), body)


@app.get("/internal/committee/presentations/{pid}", dependencies=[Depends(require_token)])
def committee_presentation(pid: str, user_id: str) -> JSONResponse:
    from committee.decide import committee_view

    with connect(autocommit=True) as conn:
        return _json(committee_view(conn, pid, user_id))


@app.post("/internal/committee/presentations/{pid}/action", dependencies=[Depends(require_token)])
def committee_presentation_action(pid: str, body: dict[str, Any]) -> JSONResponse:
    from committee.decide import committee_act

    return _review_call(committee_act, pid, str(body.get("user_id") or ""), body)


@app.get("/internal/presentations/{pid}", dependencies=[Depends(require_token)])
def contributor_presentation(pid: str, user_id: str) -> JSONResponse:
    from committee.decide import contributor_view

    with connect(autocommit=True) as conn:
        return _json(contributor_view(conn, pid, user_id))


@app.post("/internal/presentations/{pid}/action", dependencies=[Depends(require_token)])
def contributor_presentation_action(pid: str, body: dict[str, Any]) -> JSONResponse:
    from committee.decide import contributor_act

    return _review_call(contributor_act, pid, str(body.get("user_id") or ""), body)


@app.get("/internal/working-groups/{wg}", dependencies=[Depends(require_token)])
def working_group_view(wg: str, user_id: str) -> JSONResponse:
    from committee.views import working_group

    with connect(autocommit=True) as conn:
        return _json(working_group(conn, wg, user_id))


# ---- appeals (§4.12) and reports (§3.8, §5.4) ---------------------------------------------------------------------


@app.get("/internal/appeals", dependencies=[Depends(require_token)])
def appeals_mine(user_id: str) -> JSONResponse:
    from committee.appeals import mine, panel_list

    with connect(autocommit=True) as conn:
        return _json({"decisions": mine(conn, user_id), "panel": panel_list(conn, user_id)})


@app.post("/internal/appeals", dependencies=[Depends(require_token)])
def appeals_file(body: dict[str, Any]) -> JSONResponse:
    from committee.appeals import file

    return _review_call(file, str(body.get("user_id") or ""), body)


@app.get("/internal/appeals/{aid}", dependencies=[Depends(require_token)])
def appeals_view(aid: str, user_id: str) -> JSONResponse:
    from committee.appeals import panel_view

    with connect(autocommit=True) as conn:
        return _json(panel_view(conn, aid, user_id))


@app.post("/internal/appeals/{aid}/decision", dependencies=[Depends(require_token)])
def appeals_decide(aid: str, body: dict[str, Any]) -> JSONResponse:
    from committee.appeals import decide

    return _review_call(decide, aid, str(body.get("user_id") or ""), body)


@app.get("/internal/reports/{kind}", dependencies=[Depends(require_token)])
def reports_view(kind: str, user_id: str, quarter: str | None = None) -> JSONResponse:
    """Fairness or calibration for a whole quarter (§3.8, §5.4); the web app checked `view_fairness_reports`.
    Each view is written to the audit log."""
    from psycopg.types.json import Jsonb

    from committee import reports

    if kind not in ("fairness", "calibration"):
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        frm, to = reports.period(quarter)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    with connect(autocommit=True) as conn:
        body = reports.fairness(conn, frm, to) if kind == "fairness" else reports.calibration(conn, frm, to)
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'report.viewed', %s, %s)",
            (f"user:{user_id}", f"report:{kind}", Jsonb({"quarter": quarter or reports.current_quarter()})),
        )
    body["quarter"] = quarter or reports.current_quarter()
    body["quarters"] = reports.recent_quarters()
    return _json(body)
