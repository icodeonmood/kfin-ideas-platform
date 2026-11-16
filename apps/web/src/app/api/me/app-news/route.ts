import { NextResponse, type NextRequest } from "next/server";

import { auditIp, signedIn } from "@/server/auth/authorize";
import { readJson } from "@/server/http";
import { setAppNews } from "@/server/ways";

/** POST /api/me/app-news — {want: boolean}: tell me when the 1% Club app is out, or stop (S-H3, L-NOTIFY/7). */
export async function POST(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const body = await readJson(request);
  const want = body.want === undefined ? true : body.want;
  if (typeof want !== "boolean") return NextResponse.json({ error: "bad_request" }, { status: 400 });
  return NextResponse.json({ want: await setAppNews(me, want, auditIp(request.headers)) });
}
