import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { myShowcase, saveShowcase } from "@/server/ones";

/** GET /api/me/one/showcase — the One's Showcase brief (DEC-086); 403 for anyone who is not a One. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    const brief = await myShowcase(me);
    return brief ? NextResponse.json(brief) : NextResponse.json({ error: "not_a_one" }, { status: 403 });
  } catch (err) {
    return asResponse(err);
  }
}

/** PUT /api/me/one/showcase — the One saves their own words for the seven parts. */
export async function PUT(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await saveShowcase(me, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
