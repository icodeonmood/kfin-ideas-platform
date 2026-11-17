import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { profile } from "@/server/wall";

/**
 * GET /api/me/profile — the signed-in person with their points and settings (A-API.me `GET /me`, S-H6). Always
 * their own: the route takes no id. Points are private to the person (P-PRODUCT.privacy).
 */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return profile(me);
}
