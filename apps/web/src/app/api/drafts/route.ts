import { NextResponse, type NextRequest } from "next/server";

import { IDEMPOTENCY_HEADER } from "@/lib/contracts/api";
import { authorize } from "@/server/auth/authorize";
import { bodyOf, deviceOf, draftError, drafts, noStore } from "@/server/drafts";

/** GET /api/drafts?recent=1 — the person's drafts, newest first, for the "existing draft" prompt, the side bar and
 * My ideas → Drafts; `archived=1` lists archived ones to restore (A-API.drafts, L-DRAFT.autosave/6, /8). */
export async function GET(request: NextRequest) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    const archived = request.nextUrl.searchParams.get("archived") === "1";
    const { body } = await drafts.list(me, deviceOf(request), archived);
    return NextResponse.json(body, { headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}

/** POST /api/drafts `{ text?, text_en?, files?, channel }` — a draft, made on the first pause in typing or by
 * sending from Home (A-API.drafts). Takes an Idempotency-Key (A-API.conventions/3). Returns `Draft` and the run its
 * first message started, if any; the parts arrive on the stream. */
export async function POST(request: NextRequest) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  try {
    const { status, body: out } = await drafts.create(me, deviceOf(request), {
      channel: typeof body.channel === "string" ? body.channel : "web",
      ...(typeof body.text === "string" ? { text: body.text } : {}),
      ...(typeof body.text_en === "string" ? { text_en: body.text_en } : {}),
      ...(typeof body.via === "string" ? { via: body.via } : {}),
      ...(Array.isArray(body.files) ? { files: body.files.filter((f) => typeof f === "string") } : {}),
      idempotency_key: request.headers.get(IDEMPOTENCY_HEADER) ?? undefined,
    });
    return NextResponse.json(out, { status, headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
