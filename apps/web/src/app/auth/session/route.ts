import { NextResponse, type NextRequest } from "next/server";
import { sql } from "kysely";

import { draftLookup } from "@/server/auth/drafts";
import { ATTEMPT_COOKIE, attemptKeyHash, draftFromPath, intentStore } from "@/server/auth/intents";
import { expiredSession, readSession, safeNext, SESSION_COOKIE } from "@/server/auth/session";
import { getDb } from "@/server/db";
import { askingDevice } from "@/server/shell";

export const dynamic = "force-dynamic";

const noStore = { "Cache-Control": "no-store" };

/**
 * GET /auth/session (A-API.auth) → `{ person, expires_at, intent? }`, or 401 `expired` with the open draft
 * (`?draft=/share/<id>`) when the session ran out by time (L-AUTH.rules/5), or 401 `sign_in_required`.
 */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const session = await readSession(token);
  if (session) {
    const r = await sql<{ id: string; name: string; email: string; expires_at: Date }>`
      SELECT u.id, u.name, u.email, s.expires_at FROM users u JOIN sessions s ON s.user_id = u.id
      WHERE u.id = ${session.userId} AND s.revoked_at IS NULL ORDER BY s.expires_at DESC LIMIT 1
    `.execute(getDb());
    const me = r.rows[0];
    const key = request.cookies.get(ATTEMPT_COOKIE)?.value;
    const intent =
      key && key.length <= 128 ? await intentStore().find(attemptKeyHash(key), new Date()) : null;
    return NextResponse.json(
      {
        person: me ? { id: me.id, name: me.name, email: me.email } : { id: session.userId },
        expires_at: me?.expires_at ?? null,
        ...(intent ? { intent: { to: intent.to, draft_id: intent.draftId, step: intent.step } } : {}),
      },
      { headers: noStore },
    );
  }
  const expired = await expiredSession(token);
  if (!expired) return NextResponse.json({ error: "sign_in_required" }, { status: 401, headers: noStore });
  const open = draftFromPath(safeNext(request.nextUrl.searchParams.get("draft")));
  const card = open
    ? await draftLookup().card(expired.userId, open.draftId, (await askingDevice()).id)
    : null;
  return NextResponse.json(
    {
      error: "expired",
      ...(card
        ? {
            draft: {
              id: card.id,
              title: card.title,
              saved_at: card.savedAt.toISOString(),
              // A-API.auth: E-ENTITIES.draft's saved_on, from the asking browser's side (BLD-A227)
              ...(card.savedOn
                ? { saved_on: { device: card.savedOn.device, this_device: card.savedOn.thisDevice } }
                : {}),
              step: card.step,
            },
          }
        : {}),
    },
    { status: 401, headers: noStore },
  );
}
