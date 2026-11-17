import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { onesPosts } from "@/server/wall";

/** GET /api/ones/posts — what the Ones posted, newest first, for Home's fan (A-API.ones-posts, L-ONES.rules/7). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return onesPosts(me);
}
