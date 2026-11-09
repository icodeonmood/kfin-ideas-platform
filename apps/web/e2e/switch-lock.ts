/**
 * Specs that flip the same shared kill switch must not overlap: one spec switching it off in its `finally`
 * would pull it from under the other (Playwright runs files in parallel). `withSwitchLock` serialises them
 * with a lock directory (mkdir is atomic) under test-results, which Playwright clears at the start of a run.
 * A lock older than STALE_MS is taken over, so a killed run cannot block the next one.
 */
import { mkdirSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = join(__dirname, "..", "test-results", ".switch-locks");
const STALE_MS = 10 * 60_000;

export async function withSwitchLock<T>(name: string, fn: () => Promise<T>, waitMs = 8 * 60_000): Promise<T> {
  mkdirSync(ROOT, { recursive: true });
  const dir = join(ROOT, name);
  const until = Date.now() + waitMs;
  for (;;) {
    try {
      mkdirSync(dir);
      break;
    } catch {
      try {
        if (Date.now() - statSync(dir).mtimeMs > STALE_MS) rmSync(dir, { recursive: true, force: true });
      } catch {
        // gone between the two calls: try again
      }
      if (Date.now() > until) throw new Error(`switch lock ${name} still held after ${waitMs} ms`);
      await new Promise((r) => setTimeout(r, 1_000));
    }
  }
  try {
    return await fn();
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
