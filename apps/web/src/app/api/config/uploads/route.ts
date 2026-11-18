import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { uploadConfig } from "@/server/files";

/** GET /api/config/uploads (A-API.files): `{ limit_mb, types[], help_text }`, so every drop area writes its help
 * line from the one configured limit and type list (C-FILE.uploader/1, BLD-E007). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await uploadConfig(), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json(
      { error: { code: "files_unavailable", message: "That didn’t go through. Try again in a moment." } },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
