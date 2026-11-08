"""Postgres access with psycopg 3. Rows come back as dicts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from core.config import get_settings

Row = dict[str, Any]
Conn = psycopg.Connection[Row]


def connect(database_url: str | None = None, *, autocommit: bool = False) -> Conn:
    url = database_url or get_settings().database_url
    return psycopg.connect(url, row_factory=dict_row, autocommit=autocommit)


@contextmanager
def transaction(database_url: str | None = None) -> Iterator[Conn]:
    """One connection, one transaction: commit on success, roll back on any error."""
    conn = connect(database_url)
    try:
        with conn.transaction():
            yield conn
    finally:
        conn.close()


def vector_literal(values: list[float]) -> str:
    """pgvector text form, for `%s::vector` parameters."""
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
