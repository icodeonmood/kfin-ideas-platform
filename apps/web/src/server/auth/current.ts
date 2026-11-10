/** The signed-in person, for route handlers and server components. Re-validates the session every time. */
import { cookies } from "next/headers";

import { effectiveRoles, navFor, type NavItem } from "@/lib/rbac";

import { getDb } from "../db";
import { switchStates } from "../killswitch";
import { readSession, SESSION_COOKIE } from "./session";

export type CurrentUser = {
  id: string;
  name: string;
  email: string;
  lobId: string | null;
  roleFamily: string | null;
  contributorCode: string | null;
  grants: Array<{ role: string; scope_id: string | null }>;
  roles: Set<string>;
  nav: NavItem[];
  privacyAccepted: boolean;
};

export async function currentUser(): Promise<CurrentUser | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const session = await readSession(token);
  if (!session) return null;
  const user = await getDb()
    .selectFrom("users")
    .leftJoin("contributor_map", "contributor_map.user_id", "users.id")
    .select([
      "users.id",
      "users.name",
      "users.email",
      "users.lob_id",
      "users.role_family",
      "contributor_code",
    ])
    .where("users.id", "=", session.userId)
    .executeTakeFirst();
  if (!user) return null;
  const roles = effectiveRoles(session.grants);
  // Menu items tied to a switch (BLD-227) follow it; the states are cached for 10 seconds (BLD-006).
  const states = await switchStates();
  const switchesOn = new Set([...states].filter(([, state]) => state === "on").map(([name]) => name));
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    lobId: user.lob_id,
    roleFamily: user.role_family,
    contributorCode: user.contributor_code,
    grants: session.grants,
    roles,
    nav: navFor(roles, switchesOn),
    privacyAccepted: session.privacyAccepted,
  };
}
