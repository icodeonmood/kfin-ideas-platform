"use client";
/**
 * The browser's two calls for the S1 to S3 experiments (P-DECISIONS.experiments, BLD-C173, BLD-C174): one exposure per
 * page load, and a deciding event, as codes. Fire and forget: logging never gets in the way of the screen. The
 * variant is never sent: the server decides it.
 */
import { useEffect, useRef } from "react";

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

/** One exposure per page load, once `when` is true: the screen that differs for this flag was rendered. */
export function useFlagExposure(flag: FlagKey, screen: string, when: boolean): void {
  const sent = useRef<string | null>(null);
  useEffect(() => {
    if (!when) return;
    const key = `${flag}:${screen}`;
    if (sent.current === key) return;
    sent.current = key;
    post("/api/flags/exposure", { flag, screen });
  }, [flag, screen, when]);
}
