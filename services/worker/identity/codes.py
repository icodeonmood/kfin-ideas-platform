"""Contributor codes and the employee-ID hash (§2.3). Same algorithm as apps/web/src/server/identity/codes.ts.

- Contributor code: `CTR-` + the first 6 hex characters of HMAC-SHA256(employee ID, secret); 8 on a collision.
- `users.emp_id_hash`: HMAC-SHA256 of "emp:" + employee ID with the same secret. A different input on purpose:
  if it shared the code's input, anyone reading `users` could derive codes and bypass `contributor_map`,
  and deleting a map row would no longer anonymise the person (§2.5).

The secret comes only from the environment (CONTRIBUTOR_HMAC_SECRET); there is no default in code.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from core.db import Conn

DEV_PLACEHOLDER = "change-me"
MIN_SECRET_CHARS_OUTSIDE_DEV = 32


class SecretMissing(RuntimeError):
    pass


def _secret() -> bytes:
    from core.config import get_settings  # reads the environment (and .env for local runs)

    value = get_settings().contributor_hmac_secret
    if not value:
        raise SecretMissing("CONTRIBUTOR_HMAC_SECRET is not set")
    if os.environ.get("APP_ENV", "dev") in {"uat", "prod"} and (
        value == DEV_PLACEHOLDER or len(value) < MIN_SECRET_CHARS_OUTSIDE_DEV
    ):
        raise SecretMissing("CONTRIBUTOR_HMAC_SECRET is a placeholder or too short for this environment")
    return value.encode("utf-8")


def normalise_employee_id(employee_id: str) -> str:
    return employee_id.strip().upper()


def _hmac_hex(message: str) -> str:
    return hmac.new(_secret(), message.encode("utf-8"), hashlib.sha256).hexdigest()


def contributor_code(employee_id: str, length: int = 6) -> str:
    return "CTR-" + _hmac_hex(normalise_employee_id(employee_id))[:length]


def emp_id_hash(employee_id: str) -> str:
    return _hmac_hex("emp:" + normalise_employee_id(employee_id))


def email_key_hash(email: str) -> str:
    """Stand-in for emp_id_hash when SSO releases no employee ID and HR has no match (open point O2)."""
    return _hmac_hex("email:" + email.strip().lower())


def assign_contributor_code(conn: Conn, user_id: str, employee_key: str) -> str:
    """Give `user_id` its code, extending to 8 characters if the 6-character one belongs to someone else."""
    existing = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
    ).fetchone()
    if existing:
        return str(existing["contributor_code"])
    for length in (6, 8):
        code = contributor_code(employee_key, length)
        owner = conn.execute(
            "SELECT user_id FROM contributor_map WHERE contributor_code = %s", (code,)
        ).fetchone()
        if owner is None:
            conn.execute(
                "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, user_id)
            )
            return code
    raise RuntimeError("contributor code collision at 8 characters")
