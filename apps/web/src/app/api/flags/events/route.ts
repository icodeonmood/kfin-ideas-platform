import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { bodyOf, UUID } from "@/server/drafts";
import { FLAG_EVENTS, FLAG_SCREENS, isFlagKey, logFlagEvent, ownDraft } from "@/server/flag-events";

/** POST /api/flags/events `{ flag, event, outcome, screen, draft_id? }` — one deciding event the tables do not hold
 * already, as codes (P-DECISIONS.experiments, BLD-C174): S3's listening at once and its voice notes sent as heard or
 * corrected; S2's check-first comparison. Only the events and outcomes FLAG_EVENTS lists, on a screen the flag
 * changes, and a draft only if it is the person's own. The server decides the variant (lane A's reader, BLD-A216);
 * nothing is logged while the flag is off. Always `204`: logging never fails a screen. */
export async function POST(request: Request) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  const { flag, event, outcome, screen } = body;
  const draftId = typeof body.draft_id === "string" && UUID.test(body.draft_id) ? body.draft_id : null;
  if (
    isFlagKey(flag) &&
    typeof event === "string" &&
    typeof outcome === "string" &&
    typeof screen === "string" &&
    FLAG_SCREENS[flag].includes(screen) &&
    (FLAG_EVENTS[flag][event] ?? []).includes(outcome) &&
    (draftId === null || (await ownDraft(me.contributorCode, draftId)))
  ) {
    await logFlagEvent({ userId: me.id, key: flag, event, outcome, screen, draftId });
  }
  return new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
