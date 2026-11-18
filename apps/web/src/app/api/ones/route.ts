import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { wallOnes } from "@/server/ones";

/** GET /api/ones — The Ones everyone may see (wall, home, screens); `ones.public` off answers 503 at the proxy. */
export async function GET() {
  const auth = await authorize("see_org_ideas");
  if (auth instanceof NextResponse) return auth;
  try {
    return NextResponse.json(await wallOnes());
  } catch (err) {
    return asResponse(err);
  }
}
