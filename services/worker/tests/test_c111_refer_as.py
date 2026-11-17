"""BLD-C111 (DEC-108 (3), BLD-E010): how the person wants to be referred to. The unit tests need no stack; the API
tests (marked stack) run GET and PUT /api/me/refer-as against the running web app and read the same value as the
worker does."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from speech import prefs


@pytest.mark.parametrize(
    ("choice", "gender"), [("she", "Female"), ("he", "Male"), ("they", None), (None, None)]
)
def test_BLD_C111_only_she_or_he_sends_a_gender_to_the_translation(
    choice: str | None, gender: str | None
) -> None:
    assert prefs.speaker_gender(choice) == gender


def test_BLD_C111_wire_values_are_she_he_they_or_unset() -> None:
    assert [prefs.parse(v) for v in ("she", "he", "they", "unset", None)] == ["she", "he", "they", None, None]
    for bad in ("She", "her", "female", "", 1, True):  # "" is refused, as the route refuses it
        with pytest.raises(prefs.ReferAsInvalid):
            prefs.parse(bad)
    assert prefs.wire(None) == "unset" and prefs.wire("they") == "they" and prefs.wire("x") == "unset"


class _Conn:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.sql: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        self.sql.append((sql, params))
        return self

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


def test_BLD_C111_the_worker_reads_the_choice_or_none() -> None:
    assert prefs.refer_as(_Conn({"refer_as": "she"}), "u1") == "she"  # type: ignore[arg-type]
    assert prefs.refer_as(_Conn({"refer_as": None}), "u1") is None  # type: ignore[arg-type]
    assert prefs.refer_as(_Conn(None), "u1") is None  # type: ignore[arg-type]
    assert prefs.refer_as(_Conn({"refer_as": "she"}), None) is None  # type: ignore[arg-type]


def test_BLD_C111_setting_it_is_an_upsert_and_unset_stores_null() -> None:
    conn = _Conn(None)
    assert prefs.set_refer_as(conn, "u1", "unset") == "unset"  # type: ignore[arg-type]
    sql, params = conn.sql[0]
    assert "ON CONFLICT (user_id) DO UPDATE" in sql and params == ("u1", None)


# ---- the API, against the running stack --------------------------------------------------------------------


@pytest.fixture
def dev_db() -> Iterator[Any]:
    from core.db import connect

    with connect(autocommit=True) as conn:
        yield conn


@pytest.mark.stack
def test_BLD_C111_get_and_put_api_me_refer_as(dev_db: Any) -> None:
    from tests.web import people

    with people(dev_db) as make:
        person = make()
        b = person.browser()
        assert b.get("/api/me/refer-as").json() == {"refer_as": "unset"}
        for value in ("she", "he", "they", "unset"):
            r = b.put("/api/me/refer-as", json={"refer_as": value})
            assert r.status_code == 200 and r.json() == {"refer_as": value}
            assert b.get("/api/me/refer-as").json() == {"refer_as": value}
        b.put("/api/me/refer-as", json={"refer_as": "she"})
        assert prefs.refer_as(dev_db, person.user_id) == "she"  # what the translation reads
        assert b.put("/api/me/refer-as", json={"refer_as": None}).json() == {"refer_as": "unset"}
        r = b.put("/api/me/refer-as", json={"refer_as": "female"})
        assert r.status_code == 400 and r.json() == {"error": "refer_as_invalid"}
        assert prefs.refer_as(dev_db, person.user_id) is None


@pytest.mark.stack
def test_BLD_C111_the_column_takes_only_the_three_choices(dev_db: Any) -> None:
    import psycopg

    from tests.web import people

    with people(dev_db) as make:
        person = make()
        with pytest.raises(psycopg.errors.CheckViolation):
            dev_db.execute(
                "INSERT INTO person_settings (user_id, refer_as) VALUES (%s, 'her') "
                "ON CONFLICT (user_id) DO UPDATE SET refer_as = 'her'",
                (person.user_id,),
            )
