"""`/internal/drafts`: the worker side of A-API.drafts and A-API.draft-stream (L-DRAFT, BLD-C071). The web app has
checked the session and the capability, and vouches for who the person is (user id and contributor code) and which
device asks; the worker checks that the draft is theirs. Unmasked words leave here only to their owner (DEC-103):
they are sealed in a table the web role cannot read.

Runs start after the commit, off the request (`runs.dispatch`), so a message is answered at once (202) and its
parts arrive on the stream.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from core.db import connect
from core.logging import get_logger
from draft import runs, store
from draft.store import Device, DraftError, Owner

log = get_logger("api.drafts")
router = APIRouter(prefix="/internal/drafts")
NO_STORE = {"Cache-Control": "no-store"}


def _json(body: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=NO_STORE)


def _call(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except DraftError as exc:
        return _json(exc.body(), exc.status)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _owner(data: dict[str, Any]) -> Owner:
    owner = _dict(data.get("owner"))
    return Owner(str(owner.get("user_id") or ""), str(owner.get("code") or ""))


def _device(data: dict[str, Any]) -> Device:
    d = _dict(data.get("device"))
    return Device.of(d.get("kind"), d.get("id"))


def _query_owner(request: Request) -> tuple[Owner, Device]:
    q = request.query_params
    return Owner(q.get("user_id", ""), q.get("code", "")), Device.of(q.get("device_kind"), q.get("device_id"))


def _files(data: dict[str, Any]) -> list[str]:
    value = data.get("files")
    return [f for f in value if isinstance(f, str)] if isinstance(value, list) else []


def _at(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        at = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else None


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@router.post("")
async def create(request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        owner, device = _owner(data), _device(data)
        with connect(autocommit=True) as conn:
            idea_uuid, run_id = store.create(
                conn,
                owner,
                device,
                channel=str(data.get("channel") or "web"),
                text=data.get("text") if isinstance(data.get("text"), str) else None,
                text_en=data.get("text_en") if isinstance(data.get("text_en"), str) else None,
                via=str(data.get("via") or "typed"),
                idempotency_key=data.get("idempotency_key") or None,
                client_id=data.get("client_id") or None,
                files=_files(data),
            )
            runs.dispatch(run_id)
            return _json({"draft": store.view(conn, owner, idea_uuid, device), "run_id": run_id}, 201)

    return await _threaded(go)


async def _threaded(fn: Callable[[], Response]) -> Response:
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(_call, fn)


@router.get("")
def recent(request: Request) -> Response:
    def go() -> Response:
        owner, device = _query_owner(request)
        with connect(autocommit=True) as conn:
            archived = request.query_params.get("archived") in ("1", "true")
            return _json(store.recent(conn, owner, device, archived=archived))

    return _call(go)  # type: ignore[no-any-return]


@router.get("/{idea_uuid}")
def get_draft(idea_uuid: str, request: Request) -> Response:
    def go() -> Response:
        owner, device = _query_owner(request)
        with connect(autocommit=True) as conn:
            open_ = request.query_params.get("open") in ("1", "true")
            return _json(store.view(conn, owner, idea_uuid, device, open_=open_))

    return _call(go)  # type: ignore[no-any-return]


@router.get("/{idea_uuid}/live")
def live(idea_uuid: str, request: Request) -> Response:
    def go() -> Response:
        owner, _ = _query_owner(request)
        with connect(autocommit=True) as conn:
            return _json(store.live(conn, owner, idea_uuid, request.query_params.get("run_id")))

    return _call(go)  # type: ignore[no-any-return]


@router.patch("/{idea_uuid}")
async def save_step(idea_uuid: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        with connect(autocommit=True) as conn:
            return _json(store.save_step(conn, _owner(data), idea_uuid, _device(data), data.get("step")))

    return await _threaded(go)


@router.post("/{idea_uuid}/archive")
async def archive(idea_uuid: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        with connect(autocommit=True) as conn:
            store.archive(conn, _owner(data), idea_uuid)
        return Response(status_code=204, headers=NO_STORE)

    return await _threaded(go)


@router.post("/{idea_uuid}/restore")
async def restore(idea_uuid: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        owner, device = _owner(data), _device(data)
        with connect(autocommit=True) as conn:
            store.restore_draft(conn, owner, idea_uuid, device)
            return _json(store.view(conn, owner, idea_uuid, device))

    return await _threaded(go)


@router.post("/{idea_uuid}/messages")
async def add_message(idea_uuid: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        owner, device = _owner(data), _device(data)
        with connect(autocommit=True) as conn:
            mid, run_id = store.add_message(
                conn,
                owner,
                idea_uuid,
                device,
                text=data.get("text"),
                via=str(data.get("via") or "typed"),
                text_en=data.get("text_en"),
                client_id=data.get("client_id") or None,
                at=_at(data.get("at")),
                defer_run=data.get("defer_run") is True,
                files=_files(data),
                stream_id=data.get("stream_id") if isinstance(data.get("stream_id"), str) else None,
            )
            runs.dispatch(run_id)
            draft = store.view(conn, owner, idea_uuid, device)
        message = next((m for m in draft["messages"] if m["id"] == mid), None)
        return _json({"run_id": run_id, "message": message, "draft": draft}, 202)

    return await _threaded(go)


@router.patch("/{idea_uuid}/messages/{message_id}")
async def edit_message(idea_uuid: str, message_id: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        owner, device = _owner(data), _device(data)
        with connect(autocommit=True) as conn:
            mid, run_id = store.edit_message(
                conn, owner, idea_uuid, message_id, device, text=data.get("text"), text_en=data.get("text_en")
            )
            runs.dispatch(run_id)
            draft = store.view(conn, owner, idea_uuid, device)
        message = next((m for m in draft["messages"] if m["id"] == mid), None)
        return _json({"run_id": run_id, "message": message, "draft": draft}, 202)

    return await _threaded(go)


@router.patch("/{idea_uuid}/parts/{part}")
async def set_part(idea_uuid: str, part: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        owner, device = _owner(data), _device(data)
        body: dict[str, Any] = {k: data[k] for k in ("value", "pinned") if k in data}
        with connect(autocommit=True) as conn:
            run_id = store.set_part(conn, owner, idea_uuid, part, device, body)
            runs.dispatch(run_id)
            return _json({"run_id": run_id, "draft": store.view(conn, owner, idea_uuid, device)})

    return await _threaded(go)


@router.post("/{idea_uuid}/runs")
async def build(idea_uuid: str, request: Request) -> Response:
    data = await _body(request)

    def go() -> Response:
        with connect(autocommit=True) as conn:
            run_id = store.build(conn, _owner(data), idea_uuid, _device(data))
        runs.dispatch(run_id)
        return _json({"run_id": run_id}, 202)

    return await _threaded(go)


@router.post("/intake")
async def intake(request: Request) -> Response:
    """L-DRAFT.channels (BLD-C077): the 1% Club mailbox reader or the Teams app hands over one arrival. Off until
    IT gives them (`intake.email`, `intake.teams`; DEC-105), and while `submissions` is off: then 503, and the caller
    keeps the message. A note with no words is a bounce the caller sends on (`empty_message`, BLD-C037)."""
    from draft.channels import Arrival, ChannelOff
    from draft.channels import intake as take

    data = await _body(request)

    def go() -> Response:
        received = _at(data.get("received_at"))
        note = data.get("note") if data.get("note") is not None else ""  # a forward with nothing on top
        if received is None or not isinstance(note, str) or not isinstance(data.get("sender"), str):
            return _json({"error": "arrival_invalid"}, 400)
        arrival = Arrival(
            channel=str(data.get("channel") or ""),
            sender=data["sender"],
            note=note,
            received_at=received,
            subject=data.get("subject") if isinstance(data.get("subject"), str) else None,
            thread=data.get("thread") if isinstance(data.get("thread"), str) else None,
            note_en=data.get("note_en") if isinstance(data.get("note_en"), str) else None,
        )
        with connect(autocommit=True) as conn:
            try:
                out = take(conn, arrival)
            except ChannelOff as off:
                return _json({"error": "channel_off", "switch": str(off)}, 503)
        runs.dispatch(out.get("run_id"))
        return _json(out, 202 if "draft_id" in out else 200)

    return await _threaded(go)
