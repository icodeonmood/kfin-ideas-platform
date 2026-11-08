import { sql } from "kysely";
import { NextResponse } from "next/server";

import { getDb } from "@/server/db";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await sql`select 1`.execute(getDb());
  } catch {
    log.error("health.db_unreachable");
    return NextResponse.json({ status: "degraded" }, { status: 503 });
  }
  return NextResponse.json({ status: "ok" }, { headers: { "Cache-Control": "no-store" } });
}
