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


def main(argv: list[str] | None = None) -> int:
    """Ops CLI for UAT and prod, where there are no dev personas: grant the first admin, who then uses the Admin page.

    python -m identity.grants grant --employee-id <ID> --role admin --reason "…" --actor ops:<staff code>
    """
    import argparse

    from core.db import connect
    from identity.codes import emp_id_hash

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grant")
    g.add_argument("--employee-id", required=True)
    g.add_argument("--role", required=True, choices=sorted(ROLES))
    g.add_argument("--scope")
    g.add_argument("--reason", required=True)
    g.add_argument("--actor", required=True)
    args = parser.parse_args(argv)
    if len(args.reason.strip()) < 10:
        print("reason: at least 10 characters")
        return 2
    with connect(autocommit=True) as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE emp_id_hash = %s AND active", (emp_id_hash(args.employee_id),)
        ).fetchone()
        if user is None:
            print("no active person with that employee ID (they sign in once, or come in with the HR import)")
            return 1
        created = grant(conn, str(user["id"]), args.role, args.scope, actor=args.actor, reason=args.reason)
    print("granted" if created else "already granted")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
