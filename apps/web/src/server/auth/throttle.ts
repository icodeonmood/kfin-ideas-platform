/**
 * A small in-memory limit on how often the sign-in routes may write a `sign_in_intents` row (BLD-A177). Starting
 * single sign-on needs no session, so without it anyone could fill the table. Per client address, and overall.
 *
 * Over the limit, sign-in still works: the destination travels in the sealed sign-in cookie instead of a row, so the
 * person still lands where they were going. Only the switch to an email code mid-way loses it (L-AUTH.rules/4).
 * One process's memory is enough: the web app runs as one process per node, and the overall cap bounds the table
 * even if an address is spoofed.
 */
import type { NextRequest } from "next/server";

export class WindowLimiter {
  private hits = new Map<string, number[]>();

  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly maxKeys = 10_000,
  ) {}

  /** Counts one hit for the key and says whether it is within the limit. */
  take(key: string, nowMs: number): boolean {
    const since = nowMs - this.windowMs;
    const recent = (this.hits.get(key) ?? []).filter((t) => t > since);
    if (recent.length >= this.limit) {
      this.hits.set(key, recent);
      return false;
    }
    recent.push(nowMs);
    this.hits.delete(key); // re-insert, so the map's order is oldest use first
    this.hits.set(key, recent);
    while (this.hits.size > this.maxKeys) this.hits.delete(this.hits.keys().next().value!);
    return true;
  }
}

/** Per address: 20 kept destinations in 10 minutes. Overall: 300 a minute. */
export const PER_ADDRESS = { limit: 20, windowMs: 10 * 60_000 };
export const OVERALL = { limit: 300, windowMs: 60_000 };

const perAddress = new WindowLimiter(PER_ADDRESS.limit, PER_ADDRESS.windowMs);
const overall = new WindowLimiter(OVERALL.limit, OVERALL.windowMs, 1);

/**
 * The client's address as the nearest proxy saw it: the last X-Forwarded-For entry (earlier ones are whatever the
 * client sent), else X-Real-IP. Never logged.
 */
export function clientAddress(request: Pick<NextRequest, "headers">): string {
  const forwarded = request.headers.get("x-forwarded-for");
  const last = forwarded?.split(",").pop()?.trim();
  return (last || request.headers.get("x-real-ip")?.trim() || "unknown").slice(0, 64);
}

/** Whether this request may write a kept destination now. */
export function mayKeepIntent(request: Pick<NextRequest, "headers">, nowMs = Date.now()): boolean {
  return perAddress.take(clientAddress(request), nowMs) && overall.take("all", nowMs);
}
