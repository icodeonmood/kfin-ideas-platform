"""Role grants (§2.5 role_grants, §3.1). Every grant and revocation writes `audit_log` in the same transaction."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from core.db import Conn

ROLES = {
    "reviewer", "lob_committee", "core_committee", "core_chair", "appeal_panel",
    "working_group", "sponsor", "admin", "infosec", "hr",
}  # fmt: skip


def grant(conn: Conn, user_id: str, role: str, scope: str | None, *, actor: str, reason: str) -> bool:
    """Grant `role` (idempotent). Returns True if a new grant was created."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role}")
    with conn.transaction():
        existing = conn.execute(
            "SELECT id FROM role_grants WHERE user_id = %s AND role = %s AND scope_id IS NOT DISTINCT FROM %s "
            "AND (valid_to IS NULL OR valid_to > now())",
            (user_id, role, scope),
        ).fetchone()
        if existing:
            return False
        row = conn.execute(
            "INSERT INTO role_grants (user_id, role, scope_id) VALUES (%s, %s, %s) RETURNING id",
            (user_id, role, scope),
        ).fetchone()
        assert row is not None
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after, reason) VALUES (%s, 'role.grant', %s, %s, %s)",
            (
                actor,
                f"role_grant:{row['id']}",
                Jsonb({"user_id": user_id, "role": role, "scope": scope}),
                reason,
            ),
        )
    return True
