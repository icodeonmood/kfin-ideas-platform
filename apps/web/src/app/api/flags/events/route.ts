import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { bodyOf, UUID } from "@/server/drafts";
import {
  EXPOSURE_EVENTS,
  FLAG_EVENTS,
  FLAG_SCREENS,
  isFlagKey,
  logFlagEvent,
  needsDraft,
  ownDraft,
  variantOn,
} from "@/server/flag-events";

const refused = (code: string, field?: string) =>
  NextResponse.json(
    { error: { code, message: "Something went wrong. Please try again.", ...(field ? { field } : {}) } },
    { status: 422, headers: { "Cache-Control": "no-store" } },
  );

/**
 * POST /api/flags/events `{ flag, event, outcome, screen, draft_id? }` — one deciding event the tables do not hold
 * already, as codes (P-DECISIONS.experiments, BLD-C174): S3's listening at once and its voice notes sent as heard or
 * corrected; S2's draft reaching Check it and the check-first comparison.
 *
 * Only the events and outcomes FLAG_EVENTS lists, on a screen the flag changes; anything else is `422`. Every S2 event
 * and S3's notes name a draft of the person's own (`422` otherwise, and for a draft id that is not a UUID); those are
 * kept once per draft and outcome, so a flood writes nothing more. Two events also log the exposure through lane A's
 * reader, for the screen they name, when only the browser can tell the variant changes something (BLD-C173): S3's
 * phone S-04 (`s3.exposure`), and S2's close match on a Check it opened fresh (`s2.check` close_match). The server
 * decides the variant; nothing is logged while the flag is off. `204` once accepted: logging never fails a screen.
 */
export async function POST(request: Request) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  const { flag, event, outcome, screen } = body;
  if (
    !isFlagKey(flag) ||
    typeof event !== "string" ||
    typeof outcome !== "string" ||
    typeof screen !== "string" ||
    !FLAG_SCREENS[flag].includes(screen) ||
    !(FLAG_EVENTS[flag][event] ?? []).includes(outcome)
  )
    return refused("event_invalid");
  let draftId: string | null = null;
  if (body.draft_id !== undefined && body.draft_id !== null) {
    if (typeof body.draft_id !== "string" || !UUID.test(body.draft_id))
      return refused("draft_invalid", "draft_id");
    draftId = body.draft_id;
  }
  if (needsDraft(event) && !draftId) return refused("draft_required", "draft_id");
  if (draftId && !(await ownDraft(me.contributorCode, draftId))) return refused("draft_invalid", "draft_id");

  const exposure = EXPOSURE_EVENTS[event];
  if (exposure && exposure.outcome === outcome) {
    if (screen !== exposure.screen) return refused("event_invalid");
    await variantOn(me, flag, screen); // lane A logs it, once per person, screen and variant
  }
  if (event !== "s3.exposure")
    await logFlagEvent({ userId: me.id, key: flag, event, outcome, screen, draftId });
  return new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
