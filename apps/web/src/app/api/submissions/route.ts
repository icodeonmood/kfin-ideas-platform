import { NextResponse } from "next/server";

/** POST /api/submissions creates a draft (§8). Built in B3; the kill switch already guards it (proxy.ts). */
export async function POST() {
  return NextResponse.json({ error: "not_built", block: "B3" }, { status: 501 });
}
