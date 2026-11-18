/**
 * The admin page's calls to the worker (lane A; J-ONE steps 1, 2, 3 and 6): build team, shipped, measurements,
 * Finance's confirmation, Founding Ones, removing a One and "Take off the Wall". The route handler has checked the
 * capability; the worker checks the person's grants again and writes the audit rows. Errors pass through in the
 * pack's shape (A-API.conventions/2).
 */
import { NextResponse } from "next/server";

import { workerFetch } from "../worker";

export const IDEA_REF = /^IDEA-[0-9]{4}-[0-9]{6}$/;
export const MARKS = ["day_30", "day_90"] as const;

/** Forward one call, with the signed-in person named in the body, and return the worker's answer as it is. */
export async function programmeCall(
  method: "GET" | "POST" | "PUT",
  path: string,
  userId: string,
  body: Record<string, unknown> = {},
): Promise<NextResponse> {
  const res = await workerFetch(`/internal/admin${path}`, {
    method,
    headers: method === "GET" ? undefined : { "Content-Type": "application/json" },
    body: method === "GET" ? undefined : JSON.stringify({ ...body, user_id: userId }),
  });
  const json = (await res.json().catch(() => ({ error: { code: "worker_error", message: "" } }))) as unknown;
  return NextResponse.json(json, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export const badRef = () =>
  NextResponse.json(
    {
      error: {
        code: "not_found",
        message: "No idea has that reference. Check it reads like IDEA-2026-000123.",
        field: "idea",
      },
    },
    { status: 404 },
  );
