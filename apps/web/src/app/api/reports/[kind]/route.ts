import { NextResponse, type NextRequest } from "next/server";

import { report } from "@/server/appeals";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";

/** GET /api/reports/{fairness|calibration}?quarter=YYYY-Qn — whole quarters, counts only (§3.8, §5.4, BLD-223). */

export async function GET(request: NextRequest, { params }: { params: Promise<{ kind: string }> }) {
  const me = await authorize("view_fairness_reports");
  if (me instanceof NextResponse) return me;
  const kind = (await params).kind;
  if (kind !== "fairness" && kind !== "calibration") {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  try {
    return NextResponse.json(
      await report(me, kind, request.nextUrl.searchParams.get("quarter") ?? undefined),
    );
  } catch (err) {
    return asResponse(err);
  }
}
