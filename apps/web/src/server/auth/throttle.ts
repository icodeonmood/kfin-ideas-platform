/**
 * A small in-memory limit on how often the sign-in routes may write a `sign_in_intents` row (BLD-A177). Starting
 * single sign-on needs no session, so without it anyone could fill the table. Per client address, and overall.
 *
 * Over the limit nobody loses their place (L-AUTH.rules/4): single sign-on carries it in the sealed sign-in cookie,
 * the callback hands it back to S-02 as `to`, and the email code carries it in a sealed place cookie. Only a draft's
 * exact part of Check it can fall back to the first part. The per-address limit is wide enough for a whole office
 * behind one address on launch day; the overall cap is what bounds the table, even if an address is spoofed. One
 * process's memory is enough: the web app runs as one process per node.
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

/**
 * Per address: 1,200 kept destinations in 10 minutes, so an office whose people all leave by one address (the whole
 * building on launch day) is not starved. Overall: 300 a minute, which bounds the table. One address can use at most
 * 40% of the overall 10-minute budget, so other offices still get rows.
 */
export const PER_ADDRESS = { limit: 1_200, windowMs: 10 * 60_000 };
export const OVERALL = { limit: 300, windowMs: 60_000 };

type Limit = { limit: number; windowMs: number };
let perAddress = new WindowLimiter(PER_ADDRESS.limit, PER_ADDRESS.windowMs);
let overall = new WindowLimiter(OVERALL.limit, OVERALL.windowMs, 1);

/** Unit tests only: fresh limiters, optionally with other limits (0 puts every write over the limit). */
export function resetLimitsForTests(per: Limit = PER_ADDRESS, all: Limit = OVERALL) {
  perAddress = new WindowLimiter(per.limit, per.windowMs);
  overall = new WindowLimiter(all.limit, all.windowMs, 1);
}

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
