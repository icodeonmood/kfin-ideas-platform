import { NextResponse } from "next/server";

import { SubmissionError } from "./submissions";

/** Known errors become JSON with a code (never echoed text); anything else is rethrown. */
export function asResponse(err: unknown): NextResponse {
  if (err instanceof SubmissionError) {
    return NextResponse.json(
      { error: err.code, ...(err.details !== undefined ? { details: err.details } : {}) },
      { status: err.status },
    );
  }
  throw err;
}

export const readJson = async (request: Request): Promise<Record<string, unknown>> =>
  ((await request.json().catch(() => ({}))) ?? {}) as Record<string, unknown>;
