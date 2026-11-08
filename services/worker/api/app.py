"""FastAPI app for `/internal/*` (§8). Health and index trigger in B1; scan arrives in B4."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.db import connect
from core.logging import get_logger
from index.indexer import Indexer

log = get_logger("api")
app = FastAPI(title="kfin-ideas worker", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/internal/health")
def health() -> dict[str, Any]:
    try:
        with connect(autocommit=True) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        log.error("health.db_unreachable", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="database unreachable") from None
    return {"status": "ok", "roles": sorted(get_settings().roles)}


@app.post("/internal/index")
def index_now() -> dict[str, Any]:
    result = Indexer().run_once()
    return {"commit": result.to_commit, "upserted": len(result.upserted), "deleted": len(result.deleted)}


@app.post("/internal/scan")
def scan() -> JSONResponse:
    return JSONResponse({"error": "not_built", "block": "B4"}, status_code=501)


@app.post("/hooks/git-post-commit")
def post_commit() -> dict[str, Any]:
    return index_now()
