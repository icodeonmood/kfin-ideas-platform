"use client";
/**
 * The browser's call for the S1 to S3 experiments (P-DECISIONS.experiments, BLD-C174): a deciding event, as codes.
 * Fire and forget: logging never gets in the way of the screen. The variant is never sent: the server decides it.
 * Exposures are lane A's, logged on the server as the screen renders (`flagVariant`, BLD-A216).
 */
import type { FlagKey } from "./flags";

function post(path: string, body: Record<string, unknown>): void {
  try {
    void fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
      cache: "no-store",
    }).catch(() => undefined);
  } catch {
    // logging never fails a screen
  }
}

/** One deciding event, as codes. */
export function flagEvent(
  flag: FlagKey,
  event: string,
  outcome: string,
  screen: string,
  draftId?: string | null,
): void {
  post("/api/flags/events", { flag, event, outcome, screen, ...(draftId ? { draft_id: draftId } : {}) });
}
