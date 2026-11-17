"""How the person wants to be referred to (DEC-108 (3), BLD-E010, BLD-C111): she, he, they, or unset.

Asked once in Profile (S-H6, lane E): "How should we refer to you?", with "Prefer not to say". Stored in
`person_settings.refer_as` (NULL when unset). The worker reads it only to translate the person's own voice notes:
mayura:v1 gets `speaker_gender` only for she or he; they and unset send nothing, so the wording stays neutral. The
value is never logged and never shown to anyone else.
"""

from __future__ import annotations

from typing import Literal

from core.db import Conn

ReferAs = Literal["she", "he", "they"]
CHOICES: tuple[str, ...] = ("she", "he", "they")
UNSET = "unset"  # the wire value for "Prefer not to say" or never asked; NULL in the table
_GENDER = {"she": "Female", "he": "Male"}


class ReferAsInvalid(ValueError):
    """Not one of she, he, they or unset."""


def parse(value: object) -> str | None:
    """A wire value to what is stored: she, he or they, or None for unset (also None or "")."""
    if value is None or value == "" or value == UNSET:
        return None
    if isinstance(value, str) and value in CHOICES:
        return value
    raise ReferAsInvalid("refer_as_invalid")


def wire(stored: str | None) -> str:
    return stored if stored in CHOICES else UNSET


def refer_as(conn: Conn, user_id: str | None) -> str | None:
    """The person's choice, or None when unset or unknown."""
    if not user_id:
        return None
    row = conn.execute("SELECT refer_as FROM person_settings WHERE user_id = %s", (user_id,)).fetchone()
    value = row["refer_as"] if row else None
    return value if value in CHOICES else None


def set_refer_as(conn: Conn, user_id: str, value: object) -> str:
    """Store the person's choice (an upsert: the settings row may not exist yet). Returns the wire value."""
    stored = parse(value)
    conn.execute(
        "INSERT INTO person_settings (user_id, refer_as) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET refer_as = EXCLUDED.refer_as",
        (user_id, stored),
    )
    return wire(stored)


def speaker_gender(choice: str | None) -> str | None:
    """mayura:v1's `speaker_gender` for this choice: Female, Male, or None (left out: neutral)."""
    return _GENDER.get(choice or "")
