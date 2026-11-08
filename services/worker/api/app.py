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
async def upload_attachment(
    file: UploadFile, idea_uuid: str = Form(...), uploaded_by_code: str = Form(...)
) -> JSONResponse:
    limit = attachments.limits().max_bytes_each
    data = await file.read(limit + 1)
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
