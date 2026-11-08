import { sql } from "kysely";
import { NextResponse, type NextRequest } from "next/server";

import { getDb } from "@/server/db";
import { log } from "@/server/log";
import { workerFetch } from "@/server/worker";

export const dynamic = "force-dynamic";

/** GET /api/health — the database answers. `?deep=1` also checks the worker accepts this app's internal token
 * (used by the deploy smoke tests); it says only ok or not, never why. */
export async function GET(request: NextRequest) {
  try {
    await sql`select 1`.execute(getDb());
  } catch {
    log.error("health.db_unreachable");
    return NextResponse.json({ status: "degraded" }, { status: 503 });
  }
  if (request.nextUrl.searchParams.get("deep") === "1") {
    const worker = await workerFetch("/internal/token-check")
      .then((r) => (r.ok ? "ok" : "refused"))
      .catch(() => "unreachable");
    if (worker !== "ok") log.error("health.worker_check_failed", { state: worker });
    return NextResponse.json(
      { status: worker === "ok" ? "ok" : "degraded", worker },
      { status: worker === "ok" ? 200 : 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  return NextResponse.json({ status: "ok" }, { headers: { "Cache-Control": "no-store" } });
}
