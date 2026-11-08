/**
 * Defence in depth: route handlers re-check the capability the proxy already checked (B2 review), so a gap in
 * path matching can never expose a handler on its own.
 */
import { NextResponse } from "next/server";

import { can } from "@/lib/rbac";

import { currentUser, type CurrentUser } from "./current";

export async function authorize(capability: string): Promise<CurrentUser | NextResponse> {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  if (!me.privacyAccepted) return NextResponse.json({ error: "privacy_notice_required" }, { status: 403 });
  if (!can(me.roles, capability)) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  return me;
}

/** The client address for audit rows, only when a trusted edge sets it (otherwise anyone can forge it). */
export function auditIp(headers: Headers): string | null {
  if (process.env.TRUST_PROXY_HEADERS !== "true") return null;
  return headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null;
}

/** A string field from a JSON body, or undefined if it is missing or not a string. */
export const str = (value: unknown, max = 2000): string | undefined =>
  typeof value === "string" && value.length <= max ? value : undefined;
