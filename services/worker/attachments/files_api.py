"""Internal routes for files and links (A-API.files; lane C). Included by `api/app.py` behind the internal token. The
web app has checked the capability and passes the signed-in person as `user_id`; the worker decides what that person
may do with this file (`attachments.files.rights`). Errors are the pack's shape, `{error: {code, message}}`; they
never carry a file name, a link or anything read from a file (non-negotiable 3)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import JSONResponse, Response

from attachments import files
from core.db import connect

router = APIRouter()
NO_STORE = {"Cache-Control": "no-store"}


def _call(status: int, fn: Any, *args: Any, **kwargs: Any) -> Response:
    try:
        with connect(autocommit=True) as conn:
            body = fn(conn, *args, **kwargs)
    except files.FileRefused as exc:
        return JSONResponse(exc.body(), status_code=exc.status, headers=NO_STORE)
    if body is None:
        return Response(status_code=204, headers=NO_STORE)
    return JSONResponse(body, status_code=status, headers=NO_STORE)


def _target(body: dict[str, Any]) -> dict[str, str | None]:
    return {k: (str(body[k]) if isinstance(body.get(k), str) and body[k] else None)
            for k in ("draft_id", "idea_id", "answer_id")}  # fmt: skip


@router.get("/internal/files/config")
def upload_config() -> JSONResponse:
    """A-API.files `GET /config/uploads`: the one limit, the type list and the help line rendered from them."""
    return JSONResponse(files.uploads().as_json(), headers=NO_STORE)


@router.post("/internal/files")
def add_file(
    file: UploadFile,
    user_id: str = Form(...),
    draft_id: str | None = Form(None),
    idea_id: str | None = Form(None),
    answer_id: str | None = Form(None),
) -> Response:
    """`POST /files` (multipart). A plain def: FastAPI runs it in a thread, so the store and database never block."""
    data = file.file.read(files.uploads().limit_bytes + 1)
    return _call(
        201, files.accept, user_id=user_id, name=file.filename or "file", data=data,
        **_target({"draft_id": draft_id, "idea_id": idea_id, "answer_id": answer_id}),
    )  # fmt: skip


@router.post("/internal/links")
def add_link(body: dict[str, Any]) -> Response:
    """`POST /links` `{ url, draft_id | idea_id | answer_id, user_id }`. The address is never fetched."""
    url = body.get("url")
    return _call(
        201, files.accept_link, user_id=str(body.get("user_id") or ""),
        url=url if isinstance(url, str) else "", **_target(body),
    )  # fmt: skip


@router.get("/internal/files/{att_id}")
def get_file(att_id: str, user_id: str = "") -> Response:
    return _call(200, files.get_item, att_id, user_id)


@router.get("/internal/files/{att_id}/content")
def file_content(att_id: str, user_id: str = "") -> Response:
    """The stored copy for `GET /files/:id/view`, once `rights` allows this person to open it."""
    try:
        with connect(autocommit=True) as conn:
            data, mime, name = files.content(conn, att_id, user_id)
    except files.FileRefused as exc:
        return JSONResponse(exc.body(), status_code=exc.status, headers=NO_STORE)
    # The shown (masked) name, percent-encoded, so the web app can name the download without a second read.
    return Response(content=data, media_type=mime, headers={**NO_STORE, "X-File-Name": quote(name, safe="")})


@router.post("/internal/files/{att_id}/retry")
def retry_file(att_id: str, user_id: str = "") -> Response:
    return _call(200, files.retry, att_id, user_id)


@router.post("/internal/files/{att_id}/hide")
def hide_file(att_id: str, user_id: str = "") -> Response:
    return _call(200, files.hide_for_me, att_id, user_id)


@router.delete("/internal/files/{att_id}")
def remove_file(att_id: str, user_id: str = "") -> Response:
    return _call(204, files.remove, att_id, user_id)
