/**
 * Role grants from the Admin page (L-AUDIT.permissions: admin only). Every change is audited with a reason.
 * The pack's roles (E-ENUMS.roles): the review desk, the Ones Committee, the office and launch screens, and admins,
 * plus InfoSec and HR, who flip their kill switches (§7.6). The old committee, panel, group, sponsor and CEO roles
 * are retired (DEC-102, DEC-106) and can no longer be given; grants already made stay listed until they are
 * removed. `build_team` is given per idea when the team is chosen, never here (L-DECIDE.after).
 */
import { sql } from "kysely";

import { getDb } from "../db";

export const GRANTABLE_ROLES = ["reviewer", "committee", "display", "admin", "infosec", "hr"] as const;
export type GrantableRole = (typeof GRANTABLE_ROLES)[number];

// Roles whose grant must name what it covers. None of the pack's org-wide roles takes a scope.
const SCOPE_RULES: Partial<Record<GrantableRole, RegExp>> = {};

export class RoleError extends Error {
  constructor(
    public code: string,
    public status = 400,
  ) {
    super(code);
  }
}

export const REASON_MIN_CHARS = 10;
const ROLE_LOCK = 4_201_109_002; // pg advisory lock: one role change at a time

export async function listGrants() {
  return getDb()
    .selectFrom("role_grants as g")
    .innerJoin("users as u", "u.id", "g.user_id")
    .select(["g.id", "g.role", "g.scope_id", "g.valid_from", "u.name", "u.email", "u.lob_id"])
    .where("g.valid_from", "<=", new Date())
    .where((eb) => eb.or([eb("g.valid_to", "is", null), eb("g.valid_to", ">", new Date())]))
    .orderBy("g.role")
    .orderBy("u.name")
    .execute();
}

export async function grantRole(input: {
  email: string;
  role: string;
  scope: string | null;
  reason: string;
  actor: string;
  actorUserId: string;
}) {
  const reason = input.reason.trim();
  if (!GRANTABLE_ROLES.includes(input.role as GrantableRole)) throw new RoleError("unknown_role");
  if (reason.length < REASON_MIN_CHARS) throw new RoleError("reason_required");
  const rule = SCOPE_RULES[input.role as GrantableRole];
  const scope = input.scope?.trim() || null;
  if (rule && (!scope || !rule.test(scope))) throw new RoleError("scope_required");
  if (!rule && scope) throw new RoleError("scope_not_allowed");

  return getDb()
    .transaction()
    .execute(async (trx) => {
      await sql`SELECT pg_advisory_xact_lock(${ROLE_LOCK})`.execute(trx);
      const user = await trx
        .selectFrom("users")
        .select(["id", "active"])
        .where(sql`lower(email)`, "=", input.email.trim().toLowerCase())
        .executeTakeFirst();
      if (!user || !user.active) throw new RoleError("no_such_person", 404);
      const existing = await trx
        .selectFrom("role_grants")
        .select("id")
        .where("user_id", "=", user.id)
        .where("role", "=", input.role)
        .where(sql<boolean>`scope_id IS NOT DISTINCT FROM ${scope}`)
        .where((eb) => eb.or([eb("valid_to", "is", null), eb("valid_to", ">", new Date())]))
        .executeTakeFirst();
      if (existing) throw new RoleError("already_granted", 409);
      const grant = await trx
        .insertInto("role_grants")
        .values({ user_id: user.id, role: input.role, scope_id: scope, granted_by: input.actorUserId })
        .returning("id")
        .executeTakeFirstOrThrow();
      await trx
        .insertInto("audit_log")
        .values({
          actor: input.actor,
          action: "role.grant",
          entity: `role_grant:${grant.id}`,
          after: JSON.stringify({ user_id: user.id, role: input.role, scope }),
          reason,
        })
        .execute();
      return grant.id;
    });
}

export async function revokeRole(input: { grantId: string; reason: string; actor: string }) {
  const reason = input.reason.trim();
  if (reason.length < REASON_MIN_CHARS) throw new RoleError("reason_required");
  await getDb()
    .transaction()
    .execute(async (trx) => {
      // One role change at a time: two admins revoking each other at once cannot leave zero admins.
      await sql`SELECT pg_advisory_xact_lock(${ROLE_LOCK})`.execute(trx);
      const grant = await trx
        .selectFrom("role_grants")
        .select(["id", "user_id", "role", "scope_id"])
        .where("id", "=", input.grantId)
        .where((eb) => eb.or([eb("valid_to", "is", null), eb("valid_to", ">", new Date())]))
        .forUpdate()
        .executeTakeFirst();
      if (!grant) throw new RoleError("no_such_grant", 404);
      if (grant.role === "admin") {
        // Only admins who can still sign in count.
        const admins = await trx
          .selectFrom("role_grants as g")
          .innerJoin("users as u", "u.id", "g.user_id")
          .select(sql<number>`count(*)::int`.as("n"))
          .where("g.role", "=", "admin")
          .where("u.active", "=", true)
          .where((eb) => eb.or([eb("g.valid_to", "is", null), eb("g.valid_to", ">", new Date())]))
          .executeTakeFirstOrThrow();
        if (admins.n <= 1) throw new RoleError("last_admin", 409);
      }
      await trx.updateTable("role_grants").set({ valid_to: new Date() }).where("id", "=", grant.id).execute();
      await trx
        .insertInto("audit_log")
        .values({
          actor: input.actor,
          action: "role.revoke",
          entity: `role_grant:${grant.id}`,
          before: JSON.stringify({ user_id: grant.user_id, role: grant.role, scope: grant.scope_id }),
          reason,
        })
        .execute();
    });
}
