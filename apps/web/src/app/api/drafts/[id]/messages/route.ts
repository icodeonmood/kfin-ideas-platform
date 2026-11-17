import { NextResponse, type NextRequest } from "next/server";

import { IDEMPOTENCY_HEADER } from "@/lib/contracts/api";
import { authorize } from "@/server/auth/authorize";
import { bodyOf, deviceOf, draftError, drafts, noStore } from "@/server/drafts";

/** POST /api/drafts/{id}/messages `{ text, via, files?, text_en?, at?, defer_run? }` — one more message (A-API.drafts).
 * Hidden first (DEC-103), the person's own words sealed for them, then only the parts it could change are built
 * again: `202` with the run id and the message as kept; parts arrive on the stream. `text_en` is the English copy of
 * a voice note or another language, context only (DEC-108). A message typed offline is sent again with the same
 * Idempotency-Key and its own time `at` (L-DRAFT.autosave/7); it is kept once. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  try {
    const id = encodeURIComponent((await params).id);
    const { body: out } = await drafts.write(me, deviceOf(request), "POST", `${id}/messages`, {
      text: body.text,
      via: typeof body.via === "string" ? body.via : "typed",
      ...(typeof body.text_en === "string" ? { text_en: body.text_en } : {}),
      ...(typeof body.at === "string" ? { at: body.at } : {}),
      ...(body.defer_run === true ? { defer_run: true } : {}),
      ...(Array.isArray(body.files) ? { files: body.files.filter((f) => typeof f === "string") } : {}),
      client_id: request.headers.get(IDEMPOTENCY_HEADER) ?? undefined,
    });
    return NextResponse.json(out, { status: 202, headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
