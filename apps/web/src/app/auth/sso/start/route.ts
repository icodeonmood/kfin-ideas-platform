import type { NextRequest } from "next/server";

import { startSso, type StartInput } from "@/server/auth/sso";

export const dynamic = "force-dynamic";

/**
 * POST /auth/sso/start (A-API.auth): `{ intent?: { to, draft_id?, step? }, silent? }` as JSON answers
 * `{ redirect_url }` or `{ signed_in: true, to }`; the same fields from a form (S-02's buttons) answer a redirect.
 * With no intent, the attempt the browser already has is reused ("Try again" keeps where they were going).
 */
export async function POST(request: NextRequest) {
  const type = request.headers.get("content-type") ?? "";
  if (type.includes("application/json")) {
    const body = ((await request.json().catch(() => ({}))) ?? {}) as Record<string, unknown>;
    const intent = (body.intent ?? {}) as Record<string, unknown>;
    return startSso(
      request,
      { to: intent.to, draft_id: intent.draft_id, step: intent.step, silent: body.silent },
      "json",
    );
  }
  const form = await request.formData().catch(() => null);
  const field = (name: string) => {
    const v = form?.get(name);
    return typeof v === "string" && v !== "" ? v : undefined;
  };
  const input: StartInput = {
    to: field("to"),
    draft_id: field("draft_id"),
    step: field("step"),
    silent: field("silent"),
  };
  return startSso(request, input, "redirect");
}

/**
 * GET /auth/sso/start?to=/share&silent=1: what S-02's "Signing you in" state follows, so "Share a problem" on
 * Landing tries silent single sign-on (L-AUTH.rules/1) and works with scripts off.
 */
export async function GET(request: NextRequest) {
  const p = request.nextUrl.searchParams;
  const opt = (name: string) => p.get(name) ?? undefined;
  return startSso(
    request,
    { to: opt("to"), draft_id: opt("draft_id"), step: opt("step"), silent: opt("silent") },
    "link",
  );
}
